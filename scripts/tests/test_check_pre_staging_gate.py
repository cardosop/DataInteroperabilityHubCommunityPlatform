"""
Contract tests for scripts/check_pre_staging_gate.py.

The gate is the pre-deploy acceptance for the staging bring-up
(pilot-readiness 1.6). Pinned here without mocks:

- the registry MUST carry the production CORS gate (V6.2) — the
  check_production_cors.py checker was previously an orphan that nothing
  in CI or the deploy path invoked (1.6 finding);
- the CORS gate verdict must track the checker's real outcome against
  the real repo config, and flip to FAIL when the Traefik routes file
  actually carries a wildcard origin (a real temp file, no stubs);
- the gate stays runnable when Django is not importable in this
  environment (SKIP, not crash).
"""

import importlib.util
import sys
from pathlib import Path

import pytest

scripts_dir = Path(__file__).parent.parent
sys.path.insert(0, str(scripts_dir))

gate_path = scripts_dir / "check_pre_staging_gate.py"
spec = importlib.util.spec_from_file_location("check_pre_staging_gate", gate_path)
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)

cors_path = scripts_dir / "check_production_cors.py"
spec2 = importlib.util.spec_from_file_location("check_production_cors", cors_path)
cors = importlib.util.module_from_spec(spec2)
spec2.loader.exec_module(cors)

WILDCARD_ROUTES = """\
http:
  middlewares:
    cors:
      headers:
        accessControlAllowOriginList:
          - "*"
"""


@pytest.fixture(scope="module")
def registry():
    return gate._run_all_automated_checks()


class TestCorsGateRegistered:
    def test_v62_cors_gate_is_present(self, registry):
        v62 = [r for r in registry if r[0] == "V6.2"]
        assert len(v62) == 1, "V6.2 (production CORS) gate is missing"
        _, name, status, _ = v62[0]
        assert "CORS" in name
        assert status in {"PASS", "FAIL", "SKIP"}

    def test_v62_verdict_matches_the_checker_outcome(self, registry):
        # The gate must not soften or invent a verdict: compare it against
        # the checker's own real outcome for this repo state.
        v62 = next(r for r in registry if r[0] == "V6.2")
        traefik_ok = gate._CORS_CHECKER.check_traefik_cors_star(strict=True)
        expected = "PASS" if traefik_ok else "FAIL"
        assert v62[2] == expected, (v62, traefik_ok)


class TestCorsGateFailsOnWildcard:
    def test_wildcard_traefik_routes_flips_the_gate_to_fail(
        self, tmp_path, monkeypatch
    ):
        routes = tmp_path / "routes.yml"
        routes.write_text(WILDCARD_ROUTES)
        monkeypatch.setattr(gate._CORS_CHECKER, "TRAEFIK_ROUTES", routes)
        status, detail = gate._check_production_cors()
        assert status == "FAIL"
        assert "explicit origins" in detail

    def test_explicit_origins_pass(self, tmp_path, monkeypatch):
        routes = tmp_path / "routes.yml"
        routes.write_text(
            WILDCARD_ROUTES.replace('          - "*"', '          - "https://staging.example.com"')
        )
        monkeypatch.setattr(gate._CORS_CHECKER, "TRAEFIK_ROUTES", routes)
        status, _ = gate._check_production_cors()
        assert status == "PASS"

    def test_missing_routes_file_is_a_fail_in_strict_mode(self, tmp_path, monkeypatch):
        monkeypatch.setattr(gate._CORS_CHECKER, "TRAEFIK_ROUTES", tmp_path / "nope.yml")
        status, _ = gate._check_production_cors()
        assert status == "FAIL"


class TestHelmNoLiteralSecretsGate:
    def test_v63_gate_is_present(self, registry):
        v63 = [r for r in registry if r[0] == "V6.3"]
        assert len(v63) == 1, "V6.3 (helm values: no literal secrets) gate is missing"
        assert "ExternalSecrets" in v63[0][1]
        assert v63[0][2] in {"PASS", "FAIL", "SKIP"}

    def test_literal_password_is_a_violation(self, tmp_path):
        values = tmp_path / "values.yaml"
        values.write_text(
            'postgres:\n  password: "hunter2secret"\n  host: db\n'
        )
        violations = gate._find_literal_secret_violations(values)
        assert len(violations) == 1
        assert "password" in violations[0]
        assert "hunter2secret" not in violations[0]  # never echo the value

    def test_templated_and_placeholder_values_are_not_violations(self, tmp_path):
        values = tmp_path / "values.yaml"
        values.write_text(
            'postgres:\n'
            '  password: "{{ .Values.secrets.postgres }}"\n'
            '  token: "changeme"\n'
            '  host: db\n'
        )
        assert gate._find_literal_secret_violations(values) == []

    def test_real_helm_values_are_clean(self):
        for name in ("values.yaml", "values.staging.yaml"):
            violations = gate._find_literal_secret_violations(
                gate.REPO_ROOT / "helm" / name
            )
            assert violations == [], f"{name}: {violations}"

    def test_gate_function_reports_current_repo_state(self):
        status, _ = gate._check_helm_values_no_literal_secrets()
        assert status == "PASS"


class TestGateIsRunnable:
    def test_main_returns_exit_code_without_exceptions(self):
        rc = gate.main(["--gate", "V6.2"])
        assert rc in (0, 1)

    def test_strict_allows_environment_dependent_skips(self, capsys):
        # The two Django/prefect-dependent gates SKIP outside Docker; the
        # CI + post-deploy invocations run --strict with the explicit
        # allowlist so a bare host does not fail the deploy gate.
        rc = gate.main(
            ["--strict", "--allow-skip", "V0.3.reg,V0.4"]
        )
        assert rc in (0, 1)

    def test_strict_without_allowlist_fails_on_skips(self, capsys):
        rc = gate.main(["--strict", "--gate", "V0.3.reg"])
        # V0.3.reg SKIPs host-side; strict counts it as FAIL.
        assert rc == 1
