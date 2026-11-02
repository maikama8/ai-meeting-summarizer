"""Request dependencies."""

from fastapi import Request

from app.config import Settings
from app.services.summarization.base import SummarizationProvider
from app.services.transcription.base import TranscriptionProvider


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_transcription(request: Request) -> TranscriptionProvider:
    return request.app.state.transcription


def get_summarization(request: Request) -> SummarizationProvider:
    return request.app.state.summarization
