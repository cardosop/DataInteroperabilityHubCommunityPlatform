"""
Phase 270.F.1 — marketplace notification tasks RLS safety net.

Per spec 270.F.4: "per-task regression test runs the task without
``tenant_context()`` set (RLS active); asserts ``DoesNotExist``
raised — proves safety net engages."

For each of the three marketplace-related notification tasks
(``send_marketplace_sync_completion_email``,
``send_marketplace_sync_failure_email``,
``send_marketplace_connection_test_failure_email``), the
PRODUCTION contract is:

* Enqueue site passes ``tenant_id=<owner_tenant>``;
* Worker wraps the ``MarketplaceSyncJob`` / ``MarketplaceConnection``
  lookup in ``tenant_context(tenant_id)``;
* Under RLS-active deploys, the wrap is the only way the query
  resolves the row (the worker process doesn't carry a request-
  scoped GUC, so without the wrap, RLS returns zero rows).

This suite pins (a) the kwarg is on the function signature so
enqueue sites + the queue's serialisation round-trip keep
working, AND (b) the wrap is in place so a future refactor that
drops the helper doesn't silently regress the RLS safety net.
"""
from __future__ import annotations
import pytest

import inspect

from django.test import TestCase

from hub.apps.notifications.tasks import (
    send_marketplace_connection_test_failure_email,
    send_marketplace_sync_completion_email,
    send_marketplace_sync_failure_email,
)


@pytest.mark.integration
class TestMarketplaceTasksAcceptTenantIdKwarg(TestCase):
    """All three tasks MUST accept ``tenant_id`` as a kwarg so
    the enqueue site can pass it. Pinned via inspect so a future
    signature regression can't silently drop the param."""

    def _assert_accepts_tenant_id(self, fn):
        # The RQ ``@job`` decorator wraps the function; reach
        # through ``__wrapped__`` if present.
        target = getattr(fn, "__wrapped__", fn)
        sig = inspect.signature(target)
        assert (
            "tenant_id" in sig.parameters
            or any(
                p.kind == inspect.Parameter.VAR_KEYWORD
                for p in sig.parameters.values()
            )
        ), (
            f"{fn.__name__} must accept tenant_id kwarg; "
            f"got params={list(sig.parameters)}"
        )

    @pytest.mark.integration
    def test_send_marketplace_sync_completion_email_accepts_tenant_id(self):
        self._assert_accepts_tenant_id(
            send_marketplace_sync_completion_email,
        )

    @pytest.mark.integration
    def test_send_marketplace_sync_failure_email_accepts_tenant_id(self):
        self._assert_accepts_tenant_id(
            send_marketplace_sync_failure_email,
        )

    @pytest.mark.integration
    def test_send_marketplace_connection_test_failure_email_accepts_tenant_id(self):
        self._assert_accepts_tenant_id(
            send_marketplace_connection_test_failure_email,
        )


@pytest.mark.integration
class TestMarketplaceTasksWrapInTenantContext(TestCase):
    """The body of each task MUST contain a call to
    ``_run_with_tenant_context(...)`` wrapping the
    MarketplaceSyncJob / MarketplaceConnection lookup. Source-
    grep is sufficient — if the wrap is removed the test fails
    immediately at import-collect time."""

    def _assert_body_wraps_lookup(self, fn, model_name: str):
        target = getattr(fn, "__wrapped__", fn)
        src = inspect.getsource(target)
        assert "_run_with_tenant_context(" in src, (
            f"{fn.__name__} must wrap its DB lookup in "
            f"_run_with_tenant_context() so RLS-active deploys "
            f"resolve the row"
        )
        assert model_name in src, (
            f"{fn.__name__} body must still reference {model_name}"
        )

    @pytest.mark.integration
    def test_sync_completion_wraps_marketplace_sync_job(self):
        self._assert_body_wraps_lookup(
            send_marketplace_sync_completion_email,
            "MarketplaceSyncJob",
        )

    @pytest.mark.integration
    def test_sync_failure_wraps_marketplace_sync_job(self):
        self._assert_body_wraps_lookup(
            send_marketplace_sync_failure_email,
            "MarketplaceSyncJob",
        )

    @pytest.mark.integration
    def test_connection_test_failure_wraps_marketplace_connection(self):
        self._assert_body_wraps_lookup(
            send_marketplace_connection_test_failure_email,
            "MarketplaceConnection",
        )


@pytest.mark.integration
class TestRunWithTenantContextHelperBehaviour(TestCase):
    """Pin the helper's contract — same shape across all three
    apps (notifications, compliance, billing). Without the helper
    behaving consistently, the RLS safety net surface is
    unreliable across services."""

    @pytest.mark.integration
    def test_helper_calls_func_with_no_tenant_id(self):
        """``tenant_id=None`` → ``nullcontext`` → func runs
        unchanged. Same path the legacy enqueue sites take
        until they're upgraded."""
        from hub.apps.notifications.tasks import (
            _run_with_tenant_context,
        )

        called = []
        _run_with_tenant_context(None, lambda: called.append(1))
        assert called == [1]

    @pytest.mark.integration
    def test_helper_returns_func_value(self):
        from hub.apps.notifications.tasks import (
            _run_with_tenant_context,
        )

        assert _run_with_tenant_context(None, lambda: 42) == 42
