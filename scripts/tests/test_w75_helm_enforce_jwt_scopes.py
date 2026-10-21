"""W7.5 (oss-release-remediation, S1) — helm deploy-tree pins for the
ENFORCE_JWT_SCOPES flip.

The settings code-default (pinned in the backend suite,
hub/apps/auth/tests/test_scope_bypass_prevention.py) is the runtime
guarantee; these pins make the posture VISIBLE in the deploy tree:
staging (the soak target) and production (the S1 flip) both set the
flag explicitly, so a values regression cannot silently fall back to a
permissive default.

DB-free on purpose (yaml parse only) so this file runs in the CI
no-django lint job alongside scripts/tests/test_w65_scope_set_contract.py.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def _api_env(path: Path) -> dict[str, str]:
    values = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert "api" in values, f"{path}: no api section"
    return {str(k).lower(): str(v) for k, v in values["api"]["env"].items()}


def test_staging_helm_values_enforce_explicitly():
    """Staging sets the flag explicitly — the soak environment."""
    api_env = _api_env(REPO_ROOT / "helm" / "values.staging.yaml")
    assert api_env["enforce_jwt_scopes"] == "true"


def test_production_helm_values_enforce_explicitly():
    """Production sets the flag explicitly — the S1 flip."""
    api_env = _api_env(REPO_ROOT / "helm" / "values.yaml")
    assert api_env["enforce_jwt_scopes"] == "true"


def test_drift_pin_bites():
    """Falsifiability: mutating the parsed staging values must flip the
    pin RED — a green contract test that never bites detects nothing."""
    values = yaml.safe_load(
        (REPO_ROOT / "helm" / "values.staging.yaml").read_text(encoding="utf-8")
    )
    values["api"]["env"]["ENFORCE_JWT_SCOPES"] = "false"
    api_env = {str(k).lower(): str(v) for k, v in values["api"]["env"].items()}
    with pytest.raises(AssertionError):
        assert api_env["enforce_jwt_scopes"] == "true"
