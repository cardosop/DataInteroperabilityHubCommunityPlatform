"""
Phase 260.2.F — deterministic sampling for ``FILE_METADATA_VIEWED`` audits.

``GET /api/v1/files/{id}/`` can be high volume; default is a stable ~10% sample
per ``(file_owner_tenant_id, file_id, actor_user_id)`` tuple. Tenants under
investigation set :attr:`~hub.apps.tenants.models.Tenant.compliance_audit_full_sampling`
for 100% metadata-view auditing.
"""
from __future__ import annotations
import hashlib
import uuid

from hub.apps.tenants.models import Tenant

# 10% default sample rate (deterministic, no ``random`` — tests stay stable).
_SAMPLE_MOD = 100
_SAMPLE_THRESHOLD = 10


def file_metadata_view_should_emit(*, file_tenant: Tenant, file_id: uuid.UUID, user_id) -> bool:
    """Return True if this metadata view should emit ``FILE_METADATA_VIEWED``."""
    if getattr(file_tenant, "compliance_audit_full_sampling", False):
        return True
    payload = f"{file_tenant.id}:{file_id}:{user_id}".encode()
    digest = hashlib.sha256(payload).digest()
    bucket = int.from_bytes(digest[:8], "big") % _SAMPLE_MOD
    return bucket < _SAMPLE_THRESHOLD
