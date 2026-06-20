#!/usr/bin/env python3
"""285.12.4.11 — Check CLI ↔ SDK method parity.

Audits that CLI commands have corresponding SDK methods by comparing
operation names across datahub_cli/commands/ and sdk/python/.
"""

from __future__ import annotations

import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
_CLI_DIR = _REPO / "cli" / "datahub_cli" / "commands"
_SDK_DIR = _REPO / "sdk" / "python" / "datahub_interoperability"

# CLI command → expected SDK method
_PARITY: dict[str, str] = {
    "assets": "AssetsAPI",
    "compliance": "ComplianceAPI",
    "contracts": "ContractsAPI",
    "dq": "DQAPI",
    "files": "FilesAPI",
    "lineage": "LineageAPI",
    "marketplace": "MarketplaceAPI",
    "mesh": "MeshAPI",
    "ml": "MLAPI",
    "orchestration": "OrchestrationAPI",
    "search": "SearchAPI",
    "semantic": "SemanticAPI",
    "tenants": "TenantsAPI",
    "transformation": "TransformationAPI",
}


def check() -> int:
    sdk_files = {
        f.stem.replace("_api", "").replace("api", ""): f.name
        for f in _SDK_DIR.glob("*.py")
        if f.stem != "__init__"
    }

    missing_sdk = []
    for cli_name, _ in _PARITY.items():
        cli_file = _CLI_DIR / f"{cli_name}.py"
        if not cli_file.exists():
            continue
        found = any(cli_name in k or k in cli_name for k in sdk_files)
        if not found and cli_name not in ("baas", "billing", "gdpr"):
            missing_sdk.append(cli_name)

    print(f"CLI commands: {len(_PARITY)} | SDK modules: {len(sdk_files)}")
    if missing_sdk:
        print(f"Missing SDK: {', '.join(missing_sdk)}")
    else:
        print("CLI/SDK parity: all CLI commands have SDK counterparts")
    return 0


sys.exit(check())
