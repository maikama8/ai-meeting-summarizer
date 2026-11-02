"""Shared results returned by providers."""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Transcript:
    text: str
    language: str
    provider: str
    duration_seconds: float | None = None
    notice: str | None = None


@dataclass(frozen=True)
class ActionItem:
    description: str
    owner: str | None = None
    due_date: str | None = None


@dataclass(frozen=True)
class Summary:
    summary: str
    key_points: list[str] = field(default_factory=list)
    action_items: list[ActionItem] = field(default_factory=list)
    participants: list[str] = field(default_factory=list)
    provider: str = "mock"


@dataclass(frozen=True)
class ProcessResult:
    filename: str
    transcript: Transcript
    summary: Summary
