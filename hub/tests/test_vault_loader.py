"""
hub/tests/test_vault_loader.py
================================
Integration tests for hub.vault_loader.

Strategy
--------
* Spin up a Vault dev server as a pytest fixture using ``subprocess``.
* The dev server binds to an ephemeral port on 127.0.0.1, initialised with a
  fixed root token (``dev-root-token``), so no init/unseal is needed.
* We use the Vault CLI to configure the server, then call ``load_from_vault()``
  and verify env vars were injected correctly.

Test isolation
--------------
* ``vault_server`` and ``configured_vault`` are **module-scoped** — the dev
  server starts once for the whole module and is torn down at the end.
* Each test uses ``monkeypatch`` (function-scoped) for env vars so no
  cross-test pollution occurs.
* ``importlib.reload()`` is **not** used: vault_loader has no module-level
  mutable state that persists across calls, so reloading is unnecessary and
  breaks ``monkeypatch.setattr`` ordering.

Prerequisites
-------------
* ``vault`` binary must be on PATH.
* ``hvac>=2.3.0`` installed.
* Tests are **skipped automatically** when the ``vault`` binary is absent.

Run:
    pytest hub/tests/test_vault_loader.py -v
"""

from __future__ import annotations

import json
import os
import pathlib
import shutil
import socket
import subprocess
import time
from collections.abc import Generator
from typing import Any, cast

import pytest


