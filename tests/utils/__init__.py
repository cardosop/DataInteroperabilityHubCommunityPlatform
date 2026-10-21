"""
Test Data Management Utilities

Utilities for test data cleanup, seeding, isolation, and polling.
"""

from .polling import wait_until

try:
    from .test_data_management import (
        TestDataManager,
        cleanup_test_data,
        create_multi_tenant_test_data,
        reset_test_database,
        seed_test_data,
        validate_migrations,
    )
except (RuntimeError, ModuleNotFoundError):
    # Core-only mode (HUB_CORE_ONLY=1): test_data_management imports paid
    # apps (marketplace models) that are not installed, so Django raises
    # RuntimeError at model-class definition. The data-management helpers
    # are paid-context test utilities (excluded from the core suite); the
    # polling helper above remains available in every mode.
    TestDataManager = None  # type: ignore[assignment]
    cleanup_test_data = None  # type: ignore[assignment]
    create_multi_tenant_test_data = None  # type: ignore[assignment]
    reset_test_database = None  # type: ignore[assignment]
    seed_test_data = None  # type: ignore[assignment]
    validate_migrations = None  # type: ignore[assignment]

__all__ = [
    "TestDataManager",
    "cleanup_test_data",
    "create_multi_tenant_test_data",
    "reset_test_database",
    "seed_test_data",
    "validate_migrations",
    "wait_until",
]
