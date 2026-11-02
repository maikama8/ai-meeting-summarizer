"""Provider selection and the OpenAI HTTP adapters."""

import json

import httpx
import pytest
from pydantic import ValidationError

from app.main import create_app
from app.services.errors import ProviderConfigError, ProviderError
from app.services.factory import build_summarization_provider, build_transcription_provider
from app.services.summarization.openai_llm import OpenAISummarizationProvider
from app.services.transcription.faster_whisper import FasterWhisperTranscriptionProvider
from app.services.transcription.openai_whisper import OpenAITranscriptionProvider
from tests.conftest import build_settings


def test_factories_default_to_mock_providers() -> None:
    settings = build_settings()
    assert build_transcription_provider(settings).name == "mock"
    assert build_summarization_provider(settings).name == "mock"


def test_openai_provider_requires_an_api_key() -> None:
    settings = build_settings(summarization_provider="openai", openai_api_key=None)
    with pytest.raises(ProviderConfigError, match="OPENAI_API_KEY"):
        build_summarization_provider(settings)
    with pytest.raises(ProviderConfigError, match="OPENAI_API_KEY"):
        create_app(settings)


def test_provider_name_is_normalized() -> None:
    settings = build_settings(transcription_provider=" OpenAI ", openai_api_key="sk-test")
    assert settings.transcription_provider == "openai"
    assert build_transcription_provider(settings).name == "openai"


def test_unknown_provider_is_rejected() -> None:
    with pytest.raises(ValidationError):
        build_settings(transcription_provider="nope")


def test_openai_summarizer_parses_json(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    class FakeResponse:
        status_code = 200
        text = ""

        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, object]:
            content = {
                "summary": "The team will ship the fix.",
                "key_points": ["Billing hotfix"],
                "participants": ["Ada"],
                "action_items": [
                    {"description": "Ship the fix", "owner": "Ada", "due_date": "Friday"},
                    {"description": "  ", "owner": "Ada", "due_date": None},
                ],
            }
            fenced = "```json\n" + json.dumps(content) + "\n```"
            return {"choices": [{"message": {"content": fenced}}]}

    class FakeClient:
        def __init__(self, *args: object, **kwargs: object) -> None:
            del args, kwargs

        def __enter__(self) -> "FakeClient":
            return self

        def __exit__(self, *args: object) -> bool:
            return False

        def post(self, url: str, **kwargs: object) -> FakeResponse:
            captured["url"] = url
            captured["headers"] = kwargs["headers"]
            captured["json"] = kwargs["json"]
            return FakeResponse()

    monkeypatch.setattr(httpx, "Client", FakeClient)
    provider = OpenAISummarizationProvider(
        api_key="sk-test",
        base_url="https://api.openai.com/v1/",
        model="gpt-4o-mini",
        timeout=5,
    )

    summary = provider.summarize("Ship the fix.", language="en")

    assert captured["url"] == "https://api.openai.com/v1/chat/completions"
    headers = captured["headers"]
    assert isinstance(headers, dict)
    assert headers["Authorization"] == "Bearer sk-test"
    body = captured["json"]
    assert isinstance(body, dict)
    assert body["model"] == "gpt-4o-mini"
    assert "Language hint: en" in body["messages"][1]["content"]
    assert summary.provider == "openai"
    assert summary.summary == "The team will ship the fix."
    assert summary.participants == ["Ada"]
    assert len(summary.action_items) == 1
    assert summary.action_items[0].owner == "Ada"
    assert summary.action_items[0].due_date == "Friday"
    assert "sk-test" not in summary.summary


def test_openai_transcription_parses_verbose_json(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    class FakeResponse:
        status_code = 200
        text = ""

        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, object]:
            return {"text": " Hello team. ", "language": "english", "duration": 3.5}

    class FakeClient:
        def __init__(self, *args: object, **kwargs: object) -> None:
            del args, kwargs

        def __enter__(self) -> "FakeClient":
            return self

        def __exit__(self, *args: object) -> bool:
            return False

        def post(self, url: str, **kwargs: object) -> FakeResponse:
            captured["url"] = url
            captured["data"] = kwargs["data"]
            captured["files"] = kwargs["files"]
            captured["headers"] = kwargs["headers"]
            return FakeResponse()

    monkeypatch.setattr(httpx, "Client", FakeClient)
    provider = OpenAITranscriptionProvider(
        api_key="sk-test",
        base_url="https://api.openai.com/v1",
        model="whisper-1",
        timeout=5,
    )

    transcript = provider.transcribe("clips/meeting.wav", b"audio-bytes", "en")

    assert captured["url"] == "https://api.openai.com/v1/audio/transcriptions"
    assert captured["data"] == {
        "model": "whisper-1",
        "response_format": "verbose_json",
        "language": "en",
    }
    files = captured["files"]
    assert isinstance(files, dict)
    assert files["file"][0] == "meeting.wav"
    assert files["file"][1] == b"audio-bytes"
    headers = captured["headers"]
    assert isinstance(headers, dict)
    assert headers["Authorization"] == "Bearer sk-test"
    assert transcript.text == "Hello team."
    assert transcript.language == "english"
    assert transcript.duration_seconds == 3.5
    assert transcript.provider == "openai"


def test_openai_transcription_error_hides_the_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    request = httpx.Request("POST", "https://api.openai.com/v1/audio/transcriptions")
    response = httpx.Response(401, request=request, text="invalid key")

    class FakeClient:
        def __init__(self, *args: object, **kwargs: object) -> None:
            del args, kwargs

        def __enter__(self) -> "FakeClient":
            return self

        def __exit__(self, *args: object) -> bool:
            return False

        def post(self, url: str, **kwargs: object) -> httpx.Response:
            del url, kwargs
            return response

    monkeypatch.setattr(httpx, "Client", FakeClient)
    provider = OpenAITranscriptionProvider(
        api_key="sk-test-secret",
        base_url="https://api.openai.com/v1",
        model="whisper-1",
        timeout=5,
    )

    with pytest.raises(ProviderError) as caught:
        provider.transcribe("meeting.wav", b"audio", None)
    message = str(caught.value)
    assert "401" in message
    assert "sk-test-secret" not in message


def test_faster_whisper_reports_a_missing_install(monkeypatch: pytest.MonkeyPatch) -> None:
    import builtins

    real_import = builtins.__import__

    def guarded(name: str, *args: object, **kwargs: object) -> object:
        if name == "faster_whisper":
            raise ImportError("blocked for test")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded)
    with pytest.raises(ProviderConfigError, match="faster-whisper"):
        FasterWhisperTranscriptionProvider(model_size="tiny", device="cpu", compute_type="int8")
