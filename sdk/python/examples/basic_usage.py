"""
Basic SDK Usage Examples
"""

import asyncio
import os

from datahub_interoperability import DataHubClient, DataHubClientConfig
from datahub_interoperability.errors import (
    NotFoundError,
    ValidationError,
)


async def list_assets(client: DataHubClient):
    """Example: List assets"""
    try:
        assets = await client.get(
            "/assets/",
            params={
                "status": "ACTIVE",
                "limit": 20,
                "offset": 0,
            },
        )
        print("Assets:", assets)
    except NotFoundError as e:
        print(f"Assets not found: {e.message}")
    except Exception as e:
        print(f"Error: {e}")


async def create_asset(client: DataHubClient):
    """Example: Create asset"""
    try:
        asset = await client.post(
            "/assets/",
            {
                "key": "my-asset",
                "name": "My Asset",
                "description": "Asset description",
                "domain": "marketing",
            },
        )
        print("Created asset:", asset)
    except ValidationError as e:
        print(f"Validation errors: {e.details}")
    except Exception as e:
        print(f"Error: {e}")


async def get_asset(client: DataHubClient, asset_id: str):
    """Example: Get asset by ID"""
    try:
        asset = await client.get(f"/assets/{asset_id}/")
        print("Asset:", asset)
    except NotFoundError as e:
        print(f"Asset {asset_id} not found: {e.message}")
    except Exception as e:
        print(f"Error: {e}")


async def update_asset(client: DataHubClient, asset_id: str):
    """Example: Update asset"""
    try:
        asset = await client.patch(
            f"/assets/{asset_id}/",
            {
                "description": "Updated description",
            },
        )
        print("Updated asset:", asset)
    except Exception as e:
        print(f"Error: {e}")


async def delete_asset(client: DataHubClient, asset_id: str):
    """Example: Delete asset"""
    try:
        await client.delete(f"/assets/{asset_id}/")
        print("Asset deleted")
    except Exception as e:
        print(f"Error: {e}")


async def main():
    """Main example"""
    # Initialize client
    config = DataHubClientConfig(
        base_url=os.getenv("DATAHUB_BASE_URL", "https://api.hub.example.com/api/v1"),
        api_token=os.getenv("DATAHUB_API_TOKEN"),
        enable_logging=True,
    )

    async with DataHubClient(config) as client:
        await list_assets(client)
        await create_asset(client)
        # await get_asset(client, "asset-id")
        # await update_asset(client, "asset-id")
        # await delete_asset(client, "asset-id")


if __name__ == "__main__":
    asyncio.run(main())
