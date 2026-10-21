"""W11.13 (oss-release-remediation) — ASVS evidence-pack veracity pins.

These pins keep the ASVS V1-V14 evidence pack HONEST (Django-free, CI
no-django lint):

* the pack exists under ``docs/audits/asvs-2026/`` with ALL fourteen
  chapter sections (V1-V14);
* the ACCEPTANCE CRITERION is enforced here — every chapter declares
  **Level 2 or higher** (a Level-1 declaration flips the pin RED);
* every ``file.py::Class::test`` citation resolves on disk (AST — the
  file, class and test must all exist);
* every ``file.py:NNN`` line citation resolves — the file exists and the
  line is real, and for test files the line must sit INSIDE a ``def
  test_*`` body (no citing fixtures/comments as coverage);
* every non-test artifact citation (docs/reports/configs) resolves on
  disk;
* every chapter carries ≥3 citations (a prose-only chapter is not
  evidence — the pack's own anti-tautology rule);
* the pack's evidence chain is closed by the W11.x veracity pins (the
  pack cites the pins that verify the matrices it leans on);
* the openspec tasks.md W11.13 checkbox is marked with the pack cited.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
PACK_DIR = REPO_ROOT / "docs" / "audits" / "asvs-2026"
PACK_MASTER = PACK_DIR / "asvs-evidence-pack.md"
TASKS = REPO_ROOT / "openspec" / "changes" / "oss-release-remediation" / "tasks.md"

_CHAPTER_RE = re.compile(r"^## V(\d+) — .+$", re.MULTILINE)
_LEVEL_RE = re.compile(r"\*\*Declared level: Level ([123])\*\*")
_TEST_CITE = re.compile(
    r"`([A-Za-z0-9_./-]+\.py)::([A-Za-z_][A-Za-z0-9_]*)(?:::([A-Za-z_][A-Za-z0-9_]*))?`"
)
_LINE_CITE = re.compile(r"`([A-Za-z0-9_./-]+\.(?:py|conf|yaml|yml|sh|cjs)):(\d+)`")
_ARTIFACT_CITE = re.compile(r"`([A-Za-z0-9_./-]+\.(?:md|yaml|yml|json|cjs|ts|sh|conf|txt|tsx))`")

_CHAPTER_NAMES = {
    1: "Architecture, Design and Threat Modeling",
    2: "Authentication",
    3: "Session Management",
    4: "Access Control",
    5: "Validation, Sanitization and Encoding",
    6: "Stored Cryptography",
    7: "Error Handling and Logging",
    8: "Data Protection",
    9: "Communications",
    10: "Malicious Code",
    11: "Business Logic",
    12: "Files and Resources",
    13: "API and Web Service",
    14: "Configuration",
}


def _pack_text() -> str:
    assert PACK_MASTER.is_file(), "the ASVS evidence pack must be committed"
    return PACK_MASTER.read_text(encoding="utf-8")


def _chapter_sections(text: str) -> dict[int, str]:
    """Split the pack into per-chapter sections by their `## Vn —` heads
    (the heading line itself is part of the section, so the chapter-name
    check sees the canonical ASVS title)."""
    matches = list(_CHAPTER_RE.finditer(text))
    sections: dict[int, str] = {}
    for index, match in enumerate(matches):
        number = int(match.group(1))
        start = match.start()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        sections[number] = text[start:end]
    return sections


def _resolve_test_citation(citation: tuple[str, str, str | None]) -> str | None:
    path, cls, method = citation
    # ``re.findall`` yields '' (not None) for unmatched optional groups.
    method = method or None
    file = REPO_ROOT / path
    if not file.is_file():
        return f"missing file: {path}"
    try:
        tree = ast.parse(file.read_text(encoding="utf-8"))
    except (OSError, SyntaxError, UnicodeDecodeError) as exc:
        return f"unparseable {path}: {exc}"
    classes = {n.name: n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)}
    if cls in classes:
        methods = {n.name for n in ast.walk(classes[cls]) if isinstance(n, ast.FunctionDef)}
        if method is not None and method not in methods:
            return f"method {cls}::{method} not in {path}"
        return None
    # ``file.py::test_name`` — a module-level test function.
    funcs = {n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
    if method is None and cls in funcs:
        return None
    return f"class/function {cls} not in {path}"


def _test_function_ranges(file: Path, tree: ast.AST) -> list[tuple[int, int]]:
    ranges = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name.startswith("test"):
            ranges.append((node.lineno, node.end_lineno or node.lineno))
    return ranges


def _resolve_line_citation(path: str, lineno: int) -> str | None:
    file = REPO_ROOT / path
    if not file.is_file():
        return f"missing file: {path}"
    lines = file.read_text(encoding="utf-8").splitlines()
    if not (1 <= lineno <= len(lines)):
        return f"line {lineno} out of range for {path} ({len(lines)} lines)"
    if "/tests/" in path or path.endswith("_test.py") or "test_" in Path(path).name:
        try:
            tree = ast.parse(file.read_text(encoding="utf-8"))
        except (OSError, SyntaxError, UnicodeDecodeError) as exc:
            return f"unparseable {path}: {exc}"
        ranges = _test_function_ranges(file, tree)
        if not any(start <= lineno <= end for start, end in ranges):
            return f"line {lineno} in {path} is not inside a test function"
    return None


def test_pack_exists_with_all_fourteen_chapters():
    text = _pack_text()
    sections = _chapter_sections(text)
    missing = [n for n in range(1, 15) if n not in sections]
    assert not missing, f"pack missing chapters: V{missing}"
    assert len(sections) == 14, f"expected exactly 14 chapters, got {len(sections)}"
    for number, name in _CHAPTER_NAMES.items():
        assert name in sections[number], f"V{number} section missing its ASVS name"


def test_every_chapter_declares_at_least_level_two():
    """The acceptance criterion: every category ≥ Level 2."""
    text = _pack_text()
    sections = _chapter_sections(text)
    for number, section in sections.items():
        levels = [int(m.group(1)) for m in _LEVEL_RE.finditer(section)]
        assert levels, f"V{number} declares no level"
        assert all(level >= 2 for level in levels), f"V{number} declares a below-L2 level: {levels}"


def test_every_chapter_carries_at_least_three_citations():
    """A prose-only chapter is not evidence (the pack's own
    anti-tautology rule)."""
    text = _pack_text()
    sections = _chapter_sections(text)
    for number, section in sections.items():
        cited = (
            len(_TEST_CITE.findall(section))
            + len(_LINE_CITE.findall(section))
            + len(_ARTIFACT_CITE.findall(section))
        )
        assert cited >= 3, f"V{number} carries only {cited} citation(s) — prose-only"


def test_every_test_citation_resolves():
    text = _pack_text()
    broken = [err for err in (_resolve_test_citation(c) for c in _TEST_CITE.findall(text)) if err]
    assert not broken, "dead pack test citations:\n" + "\n".join(sorted(broken))


def test_every_line_citation_resolves():
    text = _pack_text()
    broken = [
        err
        for err in (_resolve_line_citation(p, int(n)) for p, n in _LINE_CITE.findall(text))
        if err
    ]
    assert not broken, "dead pack line citations:\n" + "\n".join(sorted(broken))


def test_every_artifact_citation_resolves():
    text = _pack_text()
    broken = sorted(
        {path for path in _ARTIFACT_CITE.findall(text) if not (REPO_ROOT / path).is_file()}
    )
    assert not broken, "dead pack artifact citations:\n" + "\n".join(broken)


def test_pack_cites_the_w11_veracity_pins():
    """The pack's evidence chain is itself pinned: it must cite the
    veracity pins that verify the matrices/ledgers it leans on (the pack
    can never out-claim its sources)."""
    text = _pack_text()
    for pin in (
        "scripts/tests/test_w111_threat_model_veracity.py",
        "scripts/tests/test_w112_matrix_veracity.py",
        "scripts/tests/test_w113_idor_matrix_veracity.py",
        "scripts/tests/test_w114_property_suites_veracity.py",
        "scripts/tests/test_w115_crypto_random_sweep.py",
        "scripts/tests/test_w116_exc_str_leak_ban.py",
        "scripts/tests/test_w117_business_logic_matrix_veracity.py",
        "scripts/tests/test_w118_upload_abuse_veracity.py",
        "scripts/tests/test_w119_api_configuration_veracity.py",
        "scripts/tests/test_w1110_security_tooling_gates.py",
        "scripts/tests/test_w1112_ai_threat_model_veracity.py",
    ):
        assert pin in text, f"pack must cite its veracity pin: {pin}"


def test_tasks_w1113_checked_with_evidence():
    tasks = TASKS.read_text(encoding="utf-8")
    match = re.search(r"^- \[([ x])\] W11\.13 .*$", tasks, re.MULTILINE)
    assert match, "tasks.md W11.13 line missing"
    assert match.group(1) == "x", "tasks.md W11.13 must be checked"
    assert "docs/audits/asvs-2026/" in tasks, "tasks.md evidence must cite the pack dir"
