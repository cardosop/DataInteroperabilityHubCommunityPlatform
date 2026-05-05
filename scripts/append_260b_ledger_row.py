#!/usr/bin/env python3
"""
Phase 260.B Acceptance #5 — append a ledger row.

Idempotent updater for
``docs/audit-reports/260-cookie-rollout-nightly-ledger.md`` and its JSON
sidecar. Invoked by ``.github/workflows/auto-ledger-260b.yml`` on every
nightly run completion.

Behaviour
---------
* If a row for ``--run-date`` already exists, **update** it (don't
  duplicate). This handles workflow re-runs cleanly.
* Compute the running ``consecutive_green`` counter:
    - ``green``       → counter += 1
    - ``red``         → counter = 0
    - ``infra-skip``  → counter unchanged (staging blip, not a regression)
* Stop the counter at 14: any further green rows hold at 14 (the gate
  is closed; closure-block sign-off is the next step).
* Reject rows older than the most recent row to prevent ledger rewrites.

The JSON sidecar is the source of truth for the consecutive-green
counter; the markdown table is generated from it on every run so the
two are always in sync.
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, asdict
from datetime import date, datetime
from pathlib import Path

VALID_OUTCOMES = {"green", "red", "infra-skip"}
GATE_TARGET = 14


@dataclass
class LedgerRow:
    run_date: str          # YYYY-MM-DD UTC
    run_url: str
    outcome: str           # green | red | infra-skip
    cli_result: str
    sdk_result: str
    cookie_result: str

    def __post_init__(self) -> None:
        if self.outcome not in VALID_OUTCOMES:
            raise ValueError(
                f"invalid outcome={self.outcome!r}; must be one of "
                f"{sorted(VALID_OUTCOMES)}"
            )
        # Validate the run_date is parseable.
        datetime.strptime(self.run_date, "%Y-%m-%d")


def _load_json(path: Path) -> dict:
    if not path.exists():
        return {
            "schema": "260b-cookie-rollout-ledger@1",
            "gate_target_consecutive_green": GATE_TARGET,
            "consecutive_green": 0,
            "rows": [],
        }
    return json.loads(path.read_text(encoding="utf-8"))


def _recompute_consecutive_green(rows: list[dict]) -> int:
    """Walk rows newest-to-oldest, counting consecutive `green` until a
    `red` (which resets to zero) is hit. `infra-skip` is transparent.
    """
    counter = 0
    # Rows are kept oldest-first in the JSON; iterate reversed.
    for row in reversed(rows):
        outcome = row.get("outcome")
        if outcome == "green":
            counter += 1
            if counter >= GATE_TARGET:
                return GATE_TARGET
        elif outcome == "red":
            return counter  # the red itself stops the walk
        elif outcome == "infra-skip":
            continue
        else:
            # Unknown outcome — treat conservatively as a stop.
            return counter
    return counter


def _upsert_row(rows: list[dict], new_row: LedgerRow) -> list[dict]:
    """Insert ``new_row`` keeping the list sorted by ``run_date`` ASC.

    If a row for ``new_row.run_date`` already exists, replace it
    (idempotency: workflow re-runs on the same calendar date update the
    row rather than duplicate it).

    Reject inserts older than the most recent row in the ledger to
    prevent backfill rewrites — the ledger is append-only by date.
    """
    new_dict = asdict(new_row)
    new_date = date.fromisoformat(new_row.run_date)

    # Replace if same-date row exists.
    for i, existing in enumerate(rows):
        if existing.get("run_date") == new_row.run_date:
            rows[i] = new_dict
            return rows

    if rows:
        latest = max(date.fromisoformat(r["run_date"]) for r in rows)
        if new_date < latest:
            raise ValueError(
                f"refusing to insert row dated {new_row.run_date} older "
                f"than most-recent ledger row dated {latest.isoformat()} — "
                f"the ledger is append-only; backfilling distorts the "
                f"consecutive-green counter."
            )

    rows.append(new_dict)
    rows.sort(key=lambda r: r["run_date"])
    return rows


def _render_markdown(state: dict) -> str:
    """Re-render the ledger markdown from the JSON state.

    The static framing (purpose / protocol / closure block) lives in
    the existing markdown file. This function rebuilds ONLY the run
    table section, anchored by the ``## Run ledger`` heading.
    """
    rows = state["rows"]
    consecutive = state["consecutive_green"]

    lines = []
    lines.append("")
    lines.append(
        f"<!-- auto-ledger: consecutive_green={consecutive} / target={GATE_TARGET} -->"
    )
    lines.append("")
    lines.append(
        f"**Consecutive green nights:** {consecutive} / {GATE_TARGET}"
    )
    if consecutive >= GATE_TARGET:
        lines.append("")
        lines.append(
            "> ✅ **Gate closed.** 14 consecutive green nights reached. "
            "Proceed to the closure-block sign-off below, then to "
            "[260-cookie-rollout-production-flip.md](../runbooks/260-cookie-rollout-production-flip.md)."
        )
    lines.append("")
    lines.append(
        "| #  | Run date (UTC) | Workflow run | Outcome | CLI | SDK | Cookie | Notes |"
    )
    lines.append(
        "|----|----------------|--------------|---------|-----|-----|--------|-------|"
    )
    if not rows:
        lines.append(
            "| _no nightly runs recorded yet_ | — | — | — | — | — | — | — |"
        )
    else:
        for idx, row in enumerate(rows, start=1):
            lines.append(
                "| {n} | {date} | [run]({url}) | `{outcome}` | "
                "`{cli}` | `{sdk}` | `{cookie}` | _—_ |".format(
                    n=idx,
                    date=row["run_date"],
                    url=row["run_url"],
                    outcome=row["outcome"],
                    cli=row.get("cli_result", "-"),
                    sdk=row.get("sdk_result", "-"),
                    cookie=row.get("cookie_result", "-"),
                )
            )
    lines.append("")
    return "\n".join(lines)


# Sentinel comments delimiting the auto-managed table section. The
# static (human-authored) parts of the markdown file remain untouched.
_MD_BEGIN = "<!-- auto-ledger:begin -->"
_MD_END = "<!-- auto-ledger:end -->"


def _splice_into_markdown(md_path: Path, generated: str) -> None:
    if not md_path.exists():
        raise FileNotFoundError(
            f"{md_path} is missing — create the static framing first."
        )
    body = md_path.read_text(encoding="utf-8")
    if _MD_BEGIN in body and _MD_END in body:
        before, _, rest = body.partition(_MD_BEGIN)
        _, _, after = rest.partition(_MD_END)
        new_body = (
            f"{before}{_MD_BEGIN}\n{generated}\n{_MD_END}{after}"
        )
    else:
        # First time — append a sentinel-delimited section under the
        # `## Run ledger` heading, replacing the placeholder rows.
        if "## Run ledger" not in body:
            raise ValueError(
                "The ledger markdown is missing the `## Run ledger` "
                "heading; cannot anchor the auto-managed table."
            )
        head, _, tail = body.partition("## Run ledger")
        # Drop the placeholder rows that lived under the heading;
        # auto-managed table replaces them.
        if "## Closure block" in tail:
            _, _, closure = tail.partition("## Closure block")
            closure = "## Closure block" + closure
        else:
            closure = ""
        new_body = (
            f"{head}## Run ledger\n\n{_MD_BEGIN}\n{generated}\n{_MD_END}\n\n{closure}"
        )
    md_path.write_text(new_body, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-date", required=True, help="YYYY-MM-DD UTC")
    parser.add_argument("--run-url", required=True)
    parser.add_argument("--outcome", required=True, choices=sorted(VALID_OUTCOMES))
    parser.add_argument("--cli", required=True, help="cli-regression job result")
    parser.add_argument("--sdk", required=True, help="sdk-regression job result")
    parser.add_argument("--cookie", required=True, help="cookie-mode-smoke job result")
    parser.add_argument("--json", type=Path, required=True, help="JSON sidecar path")
    parser.add_argument("--markdown", type=Path, required=True, help="Markdown ledger path")
    args = parser.parse_args()

    new_row = LedgerRow(
        run_date=args.run_date,
        run_url=args.run_url,
        outcome=args.outcome,
        cli_result=args.cli,
        sdk_result=args.sdk,
        cookie_result=args.cookie,
    )

    state = _load_json(args.json)
    state["rows"] = _upsert_row(state.get("rows", []), new_row)
    state["consecutive_green"] = _recompute_consecutive_green(state["rows"])
    state.setdefault("schema", "260b-cookie-rollout-ledger@1")
    state.setdefault("gate_target_consecutive_green", GATE_TARGET)

    args.json.write_text(
        json.dumps(state, indent=2, sort_keys=False) + "\n",
        encoding="utf-8",
    )
    _splice_into_markdown(args.markdown, _render_markdown(state))

    print(
        f"Recorded {args.run_date} as {args.outcome}; "
        f"consecutive_green={state['consecutive_green']}/{GATE_TARGET}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
