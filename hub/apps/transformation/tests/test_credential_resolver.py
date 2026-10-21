"""
285.9.1.1.2 — Tests for credential_resolver.py.

Tests resolve_warehouse_credentials() and resolve_git_credentials() using
moto's mock_aws for AWS Secrets Manager (no real AWS calls).
"""

import json
import uuid

import pytest
from moto import mock_aws

# ── Constants ─────────────────────────────────────────────────────────

_TEST_REGION = "us-east-1"
_TEST_AWS_ACCOUNT = "123456789012"
_TEST_PROFILE_NAME = "meshant_dbt"


def _create_secret(client, name: str, value: dict) -> str:
    """Create a secret in moto and return its ARN."""
    response = client.create_secret(
        Name=name,
        SecretString=json.dumps(value),
    )
    return response["ARN"]


@pytest.fixture(autouse=True)
def _aws_env(monkeypatch):
    """Ensure AWS env vars are set for all tests."""
    monkeypatch.setenv("AWS_REGION", _TEST_REGION)
    monkeypatch.setenv("AWS_DEFAULT_REGION", _TEST_REGION)
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_SECURITY_TOKEN", "testing")
    monkeypatch.setenv("AWS_SESSION_TOKEN", "testing")


# ── resolve_warehouse_credentials tests ────────────────────────────────


