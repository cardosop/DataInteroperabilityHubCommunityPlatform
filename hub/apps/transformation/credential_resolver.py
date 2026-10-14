"""
285.9.1.1.2 — Credential resolver for transformation pipelines.

Resolves warehouse and git credentials from AWS Secrets Manager,
returning them in dbt profiles.yml and git-clone-ready formats.

Key contract:
- Always fetches the latest AWS SM version (no caching).
- Rotated credentials fail fast with auth error (no retry for AccessDenied).

Phase 11 (openspec add-databricks-control-plane task 11.3) — the Hub-model
Databricks paths that FEED the databricks branch above
(``_build_dbt_profile`` / ``_databricks_output``):

- ``resolve_databricks_workspace_credentials`` — a registered
  ``DatabricksWorkspace``'s OWN credential (PAT token direct; OAUTH_M2M
  through the production exchange + the REAL M2M token cache) + the
  workspace host + the caller's SQL-warehouse http_path.
- ``resolve_databricks_connection_credentials`` — a DATABRICKS
  ``WarehouseConnection``'s OWN decrypted config (host/http_path/catalog/
  schema) + the PAT/M2M token material (the same cache + production-
  exchange primitives the 6.6 movement seam uses — composed, never
  reimplemented; the cache-key convention is shared so one bearer
  serves both surfaces).

SANCTIONED SEAM (the umbrella design's Appendix B row "dbt adapter +
introspection — hub/apps/transformation/credential_resolver.py, P11"):
these functions import ONLY the provider-agnostic m2m token-cache seam
(``hub.apps.integrations.m2m_token_cache`` — the estate registers its
``M2MTokenCache`` factory at app-ready, the W4.6 inversion shared with
the data_movement bridge) and the production exchange
(``hub.apps.warehouses.connectors.databricks.resolve_access_token``),
both lazily at call time; estate MODELS are accessed through instance
attributes and TYPE_CHECKING imports only. Fail-closed everywhere —
no credential row, an empty token, a missing host/http_path, or a
non-Databricks connection refuses with ``CredentialResolverError``
naming the bit, ZERO network calls. The token value is never logged.
"""

from __future__ import annotations

import json
import os
from typing import TYPE_CHECKING, Any

import structlog

if TYPE_CHECKING:
    # core-guard: full-mode-only — TYPE_CHECKING-only import (no runtime coupling)
    from hub.apps.databricks_admin.models import DatabricksWorkspace
    from hub.apps.warehouses.models import WarehouseConnection

logger = structlog.get_logger(__name__)

# Profile name used in the generated dbt profiles.yml
_DBT_PROFILE_NAME = "meshant_dbt"
_DEFAULT_SCHEMA = "public"
_DEFAULT_DATABASE = "analytics"


class CredentialResolverError(Exception):
    """Raised when credential resolution fails — missing secret, invalid format,
    unsupported type, or access denied."""


# ── Public API ────────────────────────────────────────────────────────


def resolve_warehouse_credentials(
    credential_ref: str, profile_name: str = _DBT_PROFILE_NAME
) -> dict[str, Any]:
    """Resolve warehouse credentials from AWS Secrets Manager and return
    a dbt ``profiles.yml`` dict.

    ``credential_ref`` must be an AWS Secrets Manager ARN.

    ``profile_name`` is the dbt profile name used in the output dict
    (default ``"meshant_dbt"``). Step 1.2 sets this to
    ``meshant_{tenant_slug}_{pipeline_id}`` for per-run isolation.

    The secret value must be a JSON object with at minimum a ``type`` key
    (``"snowflake"``, ``"bigquery"``, or ``"databricks"``) plus the
    required fields for that warehouse type.

    Returns a dict shaped like::

        {
            "<profile_name>": {
                "target": "prod",
                "outputs": {
                    "prod": {
                        "type": "snowflake",
                        "account": "...",
                        ...
                    }
                }
            }
        }
    """
    secret = _fetch_secret(credential_ref)
    profile = _build_dbt_profile(secret, profile_name)
    warehouse_type = secret.get("type", "unknown")
    logger.info(
        "warehouse_credentials_resolved",
        warehouse_type=warehouse_type,
        profile_name=profile_name,
    )
    return profile


