"""W11.9 (oss-release-remediation) — API & configuration matrix veracity
pins (ASVS V13/V14, register rows 12/13).

The matrix (``docs/security/adversarial-matrices/
w119-api-configuration-matrix.md``) claims ONE named test per
rate-limit surface and per configuration guard.  These pins keep it
HONEST: every ``file.py::Class::name`` citation resolves (file +
AST-defined test), the new suites exist and carry the named cells,
and the design register rows 12/13 cite the matrix.  Django-free for
the CI no-django lint job.
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
    / "w119-api-configuration-matrix.md"
)
DESIGN_DOC = (
    REPO_ROOT
    / "openspec"
    / "changes"
    / "oss-release-remediation"
    / "design.md"
)
MATRIX_SUITE = (
    REPO_ROOT / "hub" / "apps" / "auth" / "tests" / "test_w119_rate_limit_matrix.py"
)
CONFIG_SUITE = REPO_ROOT / "tests" / "security" / "test_w119_configuration_guards.py"

_CITATION = re.compile(
    r"`([A-Za-z0-9_./-]+\.py)::([A-Za-z_][A-Za-z0-9_]*)(?:::([A-Za-z_][A-Za-z0-9_]*))?`"
)

MATRIX_SECTIONS = (
    "## Matrix 1 — Rate-limit matrix",
    "## Matrix 2 — Default-secure configuration assertions",
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
            names = {
                node.name: node
                for node in ast.walk(tree)
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
            }
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
    assert MATRIX_DOC.is_file(), "the W11.9 matrix doc must be committed"


def test_both_matrix_sections_present():
    text = _doc_text()
    for heading in MATRIX_SECTIONS:
        assert heading in text, f"missing matrix section {heading!r}"


def test_every_cell_citation_resolves():
    text = _doc_text()
    broken = [err for err in (_resolve(c) for c in _cited_tests(text)) if err]
    assert not broken, "dead matrix citations:\n" + "\n".join(sorted(broken))


def test_the_new_suites_exist_and_are_cited():
    assert MATRIX_SUITE.is_file(), "the rate-limit matrix suite must be committed"
    assert CONFIG_SUITE.is_file(), "the configuration-guards suite must be committed"
    text = _doc_text()
    assert "test_w119_rate_limit_matrix.py" in text
    assert "test_w119_configuration_guards.py" in text


def test_root_fixes_and_open_threats_recorded():
    text = _doc_text()
    assert "## Root fixes shipped" in text
    assert "## OPEN-THREATS" in text


def test_design_register_rows_12_and_13_cite_the_matrix():
    assert DESIGN_DOC.is_file(), "design.md must exist"
    text = DESIGN_DOC.read_text(encoding="utf-8")
    row12 = re.search(r"^\| 12 \|.*$", text, re.M)
    row13 = re.search(r"^\| 13 \|.*$", text, re.M)
    assert row12 is not None, "register row 12 must exist in design.md"
    assert row13 is not None, "register row 13 must exist in design.md"
    tail = text[row12.start() : row13.end()]
    assert "w119-api-configuration-matrix.md" in tail, (
        "the matrix doc must be cited between register rows 12 and 13"
    )
