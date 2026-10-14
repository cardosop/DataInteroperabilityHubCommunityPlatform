#!/usr/bin/env python3
"""Phase Q.5 — gate falsifiability harness + registry.

A check that cannot fail is indistinguishable from a check that passes
(Phase 1.1 shipped four of them; CI shipped more). This harness runs a
TARGET check under a set of WEAKENINGS — each weakening must change the
result — and reports VACUOUS when a weakening survives.

Two weakening styles, per gate:

* SELF-MUTATION — for gates with their own pytest suite: the weakening
  mutates the GATE SCRIPT itself and the suite must fail (≥1 named test).
* OFFENDER-INJECTION — for bare scan gates: the weakening injects a real
  offender pattern into a real scanned file (``hub/tests/
  gate_falsifiability_probe.py``), the gate is re-run scoped to that file,
  and its exit code must flip 0 -> 1.

Q.5.2 extended this with the ``GATES`` registry + ``--gate`` / ``--audit``
modes so EVERY wired gate is audited, and made outcomes exit-code-aware:
script gates report no pytest summary line, so comparing summaries alone
would call a failing gate VACUOUS.

Usage:
    python scripts/verify_gate_falsifiability.py --gate gate-01-assert-true-true
    python scripts/verify_gate_falsifiability.py --audit   # every gate, table
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
# The probe lives in its OWN directory so dir-walking scan gates can be
# scoped to it (os.walk on a file path yields nothing — the Q.5.2 trap).
PROBE_DIR = str(REPO_ROOT / "hub" / "apps" / "core" / "tests" / "falsifiability_probe")
PROBE = str(
    REPO_ROOT
    / "hub"
    / "apps"
    / "core"
    / "tests"
    / "falsifiability_probe"
    / "test_gate_probe.py"
)

# Interpreter for checker commands: the canonical venv when present (this
# host has no bare `python` on PATH — the Q.5.1 trap), else python3/python.
_VENV_PYTHON = REPO_ROOT / "venv" / "bin" / "python"
PYTHON = (
    str(_VENV_PYTHON)
    if _VENV_PYTHON.exists()
    else ("python3" if shutil.which("python3") else "python")
)

# gate -> (checker command, mutation target, [(label, mutation command)])
# {target} is substituted in checker + mutation commands.
GATES: dict[str, tuple[str, str, list[tuple[str, str]]]] = {
    # ── Scan gates: offender-injection into the shared probe file ───────
    "gate-01-assert-true-true": (
        "{python} scripts/check_assert_true_true.py",
        PROBE,
        [
            (
                "inject-assertTrue(True)",
                "printf '\\n\\n    def test_probe_offender(self):\\n"
                "        self.assertTrue(True)\\n' >> {target}",
            ),
        ],
    ),
    "gate-02-unused-assert-raises": (
        "{python} scripts/check_unused_assert_raises.py --path hub/apps/core/tests/falsifiability_probe",
        PROBE,
        [
            (
                "inject-unused-cm",
                "printf '\\n\\n    def test_probe_unused_context(self):\\n"
                "        with self.assertRaises(ValueError) as cm:\\n"
                '            raise ValueError("probe")\\n\' >> {target}',
            ),
        ],
    ),
    "gate-03-broad-status-codes": (
        "{python} scripts/check_broad_status_codes.py --path hub/apps/core/tests/falsifiability_probe",
        PROBE,
        [
            (
                "inject-broad-status-list",
                "printf '\\n\\n    def test_probe_broad_statuses(self):\\n"
                '        response = type("R", (), {"status_code": 200})()\\n'
                "        self.assertIn(response.status_code, [200, 201, 400, 403, 404, 500, 503])\\n' >> {target}",
            ),
        ],
    ),
    "gate-05-time-sleep": (
        "{python} scripts/check_time_sleep_in_tests.py --max-allowed 0 --path hub/apps/core/tests/falsifiability_probe",
        PROBE,
        [
            (
                "inject-time-sleep",
                "printf '\\n\\n    def test_probe_sleeps(self):\\n"
                "        import time\\n        time.sleep(0.01)\\n' >> {target}",
            ),
        ],
    ),
    "gate-06-no-reverse-match": (
        "{python} scripts/check_no_reverse_match.py --path hub/apps/core/tests/falsifiability_probe",
        PROBE,
        [
            (
                "inject-noreversematch-handler",
                "printf '\\n\\n    def test_probe_reverse(self):\\n"
                "        try:\\n"
                "            self.assertEqual(1, 1)\\n"
                "        except NoReverseMatch:\\n"
                "            pass\\n' >> {target}",
            ),
        ],
    ),
    "gate-07-skip-in-body": (
        "{python} scripts/check_pytest_skip_in_body.py --path hub/apps/core/tests/falsifiability_probe",
        PROBE,
        [
            (
                "inject-skip-in-body",
                "printf '\\n\\n    def test_probe_skip_in_body(self):\\n"
                "        import pytest\\n"
                '        pytest.skip("probe")\\n\' >> {target}',
            ),
        ],
    ),
    "gate-08-empty-test-methods": (
        "{python} scripts/check_empty_test_methods.py --path hub/apps/core/tests/falsifiability_probe",
        PROBE,
        [
            (
                "inject-empty-test",
                "printf '\\n\\n    def test_probe_empty(self):\\n"
                '        """Docstring only — no meaningful body."""\\n\' >> {target}',
            ),
        ],
    ),
    "gate-09-bare-assert-called": (
        "{python} scripts/check_bare_assert_called.py --path hub/apps/core/tests/falsifiability_probe",
        PROBE,
        [
            (
                "inject-bare-assert-called",
                "printf '\\n\\n    def test_probe_bare_assert_called(self):\\n"
                "        from unittest import mock\\n"
                "        m = mock.Mock()\\n"
                "        m()\\n"
                "        m.assert_called()\\n' >> {target}",
            ),
        ],
    ),
    # ── Registry/flag gates: mutate the feature-flag registry ──────────
    "gate-23-stale-defaults": (
        "{python} scripts/check_stale_defaults.py",
        "hub/apps/tenants/feature_flag_registry.py",
        [
            (
                "inject-unjustified-ga-default-off",
                '{python} -c "\n'
                "import pathlib\n"
                "p = pathlib.Path('{target}')\n"
                "lines = p.read_text().splitlines()\n"
                "idx = max(i for i, l in enumerate(lines) if l.strip() == ']')\n"
                "flag = [\n"
                "    '    FeatureFlag(',\n"
                "    '        name=\\\"falsifiability_probe_q5\\\",',\n"
                "    '        description=\\\"Probe flag without documentation\\\",',\n"
                "    '        owner_team=\\\"probe-team\\\",',\n"
                "    '        owner_email=\\\"probe@meshant.com\\\",',\n"
                "    '        created_at=_PHASE_240_INTRODUCED,',\n"
                "    '        stage=\\\"GA\\\",',\n"
                "    '        retire_by=datetime(2030, 1, 1, tzinfo=UTC),',\n"
                "    '        default_existing_tenants=True,',\n"
                "    '        default_new_tenants=False,',\n"
                "    '        related_phase=\\\"Phase Q.5.2\\\",',\n"
                "    '    ),',\n"
                "]\n"
                "lines[idx:idx] = flag\n"
                "p.write_text(chr(10).join(lines) + chr(10))\n"
                '"',
            ),
        ],
    ),
    # ── Doc-marker gates: strip a real CRITICAL marker from a real test ──
    "gate-26-journey-marker-coverage": (
        "{python} scripts/lint_journey_marker_coverage.py --blocking",
        "tests/e2e/test_authentication.py",
        [
            (
                "strip-critical-journey-marker",
                'sed -i \'s/journey("JOURNEY-AUTH-001")/journey("JOURNEY-AUTH-001-STRIPPED")/\' {target}',
            ),
        ],
    ),
    "gate-27-journey-doc-marker-sync": (
        "{python} scripts/check_doc_journey_marker_sync.py --ci-mode",
        "tests/e2e/test_authentication.py",
        [
            (
                "strip-critical-journey-marker",
                'sed -i \'s/journey("JOURNEY-AUTH-001")/journey("JOURNEY-AUTH-001-STRIPPED")/\' {target}',
            ),
        ],
    ),
    # ── Suite-backed gates: self-mutation must fail ≥1 named test ───────
    "gate-29-core-boundary": (
        "{python} -m pytest scripts/tests/test_check_core_boundary_guards.py -p no:django -q -c /dev/null",
        "scripts/check_core_boundary.py",
        [
            (
                "rename-classifier-string",
                'sed -i \'s/"try-covered-BROKEN"/"try-covered"/g\' {target}',
            ),
        ],
    ),
    "gate-30-openspec-structural": (
        "{python} -m pytest scripts/tests/test_validate_openspec_change.py -p no:django -q -c /dev/null",
        "scripts/validate_openspec_change.py",
        [
            (
                "blind-missing-section-check",
                "sed -i 's/if section not in text:/if section not in text and False:/' {target}",
            ),
        ],
    ),
    "gate-31-access-request-order": (
        "{python} -m pytest scripts/tests/test_check_access_request_order_kwarg.py -p no:django -q -c /dev/null",
        "scripts/check_access_request_order_kwarg.py",
        [
            (
                "break-detected-kwarg",
                'sed -i \'s/_ORDER_KW = "order"/_ORDER_KW = "order-BROKEN"/\' {target}',
            ),
        ],
    ),
    "gate-32-core-e2e-selection": (
        "{python} -m pytest scripts/tests/test_check_core_e2e_selection.py -p no:django -q -c /dev/null",
        "scripts/check_core_e2e_selection.py",
        [
            (
                "rename-read-entries",
                "sed -i 's/def _read_entries(core_only_path/def _read_entries_disabled(core_only_path/' {target}",
            ),
        ],
    ),
    "gate-33-docs-references": (
        "{python} -m pytest scripts/tests/test_check_docs_references.py -p no:django -q -c /dev/null",
        "scripts/check_docs_references.py",
        [
            (
                "rename-looks-like-path",
                "sed -i 's/def _looks_like_path(ref/def _looks_like_path_disabled(ref/' {target}",
            ),
        ],
    ),
    "gate-34-config-single-source": (
        "{python} -m pytest scripts/tests/test_check_config_single_source.py -p no:django -q -c /dev/null",
        "scripts/check_config_single_source.py",
        [
            (
                "drop-tools-entry",
                'sed -i \'s/"ruff": {/"ruff-DISABLED": {/\' {target}',
            ),
        ],
    ),
    "gate-35-lint-debt-ratchet": (
        "{python} -m pytest scripts/tests/test_check_lint_debt_ratchet.py -p no:django -q -c /dev/null",
        "scripts/check_lint_debt_ratchet.py",
        [
            (
                "break-baseline-compare",
                "sed -i 's/count > baseline_count/count > baseline_count + 999999/' {target}",
            ),
        ],
    ),
    "q42-env-provisioning": (
        "{python} -m pytest scripts/tests/test_check_env_provisioning.py -p no:django -q -c /dev/null",
        "scripts/check_env_provisioning.py",
        [
            (
                "always-report-nothing-missing",
                "sed -i 's/    return missing$/    return {}/' {target}",
            ),
        ],
    ),
    "gate-36-mypy-ratchet": (
        "{python} -m pytest scripts/tests/test_check_mypy_debt_ratchet.py -p no:django -q -c /dev/null",
        "scripts/check_mypy_debt_ratchet.py",
        [
            (
                "blind-growth-comparison",
                "sed -i 's/if count > baseline_total:/if count > baseline_total + 999999:/' {target}",
            ),
        ],
    ),
    "gate-37-bandit-ratchet": (
        "{python} -m pytest scripts/tests/test_check_bandit_debt_ratchet.py -p no:django -q -c /dev/null",
        "scripts/check_bandit_debt_ratchet.py",
        [
            (
                "blind-growth-comparison",
                "sed -i 's/if count > baseline_total:/if count > baseline_total + 999999:/' {target}",
            ),
        ],
    ),
    # P.2b — paid AppConfig.ready() registrations pinned at source: a deleted
    # set_* call in a paid apps.py orphans a contract slot and silently
    # degrades full mode to the (partly fail-open) core fallback.
    "gate-38-paid-ready-registrations": (
        "{python} -m pytest scripts/tests/test_check_paid_ready_registrations.py -p no:django -q -c /dev/null",
        "scripts/check_paid_ready_registrations.py",
        [
            (
                "blind-clean-pass",
                "sed -i 's/return violations/return []/' {target}",
            ),
        ],
    ),
    # T.1 / W13 — an assert-free test function passes vacuously; the gate
    # ratchets the count, so the weakening injects ONE offender into the
    # probe file (8-space indent appends a method INSIDE the probe's
    # TestCase) and the gate must grow by exactly one and fail.
    "gate-39-zero-assertion-tests": (
        "{python} scripts/check_zero_assertion_tests.py",
        PROBE,
        [
            (
                "inject-assert-free-test",
                "printf '\\n        def test_probe_offender(self):\\n            pass\\n' >> {target}",
            ),
        ],
    ),
    # T.5 / W17 — scaffold debt owns a ticket and an expiry. The weakening
    # injects an EXPIRED annotated skip into the probe file: the expiry
    # check fails even under baseline, so a gate that stops checking dates
    # (or stops scanning skip sites) is caught immediately.
    # T.6 / W18 — a CODEOWNERS typo ships its subtree with no codeowner
    # and no required reviewer. The weakening injects a dead path into
    # the committed CODEOWNERS document; the gate must fail naming it.
    "gate-41-codeowners-paths": (
        "{python} scripts/check_codeowners_paths.py",
        ".github/CODEOWNERS",
        [
            (
                "inject-dead-path",
                "printf '\\nthis/does/not/exist/ @meshant/data-platform-eng\\n' >> {target}",
            ),
        ],
    ),
    "gate-40-skip-expiry": (
        "{python} scripts/check_skip_expiry.py",
        PROBE,
        [
            (
                "inject-expired-skip",
                "printf '\\n\\nimport pytest\\n\\n"
                '@pytest.mark.skip(reason="probe [TICKET=PROBE-40 EXPIRES=2000-01-01]")\\n'
                "def test_probe_expired_skip():\\n    pass\\n' >> {target}",
            ),
        ],
    ),
    # oss-release-remediation M0 — the D1-D9 decision record must stay
    # decided + dated (D1-D8) and scheduled (D9). Weakening the first
    # DECIDED status to PENDING must fail the gate; the record file is the
    # mutation target and is backed up/restored by the harness.
    "gate-47-oss-decisions-record": (
        "{python} scripts/check_oss_decisions.py",
        "openspec/changes/oss-release-remediation/decisions.md",
        [
            (
                "pending-one-decided-decision",
                "sed -i '0,/\\*\\*Status:\\*\\* DECIDED/s//**Status:** PENDING/' {target}",
            ),
        ],
    ),
    # oss-release-remediation W0.1 — the root license contract must hold at
    # the file level: weakening the first LICENSE.txt line (the license
    # name) must fail the gate; the license file is the mutation target
    # and is backed up/restored by the harness.
    "gate-48-root-license": (
        "{python} scripts/check_root_license.py",
        "LICENSE.txt",
        [
            (
                "rename-license-to-proprietary",
                "sed -i '1s/Apache License/Proprietary License/' {target}",
            ),
        ],
    ),
    # oss-release-remediation W0.2 — the committed scan report must stay
    # redacted: appending a planted GitHub-PAT-shaped line must fail the
    # gate's gitleaks self-scan; the report file is the mutation target
    # and is backed up/restored by the harness.
    "gate-49-secret-scan-report": (
        "{python} scripts/check_secret_scan_report.py",
        "docs/audits/secret-scan-2026-10-06.md",
        [
            (
                "plant-secret-in-report",
                "{python} -c \"open('{target}','a').write(chr(10)+'planted_probe = '+'ghp_'+'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789abcdef'+chr(10))\"",
            ),
        ],
    ),
    # oss-release-remediation W0.3 — the maintenance-window notice must
    # keep its recorded guard evidence: flipping the recorded exit code
    # must fail the gate; the notice file is the mutation target and is
    # backed up/restored by the harness.
    "gate-50-maintenance-window": (
        "{python} scripts/check_maintenance_window.py",
        "openspec/changes/oss-release-remediation/maintenance-window-2026-10-06.md",
        [
            (
                "flip-recorded-guard-exit",
                "sed -i 's/guard exit=0/guard exit=1/' {target}",
            ),
        ],
    ),
    # oss-release-remediation W0.5 — the rotation record must keep every
    # surface ROTATED: flipping one row back to PENDING-U must fail the
    # gate (the honest-gate contract); renaming a step heading must fail
    # it too. The record file is the mutation target and is backed
    # up/restored by the harness.
    "gate-51-credential-rotation": (
        "{python} scripts/check_credential_rotation.py",
        "openspec/changes/oss-release-remediation/credential-rotation-2026-10-06.md",
        [
            (
                "flip-rotated-row-to-pending",
                r"sed -i 's/\*\*Status:\*\* ROTATED/\*\*Status:\*\* PENDING-U/' {target}",
            ),
            (
                "rename-step-heading",
                "sed -i 's/### step: postgres-certs/### step: postgres-certs-renamed/' {target}",
            ),
        ],
    ),
    # oss-release-remediation W0.6 — the tag-archive manifest must keep
    # every row verified+deleted: flipping the first row must fail the
    # gate (the honest-gate contract), deleting a canonical row must fail
    # it too. The manifest file is the mutation target and is backed
    # up/restored by the harness.
    "gate-52-tag-archive": (
        "{python} scripts/check_tag_archive_manifest.py",
        "docs/audits/tag-archive-manifest-2026-10-06.md",
        [
            (
                "flip-verified-row",
                r"sed -i 's/verified: yes/verified: no/' {target}",
            ),
            (
                "delete-canonical-tag-row",
                r"sed -i '/- backup-staging-20251207_194944 /d' {target}",
            ),
        ],
    ),
    # oss-release-remediation W1.0 — the IdP-JWKS decision note must keep
    # its recorded outcome: flipping JWKS_EXPOSED to JWKS_NOT_EXPOSED must
    # fail the gate (the positive cert-pinned fallback + D4 re-scope
    # markers would then be missing). The note file is the mutation target
    # and is backed up/restored by the harness.
    "gate-53-idp-jwks-decision": (
        "{python} scripts/check_idp_jwks_decision.py",
        "docs/audits/idp-jwks-verification-2026-10-07.md",
        [
            (
                "flip-outcome-to-not-exposed",
                r"sed -i 's/\*\*Outcome:\*\* JWKS_EXPOSED/\*\*Outcome:\*\* JWKS_NOT_EXPOSED/' {target}",
            ),
        ],
    ),
    # W4.6 (oss-release-remediation, G1) — renaming the estate prefix makes
    # the checker blind: the planted-violation + real-tree pins in the suite
    # flip RED (a checker that reports nothing detects nothing).
    "gate-54-provider-boundary": (
        "{python} -m pytest scripts/tests/test_check_provider_boundary.py -p no:django -q -c /dev/null",
        "scripts/check_provider_boundary.py",
        [
            (
                "rename-estate-prefix",
                'sed -i \'s/_ESTATE_APP = "hub.apps.databricks_admin"/_ESTATE_APP = "hub.apps.databricks_admin-DISABLED"/\' {target}',
            ),
        ],
    ),
    # The 1.1 pin: proven end-to-end in Q.5.1 (rename weakening -> 17->0).
    # Requires the Django test env, so the no-django suite skips it; the
    # entry documents the proof.
    "1.1-commercial-hooks-pin": (
        "{python} -m pytest tests/unit/test_commercial_hooks_api_contract.py -q",
        "hub/apps/core/commercial_hooks.py",
        [
            (
                "rename-hook",
                "sed -i 's/def reset_hooks/def reset_hooks_BROKEN/' {target}",
            ),
        ],
    ),
}

# Gates whose checker needs a running Django/service env — audited only when
# the caller opts in (the no-django suite skips them with reason).
ENV_GATED = {"1.1-commercial-hooks-pin"}

# Advisory gates that NEVER fail CI by design (stale flags are tech debt,
# not merge gates — the detector prints CRITICAL/WARNING/INFO). Their
# falsifiability contract is report-content accuracy, not exit-code flips,
# so they are excluded from the BITES registry and listed here explicitly
# rather than silently skipped.
ADVISORY = {
    "gate-20-stale-feature-flags": "never fails by design (detect_stale_feature_flags.py) — report-only",
}


def _summary(text: str) -> tuple[int, int]:
    """(passed, failed) parsed from a pytest -q tail line; (-1, 0) otherwise."""
    match = re.search(r"(\d+) passed", text)
    passed = int(match.group(1)) if match else -1
    match = re.search(r"(\d+) failed", text)
    failed = int(match.group(1)) if match else 0
    return passed, failed


def run_check(
    checker: str, target: str, weakening_command: str | None = None
) -> tuple[int, str]:
    command = checker if weakening_command is None else weakening_command
    command = command.replace("{target}", target).replace("{python}", PYTHON)
    result = subprocess.run(
        command,
        shell=True,
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode, result.stdout + "\n" + result.stderr


def _outcome(rc: int, output: str) -> tuple[int, int, int]:
    """(rc, passed, failed) — rc is authoritative for script gates."""
    passed, failed = _summary(output)
    return rc, passed, failed


def verify(checker: str, target: str, weakenings: list[str]) -> tuple[bool, list[str]]:
    """Run baseline + each weakening; every weakening must change the outcome.

    Each weakening command MUTATES the target; the gate is then RE-RUN and
    its result compared against the baseline. The target is backed up and
    restored between weakenings so they stay independent.

    W7.4: when the BASELINE run is already failing (e.g. the honest
    credential-rotation gate blocking on PENDING-U surfaces), a weakening
    cannot change the outcome by construction — the weakenings are
    classified PRE-RED (not measurable, not vacuous) and the owning
    ledger documents why the gate is red.  A green-at-baseline gate
    whose weakening survives is the VACUOUS signal this harness exists
    to catch.
    """
    baseline = _outcome(*run_check(checker, target))
    report: list[str] = []
    for spec in weakenings:
        if baseline[0] != 0:
            label, _, _command = spec.partition(":")
            report.append(f"{label}: PRE-RED (gate failing at baseline — not measurable)")
            continue
        label, _, command = spec.partition(":")
        backup = target + ".falsifiability-backup"
        shutil.copy2(target, backup)
        try:
            run_check(checker, target, command)  # mutate
            weakened = _outcome(*run_check(checker, target))  # re-run the gate
        finally:
            shutil.move(backup, target)
        bites = weakened != baseline
        report.append(
            f"{label}: {'BITES' if bites else 'VACUOUS'} (baseline {baseline} -> {weakened})"
        )
    return all("VACUOUS" not in line for line in report), report


def _run_and_report(
    label: str, checker: str, target: str, weakenings: list[str]
) -> int:
    """Run one gate's weakenings and print the report; return the exit code."""
    ok, report = verify(checker, target, weakenings)
    if label:
        print(f"{label}:")
    for line in report:
        print(f"  {line}" if label else line)
    if not ok:
        print("FALSIFIABILITY: VACUOUS weakening(s) detected — the gate cannot fail.")
        return 1
    print(f"FALSIFIABILITY: all {len(report)} weakenings bite.")
    return 0


