"""W11.1 (oss-release-remediation) — STRIDE threat-model veracity pins.

The refresh ships ONE STRIDE one-pager per changed surface — auth/tenant
(W1), money (W2), pipeline (W3), event bus (W4), frontend identity (W5).
These pins keep the pages HONEST (the P4 rule, applied to threat models):

  * all five pages exist and each names its surface;
  * each page carries all six STRIDE categories (Spoofing, Tampering,
    Repudiation, Information disclosure, Denial of service, Elevation
    of privilege);
  * every cited mitigation artifact (test file / gate script / source
    file) exists on disk — a dead citation flips RED;
  * the refresh ledger (the claim→verification table, G10/W12.8
    convention) exists and lists the five pages.

RED phase: before the pages shipped, the existence pins failed
(collection-level FileNotFoundError); after, the citation scan verifies
every artifact claim mechanically — no mocks, the real tree.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
TM_DIR = REPO_ROOT / "docs" / "security" / "threat-models"
LEDGER = REPO_ROOT / "docs" / "audits" / "w111-threat-model-refresh-2026-10-15.md"

PAGES = {
    "auth-tenant": TM_DIR / "stride-auth-tenant-w1.md",
    "money": TM_DIR / "stride-money-w2.md",
    "pipeline": TM_DIR / "stride-pipeline-w3.md",
    "event-bus": TM_DIR / "stride-event-bus-w4.md",
    "frontend-identity": TM_DIR / "stride-frontend-identity-w5.md",
}

# The surface name each page must carry (as written in its title/scope).
SURFACE_MARKERS = {
    "auth-tenant": ("auth/tenant", "Auth & Tenant"),
    "money": ("Money Path",),
    "pipeline": ("Pipeline Spine",),
    "event-bus": ("Event Bus",),
    "frontend-identity": ("Frontend Identity",),
}

STRIDE_HEADINGS = (
    "Spoofing",
    "Tampering",
    "Repudiation",
    "Information disclosure",
    "Denial of service",
    "Elevation of privilege",
)

# Backticked tokens that look like repo-relative file paths.
_FILE_CITATION = re.compile(r"`([A-Za-z0-9_./-]+\.(?:py|ts|tsx|cjs|mjs|js|json|yml|yaml|sh|md))(?::\d+)?`")


def _page_texts():
    return {name: path.read_text(encoding="utf-8") for name, path in PAGES.items()}


def test_all_five_stride_pages_exist():
    missing = [str(p) for p in PAGES.values() if not p.is_file()]
    assert not missing, f"missing STRIDE pages: {missing}"


def test_each_page_names_its_surface():
    texts = _page_texts()
    for name, text in texts.items():
        markers = SURFACE_MARKERS[name]
        assert any(m.lower() in text.lower() for m in markers), (
            f"{name}: the page must name its surface ({markers})"
        )


def test_each_page_covers_all_six_stride_categories():
    texts = _page_texts()
    for name, text in texts.items():
        for heading in STRIDE_HEADINGS:
            assert heading.lower() in text.lower(), (
                f"{name}: missing STRIDE category {heading!r}"
            )


def test_every_cited_artifact_exists():
    """Every backticked file-path citation must resolve on disk — a
    dead citation is a lying threat model."""
    texts = _page_texts()
    dead: list[str] = []
    for name, text in texts.items():
        for match in _FILE_CITATION.finditer(text):
            rel = match.group(1)
            if not (REPO_ROOT / rel).is_file():
                dead.append(f"{name}: {rel}")
    assert not dead, "dead threat-model citations:\n" + "\n".join(sorted(dead))


def test_each_page_cites_at_least_one_test_or_gate_per_stride_category():
    """A mitigation with no pin is prose, not a fix: every STRIDE
    category section must cite at least one test/gate artifact."""
    texts = _page_texts()
    for name, text in texts.items():
        sections = re.split(r"\n#{2,4} ", text)
        for heading in STRIDE_HEADINGS:
            section = next(
                (s for s in sections if s.lower().startswith(heading.lower())),
                None,
            )
            assert section is not None, f"{name}: no section for {heading}"
            cited = _FILE_CITATION.findall(section)
            testish = [c for c in cited if re.search(r"test|check_|spec|gate", c, re.I)]
            assert testish, (
                f"{name}/{heading}: the section cites no test/gate artifact"
            )


def test_refresh_ledger_exists_and_lists_the_pages():
    assert LEDGER.is_file(), "the W11.1 claim→verification ledger must be committed"
    text = LEDGER.read_text(encoding="utf-8")
    for name in PAGES:
        assert name in text, f"ledger missing the {name} page row"


def test_no_page_cites_itself_as_evidence():
    """The pages document CODE fixes — a page citing only docs is prose."""
    texts = _page_texts()
    for name, text in texts.items():
        cited = _FILE_CITATION.findall(text)
        codeish = [
            c
            for c in cited
            if not c.endswith(".md") or "test" in c or "check" in c
        ]
        assert codeish, f"{name}: no code artifact cited anywhere"
