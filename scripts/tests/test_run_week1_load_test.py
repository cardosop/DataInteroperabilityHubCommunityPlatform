"""TDD suite for scripts/run_week1_load_test.py — the Week-1 scale load
test (pilot-readiness 4.4).

Contract pins (no k6 execution — the REAL run is the rehearsal itself):
scale governance (unconfirmed scale refuses under --strict), credential
validation, the k6 command construction (binary vs the pinned docker
image), and the workflow wiring (the CI gate must use the shared
comparator, not the retired inline python).
"""

from __future__ import annotations

import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
RUNNER = REPO_ROOT / "scripts" / "run_week1_load_test.py"
SCALE_FILE = REPO_ROOT / "tests" / "load" / "week1_scale.json"
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "k6-load-test-gate.yml"

# Import the runner's helpers without executing main().
import importlib.util  # noqa: E402

_spec = importlib.util.spec_from_file_location("run_week1_load_test", RUNNER)
_runner = importlib.util.module_from_spec(_spec)
assert _spec and _spec.loader
_spec.loader.exec_module(_runner)


def _run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["python3", str(RUNNER), *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


class TestScaleGovernance:
    def test_scale_env_maps_all_six_k6_keys(self):
        scale = _runner.load_scale()
        env = _runner.scale_env(scale)
        for key in (
            "K6_START_RATE",
            "K6_STEADY_RATE",
            "K6_PEAK_RATE",
            "K6_COOLDOWN_RATE",
            "K6_STEADY_MINUTES",
            "K6_MAX_VUS",
        ):
            assert key in env, f"scale_env must emit {key}"
            assert env[key].isdigit(), f"{key} must be numeric"

    def test_strict_refuses_unconfirmed_scale(self):
        scale = _runner.load_scale()
        assert scale["confirmed"] is False
        result = _run(
            "--strict",
            "--auth-email",
            "a@b.c",
            "--auth-password",
            "pw",
        )
        assert result.returncode == 1, result.stdout
        assert "unconfirmed scale" in result.stdout + result.stderr

    def test_missing_credentials_exits_2(self):
        result = _run("--api-base", "http://localhost:1")
        assert result.returncode == 2, result.stdout
        assert "auth-email" in result.stdout + result.stderr


class TestK6CommandConstruction:
    def test_scale_file_drives_the_stages(self):
        # The k6 script must read the same env keys the runner emits.
        script = (REPO_ROOT / "tests" / "load" / "critical_journeys.k6.js").read_text()
        for key in (
            "K6_START_RATE",
            "K6_STEADY_RATE",
            "K6_PEAK_RATE",
            "K6_COOLDOWN_RATE",
            "K6_STEADY_MINUTES",
            "K6_MAX_VUS",
        ):
            assert key in script, f"critical_journeys.k6.js must read {key}"

    def test_docker_fallback_pins_the_ci_k6_version(self):
        # The pinned image must match the CI gate's k6-version so a local
        # rehearsal and the nightly gate measure with the same runtime.
        workflow = WORKFLOW.read_text()
        assert "0.51.0" in workflow
        assert _runner.K6_IMAGE == "grafana/k6:0.51.0"


class TestWorkflowWiring:
    def test_workflow_uses_the_shared_comparator_not_inline_python(self):
        workflow = WORKFLOW.read_text()
        assert "compare_k6_baseline.py" in workflow, (
            "k6-load-test-gate.yml must call scripts/compare_k6_baseline.py — "
            "the inline python3 -c regression math was untestable"
        )
        assert 'python3 -c "' not in workflow, (
            "the inline regression comparison must be retired"
        )

    def test_workflow_loads_the_week1_scale(self):
        workflow = WORKFLOW.read_text()
        assert "week1_scale.json" in workflow, (
            "the gate must run at the recorded Week-1 scale"
        )
