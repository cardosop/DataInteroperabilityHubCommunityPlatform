"""W11.12 (oss-release-remediation) — AI-surface threat-model + red-team
veracity pins (register row 19).

These pins keep the W11.12 artifacts HONEST (Django-free, CI no-django
lint):

* the matrix doc exists with the required sections and every
  ``file.py::Class::test`` cell citation RESOLVES on disk (AST);
* the two suite files exist and carry the named cells;
* the design.md register row 19 carries the EXECUTED annotation citing
  the matrix;
* the fixes are LIVE in the source — the detector module, the delimiter
  + strict-validation client, the per-surface audit events, and the
  exception-echo-free ML predict responses (the pre-fix ``{e!s}``
  interpolations are GONE from ``hub/apps/ml/views.py``);
* the agent/tool-call absence is PROVEN at the source level — the
  non-test tree carries NO agentic-framework import or tool-call site
  (a future agent surface flips this RED and must ship with the
  boundary review);
* the STRIDE one-pager + ledger exist.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
MATRIX_DOC = (
    REPO_ROOT / "docs" / "security" / "adversarial-matrices" / "w1112-ai-prompt-injection-matrix.md"
)
STRIDE_DOC = REPO_ROOT / "docs" / "security" / "threat-models" / "stride-ai-surfaces-w11.md"
LEDGER = REPO_ROOT / "docs" / "audits" / "w1112-ai-surface-threat-model-2026-10-16.md"
AI_SUITE = REPO_ROOT / "hub" / "apps" / "ai" / "tests" / "test_w1112_prompt_injection_red_team.py"
ML_SUITE = REPO_ROOT / "hub" / "apps" / "ml" / "tests" / "test_w1112_ml_predict_boundaries.py"
DETECTOR = REPO_ROOT / "hub" / "apps" / "ai" / "prompt_injection.py"
LLM_CLIENT = REPO_ROOT / "hub" / "apps" / "ai" / "llm_client.py"
AI_VIEWS = REPO_ROOT / "hub" / "apps" / "ai" / "views.py"
ML_VIEWS = REPO_ROOT / "hub" / "apps" / "ml" / "views.py"
EVENT_TYPES = REPO_ROOT / "hub" / "apps" / "audit" / "event_types.py"
DESIGN = REPO_ROOT / "openspec" / "changes" / "oss-release-remediation" / "design.md"

_CITATION = re.compile(
    r"`([A-Za-z0-9_./-]+\.py)::([A-Za-z_][A-Za-z0-9_]*)(?:::([A-Za-z_][A-Za-z0-9_]*))?`"
)

_AGENT_IMPORT_ROOTS = {
    "langchain",
    "langgraph",
    "llama_index",
    "autogen",
    "crewai",
    "semantic_kernel",
    "mcp",
}
_TOOL_CALL_ATTRS = {"tool_call", "function_call", "tool_use", "create_tool", "run_tool"}
_EXCLUDED_PARTS = {"__pycache__", "migrations", "tests", "test_", ".venv", "venv", "site-packages"}


def _doc_text() -> str:
    assert MATRIX_DOC.is_file(), "the W11.12 matrix doc must be committed"
    return MATRIX_DOC.read_text(encoding="utf-8")


def _cited_tests(text: str) -> list[tuple[str, str, str | None]]:
    return [(m.group(1), m.group(2), m.group(3)) for m in _CITATION.finditer(text)]


def _resolve(citation: tuple[str, str, str | None]) -> str | None:
    path, cls, method = citation
    file = REPO_ROOT / path
    if not file.is_file():
        return f"missing file: {path}"
    try:
        tree = ast.parse(file.read_text(encoding="utf-8"))
    except (OSError, SyntaxError, UnicodeDecodeError) as exc:
        return f"unparseable {path}: {exc}"
    classes = {n.name: n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)}
    if cls not in classes:
        return f"class {cls} not in {path}"
    methods = {n.name for n in ast.walk(classes[cls]) if isinstance(n, ast.FunctionDef)}
    if method is not None and method not in methods:
        return f"method {cls}::{method} not in {path}"
    return None


def _non_test_python_files() -> list[Path]:
    files = []
    for root_name in ("hub", "services", "cli", "scripts"):
        root = REPO_ROOT / root_name
        if not root.is_dir():
            continue
        files.extend(
            path for path in sorted(root.rglob("*.py")) if not (_EXCLUDED_PARTS & set(path.parts))
        )
    return files


def test_matrix_doc_exists_with_required_sections():
    text = _doc_text()
    for section in (
        "**Change:**",
        "**Register rows closed:** 19",
        "LLM01",
        "## Root fixes shipped by this suite",
        "## OPEN-THREATS",
        "paid layer",
    ):
        assert section in text, f"matrix doc missing {section!r}"


def test_every_matrix_cell_citation_resolves():
    """Every ``file.py::Class::test`` cell citation must resolve — the file
    exists AND the named class/test is defined in it (AST)."""
    broken = [err for err in (_resolve(c) for c in _cited_tests(_doc_text())) if err]
    assert not broken, "dead matrix citations:\n" + "\n".join(sorted(broken))


def test_suite_files_exist_with_the_named_cells():
    assert AI_SUITE.is_file(), "the W11.12 AI red-team suite must be committed"
    ai_text = AI_SUITE.read_text(encoding="utf-8")
    for marker in (
        "test_instruction_override_payload_corpus_blocked",
        "test_injection_query_never_reaches_the_provider",
        "test_model_output_with_hallucinated_keys_is_normalized",
        "test_schema_matching_rejects_matches_outside_the_schemas",
        "test_nl_search_injection_query_fails_closed_with_audits",
        "test_oversized_schema_rejected",
    ):
        assert marker in ai_text, f"AI suite missing {marker}"

    assert ML_SUITE.is_file(), "the W11.12 ML boundary suite must be committed"
    ml_text = ML_SUITE.read_text(encoding="utf-8")
    for marker in (
        "test_odh_error_details_never_reach_the_client",
        "test_oversized_input_rejected",
        "test_prediction_success_emits_audit",
        "test_deployment_id_path_segment_validated",
    ):
        assert marker in ml_text, f"ML suite missing {marker}"


def test_register_row_19_annotated_and_cites_the_matrix():
    text = DESIGN.read_text(encoding="utf-8")
    row_match = re.search(r"^\| 19 \|.*$", text, flags=re.MULTILINE)
    assert row_match, "design.md register row 19 missing"
    row = row_match.group(0)
    assert "W11.12" in row, "row 19 must carry the W11.12 EXECUTED annotation"
    assert "w1112-ai-prompt-injection-matrix.md" in row, "row 19 must cite the matrix"


def test_prompt_injection_detector_lives_in_the_source():
    assert DETECTOR.is_file(), "hub/apps/ai/prompt_injection.py must be committed"
    source = DETECTOR.read_text(encoding="utf-8")
    assert "def detect_prompt_injection" in source
    assert "def detect_schema_injection" in source


def test_llm_client_carries_the_hardening():
    source = LLM_CLIENT.read_text(encoding="utf-8")
    for marker in (
        "def _extract_json_object",
        "def _validate_query_interpretation",
        "def _validate_schema_matching",
        "def _build_query_understanding_prompt",
        "detect_prompt_injection",
        "detect_schema_injection",
        "transport",
        "https://",
    ):
        assert marker in source, f"llm_client.py missing {marker!r}"
    # The delimiter close carries the per-call token — the prompt builder
    # must interpolate it, not use a static tag.
    assert re.search(r"</user_query_\{", source), "delimiter close must carry the token"


def test_ai_views_carry_the_audit_events():
    source = AI_VIEWS.read_text(encoding="utf-8")
    for event in (
        "AI_PROMPT_INJECTION_BLOCKED",
        "AI_NATURAL_LANGUAGE_SEARCH_PERFORMED",
        "AI_SCHEMA_MATCHING_PERFORMED",
    ):
        assert event in source, f"views.py missing {event}"


def test_ml_predict_responses_never_echo_exception_text():
    """The pre-fix ODH exception branches interpolated ``{e!s}`` into the
    response detail (connection strings, credentials, internal URLs — the
    W11.6 leak class). Every one is GONE from the live source."""
    source = ML_VIEWS.read_text(encoding="utf-8")
    assert "{e!s}" not in source, "ml/views.py still echoes exception text"
    assert "{e!r}" not in source, "ml/views.py still echoes exception text"
    assert "ML_PREDICTION_PERFORMED" in source


def test_audit_event_types_registered():
    source = EVENT_TYPES.read_text(encoding="utf-8")
    for event in (
        "AI_NATURAL_LANGUAGE_SEARCH_PERFORMED",
        "AI_SCHEMA_MATCHING_PERFORMED",
        "AI_PROMPT_INJECTION_BLOCKED",
        "ML_PREDICTION_PERFORMED",
    ):
        assert f'{event}: str = "{event}"' in source, f"event_types.py missing {event}"
        assert f'    "{event}",' in source, f"event_types.py __all__ missing {event}"


def test_no_agent_tool_call_code_in_the_non_test_tree():
    """The agent/tool-boundary review is an ABSENCE proof (the W11.8
    pattern): no agentic-framework import or tool-call site exists in
    non-test code — the AI surfaces are prompt-only, no excessive agency."""
    offenders: list[str] = []
    for path in _non_test_python_files():
        try:
            source = path.read_text(encoding="utf-8")
            tree = ast.parse(source)
        except (OSError, SyntaxError, UnicodeDecodeError):
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.split(".")[0] in _AGENT_IMPORT_ROOTS:
                        offenders.append(
                            f"{path.relative_to(REPO_ROOT)}:{node.lineno} import {alias.name}"
                        )
            elif isinstance(node, ast.ImportFrom):
                if node.module and node.module.split(".")[0] in _AGENT_IMPORT_ROOTS:
                    offenders.append(
                        f"{path.relative_to(REPO_ROOT)}:{node.lineno} from {node.module}"
                    )
            elif isinstance(node, ast.Call):
                func = node.func
                if isinstance(func, ast.Attribute) and func.attr in _TOOL_CALL_ATTRS:
                    offenders.append(f"{path.relative_to(REPO_ROOT)}:{node.lineno} .{func.attr}(")
    assert not offenders, "agent/tool-call sites found:\n" + "\n".join(sorted(offenders))


def test_threat_model_one_pager_and_ledger_exist():
    assert STRIDE_DOC.is_file(), "the W11.12 STRIDE one-pager must be committed"
    text = STRIDE_DOC.read_text(encoding="utf-8")
    for section in (
        "## Spoofing",
        "## Tampering",
        "## Repudiation",
        "## Information disclosure",
        "## Denial of service",
        "## Elevation of privilege",
        "## Open threats",
        "paid layer",
    ):
        assert section in text, f"STRIDE doc missing {section!r}"
    assert LEDGER.is_file(), "the W11.12 ledger must be committed"
