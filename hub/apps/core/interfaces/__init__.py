"""
311.21 (G9) — Shared service interfaces for circular import resolution.

Protocol-based interfaces that both producers and consumers can import
without creating circular dependency chains.
"""

from .assets import IAssetService
from .audit import IAuditService
from .contracts import IContractService
from .notifications import INotificationService

__all__ = [
    "IAssetService",
    "IAuditService",
    "IContractService",
    "INotificationService",
]
