"""
Bug Prevention Services

Services for idempotency keys and request deduplication.
"""

import hashlib
import json
from datetime import timedelta
from typing import Any

from django.db import transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.exceptions import APIException

from hub.apps.core.bug_prevention.models import IdempotencyKey, RequestDeduplication
from hub.apps.core.bug_prevention.validators import IdempotencyKeyValidator
from hub.apps.core.services.base import BaseService


class IdempotencyConflictError(APIException):
    """Exception raised when idempotency key conflict occurs."""

    status_code = status.HTTP_409_CONFLICT
    default_code = "IDEMPOTENCY_CONFLICT"
    default_detail = "Idempotency key already used with different request parameters"


class IdempotencyService(BaseService):
    """Service for managing idempotency keys."""

    service_name = "idempotency_service"

    @staticmethod
    def validate_key_format(key: str) -> tuple[bool, str | None]:
        """
        Validate idempotency key format.

        Args:
            key: Idempotency key to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            IdempotencyKeyValidator(key=key)
            return True, None
        except Exception as e:
            return False, str(e)

    @staticmethod
    def check_idempotency(
        tenant_id: str,
        idempotency_key: str,
        method: str,
        path: str,
        body: dict[str, Any] | None = None,
    ) -> tuple[IdempotencyKey | None, dict[str, Any] | None]:
        """
        Check if idempotency key exists and return cached response if found.

        Args:
            tenant_id: Tenant UUID
            idempotency_key: Client-provided idempotency key
            method: HTTP method
            path: Request path
            body: Request body

        Returns:
            Tuple of (idempotency_key_record, cached_response)
            - If key exists with matching fingerprint: (record, cached_response)
            - If key exists with different fingerprint: (record, None) - raises IdempotencyConflictError
            - If key doesn't exist: (None, None)
        """
        # Validate key format
        is_valid, error_message = IdempotencyService.validate_key_format(idempotency_key)
        if not is_valid:
            from rest_framework.exceptions import ValidationError

            raise ValidationError({"idempotency_key": error_message})

        # Compute request fingerprint
        fingerprint = IdempotencyKey.compute_fingerprint(method, path, body)

        # Check for existing record
        try:
            record = IdempotencyKey.objects.get(
                tenant_id=tenant_id,
                idempotency_key=idempotency_key,
                method=method.upper(),
                path=path,
            )
        except IdempotencyKey.DoesNotExist:
            return None, None

        # Check if expired
        if record.is_expired():
            # Delete expired record
            record.delete()
            return None, None

        # Check fingerprint match
        if record.request_fingerprint == fingerprint:
            # Matching request, return cached response
            return record, {"status_code": record.response_status, "data": record.response_body}
        else:
            # Different request with same key, raise conflict
            raise IdempotencyConflictError(
                detail="Idempotency key already used with different request parameters"
            )

    @staticmethod
    @transaction.atomic
    def store_idempotency(
        tenant_id: str,
        idempotency_key: str,
        method: str,
        path: str,
        body: dict[str, Any] | None,
        response_status: int,
        response_body: dict[str, Any],
    ) -> IdempotencyKey:
        """
        Store idempotency key with response.

        Args:
            tenant_id: Tenant UUID
            idempotency_key: Client-provided idempotency key
            method: HTTP method
            path: Request path
            body: Request body
            response_status: HTTP status code
            response_body: Response body

        Returns:
            Created IdempotencyKey record
        """
        # Compute request fingerprint
        fingerprint = IdempotencyKey.compute_fingerprint(method, path, body)

        # Create or update record
        record, _created = IdempotencyKey.objects.update_or_create(
            tenant_id=tenant_id,
            idempotency_key=idempotency_key,
            method=method.upper(),
            path=path,
            defaults={
                "request_fingerprint": fingerprint,
                "response_status": response_status,
                "response_body": response_body,
                "expires_at": timezone.now() + timedelta(hours=24),
            },
        )

        return record

    @staticmethod
    def cleanup_expired(older_than_hours: int = 24) -> int:
        """
        Clean up expired idempotency keys.

        Args:
            older_than_hours: Delete keys older than this many hours

        Returns:
            Number of deleted records
        """
        cutoff_time = timezone.now() - timedelta(hours=older_than_hours)
        deleted_count, _ = IdempotencyKey.objects.filter(expires_at__lt=cutoff_time).delete()
        return deleted_count


class RequestDeduplicationService(BaseService):
    """Service for request deduplication."""

    service_name = "request_deduplication_service"

    @staticmethod
    def check_duplicate(
        tenant_id: str,
        method: str,
        path: str,
        body: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> tuple[bool, RequestDeduplication | None]:
        """
        Check if request is a duplicate.

        Args:
            tenant_id: Tenant UUID
            method: HTTP method
            path: Request path
            body: Request body
            headers: Request headers

        Returns:
            Tuple of (is_duplicate, deduplication_record)
        """
        # Compute fingerprint
        fingerprint = RequestDeduplication.compute_fingerprint(
            tenant_id, method, path, body, headers
        )

        # Check for existing record
        try:
            record = RequestDeduplication.objects.get(request_fingerprint=fingerprint)
        except RequestDeduplication.DoesNotExist:
            return False, None

        # Check if expired
        if record.is_expired():
            record.delete()
            return False, None

        # Request is duplicate
        return True, record

    @staticmethod
    @transaction.atomic
    def store_request(
        tenant_id: str,
        method: str,
        path: str,
        body: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> RequestDeduplication:
        """
        Store request fingerprint for deduplication.

        Args:
            tenant_id: Tenant UUID
            method: HTTP method
            path: Request path
            body: Request body
            headers: Request headers

        Returns:
            Created RequestDeduplication record
        """
        # Compute fingerprint
        fingerprint = RequestDeduplication.compute_fingerprint(
            tenant_id, method, path, body, headers
        )

        # Compute body hash
        body_hash = ""
        if body:
            body_json = json.dumps(body, sort_keys=True)
            body_hash = hashlib.sha256(body_json.encode("utf-8")).hexdigest()

        # Create or update record
        record, _created = RequestDeduplication.objects.update_or_create(
            request_fingerprint=fingerprint,
            defaults={
                "tenant_id": tenant_id,
                "method": method.upper(),
                "path": path,
                "request_body_hash": body_hash,
                "expires_at": timezone.now() + timedelta(minutes=5),
            },
        )

        return record

    @staticmethod
    def cleanup_expired(older_than_minutes: int = 5) -> int:
        """
        Clean up expired deduplication records.

        Args:
            older_than_minutes: Delete records older than this many minutes

        Returns:
            Number of deleted records
        """
        cutoff_time = timezone.now() - timedelta(minutes=older_than_minutes)
        deleted_count, _ = RequestDeduplication.objects.filter(expires_at__lt=cutoff_time).delete()
        return deleted_count
