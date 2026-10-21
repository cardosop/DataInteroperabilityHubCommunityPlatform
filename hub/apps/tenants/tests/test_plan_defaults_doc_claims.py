"""
W12.8 (oss-release-remediation) — plan_defaults.py doc-claim veracity pins.

The named liar: the module docstring claimed ``PersonalTenantService``
imports this catalog.  It never did — the service resolves the seeded
FREE plan by slug at runtime (the seeder makes the rows it looks up).
The docstring now names the REAL importers, and these pins keep it
honest:

  * every ``<name>.py`` module named in the docstring's "Imported by"
    clause must exist and actually import the catalog (AST-verified);
  * the ``PersonalTenantService`` clause must state the correction and
    the correction must be TRUE (services.py has no plan_defaults
    import — AST-verified, not a string check);
  * every tier-count claim in the file ("Platform Plans (6 tiers)"
    comment included) must match the actual list lengths;
  * the "non-None limits_json and tier_profile" claim must hold for
    every entry in the real imported catalog.

RED phase: before the W12.8 fix this file failed three ways — the
docstring named a non-importer, the section comment undercounted
PLATFORM_PLANS as 6 tiers, and the corrected "does NOT import" clause
was absent.  All pins run against the REAL module (imported), no mocks.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

from hub.apps.tenants import plan_defaults

_REPO_ROOT = Path(__file__).resolve().parents[4]
_MODULE_PATH = _REPO_ROOT / "hub" / "apps" / "tenants" / "plan_defaults.py"
_SERVICES_PATH = _REPO_ROOT / "hub" / "apps" / "tenants" / "services.py"
_MGMT_COMMANDS = (
    _REPO_ROOT / "hub" / "apps" / "tenants" / "management" / "commands"
)

_SRC = _MODULE_PATH.read_text(encoding="utf-8")
_DOCSTRING = ast.get_docstring(ast.parse(_SRC), clean=False) or ""


def _ast_imports_plan_defaults(path: Path) -> bool:
    """True iff the module at `path` imports the plan_defaults catalog.

    AST-based (not a substring grep): covers
    ``from hub.apps.tenants.plan_defaults import ...``,
    ``from hub.apps.tenants import plan_defaults``, and
    ``from .plan_defaults import ...`` forms — and nothing else.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.module and node.module.endswith("plan_defaults"):
                return True
            if any(alias.name == "plan_defaults" for alias in node.names):
                return True
        elif isinstance(node, ast.Import):
            if any(
                alias.name.endswith("plan_defaults") for alias in node.names
            ):
                return True
    return False


def test_every_named_importer_actually_imports():
    """Every ``<name>.py`` in the "Imported by" clause must be a real,
    importing module."""
    match = re.search(r"Imported by(.+)$", _DOCSTRING, re.S)
    assert match, "docstring must carry an 'Imported by' clause"
    named = re.findall(r"``([a-z_][a-z0-9_]*)\.py``", match.group(1))
    assert named, "the 'Imported by' clause must name at least one module"
    for name in named:
        module_path = _MGMT_COMMANDS / f"{name}.py"
        assert module_path.is_file(), (
            f"docstring names importer ``{name}.py`` which does not exist "
            f"under tenants/management/commands/"
        )
        assert _ast_imports_plan_defaults(module_path), (
            f"docstring names ``{name}.py`` as an importer, but it does not "
            f"import plan_defaults"
        )


def test_personal_tenant_service_correction_is_present_and_true():
    """The liar correction: the docstring must state PersonalTenantService
    does NOT import the catalog — and that statement must be TRUE."""
    assert "PersonalTenantService" in _DOCSTRING
    assert "does NOT import" in _DOCSTRING, (
        "the docstring must carry the corrected claim: PersonalTenantService "
        "resolves the seeded FREE plan by slug, it does not import the catalog"
    )
    assert not _ast_imports_plan_defaults(_SERVICES_PATH), (
        "services.py must not import plan_defaults — the corrected docstring "
        "claim is about the real code"
    )


def test_tier_count_claims_match_the_real_lists():
    """Every 'N tiers' claim in the file (docstring AND section comments)
    must match the actual list length of the imported catalog."""
    actual = {
        "PLATFORM_PLANS": len(plan_defaults.PLATFORM_PLANS),
        "ML_PLANS": len(plan_defaults.ML_PLANS),
    }
    claims = re.findall(
        r"(PLATFORM_PLANS|Platform Plans|ML_PLANS)\s*\((\d+) tiers\)", _SRC
    )
    assert claims, "the file must carry at least one tier-count claim"
    for label, count in claims:
        key = "PLATFORM_PLANS" if label == "Platform Plans" else label
        assert int(count) == actual[key], (
            f"{label}: claims {count} tiers, the real list has {actual[key]}"
        )


def test_every_entry_has_non_none_limits_and_tier_profile():
    """The docstring's 'non-None limits_json and tier_profile dict' claim
    must hold for every entry in the real catalog."""
    for key in ("PLATFORM_PLANS", "ML_PLANS"):
        for entry in getattr(plan_defaults, key):
            slug = entry.get("slug")
            assert entry.get("limits_json") is not None, (
                f"{key}[{slug}]: limits_json is None, the docstring claims "
                f"non-None for every plan"
            )
            assert isinstance(entry.get("tier_profile"), dict), (
                f"{key}[{slug}]: tier_profile is not a dict, the docstring "
                f"claims one for every plan"
            )