def resolve_git_credentials(credential_ref: str) -> dict[str, str]:
    """Resolve git credentials from AWS Secrets Manager.

    ``credential_ref`` must be an AWS Secrets Manager ARN.

    The secret value must be a JSON object with at minimum a ``token`` key.
    Optional: ``provider`` (``"github"`` / ``"gitlab"``) and ``username``.

    Returns a dict with ``token`` and ``username`` suitable for git clone::

        {"token": "ghp_...", "username": "meshant-bot"}
    """
    secret = _fetch_secret(credential_ref)
    creds = _build_git_credential(secret)
    logger.info(
        "git_credentials_resolved",
        provider=secret.get("provider", "github"),
        has_username=bool(creds.get("username")),
    )
    return creds


# ── Internal: AWS SM fetch ────────────────────────────────────────────


def _build_client():
    """Construct a boto3 Secrets Manager client.

    Uses the region from ``AWS_REGION`` env var (default ``us-east-1``).
    Authentication via the standard boto3 credential chain (IRSA, instance
    profile, env vars, or AWS_PROFILE).
    """
    region = os.environ.get("AWS_REGION", "us-east-1").strip()
    try:
        import boto3
    except ImportError:
        raise CredentialResolverError(
            "boto3 is required for AWS Secrets Manager credential resolution. "
            "Install it with: pip install boto3"
        ) from None
    return boto3.client("secretsmanager", region_name=region)


def _fetch_secret(arn: str) -> dict[str, Any]:
    """Fetch and parse a JSON secret from AWS Secrets Manager.

    Always calls AWS SM directly — no in-process caching.
    Auth errors (AccessDenied) fail immediately (fail-fast for rotated
    credentials). Transient network / throttling errors are retried up
    to 3 times with exponential back-off following the codebase convention
    in ``hub/aws_secrets_loader.py``.
    """
    import time

    from botocore.exceptions import ClientError, EndpointConnectionError

    _RETRY_ATTEMPTS = 3
    _RETRY_BASE_DELAY = 1  # seconds: 1, 2, 4

    _TRANSIENT_EXCEPTIONS = (
        EndpointConnectionError,
        ConnectionError,
        TimeoutError,
        OSError,
    )

    client = _build_client()
    last_exc: Exception | None = None

    for attempt in range(1, _RETRY_ATTEMPTS + 1):

        def _fetch_once() -> dict[str, Any]:
            response = client.get_secret_value(SecretId=arn)
            secret_string = response.get("SecretString")
            if not secret_string:
                raise CredentialResolverError(
                    f"Secret {arn} has no SecretString (binary secrets not supported)."
                )
            try:
                result = json.loads(secret_string)
            except json.JSONDecodeError as exc:
                raise CredentialResolverError(
                    f"Invalid JSON in secret {arn}: {exc}"
                ) from exc

            logger.debug(
                "credential_secret_fetched",
                arn_hash=hash(arn),
                keys=list(result.keys()),
            )
            return result

        try:
            result = _fetch_once()
        except CredentialResolverError:
            raise  # structural errors — no retry

        except ClientError as exc:
            error_code = exc.response.get("Error", {}).get("Code", "Unknown")
            message = exc.response.get("Error", {}).get("Message", str(exc))

            # Auth errors — fail fast (rotated credentials).
            if error_code in ("AccessDeniedException", "UnrecognizedClientException"):
                logger.warning(
                    "credential_access_denied",
                    arn_hash=hash(arn),
                    error_code=error_code,
                )
                raise CredentialResolverError(
                    f"Access denied for secret {arn}: {message}"
                ) from exc

            # Not-found — no point retrying either.
            if error_code == "ResourceNotFoundException":
                logger.warning(
                    "credential_secret_not_found",
                    arn_hash=hash(arn),
                )
                raise CredentialResolverError(
                    f"Secret {arn} not found: {message}"
                ) from exc

            # Other ClientErrors (throttling, internal-error) — transient.
            last_exc = exc
            if attempt < _RETRY_ATTEMPTS:
                delay = _RETRY_BASE_DELAY * (2 ** (attempt - 1))
                logger.warning(
                    "credential_fetch_retry",
                    arn_hash=hash(arn),
                    attempt=attempt,
                    error_code=error_code,
                    retry_delay_s=delay,
                )
                time.sleep(delay)
            else:
                logger.exception(
                    "credential_fetch_failed",
                    arn_hash=hash(arn),
                    attempts=_RETRY_ATTEMPTS,
                    error_code=error_code,
                )

        except _TRANSIENT_EXCEPTIONS as exc:
            last_exc = exc
            if attempt < _RETRY_ATTEMPTS:
                delay = _RETRY_BASE_DELAY * (2 ** (attempt - 1))
                logger.warning(
                    "credential_fetch_retry_transient",
                    arn_hash=hash(arn),
                    attempt=attempt,
                    error_type=type(exc).__name__,
                    retry_delay_s=delay,
                )
                time.sleep(delay)
            else:
                logger.exception(
                    "credential_fetch_failed_transient",
                    arn_hash=hash(arn),
                    attempts=_RETRY_ATTEMPTS,
                    error_type=type(exc).__name__,
                )

        except Exception as exc:
            last_exc = exc
            if attempt < _RETRY_ATTEMPTS:
                delay = _RETRY_BASE_DELAY * (2 ** (attempt - 1))
                logger.warning(
                    "credential_fetch_retry_unexpected",
                    arn_hash=hash(arn),
                    attempt=attempt,
                    error_type=type(exc).__name__,
                    retry_delay_s=delay,
                )
                time.sleep(delay)
            else:
                logger.exception(
                    "credential_fetch_failed_unexpected",
                    arn_hash=hash(arn),
                    attempts=_RETRY_ATTEMPTS,
                    error_type=type(exc).__name__,
                )

        else:
            return result

    raise CredentialResolverError(
        f"Failed to resolve secret after {_RETRY_ATTEMPTS} attempts. Last error: {last_exc}"
    ) from last_exc


