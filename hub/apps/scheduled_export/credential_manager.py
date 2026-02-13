"""
Credential Manager for Scheduled Export

Provides secure credential masking for destination configurations.
"""

import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)


class CredentialManager:
    """
    Manager for handling credentials for scheduled exports.

    Provides:
    - Credential masking (never expose actual credentials)
    """

    # Fields that should be masked in credentials
    SENSITIVE_FIELDS = [
        "password",
        "secret",
        "secret_key",
        "secret_access_key",
        "access_key_secret",
        "api_key",
        "api_secret",
        "token",
        "auth_token",
        "private_key",
        "private_key_data",
        "passphrase",
        "credential",
        "credentials",
        "account_key",
        "sas_token",
        "connection_string",
    ]

    @staticmethod
    def get_masked_credentials(scheduled_export) -> Dict[str, Any]:
        """
        Get masked credentials for a scheduled export.

        Args:
            scheduled_export: ScheduledExport instance

        Returns:
            Dictionary with masked credentials (sensitive fields masked)
        """
        destination_config = scheduled_export.destination_config or {}
        masked_config = {}

        # Define sensitive fields to mask based on destination type
        sensitive_fields_map = {
            "S3": ["secret_access_key", "access_key_id"],
            "GCS": ["credentials_json", "private_key", "service_account_key"],
            "AZURE_BLOB": ["account_key", "sas_token", "connection_string"],
        }

        # Get sensitive fields for this destination type
        destination_type = scheduled_export.destination_type
        fields_to_mask = sensitive_fields_map.get(
            destination_type, CredentialManager.SENSITIVE_FIELDS
        )

        for key, value in destination_config.items():
            key_lower = key.lower()

            # Check if this is a sensitive field
            is_sensitive = any(
                sensitive_field in key_lower for sensitive_field in fields_to_mask
            ) or any(
                sensitive_field in key_lower
                for sensitive_field in CredentialManager.SENSITIVE_FIELDS
            )

            if is_sensitive and value:
                # Mask the value
                if isinstance(value, str):
                    if len(value) <= 4:
                        masked_config[key] = "****"
                    else:
                        # Show first 4 chars and mask the rest (e.g., AKIA***)
                        masked_config[key] = f"{value[:4]}***"
                else:
                    masked_config[key] = "****"
            else:
                # Non-sensitive field - include as-is
                masked_config[key] = value

        return masked_config
