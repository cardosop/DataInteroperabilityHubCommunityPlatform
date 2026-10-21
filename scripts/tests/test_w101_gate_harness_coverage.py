"""W10.1 (oss-release-remediation) — falsifiability-harness COVERAGE pins
(convention 11: every new gate/pin must be registered + drill-proven).

These pins keep the harness's GATES registry HONEST (Django-free, CI
no-django lint):

* every gate/pin in the W10.1 registry below has a harness entry whose
  checker references the expected script or pin suite (the convention-11
  closure — a new W-lane gate without an entry flips this RED);
* every GATES checker in the harness references a script/pin that EXISTS
  on disk (dead checkers fail);
* every GATES target exists on disk (dead targets fail);
* every weakening is shaped ``label:command``.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import verify_gate_falsifiability as harness

# W10.1 registry — the W-lane gates/pins the harness MUST cover (the
# convention-11 closure; grows with every new W-lane gate).
W101_REGISTRY = {
    "gate-44-smoke-report": "scripts/check_smoke_report.py",
    "gate-45-pilot-scope": "scripts/check_pilot_scope.py",
    "gate-46-privacy-pack": "scripts/check_privacy_pack.py",
    "gate-55-shipped-tree-litter": "scripts/tests/test_check_shipped_tree_litter.py",
    "gate-56-fork-guards": "scripts/tests/test_check_fork_guards.py",
    "gate-w111-threat-model-veracity": "scripts/tests/test_w111_threat_model_veracity.py",
    "gate-w112-matrix-veracity": "scripts/tests/test_w112_matrix_veracity.py",
    "gate-w114-property-veracity": "scripts/tests/test_w114_property_suites_veracity.py",
    "gate-w116-leak-ban": "scripts/tests/test_w116_exc_str_leak_ban.py",
    "gate-w117-business-logic-veracity": "scripts/tests/test_w117_business_logic_matrix_veracity.py",
    "gate-w118-upload-veracity": "scripts/tests/test_w118_upload_abuse_veracity.py",
    "gate-w119-config-veracity": "scripts/tests/test_w119_api_configuration_veracity.py",
    "gate-w1112-ai-veracity": "scripts/tests/test_w1112_ai_threat_model_veracity.py",
    "gate-w1113-asvs-pack-veracity": "scripts/tests/test_w1113_asvs_evidence_pack_veracity.py",
    "gate-w104-gonogo-pack-veracity": "scripts/tests/test_w104_gonogo_pack_veracity.py",
    "gate-w105-deferred-debt-triage": "scripts/tests/test_w105_deferred_debt_triage.py",
}

_PY_REF = re.compile(r"((?:scripts|tests|hub)/[\w./-]+\.py)")


def _entry_checker_refs(entry: tuple) -> str:
    checker, target, _weakenings = entry
    return f"{checker} {target}"


def test_every_w101_registry_gate_has_a_harness_entry():
    missing = []
    for name, expected_ref in sorted(W101_REGISTRY.items()):
        entry = harness.GATES.get(name)
        if entry is None:
            missing.append(f"{name}: NO harness entry")
            continue
        checker_refs = _entry_checker_refs(entry)
        if expected_ref not in checker_refs:
            missing.append(f"{name}: checker must reference {expected_ref} (got {checker_refs!r})")
    assert not missing, "convention-11 closure violations:\n" + "\n".join(sorted(missing))


def test_every_gates_checker_references_an_existing_script_or_pin():
    broken = []
    for name, entry in sorted(harness.GATES.items()):
        checker, _target, _weakenings = entry
        refs = _PY_REF.findall(checker)
        if not refs:
            broken.append(f"{name}: checker references no python path ({checker!r})")
            continue
        for ref in refs:
            if not (REPO_ROOT / ref).is_file():
                broken.append(f"{name}: dead checker reference {ref}")
    assert not broken, "dead harness checkers:\n" + "\n".join(sorted(broken))


def test_every_gates_target_exists():
    broken = []
    for name, entry in sorted(harness.GATES.items()):
        _checker, target, _weakenings = entry
        if not (REPO_ROOT / target).is_file():
            broken.append(f"{name}: dead target {target}")
    assert not broken, "dead harness targets:\n" + "\n".join(sorted(broken))


def test_every_weakening_is_label_command_shaped():
    broken = []
    for name, entry in sorted(harness.GATES.items()):
        _checker, _target, weakenings = entry
        for spec in weakenings:
            if (
                not isinstance(spec, tuple)
                or len(spec) != 2
                or not spec[0].strip()
                or not spec[1].strip()
            ):
                broken.append(f"{name}: malformed weakening {spec!r}")
    assert not broken, "malformed harness weakenings:\n" + "\n".join(sorted(broken))
