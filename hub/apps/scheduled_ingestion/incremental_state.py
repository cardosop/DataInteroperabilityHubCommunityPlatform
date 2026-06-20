"""
Incremental Ingestion State Management

Manages incremental ingestion state with atomic transactions and failure tracking.
"""

from datetime import datetime
from typing import Any

import structlog
from django.db import transaction
from django.utils import timezone

from .models import ScheduledIngestion

logger = structlog.get_logger(__name__)


class IncrementalStateManager:
    """
    Manages incremental ingestion state with atomic transactions.
    """

    def __init__(self, scheduled_ingestion: ScheduledIngestion):
        """
        Initialize state manager.

        Args:
            scheduled_ingestion: ScheduledIngestion instance
        """
        self.scheduled_ingestion = scheduled_ingestion
        self.ingestion_state = scheduled_ingestion.ingestion_state or {}

    def get_processed_files(self) -> list[str]:
        """
        Get list of processed files from state.

        Returns:
            List of processed file paths/keys
        """
        return self.ingestion_state.get("processed_files", [])

    def get_failed_files(self) -> list[dict[str, Any]]:
        """
        Get list of failed files with error information.

        Returns:
            List of failed file dictionaries with path and error
        """
        return self.ingestion_state.get("failed_files", [])

    def get_last_processed_file(self) -> str | None:
        """
        Get last processed file path.

        Returns:
            Last processed file path or None
        """
        return self.scheduled_ingestion.last_processed_file

    def get_last_processed_timestamp(self) -> datetime | None:
        """
        Get last processed file timestamp.

        Returns:
            Last processed timestamp or None
        """
        return self.scheduled_ingestion.last_processed_timestamp

    def is_file_processed(self, file_path: str) -> bool:
        """
        Check if file has been processed.

        Args:
            file_path: File path/key to check

        Returns:
            True if file has been processed, False otherwise
        """
        processed_files = self.get_processed_files()
        return file_path in processed_files

    def is_file_failed(self, file_path: str) -> bool:
        """
        Check if file has permanently failed.

        Args:
            file_path: File path/key to check

        Returns:
            True if file has permanently failed, False otherwise
        """
        failed_files = self.get_failed_files()
        return any(f.get("file_path") == file_path for f in failed_files)

    def should_process_file(self, file_path: str, file_timestamp: datetime | None = None) -> bool:
        """
        Determine if file should be processed based on incremental state.

        Args:
            file_path: File path/key to check
            file_timestamp: Optional file modification timestamp

        Returns:
            True if file should be processed, False otherwise
        """
        # Skip if already processed
        if self.is_file_processed(file_path):
            return False

        # Skip if permanently failed
        if self.is_file_failed(file_path):
            return False

        # Check timestamp-based filtering
        last_timestamp = self.get_last_processed_timestamp()
        if last_timestamp and file_timestamp:
            # Only process files newer than last processed
            if file_timestamp <= last_timestamp:
                return False

        return True

    @transaction.atomic
    def mark_file_processed(
        self, file_path: str, file_timestamp: datetime | None = None, dataset_id: str | None = None
    ) -> None:
        """
        Mark file as processed and update state atomically.

        Args:
            file_path: File path/key that was processed
            file_timestamp: Optional file modification timestamp
            dataset_id: Optional dataset ID created from file
        """
        # Refresh from database to get latest state
        self.scheduled_ingestion.refresh_from_db()
        self.ingestion_state = self.scheduled_ingestion.ingestion_state or {}

        # Update processed files list
        processed_files = self.ingestion_state.get("processed_files", [])
        if file_path not in processed_files:
            processed_files.append(file_path)
            # Keep only last 1000 files to prevent unbounded growth
            if len(processed_files) > 1000:
                processed_files = processed_files[-1000:]

        # Update ingestion state
        self.ingestion_state["processed_files"] = processed_files
        self.ingestion_state["last_processed_at"] = timezone.now().isoformat()

        # Update file-to-dataset mapping if provided
        if dataset_id:
            file_mappings = self.ingestion_state.get("file_to_dataset", {})
            file_mappings[file_path] = str(dataset_id)
            self.ingestion_state["file_to_dataset"] = file_mappings

        # Update last processed file and timestamp
        self.scheduled_ingestion.last_processed_file = file_path
        if file_timestamp:
            self.scheduled_ingestion.last_processed_timestamp = file_timestamp
        else:
            self.scheduled_ingestion.last_processed_timestamp = timezone.now()

        # Save state atomically
        self.scheduled_ingestion.ingestion_state = self.ingestion_state
        self.scheduled_ingestion.save(
            update_fields=[
                "last_processed_file",
                "last_processed_timestamp",
                "ingestion_state",
                "updated_at",
            ]
        )

        logger.info(
            "File marked as processed",
            scheduled_ingestion_id=str(self.scheduled_ingestion.id),
            file_path=file_path,
            dataset_id=dataset_id,
        )

    @transaction.atomic
    def mark_file_failed(
        self,
        file_path: str,
        error_message: str,
        error_code: str | None = None,
        retry_count: int = 0,
        max_retries: int = 3,
    ) -> bool:
        """
        Mark file as failed and track failure.

        Args:
            file_path: File path/key that failed
            error_message: Error message
            error_code: Optional error code
            retry_count: Current retry count
            max_retries: Maximum retries before permanent failure

        Returns:
            True if file should be retried, False if permanently failed
        """
        # Refresh from database to get latest state
        self.scheduled_ingestion.refresh_from_db()
        self.ingestion_state = self.scheduled_ingestion.ingestion_state or {}

        # Get failed files
        failed_files = self.ingestion_state.get("failed_files", [])

        # Find existing failure record
        failure_record = None
        for f in failed_files:
            if f.get("file_path") == file_path:
                failure_record = f
                break

        if failure_record:
            # Update existing failure record
            failure_record["retry_count"] = retry_count + 1
            failure_record["last_error"] = error_message
            failure_record["last_error_code"] = error_code
            failure_record["last_failed_at"] = timezone.now().isoformat()
        else:
            # Create new failure record
            failure_record = {
                "file_path": file_path,
                "retry_count": retry_count + 1,
                "first_failed_at": timezone.now().isoformat(),
                "last_failed_at": timezone.now().isoformat(),
                "last_error": error_message,
                "last_error_code": error_code,
                "permanent_failure": False,
            }
            failed_files.append(failure_record)

        # Check if should retry
        should_retry = failure_record["retry_count"] < max_retries

        if not should_retry:
            # Mark as permanent failure
            failure_record["permanent_failure"] = True
            failure_record["permanently_failed_at"] = timezone.now().isoformat()

            logger.warning(
                "File marked as permanently failed",
                scheduled_ingestion_id=str(self.scheduled_ingestion.id),
                file_path=file_path,
                retry_count=failure_record["retry_count"],
                error=error_message,
            )
        else:
            logger.info(
                "File marked as failed (will retry)",
                scheduled_ingestion_id=str(self.scheduled_ingestion.id),
                file_path=file_path,
                retry_count=failure_record["retry_count"],
                max_retries=max_retries,
            )

        # Update state
        self.ingestion_state["failed_files"] = failed_files
        self.scheduled_ingestion.ingestion_state = self.ingestion_state
        self.scheduled_ingestion.save(update_fields=["ingestion_state", "updated_at"])

        return should_retry

    @transaction.atomic
    def clear_failed_file(self, file_path: str) -> None:
        """
        Clear failed file record (e.g., after manual intervention).

        Args:
            file_path: File path/key to clear
        """
        # Refresh from database
        self.scheduled_ingestion.refresh_from_db()
        self.ingestion_state = self.scheduled_ingestion.ingestion_state or {}

        # Remove from failed files
        failed_files = self.ingestion_state.get("failed_files", [])
        failed_files = [f for f in failed_files if f.get("file_path") != file_path]

        # Update state
        self.ingestion_state["failed_files"] = failed_files
        self.scheduled_ingestion.ingestion_state = self.ingestion_state
        self.scheduled_ingestion.save(update_fields=["ingestion_state", "updated_at"])

        logger.info(
            "Failed file record cleared",
            scheduled_ingestion_id=str(self.scheduled_ingestion.id),
            file_path=file_path,
        )

    def get_state_summary(self) -> dict[str, Any]:
        """
        Get summary of ingestion state.

        Returns:
            State summary dictionary
        """
        processed_files = self.get_processed_files()
        failed_files = self.get_failed_files()
        permanent_failures = [f for f in failed_files if f.get("permanent_failure", False)]
        retryable_failures = [f for f in failed_files if not f.get("permanent_failure", False)]

        return {
            "total_processed": len(processed_files),
            "total_failed": len(failed_files),
            "permanent_failures": len(permanent_failures),
            "retryable_failures": len(retryable_failures),
            "last_processed_file": self.get_last_processed_file(),
            "last_processed_timestamp": (
                self.get_last_processed_timestamp().isoformat()
                if self.get_last_processed_timestamp()
                else None
            ),
            "failed_files": failed_files,
        }
