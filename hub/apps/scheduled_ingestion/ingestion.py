"""
Scheduled Ingestion Processor

Handles file discovery, filtering, downloading, and dataset creation for scheduled ingestions.
"""

import os
import re
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

import structlog
from django.core.files.base import ContentFile
from django.db import transaction
from django.utils import timezone


# Import source connectors from Prefect Integration Service (lazy import to avoid import-time failures)
def _get_source_connector_factory():
    """Lazy import of SourceConnectorFactory to avoid import-time dependency issues"""
    try:
        sys.path.insert(
            0, os.path.join(os.path.dirname(__file__), "../../../services/prefect-integration")
        )
        from connectors.factory import SourceConnectorFactory

        return SourceConnectorFactory
    except ImportError:
        # If connectors are not available (e.g., missing Google Cloud libraries), return None
        # This allows tests to mock the processor without requiring all dependencies
        return None


# Import Django models
from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.contracts.models import Contract
from hub.apps.datasets.models import Dataset
from hub.apps.files.models import File, FileStatus
from hub.apps.files.storage import S3StorageClient
from hub.apps.scheduled_ingestion.exceptions import ConnectorNotAvailableError
from hub.apps.scheduled_ingestion.incremental_state import IncrementalStateManager
from hub.apps.scheduled_ingestion.models import ScheduledIngestion

logger = structlog.get_logger(__name__)