@pytest.mark.unit
class TestResolveWarehouseCredentials:
    """Tests for resolve_warehouse_credentials()."""

    @pytest.mark.unit
    def test_snowflake_credentials(self):
        """Given Snowflake secret in AWS SM, returns dbt Snowflake profile dict."""
        with mock_aws():
            import boto3

            client = boto3.client("secretsmanager", region_name=_TEST_REGION)
            secret_value = {
                "type": "snowflake",
                "account": "abc123.us-east-1",
                "user": "dbt_user",
                "password": "s3cret!",
                "role": "transform_role",
                "database": "analytics",
                "warehouse": "compute_wh",
                "schema": "dbt_schema",
            }
            arn = _create_secret(client, f"wh-snowflake-{uuid.uuid4().hex[:8]}", secret_value)

            from hub.apps.transformation.credential_resolver import (
                resolve_warehouse_credentials,
            )

            profile = resolve_warehouse_credentials(arn)

        assert _TEST_PROFILE_NAME in profile
        outputs = profile[_TEST_PROFILE_NAME]["outputs"]
        assert "prod" in outputs
        out = outputs["prod"]
        assert out["type"] == "snowflake"
        assert out["account"] == "abc123.us-east-1"
        assert out["user"] == "dbt_user"
        assert out["password"] == "s3cret!"
        assert out["role"] == "transform_role"
        assert out["database"] == "analytics"
        assert out["warehouse"] == "compute_wh"
        assert out["schema"] == "dbt_schema"

    @pytest.mark.unit
    def test_bigquery_credentials(self):
        """Given BigQuery secret, returns dbt BigQuery profile dict."""
        with mock_aws():
            import boto3

            client = boto3.client("secretsmanager", region_name=_TEST_REGION)
            keyfile = {
                "private_key": "test-key",
                "client_email": "dbt@project.iam.gserviceaccount.com",
            }
            secret_value = {
                "type": "bigquery",
                "method": "service-account",
                "project": "my-gcp-project",
                "dataset": "analytics",
                "keyfile": keyfile,
            }
            arn = _create_secret(client, f"wh-bq-{uuid.uuid4().hex[:8]}", secret_value)

            from hub.apps.transformation.credential_resolver import (
                resolve_warehouse_credentials,
            )

            profile = resolve_warehouse_credentials(arn)

        out = profile[_TEST_PROFILE_NAME]["outputs"]["prod"]
        assert out["type"] == "bigquery"
        assert out["method"] == "service-account"
        assert out["project"] == "my-gcp-project"
        assert out["dataset"] == "analytics"
        # Inline dict → keyfile_json (not keyfile which is for paths)
        assert out["keyfile_json"] == keyfile

    @pytest.mark.unit
    def test_bigquery_oauth_method(self):
        """BigQuery with oauth-secrets method passes through correctly."""
        with mock_aws():
            import boto3

            client = boto3.client("secretsmanager", region_name=_TEST_REGION)
            secret_value = {
                "type": "bigquery",
                "method": "oauth-secrets",
                "project": "my-oauth-project",
                "dataset": "oauth_ds",
                "keyfile": {
                    "client_id": "oauth-client-id",
                    "client_secret": "oauth-secret",
                    "refresh_token": "refresh-token-value",
                },
            }
            arn = _create_secret(client, f"wh-bq-oauth-{uuid.uuid4().hex[:8]}", secret_value)

            from hub.apps.transformation.credential_resolver import (
                resolve_warehouse_credentials,
            )

            profile = resolve_warehouse_credentials(arn)

        out = profile[_TEST_PROFILE_NAME]["outputs"]["prod"]
        assert out["type"] == "bigquery"
        assert out["method"] == "oauth-secrets"
        assert "keyfile_json" in out

    @pytest.mark.unit
    def test_bigquery_path_keyfile(self):
        """BigQuery keyfile as string (file path) stays under 'keyfile' key."""
        with mock_aws():
            import boto3

            client = boto3.client("secretsmanager", region_name=_TEST_REGION)
            secret_value = {
                "type": "bigquery",
                "method": "service-account",
                "project": "path-project",
                "dataset": "path_ds",
                "keyfile": "/etc/meshant/gcp-sa.json",
            }
            arn = _create_secret(client, f"wh-bq-path-{uuid.uuid4().hex[:8]}", secret_value)

            from hub.apps.transformation.credential_resolver import (
                resolve_warehouse_credentials,
            )

            profile = resolve_warehouse_credentials(arn)

        out = profile[_TEST_PROFILE_NAME]["outputs"]["prod"]
        # String keyfile → stays as "keyfile" (file path), not "keyfile_json"
        assert out["keyfile"] == "/etc/meshant/gcp-sa.json"
        assert "keyfile_json" not in out

    @pytest.mark.unit
    def test_databricks_credentials(self):
        """Given Databricks secret, returns dbt Databricks profile dict."""
        with mock_aws():
            import boto3

            client = boto3.client("secretsmanager", region_name=_TEST_REGION)
            secret_value = {
                "type": "databricks",
                "host": "dbc-123.cloud.databricks.com",
                "http_path": "/sql/1.0/warehouses/abc123",
                "token": "dapi-secret-token",
                "catalog": "main",
                "schema": "dbt_schema",
            }
            arn = _create_secret(client, f"wh-dbr-{uuid.uuid4().hex[:8]}", secret_value)

            from hub.apps.transformation.credential_resolver import (
                resolve_warehouse_credentials,
            )

            profile = resolve_warehouse_credentials(arn)

        out = profile[_TEST_PROFILE_NAME]["outputs"]["prod"]
        assert out["type"] == "databricks"
        assert out["host"] == "dbc-123.cloud.databricks.com"
        assert out["http_path"] == "/sql/1.0/warehouses/abc123"
        assert out["token"] == "dapi-secret-token"
        assert out["catalog"] == "main"
        assert out["schema"] == "dbt_schema"

    @pytest.mark.unit
    def test_snowflake_with_optional_fields_defaults(self):
        """Snowflake secret missing optional fields gets sensible defaults."""
        with mock_aws():
            import boto3

            client = boto3.client("secretsmanager", region_name=_TEST_REGION)
            # Only required fields
            secret_value = {
                "type": "snowflake",
                "account": "min.account",
                "user": "min_user",
                "password": "min_pass",
            }
            arn = _create_secret(client, f"wh-min-{uuid.uuid4().hex[:8]}", secret_value)

            from hub.apps.transformation.credential_resolver import (
                resolve_warehouse_credentials,
            )

            profile = resolve_warehouse_credentials(arn)

        out = profile[_TEST_PROFILE_NAME]["outputs"]["prod"]
        assert out["type"] == "snowflake"
        # Optional fields get defaults
        assert out["database"] == "analytics"
        assert out["schema"] == "public"

    @pytest.mark.unit
    def test_missing_type_field_raises(self):
        """Secret without 'type' field raises CredentialResolverError."""
        with mock_aws():
            import boto3

            client = boto3.client("secretsmanager", region_name=_TEST_REGION)
            arn = _create_secret(
                client,
                f"wh-bad-{uuid.uuid4().hex[:8]}",
                {
                    "user": "someone",
                    "password": "secret",
                },
            )

            from hub.apps.transformation.credential_resolver import (
                CredentialResolverError,
                resolve_warehouse_credentials,
            )

            with pytest.raises(CredentialResolverError, match="type"):
                resolve_warehouse_credentials(arn)

    @pytest.mark.unit
    def test_missing_required_field_snowflake(self):
        """Snowflake missing 'password' raises with field name."""
        with mock_aws():
            import boto3

            client = boto3.client("secretsmanager", region_name=_TEST_REGION)
            arn = _create_secret(
                client,
                f"wh-no-pass-{uuid.uuid4().hex[:8]}",
                {
                    "type": "snowflake",
                    "account": "acct",
                    "user": "u",
                    # password missing
                },
            )

            from hub.apps.transformation.credential_resolver import (
                CredentialResolverError,
                resolve_warehouse_credentials,
            )

            with pytest.raises(CredentialResolverError, match="Missing required field 'password'"):
                resolve_warehouse_credentials(arn)

    @pytest.mark.unit
    def test_missing_required_field_bigquery(self):
        """BigQuery missing 'project' raises with field name."""
        with mock_aws():
            import boto3

            client = boto3.client("secretsmanager", region_name=_TEST_REGION)
            arn = _create_secret(
                client,
                f"wh-no-proj-{uuid.uuid4().hex[:8]}",
                {
                    "type": "bigquery",
                    "dataset": "ds",
                    "keyfile": {"k": "v"},
                },
            )

            from hub.apps.transformation.credential_resolver import (
                CredentialResolverError,
                resolve_warehouse_credentials,
            )

            with pytest.raises(CredentialResolverError, match="Missing required field 'project'"):
                resolve_warehouse_credentials(arn)

    @pytest.mark.unit
    def test_missing_required_field_databricks(self):
        """Databricks missing 'host' raises with field name."""
        with mock_aws():
            import boto3

            client = boto3.client("secretsmanager", region_name=_TEST_REGION)
            arn = _create_secret(
                client,
                f"wh-no-host-{uuid.uuid4().hex[:8]}",
                {
                    "type": "databricks",
                    "http_path": "/path",
                    "token": "tok",
                },
            )

            from hub.apps.transformation.credential_resolver import (
                CredentialResolverError,
                resolve_warehouse_credentials,
            )

            with pytest.raises(CredentialResolverError, match="Missing required field 'host'"):
                resolve_warehouse_credentials(arn)

    @pytest.mark.unit
    def test_unsupported_warehouse_type_raises(self):
        """Unknown warehouse type raises CredentialResolverError."""
        with mock_aws():
            import boto3

            client = boto3.client("secretsmanager", region_name=_TEST_REGION)
            arn = _create_secret(
                client,
                f"wh-unsup-{uuid.uuid4().hex[:8]}",
                {
                    "type": "redshift",
                    "host": "localhost",
                },
            )

            from hub.apps.transformation.credential_resolver import (
                CredentialResolverError,
                resolve_warehouse_credentials,
            )

            with pytest.raises(CredentialResolverError, match="Unsupported warehouse type"):
                resolve_warehouse_credentials(arn)

    @pytest.mark.unit
    def test_custom_profile_name(self):
        """Custom profile_name param is used as the key in the output dict."""
        with mock_aws():
            import boto3

            client = boto3.client("secretsmanager", region_name=_TEST_REGION)
            secret_value = {
                "type": "snowflake",
                "account": "custom.acct",
                "user": "custom_user",
                "password": "custom_pass",
            }
            arn = _create_secret(client, f"wh-custom-{uuid.uuid4().hex[:8]}", secret_value)

            from hub.apps.transformation.credential_resolver import (
                resolve_warehouse_credentials,
            )

            custom_name = "meshant_mytenant_pipe123"
            profile = resolve_warehouse_credentials(arn, profile_name=custom_name)

        assert custom_name in profile
        assert profile[custom_name]["target"] == "prod"
        assert profile[custom_name]["outputs"]["prod"]["type"] == "snowflake"
        # Default profile name is NOT present
        assert _TEST_PROFILE_NAME not in profile

    @pytest.mark.unit
    def test_arn_not_found_raises(self):
        """Non-existent ARN raises CredentialResolverError."""
        with mock_aws():
            from hub.apps.transformation.credential_resolver import (
                CredentialResolverError,
                resolve_warehouse_credentials,
            )

            with pytest.raises(CredentialResolverError, match="not found"):
                resolve_warehouse_credentials(
                    f"arn:aws:secretsmanager:{_TEST_REGION}:{_TEST_AWS_ACCOUNT}:secret:nonexistent-abc"
                )

    @pytest.mark.unit
    def test_no_caching_fetches_fresh_each_call(self):
        """Each call fetches from AWS SM — no caching of previous result."""
        with mock_aws():
            import boto3

            client = boto3.client("secretsmanager", region_name=_TEST_REGION)
            secret_name = f"wh-rotated-{uuid.uuid4().hex[:8]}"

            # Create initial secret
            initial_value = {
                "type": "snowflake",
                "account": "original",
                "user": "orig_user",
                "password": "orig_pass",
            }
            arn = _create_secret(client, secret_name, initial_value)

            from hub.apps.transformation.credential_resolver import (
                resolve_warehouse_credentials,
            )

            # First call — gets original
            profile1 = resolve_warehouse_credentials(arn)
            assert profile1[_TEST_PROFILE_NAME]["outputs"]["prod"]["account"] == "original"

            # Update the secret in place (simulates credential rotation)
            rotated_value = {
                "type": "snowflake",
                "account": "rotated",
                "user": "new_user",
                "password": "new_pass",
            }
            client.put_secret_value(
                SecretId=arn,
                SecretString=json.dumps(rotated_value),
            )

            # Second call — gets rotated value (proves no caching)
            profile2 = resolve_warehouse_credentials(arn)
            assert profile2[_TEST_PROFILE_NAME]["outputs"]["prod"]["account"] == "rotated"

    @pytest.mark.unit
    def test_invalid_json_secret_raises(self):
        """Non-JSON secret value raises CredentialResolverError."""
        with mock_aws():
            import boto3

            client = boto3.client("secretsmanager", region_name=_TEST_REGION)
            response = client.create_secret(
                Name=f"wh-invalid-json-{uuid.uuid4().hex[:8]}",
                SecretString="not-valid-json{{{",
            )
            arn = response["ARN"]

            from hub.apps.transformation.credential_resolver import (
                CredentialResolverError,
                resolve_warehouse_credentials,
            )

            with pytest.raises(CredentialResolverError, match="Invalid JSON"):
                resolve_warehouse_credentials(arn)


