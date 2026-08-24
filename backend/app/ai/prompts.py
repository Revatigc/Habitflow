"""Prompt builders for AI weekly summary generation."""

from datetime import date
from typing import Any


def build_weekly_summary_prompt(analytics: dict[str, Any], week_start: date) -> str:
    """Build the user prompt for the weekly summary from analytics data.

    Args:
        analytics: The dictionary returned by the weekly analytics endpoint.
        week_start: The Monday date of the workweek being summarized.

    Returns:
        A formatted prompt string containing only aggregated per-user data.
    """
    week_end = week_start.replace(day=week_start.day + 4)  # Friday
    week_label = f"{week_start.strftime('%b %d')} – {week_end.strftime('%b %d, %Y')}"

    trend_lines = []
    for day in analytics["trend"]:
        label = day["label"]
        score = day["productivity_score"]
        trend_lines.append(f"  {label}: {score}/100")

    trend_text = "\n".join(trend_lines)

    return (
        f"Weekly productivity recap for {week_label}:\n"
        f"\n"
        f"Daily productivity scores (Mon–Fri):\n"
        f"{trend_text}\n"
        f"\n"
        f"Weekly totals:\n"
        f"  Habits completed: {analytics['completions']}\n"
        f"  Focus minutes: {analytics['focus_minutes']}\n"
        f"  Active habits: {analytics['habit_count']}\n"
        f"  Weekly average score: {analytics['productivity_score']}/100\n"
        f"\n"
        f"Write a 2-3 sentence encouraging recap highlighting what went well "
        f"and one gentle suggestion for next week."
    )