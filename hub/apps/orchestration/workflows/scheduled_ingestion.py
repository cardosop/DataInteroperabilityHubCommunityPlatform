"""
Scheduled Ingestion Workflow

Orchestrates the scheduled ingestion process with proper error handling,
retry logic, parallel file processing, and compensation.
"""

import hashlib
import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import structlog
from django.core.files.base import ContentFile
from django.db import transaction
from django.utils import timezone

from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.audit.utils import create_audit_event
from hub.apps.datasets.models import Dataset
from hub.apps.files.models import File, FileStatus
from hub.apps.files.storage import S3StorageClient
from hub.apps.notifications.models import EmailType
from hub.apps.notifications.tasks import send_email_async
from hub.apps.orchestration.models import WorkflowInstance, WorkflowStatus
from hub.apps.orchestration.registry import WorkflowRegistry
from hub.apps.orchestration.workflow_engine import WorkflowEngine
from hub.apps.scheduled_ingestion.business_rules import ScheduledIngestionBusinessRules
from hub.apps.scheduled_ingestion.dead_letter_queue import DeadLetterQueueManager
from hub.apps.scheduled_ingestion.incremental_state import IncrementalStateManager
from hub.apps.scheduled_ingestion.models import (
    DeadLetterQueueItem,
    ScheduledIngestion,
    ScheduledIngestionRun,
    ScheduledIngestionRunStatus,
)
from hub.apps.search.indexing import SearchIndexer


# Import source connectors from Prefect Integration Service (lazy import to avoid import-time failures)
def _get_source_connector_factory():
    """Lazy import of SourceConnectorFactory to avoid import-time dependency issues"""
    sys.path.insert(
        0, os.path.join(os.path.dirname(__file__), "../../../../services/prefect-integration")
    )
    from connectors.factory import SourceConnectorFactory

    return SourceConnectorFactory


logger = structlog.get_logger(__name__)


