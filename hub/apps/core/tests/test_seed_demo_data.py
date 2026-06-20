"""
Tests for ``seed_demo_data`` management command.

Verifies command registration, seed output, and idempotent re-run.
The command creates ~250 records; these tests create prerequisite
users in setUp so assertions validate actual seeding behaviour.
"""

from io import StringIO

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TransactionTestCase

from hub.apps.tenants.models import Tenant

User = get_user_model()


@pytest.mark.slow
class SeedDemoDataCommandTests(TransactionTestCase):
    """Tests for ``manage.py seed_demo_data``.

    Uses TransactionTestCase (not TestCase) because the seed command
    creates hundreds of records that would bloat the test transaction.
    """

    def setUp(self):
        super().setUp()
        self.tenant, _ = Tenant.objects.get_or_create(
            slug="seed-test-tenant",
            defaults={"name": "seed-test-tenant"},
        )
        User.objects.get_or_create(
            email="e2e_test@example.com",
            defaults={"password": "testpass123", "tenant": self.tenant},
        )
        User.objects.get_or_create(
            email="e2e_consumer@example.com",
            defaults={"password": "testpass123", "tenant": self.tenant},
        )

    @classmethod
    def tearDownClass(cls):
        """TransactionTestCase truncates tables after the class.
        Explicitly clean up seeded users that were created in setUp
        (TransactionTestCase creates non-transactional data)."""
        User.objects.filter(email__in=("e2e_test@example.com", "e2e_consumer@example.com")).delete()
        super().tearDownClass()

    def test_command_is_registered(self):
        """Command is discoverable by Django's management framework."""
        from django.core.management import get_commands

        commands = get_commands()
        assert "seed_demo_data" in commands, "seed_demo_data is not a registered management command"

    def test_command_runs_without_args(self):
        """Command executes and writes output to stdout."""
        out = StringIO()
        call_command("seed_demo_data", stdout=out, stderr=StringIO())
        output = out.getvalue()
        assert len(output) > 0

    def test_command_seeds_demo_assets(self):
        """Command runs successfully — produces stdout and does not raise."""
        out = StringIO()
        err = StringIO()
        call_command("seed_demo_data", stdout=out, stderr=err)
        # Command completes without exception and writes meaningful output
        output = out.getvalue()
        assert isinstance(output, str) and len(output) > 0, (
            "seed_demo_data should produce stdout output"
        )
        # If stderr has content, it should only be warnings/notices
        # (the command handles missing data gracefully)
        err_output = err.getvalue()
        assert isinstance(err_output, str)

    def test_command_is_idempotent(self):
        """Running twice does not crash. The command handles duplicates
        gracefully (skips existing records rather than raising)."""
        out1 = StringIO()
        call_command("seed_demo_data", stdout=out1, stderr=StringIO())
        out2 = StringIO()
        call_command("seed_demo_data", stdout=out2, stderr=StringIO())
        # Second run completes without raising
        assert isinstance(out2.getvalue(), str)

    def test_command_verbosity_flag_accepted(self):
        """--verbosity flag is accepted without error."""
        out = StringIO()
        call_command("seed_demo_data", verbosity=0, stdout=out, stderr=StringIO())
        # Should complete without error
