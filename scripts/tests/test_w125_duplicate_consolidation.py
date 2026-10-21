"""W12.5 duplicate-consolidation pins (RED-first; no Django, no mocks).

Pins the design-table row-3 contract ("duplicated logic with drift"):
1. ONE ``IsTenantAdmin`` — exactly one class definition in non-test
   hub code, and every import resolves to the canonical
   ``hub.apps.auth.permissions`` module;
2. mvp_detection single-sourced — the CLI/SDK vendored copies are
   byte-identical to the canonical ``shared/mvp_detection.py`` (the
   sanctioned cross-package pattern: vendored for wheel
   self-containment, drift-pinned for single-sourcing);
3. ONE bundle-size gate script — the unwired frontend/scripts copy is
   gone (CI wires scripts/bundle_size_check.mjs);
4. ONE error envelope — the nested ``{"error": {...}}`` helpers are
   gone; every envelope construction resolves to the canonical flat
   ``{"detail", "code", "details"}`` helper; the raw-error-dict lint
   exists and is wired into CI;
5. plan seeders single-sourced — the enterprise backfill caps live in
   ``plan_defaults.py`` (no divergent local hardcode).
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
HUB = REPO / "hub"


def _py_files(root: Path) -> list[Path]:
    return [p for p in root.rglob("*.py") if "__pycache__" not in p.parts]


def _non_test_py_files() -> list[Path]:
    return [p for p in _py_files(HUB) if "/tests/" not in str(p) and not p.name.startswith("test_")]


def test_single_is_tenant_admin_definition():
    """Exactly ONE ``class IsTenantAdmin`` in non-test hub code."""
    sites = []
    for path in _non_test_py_files():
        for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if re.match(r"^class IsTenantAdmin\b", line):
                sites.append(f"{path}:{i}")
    assert len(sites) == 1, f"IsTenantAdmin defined at {sites} (want exactly 1)"


def test_is_tenant_admin_imports_resolve_to_canonical_module():
    """Every ``from X import ... IsTenantAdmin`` resolves to
    hub.apps.auth.permissions (re-exports count as canonical only when
    the import chain bottoms out there — pinned by the definition test
    above). ``IsTenantAdminProcessorAgreements`` is a distinct name and
    does not match (word boundary)."""
    offenders = []
    for path in _non_test_py_files():
        for line in path.read_text(encoding="utf-8").splitlines():
            match = re.match(r"from\s+(\S+)\s+import\s+(.*)", line)
            if not match:
                continue
            module, spec = match.groups()
            if re.search(r"\bIsTenantAdmin\b", spec) and module != "hub.apps.auth.permissions":
                offenders.append(f"{path}:{module}")
    assert not offenders, (
        f"IsTenantAdmin imports not resolving to hub.apps.auth.permissions: {offenders}"
    )


def test_mvp_detection_vendored_copies_match_shared():
    """The CLI + SDK vendored copies are byte-identical to the canonical
    shared/mvp_detection.py (single source; wheels stay self-contained)."""
    canonical = (REPO / "shared" / "mvp_detection.py").read_bytes()
    vendors = (
        REPO / "cli" / "datahub_cli" / "_mvp_detection.py",
        REPO / "sdk" / "python" / "datahub_interoperability" / "_mvp_detection.py",
    )
    for vendor in vendors:
        assert vendor.exists(), f"vendored copy missing: {vendor}"
        assert vendor.read_bytes() == canonical, (
            f"{vendor} diverged from shared/mvp_detection.py — sync it"
        )


def test_single_bundle_size_script():
    """scripts/bundle_size_check.mjs is the ONE bundle-size gate (CI-wired);
    the unwired frontend/scripts copy is deleted."""
    assert (REPO / "scripts" / "bundle_size_check.mjs").exists()
    assert not (REPO / "frontend" / "scripts" / "bundle_size_check.mjs").exists(), (
        "frontend/scripts/bundle_size_check.mjs duplicates the wired gate — delete it"
    )


def test_single_error_envelope_shape():
    """The nested {"error": {...}} envelope is gone — one flat
    {"detail", "code", "details"} contract. AST-based: flags only
    ``Response(... {"error": {...}} ...)`` constructions (OpenAPI
    docstrings and schema strings legitimately mention the word)."""
    offenders = []
    for path in _non_test_py_files():
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            name = None
            if isinstance(node.func, ast.Name):
                name = node.func.id
            elif isinstance(node.func, ast.Attribute):
                name = node.func.attr
            if name not in ("Response", "JsonResponse"):
                continue
            if not node.args or not isinstance(node.args[0], ast.Dict):
                continue
            for k, v in zip(node.args[0].keys, node.args[0].values, strict=True):
                # The divergent envelope: {"error": {<object>}} — the
                # ErrorResponse/format_error nested shape. A plain
                # {"error": "string"} is the legacy simple shape tracked
                # by the raw-error-dict lint, not this pin.
                if isinstance(k, ast.Constant) and k.value == "error" and isinstance(v, ast.Dict):
                    offenders.append(f"{path}:{node.lineno}")
    assert not offenders, f"nested error envelope still constructed at: {offenders}"


def test_raw_error_dict_lint_exists_and_wired():
    """The raw-error-dict lint exists and is wired into the CI lint list."""
    lint = REPO / "scripts" / "check_raw_error_dicts.py"
    assert lint.exists(), "scripts/check_raw_error_dicts.py missing"
    lint_workflow = (REPO / ".github" / "workflows" / "_reusable.lint.yml").read_text(
        encoding="utf-8"
    )
    assert "check_raw_error_dicts" in lint_workflow, (
        "the raw-error-dict lint is not wired into the CI lint workflow"
    )


def test_enterprise_backfill_caps_single_sourced():
    """backfill_enterprise_limits imports its caps from plan_defaults —
    no divergent local hardcode."""
    command = (
        HUB / "apps" / "tenants" / "management" / "commands" / "backfill_enterprise_limits.py"
    ).read_text(encoding="utf-8")
    assert "_ENTERPRISE_DEFAULT_CAPS" not in command, (
        "the backfill command still hardcodes its own enterprise caps"
    )
    assert "plan_defaults" in command, "the backfill command does not import plan_defaults"


if __name__ == "__main__":
    sys.exit(0 if __import__("pytest").main([__file__, "-q", "--no-header"]) == 0 else 1)
