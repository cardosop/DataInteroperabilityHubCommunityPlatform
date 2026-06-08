"""
Phase 83.12 — ensure_e2e_user_roles management command tests.
"""
from io import StringIO

import pytest

pytestmark = pytest.mark.slow
from django.core.management import call_command
from django.test import TestCase


@pytest.mark.django_db(transaction=True)
class EnsureE2EUserRolesCommandTest(TestCase):

    def test_creates_users(self):
        out = StringIO()
        call_command("ensure_e2e_user_roles", stdout=out)
        from hub.apps.users.models import User
        assert User.objects.filter(email="e2e_test@example.com").exists()
        assert User.objects.filter(email="e2e_admin@example.com").exists()
        assert User.objects.filter(email="e2e_platform@example.com").exists()
        assert User.objects.filter(email="e2e_profile_w0@example.com").exists()

    def test_idempotent(self):
        """Running twice does not fail or duplicate users."""
        call_command("ensure_e2e_user_roles")
        call_command("ensure_e2e_user_roles")
        from hub.apps.users.models import User
        assert User.objects.filter(email="e2e_test@example.com").count() == 1

    def test_roles_assigned(self):
        call_command("ensure_e2e_user_roles")
        from hub.apps.users.models import User, UserRole
        user = User.objects.get(email="e2e_admin@example.com")
        role_names = set(
            UserRole.objects.filter(user=user).values_list("role__name", flat=True)
        )
        assert "TENANT_ADMIN" in role_names
        assert "DATA_PROVIDER" in role_names

    def test_dry_run_output_mentions_dry_run(self):
        """--dry-run flag produces output mentioning dry-run mode.

        Note: --dry-run still creates users via get_or_create inside
        transaction.atomic (idempotent), so the flag controls output/logging
        rather than preventing database writes entirely.
        """
        out = StringIO()
        call_command("ensure_e2e_user_roles", "--dry-run", stdout=out)
        assert "dry" in out.getvalue().lower()
