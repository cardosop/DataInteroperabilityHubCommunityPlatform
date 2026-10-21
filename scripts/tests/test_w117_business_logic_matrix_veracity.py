"""W11.7 (oss-release-remediation) — business-logic matrix veracity pins.

The adversarial matrix (``docs/security/adversarial-matrices/
w117-business-logic-matrix.md``) claims ONE named test per cell across
the transition matrices (orders, payments, runs, ARs), the money-path
double-charge/refund/replay cells and the metering idempotency drill.
These pins keep the matrix HONEST: every ``file.py::Class::name`` /
``file.py::name`` citation must resolve (file on disk + test defined,
AST-verified, Django-free for the CI no-django lint job).

RED phase: a wrong citation (the W11.2 lesson — wrong class names and
the ``(?:::...)`` separator) flips the pin; the doc is corrected from
the pin's output until every cell resolves.
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
    / "w117-business-logic-matrix.md"
)
DESIGN_DOC = (
    REPO_ROOT
    / "openspec"
    / "changes"
    / "oss-release-remediation"
    / "design.md"
)
RACE_SUITE = (
    REPO_ROOT / "hub" / "apps" / "marketplace" / "tests" / "test_w117_refund_race.py"
)
AR_SUITE = (
    REPO_ROOT / "hub" / "apps" / "governance" / "tests" / "test_w117_ar_transition_matrix.py"
)

# file.py::Class::name  or  file.py::name  (two colons between Class and name)
_CITATION = re.compile(
    r"`([A-Za-z0-9_./-]+\.py)::([A-Za-z_][A-Za-z0-9_]*)(?:::([A-Za-z_][A-Za-z0-9_]*))?`"
)

MATRIX_SECTIONS = (
    "## Matrix 1 — State-machine transition matrices",
    "## Matrix 2 — Money path",
    "## Matrix 3 — Metering idempotency drill",
)


def _doc_text() -> str:
    return MATRIX_DOC.read_text(encoding="utf-8")


def _cited_tests(text: str) -> list[tuple[Path, str | None, str]]:
    out = []
    for match in _CITATION.finditer(text):
        file_rel, first, second = match.group(1), match.group(2), match.group(3)
        if second is None:
            out.append((Path(file_rel), None, first))
        else:
            out.append((Path(file_rel), first, second))
    return out


def _defined_names(tree: ast.AST) -> dict[str, ast.AST]:
    return {
        node.name: node
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
    }


def _resolve(citation: tuple[Path, str | None, str]) -> str | None:
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
    assert MATRIX_DOC.is_file(), "the W11.7 business-logic matrix doc must be committed"


def test_all_three_matrix_sections_present():
    text = _doc_text()
    for heading in MATRIX_SECTIONS:
        assert heading in text, f"missing matrix section {heading!r}"


def test_every_cell_citation_resolves():
    text = _doc_text()
    broken = [err for err in (_resolve(c) for c in _cited_tests(text)) if err]
    assert not broken, "dead matrix citations:\n" + "\n".join(sorted(broken))


def test_matrices_carry_a_named_test_per_cell():
    text = _doc_text()
    citations = _cited_tests(text)
    assert len(citations) >= 30, (
        f"expected ≥30 cell citations across the three matrices, got {len(citations)}"
    )


def test_the_new_w117_suites_are_cited():
    assert RACE_SUITE.is_file(), "the refund-race suite must be committed"
    assert AR_SUITE.is_file(), "the AR transition-matrix suite must be committed"
    text = _doc_text()
    assert "test_w117_refund_race.py" in text
    assert "test_w117_ar_transition_matrix.py" in text


def test_root_causes_and_open_threats_recorded():
    text = _doc_text()
    assert "## Root fixes shipped" in text, "the RED-found root fixes must be recorded"
    assert "## OPEN-THREATS" in text, "unfixed gaps must be recorded as open"


def test_design_register_rows_10_and_16_cite_the_matrix():
    """Rows 10 (TOCTOU) and 16 (race conditions) are the rows this
    matrix closes — the design doc must cite it from both."""
    assert DESIGN_DOC.is_file(), "design.md must exist"
    text = DESIGN_DOC.read_text(encoding="utf-8")
    row10 = re.search(r"^\| 10 \|.*$", text, re.M)
    row16 = re.search(r"^\| 16 \|.*$", text, re.M)
    assert row10 is not None, "register row 10 must exist in design.md"
    assert row16 is not None, "register row 16 must exist in design.md"
    tail = text[row10.start() : row16.end()]
    assert "w117-business-logic-matrix.md" in tail, (
        "the matrix doc must be cited between register rows 10 and 16"
    )
