"""
Bug Prevention Models

Models for idempotency keys and request deduplication.
"""
import hashlib
import json
import uuid
from datetime import timedelta
from typing import Any, Dict, Optional

from django.db import models
from django.utils import timezone
from django.db.models import JSONField


class IdempotencyKey(models.Model):
    """
    Idempotency key model for preventing duplicate operations.
    
    Stores idempotency keys with request fingerprints to ensure
    operations are only executed once per unique request.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant_id = models.UUIDField(db_index=True, help_text="Tenant UUID")
    idempotency_key = models.CharField(
        max_length=256,
        db_index=True,
        help_text="Client-provided idempotency key"
    )
    method = models.CharField(max_length=10, help_text="HTTP method (e.g., POST)")
    path = models.CharField(max_length=512, help_text="Request path")
    request_fingerprint = models.CharField(
        max_length=64,
        help_text="SHA-256 hash of method + path + body"
    )
    response_status = models.IntegerField(help_text="HTTP status code of response")
    response_body = JSONField(help_text="Cached response body")
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    expires_at = models.DateTimeField(db_index=True, help_text="Expiry time (24 hours from creation)")
    
    class Meta:
        app_label = "core"
        db_table = "idempotency_keys"
        unique_together = [("tenant_id", "idempotency_key", "method", "path")]
        indexes = [
            models.Index(fields=["tenant_id", "idempotency_key", "method", "path"]),
            models.Index(fields=["expires_at"]),
        ]
        ordering = ["-created_at"]
    
    def __str__(self):
        return f"{self.method} {self.path} - {self.idempotency_key[:16]}..."
    
    @classmethod
    def compute_fingerprint(
        cls,
        method: str,
        path: str,
        body: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Compute request fingerprint from method, path, and body.
        
        Args:
            method: HTTP method
            path: Request path
            body: Request body (optional)
            
        Returns:
            SHA-256 hash as hex string
        """
        # Normalize path (remove trailing slashes, query params)
        normalized_path = path.rstrip("/").split("?")[0]
        
        # Create fingerprint data
        fingerprint_data = {
            "method": method.upper(),
            "path": normalized_path,
            "body": body or {}
        }
        
        # Compute hash
        fingerprint_json = json.dumps(fingerprint_data, sort_keys=True)
        fingerprint_hash = hashlib.sha256(fingerprint_json.encode("utf-8")).hexdigest()
        
        return fingerprint_hash
    
    def is_expired(self) -> bool:
        """Check if idempotency key has expired."""
        return timezone.now() > self.expires_at
    
    def save(self, *args, **kwargs):
        """Override save to set expires_at if not provided."""
        if not self.expires_at:
            self.expires_at = timezone.now() + timedelta(hours=24)
        super().save(*args, **kwargs)


class RequestDeduplication(models.Model):
    """
    Request deduplication model for preventing duplicate requests.
    
    Stores request fingerprints to detect and prevent duplicate
    requests within a time window.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant_id = models.UUIDField(db_index=True, help_text="Tenant UUID")
    request_fingerprint = models.CharField(
        max_length=64,
        db_index=True,
        unique=True,
        help_text="SHA-256 hash of request"
    )
    method = models.CharField(max_length=10, help_text="HTTP method")
    path = models.CharField(max_length=512, help_text="Request path")
    request_body_hash = models.CharField(
        max_length=64,
        help_text="SHA-256 hash of request body"
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    expires_at = models.DateTimeField(db_index=True, help_text="Expiry time (5 minutes from creation)")
    
    class Meta:
        app_label = "core"
        db_table = "request_deduplication"
        indexes = [
            models.Index(fields=["tenant_id", "request_fingerprint"]),
            models.Index(fields=["expires_at"]),
        ]
        ordering = ["-created_at"]
    
    def __str__(self):
        return f"{self.method} {self.path} - {self.request_fingerprint[:16]}..."
    
    @classmethod
    def compute_fingerprint(
        cls,
        tenant_id: str,
        method: str,
        path: str,
        body: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None
    ) -> str:
        """
        Compute request fingerprint for deduplication.
        
        Args:
            tenant_id: Tenant UUID
            method: HTTP method
            path: Request path
            body: Request body (optional)
            headers: Request headers (optional, only relevant headers)
            
        Returns:
            SHA-256 hash as hex string
        """
        # Normalize path
        normalized_path = path.rstrip("/").split("?")[0]
        
        # Select relevant headers (exclude variable ones like Authorization, Date)
        relevant_headers = {}
        if headers:
            for key in ["Content-Type", "Accept"]:
                if key in headers:
                    relevant_headers[key] = headers[key]
        
        # Create fingerprint data
        fingerprint_data = {
            "tenant_id": str(tenant_id),
            "method": method.upper(),
            "path": normalized_path,
            "body": body or {},
            "headers": relevant_headers
        }
        
        # Compute hash
        fingerprint_json = json.dumps(fingerprint_data, sort_keys=True)
        fingerprint_hash = hashlib.sha256(fingerprint_json.encode("utf-8")).hexdigest()
        
        return fingerprint_hash
    
    def is_expired(self) -> bool:
        """Check if deduplication record has expired."""
        return timezone.now() > self.expires_at
    
    def save(self, *args, **kwargs):
        """Override save to set expires_at if not provided."""
        if not self.expires_at:
            self.expires_at = timezone.now() + timedelta(minutes=5)
        super().save(*args, **kwargs)