# ── Internal: dbt profiles.yml builders ───────────────────────────────

_WAREHOUSE_REQUIRED_FIELDS: dict[str, tuple[str, ...]] = {
    "snowflake": ("account", "user", "password"),
    "bigquery": ("project", "dataset", "keyfile"),
    "databricks": ("host", "http_path", "token"),
}


def _build_dbt_profile(secret: dict[str, Any], profile_name: str) -> dict[str, Any]:
    """Build a dbt profiles.yml dict from a parsed warehouse secret."""
    warehouse_type = secret.get("type", "").lower()
    if not warehouse_type:
        raise CredentialResolverError(
            "Secret is missing required 'type' field (expected one of: "
            "snowflake, bigquery, databricks)."
        )

    if warehouse_type not in _WAREHOUSE_REQUIRED_FIELDS:
        raise CredentialResolverError(
            f"Unsupported warehouse type '{warehouse_type}'. "
            f"Supported types: {', '.join(sorted(_WAREHOUSE_REQUIRED_FIELDS))}."
        )

    required = _WAREHOUSE_REQUIRED_FIELDS[warehouse_type]
    for field in required:
        if field not in secret:
            raise CredentialResolverError(
                f"Missing required field '{field}' for warehouse type '{warehouse_type}'."
            )

    if warehouse_type == "snowflake":
        output = _snowflake_output(secret)
    elif warehouse_type == "bigquery":
        output = _bigquery_output(secret)
    elif warehouse_type == "databricks":
        output = _databricks_output(secret)
    else:
        raise CredentialResolverError(  # pragma: no cover — validated above
            f"Unsupported warehouse type '{warehouse_type}'."
        )

    return {
        profile_name: {
            "target": "prod",
            "outputs": {
                "prod": output,
            },
        }
    }


def _snowflake_output(secret: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "snowflake",
        "account": secret["account"],
        "user": secret["user"],
        "password": secret["password"],
        "role": secret.get("role", "transform"),
        "database": secret.get("database", _DEFAULT_DATABASE),
        "warehouse": secret.get("warehouse", "compute_wh"),
        "schema": secret.get("schema", _DEFAULT_SCHEMA),
        "threads": secret.get("threads", 4),
        "client_session_keep_alive": secret.get("client_session_keep_alive", False),
    }


def _bigquery_output(secret: dict[str, Any]) -> dict[str, Any]:
    keyfile = secret["keyfile"]
    # dbt-bigquery: ``keyfile`` expects a file *path* (str), while
    # ``keyfile_json`` expects an inline dict.  Detect which form the
    # secret carries and emit the correct profile key.
    keyfield = "keyfile_json" if isinstance(keyfile, dict) else "keyfile"

    output: dict[str, Any] = {
        "type": "bigquery",
        "method": secret.get("method", "service-account"),
        "project": secret["project"],
        "dataset": secret["dataset"],
        keyfield: keyfile,
        "threads": secret.get("threads", 4),
        "priority": secret.get("priority", "interactive"),
    }
    location = secret.get("location")
    if location is not None:
        output["location"] = location
    output["timeout_seconds"] = secret.get("timeout_seconds", 300)
    return output


