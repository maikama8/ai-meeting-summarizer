"""Keep the published examples aligned with the running app."""

import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.services.transcription.mock import load_sample_transcript

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE_TRANSCRIPT = ROOT / "examples" / "sample_transcript.txt"
EXAMPLE_OUTPUT = ROOT / "examples" / "sample_output.json"
LICENSE = ROOT / "LICENSE"


def test_example_transcript_matches_the_packaged_sample() -> None:
    assert EXAMPLE_TRANSCRIPT.read_text(encoding="utf-8").strip() == load_sample_transcript()


def test_example_output_matches_the_summarize_endpoint(client: TestClient) -> None:
    transcript = EXAMPLE_TRANSCRIPT.read_text(encoding="utf-8")
    response = client.post("/summarize", json={"transcript": transcript})
    saved = json.loads(EXAMPLE_OUTPUT.read_text(encoding="utf-8"))

    assert response.status_code == 200
    assert response.json() == saved


def test_license_names_the_copyright_holder() -> None:
    text = LICENSE.read_text(encoding="utf-8")
    assert "Copyright (c) 2026 Abdulrasheed Oseni" in text
    assert "MIT License" in text
