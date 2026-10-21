"""
Real in-memory DQ client for scheduled_ingestion tests.

No mocks: real class with configurable behavior so tests can exercise
processor DQ logic without the external DQ service.
"""

from typing import Any


class InMemoryDQClient:
    """
    In-memory DQ client for tests. Implements health_check and run_dq
    with configurable responses (no mocks).
    """

    def __init__(
        self,
        health_ok: bool = True,
        run_dq_result: dict[str, Any] | None = None,
        run_dq_raises: Exception | None = None,
    ):
        self.health_ok = health_ok
        self.run_dq_result = run_dq_result or {
            "overall_status": "PASS",
            "quality_score": 0.95,
            "checks": [],
            "execution_time_seconds": 2.5,
        }
        self.run_dq_raises = run_dq_raises

    def health_check(self, timeout: float = 5.0) -> tuple[bool, str]:
        """Return configured health (no mocks)."""
        return (self.health_ok, "ok" if self.health_ok else "unavailable")

    def run_dq(
        self,
        file_content: bytes,
        file_format: str,
        profile_key: str = "intake_basic_gx",
        use_cache: bool = True,
        contract: Any | None = None,
    ) -> dict[str, Any]:
        """Return configured result or raise (no mocks)."""
        if self.run_dq_raises:
            raise self.run_dq_raises
        return dict(self.run_dq_result)
