#!/usr/bin/env python3
"""
283.6.7 / 284.E.6 — stale default checker.

Scans the feature-flag registry for GA-stage flags with ``default_new=False``
that lack documented justification. A GA flag defaulting to OFF for new tenants
must have an explicit reason: DPO signoff required, opt-in by design, cost
considerations, or security implications.

Flags with ``requires_dpo_signoff=True`` or ``requires_legal_signoff=True`` are
automatically considered justified. Other flags with ``default_new=False`` must
have a justification documented via the ``related_audit_report`` field (which
points to an ADR or decision record).

Exit 0 when all GA flags with default_new=False have documented justification;
exit 1 when any lack justification (CI blocks the PR until documented).

Usage
-----
    python scripts/check_stale_defaults.py              # human-readable report
    python scripts/check_stale_defaults.py --json       # JSON output for CI
    python scripts/check_stale_defaults.py --fix        # suggests fixes
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT))


def _load_registry():
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "feature_flag_registry",
        _REPO_ROOT / "hub" / "apps" / "tenants" / "feature_flag_registry.py",
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("Failed to load feature_flag_registry module spec")
    module = importlib.util.module_from_spec(spec)
    sys.modules["feature_flag_registry"] = module
    spec.loader.exec_module(module)
    return module.REGISTRY


# ── Auto-justified conditions ──────────────────────────────────────────

def _has_justification(flag) -> tuple[bool, str]:
    """Return (justified: bool, reason: str)."""
    # DPO / Legal signoff required → automatically justified.
    if flag.requires_dpo_signoff:
        return True, "requires_dpo_signoff=True (DPO-approval-gated feature)"
    if flag.requires_legal_signoff:
        return True, "requires_legal_signoff=True (Legal-approval-gated feature)"

    # Documented justification via related_audit_report or description keywords.
    justification_markers = [
        "sampling", "safer default", "opt-in", "opt in", "explicit opt",
        "cost", "premium", "forensic", "power-user", "power user",
        "DPO signoff", "Legal signoff", "ADR", "decision record",
    ]
    desc_lower = flag.description.lower()
    report = (flag.related_audit_report or "").lower()
    combined = desc_lower + " " + report

    for marker in justification_markers:
        if marker in combined:
            return True, f"justification found in description/report: '{marker}'"

    # Sensitive flags → implicitly justified (two-person rule gates the flip).
    if flag.sensitive:
        return True, "sensitive=True (two-person rule gates the flip)"

    return False, "no documented justification found"


def _check(registry) -> tuple[list[dict], bool]:
    """Return (rows, all_justified)."""
    rows: list[dict] = []
    ga_flags = [f for f in registry if f.stage == "GA" and not f.default_new_tenants]

    for flag in sorted(ga_flags, key=lambda f: f.name):
        justified, reason = _has_justification(flag)
        rows.append({
            "name": flag.name,
            "stage": flag.stage,
            "default_new": flag.default_new_tenants,
            "requires_dpo_signoff": flag.requires_dpo_signoff,
            "requires_legal_signoff": flag.requires_legal_signoff,
            "sensitive": flag.sensitive,
            "justified": justified,
            "reason": reason,
            "owner_team": flag.owner_team,
        })

    all_justified = all(r["justified"] for r in rows)
    return rows, all_justified


def _format_human(rows: list[dict]) -> str:
    if not rows:
        return "✓ No GA flags with default_new=False. Nothing to check.\n"

    lines: list[str] = []
    lines.append(f"Stale Default Check — {datetime.now(tz=timezone.utc).isoformat()}")
    lines.append(f"Flags checked: {len(rows)} (GA flags with default_new=False)")
    lines.append("")
    lines.append(f"{'FLAG':<50} {'JUSTIFIED':<12} {'REASON'}")
    lines.append("-" * 100)

    for r in rows:
        status = "✓" if r["justified"] else "✗ MISSING"
        lines.append(f"{r['name']:<50} {status:<12} {r['reason']}")

    unjustified = [r for r in rows if not r["justified"]]
    lines.append("-" * 100)
    lines.append(f"  Justified:  {sum(1 for r in rows if r['justified'])}")
    lines.append(f"  Unjustified: {len(unjustified)}")

    if unjustified:
        lines.append("\nFlags needing justification:")
        for r in unjustified:
            lines.append(
                f"  - {r['name']} ({r['owner_team']}): "
                "add justification to description, related_audit_report, or "
                "set requires_dpo_signoff=True / requires_legal_signoff=True"
            )

    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="283.6.7 — stale default checker for GA flags."
    )
    parser.add_argument(
        "--json", action="store_true", help="Emit JSON instead of human-readable."
    )
    parser.add_argument(
        "--fix", action="store_true",
        help="Print suggested fixes for unjustified flags.",
    )
    args = parser.parse_args()

    registry = _load_registry()
    rows, all_justified = _check(registry)

    if args.json:
        output = {
            "checked_at": datetime.now(tz=timezone.utc).isoformat(),
            "all_justified": all_justified,
            "flags": rows,
        }
        json.dump(output, sys.stdout, indent=2)
        sys.stdout.write("\n")
    else:
        sys.stdout.write(_format_human(rows))

    if args.fix:
        unjustified = [r for r in rows if not r["justified"]]
        if unjustified:
            print("\nSuggested fixes:")
            for r in unjustified:
                print(f"  {r['name']}:")
                print(f"    Option A: Set requires_dpo_signoff=True in registry (if privacy-related)")
                print(f"    Option B: Set requires_legal_signoff=True in registry (if legal-related)")
                print(f"    Option C: Add justification to flag description (e.g., 'opt-in premium feature')")
                print(f"    Option D: Write ADR at docs/adr/{r['name']}-default.md and set related_audit_report")
        else:
            print("\nNo fixes needed — all flags justified.")

    if not all_justified:
        sys.stderr.write(
            "\nFAIL: at least one GA flag has default_new=False without documented "
            "justification. Add justification per the policy above, then re-run.\n"
        )
        return 1

    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
