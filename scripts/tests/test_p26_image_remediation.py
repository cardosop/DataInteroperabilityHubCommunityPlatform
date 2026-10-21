"""
P2-6 (close-oss-release-conditions, G5) — image-remediation pins.

The P0-14 audit found every pre-rotation tag of the published images
(+ their ``buildcache`` tags) bakes credential material (the tracked
``.claude/settings.json`` live token, baked by every whole-context
``COPY . .`` image). P2-6 remediates AFTER the rotations: rebuild
-and-republish (or delete) every affected tag, with evidence recorded.

Pins, each at the weakest point:

1. **The remediation tool is real** — ``scripts/remediate_affected_images.py``
   enumerates the REAL GHCR version state through the real ``gh`` API,
   applies the pinned disposition rules, refuses destructive execution
   while the rotation gate (GATE-65, the real
   ``check_history_rotation_map.py``) is red, and records evidence.
2. **The disposition rules are pinned pure functions** — buildcache
   tags and deleted-lane packages are DELETEd outright; pre-window
   tags of active packages hold (REBUILD_THEN_DELETE) until a
   post-window replacement version exists in the same package (the
   replacement invariant — deleting the old tags without a rebuilt
   successor would leave deployments broken); post-window versions
   are KEPT.
3. **The rotation gate leg is REAL** — the executor runs the real
   gate binary; a fixture map with a PENDING row refuses execution
   and names the class; the executor's verdict matches the real
   gate's exit code on the committed map (honest in BOTH states —
   today the gate is honestly red on the 3 unrotated console
   surfaces, which is the sequencing enforcement working).
4. **The dormant inference-service lane is DELETED** (the
   delete-or-wire disposition) — the workflow lane, the helm chart
   templates and the values block are gone; the package remains in
   the executor's deleted-lane list so any published versions get
   deleted (no rebuild is possible for a lane that no longer exists).

No mocks: real gh, real gate binary, real workflow YAML, real fixture
maps. The live gh legs are W16-gated (``skip_or_fail``).
"""

from __future__ import annotations

import importlib.util
import shutil
import subprocess
import sys
from pathlib import Path

scripts_dir = Path(__file__).parent.parent
sys.path.insert(0, str(scripts_dir))

ROOT = scripts_dir.parent
sys.path.insert(0, str(ROOT))

from envpolicy import skip_or_fail

TOOL = scripts_dir / "remediate_affected_images.py"
GATE65 = scripts_dir / "check_history_rotation_map.py"
DEPLOY_WF = ROOT / ".github/workflows/deploy.yml"
HELM_VALUES = ROOT / "helm/values.yaml"

tool_spec = importlib.util.spec_from_file_location(
    "remediate_affected_images", TOOL
)
assert tool_spec is not None, "remediate_affected_images.py must load (P2-6 ships it)"
assert tool_spec.loader is not None
tool = importlib.util.module_from_spec(tool_spec)
tool_spec.loader.exec_module(tool)

audit_spec = importlib.util.spec_from_file_location(
    "audit_image_build_contexts", scripts_dir / "audit_image_build_contexts.py"
)
assert audit_spec is not None, "audit_image_build_contexts.py must load"
assert audit_spec.loader is not None
audit = importlib.util.module_from_spec(audit_spec)
audit_spec.loader.exec_module(audit)

GH = shutil.which("gh")

WINDOW = "2026-10-20T00:00:00Z"
PRE = "2026-10-01T12:00:00Z"
POST = "2026-10-21T12:00:00Z"


def _require_gh() -> None:
    if not GH:
        skip_or_fail("gh CLI (the live registry legs run against the real API)")


def _run(args: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, *args], capture_output=True, text=True, check=False, cwd=cwd
    )


def _version(
    version_id: int,
    tags: list[str],
    created: str = PRE,
    name: str | None = None,
) -> dict:
    return {
        "id": version_id,
        "name": name if name is not None else tags[0],
        "tags": tags,
        "created": created,
    }


# ── 1. The tool + inventory reuse ──────────────────────────────────────────


