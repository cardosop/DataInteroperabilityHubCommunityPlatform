"""
Contract tests for scripts/ckan_token_remint.py.

The conditional re-mint turns the 1.4 manual CKAN recovery into tooling:
probe first (PASS → nothing to do), re-mint only when the token is dead,
keep the three token carriers (.env.test, Makefile fallback, compose
CKAN_SEED_TOKEN) in sync, and revoke the superseded token. Pinned here
without mocks:

- mint-output parsing is tolerant of the leading TAB and the CLI noise
  lines the real `ckan user token add` prints (1.4 finding);
- the file rewrites are exercised against real temp copies;
- a LIVE env-gated test mints a scratch token through the real CLI and
  revokes it (the real command shapes, self-cleaning).
"""

import base64
import importlib.util
import json
import shutil
import sys
from pathlib import Path

import pytest

scripts_dir = Path(__file__).parent.parent
sys.path.insert(0, str(scripts_dir))
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from envpolicy import probe_service, skip_or_fail

script_path = scripts_dir / "ckan_token_remint.py"
spec = importlib.util.spec_from_file_location("ckan_token_remint", script_path)
remint = importlib.util.module_from_spec(spec)
spec.loader.exec_module(remint)


def _jwt(payload: dict, header: dict | None = None) -> str:
    """A synthetic JWT (fake signature) built as DATA — the fixtures
    carry no literal token shapes (secret scanners treat literal JWTs as
    findings; a computed fixture cannot be one)."""

    def _enc(obj: dict) -> str:
        raw = json.dumps(obj, separators=(",", ":")).encode()
        return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()

    return f"{_enc(header or {'alg': 'HS256'})}.{_enc(payload)}.sig-sig-sig"


JWT = _jwt({"jti": "test-jti-123", "iat": 1791234567})
MINTED = _jwt(
    {"jti": "test-jti-123", "iat": 1791234567}, header={"typ": "JWT", "alg": "HS256"}
)

REAL_MINT_OUTPUT = f"""\
/srv/app/src/ckan/ckan/cli/cli.py:7: UserWarning: pkg_resources is deprecated as an API.
2026-10-05 00:26:49,538 INFO  [ckan.cli] Using configuration file /srv/app/ckan.ini
2026-10-05 00:26:49,845 INFO  [ckan.config.environment] Loading templates from /srv/app/src/ckan/ckan/templates
2026-10-05 00:26:49,917 WARNI [ckan.config.middleware.flask_app] Extensions are excluded from CSRF protection!
API Token created:
\t{MINTED}
"""


class TestParseMintOutput:
    def test_extracts_jwt_from_tab_indented_last_line(self):
        assert remint.parse_mint_output(REAL_MINT_OUTPUT) == MINTED

    def test_takes_the_last_jwt_when_several_appear(self):
        later = _jwt({"jti": "later"}, header={"typ": "JWT"})
        out = REAL_MINT_OUTPUT + f"noise-line\n\t{later}\n"
        assert remint.parse_mint_output(out) == later

    def test_no_jwt_returns_none(self):
        assert remint.parse_mint_output("API Token created:\n") is None
        assert remint.parse_mint_output("") is None


class TestJwtJti:
    def test_decodes_jti(self):
        assert remint.jwt_jti(JWT) == "test-jti-123"

    def test_invalid_jwt_returns_none(self):
        assert remint.jwt_jti("not-a-jwt") is None
        assert remint.jwt_jti("") is None


class TestRewrites:
    def test_env_test_rewrite(self, tmp_path):
        path = tmp_path / ".env.test"
        path.write_text(
            "CKAN_TEST_API_KEY=old-token\nOTHER=keep\n"
            "# comment CKAN_TEST_API_KEY=commented\n"
        )
        assert remint.rewrite_env_test(path, JWT)
        text = path.read_text()
        assert f"CKAN_TEST_API_KEY={JWT}" in text
        assert "OTHER=keep" in text
        assert "# comment CKAN_TEST_API_KEY=commented" in text

    def test_makefile_fallback_rewrite(self, tmp_path):
        path = tmp_path / "Makefile"
        path.write_text("# comment\nCKAN_TEST_API_KEY ?= old-token\n# more\n")
        assert remint.rewrite_makefile(path, JWT)
        assert f"CKAN_TEST_API_KEY ?= {JWT}" in path.read_text()

    def test_compose_seed_token_rewrite(self, tmp_path):
        path = tmp_path / "docker-compose.test.yml"
        path.write_text(
            "      # Fixed seed token comment\n"
            "      CKAN_SEED_TOKEN: old-token\n"
            "      other: key\n"
        )
        assert remint.rewrite_compose_seed(path, JWT)
        text = path.read_text()
        assert f"CKAN_SEED_TOKEN: {JWT}" in text
        assert "other: key" in text

    def test_rewrite_missing_file_returns_false(self, tmp_path):
        assert not remint.rewrite_env_test(tmp_path / "nope", JWT)

    def test_rewrite_is_atomic_replace(self, tmp_path):
        # O1 (W0.10): a plain write_text truncates the live .env.test in
        # place — a crash mid-write leaves a HALF-WRITTEN secret carrier
        # and the next stack boot fails on a malformed env line. The
        # rewrite must be write-to-temp + os.replace (atomic on POSIX):
        # the target inode changes, readers never observe a partial file.
        path = tmp_path / ".env.test"
        path.write_text("CKAN_TEST_API_KEY=old-token\n")
        before = path.stat().st_ino
        assert remint.rewrite_env_test(path, JWT)
        assert path.stat().st_ino != before, (
            "the rewrite truncated the file in place — inode unchanged. "
            "Use a same-dir temp file + os.replace so a crash can never "
            "leave a half-written secret carrier."
        )
        assert f"CKAN_TEST_API_KEY={JWT}" in path.read_text()

    def test_rewrite_leaves_no_temp_litter(self, tmp_path):
        # The atomic pattern must clean up its temp file (same-dir temp
        # + replace leaves nothing behind).
        path = tmp_path / ".env.test"
        path.write_text("CKAN_TEST_API_KEY=old-token\n")
        assert remint.rewrite_env_test(path, JWT)
        leftovers = [p.name for p in tmp_path.iterdir() if p != path]
        assert leftovers == [], f"temp litter left behind: {leftovers}"


class TestRevokeCommandShape:
    def test_revoke_command_targets_the_old_jti(self):
        cmd = remint.revoke_command("old-jti-123")
        assert cmd[-1] == "old-jti-123"
        assert "revoke" in cmd


class TestLiveMint:
    """Real CLI round-trip against the live ckan-test (self-cleaning)."""

    @pytest.fixture
    def live_ckan_cli(self):
        if not shutil.which("docker"):
            pytest.skip("docker not installed")
        if not probe_service("http://localhost:5100/api/3/action/status_show"):
            skip_or_fail("ckan-test not reachable on localhost:5100")
        return True

    def test_real_mint_output_parses_and_token_revokes(self, live_ckan_cli):
        import subprocess

        name = f"remint_probe_{Path(__file__).stem}"
        out = subprocess.run(
            remint.mint_command(token_name=name),
            capture_output=True,
            text=True,
            check=False,
        )
        assert out.returncode == 0, out.stderr[-400:]
        token = remint.parse_mint_output(out.stdout)
        assert token, out.stdout[-400:]
        jti = remint.jwt_jti(token)
        assert jti
        # clean up through the same CLI surface the tool itself uses
        subprocess.run(remint.revoke_command(jti), check=False)
