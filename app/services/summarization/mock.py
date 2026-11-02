"""Offline meeting-note heuristic.

The parser is intentionally small and deterministic. It looks for a title,
an attendee line, decision lines, commitments, owners, and due dates in
English meeting notes. It does not call a model.
"""

import re
from dataclasses import dataclass, field, replace

from app.services.errors import InvalidTranscriptError
from app.services.models import ActionItem, Summary

_MONTHS = "January|February|March|April|May|June|July|August|September|October|November|December"
_WEEKDAYS = "Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday"
_MAX_ACTIONS = 20
_MAX_KEY_POINTS = 8

_ATTENDEES_RE = re.compile(r"^attendees\s*:\s*(.+)$", re.IGNORECASE)
_DECISION_RE = re.compile(r"^decision\s*:\s*(.+)$", re.IGNORECASE)
_SPEAKER_RE = re.compile(r"^([A-Z][A-Za-z.'\-]+(?:\s+[A-Z][A-Za-z.'\-]+)?)\s*:\s*(.+)$")
_BULLET_RE = re.compile(r"^(?:[-*•]\s+|\[[ xX]\]\s+|\d+[.)]\s+)")
_ACTION_RE = re.compile(
    r"\b(i will|i'll|we will|we'll|need to|needs to|should|must|please|action item|todo|to-do)\b",
    re.IGNORECASE,
)
_FIRST_PERSON_RE = re.compile(r"^(?:i|i'll|i will|i need to|i should|i must)\b", re.IGNORECASE)
_WE_RE = re.compile(r"^we\b", re.IGNORECASE)
_NAMED_RE = re.compile(
    r"^([A-Z][A-Za-z.'\-]+(?:\s+[A-Z][A-Za-z.'\-]+)?)\s+(?:will|should|must|needs to|to)\b"
)
_LONE_DUE_RE = re.compile(r"^due(?:\s+date)?\s*[:\-]?\s+(.+?)\.?$", re.IGNORECASE)
_ISO_RE = re.compile(r"\b(\d{4}-\d{2}-\d{2})\b")
_DMY_RE = re.compile(rf"\b(\d{{1,2}}\s+(?:{_MONTHS})\s+\d{{4}})\b", re.IGNORECASE)
_MDY_RE = re.compile(rf"\b((?:{_MONTHS})\s+\d{{1,2}},?\s+\d{{4}})\b", re.IGNORECASE)
_PREP_RE = re.compile(
    rf"\b(?:by|due|before|on)\s+((?:next\s+)?(?:{_WEEKDAYS}|week)|tomorrow|end of day|eod)\b",
    re.IGNORECASE,
)
_RELATIVE_RE = re.compile(
    rf"\b((?:next\s+)?(?:{_WEEKDAYS}|week)|tomorrow|end of day|eod)\b",
    re.IGNORECASE,
)
_METRIC_RE = re.compile(r"\d+(?:\.\d+)?\s*%|\bup\s+\d+\b", re.IGNORECASE)
_PREFIXES = (
    re.compile(r"^(?:i'll|i will|i need to|i should|i must)\s+", re.IGNORECASE),
    re.compile(r"^we\s+(?:will|need to|should|must)\s+", re.IGNORECASE),
    re.compile(r"^please\s+", re.IGNORECASE),
    re.compile(
        r"^[A-Z][A-Za-z.'\-]+(?:\s+[A-Z][A-Za-z.'\-]+)?\s+(?:will|should|must|needs to|to)\s+"
    ),
)


@dataclass
class _ParsedMeeting:
    title: str | None = None
    participants: list[str] = field(default_factory=list)
    key_points: list[str] = field(default_factory=list)
    decisions: list[str] = field(default_factory=list)
    action_items: list[ActionItem] = field(default_factory=list)
    opener: str | None = None


def _strip_bullet(line: str) -> str:
    return _BULLET_RE.sub("", line).strip()


def _split_sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return [part.strip() for part in parts if part.strip()]


def _parse_people(value: str) -> list[str]:
    people: list[str] = []
    for part in re.split(r",|\band\b", value):
        name = part.strip(" .")
        if name:
            people.append(name)
    return people


def _ensure_period(text: str) -> str:
    cleaned = text.strip()
    if cleaned and cleaned[-1] not in ".!?":
        return cleaned + "."
    return cleaned


def _looks_like_title(sentence: str) -> bool:
    return len(sentence) <= 100 and not sentence.endswith((".", "!", "?"))


def _normalize_due(value: str) -> str:
    compact = re.sub(r"\s+", " ", value).strip()
    if compact.lower() == "eod":
        return "end of day"
    return compact


def extract_due_date(sentence: str) -> str | None:
    """Return the first due date mentioned in `sentence`, if one is detectable."""
    for pattern in (_ISO_RE, _DMY_RE, _MDY_RE, _PREP_RE, _RELATIVE_RE):
        match = pattern.search(sentence)
        if match:
            return _normalize_due(match.group(1))
    return None


