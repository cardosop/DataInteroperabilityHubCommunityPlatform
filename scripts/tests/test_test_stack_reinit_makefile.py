"""
Contract tests for the `make test-stack-reinit` target (pilot-readiness 1.5).

Pins the rehearsal lessons so the durable tooling cannot regress:

- the target is .PHONY-protected;
- the destructive step uses the SERVICE name (`down -v minio-test`) —
  a volume-name argument is a silent no-op on compose v2.40.3 (1.4
  finding) — and `--env-file .env.test` on both down and up;
- the live-test guard runs BEFORE the wipe;
- the credential detector runs pre-flight (advisory) and post-flight
  (--strict);
- the CKAN re-mint is conditional tooling, not a manual recipe.
"""

import re
from pathlib import Path

import pytest

MAKEFILE = Path(__file__).parent.parent.parent / "Makefile"


def _recipe(target: str) -> list[str]:
    text = MAKEFILE.read_text()
    match = re.search(
        rf"^{re.escape(target)}:.*\n((?:\t.*\n|\t.*\\\n\t.*\n)+)",
        text,
        re.MULTILINE,
    )
    assert match, f"target {target} not found in Makefile"
    return list(match.group(1).splitlines())


@pytest.fixture(scope="module")
def recipe():
    return _recipe("test-stack-reinit")


def test_target_is_phony():
    text = MAKEFILE.read_text()
    phony_lines = [ln for ln in text.splitlines() if ln.startswith(".PHONY")]
    assert any(
        re.search(r"(^|\s)test-stack-reinit(\s|$)", ln) for ln in phony_lines
    ), "test-stack-reinit is missing from .PHONY"


def test_live_test_guard_runs_before_the_wipe(recipe):
    guard_idx = next(
        i for i, ln in enumerate(recipe) if "check_no_live_tests.py" in ln
    )
    wipe_idx = next(i for i, ln in enumerate(recipe) if "down -v minio-test" in ln)
    assert guard_idx < wipe_idx, "the live-test guard must precede the wipe"


def test_wipe_uses_service_name_never_volume_name(recipe):
    joined = "\n".join(recipe)
    assert "down -v minio-test" in joined
    assert "down -v minio-test-data" not in joined, (
        "volume-name arguments are silent no-ops on compose v2.40.3 (1.4 finding)"
    )


def test_env_file_is_explicit_on_down_and_up(recipe):
    joined = "\n".join(recipe)
    assert joined.count("--env-file .env.test") >= 2
    down_line = next(ln for ln in recipe if "down -v minio-test" in ln)
    up_line = next(ln for ln in recipe if "up -d minio-test" in ln)
    assert "--env-file .env.test" in down_line
    assert "--env-file .env.test" in up_line


def test_detector_runs_pre_flight_advisory_and_post_flight_strict(recipe):
    pre = [ln for ln in recipe if "verify_test_stack_creds.py" in ln and "--strict" not in ln]
    post = [ln for ln in recipe if "verify_test_stack_creds.py --strict" in ln]
    assert pre, "advisory pre-flight detector run is missing"
    assert post, "strict post-flight detector run is missing"
    assert next(i for i, ln in enumerate(recipe) if "down -v minio-test" in ln) < \
        recipe.index(post[0]), "strict verification must follow the wipe"


def test_ckan_remint_is_tooling_not_a_manual_recipe(recipe):
    assert any("ckan_token_remint.py" in ln for ln in recipe)


def test_recovery_precedes_the_strict_gate(recipe):
    # A dead CKAN token must be re-minted BEFORE the strict post-flight,
    # otherwise make aborts on the FAIL before the recovery step runs
    # (rehearsal run 2 finding).
    remint_idx = next(i for i, ln in enumerate(recipe) if "ckan_token_remint.py" in ln)
    strict_idx = next(
        i for i, ln in enumerate(recipe) if "verify_test_stack_creds.py --strict" in ln
    )
    assert remint_idx < strict_idx


def test_wait_for_health_before_post_flight(recipe):
    health_idx = next(i for i, ln in enumerate(recipe) if "Health.Status" in ln)
    post_idx = next(
        i for i, ln in enumerate(recipe) if "verify_test_stack_creds.py --strict" in ln
    )
    assert health_idx < post_idx, "must wait for MinIO health before verifying"
