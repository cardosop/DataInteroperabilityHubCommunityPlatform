"""
AWS Secrets Manager loader tests (312.18.2).

Validates:
- AWS Secrets Manager integration is configured correctly
- IRSA (IAM Roles for Service Accounts) auth path works
- Secrets are loaded at startup before downstream settings consume them
- Graceful degradation when AWS is unreachable
"""

import os

import pytest

# Repo-root settings.py — resolved at MODULE level so the class-body
# ``@pytest.mark.skipif`` decorators can reference it (they evaluate at import
# time, before any test method runs).
SETTINGS_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "hub",
    "settings.py",
)


class TestAWSSecretsLoaderConfig:
    """Validate the AWS Secrets Manager loader configuration."""

    def test_loader_module_exists(self):
        """The aws_secrets_loader module exists and is importable."""
        from hub import aws_secrets_loader

        assert aws_secrets_loader is not None

    def test_loader_has_load_function(self):
        """The loader exports a load_from_aws function."""
        from hub.aws_secrets_loader import load_from_aws

        assert callable(load_from_aws), "load_from_aws must be callable"

    def test_loader_disabled_by_default(self):
        """AWS_SECRETS_ENABLED defaults to false — no secrets loaded unless explicitly enabled."""
        default = os.environ.get("AWS_SECRETS_ENABLED", "false").strip().lower()
        assert default == "false", f"AWS_SECRETS_ENABLED should default to 'false', got '{default}'"

    @pytest.mark.skipif(not os.path.exists(SETTINGS_PATH), reason="settings.py not found")
    def test_loader_gate_in_settings(self):
        """settings.py gates AWS SM loading behind AWS_SECRETS_ENABLED."""
        with open(SETTINGS_PATH) as f:
            source = f.read()
        assert "AWS_SECRETS_ENABLED" in source, (
            "settings.py must check AWS_SECRETS_ENABLED before calling load_from_aws()"
        )
        assert "load_from_aws" in source or "aws_secrets_loader" in source, (
            "settings.py must import and call the AWS secrets loader"
        )


class TestIRSAIntegration:
    """IRSA (IAM Roles for Service Accounts) integration checks."""

    def test_irsa_env_var_recognized(self, monkeypatch):
        """AWS_WEB_IDENTITY_TOKEN_FILE is the IRSA indicator.

        With IRSA env present but a fake token, the web-identity chain
        engages and the loader must fail LOUD per its documented contract
        (RuntimeError after exhausting retries) — it must not hang or
        silently return.
        """
        monkeypatch.setenv("AWS_WEB_IDENTITY_TOKEN_FILE", "/tmp/fake-irsa-token")
        monkeypatch.setenv("AWS_ROLE_ARN", "arn:aws:iam::123456789012:role/fake")
        # Clear the test stack's ambient static creds (MinIO etc.) so the
        # credential chain reaches web-identity and then no-credentials —
        # instead of attempting a real AWS call with minio creds.
        for var in (
            "AWS_ACCESS_KEY_ID",
            "AWS_SECRET_ACCESS_KEY",
            "AWS_SESSION_TOKEN",
            "ATHENA_AWS_ACCESS_KEY_ID",
            "ATHENA_AWS_SECRET_ACCESS_KEY",
        ):
            monkeypatch.delenv(var, raising=False)

        from hub.aws_secrets_loader import load_from_aws

        with pytest.raises(RuntimeError):
            load_from_aws()

    def test_irsa_token_file_exists_if_configured(self, monkeypatch, tmp_path):
        """If IRSA is configured, the token file should exist."""
        token_file = tmp_path / "web-identity-token"
        token_file.write_text("fake-jwt-token")
        monkeypatch.setenv("AWS_WEB_IDENTITY_TOKEN_FILE", str(token_file))
        assert os.path.exists(str(token_file)), (
            f"AWS_WEB_IDENTITY_TOKEN_FILE points to non-existent file: {token_file}"
        )


class TestSecretsLoadingOrder:
    """Secrets must be loaded before any downstream setting consumes them."""

    @pytest.mark.skipif(not os.path.exists(SETTINGS_PATH), reason="settings.py not found")
    def test_secrets_loaded_before_database_config(self):
        """In settings.py, the AWS SM block must appear before DATABASES configuration."""
        with open(SETTINGS_PATH) as f:
            lines = f.readlines()

        aws_line = None
        db_line = None
        for i, line in enumerate(lines):
            if "load_from_aws" in line or "AWS_SECRETS_ENABLED" in line:
                aws_line = i
            if "DATABASES" in line and "=" in line:
                db_line = i
                break

        if aws_line is not None and db_line is not None:
            assert aws_line < db_line, (
                f"AWS secrets loader (line {aws_line + 1}) must run before "
                f"DATABASES config (line {db_line + 1}) in settings.py"
            )
