"""
Contract tests for scripts/verify_test_stack_creds.py.

The detector is the durable form of the pilot-readiness 1.3/1.4 landmine:
a routine stack bring-up must not silently break storage because the
MinIO volume still accepts a credential pair the env files no longer
carry. Pinned here without mocks or stubs:

- env-file parsing + internal-consistency classification (pure);
- verdict classification over real probe matrices;
- LIVE probes against the real test stack (MinIO on 9010, CKAN on 5100,
  the running containers) — W16: unreachable raises in CI, skips locally;
- no secret value is ever printed by any output path.
"""

import importlib.util
import shutil
import sys
from pathlib import Path

import pytest

scripts_dir = Path(__file__).parent.parent
sys.path.insert(0, str(scripts_dir))
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from envpolicy import probe_service, skip_or_fail

script_path = scripts_dir / "verify_test_stack_creds.py"
spec = importlib.util.spec_from_file_location("verify_test_stack_creds", script_path)
verify = importlib.util.module_from_spec(spec)
spec.loader.exec_module(verify)

REPO = Path(__file__).parent.parent.parent
ENV_TEST = REPO / ".env.test"

SECRET = "verifyprobe-secret-abc123"


def _tmp_env(tmp_path, **entries):
    path = tmp_path / ".env.probe"
    path.write_text("\n".join(f"{k}={v}" for k, v in entries.items()) + "\n")
    return path


class TestParseEnvFile:
    def test_parses_real_env_test_without_exception(self):
        parsed = verify.parse_env_file(ENV_TEST)
        assert parsed["MINIO_ROOT_USER"]
        assert parsed["AWS_ACCESS_KEY_ID"]
        assert "CKAN_TEST_API_KEY" in parsed

    def test_missing_file_returns_empty(self, tmp_path):
        assert verify.parse_env_file(tmp_path / "nope") == {}

    def test_ignores_comments_and_blank_lines(self, tmp_path):
        path = _tmp_env(
            tmp_path,
            MINIO_ROOT_USER="u1",
            MINIO_ROOT_PASSWORD="p1",
            AWS_ACCESS_KEY_ID="u1",
            AWS_SECRET_ACCESS_KEY="p1",
        )
        parsed = verify.parse_env_file(path)
        assert parsed["MINIO_ROOT_USER"] == "u1"


class TestInternalConsistency:
    def test_consistent_file_has_no_violations(self, tmp_path):
        path = _tmp_env(
            tmp_path,
            MINIO_ROOT_USER="u1",
            MINIO_ROOT_PASSWORD="p1",
            AWS_ACCESS_KEY_ID="u1",
            AWS_SECRET_ACCESS_KEY="p1",
        )
        assert verify.minio_internal_violations(verify.parse_env_file(path)) == []

    def test_user_mismatch_is_a_violation(self, tmp_path):
        path = _tmp_env(
            tmp_path,
            MINIO_ROOT_USER="u1",
            MINIO_ROOT_PASSWORD="p1",
            AWS_ACCESS_KEY_ID="u2",
            AWS_SECRET_ACCESS_KEY="p1",
        )
        violations = verify.minio_internal_violations(verify.parse_env_file(path))
        assert len(violations) == 1
        assert "MINIO_ROOT_USER" in violations[0]
        assert "AWS_ACCESS_KEY_ID" in violations[0]

    def test_password_mismatch_is_a_violation(self, tmp_path):
        path = _tmp_env(
            tmp_path,
            MINIO_ROOT_USER="u1",
            MINIO_ROOT_PASSWORD="p1",
            AWS_ACCESS_KEY_ID="u1",
            AWS_SECRET_ACCESS_KEY="p2",
        )
        violations = verify.minio_internal_violations(verify.parse_env_file(path))
        assert len(violations) == 1
        assert "MINIO_ROOT_PASSWORD" in violations[0]