def test_tool_inventory_reuses_the_audit_tool_and_keeps_the_deleted_lane():
    """The remediation universe = the deploy workflow's canonical push
    inventory (9 images post-deletion) + the deleted-lane package
    (inference-service — its published versions must still be deleted
    even though the lane is gone). The enumeration identifiers are the
    PACKAGE names (``datainteroperabilityhub-<service>`` — the image
    name minus the registry owner), not the bare service names."""
    import inspect

    packages = tool.inventory_packages(ROOT)
    workflow_services = {
        entry["service"] for entry in audit.load_inventory(DEPLOY_WF)
    }
    assert workflow_services == {
        "api-service",
        "worker-service",
        "compliance-service",
        "prefect-integration-service",
        "semantic-service",
        "dq-service",
        "datacontract-service",
        "frontend",
        "product-site",
    }
    expected = {f"datainteroperabilityhub-{s}" for s in workflow_services}
    expected |= set(tool.DELETED_LANE_PACKAGES)
    assert set(packages) == expected, f"package drift: {set(packages) ^ expected}"
    assert "datainteroperabilityhub-inference-service" in tool.DELETED_LANE_PACKAGES
    # the inventory is REUSED from the audit tool — a duplicated
    # per-tool inventory would drift (the P0-14 inventory pin is the
    # single source of truth)
    src = inspect.getsource(tool.inventory_packages)
    assert "load_inventory" in src


# ── 2. The disposition rules (pure functions) ───────────────────────────────


def test_buildcache_tag_is_deleted_regardless_of_window():
    """A buildcache tag is a BuildKit cache artifact (mode=max layers
    retain pre-fix content), never a deployment target — DELETE."""
    version = _version(1, ["buildcache"])
    assert (
        tool.disposition_for("api-service", version, WINDOW, has_post_window=False)
        == tool.DISPOSITION_DELETE
    )


def test_deleted_lane_package_versions_are_deleted_even_post_window():
    """The inference-service lane no longer exists — no rebuild is
    possible, so every published version is DELETEd, even one created
    after the rotation window."""
    version = _version(2, ["latest"], created=POST)
    assert (
        tool.disposition_for(
            "datainteroperabilityhub-inference-service",
            version,
            WINDOW,
            has_post_window=False,
        )
        == tool.DISPOSITION_DELETE
    )


def test_pre_window_tag_holds_without_a_replacement():
    """An active image's pre-rotation tag must NOT be deleted before a
    rebuilt (post-window) successor exists — deleting it would leave
    deployments without a pullable image."""
    version = _version(3, ["sha-abc123", "latest"], created=PRE)
    assert (
        tool.disposition_for("api-service", version, WINDOW, has_post_window=False)
        == tool.DISPOSITION_REBUILD_THEN_DELETE
    )
    assert (
        tool.disposition_for("api-service", version, WINDOW, has_post_window=True)
        == tool.DISPOSITION_DELETE
    )


def test_post_window_version_is_kept():
    version = _version(4, ["sha-def456"], created=POST)
    assert (
        tool.disposition_for("worker-service", version, WINDOW, has_post_window=True)
        == tool.DISPOSITION_KEEP
    )


def test_window_cutoff_is_exclusive():
    """The window-close timestamp itself is the rotation-completion
    boundary: a version created AT it is post-window (KEEP), one
    created before it is affected."""
    version = _version(5, ["sha-eq"], created=WINDOW)
    assert (
        tool.disposition_for("api-service", version, WINDOW, has_post_window=False)
        == tool.DISPOSITION_KEEP
    )
    earlier = _version(6, ["sha-before"], created="2026-10-19T23:59:59Z")
    assert (
        tool.disposition_for("api-service", earlier, WINDOW, has_post_window=False)
        == tool.DISPOSITION_REBUILD_THEN_DELETE
    )


def test_executable_rows_separate_deletes_from_holds():
    """The execution loop is a pinned pure function over the plan rows:
    REBUILD_THEN_DELETE rows HALT the run (named), DELETE rows form the
    API deletion set."""
    rows = [
        {"package": "api-service", "version_id": 1, "tag": "buildcache",
         "disposition": tool.DISPOSITION_DELETE},
        {"package": "api-service", "version_id": 2, "tag": "sha-abc123",
         "disposition": tool.DISPOSITION_REBUILD_THEN_DELETE},
        {"package": "worker-service", "version_id": 3, "tag": "latest",
         "disposition": tool.DISPOSITION_DELETE},
        {"package": "frontend", "version_id": 4, "tag": "sha-def456",
         "disposition": tool.DISPOSITION_KEEP},
    ]
    deletable, holds = tool.executable_rows(rows)
    assert [d["version_id"] for d in deletable] == [1, 3]
    assert [h["package"] for h in holds] == ["api-service"]


