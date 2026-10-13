"""
Contract tests for scripts/check_idp_jwks_decision.py (oss-release-remediation
W1.0, GATE-53).

The signed decision note (docs/audits/idp-jwks-verification-2026-10-07.md)
is the W1.0 evidence: it records the pilot-IdP JWKS capability outcome,
the live verification evidence, the D4 consequence, and the sign-off.
The gate keeps the record honest:

- the outcome is exactly one of JWKS_EXPOSED / JWKS_NOT_EXPOSED;
- the D4 consequence MATCHES the outcome — JWKS_EXPOSED carries the
  ``**D4 proceeds on the JWKS-verification plan**`` +
  ``**No cert-pinned fallback**`` markers; JWKS_NOT_EXPOSED must carry
  the positive ``**Cert-pinned fallback:**`` + ``**D4 re-scope:**``
  markers (the fallback decision + re-scope record);
- the evidence names the live check tool, records HTTP 200 on BOTH
  legs (discovery + JWKS), and counts usable signing keys;
- the sign-off table carries the D + Meshant (U) rows;
- no placeholders.

Plus the Makefile wiring pin: GATE-53 runs in ``quality-gates`` after
the tag-archive gate.
"""

import importlib.util
import re
import sys
from pathlib import Path

import pytest

scripts_dir = Path(__file__).parent.parent
sys.path.insert(0, str(scripts_dir))

script_path = scripts_dir / "check_idp_jwks_decision.py"
spec = importlib.util.spec_from_file_location("check_idp_jwks_decision", script_path)
check_decision = importlib.util.module_from_spec(spec)
spec.loader.exec_module(check_decision)

ROOT = scripts_dir.parent
MAKEFILE = ROOT / "Makefile"

NOTE = """# IdP JWKS verification — W1.0 (S3, D4 precondition)

Verified **2026-10-07** as the M1 precondition recorded in tasks.md W1.0.

## Outcome

- **Outcome:** JWKS_EXPOSED
- **Reason:** the pilot IdP serves a fetchable JWKS with 3 keys, all
  RSA RS256 signature keys loadable by the verification stack.

## Live verification evidence

- **Check tool:** `scripts/check_idp_jwks.py` (live, real HTTPS) +
  the W16-gated live tests in `hub/apps/auth/tests/test_sso_idp_metadata.py`.
- **Discovery:** HTTP 200 at `https://<host>/oidc/.well-known/oauth-authorization-server`.
- **JWKS:** HTTP 200 at the `jwks_uri` — 3 keys, kty=RSA x3, all
  alg=RS256 use=sig, all loadable by PyJWK — 3 usable signing keys.
- **Key ids:** `646befd4…`, `jnRqFg`, `vBPZrA`.

## D4 consequence

- **D4 proceeds on the JWKS-verification plan** — W1.5 implements the
  OIDC callback with JWKS signature/aud/exp verification.
- **No cert-pinned fallback** — the fallback decision is not taken:
  the precondition (S3) is met.

## Sign-off

| Party | Role | Status | Date |
|---|---|---|---|
| D (engineering) | Capability check executed live | signed | 2026-10-07 |
| Meshant (U) | IdP JWKS capability + D4 path sign-off | signed | 2026-10-07 |
"""


@pytest.fixture
def note_file(tmp_path):
    path = tmp_path / "idp-jwks-verification-2026-10-07.md"
    path.write_text(NOTE)
    return path


def _run(note):
    return check_decision.check(note)


def test_valid_note_passes(note_file):
    assert _run(note_file) == []


def test_missing_note_fails(tmp_path):
    problems = _run(tmp_path / "idp-jwks-verification-2026-10-07.md")
    assert any("missing" in p for p in problems)


@pytest.mark.parametrize(
    "section",
    [
        "## Outcome",
        "## Live verification evidence",
        "## D4 consequence",
        "## Sign-off",
    ],
)
def test_missing_section_fails(note_file, section):
    note_file.write_text(NOTE.replace(section, "## Other"))
    problems = _run(note_file)
    assert any(section in p for p in problems)


def test_unknown_outcome_fails(note_file):
    note_file.write_text(NOTE.replace("JWKS_EXPOSED", "JWKS_MAYBE"))
    problems = _run(note_file)
    assert any("JWKS_MAYBE" in p for p in problems)


def test_flipped_outcome_fails_without_the_fallback_record(note_file):
    # JWKS_NOT_EXPOSED demands the positive fallback + re-scope markers;
    # the EXPOSED note carries only the negations.
    note_file.write_text(NOTE.replace("JWKS_EXPOSED", "JWKS_NOT_EXPOSED"))
    problems = _run(note_file)
    assert any("Cert-pinned fallback" in p for p in problems)
    assert any("D4 re-scope" in p for p in problems)


