"""
Authentication operations for DataHub SDK.
"""

from typing import Any, Dict, Optional

from .client import DataHubClient


class AuthAPI:
    def __init__(self, client: DataHubClient):
        self.client = client

    async def login(self, email: str, password: str) -> Dict[str, Any]:
        return await self.client.post("auth/login/", data={"email": email, "password": password})

    async def register(
        self,
        email: str,
        password: str,
        display_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        data: Dict[str, Any] = {"email": email, "password": password}
        if display_name:
            data["display_name"] = display_name
        return await self.client.post("auth/register/", data=data)

    async def refresh_token(self, refresh_token: str) -> Dict[str, Any]:
        return await self.client.post("auth/token/refresh/", data={"refresh_token": refresh_token})

    async def logout(self) -> None:
        await self.client.post("auth/logout/")

    async def list_sessions(self) -> Dict[str, Any]:
        return await self.client.get("auth/sessions/")

    async def get_profile(self) -> Dict[str, Any]:
        return await self.client.get("auth/me/")

    async def update_profile(self, **kwargs: Any) -> Dict[str, Any]:
        return await self.client.patch("auth/me/", data=kwargs)
