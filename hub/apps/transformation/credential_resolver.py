"""
285.9.1.1.2 — Credential resolver for transformation pipelines.

Resolves warehouse and git credentials from AWS Secrets Manager,
returning them in dbt profiles.yml and git-clone-ready formats.

Key contract:
- Always fetches the latest AWS SM version (no caching).
- Rotated credentials fail fast with auth error (no retry for AccessDenied).
"""

from __future__ import annotations

import json
import os
from typing import Any

import structlog

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
        )
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

    _TRANSIENT_EXCEPTIONS = (EndpointConnectionError, ConnectionError, TimeoutError, OSError)

    client = _build_client()
    last_exc: Exception | None = None

    for attempt in range(1, _RETRY_ATTEMPTS + 1):
        try:
            response = client.get_secret_value(SecretId=arn)
            secret_string = response.get("SecretString")
            if not secret_string:
                raise CredentialResolverError(
                    f"Secret {arn} has no SecretString (binary secrets not supported)."
                )
            try:
                result = json.loads(secret_string)
            except json.JSONDecodeError as exc:
                raise CredentialResolverError(f"Invalid JSON in secret {arn}: {exc}") from exc

            logger.debug(
                "credential_secret_fetched",
                arn_hash=hash(arn),
                keys=list(result.keys()),
            )
            return result

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
                raise CredentialResolverError(f"Access denied for secret {arn}: {message}") from exc

            # Not-found — no point retrying either.
            if error_code == "ResourceNotFoundException":
                logger.warning(
                    "credential_secret_not_found",
                    arn_hash=hash(arn),
                )
                raise CredentialResolverError(f"Secret {arn} not found: {message}") from exc

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
                logger.error(
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
                logger.error(
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
                logger.error(
                    "credential_fetch_failed_unexpected",
                    arn_hash=hash(arn),
                    attempts=_RETRY_ATTEMPTS,
                    error_type=type(exc).__name__,
                )

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
    if isinstance(keyfile, dict):
        keyfield = "keyfile_json"
    else:
        keyfield = "keyfile"

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
        if provider == "gitlab":
            username = "oauth2"
        else:
            username = "meshant-bot"

    return {
        "token": token,
        "username": username,
    }
