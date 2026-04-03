"""
hub/aws_secrets_loader.py
=========================
AWS Secrets Manager secret loader for the DataInteroperabilityHub Django application.

Replaces ``hub/vault_loader.py`` (Phase 211: Vault → AWS Secrets Manager migration).

Responsibilities
----------------
* Read all required secrets from AWS Secrets Manager.
* Inject secrets into ``os.environ`` so Django settings can consume them.
* Retry on transient errors: 3 attempts, exponential back-off 1 s / 2 s / 4 s.
  Raises ``RuntimeError`` when all attempts fail or on non-retryable errors.

Invocation
----------
Called from ``hub/settings.py`` *before* any secret consumption::

    _AWS_SECRETS_ENABLED = os.environ.get("AWS_SECRETS_ENABLED", "false").strip().lower() == "true"
    if _AWS_SECRETS_ENABLED:
        from hub.aws_secrets_loader import load_from_aws
        load_from_aws()

Environment variables consumed
-------------------------------
AWS_REGION              — AWS region (default: us-east-1)
AWS_SECRETS_PREFIX      — Secret name prefix (default: hub/staging)

Authentication uses the standard boto3 credential chain:
  - IRSA (in EKS pods via projected ServiceAccount token)
  - IAM instance profile (EC2)
  - AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY (local dev, CI/CD)
  - AWS_PROFILE (local dev)
"""

from __future__ import annotations

import json
import logging
import os
import time
from typing import Any

