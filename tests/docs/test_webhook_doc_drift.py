"""
Phase 233.5 — Webhook event-type doc-vs-reality drift gate.

Pins the bidirectional consistency between the ``WebhookEventType`` enum
in ``hub/apps/webhooks/models.py`` and the "Supported Events" table in
``docs/mvpdocs/concepts/webhooks.md``:

  * FORWARD direction — every enum value MUST appear at least once in
    the doc (so subscribers reading the doc see every event they could
    subscribe to). Catches the "shipped a new event but forgot to
    document it" failure mode.

  * REVERSE direction — every event-shaped string in the doc's
    "Supported Events" section MUST correspond to a real enum value.
    Catches the "doc mentions an event that doesn't exist" failure mode
    (which the pre-233.5 doc had: 10 of 12 listed events were
    hallucinated and didn't match the enum).

Why a CI-time gate: the original Phase 0 audit (Phase 233.0 / D233.1)
flagged 37 implemented event types vs 12 documented. Without an
automated drift check, every PR that adds a new ``WebhookEventType``
member can silently drift the doc again. This test fails at CI time
rather than at the next quarterly audit.

Why standalone (no Django bootstrap):
The test is pure source-file inspection — AST-parses ``models.py`` for
the enum members + regex-parses the markdown for event strings. No
Django app registry, no DB, no Postgres. The CI job runs with
``--confcutdir=tests/docs`` so pytest doesn't pick up the repo's
top-level ``tests/conftest.py`` (which forces ``django.setup()``).

No mocks, no stubs — the test reads the actual files at their
canonical paths and validates content directly.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest


# Repository root (this file lives at tests/docs/, two levels deep).
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent

_MODELS_PATH = _REPO_ROOT / "hub" / "apps" / "webhooks" / "models.py"
_DOC_PATH = _REPO_ROOT / "docs" / "mvpdocs" / "concepts" / "webhooks.md"


def _enum_event_types() -> set[str]:
    """Extract every ``WebhookEventType`` enum value from models.py via AST.

    Returns the SET of dotted event-type strings (e.g. ``contract.created``,
    ``webhook.test``). Multi-line Assign nodes (where the tuple is wrapped
    across lines) are handled — the AST representation is identical
    regardless of source-line layout.
    """
    if not _MODELS_PATH.exists():
        pytest.fail(f"{_MODELS_PATH} not found")

    tree = ast.parse(_MODELS_PATH.read_text())
    event_types: set[str] = set()

    for node in ast.walk(tree):
        if not (isinstance(node, ast.ClassDef) and node.name == "WebhookEventType"):
            continue
        for stmt in node.body:
            # Each enum member is an ``Assign`` of the form
            # ``NAME = "value", "Display Label"`` which AST represents
            # as ``Assign(targets=[Name], value=Tuple(Constant, Constant))``.
            if not isinstance(stmt, ast.Assign):
                continue
            if len(stmt.targets) != 1 or not isinstance(stmt.targets[0], ast.Name):
                continue
            if not stmt.targets[0].id.isupper():
                continue
            value_node = stmt.value
            if isinstance(value_node, ast.Tuple) and value_node.elts:
                first = value_node.elts[0]
                if isinstance(first, ast.Constant) and isinstance(first.value, str):
                    event_types.add(first.value)
        break  # only one WebhookEventType class

    if not event_types:
        pytest.fail(
            "No WebhookEventType enum members extracted — "
            "models.py structure has changed in a way the test does "
            "not anticipate. Update _enum_event_types().",
        )
    return event_types


# Regex for event-shaped backtick-quoted strings in the doc table.
# Matches: `word.word`, `word.word.word`, etc. (lower-snake-with-dots).
# Anchored to backticks so it doesn't catch arbitrary words.
_EVENT_IN_BACKTICKS_RE = re.compile(r"`([a-z][a-z_]*(?:\.[a-z][a-z_]*)+)`")


def _doc_events_in_supported_section() -> set[str]:
    """Extract every event-shaped string from the doc's "Supported Events" section.

    The section spans from the ``## Supported Events`` heading to the next
    ``## `` heading (or EOF). Backtick-quoted dotted lowercase strings
    inside that section are the event names the doc CLAIMS the platform
    supports.
    """
    if not _DOC_PATH.exists():
        pytest.fail(f"{_DOC_PATH} not found")

    text = _DOC_PATH.read_text()

    # Slice out the "Supported Events" section.
    start_match = re.search(r"^## Supported Events\s*$", text, flags=re.MULTILINE)
    if not start_match:
        pytest.fail(
            f"Doc {_DOC_PATH} is missing the '## Supported Events' heading. "
            "Phase 233.5.1 requires this section to be present.",
        )
    section_start = start_match.end()

    # Section ends at the next "## " heading (or EOF).
    after = text[section_start:]
    end_match = re.search(r"^##\s+\S", after, flags=re.MULTILINE)
    section = after[: end_match.start()] if end_match else after

    return set(_EVENT_IN_BACKTICKS_RE.findall(section))


def _doc_full_text_events() -> set[str]:
    """Extract every event-shaped backtick-string anywhere in the doc.

    Used by the FORWARD-direction test (every enum value must appear at
    least once) — that contract lets the doc reference events outside
    the Supported Events table (e.g. in code samples) and still count
    as "documented".
    """
    if not _DOC_PATH.exists():
        pytest.fail(f"{_DOC_PATH} not found")
    text = _DOC_PATH.read_text()
    return set(_EVENT_IN_BACKTICKS_RE.findall(text))


# ---------------------------------------------------------------------------
# The drift gate.
# ---------------------------------------------------------------------------


class TestWebhookDocDrift:
    """Phase 233.5.2 — bidirectional doc-vs-enum drift gate."""

    def test_every_enum_value_is_documented(self) -> None:
        """FORWARD direction — every enum value appears at least once in the doc.

        Catches: a PR that adds ``WebhookEventType.NEW_THING`` without
        adding a row to the doc. The drift previously went undetected
        for months — pre-Phase-233.5 the doc had 12 events while the
        enum had 60+.
        """
        enum_values = _enum_event_types()
        doc_events = _doc_full_text_events()
        missing = enum_values - doc_events
        if missing:
            pytest.fail(
                f"{len(missing)} WebhookEventType enum value(s) are NOT "
                f"mentioned anywhere in {_DOC_PATH.relative_to(_REPO_ROOT)}: "
                f"{sorted(missing)}. Add a row to the 'Supported Events' "
                "table for each.",
            )

    def test_every_doc_event_corresponds_to_an_enum_value(self) -> None:
        """REVERSE direction — every event in the Supported Events section is real.

        Catches: a doc author writing about a hypothetical event
        (e.g. ``contract.activated`` when the actual enum value is
        ``contract.created``). Pre-Phase-233.5 the doc mentioned 12
        events of which 10 had no matching enum value.
        """
        enum_values = _enum_event_types()
        doc_events = _doc_events_in_supported_section()
        hallucinated = doc_events - enum_values
        if hallucinated:
            pytest.fail(
                f"{len(hallucinated)} event(s) in the 'Supported Events' "
                f"section do NOT match any WebhookEventType enum value: "
                f"{sorted(hallucinated)}. Either add the enum value or "
                "remove the doc row.",
            )

    def test_supported_events_section_is_non_empty(self) -> None:
        """The doc has a 'Supported Events' section AND lists at least one event.

        Defends against a future "minimisation" that drops the table
        entirely with the false assumption that the drift gate is enough
        on its own. The doc IS the load-bearing artefact for subscribers
        — the gate makes sure it stays in sync with reality, but the
        artefact must exist in the first place.
        """
        doc_events = _doc_events_in_supported_section()
        assert len(doc_events) >= 10, (
            f"'Supported Events' section has only {len(doc_events)} "
            "documented events; the platform has 60+ event types. The "
            "section appears to have been gutted — restore the table."
        )

    def test_enum_count_meets_minimum_baseline(self) -> None:
        """Sanity check — the AST extraction works.

        Catches: a future refactor of ``WebhookEventType`` that breaks
        the AST shape this test expects (e.g. switching from TextChoices
        to a plain Enum class). The minimum baseline is intentionally
        conservative — the actual count at Phase 233.5 land was 66; the
        test asserts ≥30 so a single-removed-event doesn't trip the
        sanity check, but a structural break (returning 0 or 1) does.
        """
        enum_values = _enum_event_types()
        assert len(enum_values) >= 30, (
            f"WebhookEventType enum extracted only {len(enum_values)} "
            "values — AST shape may have changed. Check "
            "_enum_event_types() against models.py structure."
        )
