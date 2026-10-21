"""
285.6.2.5 — Credential resolution bridge for dlt.

Unified credential resolution from three sources:
1. AWS Secrets Manager ARN → boto3 get_secret_value()
2. Prefect Block → Secret.load()
3. Local dev → .dlt/secrets.toml
"""

from __future__ import annotations

import json
import os
from typing import Any

import structlog

logger = structlog.get_logger(__name__)

# Path to dlt secrets file for local development
DLT_SECRETS_PATH = os.path.join(os.path.expanduser("~"), ".dlt", "secrets.toml")


def resolve_credentials(credential_ref: str | None = None) -> dict[str, Any]:
    """
    Resolve credentials for dlt pipeline execution.

    Priority order:
    1. If credential_ref is an AWS SM ARN → resolve via boto3
    2. If credential_ref is a Prefect block name → resolve via Secret.load()
    3. Fall back to .dlt/secrets.toml for local dev

    Returns a dict suitable for dlt destination/source credentials.
    """
    if credential_ref:
        if credential_ref.startswith("arn:aws:secretsmanager:"):
            return _resolve_from_aws_sm(credential_ref)
        if credential_ref.startswith("prefect://"):
            return _resolve_from_prefect(credential_ref)
        # Assume it's a direct key path in .dlt/secrets.toml
        return _resolve_from_toml(credential_ref)
    return _resolve_from_toml(None)


def resolve_connection_credentials(
    connection,
    *,
    exchange_base_url: str | None = None,
    token_cache=None,
) -> dict[str, Any]:
    """6.6 (wire-databricks-dlt-movement) — resolve dlt credentials from a
    ``WarehouseConnection`` (design D3).

    The connection's OWN encrypted config is the identity (the real
    ``get_config()`` decrypt — never a new credential store, never
    plaintext at rest). PAT (``auth_mode`` "PAT" or absent): the stored
    ``pat_token`` becomes dlt's ``access_token`` — an empty token fails
    closed. OAUTH_M2M: the cached M2M token layer owns the token
    lifecycle (the provider-agnostic m2m token-cache seam — the estate
    registers its ``M2MTokenCache`` factory at app-ready, W4.6; cache
    reads/writes are best-effort and never block the movement); on a
    cache miss the exchange is DELEGATED to the warehouses connector's production
    ``resolve_access_token`` (retried/jittered/classified) and the bearer
    is cached under the channel convention the control-plane client uses
    (the linked workspace id when the connection carries one, else the
    host — cache entries stay shared with the client's). The returned
    dict is the dlt credential mapping (``{"access_token": <bearer>}``);
    the token value is never logged.
    """
    import redis

    from hub.apps.warehouses.connectors.databricks import resolve_access_token
    from hub.apps.warehouses.exceptions import (
        WarehouseConnectionError,
        WarehouseUnsupportedTypeError,
    )
    from hub.apps.warehouses.models import WarehouseType

    if getattr(connection, "warehouse_type", None) != WarehouseType.DATABRICKS:
        raise WarehouseUnsupportedTypeError(
            "dlt connection credentials resolve Databricks connections only "
            f"(got {getattr(connection, 'warehouse_type', '?')})"
        )

    config = connection.get_config()
    auth_mode = config.get("auth_mode", "PAT")

    if auth_mode == "PAT":
        token = config.get("pat_token", "")
        if not token:
            raise WarehouseConnectionError(
                "Databricks PAT config has no 'pat_token' value"
            )
        return {"access_token": token}

    if auth_mode == "OAUTH_M2M":
        client_id = config.get("client_id", "")
        client_secret = config.get("client_secret", "")
        if not client_id or not client_secret:
            raise WarehouseConnectionError(
                "Databricks OAuth M2M config has no 'client_id'/'client_secret' value"
            )

        workspace_key = str(
            getattr(connection, "databricks_workspace_id", None) or ""
        ) or str(config.get("host", ""))
        credential_ref = f"{client_id}|{client_secret}"

        if token_cache is None:
            # W4.6 (oss-release-remediation, G1) — the default cache
            # rides the provider-agnostic m2m token-cache seam (the
            # estate registers its factory at app-ready); None = the
            # best-effort no-cache mode (a provider with no cache).
            from hub.apps.integrations.m2m_token_cache import (
                default_m2m_token_cache,
            )

            token_cache = default_m2m_token_cache()
            if token_cache is None:
                logger.warning(
                    "m2m_token_cache_unavailable",
                    workspace_key=workspace_key,
                    error="no provider registered a default token cache",
                )

        cached = None
        if token_cache is not None:
            try:
                cached = token_cache.get(workspace_key, credential_ref)
            except (redis.RedisError, ConnectionError, OSError):
                # Best-effort cache READ — a cache outage never blocks the
                # movement (the Phase 273 discipline).
                logger.warning(
                    "m2m_token_cache_read_failed",
                    workspace_key=workspace_key,
                    error="cache unavailable",
                )
        if cached:
            return {"access_token": cached}

        token = resolve_access_token(config, exchange_base_url=exchange_base_url)
        if token_cache is not None:
            try:
                token_cache.set(workspace_key, credential_ref, token)
            except (redis.RedisError, ConnectionError, OSError):
                # Best-effort cache WRITE — the bearer lives for this run
                # regardless; a later run re-exchanges on the miss.
                logger.warning(
                    "m2m_token_cache_write_failed",
                    workspace_key=workspace_key,
                    error="cache unavailable",
                )
        return {"access_token": token}

    raise WarehouseConnectionError(
        f"Unsupported Databricks auth_mode '{auth_mode}' (PAT|OAUTH_M2M)"
    )