def _databricks_output(secret: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "databricks",
        "host": secret["host"],
        "http_path": secret["http_path"],
        "token": secret["token"],
        "catalog": secret.get("catalog", "main"),
        "schema": secret.get("schema", _DEFAULT_SCHEMA),
        "threads": secret.get("threads", 4),
    }


# ── Internal: git credential builder ──────────────────────────────────


def _build_git_credential(secret: dict[str, Any]) -> dict[str, str]:
    """Build a git credential dict from a parsed git secret."""
    token = secret.get("token")
    if not token:
        raise CredentialResolverError("Git secret is missing required 'token' field.")

    provider = secret.get("provider", "github").lower()
    username = secret.get("username")
    if not username:
        # Sensible defaults per provider
        username = "oauth2" if provider == "gitlab" else "meshant-bot"

    return {
        "token": token,
        "username": username,
    }


# ── Phase 11 (11.3): Hub-model Databricks resolution ─────────────────────


def _m2m_bearer(
    *,
    config: dict[str, Any],
    workspace_key: str,
    exchange_base_url: str | None,
    token_cache=None,
) -> str:
    """The OAUTH_M2M bearer — the REAL token cache + the production
    exchange (``warehouses.connectors.databricks.resolve_access_token``,
    the 6.6 seam's primitives, COMPOSED — the cache-key convention is
    shared so one cached bearer serves both surfaces). Cache
    reads/writes are best-effort (a cache outage never blocks the
    resolution, the Phase 273 discipline)."""
    import redis

    client_id = str(config.get("client_id") or "").strip()
    client_secret = str(config.get("client_secret") or "").strip()
    if not client_id:
        raise CredentialResolverError("Databricks M2M config has no 'client_id' value")
    if not client_secret:
        raise CredentialResolverError(
            "Databricks M2M config has no 'client_secret' value"
        )

    credential_ref = f"{client_id}|{client_secret}"

    if token_cache is None:
        # W4.6 (oss-release-remediation, G1) — the default cache rides
        # the provider-agnostic m2m token-cache seam (the estate
        # registers its factory at app-ready); None = best-effort
        # no-cache mode.
        from hub.apps.integrations.m2m_token_cache import (
            default_m2m_token_cache,
        )

        token_cache = default_m2m_token_cache()
        if token_cache is None:
            logger.warning(
                "dbt_m2m_token_cache_unavailable",
                workspace_key=workspace_key,
                error="no provider registered a default token cache",
            )

    cached = None
    if token_cache is not None:
        try:
            cached = token_cache.get(workspace_key, credential_ref)
        except (redis.RedisError, ConnectionError, OSError):
            logger.warning(
                "dbt_m2m_token_cache_read_failed",
                workspace_key=workspace_key,
                error="cache unavailable",
            )
    if cached:
        return cached

    from hub.apps.warehouses.connectors.databricks import resolve_access_token

    # The connector dispatches on the config's auth_mode (PAT is the
    # default) — the workspace credential stores the mode on the MODEL
    # row, so the exchange config must carry it explicitly.
    bearer = resolve_access_token(
        {**config, "auth_mode": "OAUTH_M2M"}, exchange_base_url=exchange_base_url
    )
    if token_cache is not None:
        try:
            token_cache.set(workspace_key, credential_ref, bearer)
        except (redis.RedisError, ConnectionError, OSError):
            logger.warning(
                "dbt_m2m_token_cache_write_failed",
                workspace_key=workspace_key,
                error="cache unavailable",
            )
    return bearer


def _databricks_profile_from_parts(
    *,
    host: str,
    http_path: str,
    token: str,
    catalog: str | None,
    schema: str | None,
    profile_name: str,
) -> dict[str, Any]:
    """Feed the REUSED databricks branch (``_build_dbt_profile``) with
    the Hub-model material — the profile shape stays the SM path's."""
    secret: dict[str, Any] = {
        "type": "databricks",
        "host": host,
        "http_path": http_path,
        "token": token,
    }
    if catalog:
        secret["catalog"] = catalog
    if schema:
        secret["schema"] = schema
    return _build_dbt_profile(secret, profile_name)


