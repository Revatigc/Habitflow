from collections import defaultdict
from datetime import date, datetime, time, timedelta
from threading import Lock
from time import time as current_time

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..auth.jwt import current_user
from ..ai import client as ai_client
from ..ai.prompts import build_weekly_summary_prompt
from ..ai.schemas import WeeklySummaryResponse
from ..database import db
from ..models.core import FocusSession, Habit, HabitLog, Task, User

router = APIRouter()


class HabitIn(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    category: str = "General"
    frequency: str = "daily"
    target: int = Field(default=1, ge=1, le=100)


class TaskIn(BaseModel):
    title: str = Field(min_length=1, max_length=180)
    description: str | None = None
    priority: str = "medium"
    status: str = "todo"
    due_date: date | None = None


class FocusIn(BaseModel):
    minutes: int = Field(ge=1, le=240)


def owned(session: Session, model, item_id: int, user: User):
    item = session.get(model, item_id)
    if not item or item.user_id != user.id:
        raise HTTPException(404, "Not found")
    return item


@router.get("/habits")
def habits(session: Session = Depends(db), user: User = Depends(current_user)):
    return session.scalars(
        select(Habit).where(Habit.user_id == user.id, Habit.archived.is_(False))
    ).all()


@router.post("/habits")
def create_habit(data: HabitIn, session: Session = Depends(db), user: User = Depends(current_user)):
    item = Habit(user_id=user.id, **data.model_dump())
    session.add(item)
    session.commit()
    session.refresh(item)
    return item


@router.put("/habits/{habit_id}")
def update_habit(habit_id: int, data: HabitIn, session: Session = Depends(db), user: User = Depends(current_user)):
    item = owned(session, Habit, habit_id, user)
    for key, value in data.model_dump().items():
        setattr(item, key, value)
    session.commit()
    return item


@router.delete("/habits/{habit_id}", status_code=204)
def archive_habit(habit_id: int, session: Session = Depends(db), user: User = Depends(current_user)):
    owned(session, Habit, habit_id, user).archived = True
    session.commit()


@router.post("/habits/{habit_id}/complete")
def complete(habit_id: int, session: Session = Depends(db), user: User = Depends(current_user)):
    owned(session, Habit, habit_id, user)
    log = HabitLog(habit_id=habit_id)
    try:
        session.add(log)
        session.commit()
    except Exception:
        session.rollback()
        raise HTTPException(409, "Already completed today")
    return log


@router.delete("/habits/{habit_id}/complete", status_code=204)
def undo(habit_id: int, session: Session = Depends(db), user: User = Depends(current_user)):
    owned(session, Habit, habit_id, user)
    log = session.scalar(select(HabitLog).where(HabitLog.habit_id == habit_id, HabitLog.completed_on == date.today()))
    if log:
        session.delete(log)
        session.commit()


@router.get("/tasks")
def tasks(session: Session = Depends(db), user: User = Depends(current_user)):
    return session.scalars(select(Task).where(Task.user_id == user.id)).all()


@router.post("/tasks")
def create_task(data: TaskIn, session: Session = Depends(db), user: User = Depends(current_user)):
    item = Task(user_id=user.id, **data.model_dump())
    session.add(item)
    session.commit()
    session.refresh(item)
    return item


@router.put("/tasks/{task_id}")
def update_task(task_id: int, data: TaskIn, session: Session = Depends(db), user: User = Depends(current_user)):
    item = owned(session, Task, task_id, user)
    for key, value in data.model_dump().items():
        setattr(item, key, value)
    session.commit()
    return item


@router.delete("/tasks/{task_id}", status_code=204)
def delete_task(task_id: int, session: Session = Depends(db), user: User = Depends(current_user)):
    session.delete(owned(session, Task, task_id, user))
    session.commit()


@router.post("/focus-sessions")
def focus(data: FocusIn, session: Session = Depends(db), user: User = Depends(current_user)):
    item = FocusSession(user_id=user.id, **data.model_dump())
    session.add(item)
    session.commit()
    return item


@router.get("/analytics/weekly")
def weekly(session: Session = Depends(db), user: User = Depends(current_user)):
    """Return current workweek analytics calculated solely from persisted user data."""
    week_start = date.today() - timedelta(days=date.today().weekday())
    week_end = week_start + timedelta(days=5)

    completion_rows = session.execute(
        select(HabitLog.completed_on, func.count(HabitLog.id))
        .join(Habit)
        .where(Habit.user_id == user.id, HabitLog.completed_on >= week_start, HabitLog.completed_on < week_end)
        .group_by(HabitLog.completed_on)
    ).all()
    completions_by_day = {completed_on: count for completed_on, count in completion_rows}

    focus_rows = session.execute(
        select(FocusSession.completed_at, FocusSession.minutes).where(
            FocusSession.user_id == user.id,
            FocusSession.completed_at >= datetime.combine(week_start, time.min),
            FocusSession.completed_at < datetime.combine(week_end, time.min),
        )
    ).all()
    focus_by_day: dict[date, int] = {}
    for completed_at, minutes in focus_rows:
        focus_by_day[completed_at.date()] = focus_by_day.get(completed_at.date(), 0) + minutes

    trend = []
    for offset in range(5):
        day = week_start + timedelta(days=offset)
        completions = completions_by_day.get(day, 0)
        focus_minutes = focus_by_day.get(day, 0)
        trend.append({
            "date": day.isoformat(),
            "label": day.strftime("%a"),
            "productivity_score": min(100, completions * 10 + focus_minutes // 10),
        })

    total_completions = sum(completions_by_day.values())
    total_focus_minutes = sum(focus_by_day.values())
    productivity_score = round(sum(day["productivity_score"] for day in trend) / len(trend))
    habit_count = session.scalar(
        select(func.count(Habit.id)).where(Habit.user_id == user.id, Habit.archived.is_(False))
    ) or 0
    return {
        "habit_count": habit_count,
        "completions": total_completions,
        "focus_minutes": total_focus_minutes,
        "productivity_score": productivity_score,
        "trend": trend,
    }


@router.get("/profile")
def profile(user: User = Depends(current_user)):
    return user


# --- Rate limiting & caching for AI weekly summary ---
# Simple in-memory rate limiter: 10 requests per minute per user
_RATE_LIMIT_WINDOW = 60  # seconds
_RATE_LIMIT_MAX_REQUESTS = 10
_rate_limit_store: dict[str, list[float]] = defaultdict(list)
_rate_limit_lock = Lock()


def check_rate_limit(user_id: str) -> bool:
    """Check if the user has exceeded the rate limit.

    Returns True if allowed, False if rate limited.
    """
    now = current_time()
    with _rate_limit_lock:
        timestamps = _rate_limit_store[user_id]
        # Remove old entries outside the window
        cutoff = now - _RATE_LIMIT_WINDOW
        while timestamps and timestamps[0] < cutoff:
            timestamps.pop(0)
        if len(timestamps) >= _RATE_LIMIT_MAX_REQUESTS:
            return False
        timestamps.append(now)
        return True


# In-memory cache: key = (user_id, week_start_iso), value = (summary, expires_at)
_ai_cache: dict[tuple[str, str], tuple[str, float]] = {}
_ai_cache_lock = Lock()
_CACHE_TTL = 3600  # 1 hour


def get_cache_key(user_id: str, week_start: date) -> tuple[str, str]:
    """Generate cache key from user ID and week start date."""
    return (user_id, week_start.isoformat())


def get_cached_summary(user_id: str, week_start: date) -> str | None:
    """Get cached summary if valid."""
    key = get_cache_key(user_id, week_start)
    with _ai_cache_lock:
        entry = _ai_cache.get(key)
        if entry is None:
            return None
        summary, expires_at = entry
        if current_time() > expires_at:
            del _ai_cache[key]
            return None
        return summary


def set_cached_summary(user_id: str, week_start: date, summary: str) -> None:
    """Cache the summary with TTL."""
    key = get_cache_key(user_id, week_start)
    expires_at = current_time() + _CACHE_TTL
    with _ai_cache_lock:
        _ai_cache[key] = (summary, expires_at)


# --- Helper to compute weekly analytics (reused from weekly endpoint) ---
def compute_weekly_analytics(session: Session, user: User, week_start: date) -> dict:
    """Compute weekly analytics for a given week_start (Monday).

    This mirrors the logic in the weekly endpoint but accepts a specific week_start
    so we can use it for caching key generation.
    """
    week_end = week_start + timedelta(days=5)

    completion_rows = session.execute(
        select(HabitLog.completed_on, func.count(HabitLog.id))
        .join(Habit)
        .where(Habit.user_id == user.id, HabitLog.completed_on >= week_start, HabitLog.completed_on < week_end)
        .group_by(HabitLog.completed_on)
    ).all()
    completions_by_day = {completed_on: count for completed_on, count in completion_rows}

    focus_rows = session.execute(
        select(FocusSession.completed_at, FocusSession.minutes).where(
            FocusSession.user_id == user.id,
            FocusSession.completed_at >= datetime.combine(week_start, time.min),
            FocusSession.completed_at < datetime.combine(week_end, time.min),
        )
    ).all()
    focus_by_day: dict[date, int] = {}
    for completed_at, minutes in focus_rows:
        focus_by_day[completed_at.date()] = focus_by_day.get(completed_at.date(), 0) + minutes

    trend = []
    for offset in range(5):
        day = week_start + timedelta(days=offset)
        completions = completions_by_day.get(day, 0)
        focus_minutes = focus_by_day.get(day, 0)
        trend.append({
            "date": day.isoformat(),
            "label": day.strftime("%a"),
            "productivity_score": min(100, completions * 10 + focus_minutes // 10),
        })

    total_completions = sum(completions_by_day.values())
    total_focus_minutes = sum(focus_by_day.values())
    productivity_score = round(sum(day["productivity_score"] for day in trend) / len(trend))
    habit_count = session.scalar(
        select(func.count(Habit.id)).where(Habit.user_id == user.id, Habit.archived.is_(False))
    ) or 0
    return {
        "habit_count": habit_count,
        "completions": total_completions,
        "focus_minutes": total_focus_minutes,
        "productivity_score": productivity_score,
        "trend": trend,
    }


@router.get("/ai/weekly-summary", response_model=WeeklySummaryResponse)
def weekly_summary(
    session: Session = Depends(db),
    user: User = Depends(current_user),
):
    """Return an AI-generated weekly summary for the current workweek.

    - Reuses the same aggregation logic as /api/analytics/weekly
    - Caches the result for 1 hour per user per week
    - Rate limited to 10 requests/minute per user
    - Degrades gracefully if ANTHROPIC_API_KEY is not set
    """
    # Rate limiting
    if not check_rate_limit(user.id):
        raise HTTPException(429, "Rate limit exceeded. Try again later.")

    # Current workweek (Mon-Fri)
    week_start = date.today() - timedelta(days=date.today().weekday())

    # Check cache first
    cached = get_cached_summary(user.id, week_start)
    if cached is not None:
        return WeeklySummaryResponse(summary=cached)

    # Compute analytics (same as /analytics/weekly)
    analytics = compute_weekly_analytics(session, user, week_start)

    # Build prompt and call AI
    prompt = build_weekly_summary_prompt(analytics, week_start)
    summary = ai_client.generate_summary(prompt)

    # Fallback if AI is unavailable
    if summary is None:
        summary = (
            f"This week you completed {analytics['completions']} habits and logged "
            f"{analytics['focus_minutes']} minutes of focus time. "
            f"Your average productivity score was {analytics['productivity_score']}/100. "
            f"Keep up the great work!"
        )

    # Cache and return
    set_cached_summary(user.id, week_start, summary)
    return WeeklySummaryResponse(summary=summary)
