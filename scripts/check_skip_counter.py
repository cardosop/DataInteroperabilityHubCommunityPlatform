#!/usr/bin/env python3
"""Per-reason skip-counter gate for the PR 10 post-run CI step.

Aggregates every `skip-events.jsonl` file under `--artifact-dir` (default
`test-results/`), groups events by `reason`, and exits non-zero if any
single reason exceeds the configured percentage of `--total-tests`.

Usage in CI
-----------
    python scripts/check_skip_counter.py \\
        --artifact-dir test-results \\
        --total-tests 1671 \\
        --threshold 0.05 \\
        --category "audit-exposed bug awaiting fix=0.15"

Rationale
---------
The dual-channel roll-out replaced multiple silent `except Exception: pass`
blocks with `pytest.skip(reason="...")` (PR 9). That is a net win —
outages are now visible — but if 90% of the suite skips because MinIO
is down, CI goes green without having tested anything real. This script
is the enforcement: any *single* skip reason above the threshold fails
the build.

The threshold is deliberately per-reason, not aggregate. A 4% S3 skip
rate AND a 4% semantic skip rate would both be tolerated; neither
individually compromises the suite's signal, and using an aggregate
threshold would miss the case where five different reasons each skip
3% of tests (15% silent loss).

Categories (Phase 226.H)
------------------------
A *category* is a recognised skip-reason prefix that should be treated
as a single bucket for threshold purposes. The motivating use case is
`audit-exposed bug awaiting fix`: during the audit-landing cycle this
class of skip is expected to spike (and is allowed up to 15 % of the
suite) while individual non-category reasons remain on the strict 5 %
default. See `scripts/check_audit_bug_ledger.py` for the meta-track
specification.

When a reason matches a category prefix:
  - it is *not* checked against the default per-reason threshold
    (otherwise a single 6 % bug would fail the 5 % default even though
    it sits well inside the 15 % category band);
  - it contributes to one aggregated count compared against the
    category's override threshold.

The `[category-member]` annotation in the output makes the dual-bucket
semantics explicit so a CI-log reader doesn't have to infer them.

Design
------
* Append-only JSONL: parallel workers can each own a segment with no
  locking. The aggregator is OS-read-only and pure-function.
* Groups by `reason` string verbatim. Consistent skip reasons (e.g.
  "S3 not reachable" as a prefix even when the exception message
  differs) keep the aggregation meaningful — normalise at the
  call-site, not here.
* Zero-tolerance for malformed lines: a line that fails to parse as
  JSON raises. Silently dropping malformed records is the anti-pattern
  this whole initiative exists to kill.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path


def aggregate_skip_events(artifact_dir: Path) -> Counter[str]:
    """Return Counter keyed by skip reason, values = occurrence count."""
    counter: Counter[str] = Counter()
    if not artifact_dir.exists():
        return counter
    for jsonl_path in sorted(artifact_dir.glob("**/skip-events.jsonl")):
        with jsonl_path.open(encoding="utf-8") as fp:
            for line_no, raw in enumerate(fp, 1):
                line = raw.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise RuntimeError(f"Malformed JSONL at {jsonl_path}:{line_no}: {exc}") from exc
                reason = str(entry.get("reason", "(no reason)"))
                counter[reason] += 1
    return counter


def _matching_category(
    reason: str, categories: list[tuple[str, float]] | None
) -> tuple[str, float] | None:
    """Return the (prefix, threshold) tuple this reason belongs to, or None.

    First-match wins; categories are scanned in the order the caller
    supplied them, so the caller controls precedence when prefixes
    overlap. (We don't expect overlap in practice — the skip-counter
    consumer registers exactly one category per cycle.)
    """
    if not categories:
        return None
    for prefix, threshold in categories:
        if reason.startswith(prefix):
            return (prefix, threshold)
    return None


def check_thresholds(
    counts: Counter[str] | dict[str, int],
    *,
    total_tests: int,
    threshold: float,
    categories: list[tuple[str, float]] | None = None,
) -> tuple[bool, list[str]]:
    """Return (passed, messages).

    `passed=False` when:
      - any non-category reason's count / total_tests > threshold, OR
      - any category's aggregated count / total_tests > category_threshold.

    `messages` always lists every reason and every category with their
    percentages so the full picture is visible in the CI log.

    Accepts any mapping str → int; callers typically pass a Counter
    but a plain dict is fine — we sort by count descending ourselves
    rather than relying on Counter.most_common() so tests can pass
    either shape.
    """
    if total_tests <= 0:
        raise ValueError(f"total_tests must be > 0, got {total_tests!r}")
    if not (0 < threshold < 1):
        raise ValueError(f"threshold must be strictly between 0 and 1, got {threshold!r}")
    if categories:
        for prefix, cat_threshold in categories:
            if not (0 < cat_threshold < 1):
                raise ValueError(
                    f"category threshold must be strictly between 0 and 1, "
                    f"got {cat_threshold!r} for prefix {prefix!r}"
                )

    any_over = False
    messages: list[str] = []
    category_totals: dict[str, int] = {}

    # Sort descending by count, then alphabetically for ties — deterministic
    # output regardless of whether callers pass a Counter or dict.
    ordered = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    for reason, count in ordered:
        pct = count / total_tests
        match = _matching_category(reason, categories)
        if match is None:
            marker = "FAIL" if pct > threshold else "ok"
            if pct > threshold:
                any_over = True
            messages.append(f"  [{marker}] {count:5d} / {total_tests} ({pct:.1%}) — {reason}")
        else:
            prefix, _ = match
            category_totals[prefix] = category_totals.get(prefix, 0) + count
            messages.append(
                f"  [category-member] {count:5d} / {total_tests} ({pct:.1%}) — {reason}"
            )

    # Render an aggregated [category] line per registered category, even
    # if no events matched — silence on a configured category would hide
    # whether the gate fired at all.
    for prefix, cat_threshold in categories or []:
        total = category_totals.get(prefix, 0)
        pct = total / total_tests
        marker = "FAIL" if pct > cat_threshold else "ok"
        if pct > cat_threshold:
            any_over = True
        messages.append(
            f"  [category] [{marker}] {total:5d} / {total_tests} "
            f"({pct:.1%}) — {prefix} (threshold {cat_threshold:.0%})"
        )

    return (not any_over), messages


def _parse_category_arg(value: str) -> tuple[str, float]:
    """Parse `prefix=threshold` into (prefix, threshold).

    Validation is intentionally strict: a typo like `prefix:0.15` would
    silently disable the category override otherwise.
    """
    if "=" not in value:
        raise argparse.ArgumentTypeError(f"--category must be 'PREFIX=THRESHOLD', got {value!r}")
    prefix, _, raw_threshold = value.rpartition("=")
    if not prefix:
        raise argparse.ArgumentTypeError(f"--category prefix must be non-empty in {value!r}")
    try:
        threshold = float(raw_threshold)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            f"--category threshold must be a number, got {raw_threshold!r}"
        ) from exc
    if not (0 < threshold < 1):
        raise argparse.ArgumentTypeError(f"--category threshold must be in (0, 1), got {threshold}")
    return (prefix, threshold)


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Aggregate pytest skip events and gate on per-reason thresholds."
    )
    parser.add_argument("--artifact-dir", type=Path, default=Path("test-results"))
    parser.add_argument("--total-tests", type=int, required=True)
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.05,
        help="Per-reason fraction above which the build fails (default 0.05 = 5%%).",
    )
    parser.add_argument(
        "--category",
        action="append",
        default=[],
        type=_parse_category_arg,
        metavar="PREFIX=THRESHOLD",
        help=(
            "Register a category: any skip reason starting with PREFIX "
            "is aggregated and checked against THRESHOLD instead of the "
            "default per-reason threshold. May be passed multiple times. "
            "Used by 226.H.gate to allow `audit-exposed bug awaiting fix` "
            "up to 15 %% during the audit-landing cycle."
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_arg_parser().parse_args(argv)
    counts = aggregate_skip_events(args.artifact_dir)
    if not counts:
        print(f"No skip events found under {args.artifact_dir}. ✅")
        return 0

    passed, messages = check_thresholds(
        counts,
        total_tests=args.total_tests,
        threshold=args.threshold,
        categories=args.category or None,
    )
    summary = (
        f"Skip-counter gate: {len(counts)} distinct reason(s), "
        f"threshold={args.threshold:.0%} of {args.total_tests} tests"
    )
    if args.category:
        cat_summary = ", ".join(f"{p}={t:.0%}" for p, t in args.category)
        summary += f" — categories: {cat_summary}"
    print(summary)
    for msg in messages:
        print(msg)
    if not passed:
        print(
            "\n::error title=Skip-counter gate::"
            "At least one skip reason or category exceeded its threshold. "
            "Either fix the underlying infra/bug or raise the threshold "
            "with a written justification."
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
