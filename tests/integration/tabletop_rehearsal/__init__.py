"""
Phase 232.DoD.7 tabletop **rehearsal** harness.

The quarterly tabletop exercise (per
``docs/runbooks/phase232-regulator-audit-tabletop.md``) is run with
humans in real seats: regulator, tenant admin, DPO, SRE on-call,
observer. The exercise is non-trivial to schedule and easy to
short-circuit if a contract has silently regressed since the last run.

This package automates the **rehearsal**: every scenario S1–S7 has a
matching pytest module that exercises the SAME contract the humans
will exercise during the live tabletop, but in-process against the
Django test client. Each test:

* runs a real (no-mock) end-to-end interaction with the relevant
  subsystem (Consent / DSAR / Breach / RoPA / DPIA / Retention);
* measures the wall-clock duration;
* writes a structured outcome record to the harness ledger so
  ``scripts/run_tabletop_rehearsal.py`` can produce a row that maps
  one-to-one onto the live ledger at
  ``docs/audit-reports/232-tabletop-ledger.md``.

A green rehearsal run is a **pre-flight** for the live exercise. It is
NOT a substitute — the live run still has to happen quarterly with the
humans on a clock — but a red rehearsal run blocks the live run from
even being scheduled, because the contract is provably broken.

Module conventions
------------------
* Each scenario lives in ``test_s<N>_<short_name>.py``.
* Each scenario imports ``ScenarioRecorder`` from ``_harness`` and uses
  it as a context manager: the recorder captures start / stop times,
  the subsystem(s) involved, the deliverable evidence (UUIDs, S3 keys,
  etc.), and pass/partial/fail outcome.
* The recorder writes one JSON file per scenario into
  ``$TABLETOP_REHEARSAL_OUT_DIR`` (default: ``/tmp/tabletop_rehearsal``).
  ``scripts/run_tabletop_rehearsal.py`` reads them all and composes the
  ledger row.
* Scenario tests are tagged ``@pytest.mark.tabletop_rehearsal`` so they
  can be selected (``pytest -m tabletop_rehearsal``) without dragging
  the rest of the integration suite in.
"""