# ── 3. The rotation gate leg (the REAL GATE-65 binary) ──────────────────────


_MANDATED = (
    "gcp-sa-key",
    "aws-pair",
    "azure-sp-secret",
    "databricks-pat",
    "snowflake-pat",
    "stripe-test-key",
    "anthropic-auth-token",
    "staging-passwords",
    "postgres-certs",
    "test-stack",
)


def _fixture_map(tmp_path: Path, evidence: str) -> tuple[Path, Path]:
    """A REAL gate input pair: the candidate enumeration (one class —
    the class key carries the gate's markdown pipe escape) + a mapping
    covering every MANDATED class (the gate requires them all) with
    dated evidence for the candidate row."""
    candidates = tmp_path / "candidates.md"
    candidates.write_text(
        "| Rule | Category | Findings |\n|---|---|---|\n"
        "| stripe | docs/example | 1 |\n",
        encoding="utf-8",
    )
    rows = ["| Class | Evidence |", "|---|---|"]
    for cls in _MANDATED:
        rows.append(f"| {cls} | rotated 2026-10-19 (dated evidence) |")
    rows.append(f"| stripe\\|docs/example | {evidence} |")
    mapping = tmp_path / "map.md"
    mapping.write_text("\n".join(rows) + "\n", encoding="utf-8")
    return candidates, mapping


def test_verdict_wrapper_runs_the_real_gate_and_reports_pending(tmp_path):
    """The wrapper executes the REAL gate binary over fixture inputs; a
    PENDING row yields an unready verdict naming the class (values
    never appear)."""
    candidates, mapping = _fixture_map(tmp_path, "PENDING — console rotation")
    ok, problems = tool.rotation_gate_verdict(candidates, mapping)
    assert ok is False
    assert any("stripe|docs/example" in p for p in problems)
    assert any("PENDING" in p for p in problems)


def test_verdict_wrapper_green_on_evidenced_map(tmp_path):
    candidates, mapping = _fixture_map(tmp_path, "rotated 2026-10-19")
    ok, problems = tool.rotation_gate_verdict(candidates, mapping)
    assert ok is True, problems
    assert problems == []


def test_decide_execution_refusals(tmp_path):
    """The execution decision is a pinned pure function: the rotation
    gate, the window-close timestamp and the explicit confirmation are
    each independently required — any missing precondition REFUSES with
    its own named reason."""
    candidates, mapping = _fixture_map(tmp_path, "rotated 2026-10-19")
    ok, _ = tool.rotation_gate_verdict(candidates, mapping)
    assert tool.decide_execution(ok, WINDOW, confirm=False, holds=[]).action == (
        "REFUSED_CONFIRM"
    )
    assert tool.decide_execution(ok, None, confirm=True, holds=[]).action == (
        "REFUSED_WINDOW_CLOSE"
    )
    assert tool.decide_execution(False, WINDOW, confirm=True, holds=[]).action == (
        "REFUSED_ROTATION_GATE"
    )
    holds = [{"package": "api-service", "version_id": 1, "tag": "sha-abc123",
              "disposition": tool.DISPOSITION_REBUILD_THEN_DELETE}]
    assert tool.decide_execution(ok, WINDOW, confirm=True, holds=holds).action == (
        "HOLD_REBUILD"
    )
    assert tool.decide_execution(ok, WINDOW, confirm=True, holds=[]).action == (
        "PROCEED"
    )


def test_execute_refused_end_to_end_while_gate_is_red(tmp_path):
    """The real CLI run refuses --execute while the gate is red — the
    refusal fires BEFORE any registry call, so the run is safe to
    execute anywhere."""
    candidates, mapping = _fixture_map(tmp_path, "rotated")
    (mapping.parent / "map.md").write_text(
        "| Class | Evidence |\n|---|---|\n"
        "| stripe|docs/example | PENDING — console rotation |\n",
        encoding="utf-8",
    )
    proc = _run(
        [str(TOOL), "--execute", "--window-close", WINDOW, "--confirm-delete",
         "--candidates", str(candidates), "--map", str(mapping)],
        cwd=ROOT,
    )
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "REFUSED" in proc.stdout
    assert "stripe|docs/example" in proc.stdout


