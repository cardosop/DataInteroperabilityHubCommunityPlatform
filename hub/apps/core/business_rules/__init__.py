"""
Business Rules Base Classes

Provides base classes and utilities for implementing business rules validation
across the Data Interoperability Hub.

Features:
- Standardized ValidationResult structure
- Rule execution context (tenant_id, user_id, resource, metadata)
- Rule composition (combine multiple rules, short-circuit on error)
- Rule caching (cache validation results with TTL)
- Rule execution metrics (Prometheus via OpenTelemetry)
- Rule execution logging (structured logging)
- Rule execution tracing (OpenTelemetry)
- Rule registry with decorator-based registration
- Rule discovery and auto-registration
- Rule execution orchestration
- Rule dependency resolution
"""

from hub.apps.core.business_rules import utils
from hub.apps.core.business_rules.base import (
    BusinessRules,
    RuleExecutionContext,
    ValidationResult,
)
from hub.apps.core.business_rules.registry import (
    BusinessRulesRegistry,
    RuleMetadata,
    get_registry,
    register_rule,
)

__all__ = [
    "BusinessRules",
    "BusinessRulesRegistry",
    "RuleExecutionContext",
    "RuleMetadata",
    "utils",
    "ValidationResult",
    "get_registry",
    "register_rule",
]
