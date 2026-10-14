#!/usr/bin/env python3
"""285.12.4.11 / W6.4 — Check CLI ↔ SDK module parity.

Every CLI command module in ``cli/datahub_cli/commands/`` MUST have an
SDK counterpart module in ``sdk/python/datahub_interoperability/``.  A
missing counterpart FAILS the gate (exit 1) unless the module is
explicitly listed in the CLI-only floor below WITH a reason.

W6.4 root fix: the pre-fix checker hardcoded a 14-entry subset of the
command tree, matched the SDK by fuzzy substring, and ALWAYS exited 0 —
a CLI module could vanish from the SDK and the gate still printed
"all CLI commands have SDK counterparts".

Floor-reduction plan (W6.4): the 7 CLI-only modules below are the
documented debt.  Reduction order (each = a small SDK module reusing
the shared client):
  1. warehouses   — SDK module exposing the warehouse registry APIs.
  2. consent      — SDK module for consent purposes/records.
  3. dsar         — SDK module for DSAR requests.
  4. databricks   — SDK module for the estate registry surface
                    (read-only mirrors of the control-plane metadata).
  5. health       — SDK already has ``DataHubClient.check_health()``;
                    fold the remaining paths into it, then drop the
                    exemption.
  6. graphql      — SDK covers GraphQL through client-level methods;
                    document and drop the exemption.
  7. phase232_programme — programme-tracking surface; CLI-only by
                    design (operator tooling) — keep documented.
Each removal MUST update the floor count and this plan.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
_DEFAULT_CLI_DIR = _REPO / "cli" / "datahub_cli" / "commands"
_DEFAULT_SDK_DIR = _REPO / "sdk" / "python" / "datahub_interoperability"

# CLI-only floor: module → reason (every entry MUST carry a real reason —
# pinned by scripts/tests/test_check_cli_sdk_parity.py).
_CLI_ONLY_MODULES: dict[str, str] = {
    "warehouses": "SDK warehouse module not built yet (floor item 1)",
    "consent": "SDK consent module not built yet (floor item 2)",
    "dsar": "SDK DSAR module not built yet (floor item 3)",
    "databricks": "estate registry surface; SDK module pending (floor item 4)",
    "health": "covered by DataHubClient.check_health(); fold + drop exemption (floor item 5)",
    "graphql": "SDK covers GraphQL via client-level methods (floor item 6)",
    "phase232_programme": "programme-tracking operator tooling — CLI-only by design (floor item 7)",
}

# Non-domain plumbing in commands/ that has no SDK counterpart BY DESIGN.
_PLUMBING = {"__init__"}


def collect_modules(directory: Path) -> set[str]:
    return {
        f.stem
        for f in directory.glob("*.py")
        if f.stem != "__init__" and not f.name.startswith("_")
    }


def check(cli_dir: Path, sdk_dir: Path) -> int:
    cli_modules = collect_modules(cli_dir)
    sdk_modules = collect_modules(sdk_dir)

    # Exclude error/helpers modules that pair differently: a CLI module
    # counts as covered when the SDK has an exact-stem peer.
    missing = sorted(
        name
        for name in cli_modules
        if name not in _CLI_ONLY_MODULES
        and name not in _PLUMBING
        and name not in sdk_modules
    )

    floor = len(_CLI_ONLY_MODULES)
    print(f"CLI commands: {len(cli_modules)} | SDK modules: {len(sdk_modules)}")
    print(f"CLI-only floor: {floor} ({', '.join(sorted(_CLI_ONLY_MODULES))})")
    if missing:
        print(f"Missing SDK modules (FAIL): {', '.join(missing)}")
        return 1
    print("CLI/SDK parity: every CLI command module has an SDK counterpart")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--cli-dir", type=Path, default=_DEFAULT_CLI_DIR,
        help="CLI commands directory (test seam)",
    )
    parser.add_argument(
        "--sdk-dir", type=Path, default=_DEFAULT_SDK_DIR,
        help="SDK package directory (test seam)",
    )
    args = parser.parse_args()
    return check(args.cli_dir, args.sdk_dir)


if __name__ == "__main__":
    sys.exit(main())
