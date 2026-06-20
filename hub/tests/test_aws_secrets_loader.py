"""
hub/tests/test_aws_secrets_loader.py
=====================================
Tests for hub.aws_secrets_loader using moto (AWS mock library).

Strategy
--------
* Use moto's ``mock_aws`` decorator to simulate AWS Secrets Manager.
* Create test secrets in the mock SM, then call ``load_from_aws()`` and
  verify env vars were injected correctly.
* No real AWS credentials or network calls needed.

Run:
    pytest hub/tests/test_aws_secrets_loader.py -v
"""

from __future__ import annotations

import json
import os
from typing import Any

import boto3
import pytest
from moto import mock_aws

# Region used throughout tests
_TEST_REGION = "us-east-1"
_TEST_PREFIX = "hub/test"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _create_secret(client, name: str, data: dict[str, Any]) -> None:
    """Create a secret in the moto mock Secrets Manager."""
    client.create_secret(
        Name=name,
        SecretString=json.dumps(data),
    )


@pytest.fixture()
def sm_client():
    """Yield a moto-mocked Secrets Manager client with test secrets populated."""
    with mock_aws():
        client = boto3.client("secretsmanager", region_name=_TEST_REGION)

        # Django core secrets
        _create_secret(
            client,
            f"{_TEST_PREFIX}/django",
            {
                "SECRET_KEY": "test-secret-key-from-aws",
                "JWT_SECRET_KEY": "test-jwt-secret-from-aws",
                "ENCRYPTION_KEY": "test-encryption-key-from-aws",
            },
        )

        # Redis
        _create_secret(
            client,
            f"{_TEST_PREFIX}/redis",
            {
                "REDIS_CACHE_PASSWORD": "cache-pw",
                "REDIS_QUEUE_PASSWORD": "queue-pw",
                "REDIS_EVENTS_PASSWORD": "events-pw",
                "REDIS_CHANNELS_PASSWORD": "channels-pw",
            },
        )

        # S3/MinIO
        _create_secret(
            client,
            f"{_TEST_PREFIX}/s3",
            {
                "AWS_ACCESS_KEY_ID": "minio-user",
                "AWS_SECRET_ACCESS_KEY": "minio-pass",
            },
        )

        # Postgres
        _create_secret(
            client,
            f"{_TEST_PREFIX}/postgres",
            {
                "POSTGRES_PASSWORD": "pg-pass",
            },
        )

        # PgBouncer
        _create_secret(
            client,
            f"{_TEST_PREFIX}/pgbouncer",
            {
                "PGBOUNCER_ADMIN_PASSWORD": "pgb-pass",
            },
        )

        # Fuseki
        _create_secret(
            client,
            f"{_TEST_PREFIX}/fuseki",
            {
                "FUSEKI_ADMIN_PASSWORD": "fuseki-pass",
            },
        )

        # Workers
        _create_secret(
            client,
            f"{_TEST_PREFIX}/workers",
            {
                "HUB_WORKER_API_KEY": "worker-key",
            },
        )

        # API
        _create_secret(
            client,
            f"{_TEST_PREFIX}/api",
            {
                "INTERNAL_API_KEY": "internal-key",
            },
        )

        # Email
        _create_secret(
            client,
            f"{_TEST_PREFIX}/email",
            {
                "SENDGRID_API_KEY": "sg-test-key",
            },
        )

        # stripe and ckan intentionally NOT created — tests optional secret handling

        yield client


# ---------------------------------------------------------------------------
# Tests: successful loading
# ---------------------------------------------------------------------------


