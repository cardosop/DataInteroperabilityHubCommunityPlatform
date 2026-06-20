"""
Tests for hub.apps.core.config_validation (Phase 10).

No mocks: validation uses real django.conf.settings; tests override settings
via @override_settings to exercise success and failure paths.
"""

from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase, override_settings

from hub.apps.core.config_validation import (
    validate_all,
    validate_allowed_hosts,
    validate_database_config,
    validate_production_secrets,
    validate_redis_config,
)


class ValidateDatabaseConfigTests(SimpleTestCase):
    """Tests for validate_database_config."""

    @override_settings(DATABASES={})
    def test_fails_when_default_missing(self):
        with self.assertRaises(ImproperlyConfigured) as ctx:
            validate_database_config()
        self.assertIn("DATABASES['default']", str(ctx.exception))

    @override_settings(
        DATABASES={
            "default": {
                "ENGINE": "django.db.backends.postgresql",
                "NAME": "hub",
                "HOST": "localhost",
                "PORT": "5432",
            }
        }
    )
    def test_passes_when_required_keys_present(self):
        validate_database_config()

    @override_settings(
        DATABASES={
            "default": {
                "ENGINE": "django.db.backends.postgresql",
                "NAME": "hub",
                # missing HOST, PORT
            }
        }
    )
    def test_fails_when_host_missing(self):
        with self.assertRaises(ImproperlyConfigured) as ctx:
            validate_database_config()
        self.assertIn("HOST", str(ctx.exception))

    @override_settings(
        DATABASES={
            "default": {
                "ENGINE": "",
                "NAME": "hub",
                "HOST": "localhost",
                "PORT": "5432",
            }
        }
    )
    def test_fails_when_engine_empty(self):
        with self.assertRaises(ImproperlyConfigured) as ctx:
            validate_database_config()
        self.assertIn("ENGINE", str(ctx.exception))


class ValidateRedisConfigTests(SimpleTestCase):
    """Tests for validate_redis_config."""

    @override_settings(REDIS_URL="redis://localhost:6379/0", REDIS_CACHE_URL=None)
    def test_passes_with_redis_url(self):
        validate_redis_config()

    @override_settings(REDIS_URL="", REDIS_CACHE_URL="redis://redis-cache:6379/0")
    def test_passes_with_redis_cache_url(self):
        validate_redis_config()

    @override_settings(REDIS_URL="redis://localhost/0")
    def test_passes_redis_scheme(self):
        validate_redis_config()

    @override_settings(REDIS_URL="rediss://localhost:6379/0")
    def test_passes_rediss_scheme(self):
        validate_redis_config()

    @override_settings(REDIS_URL="http://localhost:6379", REDIS_CACHE_URL="")
    def test_fails_invalid_scheme(self):
        """Invalid scheme (e.g. http://) must raise; REDIS_CACHE_URL cleared so we validate REDIS_URL."""
        with self.assertRaises(ImproperlyConfigured) as ctx:
            validate_redis_config()
        self.assertIn("redis://", str(ctx.exception))

    @override_settings(
        REDIS_URL="",
        REDIS_CACHE_URL="",
        ENVIRONMENT="production",
    )
    def test_fails_in_production_when_no_redis(self):
        with self.assertRaises(ImproperlyConfigured) as ctx:
            validate_redis_config()
        self.assertIn("Redis", str(ctx.exception))

    @override_settings(
        REDIS_URL="",
        REDIS_CACHE_URL="",
        ENVIRONMENT="staging",
    )
    def test_fails_in_staging_when_no_redis(self):
        with self.assertRaises(ImproperlyConfigured) as ctx:
            validate_redis_config()
        self.assertIn("Redis", str(ctx.exception))


class ValidateAllowedHostsTests(SimpleTestCase):
    """Tests for validate_allowed_hosts."""

    @override_settings(ENVIRONMENT="development", ALLOWED_HOSTS=[])
    def test_skips_when_not_production(self):
        validate_allowed_hosts()

    @override_settings(ENVIRONMENT="production", ALLOWED_HOSTS=["api.example.com"])
    def test_passes_when_production_and_non_empty(self):
        validate_allowed_hosts()

    @override_settings(ENVIRONMENT="production", ALLOWED_HOSTS=[])
    def test_fails_when_production_and_empty(self):
        with self.assertRaises(ImproperlyConfigured) as ctx:
            validate_allowed_hosts()
        self.assertIn("ALLOWED_HOSTS", str(ctx.exception))


