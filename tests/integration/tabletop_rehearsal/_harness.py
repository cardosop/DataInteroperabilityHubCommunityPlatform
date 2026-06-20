"""
Shared harness for Phase 232 tabletop rehearsal scenarios.

Each scenario test wraps its body in ``ScenarioRecorder`` so the
runner script can compose a deterministic ledger row per run.
"""

from __future__ import annotations

import json
import os
import time
import uuid
from contextlib import AbstractContextManager
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_DEFAULT_OUT_DIR = Path(os.environ.get("TABLETOP_REHEARSAL_OUT_DIR", "/tmp/tabletop_rehearsal"))

VALID_OUTCOMES = ("pass", "partial", "fail")


@dataclass
class ScenarioRecord:
    """Structured outcome of one scenario rehearsal."""

    scenario_id: str  # "S1", "S2", ...
    title: str
    subsystems: list[str]  # ["consent"], ["dsar", "retention"], ...
    budget_minutes: int  # the live-tabletop budget the rehearsal aspires to
    started_at_utc: str = ""
    finished_at_utc: str = ""
    duration_seconds: float = 0.0
    outcome: str = "fail"
    artefacts: dict[str, Any] = field(default_factory=dict)
    failure_note: str | None = None
    rehearsal_run_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])

    def as_json(self) -> str:
        return json.dumps(asdict(self), indent=2, sort_keys=False) + "\n"


class ScenarioRecorder(AbstractContextManager["ScenarioRecorder"]):
    """Context manager + accumulator for one scenario.

    Usage in a pytest test::

        @pytest.mark.tabletop_rehearsal
        def test_s6_consent_revocation_propagation(self):
            with ScenarioRecorder(
                scenario_id="S6",
                title="Consent revocation propagates",
                subsystems=["consent"],
                budget_minutes=30,
            ) as rec:
                # ... real subsystem interactions ...
                rec.add_artefact("webhook_delivery_id", str(delivery.id))
                rec.set_outcome("pass")

    On context exit (whether via clean return or exception), the
    recorder writes a ``${scenario_id}.json`` file into
    ``$TABLETOP_REHEARSAL_OUT_DIR``. Exceptions inside the ``with``
    block flip outcome to ``fail`` and store the exception in
    ``failure_note`` so the runner ledger surfaces it.
    """

    def __init__(
        self,
        scenario_id: str,
        title: str,
        subsystems: list[str],
        budget_minutes: int,
        out_dir: Path | None = None,
    ) -> None:
        self.record = ScenarioRecord(
            scenario_id=scenario_id,
            title=title,
            subsystems=list(subsystems),
            budget_minutes=int(budget_minutes),
        )
        self._out_dir = out_dir or _DEFAULT_OUT_DIR
        self._t0: float = 0.0
        self._exited = False

    def __enter__(self) -> ScenarioRecorder:
        self.record.started_at_utc = datetime.now(UTC).isoformat()
        self._t0 = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if self._exited:
            return None
        self._exited = True
        self.record.duration_seconds = round(time.perf_counter() - self._t0, 3)
        self.record.finished_at_utc = datetime.now(UTC).isoformat()
        if exc is not None and self.record.outcome != "fail":
            self.record.outcome = "fail"
            self.record.failure_note = f"{exc_type.__name__ if exc_type else 'Exception'}: {exc}"
        self._write()
        # Don't swallow the exception — pytest still needs to fail the test.
        return None

    def add_artefact(self, key: str, value: Any) -> None:
        self.record.artefacts[key] = value

    def set_outcome(self, outcome: str, note: str | None = None) -> None:
        if outcome not in VALID_OUTCOMES:
            raise ValueError(f"invalid outcome={outcome!r}; must be one of {VALID_OUTCOMES}")
        self.record.outcome = outcome
        if note is not None:
            self.record.failure_note = note

    def _write(self) -> None:
        self._out_dir.mkdir(parents=True, exist_ok=True)
        path = self._out_dir / f"{self.record.scenario_id}.json"
        path.write_text(self.record.as_json(), encoding="utf-8")
