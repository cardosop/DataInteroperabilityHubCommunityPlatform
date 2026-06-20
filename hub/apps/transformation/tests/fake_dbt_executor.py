"""
285.9.1.5.4 — FakeDbtExecutor for deterministic testing.

Drop-in replacement for ``DbtExecutor`` that returns pre-configured
results without requiring dbt Core, a warehouse connection, or AWS
credentials.  Every test can configure its own result shape so
assertions are explicit rather than coupled to shared fixture state.
"""

from __future__ import annotations

import copy
from typing import Any


class FakeDbtExecutor:
    """Deterministic, no-dependency replacement for ``DbtExecutor``.

    Intended for integration tests that exercise the full service →
    executor pipeline without touching subprocess, AWS SM, or a real
    warehouse.  Configuration is per-instance via constructor kwargs;
    callers can also mutate ``results`` / ``error_logs`` / ``span_attrs``
    after construction for fine-grained scenario control.

    Example::

        fake = FakeDbtExecutor(
            results=[
                {"unique_id": "model.sample.customers", "status": "success",
                 "execution_time_seconds": 2.0, "rows_affected": 100},
            ],
            elapsed_total=2.5,
        )
        result = fake.dbt_run("/tmp/proj")
        assert result["results"][0]["status"] == "success"
    """

    # Pre-configured run_results.json fragments for each action so
    # callers can see realistic-looking output without setup.
    _DEFAULT_RESULTS: dict[str, list[dict[str, Any]]] = {
        "run": [
            {
                "unique_id": "model.sample.customers",
                "status": "success",
                "execution_time_seconds": 1.5,
                "rows_affected": 150,
                "message": "SUCCESS 150",
                "thread_id": "Thread-1",
            },
            {
                "unique_id": "model.sample.orders",
                "status": "success",
                "execution_time_seconds": 2.3,
                "rows_affected": 320,
                "message": "SUCCESS 320",
                "thread_id": "Thread-2",
            },
        ],
        "test": [
            {
                "unique_id": "test.sample.unique_customers_customer_id",
                "status": "success",
                "execution_time_seconds": 0.3,
                "rows_affected": 0,
                "message": "SUCCESS 0",
            },
        ],
    }

    def __init__(
        self,
        results: list[dict[str, Any]] | None = None,
        elapsed_total: float = 5.0,
        error_logs: list[str] | None = None,
        span_attributes: dict[str, Any] | None = None,
        fail_on: str | None = None,
        timeout_on: str | None = None,
    ):
        """
        Args:
            results: Per-model result dicts.  ``None`` → use
                ``_DEFAULT_RESULTS["run"]``.
            elapsed_total: Total dbt elapsed time (seconds).
            error_logs: Pre-configured error log lines.  ``None`` → empty.
            span_attributes: Pre-configured span attributes.  ``None`` →
                auto-generated from ``results``.
            fail_on: Action name (e.g. ``"run"``) that should simulate a
                dbt failure.  The executor returns ``status=FAILED`` with
                ``error_logs`` populated.
            timeout_on: Action name that should simulate a dbt timeout.
                Returns ``status=TIMEOUT`` with ``completed_models``.
        """
        self.results = results or copy.deepcopy(self._DEFAULT_RESULTS.get("run", []))
        self.elapsed_total = elapsed_total
        self.error_logs = error_logs or []
        self.span_attributes = span_attributes or {}
        self.fail_on = fail_on
        self.timeout_on = timeout_on

        # Tracks which actions were called + models/target (for assertions)
        self.called_actions: list[str] = []
        self.called_models: list[str] | None = None
        self.called_target: str | None = None

    # ── Public API (matches DbtExecutor) ─────────────────────────────

    def dbt_run(
        self,
        project_path: str,
        models: list[str] | None = None,
        target: str = "prod",
    ) -> dict[str, Any]:
        self.called_models = models
        self.called_target = target
        return self._respond("run", project_path)

    def dbt_test(self, project_path: str, target: str = "prod") -> dict[str, Any]:
        return self._respond("test", project_path)

    def dbt_docs_generate(self, project_path: str, target: str = "prod") -> dict[str, Any]:
        return self._respond("docs-generate", project_path)

    def dbt_parse(self, project_path: str, target: str = "prod") -> dict[str, Any]:
        return self._respond("parse", project_path)

    def dbt_deps(self, project_path: str, target: str = "prod") -> dict[str, Any]:
        return self._respond("deps", project_path)

    # ── Internal ────────────────────────────────────────────────────

    def _respond(self, action: str, project_path: str) -> dict[str, Any]:
        self.called_actions.append(action)

        if self.timeout_on and action == self.timeout_on:
            return {
                "action": action,
                "status": "TIMEOUT",
                "duration_seconds": 3600.0,
                "completed_models": [],
                "incomplete_models": ["model.unknown"],
                "elapsed_total": None,
                "results": [],
                "error_logs": [f"dbt {action} timed out after 3600s"],
                "span_attributes": {},
            }

        if self.fail_on and action == self.fail_on:
            return {
                "action": action,
                "status": "FAILED",
                "duration_seconds": 1.2,
                "results": [],
                "elapsed_total": None,
                "error_logs": self.error_logs or [f"Database Error in dbt {action}"],
                "span_attributes": {},
            }

        # Use action-specific defaults when available
        results = self.results
        if action in self._DEFAULT_RESULTS and self.results is None:
            results = copy.deepcopy(self._DEFAULT_RESULTS[action])

        return {
            "action": action,
            "status": "COMPLETED",
            "duration_seconds": self.elapsed_total,
            "results": results,
            "elapsed_total": self.elapsed_total,
            "error_logs": list(self.error_logs),
            "span_attributes": dict(self.span_attributes),
        }