# ── resolve_git_credentials tests ─────────────────────────────────────


@pytest.mark.unit
class TestResolveGitCredentials:
    """Tests for resolve_git_credentials()."""

    @pytest.mark.unit
    def test_github_pat_credentials(self):
        """Given git PAT secret, returns dict with token for git clone."""
        with mock_aws():
            import boto3

            client = boto3.client("secretsmanager", region_name=_TEST_REGION)
            secret_value = {
                "provider": "github",
                "token": "ghp_test1234567890",
                "username": "meshant-bot",
            }
            arn = _create_secret(client, f"git-gh-{uuid.uuid4().hex[:8]}", secret_value)

            from hub.apps.transformation.credential_resolver import (
                resolve_git_credentials,
            )

            creds = resolve_git_credentials(arn)

        assert creds["token"] == "ghp_test1234567890"
        assert creds["username"] == "meshant-bot"

    @pytest.mark.unit
    def test_gitlab_pat_credentials(self):
        """GitLab PAT returns correct token format."""
        with mock_aws():
            import boto3

            client = boto3.client("secretsmanager", region_name=_TEST_REGION)
            secret_value = {
                "provider": "gitlab",
                "token": "glpat-test-token-value",
            }
            arn = _create_secret(client, f"git-gl-{uuid.uuid4().hex[:8]}", secret_value)

            from hub.apps.transformation.credential_resolver import (
                resolve_git_credentials,
            )

            creds = resolve_git_credentials(arn)

        assert creds["token"] == "glpat-test-token-value"
        # username defaults to "oauth2" for GitLab
        assert creds["username"] == "oauth2"

    @pytest.mark.unit
    def test_missing_token_field_raises(self):
        """Git secret without 'token' raises CredentialResolverError."""
        with mock_aws():
            import boto3

            client = boto3.client("secretsmanager", region_name=_TEST_REGION)
            arn = _create_secret(
                client,
                f"git-notok-{uuid.uuid4().hex[:8]}",
                {
                    "provider": "github",
                    "username": "someone",
                },
            )

            from hub.apps.transformation.credential_resolver import (
                CredentialResolverError,
                resolve_git_credentials,
            )

            with pytest.raises(CredentialResolverError, match="token"):
                resolve_git_credentials(arn)

    @pytest.mark.unit
    def test_arn_not_found_raises(self):
        """Non-existent ARN raises CredentialResolverError for git too."""
        with mock_aws():
            from hub.apps.transformation.credential_resolver import (
                CredentialResolverError,
                resolve_git_credentials,
            )

            with pytest.raises(CredentialResolverError, match="not found"):
                resolve_git_credentials(
                    f"arn:aws:secretsmanager:{_TEST_REGION}:{_TEST_AWS_ACCOUNT}:secret:git-nonexistent"
                )

    @pytest.mark.unit
    def test_no_caching_fetches_fresh(self):
        """Git credential resolution also avoids caching."""
        with mock_aws():
            import boto3

            client = boto3.client("secretsmanager", region_name=_TEST_REGION)
            secret_name = f"git-rotated-{uuid.uuid4().hex[:8]}"
            arn = _create_secret(client, secret_name, {"token": "original-token"})

            from hub.apps.transformation.credential_resolver import (
                resolve_git_credentials,
            )

            creds1 = resolve_git_credentials(arn)
            assert creds1["token"] == "original-token"

            client.put_secret_value(
                SecretId=arn,
                SecretString=json.dumps({"token": "rotated-token"}),
            )
            creds2 = resolve_git_credentials(arn)
            assert creds2["token"] == "rotated-token"

    @pytest.mark.unit
    def test_access_denied_raises_fast(self):
        """AccessDenied from AWS SM raises immediately (fail-fast for rotated creds)."""
        with mock_aws():
            from unittest.mock import patch

            import boto3
            from botocore.exceptions import ClientError

            # We need to simulate an AccessDenied error — moto doesn't
            # simulate permission errors natively, so we patch the client.
            client = boto3.client("secretsmanager", region_name=_TEST_REGION)
            arn = _create_secret(client, f"git-auth-{uuid.uuid4().hex[:8]}", {"token": "test"})

            def _raise_access_denied(*args, **kwargs):
                raise ClientError(
                    {"Error": {"Code": "AccessDeniedException", "Message": "Access denied"}},
                    "GetSecretValue",
                )

            with patch.object(client, "get_secret_value", side_effect=_raise_access_denied):
                from hub.apps.transformation.credential_resolver import (
                    CredentialResolverError,
                    resolve_git_credentials,
                )

                with (
                    patch(
                        "hub.apps.transformation.credential_resolver._build_client",
                        return_value=client,
                    ),
                    pytest.raises(CredentialResolverError, match="Access denied"),
                ):
                    resolve_git_credentials(arn)
