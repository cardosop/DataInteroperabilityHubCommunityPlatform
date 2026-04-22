"""
Tests for hub/apps/api/checks.py — Django system checks that run on
`manage.py check --deploy` to catch staging misconfiguration.

Both checks are registered with ``deploy=True`` so they do NOT run on every
`manage.py migrate` / `collectstatic` (those happen at image-build time when
env vars may be absent). They run as a post-deploy smoke step.

Why these exist
---------------
hub.E001: prevents a silent un-gating of staging. If someone accidentally
deploys staging with MVP_MODE unset or false, all non-MVP API prefixes
become reachable on a public URL. The check catches this at boot.

hub.E002: prevents the four ``ensure_e2e_*`` endpoints from being
exposed without a shared-secret header. When the secret is unset, the
decorator 404s unconditionally — but this check fires during pre-flight
to surface the misconfiguration before users discover it.
"""
from __future__ import annotations

import pytest
from django.test import TestCase, override_settings

from hub.apps.api.checks import (
    check_e2e_secret_when_endpoints_mounted,
    check_mvp_mode_on_staging,
)


class CheckMvpModeOnStagingTest(TestCase):
    """hub.E001 — staging without MVP_MODE=True is an error."""

    @override_settings(ENVIRONMENT="staging", MVP_MODE=True)
    def test_staging_with_mvp_mode_true_passes(self):
        errors = check_mvp_mode_on_staging(app_configs=None)
        self.assertEqual(errors, [])

    @override_settings(ENVIRONMENT="staging", MVP_MODE=False)
    def test_staging_with_mvp_mode_false_fires_hub_E001(self):
        errors = check_mvp_mode_on_staging(app_configs=None)
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0].id, "hub.E001")

    @override_settings(ENVIRONMENT="staging", MVP_MODE=None)
    def test_staging_with_mvp_mode_none_fires_hub_E001(self):
        # A missing / misconfigured MVP_MODE reads as not-True too.
        errors = check_mvp_mode_on_staging(app_configs=None)
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0].id, "hub.E001")

    @override_settings(ENVIRONMENT="production", MVP_MODE=False)
    def test_production_is_not_subject_to_the_check(self):
        errors = check_mvp_mode_on_staging(app_configs=None)
        self.assertEqual(errors, [])

    @override_settings(ENVIRONMENT="development", MVP_MODE=False)
    def test_development_is_not_subject_to_the_check(self):
        errors = check_mvp_mode_on_staging(app_configs=None)
        self.assertEqual(errors, [])

    @override_settings(ENVIRONMENT="test", MVP_MODE=False)
    def test_test_is_not_subject_to_the_check(self):
        errors = check_mvp_mode_on_staging(app_configs=None)
        self.assertEqual(errors, [])


class CheckE2eSecretWhenEndpointsMountedTest(TestCase):
    """hub.E002 — missing E2E_TEST_SECRET in env where E2E URLs are mounted is an error."""

    @override_settings(ENVIRONMENT="staging", E2E_TEST_SECRET="not-a-real-secret-1234")
    def test_staging_with_secret_passes(self):
        errors = check_e2e_secret_when_endpoints_mounted(app_configs=None)
        self.assertEqual(errors, [])

    @override_settings(ENVIRONMENT="staging", E2E_TEST_SECRET="")
    def test_staging_without_secret_fires_hub_E002(self):
        errors = check_e2e_secret_when_endpoints_mounted(app_configs=None)
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0].id, "hub.E002")

    @override_settings(ENVIRONMENT="test", E2E_TEST_SECRET="")
    def test_test_environment_without_secret_also_fires(self):
        # Test environment mounts the URLs too; symmetric enforcement.
        errors = check_e2e_secret_when_endpoints_mounted(app_configs=None)
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0].id, "hub.E002")

    @override_settings(ENVIRONMENT="production", E2E_TEST_SECRET="")
    def test_production_without_secret_fires_defensively(self):
        # Prod should not serve E2E endpoints at all (decorator 404s on empty
        # secret too), but if the URLs ever leak, this check fires first.
        errors = check_e2e_secret_when_endpoints_mounted(app_configs=None)
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0].id, "hub.E002")

    @override_settings(ENVIRONMENT="development", E2E_TEST_SECRET="")
    def test_development_without_secret_does_not_fire(self):
        # Developers should be able to run without setting the secret.
        errors = check_e2e_secret_when_endpoints_mounted(app_configs=None)
        self.assertEqual(errors, [])
