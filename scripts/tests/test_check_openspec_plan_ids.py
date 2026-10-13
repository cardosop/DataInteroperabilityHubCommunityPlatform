"""TDD pin for ``check_openspec_plan_ids.py`` — the GATE-42 planned-ID allocation guard.

Rules pinned:
- planned IDs must match the canonical JOURNEY/UC regexes (same as GATE-27/28)
- no duplicate planned IDs
- no collision with ``docs/USER_JOURNEYS.md``, ``docs/USE_CASES.md``, or the
  CRITICAL YAML (a planned ID that already exists would violate the
  conflict rule the moment the phase registers it)
- every use case pairs with a planned journey
- critical candidates must NOT be pre-registered (GATE-26/27/28 BLOCK on a
  critical ID without an implementing test — the same-PR rule)
- every roadmap phase in tasks.md has >=1 planned journey AND use case,
  minus ``excluded_phases``
- artifact plan: doc paths follow convention + exist on disk; spec paths use
  a known role-code dir; aggregators exist; backend paths sit under the
  scanned test roots; spec paths are unique per journey
- the REAL repo plan passes its own gate (self-audit)
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from check_openspec_plan_ids import check, load_plan

GOOD_BODY = """
journeys:
  - {id: JOURNEY-DB-001, title: A, personas: [DE], phase: P0, uc: UC-DB-001, critical_candidate: false, doc: docs/mvpdocs/journeys/JOURNEY-DB-001.md, spec: frontend/e2e/journeys/de/JOURNEY-DB-001.spec.ts, aggregator: frontend/e2e/personas/data-engineer.spec.ts, backend: hub/apps/databricks_admin/tests/test_workspace_journeys.py}
use_cases:
  - {id: UC-DB-001, title: A, personas: [DE], phase: P0, journey: JOURNEY-DB-001, critical_candidate: false, doc: docs/mvpdocs/use-cases/UC-DB-001.md, backend: hub/apps/databricks_admin/tests/test_workspace_journeys.py}
"""


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def _plan(body: str, tmp_path: Path) -> Path:
    # Concatenation, NOT str.format — the YAML body contains `{id: ...}`
    # flow mappings that format() would try to interpolate.
    plan = tmp_path / "traceability-plan.md"
    _write(plan, "```yaml\nversion: 1\n" + body + "```\n")
    return plan


def _docs(
    tmp_path: Path,
    journeys: str = "",
    ucs: str = "",
    critical: str = "critical_journeys: []\ncritical_use_cases: []\n",
) -> tuple[Path, Path, Path]:
    journeys_doc = tmp_path / "USER_JOURNEYS.md"
    ucs_doc = tmp_path / "USE_CASES.md"
    critical_yaml = tmp_path / "CRITICAL.yaml"
    _write(journeys_doc, journeys)
    _write(ucs_doc, ucs)
    _write(critical_yaml, critical)
    return journeys_doc, ucs_doc, critical_yaml


def _tasks(tmp_path: Path, phases: str = "## Phase 0 — P0\n") -> Path:
    tasks = tmp_path / "tasks.md"
    _write(tasks, phases)
    return tasks


class TestPlanIds:
    def test_valid_plan_passes(self, tmp_path):
        journeys_doc, ucs_doc, critical_yaml = _docs(tmp_path)
        violations = check(
            load_plan(_plan(GOOD_BODY, tmp_path)),
            journeys_doc,
            ucs_doc,
            critical_yaml,
            _tasks(tmp_path),
        )
        assert violations == []

    def test_invalid_journey_id_shape(self, tmp_path):
        body = """journeys:
  - {id: JOURNEY-DB-XYZ, title: A, personas: [DE], phase: P0, uc: UC-DB-001, critical_candidate: false}
use_cases:
  - {id: UC-DB-001, title: A, personas: [DE], phase: P0, journey: JOURNEY-DB-XYZ, critical_candidate: false}
"""
        journeys_doc, ucs_doc, critical_yaml = _docs(tmp_path)
        violations = check(
            load_plan(_plan(body, tmp_path)), journeys_doc, ucs_doc, critical_yaml, _tasks(tmp_path)
        )
        assert any("invalid journey id" in v for v in violations)

    def test_collision_with_existing_journey(self, tmp_path):
        journeys_doc, ucs_doc, critical_yaml = _docs(
            tmp_path, journeys="| JOURNEY-DB-001 | Existing | DE | Phase 5 |\n"
        )
        violations = check(
            load_plan(_plan(GOOD_BODY, tmp_path)),
            journeys_doc,
            ucs_doc,
            critical_yaml,
            _tasks(tmp_path),
        )
        assert any("already exists in USER_JOURNEYS.md" in v for v in violations)

    def test_duplicate_planned_id(self, tmp_path):
        body = """journeys:
  - {id: JOURNEY-DB-001, title: A, personas: [DE], phase: P0, uc: UC-DB-001, critical_candidate: false}
  - {id: JOURNEY-DB-001, title: B, personas: [DE], phase: P0, uc: UC-DB-001, critical_candidate: false}
