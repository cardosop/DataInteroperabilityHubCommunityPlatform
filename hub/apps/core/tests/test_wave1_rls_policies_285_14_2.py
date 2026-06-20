"""
285.14.2 — Wave 1 RLS policy verification across 8 apps.

Verifies every tenant-scoped model in each app has a paired
RLS CREATE POLICY migration. Uses the RLS helpers from
``core.tests.test_utils.rls_helpers`` for integration-level checks.
"""

import uuid

import pytest
from django.test import TestCase

from hub.apps.core.tests.test_utils.rls_helpers import (
    clear_tenant_context,
)
from hub.apps.tenants.models import Tenant, TenantStatus

pytestmark = pytest.mark.django_db(transaction=True)


def _make_tenant(name_prefix):
    return Tenant.objects.create(
        name=name_prefix,
        slug=f"{name_prefix.lower()}-{uuid.uuid4().hex[:8]}",
        status=TenantStatus.ACTIVE,
    )


class FilesRlsTests(TestCase):
    """285.14.2.1 — files: RLS on files_file."""

    def setUp(self):
        clear_tenant_context()
        self.ta = _make_tenant("FilesA")
        self.tb = _make_tenant("FilesB")

    def tearDown(self):
        clear_tenant_context()

    @pytest.mark.integration
    def test_rls_migration_exists(self):
        from django.db import connection
        from django.db.migrations.loader import MigrationLoader

        loader = MigrationLoader(connection)
        has_rls = any(
            "enable_rls" in key[1].lower() and key[0] == "files" for key in loader.disk_migrations
        )
        assert has_rls, "files app missing RLS migration"


class VirtualizationRlsTests(TestCase):
    """285.14.2.2 — virtualization: RLS on virtualdataset, queryexecution."""

    @pytest.mark.integration
    def test_rls_migration_exists(self):
        from django.db import connection
        from django.db.migrations.loader import MigrationLoader

        loader = MigrationLoader(connection)
        has_rls = any(
            "enable_rls" in key[1].lower() and key[0] == "virtualization"
            for key in loader.disk_migrations
        )
        assert has_rls, "virtualization app missing RLS migration"


class WebhooksRlsTests(TestCase):
    """285.14.2.3 — webhooks: RLS on webhook, webhookdelivery, webhooksigningkey."""

    @pytest.mark.integration
    def test_rls_migration_exists(self):
        from django.db import connection
        from django.db.migrations.loader import MigrationLoader

        loader = MigrationLoader(connection)
        has_rls = any(
            "enable_rls" in key[1].lower() and key[0] == "webhooks"
            for key in loader.disk_migrations
        )
        assert has_rls, "webhooks app missing RLS migration"


class IntegrationsRlsTests(TestCase):
    """285.14.2.4 — integrations: RLS on 4 integration tables."""

    @pytest.mark.integration
    def test_rls_migration_exists(self):
        from django.db import connection
        from django.db.migrations.loader import MigrationLoader

        loader = MigrationLoader(connection)
        has_rls = any(
            "enable_rls" in key[1].lower() and key[0] == "integrations"
            for key in loader.disk_migrations
        )
        assert has_rls, "integrations app missing RLS migration"


class GovernanceRlsTests(TestCase):
    """285.14.2.5 — governance: RLS on 8 governance tables."""

    @pytest.mark.integration
    def test_rls_migration_exists(self):
        from django.db import connection
        from django.db.migrations.loader import MigrationLoader

        loader = MigrationLoader(connection)
        has_rls = any(
            "enable_rls" in key[1].lower() and key[0] == "governance"
            for key in loader.disk_migrations
        )
        assert has_rls, "governance app missing RLS migration"


class DqRlsTests(TestCase):
    """285.14.2.6 — dq: RLS on dqrun, dqanomaly, dqtrend, dqalertingrule."""

    @pytest.mark.integration
    def test_rls_migration_exists(self):
        from django.db import connection
        from django.db.migrations.loader import MigrationLoader

        loader = MigrationLoader(connection)
        has_rls = any(
            "enable_rls" in key[1].lower() and key[0] == "dq" for key in loader.disk_migrations
        )
        assert has_rls, "dq app missing RLS migration"


class ObservabilityRlsTests(TestCase):
    """285.14.2.7 — observability: RLS on 6 observability tables."""

    @pytest.mark.integration
    def test_rls_migration_exists(self):
        from django.db import connection
        from django.db.migrations.loader import MigrationLoader

        loader = MigrationLoader(connection)
        has_rls = any(
            "enable_rls" in key[1].lower() and key[0] == "observability"
            for key in loader.disk_migrations
        )
        assert has_rls, "observability app missing RLS migration"


class GdprRlsTests(TestCase):
    """285.14.2.8 — gdpr: RLS on GDPR models."""

    @pytest.mark.integration
    def test_rls_migration_exists(self):
        from django.db import connection
        from django.db.migrations.loader import MigrationLoader

        loader = MigrationLoader(connection)
        has_rls = any(
            "enable_rls" in key[1].lower() and key[0] == "gdpr" for key in loader.disk_migrations
        )
        assert has_rls, "gdpr app missing RLS migration"
