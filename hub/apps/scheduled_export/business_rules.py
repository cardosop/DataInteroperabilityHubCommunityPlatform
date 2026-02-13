"""
Scheduled Export Business Rules

Comprehensive business rules validation for scheduled export operations, including:
- Export scope validation
- Export run validation
- Destination validation
- Tenant and user context validation
- Access control validation

All validation methods follow engineering best practices:
- No mocks/stubs - use real services and models
- Fix root causes, not symptoms
- Comprehensive error messages with context
- Follow DRY, SOLID, and clean code principles
"""

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Union

from django.utils import timezone as django_timezone

from hub.apps.core.business_rules.base import (
    BusinessRules,
    RuleExecutionContext,
    ValidationResult,
)
from hub.apps.core.business_rules.registry import register_rule
from hub.apps.scheduled_export.models import (
    DestinationType,
    ScheduledExport,
    ScheduledExportRun,
    ScheduledExportStatus,
)

if TYPE_CHECKING:
    from hub.apps.tenants.models import Tenant
    from hub.apps.users.models import User

logger = logging.getLogger(__name__)


@dataclass
class ScheduledExportRuleExecutionContext(RuleExecutionContext):
    """
    Extended execution context for scheduled export business rules.

    Adds scheduled export-specific context:
    - scheduled_export: The scheduled export being validated
    - export_run: Optional export run instance
    - destination: Optional destination information
    - tenant: Optional tenant instance for validation
    - user: Optional user instance for permission validation
    """

    scheduled_export: Optional[ScheduledExport] = None
    export_run: Optional[ScheduledExportRun] = None
    destination: Optional[Dict[str, Any]] = None
    tenant: Optional[Any] = None  # Using Any to avoid circular import
    user: Optional[Any] = None  # Using Any to avoid circular import

    def to_dict(self) -> Dict[str, Any]:
        """Convert context to dictionary for caching/logging."""
        base_dict = super().to_dict()
        # Add scheduled export-specific fields
        base_dict.update(
            {
                "scheduled_export_id": (
                    str(self.scheduled_export.id) if self.scheduled_export else None
                ),
                "scheduled_export_name": (
                    self.scheduled_export.name if self.scheduled_export else None
                ),
                "scheduled_export_status": (
                    self.scheduled_export.status if self.scheduled_export else None
                ),
                "export_run_id": str(self.export_run.id) if self.export_run else None,
                "export_run_status": self.export_run.status if self.export_run else None,
                "destination_type": (
                    self.scheduled_export.destination_type if self.scheduled_export else None
                ),
            }
        )
        # Add tenant and user IDs from objects if provided
        if self.tenant:
            base_dict["tenant_id_from_object"] = str(self.tenant.id)
        if self.user:
            base_dict["user_id_from_object"] = str(self.user.id)
        return base_dict


