"""
311.21 (G9) — Shared service interfaces for circular import resolution.

Protocol-based interfaces that both producers and consumers can import
without creating circular dependency chains.
"""
from .contracts import IContractService
from .assets import IAssetService
from .audit import IAuditService
from .notifications import INotificationService

__all__ = [
    "IContractService",
    "IAssetService",
    "IAuditService",
    "INotificationService",
]
