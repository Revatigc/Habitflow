"""Thin wrapper around the Anthropic API for generating weekly summaries."""

import os
from typing import Optional

import anthropic

from .schemas import WeeklySummaryResponse


# Initialize the Anthropic client lazily to allow graceful degradation
_client: Optional[anthropic.Anthropic] = None


def get_client() -> Optional[anthropic.Anthropic]:
    """Get or create the Anthropic client.

    Returns None if ANTHROPIC_API_KEY is not set, allowing the feature
    to degrade gracefully without raising at import time.
    """
    global _client
    if _client is not None:
        return _client

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return None

    _client = anthropic.Anthropic(api_key=api_key)
    return _client


def generate_summary(prompt: str) -> Optional[str]:
    """Generate a summary using the Anthropic API.

    Args:
        prompt: The user prompt containing the weekly analytics data.

    Returns:
        The generated summary text, or None if the API key is not configured
        or if the API call fails.
    """
    client = get_client()
    if client is None:
        return None

    try:
        response = client.messages.create(
            model="claude-3-haiku-20240307",
            max_tokens=300,
            temperature=0.7,
            system=(
                "You are a concise productivity coach. Write a short, encouraging "
                "weekly recap (2-3 sentences) based on the user's habit and focus data. "
                "Be specific about what they accomplished. Use a warm, motivating tone. "
                "Never mention the data format or that you are an AI."
            ),
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text.strip() if response.content else None
    except Exception:
        # Degrade gracefully on any API error
        return None