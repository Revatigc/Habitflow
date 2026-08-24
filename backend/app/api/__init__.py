from datetime import date, datetime, time, timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..auth.jwt import current_user
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
