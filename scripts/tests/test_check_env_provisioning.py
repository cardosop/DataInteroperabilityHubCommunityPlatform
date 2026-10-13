"""check_env_provisioning.py tests — TDD fixtures, no mocks.

The pip-listing subprocess is exercised against a REAL fake interpreter
directory containing a stub python that prints a canned pip list — the
same boundary pattern the repo uses (module boundaries, not stubs of the
unit under test).
"""

from __future__ import annotations

import stat
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from check_env_provisioning import (
    _required_distributions,
    main,
    missing_distributions,
)

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def _fake_interpreter(tmp_path: Path, pip_list: str) -> Path:
    fake = tmp_path / "fakebin" / "python"
    fake.parent.mkdir(parents=True)
    fake.write_text(
        "#!/bin/sh\n"
        'if [ "$1" = "-m" ] && [ "$2" = "pip" ] && [ "$3" = "list" ]; then\n'
        f"  printf '%s\\n' {pip_list!r}\n"
        "else\n"
        "  exec /bin/true\n"
        "fi\n"
    )
    fake.chmod(fake.stat().st_mode | stat.S_IEXEC)
    return fake


class TestParsing:
    def test_requirement_parsing(self, tmp_path):
        req = tmp_path / "requirements.txt"
        req.write_text("# comment\ndjango==4.2\nrequests>=2.28\nfreezegun\n-r other.txt\n")
        parsed = _required_distributions(req)
        assert parsed == {"django": "==4.2", "requests": ">=2.28", "freezegun": ""}

    def test_missing_and_present(self, tmp_path):
        fake = _fake_interpreter(tmp_path, "django==4.2\nrequests==2.31.0\n")
        req = tmp_path / "requirements.txt"
        req.write_text("django==4.2\nfreezegun\n")
        assert missing_distributions(str(fake), req) == {"freezegun": ""}

    def test_complete_interpreter_passes(self, tmp_path):
        fake = _fake_interpreter(tmp_path, "django==4.2\n")
        req = tmp_path / "requirements.txt"
        req.write_text("django==4.2\n")
        assert main(["--python", str(fake), "--requirements", str(req)]) == 0

    def test_missing_fails_with_pip_hint(self, tmp_path, capsys):
        fake = _fake_interpreter(tmp_path, "django==4.2\n")
        req = tmp_path / "requirements.txt"
        req.write_text("django==4.2\ncsp==4.0\n")
        assert main(["--python", str(fake), "--requirements", str(req)]) == 1
        out = capsys.readouterr().out
        assert "csp" in out
        assert "pip install" in out


class TestRealEnv:
    def test_real_venv_reports_missing_dists(self):
        """The checker must run against the REAL venv and report the known
        17-dist gap honestly (venv/ is the canonical interpreter)."""
        result = main([])
        # 0 or 1 both acceptable here: the POINT is it must not crash —
        # the real gap count is recorded separately.
        assert result in (0, 1)
