"""
Real Email Service Fixtures

Real fixtures (not mocks) for testing email services with actual backend configurations.
These fixtures configure real email backends for testing.
"""

import os
from typing import Any

from django.test import override_settings


class EmailServiceFixtures:
    """
    Real email service fixtures for SendGrid, SES, and SMTP.

    These fixtures configure actual email backends for testing, not mocks.
    """

    @staticmethod
    def get_sendgrid_config() -> dict[str, Any]:
        """Get SendGrid configuration for testing"""
        return {
            "EMAIL_BACKEND": "sendgrid",
            "SENDGRID_API_KEY": os.getenv("TEST_SENDGRID_API_KEY", "test-sendgrid-key"),
            "SENDGRID_FROM_EMAIL": os.getenv("TEST_SENDGRID_FROM_EMAIL", "test@example.com"),
            "SENDGRID_FROM_NAME": os.getenv("TEST_SENDGRID_FROM_NAME", "Test Hub"),
        }

    @staticmethod
    def get_ses_config() -> dict[str, Any]:
        """Get AWS SES configuration for testing"""
        return {
            "EMAIL_BACKEND": "ses",
            "AWS_SES_REGION": os.getenv("TEST_AWS_SES_REGION", "us-east-1"),
            "AWS_SES_FROM_EMAIL": os.getenv("TEST_AWS_SES_FROM_EMAIL", "test@example.com"),
            "AWS_SES_FROM_NAME": os.getenv("TEST_AWS_SES_FROM_NAME", "Test Hub"),
            "AWS_ACCESS_KEY_ID": os.getenv("TEST_AWS_ACCESS_KEY_ID", "test-access-key"),
            "AWS_SECRET_ACCESS_KEY": os.getenv("TEST_AWS_SECRET_ACCESS_KEY", "test-secret-key"),
        }

    @staticmethod
    def get_smtp_config() -> dict[str, Any]:
        """Get SMTP configuration for testing"""
        return {
            "EMAIL_BACKEND": "smtp",
            "SMTP_HOST": os.getenv("TEST_SMTP_HOST", "localhost"),
            "SMTP_PORT": int(os.getenv("TEST_SMTP_PORT", "587")),
            "SMTP_USERNAME": os.getenv("TEST_SMTP_USERNAME", "test@example.com"),
            "SMTP_PASSWORD": os.getenv("TEST_SMTP_PASSWORD", "test-password"),
            "SMTP_USE_TLS": os.getenv("TEST_SMTP_USE_TLS", "true").lower() == "true",
            "SMTP_USE_SSL": os.getenv("TEST_SMTP_USE_SSL", "false").lower() == "true",
            "SMTP_FROM_EMAIL": os.getenv("TEST_SMTP_FROM_EMAIL", "test@example.com"),
            "SMTP_FROM_NAME": os.getenv("TEST_SMTP_FROM_NAME", "Test Hub"),
        }

    @staticmethod
    def with_sendgrid():
        """Context manager for testing with SendGrid backend"""
        return override_settings(**EmailServiceFixtures.get_sendgrid_config())

    @staticmethod
    def with_ses():
        """Context manager for testing with AWS SES backend"""
        return override_settings(**EmailServiceFixtures.get_ses_config())

    @staticmethod
    def with_smtp():
        """Context manager for testing with SMTP backend"""
        return override_settings(**EmailServiceFixtures.get_smtp_config())


class WorkerServiceFixtures:
    """
    Real worker service fixtures for job processing.

    These fixtures configure actual worker services for testing, not mocks.
    """

    @staticmethod
    def get_worker_config() -> dict[str, Any]:
        """Get worker service configuration for testing"""
        return {
            "WORKER_MAX_CONCURRENCY": int(os.getenv("TEST_WORKER_MAX_CONCURRENCY", "4")),
            "WORKER_MAX_CONCURRENCY_PER_TENANT": int(
                os.getenv("TEST_WORKER_MAX_CONCURRENCY_PER_TENANT", "2")
            ),
            "WORKER_RESERVED_SLOTS_RATIO": float(
                os.getenv("TEST_WORKER_RESERVED_SLOTS_RATIO", "0.5")
            ),
            "WORKER_STARVATION_THRESHOLD_SECONDS": int(
                os.getenv("TEST_WORKER_STARVATION_THRESHOLD_SECONDS", "300")
            ),
            "REDIS_URL": os.getenv(
                "TEST_REDIS_URL", "redis://localhost:6379/1"
            ),  # Use DB 1 for tests
        }

    @staticmethod
    def with_worker_config():
        """Context manager for testing with worker configuration"""
        return override_settings(**WorkerServiceFixtures.get_worker_config())


class RateLimitingFixtures:
    """
    Real rate limiting fixtures for all scenarios.

    These fixtures configure actual rate limiting for testing, not mocks.
    """

    @staticmethod
    def get_rate_limit_config() -> dict[str, Any]:
        """Get rate limiting configuration for testing"""
        return {
            "RATE_LIMIT_ENABLED": os.getenv("TEST_RATE_LIMIT_ENABLED", "true").lower() == "true",
            "REDIS_URL": os.getenv(
                "TEST_REDIS_URL", "redis://localhost:6379/1"
            ),  # Use DB 1 for tests
        }

    @staticmethod
    def with_rate_limiting():
        """Context manager for testing with rate limiting enabled"""
        return override_settings(**RateLimitingFixtures.get_rate_limit_config())

    @staticmethod
    def without_rate_limiting():
        """Context manager for testing with rate limiting disabled"""
        return override_settings(RATE_LIMIT_ENABLED=False)