use_cases:
  - {id: UC-DB-001, title: A, personas: [DE], phase: P0, journey: JOURNEY-DB-001, critical_candidate: false}
"""
        journeys_doc, ucs_doc, critical_yaml = _docs(tmp_path)
        violations = check(
            load_plan(_plan(body, tmp_path)), journeys_doc, ucs_doc, critical_yaml, _tasks(tmp_path)
        )
        assert any("duplicate planned journey" in v for v in violations)

    def test_uc_references_unknown_journey(self, tmp_path):
        body = """journeys:
  - {id: JOURNEY-DB-001, title: A, personas: [DE], phase: P0, uc: UC-DB-001, critical_candidate: false}
use_cases:
  - {id: UC-DB-001, title: A, personas: [DE], phase: P0, journey: JOURNEY-DB-999, critical_candidate: false}
"""
        journeys_doc, ucs_doc, critical_yaml = _docs(tmp_path)
        violations = check(
            load_plan(_plan(body, tmp_path)), journeys_doc, ucs_doc, critical_yaml, _tasks(tmp_path)
        )
        assert any("unknown journey" in v for v in violations)

    def test_shipped_phase_ids_may_exist_in_registries(self, tmp_path):
        """Once a phase ships (its implementing PR registered the IDs), the
        plan's entries for that phase may legitimately exist in the
        canonical registries and the critical YAML — the collision rules
        only guard PENDING phases."""
        journeys_doc, ucs_doc, critical_yaml = _docs(
            tmp_path,
            journeys="| JOURNEY-DB-001 | Registered | DE | P0 |\n",
            ucs="| UC-DB-001 | Registered | DE | x |\n",
            critical="critical_journeys: [JOURNEY-DB-001]\ncritical_use_cases: [UC-DB-001]\n",
        )
        shipped_body = (
            "shipped_phases: [P0]\n"
            "journeys:\n"
            "  - {id: JOURNEY-DB-001, title: A, personas: [DE], phase: P0, uc: UC-DB-001, critical_candidate: true, doc: docs/mvpdocs/journeys/JOURNEY-DB-001.md, spec: frontend/e2e/journeys/de/JOURNEY-DB-001.spec.ts, aggregator: frontend/e2e/personas/data-engineer.spec.ts, backend: hub/apps/databricks_admin/tests/test_workspace_journeys.py}\n"
            "use_cases:\n"
            "  - {id: UC-DB-001, title: A, personas: [DE], phase: P0, journey: JOURNEY-DB-001, critical_candidate: true, doc: docs/mvpdocs/use-cases/UC-DB-001.md, backend: hub/apps/databricks_admin/tests/test_workspace_journeys.py}\n"
        )
        violations = check(
            load_plan(_plan(shipped_body, tmp_path)),
            journeys_doc,
            ucs_doc,
            critical_yaml,
            _tasks(tmp_path),
        )
        assert violations == []

    def test_shipped_phase_exempts_phase_coverage(self, tmp_path):
        """A shipped phase needs no remaining planned IDs — its coverage is
        the shipped test suite, tracked by GATE-26/27/28."""
        shipped_body = (
            "shipped_phases: [P0]\n"
            "journeys:\n"
            "  - {id: JOURNEY-DB-002, title: B, personas: [DE], phase: P1, uc: UC-DB-002, critical_candidate: false, doc: docs/mvpdocs/journeys/JOURNEY-DB-002.md, spec: frontend/e2e/journeys/de/JOURNEY-DB-002.spec.ts, aggregator: frontend/e2e/personas/data-engineer.spec.ts, backend: hub/apps/databricks_admin/tests/test_workspace_journeys.py}\n"
            "use_cases:\n"
            "  - {id: UC-DB-002, title: B, personas: [DE], phase: P1, journey: JOURNEY-DB-002, critical_candidate: false, doc: docs/mvpdocs/use-cases/UC-DB-002.md, backend: hub/apps/databricks_admin/tests/test_workspace_journeys.py}\n"
        )
        journeys_doc, ucs_doc, critical_yaml = _docs(tmp_path)
        violations = check(
            load_plan(_plan(shipped_body, tmp_path)),
            journeys_doc,
            ucs_doc,
            critical_yaml,
            _tasks(tmp_path, phases="## Phase 0 — P0\n## Phase 1 — P1\n"),
        )
        assert violations == []

    def test_pending_phase_collision_still_fails(self, tmp_path):
        """Without shipped_phases, the pre-existing collision guard is intact."""
        journeys_doc, ucs_doc, critical_yaml = _docs(
            tmp_path, journeys="| JOURNEY-DB-001 | Existing | DE | Phase 5 |\n"
        )
        violations = check(
            load_plan(_plan(GOOD_BODY, tmp_path)),
            journeys_doc,
            ucs_doc,
            critical_yaml,
            _tasks(tmp_path),
        )
        assert any("already exists in USER_JOURNEYS.md" in v for v in violations)

    def test_critical_candidate_must_not_be_preregistered(self, tmp_path):
        body = """journeys:
  - {id: JOURNEY-DB-001, title: A, personas: [DE], phase: P0, uc: UC-DB-001, critical_candidate: true}
