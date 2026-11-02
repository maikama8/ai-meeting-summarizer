"""OpenAI chat-completions summarizer.

Selected with SUMMARIZATION_PROVIDER=openai. The model is asked for a JSON
object and the response is validated before it is returned.
"""

import json
import re

import httpx

from app.services.errors import ProviderError
from app.services.models import ActionItem, Summary

_SYSTEM_PROMPT = (
    "You are a meeting-notes assistant. Read the transcript and reply with one JSON object "
    "with keys summary (string), key_points (array of strings), participants (array of strings), "
    "and action_items (array of objects with description, owner, and due_date). "
    "Use null for owner or due_date when the transcript does not say. "
    "Do not invent people, dates, or tasks. Keep the summary to one short paragraph."
)
_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)


def _message_text(content: object) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict) and item.get("text"):
                parts.append(str(item["text"]))
        return "".join(parts)
    raise ProviderError("OpenAI response did not include text content.")


def _optional_text(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    return cleaned or None


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    items: list[str] = []
    for entry in value:
        text = _optional_text(entry)
        if text:
            items.append(text)
    return items


def _parse_summary(content: str) -> Summary:
    stripped = _FENCE_RE.sub("", content.strip())
    try:
        payload = json.loads(stripped)
    except json.JSONDecodeError as exc:
        raise ProviderError("OpenAI summarizer did not return valid JSON.") from exc
    if not isinstance(payload, dict):
        raise ProviderError("OpenAI summarizer returned an unexpected JSON shape.")

    summary = _optional_text(payload.get("summary"))
    if not summary:
        raise ProviderError("OpenAI summarizer returned an empty summary.")

    action_items: list[ActionItem] = []
    raw_items = payload.get("action_items") or []
    if isinstance(raw_items, list):
        for raw in raw_items:
            if not isinstance(raw, dict):
                continue
            description = _optional_text(raw.get("description"))
            if not description:
                continue
            action_items.append(
                ActionItem(
                    description=description,
                    owner=_optional_text(raw.get("owner")),
                    due_date=_optional_text(raw.get("due_date")),
                )
            )

    return Summary(
        summary=summary,
        key_points=_string_list(payload.get("key_points")),
        action_items=action_items,
        participants=_string_list(payload.get("participants")),
        provider="openai",
    )


class OpenAISummarizationProvider:
    """Summarize a transcript with an OpenAI chat model."""

    name = "openai"

    def __init__(self, *, api_key: str, base_url: str, model: str, timeout: float) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._timeout = timeout

    def summarize(self, transcript: str, language: str | None = None) -> Summary:
        instruction = transcript.strip()
        if language:
            instruction = f"Language hint: {language}\n\n{instruction}"
        body = {
            "model": self._model,
            "temperature": 0.2,
            "max_tokens": 1500,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": instruction},
            ],
        }
        try:
            with httpx.Client(timeout=self._timeout) as client:
                response = client.post(
                    f"{self._base_url}/chat/completions",
                    headers={"Authorization": f"Bearer {self._api_key}"},
                    json=body,
                )
                response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            detail = exc.response.text[:300]
            raise ProviderError(
                f"OpenAI summarizer failed ({exc.response.status_code}): {detail}"
            ) from exc
        except httpx.HTTPError as exc:
            raise ProviderError("OpenAI summarizer request failed.") from exc

        try:
            payload = response.json()
        except ValueError as exc:
            raise ProviderError("OpenAI summarizer returned a non-JSON response.") from exc

        try:
            content = payload["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ProviderError("OpenAI summarizer returned an unexpected response.") from exc
        return _parse_summary(_message_text(content))
