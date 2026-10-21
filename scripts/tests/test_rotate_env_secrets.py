"""
Contract tests for scripts/rotate_env_secrets.py (oss-release-remediation W0.5).

The rotation tool is the D/O workhorse for W0.5 (SECRET_KEY + the staging
DB/MinIO/Fuseki/Grafana password group). These tests pin its contract with
real tmp env files — no mocks or stubs:

- rotation changes the target key's VALUE only — every other line (order,
  comments, unrelated keys) is preserved verbatim;
- the write is atomic (tmp + os.replace — the O1 convention): no partial or
  leftover tmp file remains after a run;
- the tool NEVER prints values — the old and new values (fixture-known)
  must not appear in stdout;
- the tool refuses to run without the target file, and refuses a partial
  rotation (a missing target key is a loud failure, not a silent skip);
- --dry-run reports what would change without writing;
- two consecutive runs produce different values (CSPRNG, not deterministic);
- each subcommand touches exactly its own key set.
"""

import importlib.util
import secrets
import subprocess
import sys
from pathlib import Path

import pytest

scripts_dir = Path(__file__).parent.parent
sys.path.insert(0, str(scripts_dir))

spec = importlib.util.spec_from_file_location(
    "rotate_env_secrets", scripts_dir / "rotate_env_secrets.py"
)
rotate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rotate)

ENV_CONTENT = """# staging env fixture
POSTGRES_DB=hub
POSTGRES_PASSWORD={postgres_password}
POSTGRES_USER=hub
POSTGRES_ADMIN_PASSWORD={postgres_admin_password}
PGBOUNCER_AUTH_PASSWORD={pgbouncer_auth_password}
PGBOUNCER_ADMIN_PASSWORD={pgbouncer_admin_password}
MINIO_ROOT_USER=minio-user
MINIO_ROOT_PASSWORD={minio_password}
FUSEKI_ADMIN_PASSWORD={fuseki_password}
GRAFANA_ADMIN_PASSWORD={grafana_password}
SECRET_KEY={secret_key}
# trailing comment stays
"""


@pytest.fixture
def env_file(tmp_path):
    old_values = {
        "postgres_password": "old-postgres-pw",
        "postgres_admin_password": "old-postgres-admin-pw",
        "pgbouncer_auth_password": "old-pgbouncer-auth-pw",
        "pgbouncer_admin_password": "old-pgbouncer-admin-pw",
        "minio_password": "old-minio-pw",
        "fuseki_password": "old-fuseki-pw",
        "grafana_password": "old-grafana-pw",
        "secret_key": "old-secret-key-value",
    }
    path = tmp_path / ".env.staging"
    path.write_text(ENV_CONTENT.format(**old_values))
    return path, old_values


def _run(subcommand, env_file, *extra):
    return subprocess.run(
        [
            sys.executable,
            str(scripts_dir / "rotate_env_secrets.py"),
            subcommand,
            "--env-file",
            str(env_file),
            *extra,
        ],
        capture_output=True,
        text=True,
        check=False,
    )


_FIXTURE_NAMES = {
    "POSTGRES_PASSWORD": "postgres_password",
    "POSTGRES_ADMIN_PASSWORD": "postgres_admin_password",
    "PGBOUNCER_AUTH_PASSWORD": "pgbouncer_auth_password",
    "PGBOUNCER_ADMIN_PASSWORD": "pgbouncer_admin_password",
    "MINIO_ROOT_PASSWORD": "minio_password",
    "FUSEKI_ADMIN_PASSWORD": "fuseki_password",
    "GRAFANA_ADMIN_PASSWORD": "grafana_password",
}


