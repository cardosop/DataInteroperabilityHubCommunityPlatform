"""W11.6 (oss-release-remediation) — the ``str(exc)``-leak ban pins
(ASVS V7, register row 11).

The runtime half lives in the app suites: the REST envelope never
surfaces ``str(exc)`` on 5xx (W1.16, ``test_error_response_contract.py``),
and the W11.6 graphql_ld pins
(``hub/apps/graphql_ld/tests/test_resolvers.py``) prove resolver
exception text, SQL fragments and credential shapes never reach the
client (the pre-fix ``"error": str(exc)`` / per-error
``str(e)`` verbatim echo was the register-row-11 class — root-fixed).

These pins are the SOURCE half: the client-facing envelope modules are
AST-proven free of exception-text interpolation, so a reintroduced
``str(exc)`` in an error response flips RED in the CI no-django job —
and the scanner is proven to bite against a planted violation.

Django-free — runs in the CI no-django lint job.
"""

from __future__ import annotations

import ast
import textwrap
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent

# Client-facing envelope modules: NO exception-text interpolation —
# EXCEPT the W1.16-verified conditional in api/exceptions.py where
# ``str(exc)`` feeds TYPED 4xx business messages only (the 5xx branch
# short-circuits BEFORE any str(exc) site — W10.3 round-3 re-audit
# hardened the pre-fix ordering), and the line-anchored deliberate
# keeps below.
ENVELOPE_MODULES = (
    REPO_ROOT / "hub" / "apps" / "api" / "exceptions.py",
    REPO_ROOT / "hub" / "apps" / "core" / "responses.py",
    REPO_ROOT / "hub" / "apps" / "graphql_ld" / "views.py",
    # W10.3 (round-3 re-audit) — the ban extended to the view modules
    # the independent pass found shipping str(exc) into 5xx/200
    # diagnostic envelopes (fixed at root; the allowlist holds the
    # deliberate typed-4xx/classification keeps only).
    REPO_ROOT / "hub" / "apps" / "semantic" / "views.py",
    REPO_ROOT / "hub" / "apps" / "semantic" / "views_ontology.py",
    REPO_ROOT / "hub" / "apps" / "warehouses" / "views.py",
    REPO_ROOT / "hub" / "apps" / "files" / "views.py",
)

# (module, line) sites where str(exc) is the DELIBERATE typed-4xx path —
# the pin below re-verifies the 5xx-guard line exists alongside them.
_ALLOWED_SITES = {
    # The 4xx-only message branches (the 5xx guard at line 165 runs
    # FIRST — the ordering pin below).
    REPO_ROOT / "hub" / "apps" / "api" / "exceptions.py": {194, 196},
    # files/views.py:659 — classification-only: the string is inspected
    # for "NoSuchUpload" to pick the 409 branch; never echoed.
    # files/views.py:924 — the W1.16 typed-4xx contract: a
    # FILE_FORMAT_MISMATCH 400 carries the TYPED business exception's
    # human-facing message (the exception has a .code), never arbitrary
    # exception text at 5xx.
    REPO_ROOT / "hub" / "apps" / "files" / "views.py": {659, 924},
}

_GUARD_LINE = "if http_status >= 500:"

_LOGGING_NAMES = {"logger", "log", "_logger", "logging"}


def _exc_str_sites(source: str) -> list[tuple[int, str]]:
    """Every ``str(exc)``/``str(e)`` call OUTSIDE logging statements."""
    tree = ast.parse(source)
    sites: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if not (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "str"
            and node.args
            and isinstance(node.args[0], ast.Name)
            and node.args[0].id in ("exc", "e")
        ):
            continue
        # Walk up the enclosing statement: if any ancestor Call targets
        # a logger, the site is server-side logging (allowed).
        if _inside_logging_call(tree, node):
            continue
        sites.append((node.lineno, node.args[0].id))
    return sites


def _inside_logging_call(tree: ast.AST, needle: ast.Call) -> bool:
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        for child in ast.walk(node):
            if child is needle:
                func = node.func
                name = getattr(func, "id", None) or getattr(func, "attr", None) or ""
                if name in _LOGGING_NAMES:
                    return True
                if isinstance(func, ast.Attribute):
                    base = getattr(func.value, "id", None) or ""
                    if base in _LOGGING_NAMES:
                        return True
    return False


