"""Shared test fixtures."""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


def build_settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "transcription_provider": "mock",
        "summarization_provider": "mock",
        "openai_api_key": None,
    }
    values.update(overrides)
    return Settings(**values)


@pytest.fixture
def client() -> Iterator[TestClient]:
    app = create_app(build_settings())
    with TestClient(app) as test_client:
        yield test_client
