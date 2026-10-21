"""
Transaction Management Utilities

Enhanced transaction management utilities for bug prevention.
"""

from collections.abc import Callable
from contextlib import contextmanager
from functools import wraps
from typing import Any, TypeVar

from django.db import transaction
from django.db.transaction import atomic

T = TypeVar("T")


@contextmanager
def transaction_atomic(using: str | None = None, savepoint: bool = True):
    """
    Enhanced transaction context manager with better error handling.

    Usage:
        with transaction_atomic():
            # Database operations
            pass

    Args:
        using: Database alias (default: 'default')
        savepoint: Whether to use savepoints for nested transactions
    """
    with atomic(using=using, savepoint=savepoint):
        yield


def with_transaction(using: str | None = None, savepoint: bool = True):
    """
    Decorator to execute function within a transaction.

    Usage:
        @with_transaction()
        def my_function():
            # Database operations
            pass

    Args:
        using: Database alias (default: 'default')
        savepoint: Whether to use savepoints for nested transactions
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            with atomic(using=using, savepoint=savepoint):
                return func(*args, **kwargs)

        return wrapper

    return decorator


def retry_on_deadlock(max_retries: int = 3, using: str | None = None):
    """
    Decorator to retry function on database deadlock.

    Usage:
        @retry_on_deadlock(max_retries=3)
        def my_function():
            # Database operations that might deadlock
            pass

    Args:
        max_retries: Maximum number of retry attempts
        using: Database alias (default: 'default')
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            import random
            import time

            from django.db import OperationalError

            last_exception = None
            for attempt in range(max_retries):
                try:
                    with atomic(using=using):
                        return func(*args, **kwargs)
                except OperationalError as e:
                    # Check if it's a deadlock error
                    error_str = str(e).lower()
                    if "deadlock" in error_str or "lock wait timeout" in error_str:
                        last_exception = e
                        if attempt < max_retries - 1:
                            # Exponential backoff with jitter
                            wait_time = (2**attempt) + random.uniform(0, 1)
                            time.sleep(wait_time)
                            continue
                    # Not a deadlock, re-raise
                    raise

            # All retries exhausted
            raise last_exception

        return wrapper

    return decorator


class TransactionManager:
    """
    Transaction manager for complex multi-step operations.

    Provides utilities for managing transactions with savepoints,
    rollback handling, and compensation actions.
    """

    def __init__(self, using: str | None = None):
        """
        Initialize transaction manager.

        Args:
            using: Database alias (default: 'default')
        """
        self.using = using
        self.savepoints = []

    @contextmanager
    def savepoint(self):
        """
        Create a savepoint for partial rollback.

        Usage:
            with manager.savepoint():
                # Operations that can be rolled back independently
                pass
        """
        sid = transaction.savepoint(using=self.using)
        self.savepoints.append(sid)
        try:
            yield sid
        except Exception:
            transaction.savepoint_rollback(sid, using=self.using)
            raise
        finally:
            if sid in self.savepoints:
                self.savepoints.remove(sid)

    def rollback_to_savepoint(self, sid):
        """
        Rollback to a specific savepoint.

        Args:
            sid: Savepoint ID
        """
        transaction.savepoint_rollback(sid, using=self.using)

    def release_savepoint(self, sid):
        """
        Release a savepoint.

        Args:
            sid: Savepoint ID
        """
        transaction.savepoint_commit(sid, using=self.using)
        if sid in self.savepoints:
            self.savepoints.remove(sid)
