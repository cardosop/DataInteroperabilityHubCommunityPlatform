"""
SDK Configuration
"""

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class DataHubClientConfig(BaseModel):
    """
    Configuration for DataHub Client

    Attributes:
        base_url: Base URL for the API (e.g., https://api.hub.example.com/api/v1)
        api_token: API token (JWT or API key) for authentication
        timeout: Request timeout in seconds (default: 30)
        max_retries: Maximum number of retries for transient errors (default: 3)
        user_agent: Custom user agent string
        enable_logging: Enable request/response logging (default: False)
    """

    model_config = ConfigDict(frozen=True)  # Immutable config

    base_url: str = Field(..., description="Base URL for the API")
    api_token: Optional[str] = Field(None, description="API token for authentication")
    timeout: float = Field(30.0, description="Request timeout in seconds")
    max_retries: int = Field(3, description="Maximum number of retries")
    user_agent: str = Field("datahub-interoperability-sdk/1.0.0", description="User agent string")
    enable_logging: bool = Field(False, description="Enable request/response logging")