class ValidateProductionSecretsTests(SimpleTestCase):
    """Tests for validate_production_secrets."""

    @override_settings(
        ENVIRONMENT="development",
        SECRET_KEY="dev-secret-key-not-for-production",
        JWT_SECRET_KEY="dev-jwt-secret-key-not-for-production",
    )
    def test_skips_when_not_production(self):
        validate_production_secrets()

    @override_settings(
        ENVIRONMENT="production",
        SECRET_KEY="prod-secret-key-set-via-env",
        JWT_SECRET_KEY="prod-jwt-secret-set-via-env",
    )
    def test_passes_when_production_and_secrets_set(self):
        validate_production_secrets()

    @override_settings(
        ENVIRONMENT="production",
        SECRET_KEY="dev-secret-key-not-for-production",
        JWT_SECRET_KEY="prod-jwt-secret-set-via-env",
    )
    def test_fails_when_production_and_secret_key_is_dev_default(self):
        with self.assertRaises(ImproperlyConfigured) as ctx:
            validate_production_secrets()
        self.assertIn("SECRET_KEY", str(ctx.exception))

    @override_settings(
        ENVIRONMENT="production",
        SECRET_KEY="prod-secret-key-set-via-env",
        JWT_SECRET_KEY="dev-jwt-secret-key-not-for-production",
    )
    def test_fails_when_production_and_jwt_secret_is_dev_default(self):
        with self.assertRaises(ImproperlyConfigured) as ctx:
            validate_production_secrets()
        self.assertIn("JWT_SECRET_KEY", str(ctx.exception))


class ValidateAllTests(SimpleTestCase):
    """Tests for validate_all integration."""

    @override_settings(
        DATABASES={
            "default": {
                "ENGINE": "django.db.backends.postgresql",
                "NAME": "hub",
                "HOST": "localhost",
                "PORT": "5432",
            }
        },
        REDIS_URL="redis://localhost:6379/0",
        ENVIRONMENT="development",
        ALLOWED_HOSTS=["localhost"],
    )
    def test_passes_with_valid_development_config(self):
        validate_all()

    @override_settings(
        DATABASES={
            "default": {
                "ENGINE": "django.db.backends.postgresql",
                "NAME": "hub",
                "HOST": "localhost",
                "PORT": "5432",
            }
        },
        REDIS_URL="redis://localhost:6379/0",
        ENVIRONMENT="production",
        ALLOWED_HOSTS=["api.example.com"],
        SECRET_KEY="prod-secret",
        JWT_SECRET_KEY="prod-jwt-secret",
    )
    def test_passes_with_valid_production_config(self):
        validate_all()


class ValidateConfigCommandTests(SimpleTestCase):
    """Tests for the validate_config management command (exit code and output)."""

    @override_settings(
        DATABASES={
            "default": {
                "ENGINE": "django.db.backends.postgresql",
                "NAME": "hub",
                "HOST": "localhost",
                "PORT": "5432",
            }
        },
        REDIS_URL="redis://localhost:6379/0",
        ENVIRONMENT="development",
        ALLOWED_HOSTS=["localhost"],
    )
    def test_command_exits_zero_when_config_valid(self):
        from io import StringIO

        from django.core.management import call_command

        out = StringIO()
        err = StringIO()
        call_command("validate_config", stdout=out, stderr=err)
        self.assertIn("valid", out.getvalue().lower())

    @override_settings(
        DATABASES={},
        REDIS_URL="redis://localhost:6379/0",
        ENVIRONMENT="development",
    )
    def test_command_exits_non_zero_when_config_invalid(self):
        from io import StringIO

        from django.core.management import call_command

        out = StringIO()
        err = StringIO()
        with self.assertRaises(SystemExit) as ctx:
            call_command("validate_config", stdout=out, stderr=err)
        self.assertEqual(ctx.exception.code, 1)
        self.assertIn("DATABASES", err.getvalue())
