"""W10.4 (oss-release-remediation) — U.8 go/no-go ledger + evidence-pack
veracity pins.

These pins keep the M5 go/no-go record HONEST (Django-free, CI no-django
lint):

* the go/no-go ledger exists and records the GO decision (``confirmed =
  yes``) with a decision date and the evidence-pack citation (the gate is
  the machine half of the decision; the ledger is the human half);
* the ledger carries one row per DoD §6 item (dod-1..dod-9), each
  ``confirmed = yes`` with an ISO date and a non-empty evidence cell;
* every release-execution condition row carries an owner + reason (the
  stop-the-line contract — no unrecorded condition is silently dropped);
* the evidence pack exists with one section per DoD item;
* every citation in BOTH files resolves on disk — test citations
  (``file.py::Class::test`` / module-level ``file.py::test`` via AST),
  line citations (``file.py:NNN``, inside a real test function for test
  files), and artifact citations (docs/reports/configs);
* every DoD section carries ≥3 citations (a prose-only section is not
  evidence — the pack's own anti-tautology rule);
* the pack's evidence chain is closed: it cites the W11.13 ASVS pack and
  its veracity pin (the go/no-go pack can never out-claim the ASVS
  pack), the W10.1 harness-coverage pin and the W10.2 soak ledger (the
  M0-M5 evidence pack), and the W10.3 independent re-audit record;
* every ledger condition key appears in the pack (the pack is the reason
  record the stop-the-line points at);
* tasks.md W10.3/W10.4 are checked with their records cited.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
LEDGER = REPO_ROOT / "docs" / "operations" / "oss-go-nogo-ledger.md"
PACK = REPO_ROOT / "docs" / "audits" / "w104-gonogo-evidence-pack-2026-10-17.md"
W103_REVIEW = REPO_ROOT / "docs" / "audits" / "w103-independent-reaudit-2026-10-17.md"
TASKS = REPO_ROOT / "openspec" / "changes" / "oss-release-remediation" / "tasks.md"

_DOD_RE = re.compile(r"^## DoD (\d+) — .+$", re.MULTILINE)
_TEST_CITE = re.compile(
    r"`([A-Za-z0-9_./-]+\.py)::([A-Za-z_][A-Za-z0-9_]*)(?:::([A-Za-z_][A-Za-z0-9_]*))?`"
)
_LINE_CITE = re.compile(r"`([A-Za-z0-9_./-]+\.(?:py|conf|yaml|yml|sh|cjs)):(\d+)`")
_ARTIFACT_CITE = re.compile(r"`([A-Za-z0-9_./-]+\.(?:md|yaml|yml|json|cjs|ts|sh|conf|txt|tsx))`")
_ISO_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")


def _text(path: Path) -> str:
    assert path.is_file(), f"expected committed artifact: {path}"
    return path.read_text(encoding="utf-8")


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


def _test_function_ranges(tree: ast.AST) -> list[tuple[int, int]]:
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
        ranges = _test_function_ranges(tree)
        if not any(start <= lineno <= end for start, end in ranges):
            return f"line {lineno} in {path} is not inside a test function"
    return None


def _artifact_error(path: str) -> str | None:
    if not (REPO_ROOT / path).is_file():
        return f"missing artifact: {path}"
    return None


def _all_citation_errors(files: list[Path]) -> list[str]:
    errors: list[str] = []
    for file in files:
        text = _text(file)
        for err in (_resolve_test_citation(c) for c in _TEST_CITE.findall(text)):
            if err:
                errors.append(f"{file.name}: {err}")
        for err in (_resolve_line_citation(p, int(n)) for p, n in _LINE_CITE.findall(text)):
            if err:
                errors.append(f"{file.name}: {err}")
        for err in (_artifact_error(p) for p in _ARTIFACT_CITE.findall(text)):
            if err:
                errors.append(f"{file.name}: {err}")
    return errors


def _ledger_rows() -> dict[int, list[str]]:
    rows: dict[int, list[str]] = {}
    for line in _text(LEDGER).splitlines():
        match = re.match(r"^\|\s*dod-(\d+)\s*\|(.*)\|\s*$", line)
        if match:
            rows[int(match.group(1))] = [cell.strip() for cell in match.group(2).split("|")]
    return rows


def _pack_sections() -> dict[int, str]:
    text = _text(PACK)
    matches = list(_DOD_RE.finditer(text))
    sections: dict[int, str] = {}
    for index, match in enumerate(matches):
        number = int(match.group(1))
        start = match.start()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        sections[number] = text[start:end]
    return sections


def test_ledger_exists_and_records_the_go_decision():
    text = _text(LEDGER)
    assert "`confirmed = yes`" in text, "ledger must record `confirmed = yes`"
    decision = re.search(r"\*\*Decision date:\*\* (\d{4}-\d{2}-\d{2})", text)
    assert decision, "ledger must record an ISO decision date"
    assert "docs/audits/w104-gonogo-evidence-pack-2026-10-17.md" in text, (
        "ledger must cite its evidence pack"
    )


def test_ledger_carries_one_confirmed_row_per_do_d_item():
    rows = _ledger_rows()
    missing = [n for n in range(1, 10) if n not in rows]
    assert not missing, f"ledger missing DoD rows: {missing}"
    for number, cells in rows.items():
        # cells: criterion | owner | confirmed | date | evidence
        assert len(cells) >= 5, f"dod-{number} row malformed: {cells}"
        assert cells[2] == "yes", f"dod-{number} must be confirmed = yes (got {cells[2]!r})"
        assert _ISO_DATE.fullmatch(cells[3]), f"dod-{number} date not ISO: {cells[3]!r}"
        assert cells[4], f"dod-{number} evidence cell must not be empty"


def test_ledger_condition_rows_carry_owner_and_reason():
    """The stop-the-line contract: any condition the go decision depends
    on is recorded with an owner — nothing silently dropped."""
    text = _text(LEDGER)
    conditions = re.search(
        r"## Release-execution conditions.*?(?=^## |\Z)", text, re.DOTALL | re.MULTILINE
    )
    assert conditions, "ledger must carry a release-execution conditions section"
    table = [line for line in conditions.group(0).splitlines() if line.strip().startswith("|")]
    assert len(table) >= 2, "conditions section must carry a header + ≥1 row"
    body_rows = [[c.strip() for c in row.split("|")[1:-1]] for row in table[1:] if "---" not in row]
    assert body_rows, "conditions section must carry at least one condition row"
    for row in body_rows:
        assert len(row) >= 4, f"condition row malformed: {row}"
        assert row[2], f"condition row owner must not be empty: {row[0]!r}"
        assert row[3], f"condition row reason/evidence must not be empty: {row[0]!r}"


def test_every_condition_key_appears_in_the_pack():
    """Cross-file agreement: every ledger condition has its reason
    recorded in the pack (the pack is the stop-the-line reason record)."""
    text = _text(LEDGER)
    conditions = re.search(
        r"## Release-execution conditions.*?(?=^## |\Z)", text, re.DOTALL | re.MULTILINE
    )
    pack_text = _text(PACK)
    missing = []
    if conditions:
        for row in conditions.group(0).splitlines():
            match = re.match(r"^\|\s*([a-z0-9-]+)\s*\|", row)
            if match and match.group(1) not in ("key",) and match.group(1) not in pack_text:
                missing.append(match.group(1))
    assert not missing, f"conditions without pack reasons: {missing}"


def test_pack_exists_with_all_nine_do_d_sections():
    sections = _pack_sections()
    missing = [n for n in range(1, 10) if n not in sections]
    assert not missing, f"pack missing DoD sections: {missing}"
    assert len(sections) == 9, f"expected exactly 9 DoD sections, got {len(sections)}"


def test_each_do_d_section_carries_evidence():
    """A prose-only section is not evidence (the pack's own
    anti-tautology rule)."""
    sections = _pack_sections()
    for number, section in sections.items():
        cited = (
            len(_TEST_CITE.findall(section))
            + len(_LINE_CITE.findall(section))
            + len(_ARTIFACT_CITE.findall(section))
        )
        assert cited >= 3, f"DoD {number} carries only {cited} citation(s) — prose-only"


def test_every_citation_in_pack_and_ledger_resolves():
    errors = _all_citation_errors([PACK, LEDGER])
    assert not errors, "dead go/no-go citations:\n" + "\n".join(sorted(set(errors)))


def test_pack_cites_the_asvs_pack_and_its_veracity_pin():
    """The evidence-chain closure: the go/no-go pack can never out-claim
    the ASVS pack it leans on for DoD 8."""
    text = _text(PACK)
    assert "docs/audits/asvs-2026/asvs-evidence-pack.md" in text, (
        "pack must cite the W11.13 ASVS evidence pack"
    )
    assert "scripts/tests/test_w1113_asvs_evidence_pack_veracity.py" in text, (
        "pack must cite the ASVS pack's veracity pin"
    )


def test_pack_cites_the_m0_m5_evidence_ledgers():
    text = _text(PACK)
    for citation in (
        "scripts/tests/test_w101_gate_harness_coverage.py",
        "docs/audits/w102-staging-soak-2026-10-17.md",
        "docs/audits/w103-independent-reaudit-2026-10-17.md",
    ):
        assert citation in text, f"pack must cite its M0-M5 evidence: {citation}"


def test_w103_review_record_exists():
    _text(W103_REVIEW)


def test_tasks_w104_checked_with_evidence():
    tasks = TASKS.read_text(encoding="utf-8")
    match = re.search(r"^- \[([ x])\] W10\.4 .*$", tasks, re.MULTILINE)
    assert match, "tasks.md W10.4 line missing"
    assert match.group(1) == "x", "tasks.md W10.4 must be checked"
    assert "docs/audits/w104-gonogo-evidence-pack-2026-10-17.md" in tasks, (
        "tasks.md W10.4 evidence must cite the pack"
    )
    assert "docs/operations/oss-go-nogo-ledger.md" in tasks, (
        "tasks.md W10.4 evidence must cite the ledger"
    )


def test_tasks_w103_checked_with_review_evidence():
    tasks = TASKS.read_text(encoding="utf-8")
    match = re.search(r"^- \[([ x])\] W10\.3 .*$", tasks, re.MULTILINE)
    assert match, "tasks.md W10.3 line missing"
    assert match.group(1) == "x", "tasks.md W10.3 must be checked"
    assert "docs/audits/w103-independent-reaudit-2026-10-17.md" in tasks, (
        "tasks.md W10.3 evidence must cite the independent re-audit record"
    )
