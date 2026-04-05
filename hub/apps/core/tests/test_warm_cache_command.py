"""
Phase 83.10 — warm_cache management command tests.
"""
from io import StringIO
from unittest.mock import patch

import pytest
from django.core.management import call_command, CommandError
from django.test import TestCase

# Patch where the command imports, not where the functions are defined
_CMD = "hub.apps.core.management.commands.warm_cache"


@pytest.mark.django_db(transaction=True)
class WarmCacheCommandTest(TestCase):

    def _create_tenant(self):
        from hub.apps.tenants.models import Tenant
        return Tenant.objects.get_or_create(
            name="cache-test", defaults={"slug": "cache-test"},
        )[0]

    @patch(f"{_CMD}.warm_tenant_cache")
    def test_tenant_cache_warmed(self, mock_warm):
        mock_warm.return_value = {
            "assets": 5, "contracts": 3, "marketplace": 2,
        }
        tenant = self._create_tenant()
        out = StringIO()
        call_command("warm_cache", f"--tenant-id={tenant.id}", stdout=out)
        mock_warm.assert_called_once_with(str(tenant.id))

    @patch(f"{_CMD}.warm_all_tenants_cache")
    def test_all_tenants_mode(self, mock_warm):
        mock_warm.return_value = {
            "successful": 1, "total_tenants": 1,
            "failed": 0, "results_by_tenant": {},
        }
        out = StringIO()
        call_command("warm_cache", "--all-tenants", stdout=out)
        mock_warm.assert_called_once()

    @patch(f"{_CMD}.warm_marketplace_listings_cache")
    def test_marketplace_only(self, mock_warm):
        mock_warm.return_value = 10
        out = StringIO()
        call_command("warm_cache", "--marketplace-only", stdout=out)
        mock_warm.assert_called_once()

    def test_no_args_raises_error(self):
        with self.assertRaises(CommandError):
            call_command("warm_cache")

    @patch(f"{_CMD}.warm_tenant_cache", side_effect=RuntimeError("Redis down"))
    def test_cache_failure_raises(self, mock_warm):
        tenant = self._create_tenant()
        with self.assertRaises(CommandError):
            call_command("warm_cache", f"--tenant-id={tenant.id}")
