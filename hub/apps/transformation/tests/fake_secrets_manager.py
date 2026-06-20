"""
285.9.1.5.5 — FakeSecretsManager for deterministic testing.

Returns pre-configured warehouse and git credentials without calling
AWS Secrets Manager.  Designed for integration tests that exercise the
credential resolver → executor pipeline.
"""

from __future__ import annotations

from typing import Any


class FakeSecretsManager:
    """Deterministic replacement for AWS Secrets Manager credential
    resolution in tests.

    Pre-configured secrets are returned by ARN lookup.  Unknown ARNs
    raise ``KeyError`` (callers can catch and assert on the error
    path).

    Example::

        fake = FakeSecretsManager(
            warehouse={
                "type": "snowflake",
                "account": "test_account",
                "user": "test_user",
                "password": "test_pass",
            },
            git={"token": "ghp_test123", "username": "meshant-bot"},
        )
        wh = fake.resolve_warehouse_credentials("arn:aws:...")
        assert wh["meshant_dbt"]["outputs"]["prod"]["type"] == "snowflake"
    """

    # Canonical ARN prefixes so tests can use realistic-looking refs.
    WH_ARN = "arn:aws:secretsmanager:us-east-1:123456789012:secret:wh-test"
    GIT_ARN = "arn:aws:secretsmanager:us-east-1:123456789012:secret:git-test"

    # Sensible Snowflake test defaults.
    _DEFAULT_WAREHOUSE: dict[str, Any] = {
        "type": "snowflake",
        "account": "test_account.us-east-1",
        "user": "dbt_test_user",
        "password": "test_password_123",
        "role": "transform",
        "database": "analytics_test",
        "warehouse": "compute_wh",
        "schema": "public",
    }

    _DEFAULT_GIT: dict[str, str] = {
        "provider": "github",
        "token": "ghp_fake_test_token_12345",
        "username": "meshant-bot",
    }

    def __init__(
        self,
        warehouse: dict[str, Any] | None = None,
        git: dict[str, str] | None = None,
    ):
        """
        Args:
            warehouse: dict to return for ``WH_ARN``.  ``None`` → Snowflake
                defaults.
            git: dict to return for ``GIT_ARN``.  ``None`` → GitHub PAT
                defaults.
        """
        self._secrets: dict[str, dict[str, Any]] = {
            self.WH_ARN: dict(warehouse or self._DEFAULT_WAREHOUSE),
            self.GIT_ARN: dict(git or self._DEFAULT_GIT),
        }

    # ── Public API (mirrors credential_resolver) ─────────────────────

    def resolve_warehouse_credentials(
        self, credential_ref: str, profile_name: str = "meshant_dbt"
    ) -> dict[str, Any]:
        """Return a dbt profiles.yml dict for the given ARN."""
        # Patch _fetch_secret to return our pre-configured value
        import hub.apps.transformation.credential_resolver as cr
        from hub.apps.transformation.credential_resolver import (
            resolve_warehouse_credentials,
        )

        original = cr._fetch_secret
        cr._fetch_secret = lambda arn: dict(self._get(arn))
        try:
            return resolve_warehouse_credentials(credential_ref, profile_name=profile_name)
        finally:
            cr._fetch_secret = original

    def resolve_git_credentials(self, credential_ref: str) -> dict[str, str]:
        """Return a git credential dict for the given ARN."""
        import hub.apps.transformation.credential_resolver as cr
        from hub.apps.transformation.credential_resolver import (
            resolve_git_credentials,
        )

        original = cr._fetch_secret
        cr._fetch_secret = lambda arn: dict(self._get(arn))
        try:
            return resolve_git_credentials(credential_ref)
        finally:
            cr._fetch_secret = original

    # ── Direct access (for tests that want raw secrets) ──────────────

    def get_warehouse_secret(self, arn: str | None = None) -> dict[str, Any]:
        """Return the raw warehouse secret dict (no profile wrapper)."""
        return dict(self._get(arn or self.WH_ARN))

    def get_git_secret(self, arn: str | None = None) -> dict[str, str]:
        """Return the raw git secret dict."""
        return dict(self._get(arn or self.GIT_ARN))

    def set_secret(self, arn: str, value: dict[str, Any]) -> None:
        """Add or override a secret."""
        self._secrets[arn] = dict(value)

    # ── Internal ────────────────────────────────────────────────────

    def _get(self, arn: str) -> dict[str, Any]:
        if arn not in self._secrets:
            raise KeyError(f"FakeSecretsManager: unknown ARN '{arn}'")
        return self._secrets[arn]