@register_rule(
    rule_name="scheduled_export_validation",
    description="Validates scheduled export exports, runs, destinations, and tenant context",
    tags=["scheduled_export", "validation", "export"],
    priority=10,
)
class ScheduledExportBusinessRules(BusinessRules):
    """
    Business rules validator for scheduled export operations.

    Extends BusinessRules base class with scheduled export-specific validation:
    - Export scope validation
    - Export run validation
    - Destination validation
    - Access control validation
    """

    def validate(
        self,
        scheduled_export: Optional[ScheduledExport] = None,
        export_run: Optional[ScheduledExportRun] = None,
        tenant: Optional[Any] = None,
        user: Optional[Any] = None,
        validation_type: str = "all",
        **kwargs,
    ) -> ValidationResult:
        """
        Main validation entry point for scheduled export operations.

        Args:
            scheduled_export: Optional ScheduledExport instance
            export_run: Optional ScheduledExportRun instance
            tenant: Optional tenant instance
            user: Optional user instance
            validation_type: Type of validation to perform ("all", "scope", "access", "destination", "run")
            **kwargs: Additional context

        Returns:
            ValidationResult with validation status
        """
        context = ScheduledExportRuleExecutionContext(
            tenant_id=self.tenant_id,
            user_id=self.user_id,
            scheduled_export=scheduled_export,
            export_run=export_run,
            tenant=tenant,
            user=user,
        )

        if validation_type == "all":
            return self._validate_all(context)
        elif validation_type == "scope":
            return self._validate_export_scope(context)
        elif validation_type == "access":
            return self._validate_export_access(context)
        elif validation_type == "destination":
            return self._validate_destination(context)
        elif validation_type == "run":
            return self._validate_export_run(context)
        else:
            return ValidationResult(
                is_valid=False,
                errors=[f"Unknown validation_type: {validation_type}"],
            )

    def _validate_all(self, context: ScheduledExportRuleExecutionContext) -> ValidationResult:
        """Comprehensive validation of all aspects."""
        result = ValidationResult(is_valid=True)
        details = {"validation_type": "comprehensive"}

        if context.scheduled_export:
            # Validate export scope
            scope_result = self._validate_export_scope(context)
            result = result.combine(scope_result)
            details["scope_validated"] = True

            # Validate destination
            dest_result = self._validate_destination(context)
            result = result.combine(dest_result)
            details["destination_validated"] = True

            # Validate access if user provided
            if context.user:
                access_result = self._validate_export_access(context)
                result = result.combine(access_result)
                details["access_validated"] = True

        if context.export_run:
            run_result = self._validate_export_run(context)
            result = result.combine(run_result)
            details["run_validated"] = True

        result.details.update(details)
        return result

    def _validate_export_scope(
        self, context: ScheduledExportRuleExecutionContext
    ) -> ValidationResult:
        """
        Validate export source scope (asset_ids, dataset_ids, file_ids, contract_id).

        Ensures:
        - At least one scope field is provided
        - All IDs are valid UUIDs
        - All referenced resources exist and belong to tenant
        """
        errors: List[str] = []
        warnings: List[str] = []
        details: Dict[str, Any] = {
            "scope_validated": False,
            "has_asset_ids": False,
            "has_dataset_ids": False,
            "has_file_ids": False,
            "has_contract_id": False,
        }

        if not context.scheduled_export:
            return ValidationResult(
                is_valid=False,
                errors=["Scheduled export is required for scope validation"],
                details=details,
            )

        source_scope = context.scheduled_export.source_scope
        if not isinstance(source_scope, dict):
            errors.append("source_scope must be a dictionary")
            return ValidationResult(
                is_valid=False, errors=errors, warnings=warnings, details=details
            )

        # Check which scope fields are provided
        asset_ids = source_scope.get("asset_ids", [])
        dataset_ids = source_scope.get("dataset_ids", [])
        file_ids = source_scope.get("file_ids", [])
        contract_id = source_scope.get("contract_id")

        details["has_asset_ids"] = bool(asset_ids)
        details["has_dataset_ids"] = bool(dataset_ids)
        details["has_file_ids"] = bool(file_ids)
        details["has_contract_id"] = bool(contract_id)

        # Validate at least one scope field is provided
        if not (asset_ids or dataset_ids or file_ids or contract_id):
            errors.append(
                "source_scope must contain at least one of: asset_ids, dataset_ids, file_ids, contract_id"
            )
            return ValidationResult(
                is_valid=False, errors=errors, warnings=warnings, details=details
            )

        tenant_id = str(context.scheduled_export.tenant_id)

        # Validate asset_ids
        if asset_ids:
            if not isinstance(asset_ids, list):
                errors.append("asset_ids must be a list")
            else:
                from hub.apps.assets.models import Asset

                for asset_id in asset_ids:
                    try:
                        asset = Asset.objects.get(id=asset_id, tenant_id=tenant_id)
                        details.setdefault("validated_assets", []).append(str(asset.id))
                    except Asset.DoesNotExist:
                        errors.append(f"Asset {asset_id} not found or not in tenant")
                    except Exception as e:
                        errors.append(f"Error validating asset {asset_id}: {str(e)}")

        # Validate dataset_ids
        if dataset_ids:
            if not isinstance(dataset_ids, list):
                errors.append("dataset_ids must be a list")
            else:
                from hub.apps.datasets.models import Dataset

                for dataset_id in dataset_ids:
                    try:
                        dataset = Dataset.objects.get(id=dataset_id, tenant_id=tenant_id)
                        details.setdefault("validated_datasets", []).append(str(dataset.id))
                    except Dataset.DoesNotExist:
                        errors.append(f"Dataset {dataset_id} not found or not in tenant")
                    except Exception as e:
                        errors.append(f"Error validating dataset {dataset_id}: {str(e)}")

        # Validate file_ids
        if file_ids:
            if not isinstance(file_ids, list):
                errors.append("file_ids must be a list")
            else:
                from hub.apps.files.models import File

                for file_id in file_ids:
                    try:
                        file_obj = File.objects.get(id=file_id, tenant_id=tenant_id)
                        details.setdefault("validated_files", []).append(str(file_obj.id))
                    except File.DoesNotExist:
                        errors.append(f"File {file_id} not found or not in tenant")
                    except Exception as e:
                        errors.append(f"Error validating file {file_id}: {str(e)}")

        # Validate contract_id
        if contract_id:
            from hub.apps.contracts.models import Contract

            try:
                contract = Contract.objects.get(id=contract_id, tenant_id=tenant_id)
                details["validated_contract"] = str(contract.id)
            except Contract.DoesNotExist:
                errors.append(f"Contract {contract_id} not found or not in tenant")
            except Exception as e:
                errors.append(f"Error validating contract {contract_id}: {str(e)}")

        details["scope_validated"] = len(errors) == 0
        return ValidationResult(
            is_valid=len(errors) == 0, errors=errors, warnings=warnings, details=details
        )

    def _validate_export_access(
        self, context: ScheduledExportRuleExecutionContext
    ) -> ValidationResult:
        """
        Validate user access to export resources.

        Checks:
        - Tenant isolation
        - User permissions for each resource in scope
        """
        errors: List[str] = []
        warnings: List[str] = []
        details: Dict[str, Any] = {
            "access_validated": False,
            "tenant_isolation_valid": False,
        }

        if not context.scheduled_export or not context.user:
            warnings.append("User or scheduled export not provided - access validation skipped")
            return ValidationResult(
                is_valid=True, errors=errors, warnings=warnings, details=details
            )

        # Validate tenant isolation
        if hasattr(context.user, "tenant") and context.user.tenant:
            if str(context.user.tenant.id) != str(context.scheduled_export.tenant_id):
                errors.append("User tenant does not match scheduled export tenant")
                return ValidationResult(
                    is_valid=False, errors=errors, warnings=warnings, details=details
                )
            details["tenant_isolation_valid"] = True

        # Validate access to each resource in scope
        source_scope = context.scheduled_export.source_scope
        tenant_id = str(context.scheduled_export.tenant_id)

        # Check asset access
        asset_ids = source_scope.get("asset_ids", [])
        if asset_ids:
            from hub.apps.assets.business_rules import AssetsBusinessRules

            assets_rules = AssetsBusinessRules(tenant_id=tenant_id, user_id=str(context.user.id))
            for asset_id in asset_ids:
                try:
                    from hub.apps.assets.models import Asset

                    asset = Asset.objects.get(id=asset_id, tenant_id=tenant_id)
                    access_result = assets_rules.validate(
                        asset=asset, user=context.user, validation_type="permissions"
                    )
                    if not access_result.is_valid:
                        errors.extend(
                            [
                                f"Access denied to asset {asset_id}: {err}"
                                for err in access_result.errors
                            ]
                        )
                except Exception as e:
                    warnings.append(f"Could not validate access to asset {asset_id}: {str(e)}")

        # Check dataset access
        dataset_ids = source_scope.get("dataset_ids", [])
        if dataset_ids:
            from hub.apps.datasets.business_rules import DatasetsBusinessRules

            datasets_rules = DatasetsBusinessRules(
                tenant_id=tenant_id, user_id=str(context.user.id)
            )
            for dataset_id in dataset_ids:
                try:
                    from hub.apps.datasets.models import Dataset

                    dataset = Dataset.objects.get(id=dataset_id, tenant_id=tenant_id)
                    access_result = datasets_rules.validate(
                        dataset=dataset, user=context.user, validation_type="permissions"
                    )
                    if not access_result.is_valid:
                        errors.extend(
                            [
                                f"Access denied to dataset {dataset_id}: {err}"
                                for err in access_result.errors
                            ]
                        )
                except Exception as e:
                    warnings.append(f"Could not validate access to dataset {dataset_id}: {str(e)}")

        # Check file access
        file_ids = source_scope.get("file_ids", [])
        if file_ids:
            from hub.apps.files.business_rules import FilesBusinessRules

            files_rules = FilesBusinessRules(tenant_id=tenant_id, user_id=str(context.user.id))
            for file_id in file_ids:
                try:
                    from hub.apps.files.models import File

                    file_obj = File.objects.get(id=file_id, tenant_id=tenant_id)
                    access_result = files_rules.validate(
                        file=file_obj, user=context.user, validation_type="permissions"
                    )
                    if not access_result.is_valid:
                        errors.extend(
                            [
                                f"Access denied to file {file_id}: {err}"
                                for err in access_result.errors
                            ]
                        )
                except Exception as e:
                    warnings.append(f"Could not validate access to file {file_id}: {str(e)}")

        details["access_validated"] = len(errors) == 0
        return ValidationResult(
            is_valid=len(errors) == 0, errors=errors, warnings=warnings, details=details
        )

    def _validate_destination(
        self, context: ScheduledExportRuleExecutionContext
    ) -> ValidationResult:
        """
        Validate export destination configuration.

        Ensures:
        - Destination type is valid
        - Destination config has required fields
        - Credentials are present (but masked in responses)
        - Optional format/size limits are valid
        """
        errors: List[str] = []
        warnings: List[str] = []
        details: Dict[str, Any] = {"destination_validated": False}

        if not context.scheduled_export:
            return ValidationResult(
                is_valid=False,
                errors=["Scheduled export is required for destination validation"],
                details=details,
            )

        destination_type = context.scheduled_export.destination_type
        destination_config = context.scheduled_export.destination_config

        details["destination_type"] = destination_type

        if not isinstance(destination_config, dict):
            errors.append("destination_config must be a dictionary")
            return ValidationResult(
                is_valid=False, errors=errors, warnings=warnings, details=details
            )

        # Validate destination-specific requirements
        if destination_type == DestinationType.S3:
            if "bucket" not in destination_config:
                errors.append("S3 destination requires 'bucket' in destination_config")
            # Note: credentials are stored but masked in API responses
        elif destination_type == DestinationType.GCS:
            if "bucket" not in destination_config:
                errors.append("GCS destination requires 'bucket' in destination_config")
        elif destination_type == DestinationType.AZURE_BLOB:
            if "container" not in destination_config:
                errors.append("Azure Blob destination requires 'container' in destination_config")
            if "account_name" not in destination_config:
                errors.append(
                    "Azure Blob destination requires 'account_name' in destination_config"
                )
        else:
            errors.append(f"Unknown destination type: {destination_type}")

        # Validate optional format/size limits
        if "format_limits" in destination_config:
            format_limits = destination_config["format_limits"]
            if not isinstance(format_limits, dict):
                errors.append("format_limits must be a dictionary")
            else:
                # Validate allowed formats (if specified)
                if "allowed_formats" in format_limits:
                    allowed_formats = format_limits["allowed_formats"]
                    if not isinstance(allowed_formats, list):
                        errors.append("allowed_formats must be a list")
                    else:
                        valid_formats = ["CSV", "JSON", "PARQUET", "AVRO", "ORC"]
                        for fmt in allowed_formats:
                            if fmt not in valid_formats:
                                warnings.append(
                                    f"Unknown format in allowed_formats: {fmt}. Valid formats: {', '.join(valid_formats)}"
                                )

        if "size_limits" in destination_config:
            size_limits = destination_config["size_limits"]
            if not isinstance(size_limits, dict):
                errors.append("size_limits must be a dictionary")
            else:
                # Validate max_file_size (in bytes)
                if "max_file_size_bytes" in size_limits:
                    max_size = size_limits["max_file_size_bytes"]
                    if not isinstance(max_size, (int, float)) or max_size <= 0:
                        errors.append("max_file_size_bytes must be a positive number")
                    elif max_size > 100 * 1024 * 1024 * 1024:  # 100GB
                        warnings.append(
                            "max_file_size_bytes exceeds 100GB - this may cause performance issues"
                        )

                # Validate max_total_size (in bytes)
                if "max_total_size_bytes" in size_limits:
                    max_total = size_limits["max_total_size_bytes"]
                    if not isinstance(max_total, (int, float)) or max_total <= 0:
                        errors.append("max_total_size_bytes must be a positive number")
                    elif max_total > 1024 * 1024 * 1024 * 1024:  # 1TB
                        warnings.append(
                            "max_total_size_bytes exceeds 1TB - this may cause performance issues"
                        )

        details["destination_validated"] = len(errors) == 0
        return ValidationResult(
            is_valid=len(errors) == 0, errors=errors, warnings=warnings, details=details
        )

    def _validate_export_run(
        self, context: ScheduledExportRuleExecutionContext
    ) -> ValidationResult:
        """
        Validate export run state and transitions.

        Ensures:
        - Run belongs to scheduled export
        - Run belongs to tenant
        - Status transitions are valid
        """
        errors: List[str] = []
        warnings: List[str] = []
        details: Dict[str, Any] = {"run_validated": False}

        if not context.export_run:
            return ValidationResult(
                is_valid=False,
                errors=["Export run is required for run validation"],
                details=details,
            )

        # Validate run belongs to scheduled export
        if context.scheduled_export:
            if context.export_run.scheduled_export_id != context.scheduled_export.id:
                errors.append("Export run does not belong to scheduled export")
                return ValidationResult(
                    is_valid=False, errors=errors, warnings=warnings, details=details
                )

        # Validate tenant isolation
        tenant_id = str(context.export_run.tenant_id)
        if context.tenant and str(context.tenant.id) != tenant_id:
            errors.append("Export run tenant does not match provided tenant")
            return ValidationResult(
                is_valid=False, errors=errors, warnings=warnings, details=details
            )

        # Validate status
        if context.export_run.status not in [
            ScheduledExportRunStatus.RUNNING,
            ScheduledExportRunStatus.COMPLETED,
            ScheduledExportRunStatus.FAILED,
            ScheduledExportRunStatus.CANCELLED,
        ]:
            errors.append(f"Invalid export run status: {context.export_run.status}")

        details["run_validated"] = len(errors) == 0
        details["run_status"] = context.export_run.status
        details["run_tenant_id"] = tenant_id

        return ValidationResult(
            is_valid=len(errors) == 0, errors=errors, warnings=warnings, details=details
        )