import boto3
from botocore.exceptions import (
    ClientError,
    EndpointConnectionError,
    NoCredentialsError,
    NoRegionError,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Secret paths — relative to AWS_SECRETS_PREFIX
# Convention: prefix/subsystem  e.g. hub/staging/django
# Each secret is a JSON object with key-value pairs that become env vars.
# ---------------------------------------------------------------------------
_SECRET_SUBSYSTEMS: list[tuple[str, str]] = [
    ("django",   "Django core secrets"),
    ("redis",    "Redis credentials"),
    ("s3",       "S3/MinIO credentials"),
    ("postgres", "PostgreSQL credentials"),
    ("pgbouncer", "PgBouncer credentials"),
    ("fuseki",   "Fuseki credentials"),
    ("workers",  "Worker API keys"),
    ("api",      "API internal keys"),
    ("email",    "Email provider credentials"),
    ("stripe",   "Stripe payment keys"),
    ("ckan",     "CKAN integration keys"),
]

# Retry configuration
_RETRY_ATTEMPTS = 3
_RETRY_BASE_DELAY_SECONDS = 1  # delays: 1 s, 2 s, 4 s

# ---------------------------------------------------------------------------
# Exception classification
# ---------------------------------------------------------------------------
_TRANSIENT_EXCEPTIONS = (
    EndpointConnectionError,
    ConnectionError,
    TimeoutError,
    OSError,
)

_NON_RETRYABLE_EXCEPTIONS = (
    NoCredentialsError,
    NoRegionError,
)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _build_client():
    """Construct a boto3 Secrets Manager client from environment."""
    region = os.environ.get("AWS_REGION", "us-east-1").strip()
    if not region:
        raise RuntimeError(
            "AWS_REGION is not set — cannot connect to AWS Secrets Manager."
        )
    return boto3.client("secretsmanager", region_name=region)


def _read_secret(client, secret_name: str) -> dict[str, Any]:
    """
    Read a single secret from AWS Secrets Manager.

    Parameters
    ----------
    client : boto3 Secrets Manager client
    secret_name : str
        Full secret name, e.g. ``hub/staging/django``

    Returns
    -------
    dict[str, Any]
        Parsed JSON object from the secret value.
    """
    response = client.get_secret_value(SecretId=secret_name)
    secret_string = response.get("SecretString")
    if not secret_string:
        raise RuntimeError(
            f"Secret '{secret_name}' has no SecretString (binary secrets not supported)."
        )
    return json.loads(secret_string)


def _inject_secrets(secrets: dict[str, str]) -> None:
    """Inject a flat dict of secrets into ``os.environ``."""
    for key, value in secrets.items():
        os.environ[key] = str(value)


def _do_load() -> None:
    """Core load logic (called inside the retry wrapper)."""
    client = _build_client()
    prefix = os.environ.get("AWS_SECRETS_PREFIX", "hub/staging").strip()

    # Collect ALL secrets into a single dict before injecting to guarantee
    # atomicity: either all secrets are injected or none are.
    merged: dict[str, str] = {}

    for subsystem, description in _SECRET_SUBSYSTEMS:
        secret_name = f"{prefix}/{subsystem}"
        logger.debug("Reading AWS SM secret", extra={"secret_name": secret_name})
        try:
            data = _read_secret(client, secret_name)
            merged.update({k: str(v) for k, v in data.items()})
        except ClientError as exc:
            error_code = exc.response["Error"]["Code"]
            if error_code == "ResourceNotFoundException":
                # Optional secrets (stripe, ckan) may not exist — skip
                logger.debug(
                    "Secret not found (optional), skipping",
                    extra={"secret_name": secret_name, "description": description},
                )
                continue
            raise

    _inject_secrets(merged)
    logger.info(
        "AWS Secrets Manager secrets loaded successfully",
        extra={"num_keys": len(merged)},
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def load_from_aws() -> None:
    """
    Load all application secrets from AWS Secrets Manager and inject into ``os.environ``.

    Retry policy
    ------------
    * Transient errors (network, endpoint connection): retry up to
      ``_RETRY_ATTEMPTS`` times with exponential back-off (1 s, 2 s, 4 s).
    * Non-retryable errors (no credentials, no region, AccessDenied): raise immediately.
    * After exhausting all retries: raise ``RuntimeError``.

    Idempotent — safe to call multiple times; later calls overwrite earlier values.
    """
    last_exc: Exception | None = None

    for attempt in range(1, _RETRY_ATTEMPTS + 1):
        try:
            _do_load()
            return  # Success

        except _NON_RETRYABLE_EXCEPTIONS as exc:
            logger.error("AWS SM load failed (non-retryable): %s", exc)
            raise RuntimeError(
                f"Failed to load secrets from AWS Secrets Manager (non-retryable): {exc}"
            ) from exc

        except ClientError as exc:
            error_code = exc.response["Error"]["Code"]
            if error_code in ("AccessDeniedException", "UnrecognizedClientException"):
                logger.error("AWS SM load failed (auth error): %s", exc)
                raise RuntimeError(
                    f"Failed to load secrets from AWS Secrets Manager (auth): {exc}"
                ) from exc
            # Other ClientErrors (throttling, internal error) — treat as transient
            last_exc = exc
            if attempt < _RETRY_ATTEMPTS:
                delay = _RETRY_BASE_DELAY_SECONDS * (2 ** (attempt - 1))
                logger.warning(
                    "AWS SM load attempt %d/%d failed: %s. Retrying in %d s ...",
                    attempt, _RETRY_ATTEMPTS, exc, delay,
                )
                time.sleep(delay)

        except RuntimeError:
            raise

        except _TRANSIENT_EXCEPTIONS as exc:
            last_exc = exc
            if attempt < _RETRY_ATTEMPTS:
                delay = _RETRY_BASE_DELAY_SECONDS * (2 ** (attempt - 1))
                logger.warning(
                    "AWS SM load attempt %d/%d failed (transient): %s. Retrying in %d s ...",
                    attempt, _RETRY_ATTEMPTS, exc, delay,
                )
                time.sleep(delay)
            else:
                logger.error(
                    "AWS SM load failed after %d attempts: %s",
                    _RETRY_ATTEMPTS, exc,
                )

        except Exception as exc:
            last_exc = exc
            if attempt < _RETRY_ATTEMPTS:
                delay = _RETRY_BASE_DELAY_SECONDS * (2 ** (attempt - 1))
                logger.warning(
                    "AWS SM load attempt %d/%d failed (unexpected): %s. Retrying in %d s ...",
                    attempt, _RETRY_ATTEMPTS, exc, delay,
                )
                time.sleep(delay)
            else:
                logger.error(
                    "AWS SM load failed after %d attempts (unexpected): %s",
                    _RETRY_ATTEMPTS, exc,
                )

    raise RuntimeError(
        f"Failed to load secrets from AWS Secrets Manager after {_RETRY_ATTEMPTS} attempts. "
        f"Last error: {last_exc}"
    ) from last_exc