def test_exposed_note_must_keep_the_plan_markers(note_file):
    note_file.write_text(
        NOTE.replace("**D4 proceeds on the JWKS-verification plan**", "**D4 proceeds**")
    )
    problems = _run(note_file)
    assert any("D4 proceeds on the JWKS-verification plan" in p for p in problems)


def test_exposed_note_must_keep_the_no_fallback_marker(note_file):
    note_file.write_text(
        NOTE.replace("**No cert-pinned fallback**", "**Fallback maybe**")
    )
    problems = _run(note_file)
    assert any("No cert-pinned fallback" in p for p in problems)


def test_not_exposed_note_with_the_markers_passes(note_file):
    text = NOTE.replace("JWKS_EXPOSED", "JWKS_NOT_EXPOSED")
    text = text.replace(
        "**D4 proceeds on the JWKS-verification plan**",
        "**Cert-pinned fallback:** the pilot IdP cannot verify OIDC "
        "signatures via JWKS — W1.5 pins certificates instead.",
    )
    text = text.replace(
        "**No cert-pinned fallback**",
        "**D4 re-scope:** W1.5 is re-scoped to cert-pinned validation; "
        "the adversarial test matrix changes accordingly.",
    )
    note_file.write_text(text)
    assert _run(note_file) == []


def test_evidence_must_name_the_check_tool(note_file):
    note_file.write_text(
        NOTE.replace("scripts/check_idp_jwks.py", "some/other/script.py")
    )
    problems = _run(note_file)
    assert any("scripts/check_idp_jwks.py" in p for p in problems)


def test_evidence_must_record_http_200_on_both_legs(note_file):
    note_file.write_text(NOTE.replace("**JWKS:** HTTP 200", "**JWKS:** HTTP 404"))
    problems = _run(note_file)
    assert any("HTTP 200" in p for p in problems)


def test_evidence_must_count_usable_signing_keys(note_file):
    note_file.write_text(
        NOTE.replace("3 usable signing keys", "zero usable signing keys")
    )
    problems = _run(note_file)
    assert any("usable signing key" in p for p in problems)


def test_signoff_must_carry_both_parties(note_file):
    note_file.write_text(NOTE.replace("| Meshant (U) |", "| Someone else |"))
    problems = _run(note_file)
    assert any("Meshant (U)" in p for p in problems)


def test_placeholder_fails(note_file):
    note_file.write_text(NOTE.replace("3 keys", "TODO"))
    problems = _run(note_file)
    assert any("TODO" in p for p in problems)


def test_default_path_exists():
    assert (ROOT / "docs/audits/idp-jwks-verification-2026-10-07.md").exists()


class TestMainContract:
    def test_problems_exit_1(self, note_file, monkeypatch):
        note_file.write_text(NOTE.replace("JWKS_EXPOSED", "JWKS_MAYBE"))
        monkeypatch.setattr(
            sys, "argv", ["check_idp_jwks_decision.py", "--note", str(note_file)]
        )
        with pytest.raises(SystemExit) as exc_info:
            check_decision.main()
        assert exc_info.value.code == 1

    def test_clean_exits_0(self, note_file, monkeypatch):
        monkeypatch.setattr(
            sys, "argv", ["check_idp_jwks_decision.py", "--note", str(note_file)]
        )
        with pytest.raises(SystemExit) as exc_info:
            check_decision.main()
        assert exc_info.value.code == 0


def _quality_gates_recipe() -> list[str]:
    text = MAKEFILE.read_text()
    match = re.search(r"^quality-gates:.*\n((?:\t.*\n)+)", text, re.MULTILINE)
    assert match, "quality-gates target not found in Makefile"
    return list(match.group(1).splitlines())


class TestQualityGatesWiring:
    def test_gate53_wired_into_quality_gates(self):
        recipe = _quality_gates_recipe()
        joined = "\n".join(recipe)
        assert (
            "check_idp_jwks_decision.py" in joined
        ), "GATE-53 must run in quality-gates"

    def test_gate53_runs_after_the_tag_archive_gate(self):
        recipe = _quality_gates_recipe()
        gate52 = next(
            i for i, ln in enumerate(recipe) if "check_tag_archive_manifest.py" in ln
        )
        gate53 = next(
            i for i, ln in enumerate(recipe) if "check_idp_jwks_decision.py" in ln
        )
        assert gate52 < gate53, "the IdP JWKS decision gate runs after GATE-52"
