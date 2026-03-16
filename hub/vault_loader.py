"""
hub/vault_loader.py
====================
HashiCorp Vault secret loader for the DataInteroperabilityHub Django application.

Responsibilities
----------------
* Detect authentication method (AppRole vs Kubernetes) from environment.
* Authenticate to Vault and obtain a short-lived token.
* Read all required secret paths from KV v2 and the Database engine.
* Inject secrets into ``os.environ`` so Django settings can consume them.
* Retry on transient errors: 3 attempts, exponential back-off 1 s / 2 s / 4 s.
  Raises ``RuntimeError`` when all attempts fail or on non-retryable errors.

Invocation
----------
Called from ``hub/settings.py`` *before* any secret consumption::

    _VAULT_ENABLED = os.environ.get("VAULT_ENABLED", "false").strip().lower() == "true"
    if _VAULT_ENABLED:
        from hub.vault_loader import load_from_vault
        load_from_vault()

Environment variables consumed
-------------------------------
VAULT_ADDR            — Vault server URL (required)
VAULT_AUTH_METHOD     — "approle" (default) | "kubernetes"

AppRole mode:
  VAULT_ROLE_ID       — AppRole role-id
  VAULT_SECRET_ID     — AppRole secret-id

Kubernetes mode:
  VAULT_K8S_ROLE      — Vault Kubernetes auth role name (default: "hub-api")
  VAULT_K8S_JWT_PATH  — ServiceAccount JWT path
                        (default: /var/run/secrets/kubernetes.io/serviceaccount/token)

Optional:
  VAULT_SKIP_VERIFY         — "true" disables TLS cert verification (dev only)
  VAULT_CA_CERT             — Path to custom CA certificate bundle
  VAULT_NAMESPACE           — Vault Enterprise namespace (leave empty for OSS)
  VAULT_USE_DYNAMIC_DB_CREDS— "true" (default) reads database/creds/hub-api;
                              "false" skips dynamic DB creds
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any, cast

import hvac
import hvac.exceptions

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Secret paths — KV v2 full API paths (mount/data/...)
# Convention: mount=secret, path=hub/production/<subsystem>
# ---------------------------------------------------------------------------
_KV_PATHS: list[tuple[str, str]] = [
    ("secret/hub/production/django",  "Django core secrets"),
    ("secret/hub/production/redis",   "Redis credentials"),
    ("secret/hub/production/minio",   "MinIO credentials"),
    ("secret/hub/production/email",   "Email provider credentials"),
]

# Dynamic database credentials path (database secrets engine)
_DB_CREDS_PATH = "database/creds/hub-api"

# Retry configuration
_RETRY_ATTEMPTS = 3
_RETRY_BASE_DELAY_SECONDS = 1  # delays: 1 s, 2 s, 4 s

# ---------------------------------------------------------------------------
# hvac exception classification
#
# TRANSIENT — infrastructure or capacity issues; worth retrying:
#   VaultDown          (503) — Vault is down / initialising
#   VaultNotInitialized(501) — Vault booting up; not yet init'd
#   BadGateway         (502) — upstream proxy / network issue
#   InternalServerError(500) — Vault backend error; may self-recover
#   RateLimitExceeded  (429) — too many requests; back-off and retry
#   UnexpectedError          — unexpected HTTP response; treat as transient
#   ConnectionError/Timeout  — network-level failures (from requests)
#
# NON-RETRYABLE — configuration or auth errors; retrying won't help:
#   Forbidden          (403) — auth succeeded but policy denies access
#   Unauthorized       (401) — bad token / not authenticated
#   InvalidPath        (404) — secret path does not exist
#   InvalidRequest     (400) — malformed request or invalid credentials
#   UnsupportedOperation(405)— operation not supported at this path
#   ParamValidationError     — client-side parameter validation failure
# ---------------------------------------------------------------------------
_TRANSIENT_EXCEPTIONS = (
    hvac.exceptions.VaultDown,
    hvac.exceptions.VaultNotInitialized,
    hvac.exceptions.BadGateway,
    hvac.exceptions.InternalServerError,
    hvac.exceptions.RateLimitExceeded,
    hvac.exceptions.UnexpectedError,
    ConnectionError,
    TimeoutError,
    OSError,
)

_NON_RETRYABLE_EXCEPTIONS = (
    hvac.exceptions.Forbidden,
    hvac.exceptions.Unauthorized,
    hvac.exceptions.InvalidPath,
    hvac.exceptions.InvalidRequest,
    hvac.exceptions.UnsupportedOperation,
    hvac.exceptions.ParamValidationError,
)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _build_client() -> hvac.Client:
    """Construct an unauthenticated hvac.Client from environment configuration."""
    vault_addr = os.environ.get("VAULT_ADDR", "").strip()
    if not vault_addr:
        raise RuntimeError(
            "VAULT_ADDR is not set — cannot connect to Vault. "
            "Set VAULT_ADDR or disable Vault integration with VAULT_ENABLED=false."
        )

    verify: bool | str = True
    if os.environ.get("VAULT_SKIP_VERIFY", "false").lower() == "true":
        verify = False
        logger.warning("VAULT_SKIP_VERIFY=true — TLS certificate verification disabled (dev only).")
    elif ca_cert := os.environ.get("VAULT_CA_CERT", "").strip():
        verify = ca_cert

    namespace = os.environ.get("VAULT_NAMESPACE", "").strip() or None

    return hvac.Client(url=vault_addr, verify=verify, namespace=namespace)


def _authenticate_approle(client: hvac.Client) -> None:
    """Authenticate using AppRole credentials from environment."""
    role_id = os.environ.get("VAULT_ROLE_ID", "").strip()
    secret_id = os.environ.get("VAULT_SECRET_ID", "").strip()

    if not role_id:
        raise RuntimeError("VAULT_ROLE_ID is not set — required for AppRole authentication.")
    if not secret_id:
        raise RuntimeError("VAULT_SECRET_ID is not set — required for AppRole authentication.")

    resp = client.auth.approle.login(role_id=role_id, secret_id=secret_id)
    client.token = resp["auth"]["client_token"]
    logger.debug(
        "Vault AppRole authentication successful",
        extra={"lease_duration": resp["auth"]["lease_duration"]},
    )


def _authenticate_kubernetes(client: hvac.Client) -> None:
    """Authenticate using the Kubernetes ServiceAccount JWT."""
    role = os.environ.get("VAULT_K8S_ROLE", "hub-api").strip()
    jwt_path = os.environ.get(
        "VAULT_K8S_JWT_PATH",
        "/var/run/secrets/kubernetes.io/serviceaccount/token",
    ).strip()

    try:
        with open(jwt_path) as fh:
            jwt = fh.read().strip()
    except OSError as exc:
        raise RuntimeError(
            f"Cannot read Kubernetes ServiceAccount JWT at '{jwt_path}': {exc}. "
            "Ensure the pod is running with the correct ServiceAccount."
        ) from exc

    if not jwt:
        raise RuntimeError(
            f"Kubernetes ServiceAccount JWT at '{jwt_path}' is empty."
        )

    resp = client.auth.kubernetes.login(role=role, jwt=jwt)
    client.token = resp["auth"]["client_token"]
    logger.debug(
        "Vault Kubernetes authentication successful",
        extra={"role": role, "lease_duration": resp["auth"]["lease_duration"]},
    )


def _authenticate(client: hvac.Client) -> None:
    """Detect auth method from VAULT_AUTH_METHOD env var and authenticate."""
    method = os.environ.get("VAULT_AUTH_METHOD", "approle").lower().strip()
    if method == "approle":
        _authenticate_approle(client)
    elif method == "kubernetes":
        _authenticate_kubernetes(client)
    else:
        raise RuntimeError(
            f"Unknown VAULT_AUTH_METHOD '{method}'. "
            "Supported values: 'approle', 'kubernetes'."
        )


def _read_kv2(client: hvac.Client, mount: str, path: str) -> dict[str, Any]:
    """
    Read a KV v2 secret via hvac.

    Parameters
    ----------
    mount : str
        The KV v2 mount name, e.g. ``"secret"``.
    path : str
        The secret path relative to the mount, e.g. ``"hub/production/django"``.

    Returns
    -------
    dict[str, Any]
        The inner ``data`` dict from the KV v2 response.
    """
    response = client.secrets.kv.v2.read_secret_version(
        path=path,
        mount_point=mount,
        raise_on_deleted_version=True,
    )
    return cast(dict[str, Any], response["data"]["data"])


def _read_db_creds(client: hvac.Client) -> dict[str, str]:
    """Read dynamic PostgreSQL credentials from the database secrets engine."""
    response = client.read(_DB_CREDS_PATH)
    if response is None or "data" not in response:
        raise RuntimeError(
            f"Vault returned empty response for '{_DB_CREDS_PATH}'. "
            "Ensure the database secrets engine is configured and the hub-api role exists."
        )
    data = response["data"]
    return {
        "POSTGRES_USER": data["username"],
        "POSTGRES_PASSWORD": data["password"],
    }


def _inject_secrets(secrets: dict[str, str]) -> None:
    """Inject a flat dict of secrets into ``os.environ``."""
    for key, value in secrets.items():
        os.environ[key] = str(value)


def _do_load() -> None:
    """Core load logic (called inside the retry wrapper)."""
    client = _build_client()
    _authenticate(client)

    if not client.is_authenticated():
        raise RuntimeError("Vault client is not authenticated after login attempt.")

    # Collect ALL secrets into a single dict before injecting to guarantee atomicity:
    # either all secrets are injected or none are (partial-state protection).
    merged: dict[str, str] = {}

    for secret_path, description in _KV_PATHS:
        # _KV_PATHS stores mount-relative paths; mount is always "secret"
        logger.debug("Reading Vault KV path", extra={"path": secret_path})
        data = _read_kv2(client, mount="secret", path=secret_path)
        merged.update({k: str(v) for k, v in data.items()})

    # Dynamic DB credentials (optional — skippable during bootstrap)
    use_dynamic_db = os.environ.get("VAULT_USE_DYNAMIC_DB_CREDS", "true").lower() == "true"
    if use_dynamic_db:
        logger.debug("Reading dynamic database credentials", extra={"path": _DB_CREDS_PATH})
        try:
            merged.update(_read_db_creds(client))
        except Exception as exc:
            # Non-fatal only if static creds are available (bootstrap scenario)
            if os.environ.get("POSTGRES_PASSWORD", "").strip():
                logger.warning(
                    "Dynamic DB credential read failed; falling back to static POSTGRES_PASSWORD. "
                    "Error: %s",
                    exc,
                )
            else:
                raise RuntimeError(
                    f"Failed to read dynamic DB credentials and no static "
                    f"POSTGRES_PASSWORD fallback is set: {exc}"
                ) from exc

    _inject_secrets(merged)
    logger.info("Vault secrets loaded successfully", extra={"num_keys": len(merged)})


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def load_from_vault() -> None:
    """
    Load all application secrets from Vault and inject them into ``os.environ``.

    Retry policy
    ------------
    * Transient errors (network, 5xx, 429, 501, 503): retry up to
      ``_RETRY_ATTEMPTS`` times with exponential back-off (1 s, 2 s, 4 s).
    * Non-retryable errors (403, 404, 400, 401, config): raise immediately.
    * After exhausting all retries: raise ``RuntimeError``.

    Idempotent — safe to call multiple times; later calls overwrite earlier values.
    """
    last_exc: Exception | None = None

    for attempt in range(1, _RETRY_ATTEMPTS + 1):
        try:
            _do_load()
            return  # Success

        except _NON_RETRYABLE_EXCEPTIONS as exc:
            # Config / auth errors — retrying cannot help
            logger.error("Vault load failed (non-retryable error): %s", exc)
            raise RuntimeError(
                f"Failed to load secrets from Vault (non-retryable): {exc}"
            ) from exc

        except RuntimeError:
            # RuntimeError from our own validation code (missing env vars etc.)
            raise

        except _TRANSIENT_EXCEPTIONS as exc:
            last_exc = exc
            if attempt < _RETRY_ATTEMPTS:
                delay = _RETRY_BASE_DELAY_SECONDS * (2 ** (attempt - 1))  # 1 s, 2 s, 4 s
                logger.warning(
                    "Vault load attempt %d/%d failed (transient): %s. Retrying in %d s ...",
                    attempt,
                    _RETRY_ATTEMPTS,
                    exc,
                    delay,
                )
                time.sleep(delay)
            else:
                logger.error(
                    "Vault load failed after %d attempts. Last error: %s",
                    _RETRY_ATTEMPTS,
                    exc,
                )

        except Exception as exc:
            # Catch-all for unexpected hvac / network exceptions not in above lists.
            # Treat as transient — unexpected doesn't mean non-retryable.
            last_exc = exc
            if attempt < _RETRY_ATTEMPTS:
                delay = _RETRY_BASE_DELAY_SECONDS * (2 ** (attempt - 1))
                logger.warning(
                    "Vault load attempt %d/%d failed (unexpected error): %s. Retrying in %d s ...",
                    attempt,
                    _RETRY_ATTEMPTS,
                    exc,
                    delay,
                )
                time.sleep(delay)
            else:
                logger.error(
                    "Vault load failed after %d attempts (unexpected error): %s",
                    _RETRY_ATTEMPTS,
                    exc,
                )

    raise RuntimeError(
        f"Failed to load secrets from Vault after {_RETRY_ATTEMPTS} attempts. "
        f"Last error: {last_exc}"
    ) from last_exc
