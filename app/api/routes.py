"""HTTP routes for transcription and summarization."""

import asyncio
from dataclasses import asdict

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from app import __version__
from app.api.deps import get_settings, get_summarization, get_transcription
from app.config import Settings
from app.schemas.meeting import (
    HealthResponse,
    ProcessResponse,
    ServiceInfo,
    SummarizeRequest,
    SummaryResponse,
    TranscriptResponse,
)
from app.services.pipeline import process_upload
from app.services.summarization.base import SummarizationProvider
from app.services.transcription.base import TranscriptionProvider

router = APIRouter()


def _normalize_language(language: str | None) -> str | None:
    if language is None:
        return None
    cleaned = language.strip()
    if not cleaned:
        return None
    if len(cleaned) > 16:
        raise HTTPException(status_code=400, detail="Language must be a short code such as 'en'.")
    return cleaned


async def _read_upload(file: UploadFile, settings: Settings) -> bytes:
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Upload is empty.")
    if len(data) > settings.max_upload_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"Upload exceeds the {settings.max_upload_bytes} byte limit.",
        )
    return data


@router.get("/", response_model=ServiceInfo, tags=["Health"])
def root(
    settings: Settings = Depends(get_settings),
) -> ServiceInfo:
    """Service name, active providers, and a link to the interactive docs."""
    return ServiceInfo(
        name=settings.app_name,
        version=__version__,
        status="ok",
        transcription_provider=settings.transcription_provider,
        summarization_provider=settings.summarization_provider,
        docs="/docs",
    )


@router.get("/health", response_model=HealthResponse, tags=["Health"])
def health(settings: Settings = Depends(get_settings)) -> HealthResponse:
    """Liveness probe. Reports which providers are configured."""
    return HealthResponse(
        status="ok",
        transcription_provider=settings.transcription_provider,
        summarization_provider=settings.summarization_provider,
    )


@router.post("/transcribe", response_model=TranscriptResponse, tags=["Meetings"])
async def transcribe(
    file: UploadFile = File(..., description="Audio file, or a text transcript."),
    language: str | None = Form(default=None),
    settings: Settings = Depends(get_settings),
    provider: TranscriptionProvider = Depends(get_transcription),
) -> TranscriptResponse:
    """Transcribe an upload. Text files are accepted so the API can be exercised offline."""
    data = await _read_upload(file, settings)
    selected_language = _normalize_language(language)
    result = await asyncio.to_thread(
        provider.transcribe,
        file.filename or "upload",
        data,
        selected_language,
    )
    return TranscriptResponse.model_validate(asdict(result))


@router.post("/summarize", response_model=SummaryResponse, tags=["Meetings"])
async def summarize(
    body: SummarizeRequest,
    provider: SummarizationProvider = Depends(get_summarization),
) -> SummaryResponse:
    """Summarize a transcript into notes, key points, and action items."""
    result = await asyncio.to_thread(provider.summarize, body.transcript, body.language)
    return SummaryResponse.model_validate(asdict(result))


@router.post("/process", response_model=ProcessResponse, tags=["Meetings"])
async def process(
    file: UploadFile = File(..., description="Audio file, or a text transcript."),
    language: str | None = Form(default=None),
    settings: Settings = Depends(get_settings),
    transcription: TranscriptionProvider = Depends(get_transcription),
    summarization: SummarizationProvider = Depends(get_summarization),
) -> ProcessResponse:
    """Transcribe an upload and summarize it in one request."""
    data = await _read_upload(file, settings)
    selected_language = _normalize_language(language)
    result = await asyncio.to_thread(
        process_upload,
        filename=file.filename or "upload",
        data=data,
        language=selected_language,
        transcription=transcription,
        summarization=summarization,
    )
    return ProcessResponse.model_validate(asdict(result))
