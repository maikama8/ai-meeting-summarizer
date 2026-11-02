"""Build the providers selected by settings."""

from app.config import Settings
from app.services.errors import ProviderConfigError
from app.services.summarization.base import SummarizationProvider
from app.services.summarization.mock import MockSummarizationProvider
from app.services.summarization.openai_llm import OpenAISummarizationProvider
from app.services.transcription.base import TranscriptionProvider
from app.services.transcription.faster_whisper import FasterWhisperTranscriptionProvider
from app.services.transcription.mock import MockTranscriptionProvider
from app.services.transcription.openai_whisper import OpenAITranscriptionProvider


def _require_openai_api_key(settings: Settings) -> str:
    value = settings.openai_api_key_value()
    if not value:
        raise ProviderConfigError("OPENAI_API_KEY is required when a provider is set to 'openai'.")
    return value


def build_transcription_provider(settings: Settings) -> TranscriptionProvider:
    provider = settings.transcription_provider
    if provider == "mock":
        return MockTranscriptionProvider()
    if provider == "openai":
        return OpenAITranscriptionProvider(
            api_key=_require_openai_api_key(settings),
            base_url=settings.openai_base_url,
            model=settings.openai_transcription_model,
            timeout=settings.openai_timeout_seconds,
        )
    if provider == "faster_whisper":
        return FasterWhisperTranscriptionProvider(
            model_size=settings.faster_whisper_model,
            device=settings.faster_whisper_device,
            compute_type=settings.faster_whisper_compute_type,
        )
    raise ProviderConfigError(f"Unsupported transcription provider: {provider}")


def build_summarization_provider(settings: Settings) -> SummarizationProvider:
    provider = settings.summarization_provider
    if provider == "mock":
        return MockSummarizationProvider()
    if provider == "openai":
        return OpenAISummarizationProvider(
            api_key=_require_openai_api_key(settings),
            base_url=settings.openai_base_url,
            model=settings.openai_summary_model,
            timeout=settings.openai_timeout_seconds,
        )
    raise ProviderConfigError(f"Unsupported summarization provider: {provider}")
