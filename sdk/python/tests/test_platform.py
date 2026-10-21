"""283.5.16 — SDK unit tests for PlatformAPI."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from datahub_interoperability.platform import PlatformAPI


class TestPlatformAPI:
    @pytest.fixture
    def api(self):
        client = MagicMock()
        client.get = AsyncMock()
        client.post = AsyncMock()
        client.patch = AsyncMock()
        client.delete = AsyncMock()
        return PlatformAPI(client)

    @pytest.mark.asyncio
    async def test_list_tenants(self, api):
        api.client.get.return_value = {"results": []}
        result = await api.list_tenants(page=1, page_size=25)
        api.client.get.assert_called_once_with(
            "platform/tenants/", params={"page": 1, "page_size": 25}
        )
        assert result == {"results": []}

    @pytest.mark.asyncio
    async def test_create_tenant(self, api):
        api.client.post.return_value = {"id": "t1", "slug": "test"}
        result = await api.create_tenant(
            {"slug": "test", "display_name": "T", "admin_email": "a@b.com"}
        )
        api.client.post.assert_called_once_with(
            "platform/tenants/",
            data={"slug": "test", "display_name": "T", "admin_email": "a@b.com"},
        )
        assert result["id"] == "t1"

    @pytest.mark.asyncio
    async def test_delete_tenant(self, api):
        await api.delete_tenant("t1")
        api.client.delete.assert_called_once_with("platform/tenants/t1/")
