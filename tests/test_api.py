"""HTTP API coverage for the offline providers."""

import struct

from fastapi.testclient import TestClient

from app.main import create_app
from app.services.errors import ProviderConfigError, ProviderError
from tests.conftest import build_settings

SAMPLE = """\
Weekly product sync - 2 November 2026
Attendees: Amaka Okonkwo, Chinedu Adeyemi, Fatima Bello

Amaka: Welcome everyone. We need to ship the billing hotfix before Friday.
Chinedu: I will update the invoice API by Wednesday and send the PR to Amaka.
Fatima: The support queue is up 18%. Please draft a customer note by 6 November 2026.
Amaka: Chinedu should also add regression tests for the refund path. Due 2026-11-05.
Fatima: I will schedule a follow-up with finance next Monday.
Decision: We are delaying the mobile release until the hotfix is verified.
"""


def _wav_bytes() -> bytes:
    frames = b"\x00\x00" * 80
    header = struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF",
        36 + len(frames),
        b"WAVE",
        b"fmt ",
        16,
        1,
        1,
        8000,
        16000,
        2,
        16,
        b"data",
        len(frames),
    )
    return header + frames


def test_root_and_health(client: TestClient) -> None:
    root = client.get("/")
    health = client.get("/health")

    assert root.status_code == 200
    assert root.json()["status"] == "ok"
    assert root.json()["transcription_provider"] == "mock"
    assert root.json()["summarization_provider"] == "mock"
    assert root.json()["docs"] == "/docs"
    assert health.status_code == 200
    assert health.json() == {
        "status": "ok",
        "transcription_provider": "mock",
        "summarization_provider": "mock",
    }


def test_summarize_sample(client: TestClient) -> None:
    response = client.post("/summarize", json={"transcript": SAMPLE, "language": "en"})

    assert response.status_code == 200
    body = response.json()
    assert body["provider"] == "mock"
    assert body["participants"] == ["Amaka Okonkwo", "Chinedu Adeyemi", "Fatima Bello"]
    owners = {item["owner"] for item in body["action_items"]}
    assert "Chinedu Adeyemi" in owners
    assert "Fatima Bello" in owners
    due_dates = {item["due_date"] for item in body["action_items"]}
    assert "2026-11-05" in due_dates
    assert "6 November 2026" in due_dates


def test_summarize_rejects_blank_transcript(client: TestClient) -> None:
    response = client.post("/summarize", json={"transcript": "   "})
    assert response.status_code == 422


def test_transcribe_text_file(client: TestClient) -> None:
    response = client.post(
        "/transcribe",
        files={"file": ("notes.txt", b"Please send the recap by Friday.", "text/plain")},
        data={"language": "fr"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["text"] == "Please send the recap by Friday."
    assert body["language"] == "fr"
    assert body["provider"] == "mock"
    assert body["notice"]
    assert "text" in body["notice"].lower()


def test_transcribe_audio_returns_sample(client: TestClient) -> None:
    response = client.post(
        "/transcribe",
        files={"file": ("meeting.wav", _wav_bytes(), "audio/wav")},
    )

    assert response.status_code == 200
    body = response.json()
    assert "billing hotfix" in body["text"]
    assert body["provider"] == "mock"
    assert "does not decode audio" in body["notice"]


def test_process_text_matches_summarize(client: TestClient) -> None:
    processed = client.post(
        "/process",
        files={"file": ("notes.txt", SAMPLE.encode(), "text/plain")},
    )
    summarized = client.post("/summarize", json={"transcript": SAMPLE.strip()})

    assert processed.status_code == 200
    body = processed.json()
    assert body["filename"] == "notes.txt"
    assert body["transcript"]["text"] == SAMPLE.strip()
    assert body["summary"] == summarized.json()
    assert any(item["owner"] == "Chinedu Adeyemi" for item in body["summary"]["action_items"])


def test_process_rejects_empty_upload(client: TestClient) -> None:
    response = client.post("/process", files={"file": ("empty.txt", b"", "text/plain")})
    assert response.status_code == 400
    assert response.json()["detail"] == "Upload is empty."


def test_upload_over_limit_is_rejected() -> None:
    app = create_app(build_settings(max_upload_bytes=8))
    with TestClient(app) as client:
        response = client.post(
            "/transcribe",
            files={"file": ("notes.txt", b"123456789", "text/plain")},
        )
    assert response.status_code == 413


def test_language_code_must_be_short(client: TestClient) -> None:
    response = client.post(
        "/transcribe",
        files={"file": ("notes.txt", b"Hello.", "text/plain")},
        data={"language": "this-is-way-too-long"},
    )
    assert response.status_code == 400


def test_provider_misconfiguration_is_unavailable() -> None:
    app = create_app(build_settings())

    class Missing:
        name = "missing"

        def summarize(self, transcript: str, language: str | None = None) -> None:
            raise ProviderConfigError("provider is not configured")

    app.state.summarization = Missing()
    with TestClient(app) as client:
        response = client.post("/summarize", json={"transcript": "We need to ship the fix."})
    assert response.status_code == 503
    assert response.json()["detail"] == "provider is not configured"


def test_provider_failure_is_bad_gateway() -> None:
    app = create_app(build_settings())

    class FailingSummarizer:
        name = "broken"

        def summarize(self, transcript: str, language: str | None = None) -> None:
            raise ProviderError("upstream down")

    app.state.summarization = FailingSummarizer()
    with TestClient(app) as client:
        response = client.post("/summarize", json={"transcript": "We need to ship the fix."})
    assert response.status_code == 502
    assert response.json()["detail"] == "upstream down"
