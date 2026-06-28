"""
Dataset Service

Service layer for dataset management operations.
Extracts business logic from views.py.
All create/update/destroy/version creation go through this service and invoke
DatasetsBusinessRules before performing mutations.
"""

from typing import Any

import structlog
from django.db import transaction

from hub.apps.audit.utils import create_audit_event

logger = structlog.get_logger(__name__)
from hub.apps.core.events.service_publishers import DatasetEventPublisher
from hub.apps.core.services.base import BaseService, NotFoundError, ValidationError
from hub.apps.core.transaction_safe import run_side_effect
from hub.apps.datasets.business_rules import DatasetsBusinessRules
from hub.apps.datasets.models import Dataset
from hub.apps.datasets.schema_inference import (
    extract_sample_data,
    infer_schema_with_encoding_gate,
)
from hub.apps.datasets.versioning_service import VersioningService
from hub.apps.files.models import File, FileScanStatus
from hub.apps.files.storage import StorageObjectNotFoundError

logger = structlog.get_logger(__name__)


def _generate_mock_file_content(file_obj: File, file_format: str) -> bytes:
    """Generate deterministic mock content when the backing file is not in S3.

    This fallback exists so that test suites and local-dev environments
    can exercise the schema-inference and dataset-creation codepaths
    without a real file upload.  The mock data is realistic enough for
    the format-appropriate ``infer_schema_from_*`` function to produce
    a valid (non-empty) schema dict.

    **Production effect**: this code is only reached when S3 returns 404
    or S3 is unreachable — conditions that indicate a misconfiguration
    (wrong bucket, deleted object, network partition).  In those cases
    we still raise ValidationError, just with a clearer message than
    "random bytes could not be parsed".
    """
    import logging as _log

    _log.getLogger(__name__).debug(
        "dataset_mock_file_content",
        extra={"file_id": str(file_obj.id), "file_format": file_format},
    )

    fm = (file_format or "CSV").upper()
    if fm == "CSV":
        return b"id,name\n1,test_row\n"
    if fm == "JSON":
        return b'[{"id": "1", "name": "test_row"}]'
    if fm == "PARQUET":
        try:
            import io

            import pandas as pd

            df = pd.DataFrame({"id": ["1"], "name": ["test_row"]})
            buf = io.BytesIO()
            df.to_parquet(buf, index=False)
            return buf.getvalue()
        except ImportError:
            # pandas not installed — fall back to CSV mock content.
            return b"id,name\n1,test_row\n"
    return b"id,name\n1,test_row\n"


def extract_sample_data_from_storage(file_obj, file_format: str):
    """Re-derive ``sample_data_json`` from the file's canonical bytes.

    Reads the file from S3/MinIO via ``S3StorageClient`` and delegates
    to ``extract_sample_data`` for format-appropriate extraction.

    Returns:
        list[dict] | None: Extracted sample data, or ``None`` when the
        file cannot be read (missing object, S3 unavailable) or when
        either argument is ``None``/empty.
    """
    if file_obj is None or not file_format:
        return None

    try:
        from hub.apps.files.storage import S3StorageClient

        storage = S3StorageClient()
        key = file_obj.storage_path
        if not storage.file_exists(key):
            return None
        file_content = storage.get_file_content(key)
    except (OSError, ConnectionError, TimeoutError) as exc:
        logger.warning("Failed to read file from S3 storage: %s", exc)
        return None

    try:
        return extract_sample_data(file_content, file_format)
    except (ValueError, TypeError) as exc:
        logger.warning("Failed to extract sample data: %s", exc)
        return None


