"""283.5.16 — SDK unit tests for Security, Drafts, Events, Capabilities,
Integrations, Developer, OpenLineage, and LineageSubscriptions APIs."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from datahub_interoperability.capabilities import CapabilitiesAPI
from datahub_interoperability.developer import DeveloperAPI
from datahub_interoperability.drafts import DraftsAPI
from datahub_interoperability.events import EventsAPI
from datahub_interoperability.integrations import IntegrationsAPI
from datahub_interoperability.lineage_subscriptions import LineageSubscriptionsAPI
from datahub_interoperability.openlineage import OpenLineageAPI
from datahub_interoperability.security import SecurityAPI


def _make_client():
    c = MagicMock()
    c.get = AsyncMock()
    c.post = AsyncMock()
    c.put = AsyncMock()
    c.patch = AsyncMock()
    c.delete = AsyncMock()
    return c


class TestSecurityAPI:
    @pytest.fixture
    def api(self):
        return SecurityAPI(_make_client())

    @pytest.mark.asyncio
    async def test_list_incidents(self, api):
        api.client.get.return_value = {"results": []}
        await api.list_incidents()
        api.client.get.assert_called_once_with(
            "security/incidents/", params={"page": 1, "page_size": 25}
        )

    @pytest.mark.asyncio
    async def test_create_incident(self, api):
        api.client.post.return_value = {"id": "i1"}
        await api.create_incident({"title": "test", "severity": "HIGH"})
        api.client.post.assert_called_once_with(
            "security/incidents/", data={"title": "test", "severity": "HIGH"}
        )


class TestDraftsAPI:
    @pytest.fixture
    def api(self):
        return DraftsAPI(_make_client())

    @pytest.mark.asyncio
    async def test_get_draft(self, api):
        api.client.get.return_value = {"data": {}}
        await api.get_draft("asset", "default")
        api.client.get.assert_called_once_with(
            "drafts/", params={"resource_type": "asset", "draft_key": "default"}
        )

    @pytest.mark.asyncio
    async def test_save_draft(self, api):
        api.client.put.return_value = {"ok": True}
        await api.save_draft("asset", {"name": "test"})
        api.client.put.assert_called_once_with(
            "drafts/save/",
            data={
                "resource_type": "asset",
                "draft_key": "default",
                "data": {"name": "test"},
            },
        )

    @pytest.mark.asyncio
    async def test_delete_draft(self, api):
        await api.delete_draft("asset")
        api.client.delete.assert_called_once_with(
            "drafts/delete/",
            params={"resource_type": "asset", "draft_key": "default"},
        )


class TestEventsAPI:
    @pytest.fixture
    def api(self):
        return EventsAPI(_make_client())

    @pytest.mark.asyncio
    async def test_replay(self, api):
        api.client.post.return_value = {"ok": True}
        await api.replay("ev1")
        api.client.post.assert_called_once_with("events/ev1/replay/")

    @pytest.mark.asyncio
    async def test_dlq_list(self, api):
        api.client.get.return_value = []
        await api.dlq_list()
        api.client.get.assert_called_once_with("events/dlq/")


class TestCapabilitiesAPI:
    @pytest.fixture
    def api(self):
        return CapabilitiesAPI(_make_client())

    @pytest.mark.asyncio
    async def test_list_capabilities(self, api):
        api.client.get.return_value = {"features": {}}
        await api.list_capabilities()
        api.client.get.assert_called_once_with("capabilities/")


class TestIntegrationsAPI:
    @pytest.fixture
    def api(self):
        return IntegrationsAPI(_make_client())

    @pytest.mark.asyncio
    async def test_list_connections(self, api):
        api.client.get.return_value = []
        await api.list_connections()
        api.client.get.assert_called_once_with("integrations/connections/")

    @pytest.mark.asyncio
    async def test_delete_connection(self, api):
        await api.delete_connection("c1")
        api.client.delete.assert_called_once_with("integrations/connections/c1/")


class TestDeveloperAPI:
    @pytest.fixture
    def api(self):
        return DeveloperAPI(_make_client())

    @pytest.mark.asyncio
    async def test_list_plugins(self, api):
        api.client.get.return_value = []
        await api.list_plugins()
        api.client.get.assert_called_once_with("developer/plugins/")

    @pytest.mark.asyncio
    async def test_revoke_api_key(self, api):
        await api.revoke_api_key("k1")
        api.client.delete.assert_called_once_with("developer/api-keys/k1/")


class TestOpenLineageAPI:
    @pytest.fixture
    def api(self):
        return OpenLineageAPI(_make_client())

    @pytest.mark.asyncio
    async def test_list_keys(self, api):
        api.client.get.return_value = []
        await api.list_keys()
        api.client.get.assert_called_once_with("openlineage/keys/")

    @pytest.mark.asyncio
    async def test_status(self, api):
        api.client.get.return_value = {"status": "ok"}
        await api.status()
        api.client.get.assert_called_once_with("openlineage/status/")


class TestLineageSubscriptionsAPI:
    @pytest.fixture
    def api(self):
        return LineageSubscriptionsAPI(_make_client())

    @pytest.mark.asyncio
    async def test_list_subscriptions(self, api):
        api.client.get.return_value = []
        await api.list_subscriptions()
        api.client.get.assert_called_once_with("lineage-subscriptions/")

    @pytest.mark.asyncio
    async def test_delete_subscription(self, api):
        await api.delete_subscription("s1")
        api.client.delete.assert_called_once_with("lineage-subscriptions/s1/")
