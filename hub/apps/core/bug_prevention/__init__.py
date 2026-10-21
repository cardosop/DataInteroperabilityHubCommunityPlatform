"""
Bug Prevention Module

Provides input/output validation, transaction management,
idempotency keys, and request deduplication.
"""

from hub.apps.core.bug_prevention.models import (
    IdempotencyKey,
    RequestDeduplication,
)
from hub.apps.core.bug_prevention.services import (
    IdempotencyConflictError,
    IdempotencyService,
    RequestDeduplicationService,
)
from hub.apps.core.bug_prevention.transaction_utils import (
    TransactionManager,
    retry_on_deadlock,
    transaction_atomic,
    with_transaction,
)
from hub.apps.core.bug_prevention.validators import (
    InputValidator,
    OutputValidator,
    ValidationResult,
)

__all__ = [
    "IdempotencyConflictError",
    "IdempotencyKey",
    "IdempotencyService",
    "InputValidator",
    "OutputValidator",
    "RequestDeduplication",
    "RequestDeduplicationService",
    "TransactionManager",
    "ValidationResult",
    "retry_on_deadlock",
    "transaction_atomic",
    "with_transaction",
]
