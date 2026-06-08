"""
Phase 232.8.15 — programme API surface (no HTTP in this module).

.. note::
   These are **structural regression guards** — they verify that every
   expected list method exists and is an async coroutine function. They
   catch accidental deletion/renaming but do NOT validate runtime
   behavior. Behavioral tests for the programme API live in the
   integration test suite.
"""

from __future__ import annotations

import inspect

import pytest

from datahub_interoperability.phase232 import Phase232ProgrammeAPI


@pytest.mark.parametrize(
    "name",
    [
        "list_compliance_runs",
        "list_dpia_records",
        "list_ropa_generations",
        "list_breach_incidents",
        "list_dsar_requests",
        "list_consent_purposes",
        "list_processor_agreements",
    ],
)
@pytest.mark.integration
def test_phase232_programme_api_defines_list_methods(name: str) -> None:
    assert hasattr(Phase232ProgrammeAPI, name)
    fn = getattr(Phase232ProgrammeAPI, name)
    assert inspect.iscoroutinefunction(fn)
