"""Request and response models for the meeting API."""

from pydantic import BaseModel, Field, field_validator


class SummarizeRequest(BaseModel):
    transcript: str = Field(min_length=1, max_length=100_000)
    language: str | None = Field(default=None, max_length=16)

    @field_validator("transcript")
    @classmethod
    def _strip_transcript(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Transcript is empty.")
        return cleaned

    @field_validator("language")
    @classmethod
    def _strip_language(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None


class ActionItemModel(BaseModel):
    description: str
    owner: str | None = None
    due_date: str | None = None


class SummaryResponse(BaseModel):
    summary: str
    key_points: list[str]
    action_items: list[ActionItemModel]
    participants: list[str]
    provider: str


class TranscriptResponse(BaseModel):
    text: str
    language: str
    provider: str
    duration_seconds: float | None = None
    notice: str | None = None


class ProcessResponse(BaseModel):
    filename: str
    transcript: TranscriptResponse
    summary: SummaryResponse


class ServiceInfo(BaseModel):
    name: str
    version: str
    status: str
    transcription_provider: str
    summarization_provider: str
    docs: str


class HealthResponse(BaseModel):
    status: str
    transcription_provider: str
    summarization_provider: str
