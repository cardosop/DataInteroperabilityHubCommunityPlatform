"""
Contract tests for scripts/check_no_live_tests.py.

The guard backs the destructive step of `make test-stack-reinit` (volume
wipe) — it must refuse when any live pytest/playwright run is active on
the host or inside a running container. Pins the 1.4 rehearsal lessons:

- the scanner must be self-match immune: its own command line and
  bracketed grep-style patterns must NOT count as live tests;
- containers are scanned via `docker top` (host-side truth, no shell
  needed inside scratch containers).
"""

import importlib.util
import os
import shutil
import sys
from pathlib import Path

import pytest

scripts_dir = Path(__file__).parent.parent
sys.path.insert(0, str(scripts_dir))
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

script_path = scripts_dir / "check_no_live_tests.py"
spec = importlib.util.spec_from_file_location("check_no_live_tests", script_path)
guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)


class TestLineClassification:
    @pytest.mark.parametrize(
        ("line", "expected"),
        [
            # real live-test command lines
            ("python3 -m pytest hub/apps/files/tests/test_storage.py", True),
            ("/venv/bin/python -B -I -m pytest -q tests/x.py", True),
            ("/venv/bin/pytest -q hub/apps/files/tests", True),
            ("node /usr/bin/playwright test e2e/spec.ts", True),
            ("npx playwright test --project=chromium", True),
            ("npx playwright@1.49.1 test --project=chromium", True),
            # IDE tooling that mentions pytest in a FILENAME is not a live run
            # (VSCode Pylance get_pytest_options.py — rehearsal run 2 finding)
            (
                "/venv/bin/python -B -I /home/ph/.vscode/extensions/"
                "ms-python.vscode-pylance/dist/bundled/files/"
                "get_pytest_options.py",
                False,
            ),
            ("node playwright-report-generator.js", False),
            # the scanner's own command line must never match
            ("python scripts/check_no_live_tests.py", False),
            ("make test-stack-reinit", False),
            # bracketed scan patterns (grep tricks) must not match
            ("ps aux | grep -E '[p]ytest|[p]laywright' | wc -l", False),
            # unrelated processes
            ("docker compose up -d minio-test", False),
        ],
    )
    def test_classify_line(self, line, expected):
        assert guard.classify_line(line) is expected


class TestEvaluate:
    def test_no_findings_means_clean_exit(self, capsys):
        assert guard.evaluate([], []) == 0
        assert "no live" in capsys.readouterr().out.lower()

    def test_host_findings_are_reported_and_refused(self, capsys):
        assert (
            guard.evaluate(
                ["1234 python3 -m pytest tests/x.py"], []
            )
            == 1
        )
        assert "pytest" in capsys.readouterr().out

    def test_container_findings_are_reported_and_refused(self, capsys):
        assert guard.evaluate([], ["hub-test-api"]) == 1
        out = capsys.readouterr().out
        assert "hub-test-api" in out


class TestRealHostScan:
    def test_host_scan_finds_no_live_tests_right_now(self):
        # Real `ps` scan of this machine — the rehearsal environment has
        # zero live pytest/playwright runs outside maintenance windows.
        assert guard.host_live_lines() == []

    def test_ancestor_pids_walk_the_real_process_tree(self):
        me = os.getpid()
        ancestors = guard._ancestor_pids(me)
        assert os.getppid() in ancestors
        assert me not in ancestors

    def test_host_scan_excludes_its_own_ancestry(self):
        # The pytest runner is an ancestor of this test: its command line
        # must be excluded (self-match immunity), so the scan cannot flag
        # the process tree that invoked it.
        lines = guard.host_live_lines()
        assert all("test_check_no_live_tests" not in ln for ln in lines)


@pytest.mark.skipif(
    not shutil.which("docker"),
    reason="docker not installed — container scan is unreachable",
)
class TestRealContainerScan:
    def test_container_scan_finds_no_live_tests_right_now(self):
        assert guard.containers_with_live_tests() == []

    def test_container_scan_runs_without_shell_in_containers(self):
        # The scan uses `docker top` (host-side process view), so it must
        # succeed even for scratch containers without a shell.
        hits = guard.containers_with_live_tests()
        assert isinstance(hits, list)