def test_executor_verdict_matches_the_real_gate_on_the_committed_map():
    """Consistency with the real gate on the committed map — honest in
    BOTH states: while rotations pend (today: the 3 console surfaces)
    the executor refuses; once the map is fully evidenced the executor
    becomes ready."""
    real = subprocess.run(
        [sys.executable, str(GATE65)],
        capture_output=True,
        text=True,
        check=False,
        cwd=ROOT,
    )
    ok, problems = tool.rotation_gate_verdict()
    assert ok == (real.returncode == 0)
    if not ok:
        assert problems, "an unready verdict must name the pending classes"
        assert any(p in real.stdout + real.stderr for p in problems[:1])


# ── 4. The live registry legs (W16-gated) ───────────────────────────────────


def test_enumeration_fails_closed_on_unknown_package():
    """A nonexistent package returns the honest error state (the
    fail-closed shape: empty versions + a non-empty error) — never a
    crash and never a silent empty plan."""
    _require_gh()
    versions, error = tool.enumerate_package("datainteroperabilityhub-no-such-pkg")
    assert versions == []
    assert error, "a failing gh api call must report its error"


def test_live_enumeration_contract():
    """The real enumeration leg: either the token carries
    ``read:packages`` and versions come back, or the API fails and the
    error state is reported — the contract is the honest pairing, not
    the token state. (Today the keyring token carries no
    ``read:packages`` — the P2-6 record documents the required token
    scope.)"""
    _require_gh()
    versions, error = tool.enumerate_package("datainteroperabilityhub-api-service")
    assert (bool(versions) and not error) or (not versions and bool(error)), (
        f"versions={len(versions)} error={error!r}"
    )
    for version in versions:
        assert {"id", "name", "tags", "created"} <= set(version)


# ── 5. Evidence record ──────────────────────────────────────────────────────


def test_record_renders_dispositions_and_verdict():
    """The evidence record renders every row's disposition and the
    execution verdict (REFUSED while the gate is red — the honest
    pre-rotation state)."""
    enumerated = {
        "datainteroperabilityhub-api-service": (
            [
                _version(11, ["buildcache"]),
                _version(12, ["sha-abc123", "latest"], created=PRE),
                _version(13, ["sha-def456"], created=POST),
            ],
            "",
        ),
        "datainteroperabilityhub-worker-service": (
            [_version(21, ["sha-pre"], created=PRE)],
            "",
        ),
        "datainteroperabilityhub-inference-service": ([], ""),
    }
    plan = tool.build_plan(
        [
            "datainteroperabilityhub-api-service",
            "datainteroperabilityhub-worker-service",
            "datainteroperabilityhub-inference-service",
        ],
        enumerated,
        WINDOW,
        verdict_ok=False,
    )
    record = tool.render_record(plan)
    assert "api-service" in record
    assert tool.DISPOSITION_DELETE in record
    assert tool.DISPOSITION_REBUILD_THEN_DELETE in record
    assert tool.DISPOSITION_KEEP in record
    assert "REFUSED" in record
    assert "inference-service" in record


# ── 6. The dormant-lane deletion contract ───────────────────────────────────


def test_inference_lane_deleted_from_deploy_workflow():
    """delete-or-wire = DELETE: the deploy workflow carries no
    inference-service lane (build step, image env outputs, SERVICES
    entries) — the lane was guarded on a Dockerfile that never
    existed."""
    wf = DEPLOY_WF.read_text(encoding="utf-8")
    assert "build-inference" not in wf
    assert "inference-service" not in wf
    assert "inference-build-image" not in wf


def test_inference_helm_chart_deleted():
    """The disabled helm chart (enabled: false, replicaCount 0, an
    image that could never be built) is gone: no values block, no
    templates, no network policy, no helm-unittest cases."""
    values = HELM_VALUES.read_text(encoding="utf-8")
    assert "inferenceServing" not in values
    assert not (ROOT / "helm/templates/inference-serving").exists()
    assert not (
        ROOT / "helm/templates/networkpolicy/allow-inference-serving.yaml"
    ).exists()
    helm_tests = (ROOT / "helm/tests/deployment_aws_env_test.yaml").read_text(
        encoding="utf-8"
    )
    assert "inference-serving" not in helm_tests
    assert "build-inference" not in audit.STEP_SERVICE


def test_makefile_and_lint_list_wiring():
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    assert "image-remediation-plan" in makefile
    assert "remediate_affected_images.py" in makefile
    lint = (ROOT / ".github/workflows/_reusable.lint.yml").read_text(
        encoding="utf-8"
    )
    assert "scripts/tests/test_p26_image_remediation.py" in lint