class ScheduledIngestionProcessor:
    """Processor for scheduled ingestion jobs"""

    def __init__(
        self,
        scheduled_ingestion: ScheduledIngestion,
        connector_factory: Optional[Any] = None,
        dq_client: Optional[Any] = None,
    ):
        """
        Initialize processor.

        Args:
            scheduled_ingestion: ScheduledIngestion instance
            connector_factory: Optional factory with get_connector(source_type).
                When None, uses _get_source_connector_factory() (external service).
                Inject in tests to use a real in-memory connector (no mocks).
            dq_client: Optional DQ client with health_check() and run_dq().
                When None, uses DQServiceClient() (external service).
                Inject in tests to use a real in-memory DQ client (no mocks).
        """
        self.scheduled_ingestion = scheduled_ingestion
        self.tenant = scheduled_ingestion.tenant
        self.source_type = scheduled_ingestion.source_type
        self.source_config = scheduled_ingestion.get_source_config()
        self.file_pattern = scheduled_ingestion.file_pattern
        self.state_manager = IncrementalStateManager(scheduled_ingestion)
        self._connector_factory = connector_factory
        self._dq_client = dq_client

    def process(self) -> Dict[str, Any]:
        """
        Process scheduled ingestion using workflow engine.

        Returns:
            Result dictionary with processing results
        """
        logger.info(
            "Starting scheduled ingestion processing",
            scheduled_ingestion_id=str(self.scheduled_ingestion.id),
            tenant_id=str(self.tenant.id),
            source_type=self.source_type,
        )

        try:
            # Use workflow engine for orchestrated processing
            from hub.apps.orchestration.workflows.scheduled_ingestion import (
                ScheduledIngestionWorkflow,
            )

            workflow_result = ScheduledIngestionWorkflow.execute(
                scheduled_ingestion_id=str(self.scheduled_ingestion.id)
            )

            # Extract results from workflow output
            output_data = workflow_result.get("output_data", {})
            state_summary = output_data.get("state_summary", {})

            # Sync from model so result matches DB (rollback may have updated ingestion_state
            # after update_ingestion_state ran; model is authoritative).
            self.scheduled_ingestion.refresh_from_db()
            state = self.scheduled_ingestion.ingestion_state or {}
            model_failed = state.get("failed_files", [])
            if isinstance(model_failed, list) and model_failed:
                # Use model's failed_files so result and test assertions are correct
                state_summary = dict(state_summary)
                state_summary["total_failed"] = len(model_failed)
                state_summary["failed_files"] = model_failed

            # Persist failed_files list to model when workflow reported them (state_summary is source)
            failed_files_list = state_summary.get("failed_files")
            if isinstance(failed_files_list, list) and failed_files_list:
                self.scheduled_ingestion.refresh_from_db()
                state = self.scheduled_ingestion.ingestion_state or {}
                existing_failed = state.get("failed_files", [])
                if not existing_failed or len(existing_failed) < len(failed_files_list):
                    state["failed_files"] = failed_files_list
                    self.scheduled_ingestion.ingestion_state = state
                    self.scheduled_ingestion.save(update_fields=["ingestion_state", "updated_at"])

            result = {
                "files_found": output_data.get("files_found", 0),
                "files_processed": state_summary.get("total_processed", 0),
                "files_failed": state_summary.get("total_failed", 0),
                "datasets_created": state_summary.get(
                    "total_processed", 0
                ),  # Each processed file creates a dataset
                "ingestion_state": {
                    "processed_files": state_summary.get("total_processed", 0),
                    "failed_files": state_summary.get("total_failed", 0),
                    "permanent_failures": state_summary.get("permanent_failures", 0),
                    "retryable_failures": state_summary.get("retryable_failures", 0),
                    "last_processed_at": state_summary.get("last_processed_timestamp"),
                },
                "workflow_instance_id": workflow_result.get("workflow_instance_id"),
            }

            logger.info(
                "Scheduled ingestion processing completed",
                scheduled_ingestion_id=str(self.scheduled_ingestion.id),
                files_found=result["files_found"],
                files_processed=result["files_processed"],
                files_failed=result["files_failed"],
                datasets_created=result["datasets_created"],
            )

            return result

        except Exception as e:
            logger.error(
                "Scheduled ingestion processing failed",
                scheduled_ingestion_id=str(self.scheduled_ingestion.id),
                error=str(e),
                exc_info=True,
            )
            raise

    def _discover_files(self) -> List[str]:
        """
        Discover files from source using connector.

        Returns:
            List of file paths/keys
        """
        try:
            factory = self._connector_factory or _get_source_connector_factory()
            if factory is None:
                raise ConnectorNotAvailableError(
                    self.source_type, role="source", message="connector not registered (factory unavailable)"
                )
            try:
                connector = factory.get_connector(self.source_type)
            except ValueError as e:
                raise ConnectorNotAvailableError(
                    self.source_type, role="source", message="connector not registered"
                ) from e
            # Use default pattern that matches all files if pattern is None
            file_pattern = self.file_pattern or ".*"
            files = connector.discover_files(self.source_config, file_pattern)
            return files
        except ConnectorNotAvailableError:
            raise
        except Exception as e:
            logger.warning(
                "Failed to discover files",
                scheduled_ingestion_id=str(self.scheduled_ingestion.id),
                source_type=self.source_type,
                error=str(e),
                exc_info=True,
            )
            raise ConnectionError(f"Failed to discover files: {str(e)}") from e

    def _filter_files(self, files: List[str]) -> List[str]:
        """
        Filter files based on incremental state and configuration.

        Filters:
        - Skip already processed files
        - Skip permanently failed files
        - Apply timestamp-based filtering (incremental ingestion)
        - Apply file size limits

        Args:
            files: List of file paths/keys

        Returns:
            Filtered list of file paths/keys
        """
        filtered = []
        factory = self._connector_factory or _get_source_connector_factory()
        if factory is None:
            raise ConnectorNotAvailableError(
                self.source_type, role="source", message="connector not registered (factory unavailable)"
            )
        try:
            connector = factory.get_connector(self.source_type)
        except ValueError as e:
            raise ConnectorNotAvailableError(
                self.source_type, role="source", message="connector not registered"
            ) from e

        for file_path in files:
            # Check if file should be processed using state manager
            file_timestamp = None
            try:
                metadata = connector.get_file_metadata(self.source_config, file_path)
                last_modified = metadata.get("last_modified")

                if last_modified:
                    if isinstance(last_modified, str):
                        from dateutil.parser import parse

                        last_modified = parse(last_modified)
                    file_timestamp = last_modified
            except Exception:
                pass  # Continue without timestamp

            # Use state manager to determine if file should be processed
            if not self.state_manager.should_process_file(file_path, file_timestamp):
                continue

            # Apply file size limits (if configured)
            max_file_size = self.source_config.get("max_file_size_bytes")
            if max_file_size:
                try:
                    metadata = connector.get_file_metadata(self.source_config, file_path)
                    file_size = metadata.get("size", 0)

                    if file_size and file_size > max_file_size:
                        logger.warning(
                            "File exceeds size limit, skipping",
                            file_path=file_path,
                            file_size=file_size,
                            max_size=max_file_size,
                        )
                        continue
                except Exception:
                    pass  # If metadata retrieval fails, include the file

            filtered.append(file_path)

        return filtered

    def _extract_error_code(self, exception: Exception) -> str:
        """
        Extract error code from exception.

        Args:
            exception: Exception instance

        Returns:
            Error code string
        """
        error_str = str(exception).lower()

        if "timeout" in error_str:
            return "TIMEOUT"
        elif "validation" in error_str or "invalid" in error_str:
            return "VALIDATION_ERROR"
        elif "connection" in error_str or "network" in error_str:
            return "CONNECTION_ERROR"
        elif "permission" in error_str or "access" in error_str:
            return "PERMISSION_ERROR"
        elif "quality" in error_str or "dq" in error_str:
            return "DQ_FAILURE"
        else:
            return "UNKNOWN_ERROR"

    def _process_file(self, file_path: str) -> Optional[Dataset]:
        """
        Process a single file: download, create File record, create Dataset.

        Args:
            file_path: File path/key in source

        Returns:
            Created Dataset instance, or None if processing failed
        """
        with transaction.atomic():
            # Download file to temporary location
            temp_file = None
            try:
                factory = self._connector_factory or _get_source_connector_factory()
                if factory is None:
                    raise ConnectorNotAvailableError(
                        self.source_type, role="source", message="connector not registered (factory unavailable)"
                    )
                try:
                    connector = factory.get_connector(self.source_type)
                except ValueError as e:
                    raise ConnectorNotAvailableError(
                        self.source_type, role="source", message="connector not registered"
                    ) from e

                # Create temporary file
                temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=Path(file_path).suffix)
                temp_path = temp_file.name
                temp_file.close()

                # Download file
                result = connector.download_file(self.source_config, file_path, temp_path)

                if result.status.value != "SUCCESS":
                    raise Exception(f"Failed to download file: {result.message}")

                # Read file content
                with open(temp_path, "rb") as f:
                    file_content = f.read()

                # Determine file format from extension; reject unsupported extensions
                file_ext = Path(file_path).suffix.lower()
                format_map = {
                    ".csv": "CSV",
                    ".json": "JSON",
                    ".parquet": "PARQUET",
                    ".xlsx": "XLSX",
                    ".xls": "XLS",
                }
                if file_ext not in format_map:
                    raise ValueError(
                        f"Unsupported file format: {file_ext or '(no extension)'}. "
                        f"Supported: {', '.join(format_map.keys())}"
                    )
                file_format = format_map[file_ext]

                # Determine content type from format
                content_type_map = {
                    "CSV": "text/csv",
                    "JSON": "application/json",
                    "PARQUET": "application/octet-stream",
                    "XLSX": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    "XLS": "application/vnd.ms-excel",
                }
                content_type = content_type_map.get(file_format, "application/octet-stream")

                # Create File record
                file_obj = File.objects.create(
                    tenant=self.tenant,
                    name=Path(file_path).name,
                    content_type=content_type,
                    size=len(file_content),
                    status=FileStatus.ACTIVE,
                    created_by=self.scheduled_ingestion.created_by,
                )

                # Calculate SHA-256 hash
                import hashlib

                file_obj.content_sha256 = hashlib.sha256(file_content).hexdigest()

                # Upload file to storage
                storage = S3StorageClient()
                storage_path = storage.save_file(
                    tenant_id=str(self.tenant.id),
                    file_id=str(file_obj.id),
                    file_content=ContentFile(file_content, name=Path(file_path).name),
                )
                file_obj.storage_path = storage_path
                file_obj.save(update_fields=["content_sha256", "storage_path"])

                # Run DQ check before dataset creation (if enabled)
                dq_result = None
                if self._should_run_dq_check():
                    dq_result = self._run_dq_check(file_content, file_format)

                    # Check if DQ validation failed
                    if dq_result and not self._is_dq_result_valid(dq_result):
                        error_message = self._format_dq_failure_message(dq_result)
                        raise ValueError(f"DQ validation failed: {error_message}")

                # Get or create asset
                asset = self.scheduled_ingestion.asset
                if not asset and self.scheduled_ingestion.auto_create_asset:
                    asset = self._create_asset()

                # Create dataset (pass file_format and DQ result)
                dataset = self._create_dataset(file_obj, asset, file_format, dq_result)

                # Auto-activate asset if configured
                if asset and self.scheduled_ingestion.auto_activate:
                    asset.status = AssetStatus.ACTIVE
                    asset.save()

                return dataset

            finally:
                # Clean up temporary file
                if temp_file and os.path.exists(temp_path):
                    try:
                        os.unlink(temp_path)
                    except Exception:
                        pass

    def _create_asset(self) -> Asset:
        """
        Create asset for scheduled ingestion.

        Returns:
            Created Asset instance
        """
        from hub.apps.assets.models import Asset, AssetStatus, AssetVisibility

        asset_name = self.scheduled_ingestion.name
        asset_key = f"scheduled-ingestion-{self.scheduled_ingestion.id}"

        # Generate unique key
        counter = 1
        while Asset.objects.filter(tenant=self.tenant, key=asset_key).exists():
            asset_key = f"scheduled-ingestion-{self.scheduled_ingestion.id}-{counter}"
            counter += 1

        asset = Asset.objects.create(
            tenant=self.tenant,
            key=asset_key,
            name=asset_name,
            description=self.scheduled_ingestion.description
            or f"Asset created from scheduled ingestion {self.scheduled_ingestion.name}",
            status=AssetStatus.DRAFT,
            visibility=AssetVisibility.INTERNAL,
            created_by=self.scheduled_ingestion.created_by,
        )

        # Update scheduled ingestion with asset
        self.scheduled_ingestion.asset = asset
        self.scheduled_ingestion.save()

        return asset

    def _should_run_dq_check(self) -> bool:
        """
        Determine if DQ check should be run before dataset creation.

        Returns:
            True if DQ check should be run, False otherwise
        """
        # Check if DQ validation is enabled in source_config or scheduled_ingestion config
        source_config = self.source_config or {}
        ingestion_config = self.scheduled_ingestion.ingestion_state or {}

        # Check source_config first
        if source_config.get("enable_dq_validation", False):
            return True

        # Check ingestion_state config
        if ingestion_config.get("enable_dq_validation", False):
            return True

        # Default: don't run DQ check (can be enabled per ingestion)
        return False

    def _run_dq_check(self, file_content: bytes, file_format: str) -> Optional[Dict[str, Any]]:
        """
        Run DQ check on file content before dataset creation.

        Args:
            file_content: File content bytes
            file_format: File format (CSV, JSON, PARQUET, etc.)

        Returns:
            DQ result dictionary or None if check failed
        """
        try:
            # Use injectable DQ client when provided (e.g. tests); else external service
            if self._dq_client is not None:
                dq_client = self._dq_client
            else:
                from hub.apps.dq.service_client import DQServiceClient

                dq_client = DQServiceClient()

            # Get DQ configuration
            source_config = self.source_config or {}
            profile_key = source_config.get("dq_profile_key", "intake_basic_gx")

            # Get contract if available (for custom quality rules)
            contract = self.scheduled_ingestion.contract

            # Check DQ service health
            is_healthy, _ = dq_client.health_check()
            if not is_healthy:
                logger.warning(
                    "DQ service is unavailable, skipping DQ check",
                    scheduled_ingestion_id=str(self.scheduled_ingestion.id),
                )
                return None

            # Run DQ check
            dq_result = dq_client.run_dq(
                file_content=file_content,
                file_format=file_format.lower(),
                profile_key=profile_key,
                contract=contract,
            )

            logger.info(
                "DQ check completed",
                scheduled_ingestion_id=str(self.scheduled_ingestion.id),
                overall_status=dq_result.get("overall_status"),
                quality_score=dq_result.get("quality_score"),
            )

            return dq_result

        except Exception as e:
            logger.warning(
                "DQ check failed",
                scheduled_ingestion_id=str(self.scheduled_ingestion.id),
                error=str(e),
                exc_info=True,
            )
            # If DQ check fails, we can either:
            # 1. Fail the ingestion (strict mode)
            # 2. Continue without DQ (lenient mode)
            # For now, we'll fail in strict mode if DQ is enabled
            source_config = self.source_config or {}
            if source_config.get("dq_strict_mode", True):
                raise ValueError(f"DQ check failed: {str(e)}")
            return None

    def _is_dq_result_valid(self, dq_result: Dict[str, Any]) -> bool:
        """
        Check if DQ result is valid (passes quality thresholds).

        Args:
            dq_result: DQ result dictionary

        Returns:
            True if DQ result is valid, False otherwise
        """
        if not dq_result:
            return False

        # Check overall status
        overall_status = dq_result.get("overall_status", "").upper()
        if overall_status not in ["PASS", "SUCCESS"]:
            return False

        # Check quality score threshold
        quality_score = dq_result.get("quality_score", 0.0)
        source_config = self.source_config or {}
        min_quality_score = source_config.get("min_quality_score", 0.8)  # Default 80%

        if quality_score < min_quality_score:
            logger.warning(
                "DQ quality score below threshold",
                scheduled_ingestion_id=str(self.scheduled_ingestion.id),
                quality_score=quality_score,
                min_quality_score=min_quality_score,
            )
            return False

        # Check for critical failures
        checks = dq_result.get("checks", [])
        for check in checks:
            severity = check.get("severity", "").upper()
            status = check.get("status", "").upper()

            # Fail if critical check failed
            if severity == "CRITICAL" and status not in ["PASS", "SUCCESS"]:
                return False

        return True

    def _format_dq_failure_message(self, dq_result: Dict[str, Any]) -> str:
        """
        Format DQ failure message for error reporting.

        Args:
            dq_result: DQ result dictionary

        Returns:
            Formatted error message
        """
        overall_status = dq_result.get("overall_status", "UNKNOWN")
        quality_score = dq_result.get("quality_score", 0.0)

        # Get failed checks
        checks = dq_result.get("checks", [])
        failed_checks = [
            check for check in checks if check.get("status", "").upper() not in ["PASS", "SUCCESS"]
        ]

        message = f"Overall status: {overall_status}, Quality score: {quality_score:.2%}"

        if failed_checks:
            critical_failures = [
                check for check in failed_checks if check.get("severity", "").upper() == "CRITICAL"
            ]

            if critical_failures:
                message += f", Critical failures: {len(critical_failures)}"

            message += f", Total failures: {len(failed_checks)}"

        return message

    def _create_dataset(
        self,
        file_obj: File,
        asset: Optional[Asset] = None,
        file_format: str = "CSV",
        dq_result: Optional[Dict[str, Any]] = None,
    ) -> Dataset:
        """
        Create dataset from file.

        Args:
            file_obj: File instance
            asset: Optional Asset instance
            file_format: File format (CSV, JSON, PARQUET, XLSX, XLS)

        Returns:
            Created Dataset instance
        """
        from hub.apps.datasets.schema_inference import (
            extract_sample_data,
            infer_schema_from_csv,
            infer_schema_from_excel,
            infer_schema_from_json,
            infer_schema_from_parquet,
        )

        # Download file from storage
        storage = S3StorageClient()
        file_content = storage.get_file_content(file_obj.storage_path)

        # Infer schema based on format
        schema_json = {}
        try:
            if file_format == "CSV":
                schema_json = infer_schema_from_csv(file_content)
            elif file_format == "JSON":
                schema_json = infer_schema_from_json(file_content)
            elif file_format == "PARQUET":
                schema_json = infer_schema_from_parquet(file_content)
            elif file_format in ["XLSX", "XLS"]:
                schema_json = infer_schema_from_excel(file_content)
            else:
                logger.warning(
                    "Unsupported file format for schema inference",
                    file_id=str(file_obj.id),
                    file_format=file_format,
                )
        except Exception as e:
            logger.error(
                "Schema inference failed",
                file_id=str(file_obj.id),
                file_format=file_format,
                error=str(e),
                exc_info=True,
            )
            # Continue without schema if inference fails

        # Extract sample data
        try:
            sample_data_json = extract_sample_data(file_content, file_format)
        except Exception as e:
            logger.warning(
                "Sample data extraction failed",
                file_id=str(file_obj.id),
                file_format=file_format,
                error=str(e),
            )
            sample_data_json = []

        # Get row count from schema
        row_count = schema_json.get("row_count_estimated")

        # Get next version for asset
        version = 1
        parent_version = None
        if asset:
            latest_dataset = (
                Dataset.objects.filter(tenant=self.tenant, asset=asset).order_by("-version").first()
            )
            if latest_dataset:
                version = latest_dataset.version + 1
                parent_version = latest_dataset

        # Store DQ result in dataset metadata if available
        metadata_json = {}
        if dq_result:
            metadata_json["pre_ingestion_dq"] = {
                "overall_status": dq_result.get("overall_status"),
                "quality_score": dq_result.get("quality_score"),
                "execution_time_seconds": dq_result.get("execution_time_seconds"),
                "checks_count": len(dq_result.get("checks", [])),
                "passed_checks": len(
                    [
                        c
                        for c in dq_result.get("checks", [])
                        if c.get("status", "").upper() in ["PASS", "SUCCESS"]
                    ]
                ),
                "failed_checks": len(
                    [
                        c
                        for c in dq_result.get("checks", [])
                        if c.get("status", "").upper() not in ["PASS", "SUCCESS"]
                    ]
                ),
            }

        # Create dataset (Dataset model has snapshot_metadata for DQ/version metadata, no kind/metadata_json)
        dataset = Dataset.objects.create(
            tenant=self.tenant,
            asset=asset,
            file=file_obj,
            schema_json=schema_json,
            sample_data_json=sample_data_json,
            row_count=row_count,
            format=file_format,
            version=version,
            created_by=self.scheduled_ingestion.created_by,
            snapshot_metadata=metadata_json if metadata_json else {},
        )

        # Initialize version history
        from hub.apps.datasets.versioning import VersionHistoryManager

        VersionHistoryManager.create_version(
            dataset=dataset, parent_version=parent_version, is_current=True
        )

        return dataset