class ScheduledIngestionWorkflow:
    """
    Scheduled ingestion workflow orchestrator.

    Manages the complete scheduled ingestion process:
    1. Validate ingestion configuration
    2. Connect to source (S3/GCS/Azure/etc.)
    3. Discover files
    4. Filter files (incremental logic)
    5. For each file: Download, validate, run DQ checks, create dataset version, index
    6. Update ingestion state
    7. Send completion notification
    8. Handle failures (DLQ)
    """

    WORKFLOW_NAME = "scheduled_ingestion"

    @classmethod
    def register_workflow(cls, registry: WorkflowRegistry) -> None:
        """
        Register the scheduled ingestion workflow definition.

        Args:
            registry: WorkflowRegistry instance
        """
        workflow_dsl = {
            "version": "1.0.0",
            "dependencies": [],
            "steps": [
                {
                    "name": "validate_ingestion_config",
                    "type": "task",
                    "task": "scheduled_ingestion.validate_ingestion_config",
                },
                {
                    "name": "connect_to_source",
                    "type": "task",
                    "task": "scheduled_ingestion.connect_to_source",
                    "compensation": {
                        "type": "task",
                        "task": "scheduled_ingestion.rollback_connection",
                    },
                },
                {
                    "name": "discover_files",
                    "type": "task",
                    "task": "scheduled_ingestion.discover_files",
                },
                {
                    "name": "filter_files",
                    "type": "task",
                    "task": "scheduled_ingestion.filter_files",
                },
                {
                    "name": "process_files",
                    "type": "loop",
                    "items": "${filtered_files}",
                    "steps": [
                        {
                            "name": "download_file",
                            "type": "task",
                            "task": "scheduled_ingestion.download_file",
                            "compensation": {
                                "type": "task",
                                "task": "scheduled_ingestion.rollback_file_download",
                            },
                        },
                        {
                            "name": "validate_file",
                            "type": "task",
                            "task": "scheduled_ingestion.validate_file",
                        },
                        {
                            "name": "run_dq_check",
                            "type": "conditional",
                            "condition": {
                                "operator": "equals",
                                "field": "enable_dq_validation",
                                "value": True,
                            },
                            "then": [
                                {
                                    "name": "execute_dq_check",
                                    "type": "task",
                                    "task": "scheduled_ingestion.run_dq_check",
                                }
                            ],
                            "else": [],
                        },
                        {
                            "name": "create_dataset_version",
                            "type": "task",
                            "task": "scheduled_ingestion.create_dataset_version",
                            "compensation": {
                                "type": "task",
                                "task": "scheduled_ingestion.rollback_dataset_creation",
                            },
                        },
                        {
                            "name": "index_dataset",
                            "type": "task",
                            "task": "scheduled_ingestion.index_dataset",
                            "compensation": {
                                "type": "task",
                                "task": "scheduled_ingestion.rollback_indexing",
                            },
                        },
                        {
                            "name": "mark_file_processed",
                            "type": "task",
                            "task": "scheduled_ingestion.mark_file_processed",
                        },
                    ],
                },
                {
                    "name": "update_ingestion_state",
                    "type": "task",
                    "task": "scheduled_ingestion.update_ingestion_state",
                },
                {
                    "name": "handle_failures_dlq",
                    "type": "task",
                    "task": "scheduled_ingestion.handle_failures_dlq",
                },
                {
                    "name": "send_completion_notification",
                    "type": "task",
                    "task": "scheduled_ingestion.send_completion_notification",
                },
                {
                    "name": "audit_logging",
                    "type": "task",
                    "task": "scheduled_ingestion.audit_logging",
                },
            ],
            "compensation": {"enabled": True},
        }

        registry.register_workflow(
            workflow_name=cls.WORKFLOW_NAME,
            dsl_json=workflow_dsl,
            description="Orchestrates scheduled ingestion with file discovery, filtering, parallel processing, DQ checks, and failure handling",
        )

    @classmethod
    def register_tasks(cls, engine: WorkflowEngine) -> None:
        """
        Register all workflow task functions.

        Args:
            engine: WorkflowEngine instance
        """
        engine.register_task(
            "scheduled_ingestion.validate_ingestion_config", cls._validate_ingestion_config_task
        )
        engine.register_task("scheduled_ingestion.connect_to_source", cls._connect_to_source_task)
        engine.register_task("scheduled_ingestion.discover_files", cls._discover_files_task)
        engine.register_task("scheduled_ingestion.filter_files", cls._filter_files_task)
        engine.register_task("scheduled_ingestion.download_file", cls._download_file_task)
        engine.register_task("scheduled_ingestion.validate_file", cls._validate_file_task)
        engine.register_task("scheduled_ingestion.run_dq_check", cls._run_dq_check_task)
        engine.register_task(
            "scheduled_ingestion.create_dataset_version", cls._create_dataset_version_task
        )
        engine.register_task("scheduled_ingestion.index_dataset", cls._index_dataset_task)
        engine.register_task(
            "scheduled_ingestion.mark_file_processed", cls._mark_file_processed_task
        )
        engine.register_task(
            "scheduled_ingestion.update_ingestion_state", cls._update_ingestion_state_task
        )
        engine.register_task(
            "scheduled_ingestion.handle_failures_dlq", cls._handle_failures_dlq_task
        )
        engine.register_task(
            "scheduled_ingestion.send_completion_notification",
            cls._send_completion_notification_task,
        )
        engine.register_task("scheduled_ingestion.audit_logging", cls._audit_logging_task)

        # Compensation tasks
        engine.register_task(
            "scheduled_ingestion.rollback_connection", cls._rollback_connection_task
        )
        engine.register_task(
            "scheduled_ingestion.rollback_file_download", cls._rollback_file_download_task
        )
        engine.register_task(
            "scheduled_ingestion.rollback_dataset_creation", cls._rollback_dataset_creation_task
        )
        engine.register_task("scheduled_ingestion.rollback_indexing", cls._rollback_indexing_task)

    @staticmethod
    def _validate_ingestion_config_task(
        input_data: Dict[str, Any], instance: WorkflowInstance, step
    ) -> Dict[str, Any]:
        """
        Validate ingestion configuration.

        Args:
            input_data: Workflow input data
            instance: Workflow instance
            step: Workflow step

        Returns:
            Task output with validated configuration
        """
        scheduled_ingestion_id = input_data.get("scheduled_ingestion_id")
        if not scheduled_ingestion_id:
            raise ValueError("scheduled_ingestion_id is required")

        try:
            scheduled_ingestion = ScheduledIngestion.objects.get(id=scheduled_ingestion_id)
        except ScheduledIngestion.DoesNotExist:
            raise ValueError(f"Scheduled ingestion {scheduled_ingestion_id} not found")

        # Validate source configuration
        source_config = scheduled_ingestion.source_config
        if not source_config:
            raise ValueError("source_config is required")

        source_type = scheduled_ingestion.source_type
        if not source_type:
            raise ValueError("source_type is required")

        # Use default pattern that matches all files when file_pattern is None or empty
        import re

        file_pattern = scheduled_ingestion.file_pattern or ".*"
        try:
            re.compile(file_pattern)
        except re.error as e:
            raise ValueError(f"Invalid file pattern regex: {str(e)}")

        # Validate ingestion configuration using ScheduledIngestionBusinessRules
        ingestion_rules = ScheduledIngestionBusinessRules(
            tenant_id=str(scheduled_ingestion.tenant_id) if scheduled_ingestion.tenant_id else None,
            user_id=str(instance.created_by_id) if instance.created_by_id else None,
        )

        # Validate scheduled ingestion
        ingestion_validation_result = ingestion_rules.validate(
            schedule=scheduled_ingestion,
            tenant=scheduled_ingestion.tenant,
            user=instance.created_by,
            validation_type="schedule",
        )

        if not ingestion_validation_result.is_valid:
            error_messages = ingestion_validation_result.errors
            raise ValueError(
                f"Ingestion configuration validation failed: {'; '.join(error_messages)}"
            )

        # Log validation warnings if any
        if ingestion_validation_result.warnings:
            logger.warning(
                "Ingestion configuration validation warnings",
                workflow_instance_id=str(instance.id),
                scheduled_ingestion_id=str(scheduled_ingestion.id),
                warnings=ingestion_validation_result.warnings,
            )

        logger.info(
            "Ingestion configuration validated",
            workflow_instance_id=str(instance.id),
            scheduled_ingestion_id=str(scheduled_ingestion.id),
            source_type=source_type,
        )

        return {
            "validated": True,
            "scheduled_ingestion_id": str(scheduled_ingestion.id),
            "tenant_id": str(scheduled_ingestion.tenant.id),
            "source_type": source_type,
            "source_config": source_config,
            "file_pattern": file_pattern,
            "auto_create_asset": scheduled_ingestion.auto_create_asset,
            "auto_activate": scheduled_ingestion.auto_activate,
            "enable_dq_validation": source_config.get("enable_dq_validation", False),
            "dq_strict_mode": source_config.get("dq_strict_mode", True),
            "dq_profile_key": source_config.get("dq_profile_key", "intake_basic_gx"),
            "min_quality_score": source_config.get("min_quality_score", 0.8),
            "max_file_size_bytes": source_config.get("max_file_size_bytes"),
        }

    @staticmethod
    def _connect_to_source_task(
        input_data: Dict[str, Any], instance: WorkflowInstance, step
    ) -> Dict[str, Any]:
        """
        Connect to source and validate connection.

        Args:
            input_data: Workflow input data
            instance: Workflow instance
            step: Workflow step

        Returns:
            Task output with connection status
        """
        source_type = input_data.get("source_type")
        source_config = input_data.get("source_config")

        try:
            SourceConnectorFactory = _get_source_connector_factory()
            connector = SourceConnectorFactory.get_connector(source_type)
            # Test connection by attempting to list files (with limit)
            test_result = connector.test_connection(source_config)

            # Handle both bool and dict return types from test_connection
            # ROOT CAUSE: SourceConnector.test_connection() returns bool, but code expected dict
            # SOLUTION: Check type and handle both cases gracefully
            if isinstance(test_result, bool):
                # test_connection returned bool (True/False)
                if not test_result:
                    raise ConnectionError("Connection test failed: Unable to connect to source")
                connection_details = {}
            elif isinstance(test_result, dict):
                # test_connection returned dict (legacy or extended format)
                if not test_result.get("success", False):
                    raise ConnectionError(
                        f"Connection test failed: {test_result.get('error', 'Unknown error')}"
                    )
                connection_details = test_result.get("details", {})
            else:
                # Unexpected return type
                raise ConnectionError(
                    f"Unexpected test_connection return type: {type(test_result)}"
                )

            logger.info(
                "Connected to source",
                workflow_instance_id=str(instance.id),
                source_type=source_type,
            )

            return {
                "connected": True,
                "connector_type": source_type,
                "connection_details": connection_details,
            }
        except Exception as e:
            logger.error(
                "Failed to connect to source",
                workflow_instance_id=str(instance.id),
                source_type=source_type,
                error=str(e),
                exc_info=True,
            )
            raise ConnectionError(f"Failed to connect to source: {str(e)}") from e

    @staticmethod
    def _discover_files_task(
        input_data: Dict[str, Any], instance: WorkflowInstance, step
    ) -> Dict[str, Any]:
        """
        Discover files from source.

        Args:
            input_data: Workflow input data
            instance: Workflow instance
            step: Workflow step

        Returns:
            Task output with discovered files
        """
        source_type = input_data.get("source_type")
        source_config = input_data.get("source_config")
        file_pattern = input_data.get("file_pattern")
        scheduled_ingestion_id = input_data.get("scheduled_ingestion_id")

        try:
            SourceConnectorFactory = _get_source_connector_factory()
            connector = SourceConnectorFactory.get_connector(source_type)
            # Use default pattern that matches all files if pattern is None
            pattern = file_pattern or ".*"
            files = connector.discover_files(source_config, pattern)

            logger.info(
                "Files discovered",
                workflow_instance_id=str(instance.id),
                scheduled_ingestion_id=scheduled_ingestion_id,
                files_found=len(files),
                source_type=source_type,
            )

            return {"files_found": len(files), "discovered_files": files}
        except Exception as e:
            logger.error(
                "Failed to discover files",
                workflow_instance_id=str(instance.id),
                scheduled_ingestion_id=scheduled_ingestion_id,
                source_type=source_type,
                error=str(e),
                exc_info=True,
            )
            raise ConnectionError(f"Failed to discover files: {str(e)}") from e

    @staticmethod
    def _filter_files_task(
        input_data: Dict[str, Any], instance: WorkflowInstance, step
    ) -> Dict[str, Any]:
        """
        Filter files based on incremental state and configuration.

        Args:
            input_data: Workflow input data
            instance: Workflow instance
            step: Workflow step

        Returns:
            Task output with filtered files
        """
        scheduled_ingestion_id = input_data.get("scheduled_ingestion_id")
        discovered_files = input_data.get("discovered_files", [])
        source_type = input_data.get("source_type")
        source_config = input_data.get("source_config")
        max_file_size_bytes = input_data.get("max_file_size_bytes")

        scheduled_ingestion = ScheduledIngestion.objects.get(id=scheduled_ingestion_id)
        state_manager = IncrementalStateManager(scheduled_ingestion)

        filtered_files = []
        SourceConnectorFactory = _get_source_connector_factory()
        connector = SourceConnectorFactory.get_connector(source_type)

        for file_path in discovered_files:
            # Get file metadata for filtering
            file_timestamp = None
            file_size = None
            try:
                metadata = connector.get_file_metadata(source_config, file_path)
                last_modified = metadata.get("last_modified")
                if last_modified:
                    if isinstance(last_modified, str):
                        from dateutil.parser import parse

                        last_modified = parse(last_modified)
                    file_timestamp = last_modified
                file_size = metadata.get("size")
            except Exception:
                pass  # Continue without metadata

            # Check if file should be processed using state manager
            if not state_manager.should_process_file(file_path, file_timestamp):
                continue

            # Apply file size limits (if configured)
            if max_file_size_bytes and file_size and file_size > max_file_size_bytes:
                logger.warning(
                    "File exceeds size limit, skipping",
                    file_path=file_path,
                    file_size=file_size,
                    max_size=max_file_size_bytes,
                )
                continue

            filtered_files.append(
                {
                    "file_path": file_path,
                    "file_timestamp": file_timestamp.isoformat() if file_timestamp else None,
                    "file_size": file_size,
                }
            )

        logger.info(
            "Files filtered",
            workflow_instance_id=str(instance.id),
            scheduled_ingestion_id=scheduled_ingestion_id,
            total_files=len(discovered_files),
            filtered_files=len(filtered_files),
        )

        # Store filtered_files in state_data for loop step
        return {
            "filtered_files": filtered_files,
            "files_filtered": len(filtered_files),
            "state": {"filtered_files": filtered_files},
        }

    @staticmethod
    @transaction.atomic
    def _download_file_task(
        input_data: Dict[str, Any], instance: WorkflowInstance, step
    ) -> Dict[str, Any]:
        """
        Download file from source to temporary location.

        Args:
            input_data: Workflow input data (includes loop_item for file_path)
            instance: Workflow instance
            step: Workflow step

        Returns:
            Task output with file download information
        """
        scheduled_ingestion_id = input_data.get("scheduled_ingestion_id")
        source_type = input_data.get("source_type")
        source_config = input_data.get("source_config")

        # Get file_path from loop_item (set by loop step) or input_data
        loop_item = input_data.get("loop_item")
        if loop_item:
            if isinstance(loop_item, dict):
                file_info = loop_item
                file_path = file_info.get("file_path")
            elif isinstance(loop_item, str):
                file_path = loop_item
                file_info = {"file_path": file_path}
            else:
                file_path = None
                file_info = {}
        else:
            file_info = input_data.get("file_info", {})
            file_path = file_info.get("file_path") if isinstance(file_info, dict) else None

        if not file_path:
            raise ValueError("file_path is required")

        scheduled_ingestion = ScheduledIngestion.objects.get(id=scheduled_ingestion_id)
        tenant = scheduled_ingestion.tenant

        temp_file = None
        temp_path = None
        try:
            SourceConnectorFactory = _get_source_connector_factory()
            connector = SourceConnectorFactory.get_connector(source_type)

            # Create temporary file
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=Path(file_path).suffix)
            temp_path = temp_file.name
            temp_file.close()

            # Download file
            result = connector.download_file(source_config, file_path, temp_path)

            if result.status.value != "SUCCESS":
                raise Exception(f"Failed to download file: {result.message}")

            # Read file content
            with open(temp_path, "rb") as f:
                file_content = f.read()

            # Determine file format from extension
            file_ext = Path(file_path).suffix.lower()
            format_map = {
                ".csv": "CSV",
                ".json": "JSON",
                ".parquet": "PARQUET",
                ".xlsx": "XLSX",
                ".xls": "XLS",
            }
            file_format = format_map.get(file_ext, "CSV")

            # Determine content type from format
            content_type_map = {
                "CSV": "text/csv",
                "JSON": "application/json",
                "PARQUET": "application/octet-stream",
                "XLSX": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                "XLS": "application/vnd.ms-excel",
            }
            content_type = content_type_map.get(file_format, "application/octet-stream")

            # Calculate SHA-256 hash
            file_hash = hashlib.sha256(file_content).hexdigest()

            logger.info(
                "File downloaded",
                workflow_instance_id=str(instance.id),
                scheduled_ingestion_id=scheduled_ingestion_id,
                file_path=file_path,
                file_size=len(file_content),
                file_format=file_format,
            )

            return {
                "file_path": file_path,
                "temp_path": temp_path,
                "file_content_length": len(file_content),
                "file_format": file_format,
                "content_type": content_type,
                "file_hash": file_hash,
                "file_info": file_info,
            }
        except Exception as e:
            # Clean up temp file on error
            if temp_path and os.path.exists(temp_path):
                try:
                    os.unlink(temp_path)
                except Exception:
                    pass

            logger.error(
                "Failed to download file",
                workflow_instance_id=str(instance.id),
                scheduled_ingestion_id=scheduled_ingestion_id,
                file_path=file_path,
                error=str(e),
                exc_info=True,
            )
            raise

    @staticmethod
    def _validate_file_task(
        input_data: Dict[str, Any], instance: WorkflowInstance, step
    ) -> Dict[str, Any]:
        """
        Validate file format and content.

        Args:
            input_data: Workflow input data
            instance: Workflow instance
            step: Workflow step

        Returns:
            Task output with validation results
        """
        file_path = input_data.get("file_path")
        file_format = input_data.get("file_format")
        file_content_length = input_data.get("file_content_length", 0)

        # Basic validation
        if file_content_length == 0:
            raise ValueError(f"File {file_path} is empty")

        # Validate file format is supported
        supported_formats = ["CSV", "JSON", "PARQUET", "XLSX", "XLS"]
        if file_format not in supported_formats:
            raise ValueError(f"Unsupported file format: {file_format}")

        # Validate file using ScheduledIngestionBusinessRules
        scheduled_ingestion_id = instance.state_data.get("scheduled_ingestion_id")
        if scheduled_ingestion_id:
            try:
                scheduled_ingestion = ScheduledIngestion.objects.get(id=scheduled_ingestion_id)
                ingestion_rules = ScheduledIngestionBusinessRules(
                    tenant_id=(
                        str(scheduled_ingestion.tenant_id)
                        if scheduled_ingestion.tenant_id
                        else None
                    ),
                    user_id=str(instance.created_by_id) if instance.created_by_id else None,
                )

                # Validate file format and size using business rules
                file_validation_result = ingestion_rules.validate(
                    schedule=scheduled_ingestion,
                    tenant=scheduled_ingestion.tenant,
                    user=instance.created_by,
                    validation_type="source",
                )

                if not file_validation_result.is_valid:
                    error_messages = file_validation_result.errors
                    raise ValueError(f"File validation failed: {'; '.join(error_messages)}")

                # Log validation warnings if any
                if file_validation_result.warnings:
                    logger.warning(
                        "File validation warnings",
                        workflow_instance_id=str(instance.id),
                        file_path=file_path,
                        warnings=file_validation_result.warnings,
                    )
            except ScheduledIngestion.DoesNotExist:
                logger.warning(
                    "Scheduled ingestion not found for file validation",
                    workflow_instance_id=str(instance.id),
                    scheduled_ingestion_id=scheduled_ingestion_id,
                )

        logger.info(
            "File validated",
            workflow_instance_id=str(instance.id),
            file_path=file_path,
            file_format=file_format,
            file_size=file_content_length,
        )

        return {"validated": True, "file_format": file_format}

    @staticmethod
    def _run_dq_check_task(
        input_data: Dict[str, Any], instance: WorkflowInstance, step
    ) -> Dict[str, Any]:
        """
        Run data quality check on file content.

        Args:
            input_data: Workflow input data
            instance: Workflow instance
            step: Workflow step

        Returns:
            Task output with DQ results
        """
        scheduled_ingestion_id = input_data.get("scheduled_ingestion_id")
        file_path = input_data.get("file_path")
        temp_path = input_data.get("temp_path")
        file_format = input_data.get("file_format")
        dq_profile_key = input_data.get("dq_profile_key", "intake_basic_gx")
        dq_strict_mode = input_data.get("dq_strict_mode", True)
        min_quality_score = input_data.get("min_quality_score", 0.8)

        scheduled_ingestion = ScheduledIngestion.objects.get(id=scheduled_ingestion_id)
        contract = scheduled_ingestion.contract

        try:
            from hub.apps.dq.service_client import DQServiceClient

            # Read file content
            with open(temp_path, "rb") as f:
                file_content = f.read()

            # Initialize DQ client
            dq_client = DQServiceClient()

            # Check DQ service health
            is_healthy, _ = dq_client.health_check()
            if not is_healthy:
                logger.warning(
                    "DQ service is unavailable, skipping DQ check",
                    workflow_instance_id=str(instance.id),
                    scheduled_ingestion_id=scheduled_ingestion_id,
                )
                return {"dq_check_skipped": True, "reason": "DQ service unavailable"}

            # Run DQ check
            dq_result = dq_client.run_dq(
                file_content=file_content,
                file_format=file_format.lower(),
                profile_key=dq_profile_key,
                contract=contract,
            )

            # Validate DQ result
            overall_status = dq_result.get("overall_status", "").upper()
            quality_score = dq_result.get("quality_score", 0.0)

            # Check quality score threshold
            if quality_score < min_quality_score:
                error_message = (
                    f"DQ quality score {quality_score:.2%} below threshold {min_quality_score:.2%}"
                )
                logger.warning(
                    "DQ quality score below threshold",
                    workflow_instance_id=str(instance.id),
                    file_path=file_path,
                    quality_score=quality_score,
                    min_quality_score=min_quality_score,
                )
                if dq_strict_mode:
                    raise ValueError(error_message)

            # Check overall status
            if overall_status not in ["PASS", "SUCCESS"]:
                error_message = f"DQ check failed with status: {overall_status}"
                logger.warning(
                    "DQ check failed",
                    workflow_instance_id=str(instance.id),
                    file_path=file_path,
                    overall_status=overall_status,
                )
                if dq_strict_mode:
                    raise ValueError(error_message)

            # Check for critical failures
            checks = dq_result.get("checks", [])
            critical_failures = [
                check
                for check in checks
                if check.get("severity", "").upper() == "CRITICAL"
                and check.get("status", "").upper() not in ["PASS", "SUCCESS"]
            ]

            if critical_failures and dq_strict_mode:
                raise ValueError(f"DQ check failed with {len(critical_failures)} critical failures")

            logger.info(
                "DQ check completed",
                workflow_instance_id=str(instance.id),
                file_path=file_path,
                overall_status=overall_status,
                quality_score=quality_score,
            )

            return {
                "dq_check_passed": True,
                "dq_result": dq_result,
                "overall_status": overall_status,
                "quality_score": quality_score,
            }
        except Exception as e:
            logger.error(
                "DQ check failed",
                workflow_instance_id=str(instance.id),
                scheduled_ingestion_id=scheduled_ingestion_id,
                file_path=file_path,
                error=str(e),
                exc_info=True,
            )
            if dq_strict_mode:
                raise ValueError(f"DQ check failed: {str(e)}") from e
            return {"dq_check_failed": True, "error": str(e)}

    @staticmethod
    @transaction.atomic
    def _create_dataset_version_task(
        input_data: Dict[str, Any], instance: WorkflowInstance, step
    ) -> Dict[str, Any]:
        """
        Create dataset version from file.

        Args:
            input_data: Workflow input data
            instance: Workflow instance
            step: Workflow step

        Returns:
            Task output with dataset ID
        """
        scheduled_ingestion_id = input_data.get("scheduled_ingestion_id")
        file_path = input_data.get("file_path")
        temp_path = input_data.get("temp_path")
        file_format = input_data.get("file_format")
        content_type = input_data.get("content_type")
        file_hash = input_data.get("file_hash")
        dq_result = input_data.get("dq_result")

        scheduled_ingestion = ScheduledIngestion.objects.get(id=scheduled_ingestion_id)
        tenant = scheduled_ingestion.tenant

        # Read file content
        with open(temp_path, "rb") as f:
            file_content = f.read()

        # Create File record
        file_obj = File.objects.create(
            tenant=tenant,
            name=Path(file_path).name,
            content_type=content_type,
            size=len(file_content),
            status=FileStatus.ACTIVE,
            created_by=scheduled_ingestion.created_by,
            content_sha256=file_hash,
        )

        # Upload file to storage
        storage = S3StorageClient()
        storage_path = storage.save_file(
            tenant_id=str(tenant.id),
            file_id=str(file_obj.id),
            file_content=ContentFile(file_content, name=Path(file_path).name),
        )
        file_obj.storage_path = storage_path
        file_obj.save(update_fields=["storage_path"])

        # Infer schema
        from hub.apps.datasets.schema_inference import (
            extract_sample_data,
            infer_schema_from_csv,
            infer_schema_from_excel,
            infer_schema_from_json,
            infer_schema_from_parquet,
        )

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
        except Exception as e:
            logger.warning(
                "Schema inference failed",
                workflow_instance_id=str(instance.id),
                file_id=str(file_obj.id),
                file_format=file_format,
                error=str(e),
            )

        # Extract sample data
        try:
            sample_data_json = extract_sample_data(file_content, file_format)
        except Exception as e:
            logger.warning(
                "Sample data extraction failed",
                workflow_instance_id=str(instance.id),
                file_id=str(file_obj.id),
                file_format=file_format,
                error=str(e),
            )
            sample_data_json = []

        # Get or create asset
        asset = scheduled_ingestion.asset
        if not asset and scheduled_ingestion.auto_create_asset:
            asset_key = f"scheduled-ingestion-{scheduled_ingestion.id}"
            counter = 1
            while Asset.objects.filter(tenant=tenant, key=asset_key).exists():
                asset_key = f"scheduled-ingestion-{scheduled_ingestion.id}-{counter}"
                counter += 1

            asset = Asset.objects.create(
                tenant=tenant,
                key=asset_key,
                name=scheduled_ingestion.name,
                description=scheduled_ingestion.description
                or f"Asset created from scheduled ingestion {scheduled_ingestion.name}",
                status=AssetStatus.DRAFT,
                created_by=scheduled_ingestion.created_by,
            )
            scheduled_ingestion.asset = asset
            scheduled_ingestion.save(update_fields=["asset"])

        # Get next version for asset
        version = 1
        parent_version = None
        if asset:
            latest_dataset = (
                Dataset.objects.filter(tenant=tenant, asset=asset).order_by("-version").first()
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

        # Create dataset (Dataset model uses snapshot_metadata for DQ/version metadata, not kind/metadata_json)
        dataset = Dataset.objects.create(
            tenant=tenant,
            asset=asset,
            file=file_obj,
            schema_json=schema_json,
            sample_data_json=sample_data_json,
            row_count=schema_json.get("row_count_estimated"),
            format=file_format,
            version=version,
            created_by=scheduled_ingestion.created_by,
            snapshot_metadata=metadata_json if metadata_json else {},
        )

        # Initialize version history
        from hub.apps.datasets.versioning import VersionHistoryManager

        VersionHistoryManager.create_version(
            dataset=dataset, parent_version=parent_version, is_current=True
        )

        # Auto-activate asset if configured
        if asset and scheduled_ingestion.auto_activate:
            asset.status = AssetStatus.ACTIVE
            asset.save(update_fields=["status"])

        logger.info(
            "Dataset version created",
            workflow_instance_id=str(instance.id),
            scheduled_ingestion_id=scheduled_ingestion_id,
            file_path=file_path,
            dataset_id=str(dataset.id),
            version=version,
        )

        return {
            "dataset_id": str(dataset.id),
            "file_id": str(file_obj.id),
            "asset_id": str(asset.id) if asset else None,
            "version": version,
        }

    @staticmethod
    @transaction.atomic
    def _index_dataset_task(
        input_data: Dict[str, Any], instance: WorkflowInstance, step
    ) -> Dict[str, Any]:
        """
        Index dataset for search.

        Args:
            input_data: Workflow input data
            instance: Workflow instance
            step: Workflow step

        Returns:
            Task output with indexing results
        """
        dataset_id = input_data.get("dataset_id")

        if not dataset_id:
            raise ValueError("dataset_id is required")

        try:
            dataset = Dataset.objects.get(id=dataset_id)
            SearchIndexer.index_dataset(dataset)

            logger.info(
                "Dataset indexed", workflow_instance_id=str(instance.id), dataset_id=dataset_id
            )

            return {"indexed": True, "dataset_id": dataset_id}
        except Exception as e:
            logger.error(
                "Failed to index dataset",
                workflow_instance_id=str(instance.id),
                dataset_id=dataset_id,
                error=str(e),
                exc_info=True,
            )
            # Don't fail workflow if indexing fails
            return {"indexed": False, "error": str(e)}

    @staticmethod
    @transaction.atomic
    def _mark_file_processed_task(
        input_data: Dict[str, Any], instance: WorkflowInstance, step
    ) -> Dict[str, Any]:
        """
        Mark file as processed in ingestion state.

        Args:
            input_data: Workflow input data
            instance: Workflow instance
            step: Workflow step

        Returns:
            Task output with processing status
        """
        scheduled_ingestion_id = input_data.get("scheduled_ingestion_id")
        file_path = input_data.get("file_path")
        dataset_id = input_data.get("dataset_id")
        # Get file_info from loop_item or input_data
        loop_item = input_data.get("loop_item")
        if loop_item:
            if isinstance(loop_item, dict):
                file_info = loop_item
            else:
                file_info = {"file_path": str(loop_item)}
        else:
            file_info = input_data.get("file_info", {})

        scheduled_ingestion = ScheduledIngestion.objects.get(id=scheduled_ingestion_id)
        state_manager = IncrementalStateManager(scheduled_ingestion)

        # Get file timestamp from file_info
        file_timestamp = None
        if isinstance(file_info, dict):
            timestamp_str = file_info.get("file_timestamp")
            if timestamp_str:
                from dateutil.parser import parse

                file_timestamp = parse(timestamp_str)

        # Mark file as processed
        state_manager.mark_file_processed(
            file_path=file_path, file_timestamp=file_timestamp, dataset_id=dataset_id
        )

        logger.info(
            "File marked as processed",
            workflow_instance_id=str(instance.id),
            scheduled_ingestion_id=scheduled_ingestion_id,
            file_path=file_path,
            dataset_id=dataset_id,
        )

        return {"processed": True, "file_path": file_path, "dataset_id": dataset_id}

    @staticmethod
    @transaction.atomic
    def _update_ingestion_state_task(
        input_data: Dict[str, Any], instance: WorkflowInstance, step
    ) -> Dict[str, Any]:
        """
        Update ingestion state summary.

        Args:
            input_data: Workflow input data
            instance: Workflow instance
            step: Workflow step

        Returns:
            Task output with state summary
        """
        scheduled_ingestion_id = input_data.get("scheduled_ingestion_id")

        scheduled_ingestion = ScheduledIngestion.objects.get(id=scheduled_ingestion_id)
        state_manager = IncrementalStateManager(scheduled_ingestion)

        state_summary = state_manager.get_state_summary()

        logger.info(
            "Ingestion state updated",
            workflow_instance_id=str(instance.id),
            scheduled_ingestion_id=scheduled_ingestion_id,
            total_processed=state_summary["total_processed"],
            total_failed=state_summary["total_failed"],
        )

        return {"state_summary": state_summary}

    @staticmethod
    @transaction.atomic
    def _handle_failures_dlq_task(
        input_data: Dict[str, Any], instance: WorkflowInstance, step
    ) -> Dict[str, Any]:
        """
        Handle failures and sync to Dead Letter Queue.

        Args:
            input_data: Workflow input data
            instance: Workflow instance
            step: Workflow step

        Returns:
            Task output with DLQ sync results
        """
        scheduled_ingestion_id = input_data.get("scheduled_ingestion_id")

        try:
            # Sync DLQ items from ingestion state
            items_synced = DeadLetterQueueManager.sync_from_ingestion_state(scheduled_ingestion_id)

            logger.info(
                "DLQ items synced",
                workflow_instance_id=str(instance.id),
                scheduled_ingestion_id=scheduled_ingestion_id,
                items_synced=items_synced,
            )

            return {"dlq_synced": True, "items_synced": items_synced}
        except Exception as e:
            logger.error(
                "Failed to sync DLQ items",
                workflow_instance_id=str(instance.id),
                scheduled_ingestion_id=scheduled_ingestion_id,
                error=str(e),
                exc_info=True,
            )
            # Don't fail workflow if DLQ sync fails
            return {"dlq_synced": False, "error": str(e)}

    @staticmethod
    def _send_completion_notification_task(
        input_data: Dict[str, Any], instance: WorkflowInstance, step
    ) -> Dict[str, Any]:
        """
        Send completion notification.

        Args:
            input_data: Workflow input data
            instance: Workflow instance
            step: Workflow step

        Returns:
            Task output with notification status
        """
        scheduled_ingestion_id = input_data.get("scheduled_ingestion_id")
        state_summary = input_data.get("state_summary", {})

        scheduled_ingestion = ScheduledIngestion.objects.get(id=scheduled_ingestion_id)

        # Only send notification if configured
        source_config = scheduled_ingestion.source_config or {}
        if not source_config.get("send_notifications", True):
            return {"notification_sent": False, "reason": "Notifications disabled"}

        try:
            # Get notification recipients
            recipients = source_config.get("notification_recipients", [])
            if not recipients and scheduled_ingestion.created_by:
                recipients = [scheduled_ingestion.created_by.email]

            if not recipients:
                return {"notification_sent": False, "reason": "No recipients configured"}

            # Prepare notification content
            subject = f"Scheduled Ingestion Completed: {scheduled_ingestion.name}"
            message = f"""
Scheduled ingestion '{scheduled_ingestion.name}' has completed.

Summary:
- Files processed: {state_summary.get('total_processed', 0)}
- Files failed: {state_summary.get('total_failed', 0)}
- Permanent failures: {state_summary.get('permanent_failures', 0)}
- Retryable failures: {state_summary.get('retryable_failures', 0)}

Workflow Instance: {instance.id}
            """

            # Send notification (sync; send_email_async is a function, not a Celery task)
            for recipient in recipients:
                send_email_async(
                    email_type=EmailType.JOB_COMPLETION,
                    to_email=recipient,
                    subject=subject,
                    template_name="notifications/emails/job_completion.html",
                    context={
                        "user": scheduled_ingestion.created_by,
                        "job_type": "Scheduled Ingestion",
                        "resource_type": "scheduled_ingestion",
                        "resource_id": str(scheduled_ingestion.id),
                        "result_summary": message.strip(),
                        "job_url": None,
                    },
                )

            logger.info(
                "Completion notification sent",
                workflow_instance_id=str(instance.id),
                scheduled_ingestion_id=scheduled_ingestion_id,
                recipients=recipients,
            )

            return {"notification_sent": True, "recipients": recipients}
        except Exception as e:
            logger.error(
                "Failed to send completion notification",
                workflow_instance_id=str(instance.id),
                scheduled_ingestion_id=scheduled_ingestion_id,
                error=str(e),
                exc_info=True,
            )
            # Don't fail workflow if notification fails
            return {"notification_sent": False, "error": str(e)}

    @staticmethod
    @transaction.atomic
    def _audit_logging_task(
        input_data: Dict[str, Any], instance: WorkflowInstance, step
    ) -> Dict[str, Any]:
        """
        Create audit log entry for ingestion completion.

        Args:
            input_data: Workflow input data
            instance: Workflow instance
            step: Workflow step

        Returns:
            Task output with audit log ID
        """
        scheduled_ingestion_id = input_data.get("scheduled_ingestion_id")
        state_summary = input_data.get("state_summary", {})

        scheduled_ingestion = ScheduledIngestion.objects.get(id=scheduled_ingestion_id)

        try:
            audit_event = create_audit_event(
                resource_type="scheduled_ingestion",
                action="SCHEDULED_INGESTION_COMPLETED",
                actor_user=scheduled_ingestion.created_by,
                tenant=scheduled_ingestion.tenant,
                resource_id=str(scheduled_ingestion.id),
                result="SUCCESS",
                details={
                    "workflow_instance_id": str(instance.id),
                    "files_processed": state_summary.get("total_processed", 0),
                    "files_failed": state_summary.get("total_failed", 0),
                    "permanent_failures": state_summary.get("permanent_failures", 0),
                    "retryable_failures": state_summary.get("retryable_failures", 0),
                },
            )

            logger.info(
                "Audit log created",
                workflow_instance_id=str(instance.id),
                scheduled_ingestion_id=scheduled_ingestion_id,
                audit_event_id=str(audit_event.id),
            )

            return {"audit_logged": True, "audit_event_id": str(audit_event.id)}
        except Exception as e:
            logger.error(
                "Failed to create audit log",
                workflow_instance_id=str(instance.id),
                scheduled_ingestion_id=scheduled_ingestion_id,
                error=str(e),
                exc_info=True,
            )
            # Don't fail workflow if audit logging fails
            return {"audit_logged": False, "error": str(e)}

    # Compensation tasks
    @staticmethod
    def _rollback_connection_task(
        input_data: Dict[str, Any], instance: WorkflowInstance, step
    ) -> Dict[str, Any]:
        """Rollback connection (no-op, connection is stateless)"""
        return {"rolled_back": True}

    @staticmethod
    @transaction.atomic
    def _rollback_file_download_task(
        input_data: Dict[str, Any], instance: WorkflowInstance, step
    ) -> Dict[str, Any]:
        """Rollback file download: clean up temp file and mark file as failed for counting."""
        temp_path = input_data.get("temp_path")
        if temp_path and os.path.exists(temp_path):
            try:
                os.unlink(temp_path)
            except Exception:
                pass
        # Mark current file as failed so state_summary total_failed is correct
        file_path = input_data.get("file_path")
        if not file_path:
            loop_item = input_data.get("loop_item")
            if isinstance(loop_item, dict):
                file_path = loop_item.get("file_path")
            elif isinstance(loop_item, str):
                file_path = loop_item
        if file_path:
            scheduled_ingestion_id = input_data.get("scheduled_ingestion_id")
            if scheduled_ingestion_id:
                try:
                    si = ScheduledIngestion.objects.get(id=scheduled_ingestion_id)
                    state_manager = IncrementalStateManager(si)
                    state_manager.mark_file_failed(
                        file_path=file_path,
                        error_message=input_data.get("last_error") or "Step failed",
                    )
                except ScheduledIngestion.DoesNotExist:
                    pass
                except Exception as e:
                    logger.warning(
                        "Failed to mark file as failed in rollback",
                        file_path=file_path,
                        error=str(e),
                    )
        return {"rolled_back": True}

    @staticmethod
    @transaction.atomic
    def _rollback_dataset_creation_task(
        input_data: Dict[str, Any], instance: WorkflowInstance, step
    ) -> Dict[str, Any]:
        """Rollback dataset creation by deleting dataset and file"""
        dataset_id = input_data.get("dataset_id")
        file_id = input_data.get("file_id")

        if dataset_id:
            try:
                dataset = Dataset.objects.get(id=dataset_id)
                dataset.delete()
            except Dataset.DoesNotExist:
                pass

        if file_id:
            try:
                file_obj = File.objects.get(id=file_id)
                # Delete from storage
                storage = S3StorageClient()
                try:
                    storage.delete_file(file_obj.storage_path)
                except Exception:
                    pass
                file_obj.delete()
            except File.DoesNotExist:
                pass

        return {"rolled_back": True}

    @staticmethod
    @transaction.atomic
    def _rollback_indexing_task(
        input_data: Dict[str, Any], instance: WorkflowInstance, step
    ) -> Dict[str, Any]:
        """Rollback indexing by deleting search index"""
        dataset_id = input_data.get("dataset_id")

        if dataset_id:
            try:
                SearchIndexer.delete_index(
                    tenant_id=input_data.get("tenant_id"),
                    resource_type="dataset",
                    resource_id=dataset_id,
                )
            except Exception:
                pass

        return {"rolled_back": True}

    @classmethod
    @transaction.atomic
    def execute(
        cls,
        scheduled_ingestion_id: str,
        engine: Optional[WorkflowEngine] = None,
        registry: Optional[WorkflowRegistry] = None,
    ) -> Dict[str, Any]:
        """
        Execute scheduled ingestion workflow.

        Args:
            scheduled_ingestion_id: Scheduled ingestion ID
            engine: Optional WorkflowEngine instance (creates new if not provided)
            registry: Optional WorkflowRegistry instance (creates new if not provided)

        Returns:
            Workflow execution result dictionary

        Raises:
            ValueError: If workflow execution fails
        """
        # Create engine and registry if not provided
        if engine is None:
            engine = WorkflowEngine()
            cls.register_tasks(engine)

        if registry is None:
            registry = WorkflowRegistry()
            cls.register_workflow(registry)

        # Get scheduled ingestion
        try:
            scheduled_ingestion = ScheduledIngestion.objects.get(id=scheduled_ingestion_id)
        except ScheduledIngestion.DoesNotExist:
            raise ValueError(f"Scheduled ingestion {scheduled_ingestion_id} not found")

        # Prepare workflow input
        workflow_input = {
            "scheduled_ingestion_id": str(scheduled_ingestion.id),
            "tenant_id": str(scheduled_ingestion.tenant.id),
            "user_id": (
                str(scheduled_ingestion.created_by.id) if scheduled_ingestion.created_by else None
            ),
        }

        # Create workflow instance
        workflow_instance = engine.create_instance(
            workflow_name=cls.WORKFLOW_NAME,
            input_data=workflow_input,
            tenant_id=str(scheduled_ingestion.tenant.id),
            created_by_id=(
                str(scheduled_ingestion.created_by.id) if scheduled_ingestion.created_by else None
            ),
        )

        # Start and execute workflow
        workflow_instance = engine.start_instance(str(workflow_instance.id))
        workflow_instance = engine.execute_instance(str(workflow_instance.id))

        # Check workflow status
        if workflow_instance.status == WorkflowStatus.COMPLETED:
            logger.info(
                "Scheduled ingestion workflow completed",
                scheduled_ingestion_id=scheduled_ingestion_id,
                workflow_instance_id=str(workflow_instance.id),
            )
            return {
                "success": True,
                "workflow_instance_id": str(workflow_instance.id),
                "output_data": workflow_instance.output_data,
            }
        else:
            error_message = workflow_instance.error_message or "Workflow execution failed"
            logger.error(
                "Scheduled ingestion workflow failed",
                scheduled_ingestion_id=scheduled_ingestion_id,
                workflow_instance_id=str(workflow_instance.id),
                error=error_message,
            )
            raise ValueError(f"Scheduled ingestion workflow failed: {error_message}")
