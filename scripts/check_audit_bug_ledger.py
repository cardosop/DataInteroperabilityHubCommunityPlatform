#!/usr/bin/env python3
"""Bug-fix bandwidth meta-track validator (Phase 226.H).

Implements the three gates that protect the bug-fix bandwidth contract:

    226.H.process — Every audit-exposed bug has a ticket + owner + expiry
                    date (default 14 d) within 48 h of the surfacing PR
                    landing.

    226.H.gate    — `audit-exposed bug awaiting fix` is a recognised
                    skip-reason prefix in the skip-counter. The canonical
                    prefix string + 15 % threshold are emitted from this
                    script via `--mode emit-gate-config` so the CI step
                    consumes them without re-declaring the constants.

    226.H.close   — End-of-cycle: the audit-bug skip count returns to
                    ≤ 3 (residual long-tail) AND no open bug is past
                    its effective expiry without an extension review.

Why a single script for three gates
-----------------------------------
The three concerns share the same source of truth — the ledger document
at `docs/audit-exposed-bugs.json`. Putting them in one validator lets
the gate config (the canonical prefix and threshold values consumed by
the skip-counter) live in code adjacent to the ledger schema that
defines them. Splitting them across three files would invite drift.

Stdlib-only by design
---------------------
This script is invoked from `.github/workflows/e2e-metrics.yml` in the
same self-test step that runs `scripts/tests/test_check_skip_counter.py`.
That step deliberately runs `pytest -c /dev/null` and only installs
`pytest`, so the script's own dependencies must stay stdlib-only — the
ledger format is therefore JSON, not YAML.

Output schema (ledger)
----------------------
See `validate_schema()` for the authoritative shape. Every required
field is enforced here; any drift fails the validate gate.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Canonical constants — single source of truth, read by the skip-counter
# ---------------------------------------------------------------------------

# The exact prefix that test code must use when calling pytest.skip(...) for
# an audit-exposed bug. Any deviation breaks the gate. The full skip reason
# is expected to look like:
#
#     audit-exposed bug awaiting fix: AUDIT-BUG-001 — short description
#
# The prefix above must match exactly; the suffix is free-form and may
# include the bug id and a one-line explanation for the test report.
AUDIT_BUG_SKIP_REASON_PREFIX = "audit-exposed bug awaiting fix"

# 15 % of total skips during the audit-landing cycle (226.H.gate).
DEFAULT_CATEGORY_THRESHOLD = 0.15

# Default expiry on a newly-surfaced audit-exposed bug.
DEFAULT_EXPIRY_DAYS = 14

# The 48 h grace window for backfilling ticket/owner/expiry after the
# surfacing PR lands (226.H.process).
DEFAULT_TICKET_GRACE_HOURS = 48

# Residual long-tail at end-of-cycle (226.H.close).
DEFAULT_RESIDUAL_MAX = 3

# Required keys on every bug entry — checked by `validate_schema`.
_BUG_REQUIRED_FIELDS = (
    "id",
    "title",
    "ticket",
    "owner",
    "surfaced_by_pr",
    "surfaced_at",
    "status",
    "extensions",
)
_BUG_VALID_STATUSES = ("open", "closed")
_EXTENSION_REQUIRED_FIELDS = ("extended_at", "new_expiry", "approver", "reason")


# ---------------------------------------------------------------------------
# Schema validation
# ---------------------------------------------------------------------------


def _check_parseable_date(
    problems: list[str], ctx: str, field: str, value: Any
) -> None:
    """Append a parse-error problem if a non-empty value isn't ISO-8601.

    A null/missing value is not flagged here — required-field checks are
    a separate concern. We only fail loudly when a value IS present but
    can't be parsed, since that's a typo that would silently bypass any
    downstream date math.
    """
    if value is None:
        return
    if not isinstance(value, str) or not value.strip():
        return
    if _parse_iso_dt(value) is None:
        problems.append(
            f"{ctx} {field} must parse as ISO-8601 (date or datetime), "
            f"got {value!r}"
        )


def validate_schema(doc: Any) -> list[str]:
    """Return a list of human-readable problem strings.

    Empty list = valid. The validator is fail-loud: every field is checked
    on every load, and unknown fields are tolerated to allow forward
    evolution. Missing required fields, wrong types, duplicate ids,
    invalid enum values, unparseable dates, out-of-range numerics, and
    inconsistent skip-reason examples all surface as separate problems.
    """
    problems: list[str] = []
    if not isinstance(doc, dict):
        return [f"Ledger root must be a JSON object, got {type(doc).__name__}"]

    schema_version = doc.get("schema_version")
    if schema_version != 1:
        problems.append(
            f"schema_version must be 1, got {schema_version!r} — "
            "bump and migrate explicitly before relying on new fields."
        )

    expected_prefix = doc.get("skip_reason_prefix")
    if expected_prefix != AUDIT_BUG_SKIP_REASON_PREFIX:
        problems.append(
            f"skip_reason_prefix must equal "
            f"{AUDIT_BUG_SKIP_REASON_PREFIX!r}, got {expected_prefix!r}. "
            "The constant is the contract between the ledger and the "
            "skip-counter — drift here silently disables 226.H.gate."
        )

    # default_expiry_days: must be a strictly-positive int. Zero would
    # silently make every bug past-expiry on the day it was surfaced;
    # negatives are nonsense.
    if "default_expiry_days" in doc:
        ded = doc["default_expiry_days"]
        if not isinstance(ded, int) or isinstance(ded, bool) or ded <= 0:
            problems.append(
                f"default_expiry_days must be a positive integer, got {ded!r}"
            )

    cycle = doc.get("cycle") or {}
    if not isinstance(cycle, dict):
        problems.append("cycle must be an object")
    elif "residual_max" in cycle:
        rm = cycle["residual_max"]
        if not isinstance(rm, int) or isinstance(rm, bool) or rm < 0:
            problems.append(
                f"cycle.residual_max must be an integer ≥ 0, got {rm!r}"
            )

    process = doc.get("process") or {}
    if not isinstance(process, dict):
        problems.append("process must be an object")
    elif "ticket_grace_period_hours" in process:
        g = process["ticket_grace_period_hours"]
        if (
            not isinstance(g, (int, float))
            or isinstance(g, bool)
            or g < 0
        ):
            problems.append(
                f"process.ticket_grace_period_hours must be a non-negative "
                f"number, got {g!r}"
            )

    bugs = doc.get("bugs")
    if bugs is None:
        problems.append("bugs is required (use [] for an empty ledger)")
        return problems
    if not isinstance(bugs, list):
        problems.append(f"bugs must be a list, got {type(bugs).__name__}")
        return problems

    seen_ids: set[str] = set()
    for idx, bug in enumerate(bugs):
        ctx = f"bugs[{idx}]"
        if not isinstance(bug, dict):
            problems.append(f"{ctx} must be an object")
            continue
        for field in _BUG_REQUIRED_FIELDS:
            if field not in bug:
                problems.append(f"{ctx} missing required field: {field}")
        bug_id = bug.get("id")
        if isinstance(bug_id, str):
            if bug_id in seen_ids:
                problems.append(f"{ctx} duplicate id: {bug_id}")
            else:
                seen_ids.add(bug_id)
        status = bug.get("status")
        if status not in _BUG_VALID_STATUSES:
            problems.append(
                f"{ctx} status must be one of {_BUG_VALID_STATUSES}, got {status!r}"
            )
        if status == "closed" and not bug.get("closed_at"):
            problems.append(f"{ctx} status=closed requires closed_at to be set")

        # Date parseability: surfaced_at, expiry, closed_at must all be
        # parseable when present. The process and close gates rely on
        # this; silently ignoring a bogus date would let a broken entry
        # pass while the gate appears to fire green.
        _check_parseable_date(problems, ctx, "surfaced_at", bug.get("surfaced_at"))
        _check_parseable_date(problems, ctx, "expiry", bug.get("expiry"))
        _check_parseable_date(problems, ctx, "closed_at", bug.get("closed_at"))

        # skip_reason_examples must use the canonical prefix — the entries
        # exist precisely so a reader can spot-check that the gate's
        # category matcher will see them.
        examples = bug.get("skip_reason_examples")
        if examples is not None:
            if not isinstance(examples, list):
                problems.append(f"{ctx} skip_reason_examples must be a list")
            else:
                for e_idx, example in enumerate(examples):
                    if not isinstance(example, str):
                        problems.append(
                            f"{ctx}.skip_reason_examples[{e_idx}] must be a string"
                        )
                        continue
                    if not example.startswith(AUDIT_BUG_SKIP_REASON_PREFIX):
                        problems.append(
                            f"{ctx}.skip_reason_examples[{e_idx}] must start "
                            f"with the canonical prefix "
                            f"{AUDIT_BUG_SKIP_REASON_PREFIX!r}, got {example!r}"
                        )

        extensions = bug.get("extensions") or []
        if not isinstance(extensions, list):
            problems.append(f"{ctx} extensions must be a list")
            continue
        for e_idx, ext in enumerate(extensions):
            ectx = f"{ctx}.extensions[{e_idx}]"
            if not isinstance(ext, dict):
                problems.append(f"{ectx} must be an object")
                continue
            for field in _EXTENSION_REQUIRED_FIELDS:
                if field not in ext:
                    problems.append(f"{ectx} extension missing field: {field}")
            _check_parseable_date(problems, ectx, "extended_at", ext.get("extended_at"))
            _check_parseable_date(problems, ectx, "new_expiry", ext.get("new_expiry"))
            # Backward extension: new_expiry must be on or after extended_at.
            # An extension that moves the deadline earlier is almost
            # certainly a typo (or someone trying to game the close gate).
            extended_at = _parse_iso_dt(ext.get("extended_at"))
            new_expiry = _parse_iso_dt(ext.get("new_expiry"))
            if extended_at and new_expiry and new_expiry < extended_at:
                problems.append(
                    f"{ectx} new_expiry {ext.get('new_expiry')!r} is before "
                    f"extended_at {ext.get('extended_at')!r} — extensions "
                    "must move the deadline forward"
                )

    return problems


# ---------------------------------------------------------------------------
# Date math — pure helpers used by every gate
# ---------------------------------------------------------------------------


def _parse_iso_dt(value: Any) -> datetime | None:
    """Parse an ISO-8601 date or datetime; tolerate trailing 'Z'.

    Returns None on any parse failure so callers can decide whether the
    miss is a problem (process gate: yes, it's a fail) or merely a
    fallback signal (effective_expiry: yes, fall back to default).
    """
    if not isinstance(value, str) or not value:
        return None
    try:
        # datetime.fromisoformat accepts both date and datetime strings,
        # but pre-3.11 it can't parse the trailing 'Z' suffix.
        normalised = value.replace("Z", "+00:00")
        dt = datetime.fromisoformat(normalised)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def effective_expiry(bug: dict, *, default_days: int) -> datetime | None:
    """Return the expiry date currently in effect for a bug.

    Order of precedence:
        1. Latest extension by `extended_at` if any extensions exist.
        2. Explicit `expiry` field on the bug.
        3. `surfaced_at + default_days` as the implicit fallback.

    Returns None when none of the three sources yields a parseable date.
    """
    extensions = bug.get("extensions") or []
    if isinstance(extensions, list) and extensions:
        # Sort by extended_at (the *date* the extension was approved) so
        # the most recently-approved extension wins. Unparseable entries
        # sort to the front and are ignored as long as a parseable one
        # exists.
        ranked: list[tuple[datetime, datetime]] = []
        for ext in extensions:
            if not isinstance(ext, dict):
                continue
            extended_at = _parse_iso_dt(ext.get("extended_at"))
            new_expiry = _parse_iso_dt(ext.get("new_expiry"))
            if extended_at and new_expiry:
                ranked.append((extended_at, new_expiry))
        if ranked:
            ranked.sort(key=lambda t: t[0])
            return ranked[-1][1]

    explicit = _parse_iso_dt(bug.get("expiry"))
    if explicit:
        return explicit

    surfaced = _parse_iso_dt(bug.get("surfaced_at"))
    if surfaced:
        return surfaced + timedelta(days=default_days)

    return None


def bug_is_past_expiry(
    bug: dict, *, now: datetime, default_days: int
) -> bool:
    """True iff the bug is still open AND the effective expiry is in the past.

    Closed bugs are never past expiry (the 14 d clock stops at closure).
    Bugs with an unresolvable expiry are NOT considered past — that case
    is handled separately by the process gate (which fails on missing
    expiry) so we don't double-flag.
    """
    if bug.get("status") != "open":
        return False
    expiry = effective_expiry(bug, default_days=default_days)
    if expiry is None:
        return False
    return now > expiry


# ---------------------------------------------------------------------------
# 226.H.process — every bug ticketed/owned/expiry'd within 48 h
# ---------------------------------------------------------------------------


def check_process(doc: dict, *, now: datetime) -> tuple[bool, list[str]]:
    """Validate the 226.H.process contract.

    Each *open* bug is checked. If the surfacing event is within the
    grace window, missing fields are reported as `[grace]` (informational)
    rather than `[FAIL]`. After the grace window, missing ticket / owner
    / expiry are hard failures.
    """
    process_cfg = doc.get("process") or {}
    grace_hours = process_cfg.get(
        "ticket_grace_period_hours", DEFAULT_TICKET_GRACE_HOURS
    )
    default_days = doc.get("default_expiry_days", DEFAULT_EXPIRY_DAYS)
    grace_window = timedelta(hours=grace_hours)

    bugs = doc.get("bugs") or []
    messages: list[str] = []
    any_fail = False

    if not bugs:
        messages.append("  [ok] no audit-exposed bugs in the ledger")
        return True, messages

    for bug in bugs:
        bug_id = bug.get("id", "(no-id)")
        if bug.get("status") != "open":
            messages.append(f"  [ok] {bug_id} — closed, process gate skipped")
            continue

        surfaced = _parse_iso_dt(bug.get("surfaced_at"))
        within_grace = (
            surfaced is not None and (now - surfaced) <= grace_window
        )

        problems: list[str] = []
        if not (bug.get("ticket") or "").strip():
            problems.append("ticket")
        if not (bug.get("owner") or "").strip():
            problems.append("owner")
        # Distinguish "missing → fall back to default" from
        # "explicitly set but unparseable → typo, fail loudly". A literal
        # null/empty `expiry` plus a parseable `surfaced_at` is fine —
        # the 14-d default applies. A non-empty string we can't parse
        # is a data-quality bug in the ledger entry itself.
        raw_expiry = bug.get("expiry")
        if isinstance(raw_expiry, str) and raw_expiry.strip() and _parse_iso_dt(raw_expiry) is None:
            problems.append("expiry")
        elif effective_expiry(bug, default_days=default_days) is None:
            problems.append("expiry")

        if not problems:
            messages.append(f"  [ok] {bug_id} — process complete")
            continue

        if within_grace:
            remaining = grace_window - (now - surfaced) if surfaced else grace_window
            hours_left = max(0.0, remaining.total_seconds() / 3600)
            messages.append(
                f"  [grace] {bug_id} — missing {', '.join(problems)}; "
                f"{hours_left:.1f}h of {grace_hours}h grace remaining"
            )
            continue

        any_fail = True
        for field in problems:
            messages.append(
                f"  [FAIL] {bug_id} — {field} missing past "
                f"{grace_hours}h grace window"
            )

    return (not any_fail), messages


# ---------------------------------------------------------------------------
# 226.H.gate — skip-category counting helper (consumed by the close gate)
# ---------------------------------------------------------------------------


def count_category_skips(counts: dict[str, int], prefix: str) -> int:
    """Sum the counts of every skip reason whose verbatim prefix matches.

    Case-sensitive on purpose: the canonical prefix is a constant, and
    fuzzy matching would silently swallow legitimate-looking-but-wrong
    skip reasons that drifted away from the canonical form.
    """
    return sum(count for reason, count in counts.items() if reason.startswith(prefix))


def _aggregate_skip_events(artifact_dir: Path) -> dict[str, int]:
    """Local re-implementation of the skip-counter aggregator.

    We don't import from `check_skip_counter` because:
      (a) That script lives in the same directory but isn't a package, so
          the import path is awkward, and
      (b) The skip-counter is the consumer of *our* gate config, so a
          dependency in the other direction would be a circle.

    The format is identical: append-only JSONL, one event per line, with
    a `reason` field. Any malformed line raises — silent drops are the
    anti-pattern this whole initiative kills.
    """
    counts: dict[str, int] = {}
    if not artifact_dir.exists():
        return counts
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
                counts[reason] = counts.get(reason, 0) + 1
    return counts


# ---------------------------------------------------------------------------
# 226.H.close — end-of-cycle gate
# ---------------------------------------------------------------------------


def check_close(
    doc: dict,
    *,
    skip_counts: dict[str, int],
    now: datetime,
) -> tuple[bool, list[str]]:
    """Validate the 226.H.close contract.

    Two independent failure modes:
      1. Total audit-bug skip count must be ≤ cycle.residual_max.
      2. No open bug may be past effective expiry.
    """
    cycle = doc.get("cycle") or {}
    residual_max = cycle.get("residual_max", DEFAULT_RESIDUAL_MAX)
    default_days = doc.get("default_expiry_days", DEFAULT_EXPIRY_DAYS)
    prefix = doc.get("skip_reason_prefix", AUDIT_BUG_SKIP_REASON_PREFIX)

    messages: list[str] = []
    any_fail = False

    category_count = count_category_skips(skip_counts, prefix)
    if category_count <= residual_max:
        messages.append(
            f"  [ok] residual long-tail: {category_count} skip(s) ≤ {residual_max} cap"
        )
    else:
        any_fail = True
        messages.append(
            f"  [FAIL] residual long-tail exceeded: "
            f"{category_count} skip(s) > {residual_max} cap "
            f"(prefix={prefix!r})"
        )

    bugs = doc.get("bugs") or []
    past_expiry: list[str] = []
    for bug in bugs:
        if bug_is_past_expiry(bug, now=now, default_days=default_days):
            past_expiry.append(bug.get("id", "(no-id)"))
    if not past_expiry:
        messages.append("  [ok] no open bug is past expiry without extension")
    else:
        any_fail = True
        for bug_id in past_expiry:
            messages.append(
                f"  [FAIL] {bug_id} — past expiry without an active extension review"
            )

    return (not any_fail), messages


# ---------------------------------------------------------------------------
# Loader + CLI
# ---------------------------------------------------------------------------


def load_ledger(path: Path) -> dict:
    """Read + parse the ledger JSON, preserving file-path context on errors.

    Schema validation runs separately via `validate_schema()`. This loader
    only enforces the JSON-object-at-the-root constraint; everything else
    is reported by the validator with full diagnostics.
    """
    if not path.exists():
        raise FileNotFoundError(f"Ledger not found: {path}")
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Malformed ledger at {path}: {exc}") from exc
    if not isinstance(parsed, dict):
        raise ValueError(
            f"Malformed ledger at {path}: root must be a JSON object, "
            f"got {type(parsed).__name__}"
        )
    return parsed


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Validate the audit-exposed-bugs ledger and gate the bug-fix "
            "bandwidth contract (Phase 226.H)."
        )
    )
    parser.add_argument(
        "--mode",
        required=True,
        choices=["validate", "process", "close", "emit-gate-config"],
        help=(
            "validate = schema only; "
            "process = 226.H.process (ticket/owner/expiry within grace); "
            "close = 226.H.close (residual + past-expiry); "
            "emit-gate-config = print canonical prefix + threshold as JSON."
        ),
    )
    parser.add_argument(
        "--ledger",
        type=Path,
        default=Path("docs/audit-exposed-bugs.json"),
        help="Path to the ledger document (JSON).",
    )
    parser.add_argument(
        "--artifact-dir",
        type=Path,
        default=Path("test-results"),
        help="Skip-events artifact directory (close mode only).",
    )
    parser.add_argument(
        "--now",
        type=str,
        default=None,
        help=(
            "Override 'now' for deterministic tests; ISO-8601 datetime. "
            "Defaults to current UTC."
        ),
    )
    return parser


def _resolve_now(arg: str | None) -> datetime:
    if arg:
        parsed = _parse_iso_dt(arg)
        if not parsed:
            raise SystemExit(f"--now must be ISO-8601, got {arg!r}")
        return parsed
    return datetime.now(timezone.utc)


def main(argv: list[str] | None = None) -> int:
    args = _build_arg_parser().parse_args(argv)

    if args.mode == "emit-gate-config":
        # The skip-counter CI step consumes this output to construct its
        # `--category` flag without re-declaring the prefix string.
        payload = {
            "skip_reason_prefix": AUDIT_BUG_SKIP_REASON_PREFIX,
            "category_threshold": DEFAULT_CATEGORY_THRESHOLD,
            "default_expiry_days": DEFAULT_EXPIRY_DAYS,
            "default_residual_max": DEFAULT_RESIDUAL_MAX,
            "default_ticket_grace_hours": DEFAULT_TICKET_GRACE_HOURS,
        }
        print(json.dumps(payload, indent=2))
        return 0

    doc = load_ledger(args.ledger)
    schema_problems = validate_schema(doc)

    if args.mode == "validate":
        if schema_problems:
            print("Ledger schema validation failed:")
            for p in schema_problems:
                print(f"  [FAIL] {p}")
            return 1
        print("Ledger schema OK.")
        return 0

    # Both `process` and `close` need a valid schema before they can run.
    if schema_problems:
        print("Ledger schema validation failed (run --mode validate to see details):")
        for p in schema_problems:
            print(f"  [FAIL] {p}")
        return 1

    now = _resolve_now(args.now)

    if args.mode == "process":
        passed, msgs = check_process(doc, now=now)
        grace_hours = (doc.get("process") or {}).get(
            "ticket_grace_period_hours", DEFAULT_TICKET_GRACE_HOURS
        )
        header = (
            f"226.H.process gate — ledger={args.ledger}, "
            f"now={now.isoformat()}, grace={grace_hours}h"
        )
        print(header)
        for m in msgs:
            print(m)
        if not passed:
            print(
                "\n::error title=226.H.process gate::"
                "An audit-exposed bug is missing ticket/owner/expiry past "
                "the 48 h grace window. Backfill the ledger entry."
            )
            return 1
        return 0

    if args.mode == "close":
        try:
            counts = _aggregate_skip_events(args.artifact_dir)
        except RuntimeError as exc:
            print(f"::error title=226.H.close gate::{exc}")
            return 2
        passed, msgs = check_close(doc, skip_counts=counts, now=now)
        header = (
            f"226.H.close gate — ledger={args.ledger}, "
            f"artifact-dir={args.artifact_dir}, "
            f"now={now.isoformat()}"
        )
        print(header)
        for m in msgs:
            print(m)
        if not passed:
            print(
                "\n::error title=226.H.close gate::"
                "Residual audit-bug skip count exceeded the cycle cap, "
                "or an open bug is past its effective expiry without an "
                "extension review. Fix root causes or extend explicitly."
            )
            return 1
        return 0

    raise SystemExit(f"Unhandled mode: {args.mode}")


if __name__ == "__main__":
    sys.exit(main())
