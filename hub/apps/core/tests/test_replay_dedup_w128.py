"""
W12.8 (oss-release-remediation) — event-replay dedup veracity pins.

The named liar: the replay command's help claimed "Skip events that
have already been replayed (idempotency)" while the guard was
check-then-act — a non-atomic exists() before publish and a plain
setex after, so concurrent replays double-published and the 24h marker
TTL silently re-allowed replays.  The same duplicated non-atomic pair
existed in the API view (``core/events/views.py``).

Root fix (W12.8): ONE atomic claim in the shared dedup module —
``claim_event_replay`` (SETNX / ``cache.add``, 24h TTL) + a
best-effort ``release_event_replay`` called on a FAILED replay so
retries can re-run at-least-once.  Both the management command and the
API view use it; the local duplicate helpers are deleted.

Pins run against the REAL marker store (Redis events pool when
reachable, else the atomic Django cache fallback — both are SET-NX).
"""

from __future__ import annotations

import uuid
from pathlib import Path

import pytest

from hub.apps.core.events.deduplication import (
    REPLAY_MARKER_TTL,
    claim_event_replay,
    release_event_replay,
)

pytestmark = [pytest.mark.django_db]


def _fresh_event_id() -> str:
    return str(uuid.uuid4())


class TestClaimRelease:
    def test_first_claim_wins_second_loses(self):
        event_id = _fresh_event_id()
        try:
            assert claim_event_replay(event_id) is True
            # A second claimant — a concurrent replayer or a re-run
            # inside the TTL window — must lose the claim.
            assert claim_event_replay(event_id) is False
        finally:
            release_event_replay(event_id)

    def test_release_allows_reclaim(self):
        event_id = _fresh_event_id()
        try:
            assert claim_event_replay(event_id) is True
            release_event_replay(event_id)
            # After the release (a failed replay), a retry can re-claim.
            assert claim_event_replay(event_id) is True
        finally:
            release_event_replay(event_id)

    def test_marker_ttl_is_the_documented_24h_window(self):
        assert REPLAY_MARKER_TTL == 24 * 60 * 60


class TestConsolidation:
    def test_views_have_no_local_duplicate_helpers(self):
        """The API view must use the shared claim/release — the
        duplicated non-atomic check/mark pair is deleted."""
        views = Path(__file__).resolve().parents[1] / "events" / "views.py"
        text = views.read_text(encoding="utf-8")
        assert "def _check_event_duplicate" not in text
        assert "def _mark_event_replayed" not in text
        assert "claim_event_replay" in text
        assert "release_event_replay" in text

    def test_command_help_states_the_real_contract(self):
        """The command help must state the 24h window + the atomic
        claim, not the old 'already replayed' overstatement."""
        command = (
            Path(__file__).resolve().parents[2]
            / "core"
            / "management"
            / "commands"
            / "replay_events.py"
        )
        text = command.read_text(encoding="utf-8")
        assert "24 hours" in text
        assert "SETNX" in text
        assert "released on a failed replay" in text
