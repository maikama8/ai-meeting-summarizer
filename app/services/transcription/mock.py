"""Offline transcription provider.

Text uploads are returned as the transcript. Audio uploads receive a bundled
sample meeting so the rest of the pipeline can run without a model or API key.
"""

from importlib.resources import files
from pathlib import Path

from app.services.models import Transcript

_AUDIO_EXTENSIONS = {
    ".wav",
    ".mp3",
    ".m4a",
    ".mp4",
    ".mpeg",
    ".mpga",
    ".ogg",
    ".flac",
    ".webm",
    ".aac",
}
_TEXT_EXTENSIONS = {".txt", ".md", ".vtt", ".srt", ".json"}

_AUDIO_NOTICE = (
    "Mock transcription provider does not decode audio. It returned the bundled "
    "sample meeting so summarization can run offline. Set TRANSCRIPTION_PROVIDER "
    "to 'openai' or 'faster_whisper' to transcribe this file."
)
_TEXT_NOTICE = (
    "File content was read as a transcript because it is text. No speech-to-text model was called."
)


def load_sample_transcript() -> str:
    """Return the bundled meeting transcript shipped with the app."""
    sample = files("app.samples").joinpath("sample_transcript.txt")
    return sample.read_text(encoding="utf-8").strip()


def _looks_like_text(data: bytes) -> bool:
    if not data or b"\x00" in data:
        return False
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return False
    printable = sum(character.isprintable() or character.isspace() for character in text)
    return printable / len(text) >= 0.95


def is_text_transcript(filename: str, data: bytes) -> bool:
    extension = Path(filename).suffix.lower()
    if extension in _AUDIO_EXTENSIONS:
        return False
    if extension in _TEXT_EXTENSIONS:
        return True
    return _looks_like_text(data)


class MockTranscriptionProvider:
    """Deterministic transcription used when no external provider is configured."""

    name = "mock"

    def transcribe(self, filename: str, data: bytes, language: str | None) -> Transcript:
        selected_language = language or "en"
        if is_text_transcript(filename, data):
            text = data.decode("utf-8", errors="replace").strip()
            return Transcript(
                text=text,
                language=selected_language,
                provider=self.name,
                notice=_TEXT_NOTICE,
            )
        return Transcript(
            text=load_sample_transcript(),
            language=selected_language,
            provider=self.name,
            notice=_AUDIO_NOTICE,
        )