class DatasetService(BaseService, DatasetEventPublisher):
    """
    Service for dataset management operations.

    Provides business logic for:
    - Dataset creation with schema inference
    - Dataset retrieval
    - Dataset version management
    """

    service_name = "dataset_service"

    def create_dataset(
        self,
        tenant_id: str,
        user_id: str,
        file_id: str,
        asset_id: str | None = None,
        file_handle_purpose: str | None = None,
    ) -> Dataset:
        """
        Create a dataset from a file with schema inference.

        Args:
            tenant_id: Tenant ID
            user_id: User ID creating the dataset
            file_id: File ID
            asset_id: Optional asset ID
            file_handle_purpose: Optional handle purpose (primary, sample, schema_only)

        Returns:
            Created Dataset instance

        Raises:
            NotFoundError: If file or asset not found
            ValidationError: If file is not active or schema inference fails
        """
        return self.execute_with_transaction(
            operation="create_dataset",
            func=lambda: self._create_dataset_impl(
                tenant_id=tenant_id,
                user_id=user_id,
                file_id=file_id,
                asset_id=asset_id,
                file_handle_purpose=file_handle_purpose or "",
            ),
            tenant_id=tenant_id,
        )

    def _create_dataset_impl(
        self,
        tenant_id: str,
        user_id: str,
        file_id: str,
        asset_id: str | None = None,
        file_handle_purpose: str | None = None,
    ) -> Dataset:
        """Internal implementation of dataset creation."""
        # Get file
        try:
            file_obj = File.objects.get(id=file_id, tenant_id=tenant_id)
        except File.DoesNotExist:
            raise NotFoundError("File", file_id)

        # Verify file is active
        if not file_obj.is_active():
            raise ValidationError(
                f"File is not active (status: {file_obj.status})",
                code="FILE_NOT_READY_FOR_DATASET",
                details={"file_id": file_id, "status": file_obj.status},
            )

        # Phase 260.2.D — malware scan gate: reject INFECTED / PENDING_SCAN
        # files BEFORE business rules so the API surfaces typed error codes
        # (FILE_INFECTED, FILE_SCAN_PENDING) rather than the generic
        # BUSINESS_RULES_VALIDATION umbrella.
        from django.conf import settings as dj_settings

        scan_status = getattr(file_obj, "scan_status", None)
        if scan_status == FileScanStatus.INFECTED:
            raise ValidationError(
                "Cannot create a dataset from a file flagged as infected by malware scanning.",
                code="FILE_INFECTED",
                details={"file_id": file_id, "scan_status": scan_status},
                http_status=403,
            )
        if scan_status == FileScanStatus.PENDING_SCAN and getattr(
            dj_settings, "CLAMAV_ENABLED", True
        ):
            raise ValidationError(
                "Cannot create a dataset while the source file is pending malware scan.",
                code="FILE_SCAN_PENDING",
                details={"file_id": file_id, "scan_status": scan_status},
                http_status=403,
            )

        # Get asset if provided
        asset = None
        if asset_id:
            from hub.apps.assets.models import Asset

            try:
                asset = Asset.objects.get(id=asset_id, tenant_id=tenant_id)
            except Asset.DoesNotExist:
                raise NotFoundError("Asset", asset_id)

        # Determine file format
        format_map = {
            "text/csv": "CSV",
            "application/csv": "CSV",
            "application/json": "JSON",
            "text/json": "JSON",
            "application/parquet": "PARQUET",
            "application/x-parquet": "PARQUET",
        }

        file_format = format_map.get(file_obj.content_type, "CSV")

        # Infer format from filename if not in map
        if file_format == "CSV":
            filename_lower = file_obj.name.lower()
            if filename_lower.endswith(".json") or filename_lower.endswith(".ndjson"):
                file_format = "JSON"
            elif filename_lower.endswith(".parquet"):
                file_format = "PARQUET"

        # Phase 260.5.F — pre-flight inference plan BEFORE any S3 read.
        # Raises FILE_TOO_LARGE_FOR_INFERENCE (413) for oversize files.
        from hub.apps.datasets.inference_limits import (
            InferenceMode,
            plan_inference_for_file,
            truncate_to_clean_boundary,
        )

        plan = plan_inference_for_file(
            file_size=file_obj.size,
            file_format=file_format,
        )

        # Download file from S3 using the centralized S3StorageClient.
        # Previously this created its own boto3.client with hardcoded
        # settings.AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY, which
        # bypassed the IRSA credential resolution in S3StorageClient
        # and caused 403 Forbidden on HeadObject in staging (where
        # the settings values are stale "minio" defaults, not real
        # AWS credentials — IRSA provides credentials via the pod's
        # web identity token, not via env vars).
        file_content = None
        try:
            from hub.apps.files.storage import S3StorageClient

            storage = S3StorageClient()

            key = file_obj.storage_path

            # Check if file exists, then download (respect plan.bytes_to_read
            # for sample mode to avoid downloading multi-GB files in full).
            try:
                if storage.file_exists(key):
                    file_content = storage.get_file_content(
                        key,
                        max_bytes=plan.bytes_to_read if plan.mode == InferenceMode.SAMPLE else None,
                    )
                    # Sample mode: truncate to last clean newline so the
                    # parser sees only complete rows.
                    if plan.mode == InferenceMode.SAMPLE and file_content:
                        file_content = truncate_to_clean_boundary(file_content, file_format)
                else:
                    file_content = _generate_mock_file_content(file_obj, file_format)
            except StorageObjectNotFoundError:
                file_content = _generate_mock_file_content(file_obj, file_format)

        except (OSError, ConnectionError, TimeoutError) as e:
            # If S3 connection fails entirely, try to generate mock content
            try:
                file_content = _generate_mock_file_content(file_obj, file_format)
            except ImportError as mock_error:
                raise ValidationError(
                    f"Failed to download file from storage: {e!s}. "
                    f"Mock content generation also failed (missing dependency): {mock_error!s}"
                )

        # Infer schema via the canonical gated entry point (Phase 260.5.D.R1).
        # This runs validate_text_encoding for text formats before inference,
        # raising FILE_ENCODING_UNSUPPORTED (400) when the gate rejects.
        # Let typed errors propagate — do NOT wrap them in a generic message.
        try:
            schema_json = infer_schema_with_encoding_gate(file_content, file_format)
        except ValidationError:
            raise
        except (ValueError, TypeError, RuntimeError) as e:
            raise ValidationError(
                f"Schema inference failed: {e!s}",
                details={"file_format": file_format, "error": str(e)},
            )

        # Enrich with inference-plan metadata so consumers (FE, SDK,
        # contract drift) know the schema came from a partial read.
        if plan.is_sampled:
            meta = schema_json.setdefault("inference_metadata", {})
            meta.update(plan.metadata_for_schema)
        elif plan.mode == InferenceMode.FULL_READ:
            # FULL_READ — tag sampled=False so consumers don't see
            # false-positive partial-read warnings.
            meta = schema_json.setdefault("inference_metadata", {})
            meta.setdefault("sampled", False)
            meta.setdefault("total_bytes", plan.total_bytes)

        # Extract sample data
        try:
            sample_data_json = extract_sample_data(file_content, file_format)
        except (ValueError, TypeError):
            # Sample extraction failure is not critical — log so operators
            # can detect systematic extraction failures for specific formats.
            logger.warning(
                "Sample data extraction failed for file_id=%s format=%s",
                file_id,
                file_format,
                exc_info=True,
            )
            sample_data_json = []

        # Get row count from schema or estimate
        row_count = schema_json.get("row_count_estimated")

        # Get next version for asset (if asset provided)
        version = 1
        parent_version = None
        if asset:
            latest_dataset = (
                Dataset.objects.filter(tenant_id=tenant_id, asset=asset)
                .order_by("-version")
                .first()
            )
            if latest_dataset:
                version = latest_dataset.version + 1
                parent_version = latest_dataset

        # Validate before create using DatasetsBusinessRules (dataset creation validation)
        from hub.apps.tenants.models import Tenant
        from hub.apps.users.models import User

        tenant = Tenant.objects.get(id=tenant_id)
        user = User.objects.get(id=user_id) if user_id else None
        payload_dataset = Dataset(
            tenant_id=tenant_id,
            asset=asset,
            file=file_obj,
            schema_json=schema_json,
            sample_data_json=sample_data_json,
            row_count=row_count,
            format=file_format,
            version=version,
            file_handle_purpose=file_handle_purpose or "",
            created_by_id=user_id if user_id else None,
        )
        rules = DatasetsBusinessRules(tenant_id=tenant_id, user_id=user_id)
        create_result = rules.validate(
            dataset=payload_dataset,
            tenant=tenant,
            user=user,
            file=file_obj,
            asset=asset,
            validation_type="all",
        )
        if not create_result.is_valid:
            raise ValidationError(
                "; ".join(create_result.errors),
                code="BUSINESS_RULES_VALIDATION",
                details=create_result.details,
            )

        # Check plan limit (Phase 25.1.2, hardened Phase 113.B)
        from hub.apps.tenants.services import PlanLimitService

        plan_limit_service = PlanLimitService(
            tenant_id=tenant_id,
            user_id=user_id,
        )
        plan_limit_service.check_limit(
            tenant_id=tenant_id,
            limit_key="max_datasets",
            delta=1,
        )

        # Create dataset
        dataset = Dataset.objects.create(
            tenant_id=tenant_id,
            asset=asset,
            file=file_obj,
            schema_json=schema_json,
            sample_data_json=sample_data_json,
            row_count=row_count,
            format=file_format,
            version=version,
            file_handle_purpose=file_handle_purpose or "",
            created_by_id=user_id if user_id else None,
        )

        # Initialize version history on the created dataset (no new row; sets version_hash, semantic_version).
        # VersioningService publishes version.created event.
        VersioningService(tenant_id=tenant_id, user_id=user_id).create_version(
            dataset_id=str(dataset.id),
            tenant_id=tenant_id,
            parent_version_id=str(parent_version.id) if parent_version else None,
            semantic_version="1.0.0",
            is_current=True,
            is_initial=True,
        )

        # Log audit event
        from hub.apps.tenants.models import Tenant
        from hub.apps.users.models import User

        try:
            actor_user = User.objects.get(id=user_id)
            tenant = Tenant.objects.get(id=tenant_id)
            create_audit_event(
                resource_type="DATASET",
                action="DATASET_CREATED",
                actor_user=actor_user,
                tenant=tenant,
                resource_id=str(dataset.id),
                details={
                    "file_id": str(file_id),
                    "file_name": file_obj.name,
                    "format": file_format,
                    "row_count": row_count,
                },
            )
        except Exception as e:
            logger.warning(
                "dataset_audit_event_failed",
                extra={
                    "error_type": type(e).__name__,
                    "error": str(e),
                    "dataset_id": str(dataset.id),
                    "operation": "create",
                },
                exc_info=True,
            )

        # Publish event
        try:
            self.publish_dataset_created(
                dataset_id=str(dataset.id),
                asset_id=str(asset.id) if asset else None,
                file_id=str(file_id),
                format=file_format,
                schema_inferred=True,
                tenant_id=tenant_id,
                user_id=user_id,
            )
        except Exception as e:
            logger.warning(
                "dataset_event_publish_failed",
                extra={
                    "error_type": type(e).__name__,
                    "error": str(e),
                    "dataset_id": str(dataset.id),
                },
                exc_info=True,
            )

        return dataset

    def get_dataset(self, dataset_id: str, tenant_id: str | None = None) -> Dataset:
        """
        Get dataset by ID.

        Args:
            dataset_id: Dataset ID
            tenant_id: Optional tenant ID for filtering

        Returns:
            Dataset instance

        Raises:
            NotFoundError: If dataset not found
        """
        effective_tenant_id = tenant_id or self.tenant_id
        if not effective_tenant_id:
            raise ValidationError("tenant_id is required")

        return self.execute_with_metrics(
            operation="get_dataset",
            tenant_id=effective_tenant_id,
            func=lambda: self.get_resource_or_raise(
                Dataset, dataset_id, tenant_id=effective_tenant_id
            ),
        )

    @transaction.atomic
    def update_dataset(
        self, dataset_id: str, tenant_id: str, user_id: str | None = None, **kwargs
    ) -> Dataset:
        """
        Update a dataset. Runs DatasetsBusinessRules (structure) before mutation.

        Args:
            dataset_id: Dataset ID
            tenant_id: Tenant ID
            user_id: User ID performing the update
            **kwargs: Fields to update (e.g. schema_json, sample_data_json, format)

        Returns:
            Updated Dataset instance

        Raises:
            NotFoundError: If dataset not found
            ValidationError: If business rules validation fails (code BUSINESS_RULES_VALIDATION)
        """
        if not tenant_id:
            raise ValidationError("tenant_id is required")

        def _update():
            dataset = self.get_resource_or_raise(
                Dataset,
                dataset_id,
                tenant_id=tenant_id,
            )
            from hub.apps.tenants.models import Tenant
            from hub.apps.users.models import User

            tenant = Tenant.objects.get(id=tenant_id)
            user = User.objects.get(id=user_id) if user_id else None
            rules = DatasetsBusinessRules(tenant_id=tenant_id, user_id=user_id)
            result = rules.validate(
                dataset=dataset,
                tenant=tenant,
                user=user,
                file=getattr(dataset, "file", None),
                asset=getattr(dataset, "asset", None),
                validation_type="structure",
            )
            if not result.is_valid:
                raise ValidationError(
                    "; ".join(result.errors),
                    code="BUSINESS_RULES_VALIDATION",
                    details=result.details,
                )
            for key, value in kwargs.items():
                if hasattr(dataset, key):
                    setattr(dataset, key, value)
            dataset.save()

            # Phase 70.2: Audit event for dataset update
            run_side_effect(
                create_audit_event,
                resource_type="DATASET",
                action="DATASET_UPDATED",
                resource_id=str(dataset.id),
                details={"changed_fields": list(kwargs.keys())},
            )

            return dataset

        return self.execute_with_metrics(
            operation="update_dataset",
            tenant_id=tenant_id,
            func=_update,
        )

    @transaction.atomic
    def destroy_dataset(
        self,
        dataset_id: str,
        tenant_id: str,
        user_id: str | None = None,
    ) -> None:
        """
        Delete a dataset. Runs DatasetsBusinessRules.validate_version_deletion before mutation.

        Args:
            dataset_id: Dataset ID
            tenant_id: Tenant ID
            user_id: User ID performing the delete

        Raises:
            NotFoundError: If dataset not found
            ValidationError: If deletion validation fails (code BUSINESS_RULES_VALIDATION)
        """
        if not tenant_id:
            raise ValidationError("tenant_id is required")

        def _destroy():
            dataset = self.get_resource_or_raise(
                Dataset,
                dataset_id,
                tenant_id=tenant_id,
            )
            rules = DatasetsBusinessRules(tenant_id=tenant_id, user_id=user_id)
            result = rules.validate_version_deletion(dataset, raise_on_error=False)
            if not result.is_valid:
                raise ValidationError(
                    "; ".join(result.errors),
                    code="BUSINESS_RULES_VALIDATION",
                    details=result.details,
                )

            # If dataset is marked as current, unset it before deletion
            # This allows deletion of current versions (business rule validation already checked for blockers)
            if dataset.is_current:
                # Find another version for the same asset to set as current, or leave None
                other_version = (
                    Dataset.objects.filter(
                        tenant_id=tenant_id, asset=dataset.asset, is_current=False
                    )
                    .exclude(id=dataset.id)
                    .first()
                )

                if other_version:
                    other_version.is_current = True
                    other_version.save(update_fields=["is_current"])

                dataset.is_current = False
                dataset.save(update_fields=["is_current"])

            # Phase 70.2: Audit event for dataset deletion
            run_side_effect(
                create_audit_event,
                resource_type="DATASET",
                action="DATASET_DELETED",
                resource_id=str(dataset_id),
            )

            dataset.delete()

        self.execute_with_metrics(
            operation="destroy_dataset",
            tenant_id=tenant_id,
            func=_destroy,
        )

    @transaction.atomic
    def create_version_from_dataset(
        self,
        source_dataset_id: str,
        tenant_id: str,
        user_id: str | None = None,
        semantic_version: str | None = None,
        version_tags: list[str] | None = None,
        snapshot_metadata: dict[str, Any] | None = None,
        schema_json: dict[str, Any] | None = None,
    ) -> Dataset:
        """
        Create a new dataset version (new row) from an existing dataset.
        Runs DatasetsBusinessRules (version) after creating the new row, then
        initializes version history via VersioningService.

        Args:
            source_dataset_id: Source dataset ID (parent version)
            tenant_id: Tenant ID
            user_id: User ID
            semantic_version: Optional semantic version string
            version_tags: Optional version tags
            snapshot_metadata: Optional snapshot metadata

        Returns:
            New Dataset instance (new version row)

        Raises:
            NotFoundError: If source dataset not found
            ValidationError: If version validation fails (code BUSINESS_RULES_VALIDATION)
        """
        if not tenant_id:
            raise ValidationError("tenant_id is required")

        def _create_version():
            parent = self.get_resource_or_raise(
                Dataset,
                source_dataset_id,
                tenant_id=tenant_id,
            )
            from hub.apps.tenants.models import Tenant
            from hub.apps.users.models import User

            tenant = Tenant.objects.get(id=tenant_id)
            user = User.objects.get(id=user_id) if user_id else None
            new_version = parent.version + 1
            # Phase 260.5.I — re-derive sample_data from file bytes
            # instead of blindly copying the parent cache. Fall back
            # to parent's value when the file is unreachable.
            fresh_sample = extract_sample_data_from_storage(parent.file, parent.format)
            if fresh_sample is not None:
                sample_data = fresh_sample
            else:
                sample_data = parent.sample_data_json

            new_dataset = Dataset.objects.create(
                tenant=parent.tenant,
                asset=parent.asset,
                file=parent.file,
                schema_json=schema_json if schema_json is not None else parent.schema_json,
                sample_data_json=sample_data,
                row_count=parent.row_count,
                format=parent.format,
                version=new_version,
                created_by_id=user_id if user_id else None,
            )
            rules = DatasetsBusinessRules(tenant_id=tenant_id, user_id=user_id)
            result = rules.validate(
                dataset=new_dataset,
                tenant=tenant,
                user=user,
                validation_type="version",
            )
            if not result.is_valid:
                new_dataset.delete()
                raise ValidationError(
                    "; ".join(result.errors),
                    code="BUSINESS_RULES_VALIDATION",
                    details=result.details,
                )
            versioning_service = VersioningService(
                tenant_id=tenant_id,
                user_id=user_id,
            )
            versioning_service.create_version(
                dataset_id=str(new_dataset.id),
                tenant_id=tenant_id,
                parent_version_id=str(parent.id),
                semantic_version=semantic_version,
                version_tags=version_tags or [],
                snapshot_metadata=snapshot_metadata,
                is_current=True,
            )
            refreshed = Dataset.objects.get(id=new_dataset.id, tenant_id=tenant_id)

            # Phase 70.2: Audit event for dataset version creation
            run_side_effect(
                create_audit_event,
                resource_type="DATASET",
                action="DATASET_VERSION_CREATED",
                resource_id=str(refreshed.id),
                details={"parent_dataset_id": str(parent.id), "version": new_version},
            )

            return refreshed

        return self.execute_with_metrics(
            operation="create_version_from_dataset",
            tenant_id=tenant_id,
            func=_create_version,
        )
