"""Pydantic schemas for AI weekly summary endpoint."""

from pydantic import BaseModel


class WeeklySummaryResponse(BaseModel):
    """Response model for the AI weekly summary endpoint."""

    summary: str