class TestAwsSecretsLoaderSuccess:
    """Tests for successful secret loading from AWS Secrets Manager."""

    def test_load_injects_django_secrets(
        self,
        sm_client,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Django core secrets are injected into os.environ."""
        monkeypatch.setenv("AWS_REGION", _TEST_REGION)
        monkeypatch.setenv("AWS_SECRETS_PREFIX", _TEST_PREFIX)
        for key in ("SECRET_KEY", "JWT_SECRET_KEY", "ENCRYPTION_KEY"):
            monkeypatch.delenv(key, raising=False)

        from hub.aws_secrets_loader import load_from_aws

        load_from_aws()

        assert os.environ["SECRET_KEY"] == "test-secret-key-from-aws"
        assert os.environ["JWT_SECRET_KEY"] == "test-jwt-secret-from-aws"
        assert os.environ["ENCRYPTION_KEY"] == "test-encryption-key-from-aws"

    def test_load_injects_redis_secrets(
        self,
        sm_client,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """All Redis password env vars are injected."""
        monkeypatch.setenv("AWS_REGION", _TEST_REGION)
        monkeypatch.setenv("AWS_SECRETS_PREFIX", _TEST_PREFIX)
        for key in (
            "REDIS_CACHE_PASSWORD",
            "REDIS_QUEUE_PASSWORD",
            "REDIS_EVENTS_PASSWORD",
            "REDIS_CHANNELS_PASSWORD",
        ):
            monkeypatch.delenv(key, raising=False)

        from hub.aws_secrets_loader import load_from_aws

        load_from_aws()

        assert os.environ["REDIS_CACHE_PASSWORD"] == "cache-pw"
        assert os.environ["REDIS_QUEUE_PASSWORD"] == "queue-pw"
        assert os.environ["REDIS_EVENTS_PASSWORD"] == "events-pw"
        assert os.environ["REDIS_CHANNELS_PASSWORD"] == "channels-pw"

    def test_load_injects_s3_secrets(
        self,
        sm_client,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """S3/MinIO credentials are injected."""
        monkeypatch.setenv("AWS_REGION", _TEST_REGION)
        monkeypatch.setenv("AWS_SECRETS_PREFIX", _TEST_PREFIX)
        for key in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY"):
            monkeypatch.delenv(key, raising=False)

        from hub.aws_secrets_loader import load_from_aws

        load_from_aws()

        assert os.environ["AWS_ACCESS_KEY_ID"] == "minio-user"
        assert os.environ["AWS_SECRET_ACCESS_KEY"] == "minio-pass"

    def test_load_injects_all_service_secrets(
        self,
        sm_client,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Postgres, PgBouncer, Fuseki, Workers, API secrets all injected."""
        monkeypatch.setenv("AWS_REGION", _TEST_REGION)
        monkeypatch.setenv("AWS_SECRETS_PREFIX", _TEST_PREFIX)

        from hub.aws_secrets_loader import load_from_aws

        load_from_aws()

        assert os.environ["POSTGRES_PASSWORD"] == "pg-pass"
        assert os.environ["PGBOUNCER_ADMIN_PASSWORD"] == "pgb-pass"
        assert os.environ["FUSEKI_ADMIN_PASSWORD"] == "fuseki-pass"
        assert os.environ["HUB_WORKER_API_KEY"] == "worker-key"
        assert os.environ["INTERNAL_API_KEY"] == "internal-key"

    def test_load_injects_email_secrets(
        self,
        sm_client,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Email credentials are injected."""
        monkeypatch.setenv("AWS_REGION", _TEST_REGION)
        monkeypatch.setenv("AWS_SECRETS_PREFIX", _TEST_PREFIX)
        monkeypatch.delenv("SENDGRID_API_KEY", raising=False)

        from hub.aws_secrets_loader import load_from_aws

        load_from_aws()

        assert os.environ["SENDGRID_API_KEY"] == "sg-test-key"

    def test_optional_secrets_skipped_gracefully(
        self,
        sm_client,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Missing optional secrets (stripe, ckan) don't cause failure."""
        monkeypatch.setenv("AWS_REGION", _TEST_REGION)
        monkeypatch.setenv("AWS_SECRETS_PREFIX", _TEST_PREFIX)
        # Ensure stripe/ckan keys are absent before loading
        monkeypatch.delenv("STRIPE_SECRET_KEY", raising=False)
        monkeypatch.delenv("CKAN_DADOS_GOV_BR_API_KEY", raising=False)

        from hub.aws_secrets_loader import load_from_aws

        # Should not raise even though stripe and ckan secrets don't exist
        load_from_aws()

        # Core secrets still loaded
        assert os.environ["SECRET_KEY"] == "test-secret-key-from-aws"
        # Stripe and ckan keys must NOT be in env (they were never created)
        assert "STRIPE_SECRET_KEY" not in os.environ
        assert "CKAN_DADOS_GOV_BR_API_KEY" not in os.environ

    def test_load_is_idempotent(
        self,
        sm_client,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Calling load_from_aws() twice overwrites with latest values."""
        monkeypatch.setenv("AWS_REGION", _TEST_REGION)
        monkeypatch.setenv("AWS_SECRETS_PREFIX", _TEST_PREFIX)

        from hub.aws_secrets_loader import load_from_aws

        load_from_aws()
        assert os.environ["SECRET_KEY"] == "test-secret-key-from-aws"

        # Manually change the env var to prove 2nd call overwrites it
        monkeypatch.setenv("SECRET_KEY", "tampered-value")
        assert os.environ["SECRET_KEY"] == "tampered-value"

        load_from_aws()  # second call should overwrite
        assert os.environ["SECRET_KEY"] == "test-secret-key-from-aws"


# ---------------------------------------------------------------------------
# Tests: error handling
# ---------------------------------------------------------------------------


class TestAwsSecretsLoaderErrors:
    """Tests for error handling and retry behavior."""

    def test_no_credentials_raises_immediately(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """NoCredentialsError raises RuntimeError without retrying."""
        from botocore.exceptions import NoCredentialsError

        import hub.aws_secrets_loader as loader_mod

        monkeypatch.setenv("AWS_REGION", _TEST_REGION)
        monkeypatch.setenv("AWS_SECRETS_PREFIX", _TEST_PREFIX)

        # Patch _build_client to raise NoCredentialsError directly,
        # rather than relying on real credential chain (which may
        # succeed on machines with AWS credentials configured).
        def _no_creds_client():
            raise NoCredentialsError()

        monkeypatch.setattr(loader_mod, "_build_client", _no_creds_client)

        with pytest.raises(RuntimeError, match="non-retryable"):
            loader_mod.load_from_aws()

    def test_access_denied_raises_immediately(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """AccessDeniedException raises RuntimeError without retrying."""
        from botocore.exceptions import ClientError

        import hub.aws_secrets_loader as loader_mod

        monkeypatch.setenv("AWS_REGION", _TEST_REGION)
        monkeypatch.setenv("AWS_SECRETS_PREFIX", _TEST_PREFIX)

        # Simulate AccessDeniedException from the first get_secret_value call.
        # moto can't simulate IAM denials, so we patch _do_load to raise the
        # specific ClientError that the production code checks for.
        def _access_denied_load():
            raise ClientError(
                {"Error": {"Code": "AccessDeniedException", "Message": "Access denied"}},
                "GetSecretValue",
            )

        monkeypatch.setattr(loader_mod, "_do_load", _access_denied_load)

        with pytest.raises(RuntimeError, match="auth"):
            loader_mod.load_from_aws()

    @mock_aws
    def test_all_secrets_missing_succeeds_with_empty(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """When ALL secrets are missing (empty SM), loader succeeds but injects nothing."""
        monkeypatch.setenv("AWS_REGION", _TEST_REGION)
        monkeypatch.setenv("AWS_SECRETS_PREFIX", "completely/empty/prefix")
        monkeypatch.delenv("SECRET_KEY", raising=False)

        from hub.aws_secrets_loader import load_from_aws

        # Succeeds (all ResourceNotFound → skipped)
        load_from_aws()
        # But SECRET_KEY was never injected — it stays absent
        assert os.environ.get("SECRET_KEY") is None

    @mock_aws
    def test_transient_error_retries_and_raises(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Transient errors retry _RETRY_ATTEMPTS times then raise."""
        import hub.aws_secrets_loader as loader_mod

        sleep_calls: list[float] = []

        class _FakeTime:
            @staticmethod
            def sleep(seconds: float) -> None:
                sleep_calls.append(seconds)

        monkeypatch.setattr(loader_mod, "time", _FakeTime)
        monkeypatch.setenv("AWS_REGION", _TEST_REGION)
        monkeypatch.setenv("AWS_SECRETS_PREFIX", _TEST_PREFIX)

        # Patch _build_client to raise EndpointConnectionError every time
        def _failing_client():
            raise EndpointConnectionError(endpoint_url="https://fake.endpoint.com")

        from botocore.exceptions import EndpointConnectionError

        monkeypatch.setattr(loader_mod, "_build_client", _failing_client)

        with pytest.raises(RuntimeError, match="after 3 attempts"):
            loader_mod.load_from_aws()

        # 3 attempts → 2 sleeps
        assert len(sleep_calls) == loader_mod._RETRY_ATTEMPTS - 1
        assert sleep_calls[0] == 1
        assert sleep_calls[1] == 2


# ---------------------------------------------------------------------------
# Tests: settings.py integration
# ---------------------------------------------------------------------------


class TestSettingsIntegration:
    """Tests that settings.py branching logic matches the env var contract.

    We can't re-import settings.py at runtime (it runs Django setup),
    so we test the actual branching logic by reading settings.py source
    and verifying the conditional structure is correct.
    """

    def test_settings_has_aws_secrets_enabled_check(self) -> None:
        """settings.py checks AWS_SECRETS_ENABLED and imports aws_secrets_loader."""
        import inspect

        from hub import settings as settings_mod

        source = inspect.getsource(settings_mod)
        assert "AWS_SECRETS_ENABLED" in source
        assert "from hub.aws_secrets_loader import load_from_aws" in source

    def test_settings_has_no_vault_references(self) -> None:
        """settings.py no longer references vault_loader (deleted in 210.20l)."""
        import inspect

        from hub import settings as settings_mod

        source = inspect.getsource(settings_mod)
        assert "vault_loader" not in source, (
            "settings.py still references vault_loader — "
            "it was deleted in Phase 211 cleanup (210.20l)"
        )
        assert "VAULT_ENABLED" not in source, (
            "settings.py still references VAULT_ENABLED — vault backward compat removed in 210.20l"
        )
