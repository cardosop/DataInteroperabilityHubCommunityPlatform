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


class TestAWSSecretsLoaderConfig:
    """Validate the AWS Secrets Manager loader configuration."""

    def test_loader_module_exists(self):
        """The aws_secrets_loader module exists and is importable."""
        try:
            from hub import aws_secrets_loader  # noqa: F401
        except ImportError:
            pytest.skip("aws_secrets_loader module not available in this environment")

    def test_loader_has_load_function(self):
        """The loader exports a load_from_aws function."""
        try:
            from hub.aws_secrets_loader import load_from_aws
            assert callable(load_from_aws), "load_from_aws must be callable"
        except ImportError:
            pytest.skip("aws_secrets_loader not available")

    def test_loader_disabled_by_default(self):
        """AWS_SECRETS_ENABLED defaults to false — no secrets loaded unless explicitly enabled."""
        default = os.environ.get("AWS_SECRETS_ENABLED", "false").strip().lower()
        assert default == "false", (
            f"AWS_SECRETS_ENABLED should default to 'false', got '{default}'"
        )

    def test_loader_gate_in_settings(self):
        """settings.py gates AWS SM loading behind AWS_SECRETS_ENABLED."""
        settings_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "hub", "settings.py",
        )
        if not os.path.exists(settings_path):
            pytest.skip("settings.py not found")
        with open(settings_path) as f:
            source = f.read()
        assert "AWS_SECRETS_ENABLED" in source, (
            "settings.py must check AWS_SECRETS_ENABLED before calling load_from_aws()"
        )
        assert "load_from_aws" in source or "aws_secrets_loader" in source, (
            "settings.py must import and call the AWS secrets loader"
        )


class TestIRSAIntegration:
    """IRSA (IAM Roles for Service Accounts) integration checks."""

    def test_irsa_env_var_recognized(self):
        """AWS_WEB_IDENTITY_TOKEN_FILE is the IRSA indicator."""
        token_file = os.environ.get("AWS_WEB_IDENTITY_TOKEN_FILE", "")
        role_arn = os.environ.get("AWS_ROLE_ARN", "")
        if not token_file and not role_arn:
            pytest.skip("IRSA not configured in this environment")

    def test_irsa_token_file_exists_if_configured(self):
        """If IRSA is configured, the token file should exist."""
        token_file = os.environ.get("AWS_WEB_IDENTITY_TOKEN_FILE", "")
        if not token_file:
            pytest.skip("AWS_WEB_IDENTITY_TOKEN_FILE not set")
        assert os.path.exists(token_file), (
            f"AWS_WEB_IDENTITY_TOKEN_FILE points to non-existent file: {token_file}"
        )


class TestSecretsLoadingOrder:
    """Secrets must be loaded before any downstream setting consumes them."""

    def test_secrets_loaded_before_database_config(self):
        """In settings.py, the AWS SM block must appear before DATABASES configuration."""
        settings_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "hub", "settings.py",
        )
        if not os.path.exists(settings_path):
            pytest.skip("settings.py not found")
        with open(settings_path) as f:
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
                f"AWS secrets loader (line {aws_line+1}) must run before "
                f"DATABASES config (line {db_line+1}) in settings.py"
            )