# ---------------------------------------------------------------------------
# Skip entire module when vault binary is absent
# ---------------------------------------------------------------------------
pytestmark = pytest.mark.skipif(
    shutil.which("vault") is None,
    reason="vault binary not found in PATH — skipping Vault integration tests",
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _free_port() -> int:
    """Return an unused TCP port on 127.0.0.1."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        return cast(int, s.getsockname()[1])


def _wait_for_vault(addr: str, timeout: float = 20.0) -> None:
    """Poll until Vault responds on its health endpoint or raise TimeoutError."""
    # Local import: the skip guard above ensures vault is present, but hvac
    # may not be installed in non-test environments; keep it isolated here.
    import hvac  # noqa: PLC0415  (import not at top of file — intentional)

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            client = hvac.Client(url=addr)
            resp = client.sys.read_health_status(method="GET")
            if resp.ok:
                return
        except Exception:
            pass
        time.sleep(0.25)
    raise TimeoutError(
        f"Vault dev server at {addr} did not become ready within {timeout}s"
    )


def _vault_cli(
    args: list[str],
    env: dict[str, str],
    stdin: str | None = None,
) -> subprocess.CompletedProcess[str]:
    """
    Run a vault CLI command.

    Parameters
    ----------
    args  : CLI arguments after ``vault``
    env   : Full environment dict (must include VAULT_ADDR + VAULT_TOKEN)
    stdin : Optional string piped to the process stdin (e.g. policy HCL)

    Raises RuntimeError on non-zero exit.
    """
    result = subprocess.run(
        ["vault"] + args,
        env=env,
        input=stdin,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"vault {' '.join(args)} failed (rc={result.returncode}):\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )
    return result


# ---------------------------------------------------------------------------
# Module-scoped fixtures
# ---------------------------------------------------------------------------

VaultInfo = dict[str, Any]  # {addr: str, token: str, env: dict[str,str], ...}


@pytest.fixture(scope="module")
def vault_server() -> Generator[VaultInfo, None, None]:
    """
    Start a Vault dev server on an ephemeral port.
    Yields a VaultInfo dict; terminates the process on teardown.
    """
    port = _free_port()
    addr = f"http://127.0.0.1:{port}"
    root_token = "dev-root-token"

    proc = subprocess.Popen(
        [
            "vault", "server",
            "-dev",
            f"-dev-listen-address=127.0.0.1:{port}",
            f"-dev-root-token-id={root_token}",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    # Build env for CLI calls: start from os.environ, then override Vault vars.
    cli_env: dict[str, str] = dict(os.environ)
    cli_env["VAULT_ADDR"] = addr
    cli_env["VAULT_TOKEN"] = root_token
    cli_env["VAULT_SKIP_VERIFY"] = "true"

    try:
        _wait_for_vault(addr)
        yield {"addr": addr, "token": root_token, "env": cli_env}
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


@pytest.fixture(scope="module")
def configured_vault(vault_server: VaultInfo) -> VaultInfo:
    """
    Configure the dev Vault server:
      - Upgrade secret/ from KV v1 (dev default) to KV v2
      - Write test secrets to secret/hub/production/*
      - Write hub-api policy via stdin
      - Enable AppRole auth + create hub-api role
    Returns VaultInfo augmented with ``role_id`` and ``secret_id``.
    """
    cli_env: dict[str, str] = vault_server["env"]

    # -------------------------------------------------------------------------
    # KV v2 — dev server starts with KV v1; disable then re-enable as v2
    # -------------------------------------------------------------------------
    try:
        _vault_cli(["secrets", "disable", "secret/"], cli_env)
    except RuntimeError:
        pass  # not mounted — fine

    _vault_cli(["secrets", "enable", "-path=secret", "-version=2", "kv"], cli_env)

    # -------------------------------------------------------------------------
    # Write test secrets (paths match vault_loader._KV_PATHS)
    # -------------------------------------------------------------------------
    _vault_cli(
        ["kv", "put", "secret/hub/production/django",
         "SECRET_KEY=test-secret-key-from-vault",
         "JWT_SECRET_KEY=test-jwt-secret-from-vault",
         "ENCRYPTION_KEY=test-encryption-key-from-vault"],
        cli_env,
    )
    _vault_cli(
        ["kv", "put", "secret/hub/production/redis",
         "REDIS_CACHE_PASSWORD=cache-pw",
         "REDIS_QUEUE_PASSWORD=queue-pw",
         "REDIS_EVENTS_PASSWORD=events-pw",
         "REDIS_CHANNELS_PASSWORD=channels-pw"],
        cli_env,
    )
    _vault_cli(
        ["kv", "put", "secret/hub/production/minio",
         "MINIO_ROOT_USER=minio-user",
         "MINIO_ROOT_PASSWORD=minio-pass"],
        cli_env,
    )
    _vault_cli(
        ["kv", "put", "secret/hub/production/email",
         "SENDGRID_API_KEY=sg-test-key"],
        cli_env,
    )

    # -------------------------------------------------------------------------
    # Hub-api policy — MUST be written via stdin; env vars are not supported
    # -------------------------------------------------------------------------
    policy_hcl = (
        'path "secret/data/hub/production/*" { capabilities = ["read"] }\n'
        'path "secret/metadata/hub/production/*" { capabilities = ["list", "read"] }\n'
        'path "auth/token/renew-self" { capabilities = ["update"] }\n'
        'path "auth/token/lookup-self" { capabilities = ["read"] }\n'
    )
    _vault_cli(["policy", "write", "hub-api", "-"], cli_env, stdin=policy_hcl)

    # -------------------------------------------------------------------------
    # AppRole auth
    # -------------------------------------------------------------------------
    try:
        _vault_cli(["auth", "enable", "approle"], cli_env)
    except RuntimeError:
        pass  # already enabled

    _vault_cli(
        ["write", "auth/approle/role/hub-api",
         "token_policies=hub-api",
         "token_ttl=1h",
         "secret_id_ttl=24h"],
        cli_env,
    )

    role_id: str = json.loads(
        _vault_cli(
            ["read", "-format=json", "auth/approle/role/hub-api/role-id"],
            cli_env,
        ).stdout
    )["data"]["role_id"]

    secret_id: str = json.loads(
        _vault_cli(
            ["-format=json", "write", "-force", "auth/approle/role/hub-api/secret-id"],
            cli_env,
        ).stdout
    )["data"]["secret_id"]

    return {**vault_server, "role_id": role_id, "secret_id": secret_id}


# ---------------------------------------------------------------------------
# Helper: minimal env vars for vault_loader in AppRole mode
# ---------------------------------------------------------------------------
def _approle_env(vault_info: VaultInfo) -> dict[str, str]:
    return {
        "VAULT_ADDR": vault_info["addr"],
        "VAULT_SKIP_VERIFY": "true",
        "VAULT_AUTH_METHOD": "approle",
        "VAULT_ROLE_ID": vault_info["role_id"],
        "VAULT_SECRET_ID": vault_info["secret_id"],
        "VAULT_USE_DYNAMIC_DB_CREDS": "false",  # no DB engine in dev server
    }


# ---------------------------------------------------------------------------
# AppRole tests
# ---------------------------------------------------------------------------

class TestVaultLoaderAppRole:
    """Tests for AppRole authentication path."""

    def test_load_injects_django_secrets(
        self,
        configured_vault: VaultInfo,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Django core secrets are injected into os.environ."""
        for k, v in _approle_env(configured_vault).items():
            monkeypatch.setenv(k, v)
        for key in ("SECRET_KEY", "JWT_SECRET_KEY", "ENCRYPTION_KEY"):
            monkeypatch.delenv(key, raising=False)

        from hub.vault_loader import load_from_vault
        load_from_vault()

        assert os.environ["SECRET_KEY"] == "test-secret-key-from-vault"
        assert os.environ["JWT_SECRET_KEY"] == "test-jwt-secret-from-vault"
        assert os.environ["ENCRYPTION_KEY"] == "test-encryption-key-from-vault"

    def test_load_injects_redis_secrets(
        self,
        configured_vault: VaultInfo,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """All Redis password env vars are injected."""
        for k, v in _approle_env(configured_vault).items():
            monkeypatch.setenv(k, v)
        for key in ("REDIS_CACHE_PASSWORD", "REDIS_QUEUE_PASSWORD",
                    "REDIS_EVENTS_PASSWORD", "REDIS_CHANNELS_PASSWORD"):
            monkeypatch.delenv(key, raising=False)

        from hub.vault_loader import load_from_vault
        load_from_vault()

        assert os.environ["REDIS_CACHE_PASSWORD"] == "cache-pw"
        assert os.environ["REDIS_QUEUE_PASSWORD"] == "queue-pw"
        assert os.environ["REDIS_EVENTS_PASSWORD"] == "events-pw"
        assert os.environ["REDIS_CHANNELS_PASSWORD"] == "channels-pw"

    def test_load_injects_minio_secrets(
        self,
        configured_vault: VaultInfo,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """MinIO credentials are injected."""
        for k, v in _approle_env(configured_vault).items():
            monkeypatch.setenv(k, v)
        for key in ("MINIO_ROOT_USER", "MINIO_ROOT_PASSWORD"):
            monkeypatch.delenv(key, raising=False)

        from hub.vault_loader import load_from_vault
        load_from_vault()

        assert os.environ["MINIO_ROOT_USER"] == "minio-user"
        assert os.environ["MINIO_ROOT_PASSWORD"] == "minio-pass"

    def test_load_injects_email_secrets(
        self,
        configured_vault: VaultInfo,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Email credentials are injected."""
        for k, v in _approle_env(configured_vault).items():
            monkeypatch.setenv(k, v)
        monkeypatch.delenv("SENDGRID_API_KEY", raising=False)

        from hub.vault_loader import load_from_vault
        load_from_vault()

        assert os.environ["SENDGRID_API_KEY"] == "sg-test-key"

    def test_wrong_secret_id_raises_runtime_error(
        self,
        configured_vault: VaultInfo,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Invalid secret-id raises RuntimeError (non-retryable 400/403)."""
        monkeypatch.setenv("VAULT_ADDR", configured_vault["addr"])
        monkeypatch.setenv("VAULT_SKIP_VERIFY", "true")
        monkeypatch.setenv("VAULT_AUTH_METHOD", "approle")
        monkeypatch.setenv("VAULT_ROLE_ID", configured_vault["role_id"])
        monkeypatch.setenv("VAULT_SECRET_ID", "00000000-0000-0000-0000-000000000000")
        monkeypatch.setenv("VAULT_USE_DYNAMIC_DB_CREDS", "false")

        from hub.vault_loader import load_from_vault
        with pytest.raises(RuntimeError):
            load_from_vault()

    def test_missing_role_id_raises_immediately(
        self,
        configured_vault: VaultInfo,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Missing VAULT_ROLE_ID raises RuntimeError without retrying."""
        monkeypatch.setenv("VAULT_ADDR", configured_vault["addr"])
        monkeypatch.setenv("VAULT_AUTH_METHOD", "approle")
        monkeypatch.delenv("VAULT_ROLE_ID", raising=False)
        monkeypatch.setenv("VAULT_SECRET_ID", "anything")

        from hub.vault_loader import load_from_vault
        with pytest.raises(RuntimeError, match="VAULT_ROLE_ID"):
            load_from_vault()

    def test_vault_unreachable_retries_and_raises(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Unreachable Vault retries _RETRY_ATTEMPTS times then raises.

        Ordering: import module BEFORE patching time so monkeypatch targets
        the live module object.  A reload() after the patch would discard it.
        """
        import hub.vault_loader as vault_loader_mod  # ensure module is loaded

        # Record sleep calls via a simple replacement object
        sleep_calls: list[float] = []

        class _FakeTime:
            @staticmethod
            def sleep(seconds: float) -> None:
                sleep_calls.append(seconds)

        monkeypatch.setattr(vault_loader_mod, "time", _FakeTime)

        monkeypatch.setenv("VAULT_ADDR", "http://127.0.0.1:1")
        monkeypatch.setenv("VAULT_AUTH_METHOD", "approle")
        monkeypatch.setenv("VAULT_ROLE_ID", "some-role-id")
        monkeypatch.setenv("VAULT_SECRET_ID", "some-secret-id")
        monkeypatch.setenv("VAULT_USE_DYNAMIC_DB_CREDS", "false")

        with pytest.raises(RuntimeError):
            vault_loader_mod.load_from_vault()

        # 3 attempts → 2 sleeps (no sleep after last attempt)
        assert len(sleep_calls) == vault_loader_mod._RETRY_ATTEMPTS - 1
        assert sleep_calls[0] == 1  # 1 s back-off
        assert sleep_calls[1] == 2  # 2 s back-off

    def test_unknown_auth_method_raises(
        self,
        configured_vault: VaultInfo,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Unknown VAULT_AUTH_METHOD raises RuntimeError immediately."""
        monkeypatch.setenv("VAULT_ADDR", configured_vault["addr"])
        monkeypatch.setenv("VAULT_AUTH_METHOD", "ldap")

        from hub.vault_loader import load_from_vault
        with pytest.raises(RuntimeError, match="Unknown VAULT_AUTH_METHOD"):
            load_from_vault()

    def test_missing_vault_addr_raises(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Missing VAULT_ADDR raises RuntimeError immediately."""
        monkeypatch.delenv("VAULT_ADDR", raising=False)
        monkeypatch.setenv("VAULT_AUTH_METHOD", "approle")
        monkeypatch.setenv("VAULT_ROLE_ID", "r")
        monkeypatch.setenv("VAULT_SECRET_ID", "s")

        from hub.vault_loader import load_from_vault
        with pytest.raises(RuntimeError, match="VAULT_ADDR"):
            load_from_vault()


# ---------------------------------------------------------------------------
# Kubernetes authentication tests
# ---------------------------------------------------------------------------

class TestVaultLoaderKubernetes:
    """Tests for the Kubernetes ServiceAccount authentication path.

    No live k8s cluster is required.  We simulate the JWT file with a
    temporary file and verify that vault_loader reads the correct path and
    surfaces the right errors.
    """

    def test_missing_jwt_file_raises_runtime_error(
        self,
        configured_vault: VaultInfo,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """When the JWT file does not exist, RuntimeError is raised immediately."""
        monkeypatch.setenv("VAULT_ADDR", configured_vault["addr"])
        monkeypatch.setenv("VAULT_AUTH_METHOD", "kubernetes")
        monkeypatch.setenv("VAULT_K8S_ROLE", "hub-api")
        monkeypatch.setenv("VAULT_K8S_JWT_PATH", "/nonexistent/sa/token")
        monkeypatch.setenv("VAULT_USE_DYNAMIC_DB_CREDS", "false")

        from hub.vault_loader import load_from_vault
        with pytest.raises(RuntimeError, match="Cannot read Kubernetes ServiceAccount JWT"):
            load_from_vault()

    def test_empty_jwt_file_raises_runtime_error(
        self,
        configured_vault: VaultInfo,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: pathlib.Path,
    ) -> None:
        """An empty JWT file raises RuntimeError before any network call."""
        jwt_file = tmp_path / "token"
        jwt_file.write_text("")

        monkeypatch.setenv("VAULT_ADDR", configured_vault["addr"])
        monkeypatch.setenv("VAULT_AUTH_METHOD", "kubernetes")
        monkeypatch.setenv("VAULT_K8S_ROLE", "hub-api")
        monkeypatch.setenv("VAULT_K8S_JWT_PATH", str(jwt_file))
        monkeypatch.setenv("VAULT_USE_DYNAMIC_DB_CREDS", "false")

        from hub.vault_loader import load_from_vault
        with pytest.raises(RuntimeError, match="empty"):
            load_from_vault()

    def test_invalid_jwt_raises_error(
        self,
        configured_vault: VaultInfo,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: pathlib.Path,
    ) -> None:
        """A syntactically-valid but invalid JWT is rejected by Vault auth.

        The k8s auth method is configured with a dummy cluster host.  Vault
        will reject the JWT, producing a non-retryable error.  This verifies
        the full code path: JWT file read → hvac.auth.kubernetes.login call.
        """
        cli_env: dict[str, str] = configured_vault["env"]

        try:
            _vault_cli(["auth", "enable", "kubernetes"], cli_env)
        except RuntimeError:
            pass  # already enabled

        _vault_cli(
            ["write", "auth/kubernetes/config",
             "kubernetes_host=https://127.0.0.1:6443",
             "disable_local_ca_jwt=true"],
            cli_env,
        )
        _vault_cli(
            ["write", "auth/kubernetes/role/hub-api",
             "bound_service_account_names=hub-api",
             "bound_service_account_namespaces=hub",
             "token_policies=hub-api",
             "token_ttl=1h"],
            cli_env,
        )

        # Three-part JWT (header.payload.signature) — valid format, bad crypto
        fake_jwt = (
            "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9"
            ".eyJzdWIiOiJzeXN0ZW06c2VydmljZWFjY291bnQ6aHViOmh1Yi1hcGkifQ"
            ".FAKESIGNATURE"
        )
        jwt_file = tmp_path / "token"
        jwt_file.write_text(fake_jwt)

        monkeypatch.setenv("VAULT_ADDR", configured_vault["addr"])
        monkeypatch.setenv("VAULT_AUTH_METHOD", "kubernetes")
        monkeypatch.setenv("VAULT_K8S_ROLE", "hub-api")
        monkeypatch.setenv("VAULT_K8S_JWT_PATH", str(jwt_file))
        monkeypatch.setenv("VAULT_USE_DYNAMIC_DB_CREDS", "false")

        from hub.vault_loader import load_from_vault
        with pytest.raises(RuntimeError):
            load_from_vault()

    def test_k8s_jwt_path_env_var_respected(
        self,
        configured_vault: VaultInfo,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: pathlib.Path,
    ) -> None:
        """VAULT_K8S_JWT_PATH env var controls which file is read."""
        custom_path = str(tmp_path / "custom_jwt_path")  # file does not exist

        monkeypatch.setenv("VAULT_ADDR", configured_vault["addr"])
        monkeypatch.setenv("VAULT_AUTH_METHOD", "kubernetes")
        monkeypatch.setenv("VAULT_K8S_JWT_PATH", custom_path)
        monkeypatch.setenv("VAULT_USE_DYNAMIC_DB_CREDS", "false")

        from hub.vault_loader import load_from_vault
        # Error message must mention the custom path we requested
        with pytest.raises(RuntimeError, match=custom_path):
            load_from_vault()
