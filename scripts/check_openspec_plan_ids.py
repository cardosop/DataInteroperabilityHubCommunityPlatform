"""check_openspec_plan_ids.py — planned journey/UC allocation + artifact guard (GATE-42).

The umbrella change `openspec/changes/add-databricks-control-plane/traceability-plan.md`
pre-allocates JOURNEY-DB-XXX / UC-DB-XXX IDs for the P0-P12 roadmap and maps each to
its documentation and test artifacts (journey doc, UC page, backend test module,
frontend spec, persona aggregator). This check pins the allocation against the
canonical registries so a planned ID can never:

- deviate from the canonical ID shape (same regexes the doc-sync gates use)
- duplicate another planned ID
- collide with an existing ID in `docs/USER_JOURNEYS.md` / `docs/USE_CASES.md`
- pair a use case with a journey that is not planned
- pre-register a critical candidate before its implementing markers exist
  (GATE-26/27/28 + the traceability gate BLOCK on critical IDs without tests)
- leave a roadmap phase in tasks.md without at least one journey AND one use case
  (minus `excluded_phases`)

and pins the artifact plan:

- `doc` paths follow the canonical convention and the files exist on disk
- `spec` paths live under a known role-code journey dir with the ID-named file
- `aggregator` files exist under the personas dir
- `backend` paths live under the scanned test roots (`hub/apps/.../tests/` or `tests/e2e/`)
- no two journeys share a frontend spec path (backend MODULES may be shared —
  that is the repo's module-level marker pattern)

Exit 0 when every check passes; exit 1 with a violation list otherwise.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

JOURNEY_RE = re.compile(r"JOURNEY-[A-Z]+-\d+")
UC_RE = re.compile(r"UC-[A-Z]+(?:-[A-Z]+)*-\d+[A-Z]?")
_TASKS_PHASE_RE = re.compile(r"^## Phase (\d+\w?)\b", re.MULTILINE)

# Existing role-code journey dirs the DB plan uses; extend when a new dir is
# introduced for a future journey family.
SPEC_ROLE_DIRS = {"de", "mpa", "dc", "ds", "auth"}
BACKEND_ROOTS = ("hub/apps/", "tests/e2e/")


def _yaml_block(text: str) -> dict:
    import yaml

    fence = re.search(r"```yaml\n(.*?)\n```", text, re.DOTALL)
    if not fence:
        raise ValueError("no ```yaml block found in plan file")
    data = yaml.safe_load(fence.group(1))
    return data if isinstance(data, dict) else {}


def load_plan(plan_path: Path) -> dict:
    """Parse the YAML allocation block out of the traceability plan markdown."""
    return _yaml_block(plan_path.read_text())


def extract_existing_ids(path: Path, pattern: re.Pattern) -> set[str]:
    """IDs present in a canonical registry doc (same regexes the doc-sync gates use)."""
    return set(pattern.findall(path.read_text()))


def _check_artifact_fields(
    plan: dict,
    violations: list[str],
    personas_dir: Path | None,
    repo_root: Path | None,
) -> None:
    journeys = plan.get("journeys", [])
    use_cases = plan.get("use_cases", [])

    for j in journeys:
        jid = j["id"]
        expected_doc = f"docs/mvpdocs/journeys/{jid}.md"
        if j.get("doc") != expected_doc:
            violations.append(
                f"journey {jid} doc path {j.get('doc')!r} != convention {expected_doc!r}"
            )
        elif repo_root is not None and not (repo_root / expected_doc).exists():
            violations.append(f"journey {jid} doc file missing on disk: {expected_doc}")

        spec = j.get("spec", "")
        match = re.fullmatch(rf"frontend/e2e/journeys/([^/]+)/{jid}\.spec\.ts", spec)
        if not match:
            violations.append(
                f"journey {jid} spec path {spec!r} violates convention frontend/e2e/journeys/<role>/{jid}.spec.ts"
            )
        elif match.group(1) not in SPEC_ROLE_DIRS:
            violations.append(
                f"journey {jid} spec role dir {match.group(1)!r} not in {sorted(SPEC_ROLE_DIRS)}"
            )

        aggregator = j.get("aggregator", "")
        if (
            personas_dir is not None
            and aggregator
            and not (personas_dir / Path(aggregator).name).exists()
        ):
            violations.append(f"journey {jid} aggregator missing: {aggregator}")

        backend = j.get("backend", "")
        if not backend.startswith(BACKEND_ROOTS) or "/tests/" not in backend:
            violations.append(
                f"journey {jid} backend path {backend!r} outside scanned test roots {BACKEND_ROOTS}"
            )

    for u in use_cases:
        uid = u["id"]
        expected_doc = f"docs/mvpdocs/use-cases/{uid}.md"
        if u.get("doc") != expected_doc:
            violations.append(
                f"use case {uid} doc path {u.get('doc')!r} != convention {expected_doc!r}"
            )
        elif repo_root is not None and not (repo_root / expected_doc).exists():
            violations.append(f"use case {uid} doc file missing on disk: {expected_doc}")

        backend = u.get("backend", "")
        if not backend.startswith(BACKEND_ROOTS) or "/tests/" not in backend:
            violations.append(
                f"use case {uid} backend path {backend!r} outside scanned test roots {BACKEND_ROOTS}"
            )

    # Spec paths must be unique per journey; backend MODULES may be shared
    # (module-level markers are the repo pattern).
    specs = [j.get("spec") for j in journeys if j.get("spec")]
    violations.extend(
        f"duplicate frontend spec path {s}"
        for s in sorted({x for x in specs if specs.count(x) > 1})
    )


def check(
    plan: dict,
    journeys_doc: Path,
    use_cases_doc: Path,
    critical_yaml: Path,
    tasks: Path | None = None,
    personas_dir: Path | None = None,
    repo_root: Path | None = None,
) -> list[str]:
    """Return the violation list (empty == clean)."""
    import yaml

    violations: list[str] = []
    journeys = plan.get("journeys", [])
    use_cases = plan.get("use_cases", [])
    excluded_phases = set(plan.get("excluded_phases", []))
    # Phases whose implementing PR has ALREADY registered their IDs: their
    # entries may legitimately exist in the canonical registries + critical
    # YAML (the collision guards only protect PENDING reservations), and
    # they are exempt from the per-phase coverage rule (their coverage is
    # the shipped suite, tracked by GATE-26/27/28).
    shipped_phases = set(plan.get("shipped_phases", []))

    existing_journeys = extract_existing_ids(journeys_doc, JOURNEY_RE)
    existing_ucs = extract_existing_ids(use_cases_doc, UC_RE)
    critical_data = yaml.safe_load(critical_yaml.read_text()) or {}
    critical_ids = set(critical_data.get("critical_journeys", [])) | set(
        critical_data.get("critical_use_cases", [])
    )

    pending_journeys = [j for j in journeys if j.get("phase") not in shipped_phases]
    pending_use_cases = [u for u in use_cases if u.get("phase") not in shipped_phases]

    jids = [j["id"] for j in journeys]
    uids = [u["id"] for u in use_cases]
    pending_jids = [j["id"] for j in pending_journeys]
    pending_uids = [u["id"] for u in pending_use_cases]

    # 1. ID shape
    violations.extend(
        f"invalid journey id {jid!r} (expected JOURNEY-<PREFIX>-<NNN>)"
        for jid in jids
        if not JOURNEY_RE.fullmatch(jid)
    )
    violations.extend(
        f"invalid use case id {uid!r} (expected UC-<DOMAIN>-<NNN>)"
        for uid in uids
        if not UC_RE.fullmatch(uid)
    )

    # 2. Duplicates within the plan
    violations.extend(
        f"duplicate planned journey {jid}" for jid in sorted({x for x in jids if jids.count(x) > 1})
    )
    violations.extend(
        f"duplicate planned use case {uid}"
        for uid in sorted({x for x in uids if uids.count(x) > 1})
    )

    # 3. Collisions with canonical registries / critical YAML — PENDING
    # reservations only; shipped-phase IDs are expected to be registered.
    violations.extend(
        f"journey {jid} already exists in {journeys_doc.name}"
        for jid in pending_jids
        if jid in existing_journeys
    )
    violations.extend(
        f"use case {uid} already exists in {use_cases_doc.name}"
        for uid in pending_uids
        if uid in existing_ucs
    )
    violations.extend(
        f"journey {jid} already registered as critical"
        for jid in pending_jids
        if jid in critical_ids
    )
    violations.extend(
        f"use case {uid} already registered as critical"
        for uid in pending_uids
        if uid in critical_ids
    )

    # 4. UC → journey pairing
    journey_set = set(jids)
    violations.extend(
        f"use case {u['id']} references unknown journey {u.get('journey')!r}"
        for u in use_cases
        if u.get("journey") not in journey_set
    )

    # 5. Critical candidates must NOT be pre-registered (same-PR registration
    # rule) — except for SHIPPED phases, whose implementing PR registered
    # them by definition.
    violations.extend(
        f"critical candidate {j['id']} is already in the critical YAML — register only with the implementing PR"
        for j in pending_journeys
        if j.get("critical_candidate") and j["id"] in critical_ids
    )
    violations.extend(
        f"critical candidate {u['id']} is already in the critical YAML — register only with the implementing PR"
        for u in pending_use_cases
        if u.get("critical_candidate") and u["id"] in critical_ids
    )

    # 6. Phase coverage: every roadmap phase in tasks.md (minus excluded AND
    #    shipped) has at least one journey AND one use case planned.
    if tasks is not None and tasks.exists():
        phases = _TASKS_PHASE_RE.findall(tasks.read_text())
        plan_phases = {j["phase"] for j in pending_journeys} & {
            u["phase"] for u in pending_use_cases
        }
        for phase in phases:
            norm = phase if phase.startswith("P") else f"P{phase}"
            if norm in excluded_phases or norm in shipped_phases:
                continue
            if norm not in plan_phases:
                violations.append(f"phase {norm} in tasks.md has no planned journey+use case")

    # 7. Artifact plan (doc/spec/aggregator/backend conventions + existence)
    _check_artifact_fields(plan, violations, personas_dir, repo_root)

    return violations


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    repo = Path(__file__).resolve().parent.parent
    parser.add_argument(
        "--plan",
        type=Path,
        default=repo / "openspec/changes/add-databricks-control-plane/traceability-plan.md",
    )
    parser.add_argument(
        "--tasks",
        type=Path,
        default=repo / "openspec/changes/add-databricks-control-plane/tasks.md",
    )
    parser.add_argument("--journeys-doc", type=Path, default=repo / "docs/USER_JOURNEYS.md")
    parser.add_argument("--use-cases-doc", type=Path, default=repo / "docs/USE_CASES.md")
    parser.add_argument(
        "--critical-yaml", type=Path, default=repo / "docs/CRITICAL_UC_JOURNEY_IDS.yaml"
    )
    parser.add_argument("--personas-dir", type=Path, default=repo / "frontend/e2e/personas")
    args = parser.parse_args(argv)

    violations = check(
        load_plan(args.plan),
        args.journeys_doc,
        args.use_cases_doc,
        args.critical_yaml,
        args.tasks,
        personas_dir=args.personas_dir,
        repo_root=repo,
    )
    if violations:
        print("PLAN-IDS: FAIL")
        for violation in violations:
            print(f"  - {violation}")
        return 1
    print("PLAN-IDS: clean")
    return 0


if __name__ == "__main__":
    sys.exit(main())
