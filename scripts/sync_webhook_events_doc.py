#!/usr/bin/env python3
"""Regenerate the webhook "Supported Events" table from the enum.

Phase U triage (first armed CI run): the drift gate
(tests/docs/test_webhook_doc_drift.py) failed BOTH directions — 72 enum
values undocumented and 10 stale doc rows referencing values the enum
no longer has. The doc table is hand-maintained; the enum is the single
source of truth. This script (pure AST + regex, the same approach as the
drift test — no Django bootstrap) regenerates the table:

  * every CURRENT ``WebhookEventType`` value gets a row, sorted;
  * rows whose value still exists keep their hand-written trigger
    description;
  * new values get a deterministic derived description
    (``<noun> transitions to the <verb> state.``) marked "auto".

The drift test remains the CI pin; this script is the fix path the test
message points at. Run: python scripts/sync_webhook_events_doc.py
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_MODELS_PATH = _REPO_ROOT / "hub" / "apps" / "webhooks" / "models.py"
_DOC_PATH = _REPO_ROOT / "docs" / "mvpdocs" / "concepts" / "webhooks.md"

_TABLE_HEADER_RE = re.compile(r"^## Supported Events\s*$", re.M)
_NEXT_SECTION_RE = re.compile(r"^## \S", re.M)
_ROW_RE = re.compile(r"^\|\s*`([^`]+)`\s*\|\s*(.+?)\s*\|$")


def enum_event_types(models_path: Path = _MODELS_PATH) -> list[str]:
    """AST-extract WebhookEventType values — mirrors the drift test exactly:
    each member is ``NAME = ("value", "Display Label")`` and the dotted
    event type is the tuple's FIRST string constant."""
    tree = ast.parse(models_path.read_text(encoding="utf-8"))
    values: list[str] = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.ClassDef) and node.name == "WebhookEventType"):
            continue
        for stmt in node.body:
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
                    values.append(first.value)
        break  # only one WebhookEventType class
    return values


def derive_description(event: str) -> str:
    """Deterministic trigger description for an event without a curated one."""
    parts = event.split(".")
    verb = parts[-1].replace("_", " ")
    noun = parts[0] if len(parts) > 1 else "resource"
    article = "An" if noun[0] in "aeiou" else "A"
    return f"{article} {noun} {verb} event occurs. (auto-generated — edit the doc row for a curated description)"


def existing_rows(doc: str) -> dict[str, str]:
    """Event -> trigger description for the current table rows."""
    section = _table_after(doc)
    rows: dict[str, str] = {}
    for line in section.splitlines():
        m = _ROW_RE.match(line)
        if m:
            rows[m.group(1)] = m.group(2)
    return rows


def _table_after(doc: str) -> str:
    m = _TABLE_HEADER_RE.search(doc)
    if m is None:
        return ""
    tail = doc[m.end() :]
    nxt = _NEXT_SECTION_RE.search(tail)
    return tail[: nxt.start()] if nxt else tail


def render_table(values: list[str], existing: dict[str, str]) -> str:
    lines = ["| Event | Trigger |", "|---|---|"]
    for event in sorted(values):
        desc = existing.get(event) or derive_description(event)
        lines.append(f"| `{event}` | {desc} |")
    return "\n".join(lines) + "\n"


def sync(models_path: Path = _MODELS_PATH, doc_path: Path = _DOC_PATH) -> str:
    """Return the doc with the Supported Events table regenerated."""
    doc = doc_path.read_text(encoding="utf-8")
    values = enum_event_types(models_path)
    table = render_table(values, existing_rows(doc))

    m = _TABLE_HEADER_RE.search(doc)
    if m is None:
        raise SystemExit("docs/mvpdocs/concepts/webhooks.md has no '## Supported Events' section")
    tail = doc[m.end() :]
    nxt = _NEXT_SECTION_RE.search(tail)
    end = m.end() + (nxt.start() if nxt else len(tail))
    header = (
        "## Supported Events\n\n"
        "> Generated from `WebhookEventType` by `scripts/sync_webhook_events_doc.py` "
        "— run it when the enum changes; the drift gate (tests/docs/test_webhook_doc_drift.py) "
        "enforces the sync at CI time.\n\n"
    )
    return doc[: m.start()] + header + table + "\n" + doc[end:]


def main() -> int:
    synced = sync()
    _DOC_PATH.write_text(synced, encoding="utf-8")
    print(f"synced {len(enum_event_types())} WebhookEventType values into {_DOC_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
