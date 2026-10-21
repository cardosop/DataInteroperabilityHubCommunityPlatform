"""core_boot_smoke.py — public-CI core boot gate (task 1.7, 313-H).

The public repo has no paid layer, so an unguarded paid import anywhere in
the boot path — a management command, a settings branch, a signal handler —
survives the import-direction gates (which scan SOURCE) and only explodes
at RUNTIME in a contributor's checkout. This script automates the H.2.5
recipe: ``HUB_CORE_ONLY=1 manage.py check`` + ``help`` + sampled command
``--help`` imports, so an import-time regression fails CI before publish.

No mocks: the real runner is exercised against a real fake-Django
``manage.py`` harness that behaves like Django's (``check`` exits 0,
``help`` lists commands, ``<cmd> --help`` exits 0, and an import-time
regression exits nonzero with a traceback), plus a REAL-repo smoke
integration test.
"""

from __future__ import annotations

import subprocess
import sys
import textwrap
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def _write_manage_harness(root: Path, broken_commands: tuple[str, ...] = ()) -> Path:
    """A manage.py that behaves like Django's CLI enough for the smoke.

    ``check`` / ``help`` / ``<cmd> --help`` exit 0; a broken command raises
    an import-time error (the regression class this gate exists for).
    """
    manage = root / "manage.py"
    commands = {
        "clean_command": "clean",
        "other_command": "other",
    }
    for name in broken_commands:
        commands[name] = "broken"
    manage.write_text(
        textwrap.dedent(
            f"""
            import sys

            _COMMANDS = {commands!r}
            _BROKEN = {list(broken_commands)!r}

            def main():
                argv = sys.argv[1:]
                if not argv or argv[0] in ("help", "-h", "--help"):
                    for name in sorted(_COMMANDS):
                        print(f"[harness]\\n    {{name}}")
                    return 0
                if argv[0] == "check":
                    print("System check identified no issues (0 silenced).")
                    return 0
                cmd, *rest = argv
                if cmd in _BROKEN:
                    raise ImportError(
                        "No module named 'hub.apps.semantic' (unhandled import)"
                    )
                if "--help" in rest or "-h" in rest:
                    print(f"usage: {{cmd}} [options]")
                    return 0
                print(f"harness command {{cmd}} ran")
                return 0

            if __name__ == "__main__":
                raise SystemExit(main())
            """
        )
    )
    return manage


def _run_smoke(
    repo: Path,
    manage_rel: str = "manage.py",
    *,
    sample_commands: str | None = "clean_command,other_command",
) -> subprocess.CompletedProcess:
    env = {
        "PATH": "/usr/bin:/bin:/usr/local/bin",
        "HOME": str(repo),
        "HUB_CORE_ONLY": "1",
        "PYTHONPATH": str(repo),
    }
    if sample_commands is not None:
        env["SMOKE_SAMPLE_COMMANDS"] = sample_commands
    return subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts" / "core_boot_smoke.py"),
            "--repo",
            str(repo),
            "--manage",
            manage_rel,
        ],
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )


class TestRunner:
    def test_clean_boot_passes(self, tmp_path):
        _write_manage_harness(tmp_path)
        result = _run_smoke(tmp_path)
        assert result.returncode == 0, result.stdout + result.stderr
        assert "check" in result.stdout
        assert "help" in result.stdout
        for cmd in ("clean_command", "other_command"):
            assert cmd in result.stdout

    def test_import_time_regression_fails(self, tmp_path):
        """THE regression class: an unguarded import in a sampled command."""
        _write_manage_harness(tmp_path, broken_commands=("clean_command",))
        result = _run_smoke(tmp_path)
        assert result.returncode != 0, "import-time regression must fail the gate"
        assert "clean_command" in result.stdout + result.stderr
        assert "semantic" in result.stdout + result.stderr

    def test_check_failure_fails(self, tmp_path):
        root = tmp_path
        (root / "manage.py").write_text(
            "import sys\nprint('System check identified 2 issues.')\nsys.exit(1)\n"
        )
        result = _run_smoke(root)
        assert result.returncode != 0
        assert "check" in result.stdout

    def test_help_failure_fails(self, tmp_path):
        root = tmp_path
        (root / "manage.py").write_text(
            "import sys\nraise ImportError('No module named hub.apps.semantic')\n"
        )
        result = _run_smoke(root)
        assert result.returncode != 0
        assert "semantic" in result.stdout + result.stderr

    def test_report_names_every_step(self, tmp_path):
        _write_manage_harness(tmp_path)
        result = _run_smoke(tmp_path)
        for step in ("check", "help", "clean_command", "other_command"):
            assert step in result.stdout, f"report missing step {step!r}"


class TestRealRepo:
    def test_real_repo_core_boot_smoke(self):
        """The real H.2.5 recipe, automated: must pass on this tree today.

        Runs the DEFAULT sample (no SMOKE_SAMPLE_COMMANDS override) so this
        test exercises exactly what the public CI job runs.
        """
        result = _run_smoke(REPO_ROOT, manage_rel="hub/manage.py", sample_commands=None)
        assert result.returncode == 0, result.stdout + result.stderr
        assert "check      -> exit 0" in result.stdout
        assert "help       -> exit 0" in result.stdout
        assert "check_services" in result.stdout  # the default sample ran
        assert "all boot checks passed" in result.stdout
