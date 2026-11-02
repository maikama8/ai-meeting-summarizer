"""Run transcription and summarization as one step."""

from app.services.models import ProcessResult
from app.services.summarization.base import SummarizationProvider
from app.services.transcription.base import TranscriptionProvider


def process_upload(
    *,
    filename: str,
    data: bytes,
    language: str | None,
    transcription: TranscriptionProvider,
    summarization: SummarizationProvider,
) -> ProcessResult:
    transcript = transcription.transcribe(filename, data, language)
    summary = summarization.summarize(transcript.text, language or transcript.language)
    return ProcessResult(filename=filename, transcript=transcript, summary=summary)
