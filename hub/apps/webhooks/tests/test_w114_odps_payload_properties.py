"""W11.4 (oss-release-remediation) — Hypothesis property suite for the
ODPS webhook payload validator (ASVS V5, register row 14).

``validate_odps_webhook_payload`` is the gate in front of ODPS webhook
delivery: non-ODPS event types, structural violations, oversized
payloads and type-mismatched fields are all refused with TYPED
``ODPSWebhook*Error`` exceptions (never a bare crash).  These
properties pin the INVARIANT for EVERY payload a client could send:

* **robustness** — any dict payload with any event type either passes
  (returns None) or raises an ``ODPSWebhookError`` — never a
  TypeError/KeyError/AttributeError/RecursionError (the fail-open
  class register row 14 exists to kill);
* **event-type gate** — a non-ODPS event type is refused with
  ``INVALID_EVENT_TYPE``;
* **required-field gate** — a payload missing any required base field
  is refused with ``MISSING_REQUIRED_FIELD``;
* **size gate** — an oversized payload is refused with
  ``PAYLOAD_TOO_LARGE``;
* **canonical payloads pass** — the documented valid shape for every
  ODPS event type validates cleanly.

Plus the W11.4 corpus replay (docs/security/fuzz/w114-property-corpus.json).

Pure property tests — no database, no mocks.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from hub.apps.webhooks.models import WebhookEventType
from hub.apps.webhooks.odps_webhook_errors import (
    ODPSWebhookError,
    ODPSWebhookPayloadError,
    ODPSWebhookValidationError,
)
from hub.apps.webhooks.odps_webhook_validators import validate_odps_webhook_payload

pytestmark = pytest.mark.django_db  # the app conftest's MVP marker scope

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent
CORPUS = REPO_ROOT / "docs" / "security" / "fuzz" / "w114-property-corpus.json"

_ODPS_EVENT_TYPES = [
    WebhookEventType.ODPS_CREATED,
    WebhookEventType.ODPS_UPDATED,
    WebhookEventType.ODPS_DELETED,
    WebhookEventType.ODPS_NORMALIZED,
    WebhookEventType.ODPS_LINKED,
    WebhookEventType.ODPS_UNLINKED,
    WebhookEventType.ODPS_EXPORT_STARTED,
    WebhookEventType.ODPS_EXPORT_COMPLETED,
]

_TEXT = st.text(alphabet=st.characters(blacklist_categories=("Cs",)), max_size=60)
_JSON_VALUE = st.recursive(
    st.one_of(
        st.none(),
        st.booleans(),
        st.integers(min_value=-(2**63), max_value=2**63),
        _TEXT,
    ),
    lambda children: st.one_of(
        st.lists(children, max_size=4),
        st.dictionaries(_TEXT, children, max_size=4),
    ),
    max_leaves=24,
)


def _canonical_payload(event_type: str) -> dict:
    """The documented valid shape for the event type."""
    return {
        "event_type": event_type,
        "resource_type": "dataset",
        "resource_id": "res-1",
        "timestamp": "2026-01-01T00:00:00Z",
        "data": {},
    }


@settings(max_examples=300, deadline=None)
@given(
    payload=st.one_of(
        st.dictionaries(_TEXT, _JSON_VALUE, max_size=8),
        st.none(),
        st.integers(),
        st.lists(_JSON_VALUE, max_size=3),
        _TEXT,
    ),
    event_type=st.one_of(st.sampled_from(_ODPS_EVENT_TYPES), _TEXT),
)
def test_any_payload_either_passes_or_raises_typed_odps_error(payload, event_type):
    """ANY payload (dict, None, scalar, list, text) + ANY event type →
    return None or raise an ODPSWebhookError subclass — never an
    undocumented exception."""
    try:
        validate_odps_webhook_payload(payload, event_type)
    except ODPSWebhookError:
        pass
    else:
        # No exception: the payload was structurally acceptable for the
        # given event type (the type-gate ran before structure checks).
        assert True


@settings(max_examples=200, deadline=None)
@given(event_type=_TEXT)
def test_non_odps_event_type_rejected_typed(event_type):
    from hypothesis import assume

    assume(not WebhookEventType.is_odps_event_type(event_type))
    with pytest.raises(ODPSWebhookValidationError) as exc_info:
        validate_odps_webhook_payload({}, event_type)
    assert exc_info.value.error_code == ODPSWebhookValidationError.ERROR_CODE_INVALID_EVENT_TYPE


@settings(max_examples=200, deadline=None)
@given(
    payload=st.dictionaries(_TEXT, _JSON_VALUE, max_size=5),
    event_type=st.sampled_from(_ODPS_EVENT_TYPES),
)
def test_missing_required_field_refused_typed(payload, event_type):
    """A payload missing ANY required base field is refused with the
    MISSING_REQUIRED_FIELD code (the size gate never masks it — these
    payloads stay small)."""
    if set(payload) >= {
        "event_type",
        "resource_type",
        "resource_id",
        "timestamp",
        "data",
    }:
        return  # complete payload — the missing-field gate doesn't apply
    with pytest.raises(ODPSWebhookPayloadError) as exc_info:
        validate_odps_webhook_payload(payload, event_type)
    assert exc_info.value.error_code == ODPSWebhookPayloadError.ERROR_CODE_MISSING_REQUIRED_FIELD


@settings(max_examples=20, deadline=None)
@given(
    event_type=st.sampled_from(_ODPS_EVENT_TYPES),
    seed=st.text(alphabet=st.characters(blacklist_categories=("Cs",)), min_size=1, max_size=40),
)
def test_oversized_payload_refused_typed(event_type, seed):
    """The size gate fires typed before any deep validation — the blob
    exceeds MAX_PAYLOAD_SIZE by construction."""
    from hub.apps.webhooks.odps_webhook_validators import MAX_PAYLOAD_SIZE

    payload = _canonical_payload(event_type)
    payload["data"] = {"blob": seed * ((MAX_PAYLOAD_SIZE // len(seed)) + 2)}
    with pytest.raises(ODPSWebhookPayloadError) as exc_info:
        validate_odps_webhook_payload(payload, event_type)
    assert exc_info.value.error_code == ODPSWebhookPayloadError.ERROR_CODE_PAYLOAD_TOO_LARGE


@pytest.mark.parametrize("event_type", _ODPS_EVENT_TYPES)
def test_canonical_payload_passes(event_type):
    """The documented valid shape for every ODPS event type validates."""
    assert validate_odps_webhook_payload(_canonical_payload(event_type), event_type) is None


def test_w114_corpus_replay():
    """Replay the W11.4 fuzz corpus through the real validator."""
    corpus = json.loads(CORPUS.read_text(encoding="utf-8"))
    entries = corpus.get("odps", [])
    assert entries, "the odps corpus section must carry entries"
    for entry in entries:
        payload = entry["payload"]
        event_type = entry["event_type"]
        try:
            validate_odps_webhook_payload(payload, event_type)
            passed = True
        except ODPSWebhookError as exc:
            passed = False
            actual_code = exc.error_code
        if entry.get("expect_pass"):
            assert passed, f"corpus entry must pass: {entry}"
        else:
            assert not passed, f"corpus entry must be refused: {entry}"
            if entry.get("code"):
                assert actual_code == entry["code"], (
                    f"corpus entry code mismatch: {entry} -> {actual_code}"
                )
