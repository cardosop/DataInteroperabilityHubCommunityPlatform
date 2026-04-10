#!/usr/bin/env python3
"""Check MVP documentation boundary (D157).

Walks docs/mvpdocs/ and fails if any user-facing page references a
post-MVP feature without a [Post-MVP] badge.  Checks three vectors:

1. API paths: /api/v1/{gated-prefix} links
2. SDK classes: post-MVP SDK class names in fenced Python blocks
3. CLI commands: post-MVP CLI group names in fenced bash/shell blocks

Uses the canonical gated-prefix list from hub/apps/api/mvp_mode.py
via ast.parse (no Django import, no regex on source).  The drift test
at the end asserts the extracted prefix list matches expectations.

Phase 217.0.7 / 217.5.1
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
MVPDOCS_DIR = REPO_ROOT / "docs" / "mvpdocs"
MVP_MODE_FILE = (
    REPO_ROOT / "hub" / "apps" / "api" / "mvp_mode.py"
)

# Post-MVP SDK classes (gated via ml/, mesh/, etc.)
POST_MVP_SDK_CLASSES = frozenset(
    {
        "AIAPI",
        "BaaSAPI",
        "InferenceAPI",
        "MarketplaceIntegrationAPI",
        "MeshAPI",
        "ModelServingAPI",
        "ODHIntegrationAPI",
        "ScheduledExportAPI",
        "ScheduledIngestionAPI",
        "SocialAPI",
        "TrainingAPI",
        "TransformationAPI",
        "VirtualizationAPI",
    }
)

# Post-MVP CLI groups
POST_MVP_CLI_GROUPS = frozenset(
    {
        "mesh",
        "virtualization",
        "baas",
        "ml",
        "transformation",
        "scheduled-ingestion",
        "scheduled-export",
    }
)


def _extract_gated_prefixes() -> frozenset[str]:
    """Extract MVP_GATED_RELATIVE_PREFIXES via ast.parse."""
    tree = ast.parse(MVP_MODE_FILE.read_text())
    for node in ast.walk(tree):
        if isinstance(node, (ast.AnnAssign, ast.Assign)):
            targets = (
                [node.target]
                if isinstance(node, ast.AnnAssign)
                else node.targets
            )
            for t in targets:
                if (
                    isinstance(t, ast.Name)
                    and t.id == "MVP_GATED_RELATIVE_PREFIXES"
                ):
                    val = node.value
                    if (
                        isinstance(val, ast.Call)
                        and isinstance(val.func, ast.Name)
                        and val.func.id == "frozenset"
                    ):
                        elts = val.args[0].elts
                    else:
                        elts = val.elts
                    return frozenset(
                        ast.literal_eval(e) for e in elts
                    )
    msg = "Could not find MVP_GATED_RELATIVE_PREFIXES"
    raise RuntimeError(msg)


def _page_has_badge(content: str) -> bool:
    """Check if page has a [Post-MVP] badge or marker."""
    return "[Post-MVP]" in content


_FENCED_PYTHON = re.compile(
    r"```(?:python|py)\n(.*?)```", re.DOTALL
)
_FENCED_BASH = re.compile(
    r"```(?:bash|shell|sh)\n(.*?)```", re.DOTALL
)


def _check_sdk_classes(
    content: str, rel: str, errors: list[str],
) -> None:
    """Check for post-MVP SDK class references in Python blocks."""
    for block in _FENCED_PYTHON.findall(content):
        for cls in POST_MVP_SDK_CLASSES:
            if cls in block:
                errors.append(
                    f"{rel}: references post-MVP SDK class"
                    f" {cls!r} in Python code block"
                    " without [Post-MVP] badge"
                )


def _check_cli_commands(
    content: str, rel: str, errors: list[str],
) -> None:
    """Check for post-MVP CLI group references in bash blocks."""
    for block in _FENCED_BASH.findall(content):
        for group in POST_MVP_CLI_GROUPS:
            pattern = rf"\bdatahub\s+{re.escape(group)}\b"
            if re.search(pattern, block):
                errors.append(
                    f"{rel}: references post-MVP CLI group"
                    f" 'datahub {group}' in code block"
                    " without [Post-MVP] badge"
                )


def _check_api_paths(
    content: str,
    rel: str,
    api_patterns: list[re.Pattern[str]],
    errors: list[str],
) -> None:
    """Check for post-MVP API path references."""
    for pattern in api_patterns:
        matches = pattern.findall(content)
        if matches:
            errors.append(
                f"{rel}: references post-MVP path"
                f" {matches[0]!r} without [Post-MVP] badge"
            )


def _drift_test(prefixes: frozenset[str]) -> list[str]:
    """Assert extracted prefixes match expected set."""
    expected = frozenset(
        {
            "mesh/",
            "virtualization/",
            "integrations/",
            "baas/",
            "ml/",
            "ai/",
            "transformation/",
            "social/",
            "scheduled-ingestions/",
            "scheduled-exports/",
        }
    )
    errors: list[str] = []
    extra = prefixes - expected
    missing = expected - prefixes
    if extra:
        errors.append(
            f"DRIFT: unexpected prefixes in mvp_mode.py:"
            f" {sorted(extra)}"
        )
    if missing:
        errors.append(
            f"DRIFT: missing prefixes from mvp_mode.py:"
            f" {sorted(missing)}"
        )
    return errors


def main() -> int:
    if not MVP_MODE_FILE.exists():
        print(f"SKIP: {MVP_MODE_FILE} not found")
        return 0

    prefixes = _extract_gated_prefixes()

    # Drift test first
    drift_errors = _drift_test(prefixes)
    if drift_errors:
        print("FAIL: prefix drift detected:")
        for e in drift_errors:
            print(f"  - {e}")
        return 1

    # Build API path patterns
    api_patterns: list[re.Pattern[str]] = []
    for prefix in prefixes:
        clean = prefix.rstrip("/")
        api_patterns.append(
            re.compile(rf"/api/v1/{re.escape(clean)}\b")
        )

    errors: list[str] = []

    if not MVPDOCS_DIR.exists():
        print(f"SKIP: {MVPDOCS_DIR} does not exist yet")
        return 0

    for md_file in sorted(MVPDOCS_DIR.rglob("*.md")):
        rel = str(md_file.relative_to(MVPDOCS_DIR))
        if rel.startswith("_"):
            continue

        content = md_file.read_text(errors="replace")

        if _page_has_badge(content):
            continue

        _check_api_paths(content, rel, api_patterns, errors)
        _check_sdk_classes(content, rel, errors)
        _check_cli_commands(content, rel, errors)

    if errors:
        print(
            f"FAIL: {len(errors)} MVP boundary violation(s):"
        )
        for e in errors:
            print(f"  - {e}")
        return 1

    checks = (
        f"{len(prefixes)} API prefixes, "
        f"{len(POST_MVP_SDK_CLASSES)} SDK classes, "
        f"{len(POST_MVP_CLI_GROUPS)} CLI groups"
    )
    print(f"PASS: {checks} checked across docs/mvpdocs/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