def resolve_databricks_workspace_credentials(
    workspace: DatabricksWorkspace,
    *,
    http_path: str,
    catalog: str = "main",
    schema: str = _DEFAULT_SCHEMA,
    profile_name: str = _DBT_PROFILE_NAME,
    token_cache=None,
    exchange_base_url: str | None = None,
) -> dict[str, Any]:
    """Resolve a dbt profiles.yml dict for a registered workspace — the
    workspace's OWN credential is the identity (never a new credential
    store): the LATEST PAT|OAUTH_M2M credential row (the 1.3 view
    convention); a PAT token ships direct, an M2M credential resolves
    the bearer through the REAL cache + production exchange. The
    http_path is the CALLER's SQL-warehouse path (the 3.6 derived
    value). Fails closed with ZERO network on a missing credential,
    an empty token, or a missing http_path."""
    http_path = (http_path or "").strip()
    if not http_path:
        raise CredentialResolverError("A SQL-warehouse http_path is required")

    credential = (
        workspace.credentials.filter(auth_mode__in=["PAT", "OAUTH_M2M"])
        .order_by("-created_at")
        .first()
    )
    if credential is None:
        raise CredentialResolverError(
            f"Workspace {workspace.id} has no PAT|OAUTH_M2M credential — "
            "register one before running dbt against it"
        )

    config = credential.get_config()
    if credential.auth_mode == "PAT":
        token = str(config.get("token") or "").strip()
        if not token:
            raise CredentialResolverError("Databricks PAT config has no 'token' value")
    else:
        token = _m2m_bearer(
            config=config,
            workspace_key=str(workspace.id),
            exchange_base_url=exchange_base_url or f"https://{workspace.host}",
            token_cache=token_cache,
        )

    return _databricks_profile_from_parts(
        host=workspace.host,
        http_path=http_path,
        token=token,
        catalog=catalog,
        schema=schema,
        profile_name=profile_name,
    )


def resolve_databricks_connection_credentials(
    connection: WarehouseConnection,
    *,
    catalog: str | None = None,
    schema: str | None = None,
    profile_name: str = _DBT_PROFILE_NAME,
    token_cache=None,
    exchange_base_url: str | None = None,
) -> dict[str, Any]:
    """Resolve a dbt profiles.yml dict from a DATABRICKS
    ``WarehouseConnection`` — the connection's OWN decrypted config is
    the identity (the real ``get_config()`` decrypt, never a new
    credential store). PAT (``auth_mode`` "PAT" or absent): the stored
    ``pat_token``; OAUTH_M2M: the REAL cache + production exchange (the
    6.6 primitives). host/http_path are the connection's transport
    values (the 3.6 derived path). catalog/schema: caller kwargs >
    config keys > the branch defaults. Fails closed naming the bit."""
    from hub.apps.warehouses.models import WarehouseType

    if getattr(connection, "warehouse_type", None) != WarehouseType.DATABRICKS:
        raise CredentialResolverError(
            "dbt Databricks profiles resolve DATABRICKS connections only "
            f"(got {getattr(connection, 'warehouse_type', '?')})"
        )

    config = connection.get_config()
    host = str(config.get("host") or "").strip()
    if not host:
        raise CredentialResolverError(
            "Databricks connection config has no 'host' value"
        )
    http_path = str(config.get("http_path") or "").strip()
    if not http_path:
        raise CredentialResolverError(
            "Databricks connection config has no 'http_path' value (the 3.6 derived path)"
        )

    auth_mode = config.get("auth_mode", "PAT")
    if auth_mode == "PAT":
        token = str(config.get("pat_token") or "").strip()
        if not token:
            raise CredentialResolverError(
                "Databricks PAT config has no 'pat_token' value"
            )
    elif auth_mode == "OAUTH_M2M":
        workspace_key = (
            str(getattr(connection, "databricks_workspace_id", None) or "") or host
        )
        token = _m2m_bearer(
            config=config,
            workspace_key=workspace_key,
            exchange_base_url=exchange_base_url,
            token_cache=token_cache,
        )
    else:
        raise CredentialResolverError(
            f"Unsupported Databricks auth_mode '{auth_mode}' (PAT|OAUTH_M2M)"
        )

    resolved_catalog = catalog or str(config.get("catalog") or "").strip() or "main"
    resolved_schema = (
        schema or str(config.get("schema") or "").strip() or _DEFAULT_SCHEMA
    )
    return _databricks_profile_from_parts(
        host=host,
        http_path=http_path,
        token=token,
        catalog=resolved_catalog,
        schema=resolved_schema,
        profile_name=profile_name,
    )