def _resolve_from_aws_sm(arn: str) -> dict[str, Any]:
    """Resolve credentials from AWS Secrets Manager ARN."""
    try:
        import boto3
        from botocore.exceptions import ClientError

        region = os.environ.get("AWS_REGION", "us-east-1")
        client = boto3.client("secretsmanager", region_name=region)
        response = client.get_secret_value(SecretId=arn)
        secret = response.get("SecretString")
        if secret:
            try:
                return json.loads(secret)
            except json.JSONDecodeError:
                return {"secret_value": secret}
    except ClientError as e:
        logger.exception("aws_sm_resolve_failed", arn=arn, error=str(e))
    except Exception as e:
        logger.exception("aws_sm_unexpected_error", arn=arn, error=str(e))
    return {}


def _resolve_from_prefect(block_name: str) -> dict[str, Any]:
    """Resolve credentials from a Prefect Secret block."""
    try:
        from prefect.blocks.system import Secret

        secret = Secret.load(block_name.replace("prefect://", ""))
        value = secret.get()
        if isinstance(value, str):
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return {"secret_value": value}
        return value if isinstance(value, dict) else {}
    except ImportError:
        logger.warning("prefect_not_installed", block=block_name)
    except Exception as e:
        logger.exception("prefect_resolve_failed", block=block_name, error=str(e))
    return {}


def _resolve_from_toml(key_path: str | None = None) -> dict[str, Any]:
    """Resolve credentials from .dlt/secrets.toml."""
    try:
        if os.path.exists(DLT_SECRETS_PATH):
            # Python 3.11+ has tomllib; fall back to tomli
            try:
                import tomllib
            except ImportError:
                import tomli as tomllib
            with open(DLT_SECRETS_PATH, "rb") as f:
                secrets = tomllib.load(f)
            if key_path:
                parts = key_path.split(".")
                result = secrets
                for part in parts:
                    result = result.get(part, {})
                return result if isinstance(result, dict) else {}
            return secrets.get("destination", secrets)
    except Exception as e:
        logger.debug("toml_resolve_skipped", path=DLT_SECRETS_PATH, error=str(e))
    return {}
