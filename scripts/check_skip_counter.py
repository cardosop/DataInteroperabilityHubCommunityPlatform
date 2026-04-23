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
        --threshold 0.05

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
                    raise RuntimeError(
                        f"Malformed JSONL at {jsonl_path}:{line_no}: {exc}"
                    ) from exc
                reason = str(entry.get("reason", "(no reason)"))
                counter[reason] += 1
    return counter


def check_thresholds(
    counts: "Counter[str] | dict[str, int]",
    *,
    total_tests: int,
    threshold: float,
) -> tuple[bool, list[str]]:
    """Return (passed, messages).

    `passed=False` when any reason's count / total_tests > threshold.
    `messages` always lists every reason with its percentage so the
    full picture is visible in the CI log.

    Accepts any mapping str → int; callers typically pass a Counter
    but a plain dict is fine — we sort by count descending ourselves
    rather than relying on Counter.most_common() so tests can pass
    either shape.
    """
    if total_tests <= 0:
        raise ValueError(f"total_tests must be > 0, got {total_tests!r}")
    if not (0 < threshold < 1):
        raise ValueError(
            f"threshold must be strictly between 0 and 1, got {threshold!r}"
        )

    any_over = False
    messages: list[str] = []
    # Sort descending by count, then alphabetically for ties — deterministic
    # output regardless of whether callers pass a Counter or dict.
    ordered = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    for reason, count in ordered:
        pct = count / total_tests
        marker = "FAIL" if pct > threshold else "ok"
        if pct > threshold:
            any_over = True
        messages.append(
            f"  [{marker}] {count:5d} / {total_tests} ({pct:.1%}) — {reason}"
        )
    return (not any_over), messages


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Aggregate pytest skip events and gate on per-reason thresholds."
    )
    parser.add_argument("--artifact-dir", type=Path, default=Path("test-results"))
    parser.add_argument("--total-tests", type=int, required=True)
    parser.add_argument(
        "--threshold", type=float, default=0.05,
        help="Per-reason fraction above which the build fails (default 0.05 = 5%%).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_arg_parser().parse_args(argv)
    counts = aggregate_skip_events(args.artifact_dir)
    if not counts:
        print(f"No skip events found under {args.artifact_dir}. ✅")
        return 0

    passed, messages = check_thresholds(
        counts, total_tests=args.total_tests, threshold=args.threshold,
    )
    print(
        f"Skip-counter gate: {len(counts)} distinct reason(s), "
        f"threshold={args.threshold:.0%} of {args.total_tests} tests"
    )
    for msg in messages:
        print(msg)
    if not passed:
        print(
            "\n::error title=Skip-counter gate::"
            "At least one skip reason exceeded the per-reason threshold. "
            "Either fix the underlying infra or raise --threshold with a "
            "written justification."
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
