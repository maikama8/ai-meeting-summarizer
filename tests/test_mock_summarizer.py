"""Behavior of the offline summarizer."""

import pytest

from app.services.errors import InvalidTranscriptError
from app.services.summarization.mock import MockSummarizationProvider

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


def test_sample_transcript_extracts_owners_and_due_dates() -> None:
    summary = MockSummarizationProvider().summarize(SAMPLE)

    assert summary.provider == "mock"
    assert summary.participants == ["Amaka Okonkwo", "Chinedu Adeyemi", "Fatima Bello"]
    assert summary.summary == (
        "Notes from Weekly product sync - 2 November 2026. "
        "Participants: Amaka Okonkwo, Chinedu Adeyemi, Fatima Bello. "
        "We are delaying the mobile release until the hotfix is verified. "
        "5 action items captured."
    )
    assert summary.key_points == [
        "The support queue is up 18%.",
        "We are delaying the mobile release until the hotfix is verified.",
    ]
    assert [(item.description, item.owner, item.due_date) for item in summary.action_items] == [
        ("Ship the billing hotfix before Friday", None, "Friday"),
        (
            "Update the invoice API by Wednesday and send the PR to Amaka",
            "Chinedu Adeyemi",
            "Wednesday",
        ),
        ("Draft a customer note by 6 November 2026", None, "6 November 2026"),
        ("Add regression tests for the refund path", "Chinedu Adeyemi", "2026-11-05"),
        ("Schedule a follow-up with finance next Monday", "Fatima Bello", "next Monday"),
    ]


def test_bullet_and_numbered_commitments() -> None:
    transcript = """\
- Amaka to publish the release notes by Friday.
2. Chinedu will rotate the API keys tomorrow.
"""
    summary = MockSummarizationProvider().summarize(transcript)

    assert [(item.description, item.owner, item.due_date) for item in summary.action_items] == [
        ("Publish the release notes by Friday", "Amaka", "Friday"),
        ("Rotate the API keys tomorrow", "Chinedu", "tomorrow"),
    ]


def test_prose_without_commitments_has_no_action_items() -> None:
    summary = MockSummarizationProvider().summarize(
        "The team discussed the roadmap and agreed the design looks fine."
    )

    assert summary.action_items == []
    assert "roadmap" in summary.summary
    assert summary.summary.endswith("0 action items captured.")


def test_empty_transcript_is_rejected() -> None:
    with pytest.raises(InvalidTranscriptError):
        MockSummarizationProvider().summarize("   ")
