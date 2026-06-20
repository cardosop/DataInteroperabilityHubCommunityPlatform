"""
Data Masking

Implements various data masking strategies for sensitive data.
"""

import hashlib
import re
from enum import Enum
from typing import Any

from .models import ClassificationCategory


class MaskingStrategy(str, Enum):
    """Data masking strategies"""

    REDACT = "REDACT"  # Replace with fixed string
    HASH = "HASH"  # Hash the value
    PARTIAL = "PARTIAL"  # Show partial value (e.g., ***1234)
    FORMAT_PRESERVING = "FORMAT_PRESERVING"  # Preserve format (e.g., ***-***-1234)
    NONE = "NONE"  # No masking


class DataMasker:
    """
    Data masking engine.

    Implements various masking strategies:
    - REDACT: Replace with fixed string
    - HASH: Hash the value
    - PARTIAL: Show partial value
    - FORMAT_PRESERVING: Preserve format
    """

    @staticmethod
    def mask_value(value: Any, strategy: str, config: dict[str, Any] | None = None) -> Any:
        """
        Mask a value based on strategy.

        Args:
            value: Value to mask
            strategy: Masking strategy
            config: Optional masking configuration

        Returns:
            Masked value
        """
        if value is None:
            return None

        if strategy == MaskingStrategy.NONE.value:
            return value

        if strategy == MaskingStrategy.REDACT.value:
            return DataMasker._redact(value, config)
        elif strategy == MaskingStrategy.HASH.value:
            return DataMasker._hash(value, config)
        elif strategy == MaskingStrategy.PARTIAL.value:
            return DataMasker._partial(value, config)
        elif strategy == MaskingStrategy.FORMAT_PRESERVING.value:
            return DataMasker._format_preserving(value, config)
        else:
            return value

    @staticmethod
    def _redact(value: Any, config: dict[str, Any] | None = None) -> str:
        """Redact value (replace with fixed string)"""
        redact_string = (
            config.get("redact_string", "***REDACTED***") if config else "***REDACTED***"
        )
        return redact_string

    @staticmethod
    def _hash(value: Any, config: dict[str, Any] | None = None) -> str:
        """Hash value"""
        algorithm = config.get("algorithm", "sha256") if config else "sha256"
        value_str = str(value)

        if algorithm == "sha256":
            return hashlib.sha256(value_str.encode()).hexdigest()
        elif algorithm == "md5":
            return hashlib.md5(value_str.encode()).hexdigest()
        else:
            return hashlib.sha256(value_str.encode()).hexdigest()

    @staticmethod
    def _partial(value: Any, config: dict[str, Any] | None = None) -> str:
        """Show partial value"""
        value_str = str(value)

        if not value_str:
            return value_str

        # Default: show last 4 characters
        show_chars = config.get("show_chars", 4) if config else 4
        mask_char = config.get("mask_char", "*") if config else "*"

        if len(value_str) <= show_chars:
            return mask_char * len(value_str)

        masked_length = len(value_str) - show_chars
        return mask_char * masked_length + value_str[-show_chars:]

    @staticmethod
    def _format_preserving(value: Any, config: dict[str, Any] | None = None) -> str:
        """Preserve format while masking"""
        value_str = str(value)

        if not value_str:
            return value_str

        mask_char = config.get("mask_char", "*") if config else "*"
        show_last = config.get("show_last", 4) if config else 4

        # Detect format patterns (SSN before phone so 123-45-6789 is not treated as phone)
        # SSN: 123-45-6789 -> ***-**-6789
        ssn_pattern = r"^\d{3}-\d{2}-\d{4}$"
        if re.match(ssn_pattern, value_str):
            return f"{mask_char * 3}-{mask_char * 2}-{value_str[-4:]}"

        # Email: user@domain.com -> ***@domain.com
        if "@" in value_str:
            parts = value_str.split("@")
            if len(parts) == 2:
                masked_local = mask_char * min(len(parts[0]), 3)
                return f"{masked_local}@{parts[1]}"

        # Phone: (123) 456-7890 -> (***) ***-7890
        phone_pattern = r"^(\+?\d{1,3}[-.\s]?)?\(?\d{1,4}\)?[-.\s]?\d{1,4}[-.\s]?\d{1,9}$"
        if re.match(
            phone_pattern,
            value_str.replace(" ", "").replace("-", "").replace("(", "").replace(")", ""),
        ):
            # Mask all but last 4 digits
            digits = re.sub(r"\D", "", value_str)
            if len(digits) >= 4:
                masked = mask_char * (len(digits) - 4) + digits[-4:]
                # Try to preserve format
                if "-" in value_str:
                    return f"{mask_char * 3}-{mask_char * 3}-{masked[-4:]}"
                elif "(" in value_str:
                    return f"({mask_char * 3}) {mask_char * 3}-{masked[-4:]}"
                else:
                    return masked

        # Credit card: 1234-5678-9012-3456 -> ****-****-****-3456
        cc_pattern = r"^\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}$"
        if re.match(cc_pattern, value_str.replace(" ", "").replace("-", "")):
            digits = re.sub(r"\D", "", value_str)
            if len(digits) == 16:
                return f"{mask_char * 4}-{mask_char * 4}-{mask_char * 4}-{digits[-4:]}"

        # Default: show last N characters
        if len(value_str) <= show_last:
            return mask_char * len(value_str)

        return mask_char * (len(value_str) - show_last) + value_str[-show_last:]

    @staticmethod
    def mask_dataset_row(
        row: dict[str, Any],
        dataset_id: str,
        tenant_id: str,
        user_id: str,
        access_type: str = "READ",
    ) -> dict[str, Any]:
        """
        Mask a dataset row based on field access policies.

        Args:
            row: Dataset row (dictionary of field_name -> value)
            dataset_id: Dataset UUID
            tenant_id: Tenant UUID
            user_id: User UUID
            access_type: Access type (READ, WRITE)

        Returns:
            Masked row dictionary
        """
        from .abac import ABACEngine

        masked_row = {}

        for field_name, value in row.items():
            # Check field-level access
            result = ABACEngine.evaluate_access(
                user_id=user_id,
                tenant_id=tenant_id,
                resource_type="DATASET",
                resource_id=dataset_id,
                access_type=access_type,
                field_name=field_name,
            )

            if not result.allowed:
                # Deny access to this field
                masked_row[field_name] = None
            elif result.masking_required and result.field_policies:
                # Apply masking
                field_policy = result.field_policies[0]  # Use first matching policy
                masked_value = DataMasker.mask_value(
                    value=value,
                    strategy=field_policy.masking_strategy or MaskingStrategy.REDACT.value,
                    config=field_policy.masking_config,
                )
                masked_row[field_name] = masked_value
            else:
                # No masking required
                masked_row[field_name] = value

        return masked_row

    @staticmethod
    def mask_based_on_classification(
        value: Any, classification: ClassificationCategory, config: dict[str, Any] | None = None
    ) -> Any:
        """
        Mask value based on classification.

        Args:
            value: Value to mask
            classification: Classification category
            config: Optional masking configuration

        Returns:
            Masked value
        """
        # Determine strategy based on classification
        strategy_map = {
            ClassificationCategory.PUBLIC.value: MaskingStrategy.NONE.value,
            ClassificationCategory.INTERNAL.value: MaskingStrategy.PARTIAL.value,
            ClassificationCategory.CONFIDENTIAL.value: MaskingStrategy.PARTIAL.value,
            ClassificationCategory.RESTRICTED.value: MaskingStrategy.REDACT.value,
            ClassificationCategory.PII.value: MaskingStrategy.FORMAT_PRESERVING.value,
            ClassificationCategory.PHI.value: MaskingStrategy.REDACT.value,
            ClassificationCategory.PCI.value: MaskingStrategy.REDACT.value,
            ClassificationCategory.FINANCIAL.value: MaskingStrategy.PARTIAL.value,
            ClassificationCategory.LEGAL.value: MaskingStrategy.REDACT.value,
        }

        strategy = strategy_map.get(classification.value, MaskingStrategy.PARTIAL.value)

        return DataMasker.mask_value(value, strategy, config)
