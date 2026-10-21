"""
Phase 274.16.12 — Business Rules health endpoint.

Exposes ``BusinessRulesRegistry.degraded_rules`` — a set of rule
names whose registration failed at import time. SRE alert fires
when the set is non-empty.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# Rules whose @register_rule or module import failed.
_degraded: set[str] = set()


def mark_rule_degraded(rule_name: str, error: str) -> None:
    """Record a rule registration failure."""
    _degraded.add(rule_name)
    logger.error("business_rule_registration_failed rule=%s error=%s", rule_name, error)


def get_degraded_rules() -> set[str]:
    """Return the current set of degraded rule names."""
    return set(_degraded)


def clear_degraded_rules() -> None:
    """Reset degraded rules (for testing)."""
    _degraded.clear()


def health_check() -> dict:
    """Return health status for the business-rules subsystem."""
    degraded = get_degraded_rules()
    return {
        "status": "DEGRADED" if degraded else "HEALTHY",
        "degraded_rules": sorted(degraded),
        "degraded_count": len(degraded),
    }
