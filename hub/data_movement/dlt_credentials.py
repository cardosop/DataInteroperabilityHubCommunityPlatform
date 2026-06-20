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
        logger.error("aws_sm_resolve_failed", arn=arn, error=str(e))
    except Exception as e:
        logger.error("aws_sm_unexpected_error", arn=arn, error=str(e))
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
        logger.error("prefect_resolve_failed", block=block_name, error=str(e))
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
