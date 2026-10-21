"""verify_gate_falsifiability.py tests — REAL checkers, no mocks."""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from verify_gate_falsifiability import GATES, main, verify

# The substitution SEARCH portion of a sed command: s/<search>/<replace>/…
# (an empty search — the s// form — reuses the address regex and is fine).
_SED_SEARCH = re.compile(r"s/((?:\\.|[^/\\])*)/")


class TestHarness:
    def _checker(self, tmp_path: Path) -> str:
        """A REAL python gate: greps the target for BANNED and exits 1 on a hit."""
        script = tmp_path / "gate.py"
        script.write_text(
            "import sys\n"
            "text = open(sys.argv[1]).read()\n"
            "if 'BANNED' in text:\n"
            "    print('1 failed')\n"
            "    sys.exit(1)\n"
            "print('1 passed')\n"
            "sys.exit(0)\n"
        )
        return f"{sys.executable} {script} {{target}}"

    def _target(self, tmp_path: Path) -> Path:
        target = tmp_path / "target.txt"
        target.write_text("clean content\n")
        return target

    def test_all_weakenings_bite(self, tmp_path):
        checker = self._checker(tmp_path)
        target = self._target(tmp_path)
        ok, report = verify(
            checker,
            str(target),
            [
                f"inject-banned:{sys.executable} -c \"open('{{target}}','a').write('BANNED\\n')\"",
            ],
        )
        assert ok, report
        assert "BITES" in report[0]

    def test_vacuous_weakening_is_reported(self, tmp_path):
        checker = self._checker(tmp_path)
        target = self._target(tmp_path)
        # A weakening that does NOT change the target's semantics.
        ok, report = verify(
            checker,
            str(target),
            [
                f"no-op:{sys.executable} -c \"open('{{target}}','a').write('nothing\\n')\"",
            ],
        )
        assert not ok
        assert any("VACUOUS" in line for line in report)

    def test_exit_code_is_part_of_the_outcome(self, tmp_path):
        """A script gate with NO pytest summary must still bite via rc.

        Regression for the Q.5.2 harness bug: comparing summary lines alone
        makes every non-pytest gate VACUOUS.
        """
        checker = self._checker(
            tmp_path
        )  # prints '1 passed'/'1 failed' — no pytest tail
        target = self._target(tmp_path)
        ok, report = verify(
            checker,
            str(target),
            [
                f"inject-banned:{sys.executable} -c \"open('{{target}}','a').write('BANNED\\n')\"",
            ],
        )
        assert ok, report

    def test_target_restored_byte_identical_after_bites(self, tmp_path):
        checker = self._checker(tmp_path)
        target = self._target(tmp_path)
        before = target.read_bytes()
        verify(
            checker,
            str(target),
            [
                f"inject-banned:{sys.executable} -c \"open('{{target}}','a').write('BANNED\\n')\"",
            ],
        )
        assert target.read_bytes() == before, "the mutation must be fully restored"


class TestRegistry:
    def test_every_registry_target_exists(self):
        for name, (_checker, target, _weakenings) in GATES.items():
            assert Path(target).exists(), f"{name}: mutation target missing: {target}"

    def test_every_weakening_has_label_and_command(self):
        for name, (_checker, _target, weakenings) in GATES.items():
            assert weakenings, f"{name}: no weakenings defined"
            for label, command in weakenings:
                assert label, f"{name}: malformed weakening {label!r}"
                assert command, f"{name}: malformed weakening {label!r}"

    def test_no_unescaped_double_asterisk_in_sed_searches(self):
        # A leading `*` in a POSIX BRE is invalid ("Invalid preceding
        # regular expression") — sed exits non-zero, the mutation no-ops,
        # and the weakening silently reads VACUOUS. Markdown bold fields
        # (`**Field:** VALUE`) must be escaped: `\*\*Field:\*\*`.
        # Found 2026-10-07: GATE-51's flip-rotated-row weakening carried
        # the unescaped form since W0.5 — its claimed "BITES" was never
        # exercised by a real mutation.
        offenders = []
        for name, (_checker, _target, weakenings) in GATES.items():
            for label, command in weakenings:
                if "sed" not in command:
                    continue
                for search in _SED_SEARCH.findall(command):
                    if re.search(r"(?<!\\)\*\*", search):
                        offenders.append(f"{name}::{label}")
        assert not offenders, (
            "unescaped `**` in a sed search is an invalid POSIX BRE — the "
            f"weakening silently no-ops (VACUOUS): {offenders}"
        )

    def test_unknown_gate_is_usage_error(self):
        assert main(["--gate", "no-such-gate"]) == 2

    def test_gate_mode_runs_a_registry_entry(self):
        assert main(["--gate", "gate-02-unused-assert-raises"]) == 0

    def test_audit_reports_every_gate_falsifiable(self):
        """The W5 DoD: every wired gate is falsifiable — the full audit.

        Runs the REAL weakenings against the REAL targets (mutate + gate
        re-run + restore), including the pytest-backed gate suites.
        """
        assert main(["--audit"]) == 0


class TestRealGate:
    def test_real_contract_pin_is_falsifiable(self):
        """The 1.1 hook-contract pin under a REAL weakening: dropping a key
        from the metadata table must fail the suite.

        Requires a REACHABLE test database (the subprocess pytest boots the
        root conftest → Django). Skip when the configured host:port is not
        reachable — checking POSTGRES_HOST alone is insufficient: the root
        conftest's django.setup() loads .env defaults into os.environ, so
        the variable is set even in envs where the DB is unreachable.
        """
        import os
        import socket

        import pytest as _pytest

        host = os.environ.get("POSTGRES_HOST", "postgres")
        port = int(os.environ.get("POSTGRES_PORT", "5432"))
        try:
            with socket.create_connection((host, port), timeout=2):
                pass
        except OSError:
            _pytest.skip(f"host-side DB unreachable at {host}:{port}")
        ok, report = verify(
            checker=f"{sys.executable} -m pytest tests/unit/test_commercial_hooks_api_contract.py -q -p no:cacheprovider",
            target="hub/apps/core/commercial_hooks.py",
            weakenings=[
                f"drop-key:{sys.executable} - <<'PY'\n"
                "from pathlib import Path\n"
                "p = Path('{target}')\n"
                "t = p.read_text()\n"
                'p.write_text(t.replace(\'("get_tenant_sparql_view", "",\', \'("get_tenant_sparql_view_RENAMED", "",\', 1))\n'
                "PY",
            ],
        )
        assert ok, report