def test_envelope_modules_carry_no_exception_text_interpolation():
    for path in ENVELOPE_MODULES:
        assert path.is_file(), f"envelope module missing: {path}"
        source = path.read_text(encoding="utf-8")
        sites = _exc_str_sites(source)
        allowed = _ALLOWED_SITES.get(path, set())
        offenders = [(line, var) for line, var in sites if line not in allowed]
        assert not offenders, (
            f"{path}: str(exc) interpolation in a client-facing module: "
            f"{offenders} — exceptions must be logged server-side, never "
            f"echoed (register row 11)"
        )


def test_the_typed_4xx_exception_is_the_only_allowlisted_use():
    """The api/exceptions.py allowlist holds ONLY the W1.16 conditional
    — and the 5xx guard must run BEFORE every str(exc) site (the W10.3
    round-3 re-audit fix: the pre-fix ordering let ``.message``-bearing
    repo exceptions bypass the 5xx redaction)."""
    path = REPO_ROOT / "hub" / "apps" / "api" / "exceptions.py"
    source = path.read_text(encoding="utf-8")
    assert _GUARD_LINE in source, (
        "the W1.16 5xx-guard line must exist in api/exceptions.py"
    )
    guard_line = next(
        index + 1
        for index, line in enumerate(source.splitlines())
        if line.strip() == _GUARD_LINE
    )
    sites = _exc_str_sites(source)
    assert {line for line, _var in sites} <= _ALLOWED_SITES[path], (
        "only the line-anchored typed-4xx sites may use str(exc) in "
        f"api/exceptions.py: got {sites}"
    )
    late = [line for line, _var in sites if line <= guard_line]
    assert not late, (
        f"str(exc) before the 5xx guard (line {guard_line}) reopens the "
        f"round-3 leak: sites at {late}"
    )


def test_scanner_bites_on_a_planted_violation(tmp_path):
    """The scanner must flag a planted ``"error": str(exc)`` response —
    a checker that reports nothing detects nothing."""
    planted = tmp_path / "planted_views.py"
    planted.write_text(
        textwrap.dedent(
            """
            def handle(request):
                try:
                    ...
                except Exception as exc:
                    return {"error": str(exc)}
            """
        ),
        encoding="utf-8",
    )
    sites = _exc_str_sites(planted.read_text(encoding="utf-8"))
    assert sites, "the planted str(exc) response must be flagged"
    assert any(var == "exc" for _line, var in sites)


def test_scanner_accepts_logging_only_usage(tmp_path):
    """Server-side logging of the exception is the ALLOWED pattern —
    the scanner must not flag it."""
    benign = tmp_path / "benign.py"
    benign.write_text(
        textwrap.dedent(
            """
            import logging
            logger = logging.getLogger(__name__)

            def handle(request):
                try:
                    ...
                except Exception as exc:
                    logger.error("failed: %s", exc, exc_info=True)
                    return {"error": {"code": "GENERIC"}}
            """
        ),
        encoding="utf-8",
    )
    assert _exc_str_sites(benign.read_text(encoding="utf-8")) == []


def test_pii_map_and_redaction_artifacts_exist():
    pii_map = REPO_ROOT / "docs" / "PII_DATA_MAP.md"
    redaction = (
        REPO_ROOT
        / "docs"
        / "audits"
        / "w116-pii-redaction-coverage-2026-10-16.md"
    )
    assert pii_map.is_file(), "docs/PII_DATA_MAP.md must be committed"
    assert redaction.is_file(), "the PII redaction-coverage audit must be committed"
    text = redaction.read_text(encoding="utf-8")
    for marker in ("email", "phone", "ssn", "credit_card", "ip_address"):
        assert marker in text, f"redaction audit missing {marker}"


def test_encryption_coverage_artifacts_exist():
    report = (
        REPO_ROOT
        / "docs"
        / "audits"
        / "w116-encryption-coverage-2026-10-16.md"
    )
    script = REPO_ROOT / "scripts" / "audit_encryption_coverage.py"
    assert report.is_file(), "the W11.6 encryption-coverage report must be committed"
    assert script.is_file(), "the encryption-coverage audit script must exist"
    text = report.read_text(encoding="utf-8")
    for marker in ("Fernet", "KMS", "encrypt_json_field", "sso_config"):
        assert marker in text, f"encryption report missing {marker}"
