"""P0-12 (close-oss-release-conditions, L-1/H-6/G14) — decision-package pins.

The P0-12 deliverables are decision INPUTS, not decisions: the
dual-license review bundle for L (with the G14 trademark/scope review),
the D9 pentest scope/RFP options for U at W11.14, and the SECURITY.md
refresh draft. The pins enforce the package contract:

1. each deliverable exists at its canonical path with its required
   sections (U and L can review what the task promises — no silent
   half-packages);
2. the G14 review actually covers the npm scope AND the branding, with
   keep/rename options + rationale (a bundle that omits the
   keep/rename analysis is a placeholder);
3. the D9 package carries ≥2 scope options AND ≥2 provider models plus
   a recommendation — and does NOT flip the decision itself: decisions.md
   D9 must stay SCHEDULED at W11.14 (GATE-47 also enforces this; the pin
   here guards the package boundary, the gate guards the record);
4. the SECURITY refresh draft contains the private-advisories, CVE and
   support-matrix content named in H-6 and merges cleanly;
5. the pin file is CI-wired (the house self-wiring pin).

No mocks: real files, real content, the real CI wiring.
"""

from __future__ import annotations

import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
REPO_ROOT = SCRIPTS.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from envpolicy import skip_or_fail

BUNDLE = REPO_ROOT / "docs/strategy/DUAL_LICENSE_REVIEW_BUNDLE.md"
PENTEST = REPO_ROOT / "docs/strategy/PENTEST_SCOPE_RFP_OPTIONS.md"
SEC_DRAFT = REPO_ROOT / "docs/strategy/SECURITY_REFRESH_DRAFT.md"
DECISIONS = REPO_ROOT / "openspec/changes/oss-release-remediation/decisions.md"
LINT_YML = REPO_ROOT / ".github/workflows/_reusable.lint.yml"


def _read(path: Path) -> str:
    if not path.is_file():
        skip_or_fail(f"{path} does not exist")
    return path.read_text(encoding="utf-8")


def _assert_all(text: str, anchors: list[str], label: str) -> None:
    missing = [a for a in anchors if a not in text]
    assert not missing, f"{label}: missing required anchors {missing}"


# ── 1. Dual-license review bundle (L-1 + G14) ────────────────────────────────


def test_dual_license_bundle_exists_with_required_sections():
    text = _read(BUNDLE)
    _assert_all(
        text,
        [
            "Apache-2.0",
            "MIT",
            "NOTICE",
            "DCO",
            "trademark",
            "Recommendation",
            "Open questions",
            "L-1",
            "decisions.md",
        ],
        "DUAL_LICENSE_REVIEW_BUNDLE.md",
    )


def test_g14_review_covers_npm_scope_and_branding_with_options():
    text = _read(BUNDLE)
    _assert_all(
        text,
        [
            "@meshant",
            "interoperability-sdk",
            "Meshant branding",
            "Keep",
            "Rename",
        ],
        "G14 trademark review",
    )
    # The review must reach a recommendation with rationale (not just list).
    assert "rationale" in text.lower()
    # the npm-scope amendment decision (D3) is referenced
    assert "D3" in text


# ── 2. D9 pentest scope/RFP options (H-6, decision point W11.14) ─────────────


def test_pentest_options_exist_with_scope_and_provider_options():
    text = _read(PENTEST)
    _assert_all(
        text,
        [
            "W11.14",
            "D9",
            "Scope option",
            "Provider option",
            "Recommendation",
            "RFP",
            "retest",
            "ASVS",
        ],
        "PENTEST_SCOPE_RFP_OPTIONS.md",
    )
    assert text.count("Scope option") >= 2, "at least two scope options required"
    assert text.count("Provider option") >= 2, "at least two provider models required"


def test_d9_stays_scheduled_for_w11_14():
    text = _read(DECISIONS)
    section = text.split("## D9")[1].split("## ")[0] if "## D9" in text else ""
    assert "SCHEDULED — decision point W11.14" in section, (
        "D9 must stay SCHEDULED — the package is options, not the decision"
    )
    assert "W11.14" in section


# ── 3. SECURITY.md refresh draft (H-6) ───────────────────────────────────────


def test_security_refresh_draft_has_ghsa_cve_support():
    text = _read(SEC_DRAFT)
    _assert_all(
        text,
        [
            "Private advisories",
            "CVE process",
            "support-matrix",
            "COMMUNITY_ENTERPRISE_MATRIX.md",
            "Merge",
            "SECURITY.md",
        ],
        "SECURITY_REFRESH_DRAFT.md",
    )


# ── 4. CI wiring ─────────────────────────────────────────────────────────────


def test_p12_pins_ci_wired():
    text = _read(LINT_YML)
    assert (
        "scripts/tests/test_p12_decision_packages.py" in text
    ), "P0-12 pins must be wired into the CI lint list (_reusable.lint.yml)"