def _lone_due_date(sentence: str) -> str | None:
    match = _LONE_DUE_RE.match(sentence.strip())
    if not match:
        return None
    return extract_due_date(match.group(1)) or match.group(1).strip().rstrip(".")


def _is_action(sentence: str) -> bool:
    return _ACTION_RE.search(sentence) is not None or _NAMED_RE.match(sentence) is not None


def _detect_owner(sentence: str, speaker: str | None) -> str | None:
    if _FIRST_PERSON_RE.match(sentence):
        return speaker
    if _WE_RE.match(sentence):
        return None
    named = _NAMED_RE.match(sentence)
    if named:
        return named.group(1)
    return None


def _resolve_person(name: str | None, participants: list[str]) -> str | None:
    if not name:
        return None
    lowered = name.lower()
    if lowered in {"i", "we", "us", "someone", "team"}:
        return None
    for person in participants:
        first = person.split()[0].lower()
        if person.lower() == lowered or first == lowered:
            return person
    return name


def _clean_description(sentence: str) -> str:
    text = re.sub(r"\s+", " ", sentence).strip()
    for pattern in _PREFIXES:
        updated = pattern.sub("", text, count=1)
        if updated != text:
            text = updated
            break
    text = re.sub(r"^also\s+", "", text, flags=re.IGNORECASE).strip(" -")
    if not text:
        return sentence.strip().rstrip(".")
    text = text[0].upper() + text[1:]
    return text[:-1] if text.endswith(".") else text


def _add_key_point(parsed: _ParsedMeeting, text: str) -> None:
    point = _ensure_period(text)
    if not point or len(parsed.key_points) >= _MAX_KEY_POINTS:
        return
    if any(existing.lower() == point.lower() for existing in parsed.key_points):
        return
    parsed.key_points.append(point)


def _parse(transcript: str) -> _ParsedMeeting:
    parsed = _ParsedMeeting()
    seen_content = False
    seen_actions: set[str] = set()
    speaker: str | None = None

    for raw_line in transcript.splitlines():
        line = _strip_bullet(raw_line.strip())
        if not line:
            continue
        attendees = _ATTENDEES_RE.match(line)
        if attendees:
            parsed.participants = _parse_people(attendees.group(1))
            continue
        decision = _DECISION_RE.match(line)
        if decision:
            text = decision.group(1).strip()
            parsed.decisions.append(text)
            _add_key_point(parsed, text)
            continue
        speaker_match = _SPEAKER_RE.match(line)
        if speaker_match:
            speaker = speaker_match.group(1)
            body = speaker_match.group(2).strip()
        else:
            body = line

        for sentence in _split_sentences(body):
            due_only = _lone_due_date(sentence)
            if due_only:
                if parsed.action_items and parsed.action_items[-1].due_date is None:
                    parsed.action_items[-1] = replace(parsed.action_items[-1], due_date=due_only)
                continue
            if (
                parsed.title is None
                and not seen_content
                and speaker_match is None
                and _looks_like_title(sentence)
                and not _is_action(sentence)
            ):
                parsed.title = sentence
                seen_content = True
                continue
            seen_content = True
            if _is_action(sentence):
                if len(parsed.action_items) >= _MAX_ACTIONS:
                    continue
                description = _clean_description(sentence)
                if description.lower() in seen_actions:
                    continue
                seen_actions.add(description.lower())
                owner = _resolve_person(_detect_owner(sentence, speaker), parsed.participants)
                parsed.action_items.append(
                    ActionItem(
                        description=description,
                        owner=owner,
                        due_date=extract_due_date(sentence),
                    )
                )
                continue
            if parsed.opener is None:
                parsed.opener = _ensure_period(sentence)
            if _METRIC_RE.search(sentence):
                _add_key_point(parsed, sentence)
    return parsed


def _build_summary(parsed: _ParsedMeeting) -> str:
    parts: list[str] = []
    if parsed.title:
        parts.append(f"Notes from {parsed.title.rstrip('.')}.")
    elif parsed.opener:
        parts.append(parsed.opener)
    else:
        parts.append("Meeting notes.")
    if parsed.participants:
        parts.append("Participants: " + ", ".join(parsed.participants) + ".")
    if parsed.decisions:
        parts.append(" ".join(_ensure_period(decision) for decision in parsed.decisions))
    noun = "action item" if len(parsed.action_items) == 1 else "action items"
    parts.append(f"{len(parsed.action_items)} {noun} captured.")
    return " ".join(parts)


class MockSummarizationProvider:
    """Extract a summary and action items without calling an LLM."""

    name = "mock"

    def summarize(self, transcript: str, language: str | None = None) -> Summary:
        del language  # Accepted so every provider shares the same signature.
        if not transcript or not transcript.strip():
            raise InvalidTranscriptError("Transcript is empty.")
        parsed = _parse(transcript)
        return Summary(
            summary=_build_summary(parsed),
            key_points=parsed.key_points,
            action_items=parsed.action_items,
            participants=parsed.participants,
            provider=self.name,
        )
