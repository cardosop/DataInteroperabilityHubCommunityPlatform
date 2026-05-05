"""
Phase 250.5.A — typed exceptions for federated-import gating.

The platform's existing ``hub.apps.core.services.base`` module exposes
generic ``ValidationError`` / ``ConflictError`` / ``NotFoundError``
that the integrations service uses for most paths. The federated-
import gates introduced in Phase 250.5.A need a DEDICATED exception
type so callers can distinguish gate refusals (recoverable: ops
flips a flag, retry succeeds) from other validation failures (caller
must fix the request body).

The exception carries a structured ``code`` mirroring the audit
event's ``details_json["code"]`` so caller-side error handlers and
audit-replay queries reach the same enumeration:

* ``"FEDERATED_IMPORT_DISABLED"`` — tenant flag is False (D250.3).
* ``"CROSS_REGION_CONSENT_REQUIRED"`` — region mismatch without
  consent (I2-3 / D250.16-companion).
* ``"COMPLIANCE_FAILED"`` — pre-import compliance gate FAIL.
"""
from __future__ import annotations

from typing import Any, Dict, Optional


class FederatedImportRejected(Exception):
    """Raised by ``MarketplaceIntegrationService.create_federated_asset_with_contracts``
    when a configured gate refuses the import request.

    The raise site emits the corresponding ``FEDERATED_IMPORT_REJECTED``
    (or sub-class) audit event BEFORE this exception propagates, so a
    caller-side ``try/except`` is guaranteed the audit row is durable
    even if the caller subsequently swallows the exception.
    """

    def __init__(
        self,
        message: str,
        *,
        code: str,
        http_status: int = 403,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.http_status = http_status
        self.details = details or {}

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"FederatedImportRejected(code={self.code!r}, "
            f"http_status={self.http_status}, message={self.message!r})"
        )