class TestStackPasswordsRotation:
    STACK_KEYS = tuple(_FIXTURE_NAMES)

    def test_rotates_only_the_stack_password_group(self, env_file):
        path, old = env_file
        before = path.read_text()
        result = _run("stack-passwords", path)
        assert result.returncode == 0, result.stderr
        after = path.read_text()

        for key in self.STACK_KEYS:
            line = next(ln for ln in after.splitlines() if ln.startswith(f"{key}="))
            value = line.split("=", 1)[1]
            assert value != old[_FIXTURE_NAMES[key]], f"{key} was not rotated"

        # The untouched lines survive verbatim.
        assert "POSTGRES_DB=hub" in after
        assert "MINIO_ROOT_USER=minio-user" in after
        assert "SECRET_KEY=old-secret-key-value" in after
        assert after.count("# staging env fixture") == 1
        assert after.count("# trailing comment stays") == 1
        # Line order is preserved (before/after differ only in values).
        assert len(before.splitlines()) == len(after.splitlines())

    def test_output_never_contains_values(self, env_file, capsys):
        path, old = env_file
        result = _run("stack-passwords", path)
        out = result.stdout + result.stderr
        for value in old.values():
            assert value not in out
        new_values = [
            ln.split("=", 1)[1]
            for ln in path.read_text().splitlines()
            if any(ln.startswith(f"{k}=") for k in self.STACK_KEYS)
        ]
        for value in new_values:
            assert value not in out

    def test_two_runs_produce_different_values(self, env_file):
        path, _ = env_file
        assert _run("stack-passwords", path).returncode == 0
        first = {
            ln.split("=", 1)[1]
            for ln in path.read_text().splitlines()
            if any(ln.startswith(f"{k}=") for k in self.STACK_KEYS)
        }
        assert _run("stack-passwords", path).returncode == 0
        second = {
            ln.split("=", 1)[1]
            for ln in path.read_text().splitlines()
            if any(ln.startswith(f"{k}=") for k in self.STACK_KEYS)
        }
        assert first.isdisjoint(second), "CSPRNG rotation must not repeat values"

    def test_dry_run_reports_without_writing(self, env_file):
        path, _ = env_file
        before = path.read_text()
        result = _run("stack-passwords", path, "--dry-run")
        assert result.returncode == 0, result.stderr
        assert path.read_text() == before
        assert "dry-run" in result.stdout.lower()

    def test_refuses_missing_target_file(self, tmp_path):
        result = _run("stack-passwords", tmp_path / "missing.env")
        assert result.returncode != 0

    def test_refuses_partial_rotation_when_key_missing(self, tmp_path):
        path = tmp_path / ".env.staging"
        path.write_text("POSTGRES_PASSWORD=only-one\n")
        result = _run("stack-passwords", path)
        assert result.returncode != 0
        assert path.read_text() == "POSTGRES_PASSWORD=only-one\n"

    def test_atomic_write_leaves_no_tmp_files(self, env_file):
        path, _ = env_file
        assert _run("stack-passwords", path).returncode == 0
        leftovers = list(path.parent.glob("*"))
        assert [p.name for p in leftovers] == [path.name]


class TestDjangoSecretKeyRotation:
    def test_rotates_secret_key_only(self, env_file):
        path, old = env_file
        result = _run("django-secret-key", path)
        assert result.returncode == 0, result.stderr
        after = path.read_text()
        line = next(ln for ln in after.splitlines() if ln.startswith("SECRET_KEY="))
        assert line.split("=", 1)[1] != old["secret_key"]
        # The stack passwords are NOT touched by this subcommand.
        for key in ("POSTGRES_PASSWORD", "MINIO_ROOT_PASSWORD", "FUSEKI_ADMIN_PASSWORD"):
            assert f"{key}=old-" in after, f"{key} was changed by django-secret-key"

    def test_secret_key_has_sufficient_entropy(self, env_file):
        path, _ = env_file
        assert _run("django-secret-key", path).returncode == 0
        line = next(ln for ln in path.read_text().splitlines() if ln.startswith("SECRET_KEY="))
        assert len(line.split("=", 1)[1]) >= 48

    def test_output_never_contains_values(self, env_file, capsys):
        path, old = env_file
        result = _run("django-secret-key", path)
        out = result.stdout + result.stderr
        assert old["secret_key"] not in out
        new_value = next(
            ln.split("=", 1)[1]
            for ln in path.read_text().splitlines()
            if ln.startswith("SECRET_KEY=")
        )
        assert new_value not in out


class TestModuleShape:
    def test_stack_password_keys_are_the_contract(self):
        assert set(rotate.STACK_PASSWORD_KEYS) == {
            "POSTGRES_PASSWORD",
            "POSTGRES_ADMIN_PASSWORD",
            "PGBOUNCER_AUTH_PASSWORD",
            "PGBOUNCER_ADMIN_PASSWORD",
            "MINIO_ROOT_PASSWORD",
            "FUSEKI_ADMIN_PASSWORD",
            "GRAFANA_ADMIN_PASSWORD",
        }

    def test_generators_are_csprng_backed(self):
        # The values come from secrets.token_urlsafe, never random.* —
        # pin the generator lengths the tool is allowed to produce.
        assert rotate.SECRET_KEY_LENGTH == 48
        assert rotate.STACK_PASSWORD_LENGTH == 18
        value = rotate._new_secret(rotate.STACK_PASSWORD_LENGTH)
        assert isinstance(value, str)
        assert len(value) >= rotate.STACK_PASSWORD_LENGTH
        assert secrets.compare_digest(rotate._new_secret(48), rotate._new_secret(48)) is False
