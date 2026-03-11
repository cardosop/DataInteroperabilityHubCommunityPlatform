"""
Security tests: IDOR for Scheduled ingestions and exports.

Per tasks 29.5.2. User from tenant A must not access tenant B's scheduled
ingestion/export by ID. Real APIClient; two tenants/users; assert 403 or 404.
"""

import pytest
from rest_framework import status

from hub.apps.scheduled_export.models import (
    DestinationType,
    ScheduledExport,
    ScheduledExportStatus,
)
from hub.apps.scheduled_ingestion.models import (
    ScheduleType,
    ScheduledIngestion,
    ScheduledIngestionStatus,
    SourceType,
)

from .base_idor import IDORTestBase

pytestmark = pytest.mark.django_db(transaction=True)


class ScheduledIngestionIDORTest(IDORTestBase):
    """IDOR: user from tenant A must not access tenant B's scheduled ingestion by ID."""

    def test_scheduled_ingestion_retrieve_returns_403_or_404_for_other_tenant(self):
        """GET scheduled-ingestions/{id}/ for other tenant's ingestion must return 403 or 404."""
        ingestion_b = ScheduledIngestion.objects.create(
            tenant=self.tenant_b,
            name="Ingestion B",
            source_type=SourceType.S3,
            source_config={"bucket": "bucket-b"},
            schedule_type=ScheduleType.DAILY,
            schedule_config={"time": "02:00"},
            status=ScheduledIngestionStatus.ACTIVE,
        )
        self.client.force_authenticate(user=self.user_a)
        response = self.client.get(f"/api/v1/scheduled-ingestions/{ingestion_b.id}/")
        self.assertIn(
            response.status_code,
            (status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND),
            "Cross-tenant scheduled ingestion access must be 403 or 404",
        )

    def test_scheduled_ingestion_retrieve_succeeds_for_own_tenant(self):
        """GET scheduled-ingestions/{id}/ for own tenant's ingestion can return 200."""
        ingestion_a = ScheduledIngestion.objects.create(
            tenant=self.tenant_a,
            name="Ingestion A",
            source_type=SourceType.S3,
            source_config={"bucket": "bucket-a"},
            schedule_type=ScheduleType.DAILY,
            schedule_config={"time": "02:00"},
            status=ScheduledIngestionStatus.ACTIVE,
        )
        self.client.force_authenticate(user=self.user_a)
        response = self.client.get(f"/api/v1/scheduled-ingestions/{ingestion_a.id}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)


class ScheduledExportIDORTest(IDORTestBase):
    """IDOR: user from tenant A must not access tenant B's scheduled export by ID."""

    def test_scheduled_export_retrieve_returns_403_or_404_for_other_tenant(self):
        """GET scheduled-exports/{id}/ for other tenant's export must return 403 or 404."""
        from hub.apps.assets.models import Asset, AssetStatus

        asset_b = Asset.objects.create(
            tenant=self.tenant_b,
            name="Asset B",
            status=AssetStatus.ACTIVE,
        )
        export_b = ScheduledExport.objects.create(
            tenant=self.tenant_b,
            name="Export B",
            schedule_config={"cron": "0 2 * * *"},
            destination_type=DestinationType.S3,
            destination_config={"bucket": "bucket-b"},
            source_scope={"asset_ids": [str(asset_b.id)]},
            status=ScheduledExportStatus.ACTIVE,
        )
        self.client.force_authenticate(user=self.user_a)
        response = self.client.get(f"/api/v1/scheduled-exports/{export_b.id}/")
        self.assertIn(
            response.status_code,
            (status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND),
            "Cross-tenant scheduled export access must be 403 or 404",
        )

    def test_scheduled_export_retrieve_succeeds_for_own_tenant(self):
        """GET scheduled-exports/{id}/ for own tenant's export can return 200."""
        from hub.apps.assets.models import Asset, AssetStatus

        asset_a = Asset.objects.create(
            tenant=self.tenant_a,
            name="Asset A",
            status=AssetStatus.ACTIVE,
        )
        export_a = ScheduledExport.objects.create(
            tenant=self.tenant_a,
            name="Export A",
            schedule_config={"cron": "0 2 * * *"},
            destination_type=DestinationType.S3,
            destination_config={"bucket": "bucket-a"},
            source_scope={"asset_ids": [str(asset_a.id)]},
            status=ScheduledExportStatus.ACTIVE,
        )
        self.client.force_authenticate(user=self.user_a)
        response = self.client.get(f"/api/v1/scheduled-exports/{export_a.id}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