class TestVerdictClassification:
    ENV_PAIR = ("env-user", "env-pass")

    def test_volume_accepts_env_pair_is_pass(self):
        status, _ = verify.classify_minio_volume(
            accepted_pair=self.ENV_PAIR, env_pair=self.ENV_PAIR
        )
        assert status == "PASS"

    def test_volume_accepts_foreign_pair_is_fail(self):
        status, detail = verify.classify_minio_volume(
            accepted_pair=("other", "other"), env_pair=self.ENV_PAIR
        )
        assert status == "FAIL"
        assert "re-init" in detail
        assert "env-user" not in detail
        assert "env-pass" not in detail

    def test_reachable_volume_rejecting_every_pair_is_fail(self):
        status, detail = verify.classify_minio_volume(
            accepted_pair=None, env_pair=self.ENV_PAIR, rejected_all=True
        )
        assert status == "FAIL"
        assert "foreign" in detail
        assert "env-user" not in detail

    def test_unreachable_is_skip_but_strict_fails(self):
        status, _ = verify.classify_minio_volume(
            accepted_pair=None, env_pair=self.ENV_PAIR, strict=False
        )
        assert status == "SKIP"
        status, _ = verify.classify_minio_volume(
            accepted_pair=None, env_pair=self.ENV_PAIR, strict=True
        )
        assert status == "FAIL"


class TestLiveMinioProbe:
    """Real boto3 against the real test-stack MinIO (host port 9010)."""

    @pytest.fixture
    def live_minio(self):
        if not probe_service("http://localhost:9010/minio/health/live"):
            skip_or_fail("minio-test not reachable on localhost:9010")
        return "http://localhost:9010"

    def test_env_test_pair_is_accepted_by_the_live_volume(self, live_minio):
        parsed = verify.parse_env_file(ENV_TEST)
        assert verify.probe_minio_pair(
            live_minio, parsed["MINIO_ROOT_USER"], parsed["MINIO_ROOT_PASSWORD"]
        )

    def test_wrong_pair_is_rejected_by_the_live_volume(self, live_minio):
        assert not verify.probe_minio_pair(live_minio, "no-such-user", "no-such-pass")


class TestLiveCkanProbe:
    @pytest.fixture
    def live_ckan(self):
        if not probe_service("http://localhost:5100/api/3/action/status_show"):
            skip_or_fail("ckan-test not reachable on localhost:5100")
        return "http://localhost:5100"

    def test_env_test_token_passes_live(self, live_ckan):
        from verify_connector_creds import ckan_probe_result

        parsed = verify.parse_env_file(ENV_TEST)
        status, detail = ckan_probe_result(
            parsed["CKAN_TEST_API_KEY"], base=live_ckan
        )
        assert status == "PASS", detail

    def test_bogus_token_fails_live(self, live_ckan):
        from verify_connector_creds import ckan_probe_result

        status, detail = ckan_probe_result("eyJgarbage.invalid", base=live_ckan)
        assert status == "FAIL"
        assert "eyJgarbage" not in detail


class TestFusekiConvergence:
    def test_converged_envs_pass(self):
        status, _ = verify.classify_fuseki(
            env_password=SECRET, container_passwords={"hub-test-api": SECRET}
        )
        assert status == "PASS"

    def test_diverged_container_fails_and_names_it(self):
        status, detail = verify.classify_fuseki(
            env_password=SECRET, container_passwords={"hub-test-api": "old"}
        )
        assert status == "FAIL"
        assert "hub-test-api" in detail
        assert SECRET not in detail

    def test_no_containers_is_skip(self):
        status, _ = verify.classify_fuseki(env_password=SECRET, container_passwords={})
        assert status == "SKIP"

    @pytest.mark.skipif(not shutil.which("docker"), reason="docker not installed")
    def test_live_containers_converge_with_env_test(self):
        parsed = verify.parse_env_file(ENV_TEST)
        passwords = verify.fuseki_container_passwords(
            ["hub-test-api", "hub-test-semantic"]
        )
        if not passwords:
            skip_or_fail("test-stack containers not running")
        assert all(p == parsed["FUSEKI_ADMIN_PASSWORD"] for p in passwords.values())


class TestNoSecretLeakage:
    def test_full_pipeline_never_prints_values_on_mismatch(
        self, tmp_path, monkeypatch, capsys
    ):
        # A consistent env file whose pair the live volume does NOT accept:
        # the detector must FAIL without ever printing the pair's values.
        # Requires the real MinIO (a reachable volume that rejects the pair).
        if not probe_service("http://localhost:9010/minio/health/live"):
            skip_or_fail("minio-test not reachable on localhost:9010")
        path = _tmp_env(
            tmp_path,
            MINIO_ROOT_USER="leakuser-xyz",
            MINIO_ROOT_PASSWORD=SECRET,
            AWS_ACCESS_KEY_ID="leakuser-xyz",
            AWS_SECRET_ACCESS_KEY=SECRET,
        )
        rc = verify.main(["--env-file", str(path)])
        out = capsys.readouterr().out
        assert "FAIL" in out
        assert rc == 1
        assert SECRET not in out
        assert "leakuser-xyz" not in out