use_cases:
  - {id: UC-DB-001, title: A, personas: [DE], phase: P0, journey: JOURNEY-DB-001, critical_candidate: true}
"""
        journeys_doc, ucs_doc, critical_yaml = _docs(
            tmp_path, critical="critical_journeys: [JOURNEY-DB-001]\ncritical_use_cases: []\n"
        )
        violations = check(
            load_plan(_plan(body, tmp_path)), journeys_doc, ucs_doc, critical_yaml, _tasks(tmp_path)
        )
        assert any("critical candidate" in v for v in violations)

    def test_phase_without_coverage_fails(self, tmp_path):
        journeys_doc, ucs_doc, critical_yaml = _docs(tmp_path)
        violations = check(
            load_plan(_plan(GOOD_BODY, tmp_path)),
            journeys_doc,
            ucs_doc,
            critical_yaml,
            _tasks(tmp_path, phases="## Phase 0 — P0\n## Phase 1 — P1\n"),
        )
        assert any("no planned journey+use case" in v for v in violations)

    def test_excluded_phase_is_skipped(self, tmp_path):
        body = GOOD_BODY + "excluded_phases: [P1]\n"
        journeys_doc, ucs_doc, critical_yaml = _docs(tmp_path)
        violations = check(
            load_plan(_plan(body, tmp_path)),
            journeys_doc,
            ucs_doc,
            critical_yaml,
            _tasks(tmp_path, phases="## Phase 0 — P0\n## Phase 1 — P1\n"),
        )
        assert violations == []

    # ── Artifact-plan rules (added with the 38-doc writing step) ──────────

    def test_doc_path_convention_violation(self, tmp_path):
        body = GOOD_BODY.replace(
            "doc: docs/mvpdocs/journeys/JOURNEY-DB-001.md",
            "doc: docs/mvpdocs/journeys/WRONG.md",
        )
        journeys_doc, ucs_doc, critical_yaml = _docs(tmp_path)
        violations = check(
            load_plan(_plan(body, tmp_path)), journeys_doc, ucs_doc, critical_yaml, _tasks(tmp_path)
        )
        assert any("doc path" in v and "convention" in v for v in violations)

    def test_doc_file_missing_on_disk(self, tmp_path):
        repo_root = tmp_path / "repo"
        journeys_doc, ucs_doc, critical_yaml = _docs(repo_root)
        violations = check(
            load_plan(_plan(GOOD_BODY, tmp_path)),
            journeys_doc,
            ucs_doc,
            critical_yaml,
            _tasks(tmp_path),
            repo_root=repo_root,
        )
        assert any("doc file missing on disk" in v for v in violations)

    def test_doc_files_present_pass(self, tmp_path):
        repo_root = tmp_path / "repo"
        journeys_doc, ucs_doc, critical_yaml = _docs(repo_root)
        _write(repo_root / "docs/mvpdocs/journeys/JOURNEY-DB-001.md", "# doc\n")
        _write(repo_root / "docs/mvpdocs/use-cases/UC-DB-001.md", "# doc\n")
        violations = check(
            load_plan(_plan(GOOD_BODY, tmp_path)),
            journeys_doc,
            ucs_doc,
            critical_yaml,
            _tasks(tmp_path),
            repo_root=repo_root,
        )
        assert violations == []

    def test_spec_role_dir_invalid(self, tmp_path):
        body = GOOD_BODY.replace(
            "spec: frontend/e2e/journeys/de/JOURNEY-DB-001.spec.ts",
            "spec: frontend/e2e/journeys/unknown-role/JOURNEY-DB-001.spec.ts",
        )
        journeys_doc, ucs_doc, critical_yaml = _docs(tmp_path)
        violations = check(
            load_plan(_plan(body, tmp_path)), journeys_doc, ucs_doc, critical_yaml, _tasks(tmp_path)
        )
        assert any("spec role dir" in v for v in violations)

    def test_aggregator_missing_fails(self, tmp_path):
        personas_dir = tmp_path / "personas"
        personas_dir.mkdir()
        journeys_doc, ucs_doc, critical_yaml = _docs(tmp_path)
        violations = check(
            load_plan(_plan(GOOD_BODY, tmp_path)),
            journeys_doc,
            ucs_doc,
            critical_yaml,
            _tasks(tmp_path),
            personas_dir=personas_dir,
        )
        assert any("aggregator missing" in v for v in violations)

    def test_aggregator_present_passes(self, tmp_path):
        personas_dir = tmp_path / "personas"
        _write(personas_dir / "data-engineer.spec.ts", "// aggregator\n")
        journeys_doc, ucs_doc, critical_yaml = _docs(tmp_path)
        violations = check(
            load_plan(_plan(GOOD_BODY, tmp_path)),
            journeys_doc,
            ucs_doc,
            critical_yaml,
            _tasks(tmp_path),
            personas_dir=personas_dir,
        )
        assert violations == []

    def test_duplicate_spec_path_fails(self, tmp_path):
        body = """journeys:
  - {id: JOURNEY-DB-001, title: A, personas: [DE], phase: P0, uc: UC-DB-001, critical_candidate: false, doc: docs/mvpdocs/journeys/JOURNEY-DB-001.md, spec: frontend/e2e/journeys/de/JOURNEY-DB-001.spec.ts, aggregator: frontend/e2e/personas/data-engineer.spec.ts, backend: hub/apps/databricks_admin/tests/test_workspace_journeys.py}
  - {id: JOURNEY-DB-002, title: B, personas: [DE], phase: P0, uc: UC-DB-002, critical_candidate: false, doc: docs/mvpdocs/journeys/JOURNEY-DB-002.md, spec: frontend/e2e/journeys/de/JOURNEY-DB-001.spec.ts, aggregator: frontend/e2e/personas/data-engineer.spec.ts, backend: hub/apps/databricks_admin/tests/test_workspace_journeys.py}
