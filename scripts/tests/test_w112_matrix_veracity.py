"""W11.2 (oss-release-remediation) — ASVS V2/V3 matrix veracity pins.

The adversarial matrix (``docs/security/adversarial-matrices/
w112-auth-session-matrix.md``) claims ONE named test per cell across the
three matrices (SSO forged-token, JWT lifecycle, API-key scope x endpoint
x role).  These pins keep the matrix HONEST (the P4 rule, applied to the
ASVS evidence): every ``file.py::Class::name`` / ``file.py::name`` cell
citation must resolve — the file on disk AND the test defined in it
(AST-verified, no imports, Django-free so the CI no-django lint job can
run it).  A renamed or deleted test flips RED.

RED phase: before the doc existed, the existence pins failed
(FileNotFoundError); after the doc shipped, every citation is resolved
mechanically against the real tree.

The register rows the matrix closes (design.md §1.1 rows 6 and 8) must
cite this doc — the matrix is the verification artifact for both rows.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
MATRIX_DOC = (
    REPO_ROOT
    / "docs"
    / "security"
    / "adversarial-matrices"
    / "w112-auth-session-matrix.md"
)
DESIGN_DOC = (
    REPO_ROOT
    / "openspec"
    / "changes"
    / "oss-release-remediation"
    / "design.md"
)
NEW_SUITE = (
    REPO_ROOT / "hub" / "apps" / "auth" / "tests" / "test_w112_asvs_auth_adversarial.py"
)

# file.py::Class::name  or  file.py::name
# NOTE: the separator between Class and name is TWO colons — the regex
# needs `(?:::...)` (non-capturing marker `?:` + two literal colons).
_CITATION = re.compile(
    r"`([A-Za-z0-9_./-]+\.py)::([A-Za-z_][A-Za-z0-9_]*)(?:::([A-Za-z_][A-Za-z0-9_]*))?`"
)

# Backticked repo-relative file paths (non-test artifact citations).
_FILE_CITATION = re.compile(
    r"`([A-Za-z0-9_./-]+\.(?:py|ts|tsx|cjs|mjs|js|json|yml|yaml|sh|md))(?::\d+)?`"
)

MATRIX_SECTIONS = (
    "## Matrix 1 — SSO forged-token",
    "## Matrix 2 — JWT lifecycle",
    "## Matrix 3 — API-key",
)


def _doc_text() -> str:
    return MATRIX_DOC.read_text(encoding="utf-8")


def _cited_tests(text: str) -> list[tuple[Path, str | None, str]]:
    """Yield (file, class_name|None, test_name) per citation."""
    out = []
    for match in _CITATION.finditer(text):
        file_rel, class_name, test_name = match.group(1), match.group(2), match.group(3)
        if test_name is None:
            # file.py::test_name form
            out.append((Path(file_rel), None, class_name))
        else:
            out.append((Path(file_rel), class_name, test_name))
    return out


def _defined_names(tree: ast.AST) -> dict[str, ast.AST]:
    names: dict[str, ast.AST] = {}
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names[node.name] = node
    return names


def _resolve(citation: tuple[Path, str | None, str]) -> str | None:
    """Return an error message when the citation does not resolve."""
    file_rel, class_name, test_name = citation
    path = REPO_ROOT / file_rel
    error: str | None
    if not path.is_file():
        error = f"{file_rel}: cited file does not exist"
    else:
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError as exc:
            error = f"{file_rel}: cannot parse ({exc})"
        else:
            names = _defined_names(tree)
            if class_name is None:
                resolved = test_name in names and isinstance(
                    names[test_name], (ast.FunctionDef, ast.AsyncFunctionDef)
                )
                error = None if resolved else f"{file_rel}: no module-level test named {test_name!r}"
            else:
                klass = names.get(class_name)
                if klass is None or not isinstance(klass, ast.ClassDef):
                    error = f"{file_rel}: no class named {class_name!r}"
                else:
                    resolved = any(
                        isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                        and node.name == test_name
                        for node in klass.body
                    )
                    error = (
                        None
                        if resolved
                        else f"{file_rel}: {class_name} has no test named {test_name!r}"
                    )
    return error


def test_matrix_doc_exists():
    assert MATRIX_DOC.is_file(), "the W11.2 adversarial matrix doc must be committed"


def test_all_three_matrix_sections_present():
    text = _doc_text()
    for heading in MATRIX_SECTIONS:
        assert heading in text, f"missing matrix section {heading!r}"


def test_every_cell_citation_resolves():
    """Every ``file.py::Class::name`` cell citation must resolve — the
    file exists AND the named test is defined in it (AST)."""
    text = _doc_text()
    broken = [err for err in (_resolve(c) for c in _cited_tests(text)) if err]
    assert not broken, "dead matrix citations:\n" + "\n".join(sorted(broken))


def test_matrices_carry_a_named_test_per_cell():
    """The three matrices must actually cite tests (not just prose rows)."""
    text = _doc_text()
    citations = _cited_tests(text)
    assert len(citations) >= 40, (
        f"expected ≥40 cell citations across the three matrices, got {len(citations)}"
    )
    files = {str(c[0]) for c in citations}
    assert str(Path("hub/apps/auth/tests/test_w112_asvs_auth_adversarial.py")) in files, (
        "the new W11.2 suite must be cited by the matrix"
    )


def test_new_suite_exists_and_is_cited():
    assert NEW_SUITE.is_file(), "the W11.2 adversarial suite must be committed"
    text = _doc_text()
    assert "test_w112_asvs_auth_adversarial.py" in text


def test_root_causes_section_and_open_threats_recorded():
    text = _doc_text()
    assert "## Root causes fixed" in text, "the RED-found root fixes must be recorded"
    assert "## OPEN-THREATS" in text, (
        "unfixed residual gaps must be recorded as open, not claimed fixed"
    )


def test_every_backticked_artifact_citation_exists():
    """Non-test backticked path citations (source files, docs) must
    resolve on disk — a dead citation is a lying matrix."""
    text = _doc_text()
    dead: list[str] = []
    for match in _FILE_CITATION.finditer(text):
        rel = match.group(1)
        if rel.endswith(".py") and "::" in match.group(0):
            # test citations are verified by test_every_cell_citation_resolves
            continue
        if not (REPO_ROOT / rel).is_file():
            dead.append(rel)
    assert not dead, "dead artifact citations:\n" + "\n".join(sorted(dead))


def test_design_register_rows_6_and_8_cite_the_matrix_doc():
    """Register rows 6 (broken auth) and 8 (scopes as decoration) are the
    rows this matrix closes — the design doc must cite it from both."""
    assert DESIGN_DOC.is_file(), "design.md must exist"
    text = DESIGN_DOC.read_text(encoding="utf-8")
    doc_rel = "docs/security/adversarial-matrices/w112-auth-session-matrix.md"
    assert doc_rel in text, f"design.md must cite {doc_rel}"
    # The citation must sit in/near the register rows (find their lines).
    row6 = re.search(r"^\| 6 \|.*$", text, re.M)
    row8 = re.search(r"^\| 8 \|.*$", text, re.M)
    assert row6 is not None, "register row 6 must exist in design.md"
    assert row8 is not None, "register row 8 must exist in design.md"
    tail = text[row6.start() : row8.end()]
    assert doc_rel in tail, "the matrix doc must be cited between register rows 6 and 8"