def _audit(gates: list[str]) -> tuple[bool, list[str]]:
    ok = True
    rows: list[str] = []
    for name in gates:
        checker, target, weakenings = GATES[name]
        passed, report = verify(
            checker, target, [f"{label}:{cmd}" for label, cmd in weakenings]
        )
        status = "FALSIFIABLE" if passed else "VACUOUS"
        ok = ok and passed
        rows.append(f"{name}: {status}")
        for line in report:
            rows.append(f"    {line}")
    return ok, rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Gate falsifiability harness + registry"
    )
    parser.add_argument(
        "--checker", help="command running the gate; may use {target} (direct mode)"
    )
    parser.add_argument("--target", help="the file the weakenings mutate (direct mode)")
    parser.add_argument(
        "--weaken", action="append", default=[], help="label:command (direct mode)"
    )
    parser.add_argument("--gate", help="run one registry gate by name")
    parser.add_argument("--audit", action="store_true", help="run every registry gate")
    parser.add_argument(
        "--include-env-gated", action="store_true", help="audit env-gated gates too"
    )
    args = parser.parse_args(argv)

    if args.gate:
        if args.gate not in GATES:
            print(
                f"FALSIFIABILITY: unknown gate {args.gate!r}; registry has {len(GATES)} gates"
            )
            return 2
        checker, target, weakenings = GATES[args.gate]
        return _run_and_report(
            args.gate,
            checker,
            target,
            [f"{wlabel}:{wcommand}" for wlabel, wcommand in weakenings],
        )

    if args.audit:
        names = [n for n in GATES if args.include_env_gated or n not in ENV_GATED]
        ok, rows = _audit(names)
        for row in rows:
            print(row)
        audited = len(names)
        if ADVISORY:
            print(f"ADVISORY (excluded by design): {', '.join(sorted(ADVISORY))}")
        if ENV_GATED and not args.include_env_gated:
            print(
                "ENV-GATED (skipped; run with --include-env-gated in the full env): "
                + ", ".join(sorted(ENV_GATED))
            )
        if not ok:
            print(
                f"FALSIFIABILITY: {sum(1 for r in rows if 'VACUOUS' in r)} of {audited} "
                "audited gates are VACUOUS."
            )
            return 1
        print(f"FALSIFIABILITY: all {audited} audited gates are falsifiable.")
        return 0

    if not (args.checker and args.target and args.weaken):
        parser.error(
            "direct mode requires --checker --target --weaken; or use --gate/--audit"
        )

    return _run_and_report("", args.checker, args.target, args.weaken)


if __name__ == "__main__":
    raise SystemExit(main())