use_cases:
  - {id: UC-DB-001, title: A, personas: [DE], phase: P0, journey: JOURNEY-DB-001, critical_candidate: false, doc: docs/mvpdocs/use-cases/UC-DB-001.md, backend: hub/apps/databricks_admin/tests/test_workspace_journeys.py}
  - {id: UC-DB-002, title: B, personas: [DE], phase: P0, journey: JOURNEY-DB-002, critical_candidate: false, doc: docs/mvpdocs/use-cases/UC-DB-002.md, backend: hub/apps/databricks_admin/tests/test_workspace_journeys.py}
"""
        journeys_doc, ucs_doc, critical_yaml = _docs(tmp_path)
        violations = check(
            load_plan(_plan(body, tmp_path)), journeys_doc, ucs_doc, critical_yaml, _tasks(tmp_path)
        )
        assert any("duplicate frontend spec path" in v for v in violations)

    def test_backend_outside_scanned_roots_fails(self, tmp_path):
        body = GOOD_BODY.replace(
            "backend: hub/apps/databricks_admin/tests/test_workspace_journeys.py",
            "backend: some/other/dir/test_x.py",
        )
        journeys_doc, ucs_doc, critical_yaml = _docs(tmp_path)
        violations = check(
            load_plan(_plan(body, tmp_path)), journeys_doc, ucs_doc, critical_yaml, _tasks(tmp_path)
        )
        assert any("outside scanned test roots" in v for v in violations)

    def test_real_repo_plan_is_clean(self):
        """Self-audit: the committed allocation must always pass its own gate."""
        plan = REPO_ROOT / "openspec/changes/add-databricks-control-plane/traceability-plan.md"
        tasks = REPO_ROOT / "openspec/changes/add-databricks-control-plane/tasks.md"
        journeys_doc = REPO_ROOT / "docs/USER_JOURNEYS.md"
        ucs_doc = REPO_ROOT / "docs/USE_CASES.md"
        critical_yaml = REPO_ROOT / "docs/CRITICAL_UC_JOURNEY_IDS.yaml"
        personas_dir = REPO_ROOT / "frontend/e2e/personas"
        violations = check(
            load_plan(plan),
            journeys_doc,
            ucs_doc,
            critical_yaml,
            tasks,
            personas_dir=personas_dir,
            repo_root=REPO_ROOT,
        )
        assert violations == []
