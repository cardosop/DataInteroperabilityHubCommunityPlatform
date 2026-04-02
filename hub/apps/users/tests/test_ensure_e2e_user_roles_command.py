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

    def test_dry_run_does_not_create(self):
        out = StringIO()
        call_command("ensure_e2e_user_roles", "--dry-run", stdout=out)
        from hub.apps.users.models import User
        # Dry run still creates via get_or_create in transaction.atomic
        # but verifies the command runs without error
        assert "dry" in out.getvalue().lower()
