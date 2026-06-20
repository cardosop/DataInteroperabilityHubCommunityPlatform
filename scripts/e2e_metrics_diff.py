#!/usr/bin/env python3
"""Render a GitHub-flavoured markdown delta between two e2e-metrics JSON files.

Invoked by the `e2e-metrics` workflow on every pull request to post a PR
comment showing how the branch moves each baseline metric. Polarity matters —
fewer swallowed exceptions is good, more `pageerror` handlers is good,
`status_code_assertion_count` is a shape indicator (neither inherently good
nor bad). The emoji in the delta column reflects that.

Usage:
    python scripts/e2e_metrics_diff.py <baseline.json> <current.json>

Writes the rendered markdown to stdout. Exits non-zero on IO or JSON errors
(silent failure here would let a broken diff silently pass through the
PR-comment bot — the exact anti-pattern this work exists to kill).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Literal

Polarity = Literal["down_is_good", "up_is_good", "neutral"]

# Declared separately from e2e_metrics.py so the semantics live with the
# presentation layer. If a metric is added there, add it here too and pick a
# polarity — the test suite will catch a missing entry via end-to-end assertions.
METRIC_POLARITY: dict[str, dict[str, Polarity]] = {
    "pytest": {
        "except_exception_pass_count": "down_is_good",
        "orm_query_count": "up_is_good",
        "status_code_assertion_count": "neutral",
        "test_skip_call_count": "down_is_good",
    },
    "playwright": {
        "test_skip_true_count": "down_is_good",
        "page_on_pageerror_count": "up_is_good",
        "page_request_call_count": "up_is_good",
        "verify_via_api_call_count": "up_is_good",
    },
}

EMOJI_GOOD = "🟢"
EMOJI_BAD = "🔴"
EMOJI_NEUTRAL = "⚪"
NO_CHANGE = "—"


def _delta_cell(before: int, after: int, polarity: Polarity) -> str:
    """Render the Δ cell of a markdown table row for a single metric."""
    if before == after:
        return NO_CHANGE
    delta = after - before
    sign = "+" if delta > 0 else ""
    text = f"{sign}{delta}"
    if polarity == "neutral":
        return f"{EMOJI_NEUTRAL} {text}"
    improvement = (polarity == "up_is_good" and delta > 0) or (
        polarity == "down_is_good" and delta < 0
    )
    emoji = EMOJI_GOOD if improvement else EMOJI_BAD
    return f"{emoji} {text}"


def render_diff(baseline: dict, current: dict) -> str:
    """Render a markdown block summarising baseline → current deltas."""
    lines: list[str] = ["## E2E Metrics Delta", ""]
    any_change = False

    for section, metrics in METRIC_POLARITY.items():
        lines.append(f"### {section}")
        lines.append("")
        lines.append("| Metric | Before | After | Δ |")
        lines.append("|---|---:|---:|:---|")
        b_section = baseline.get(section, {}) or {}
        c_section = current.get(section, {}) or {}
        for key, polarity in metrics.items():
            before = int(b_section.get(key, 0))
            after = int(c_section.get(key, 0))
            if before != after:
                any_change = True
            cell = _delta_cell(before, after, polarity)
            lines.append(f"| `{key}` | {before} | {after} | {cell} |")
        lines.append("")

    if not any_change:
        lines.append("_No changes in tracked metrics._")
        lines.append("")

    lines.append(
        "Polarity legend: "
        f"{EMOJI_GOOD} improvement · "
        f"{EMOJI_BAD} regression · "
        f"{EMOJI_NEUTRAL} neutral metric · "
        f"{NO_CHANGE} no change"
    )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    if len(args) != 2:
        sys.stderr.write("usage: e2e_metrics_diff.py <baseline.json> <current.json>\n")
        return 2
    baseline = json.loads(Path(args[0]).read_text(encoding="utf-8"))
    current = json.loads(Path(args[1]).read_text(encoding="utf-8"))
    sys.stdout.write(render_diff(baseline, current) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
