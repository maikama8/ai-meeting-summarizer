"""Summarization provider interface."""

from typing import Protocol

from app.services.models import Summary


class SummarizationProvider(Protocol):
    """Turn a transcript into notes and action items."""

    name: str

    def summarize(self, transcript: str, language: str | None = None) -> Summary:
        """Summarize `transcript`."""
