"""
Unit tests for OpenLineage async tasks.

Previously :func:`send_openlineage_event_async` had zero direct test
coverage — every outbound-wiring test mocked at the dispatch boundary.
This file covers all five return paths of the task body.
"""

from __future__ import annotations

import uuid
from unittest import mock

import pytest
from django.test import TransactionTestCase, override_settings

from hub.apps.integrations.openlineage.adapter import DeliveryOutcome
from hub.apps.integrations.openlineage.tasks import send_openlineage_event_async


def _create_tenant():
    from hub.apps.tenants.models import Tenant

    suffix = uuid.uuid4().hex[:8]
    return Tenant.objects.create(
        name=f"OLTaskTest Co {suffix}",
        slug=f"oltt-{suffix}",
    )


@pytest.mark.django_db(transaction=True)
class TestSendOpenLineageEventAsync(TransactionTestCase):
    """Cover all five return paths of ``send_openlineage_event_async``."""

    def test_no_tenant_id_returns_skipped(self):
        """When ``tenant_id`` is None, return ``skipped:no_tenant``
        and never call the adapter."""
        with mock.patch(
            "hub.apps.integrations.openlineage.adapter.OpenLineageAdapter"
        ) as adapter_cls:
            result = send_openlineage_event_async({"e": 1}, tenant_id=None)
            adapter_cls.return_value.deliver.assert_not_called()
        assert result == "skipped:no_tenant"

    def test_tenant_does_not_exist_returns_skipped(self):
        """When the tenant_id does not match any Tenant row, return
        ``skipped:tenant_not_found`` and never call the adapter."""
        bad_id = str(uuid.uuid4())
        with mock.patch(
            "hub.apps.integrations.openlineage.adapter.OpenLineageAdapter"
        ) as adapter_cls:
            result = send_openlineage_event_async({"e": 1}, tenant_id=bad_id)
            adapter_cls.return_value.deliver.assert_not_called()
        assert result == "skipped:tenant_not_found"

    def test_no_target_url_and_no_setting_returns_skipped(self):
        """When neither ``target_url`` nor ``settings.OPENLINEAGE_URL``
        is set, return ``skipped:no_target_url``."""
        tenant = _create_tenant()
        with mock.patch(
            "hub.apps.integrations.openlineage.adapter.OpenLineageAdapter"
        ) as adapter_cls:
            result = send_openlineage_event_async(
                {"e": 1},
                tenant_id=str(tenant.id),
                target_url=None,
            )
            adapter_cls.return_value.deliver.assert_not_called()
        assert result == "skipped:no_target_url"

    def test_uses_settings_openlineage_url_as_fallback(self):
        """When ``target_url`` is None but ``settings.OPENLINEAGE_URL``
        is configured, the task should use the setting value."""
        tenant = _create_tenant()
        with override_settings(OPENLINEAGE_URL="http://marquez.example/api/v1/lineage"):
            with mock.patch(
                "hub.apps.integrations.openlineage.adapter.OpenLineageAdapter"
            ) as adapter_cls:
                adapter_cls.return_value.deliver.return_value = DeliveryOutcome.DELIVERED
                result = send_openlineage_event_async(
                    {"e": 1},
                    tenant_id=str(tenant.id),
                    target_url=None,
                )
                adapter_cls.return_value.deliver.assert_called_once_with(
                    event={"e": 1},
                    target_url="http://marquez.example/api/v1/lineage",
                    tenant=tenant,
                )
        assert result == str(DeliveryOutcome.DELIVERED)

    def test_explicit_target_url_takes_priority(self):
        """A caller-supplied ``target_url`` overrides ``settings.OPENLINEAGE_URL``."""
        tenant = _create_tenant()
        explicit_url = "http://explicit-marquez.example/api/v1/lineage"
        with override_settings(OPENLINEAGE_URL="http://settings-marquez.example/api/v1/lineage"):
            with mock.patch(
                "hub.apps.integrations.openlineage.adapter.OpenLineageAdapter"
            ) as adapter_cls:
                adapter_cls.return_value.deliver.return_value = DeliveryOutcome.DELIVERED
                result = send_openlineage_event_async(
                    {"e": 1},
                    tenant_id=str(tenant.id),
                    target_url=explicit_url,
                )
                adapter_cls.return_value.deliver.assert_called_once_with(
                    event={"e": 1},
                    target_url=explicit_url,
                    tenant=tenant,
                )
        assert result == str(DeliveryOutcome.DELIVERED)

    def test_successful_delivery_returns_delivered(self):
        """A successful adapter delivery returns ``DeliveryOutcome.DELIVERED`` as a string."""
        tenant = _create_tenant()
        with mock.patch(
            "hub.apps.integrations.openlineage.adapter.OpenLineageAdapter"
        ) as adapter_cls:
            adapter_cls.return_value.deliver.return_value = DeliveryOutcome.DELIVERED
            result = send_openlineage_event_async(
                {"run": {"runId": str(uuid.uuid4())}},
                tenant_id=str(tenant.id),
                target_url="http://marquez.example/api/v1/lineage",
            )
        assert result == str(DeliveryOutcome.DELIVERED)

    def test_failed_delivery_returns_dead_lettered(self):
        """An adapter that dead-letters the event returns
        ``DeliveryOutcome.DEAD_LETTERED`` as a string."""
        tenant = _create_tenant()
        with mock.patch(
            "hub.apps.integrations.openlineage.adapter.OpenLineageAdapter"
        ) as adapter_cls:
            adapter_cls.return_value.deliver.return_value = DeliveryOutcome.DEAD_LETTERED
            result = send_openlineage_event_async(
                {"run": {"runId": str(uuid.uuid4())}},
                tenant_id=str(tenant.id),
                target_url="http://marquez.example/api/v1/lineage",
            )
        assert result == str(DeliveryOutcome.DEAD_LETTERED)
