#!/usr/bin/env python3
"""GATE-40 — skip/placeholder debt owns a ticket and an expiry (Phase T.5 / W17).

Scaffold debt must never silently re-activate: every ``skip``/``fixme``/
``xfail`` REASON carries ``TICKET=<id> EXPIRES=<YYYY-MM-DD>``, and every
placeholder-bodied test carries the same tokens in a leading comment.
The gate fails on EXPIRED annotated sites (always — even under baseline)
and on NET-GROWTH of unannotated sites per bucket (ratchet, same shape as
GATE-35/39).

Annotation format
-----------------
    TICKET=<id> EXPIRES=<YYYY-MM-DD>
inside the reason string, e.g.
    @pytest.mark.skip(reason="legacy SDK path [TICKET=PREPRO01-105, EXPIRES=2026-12-31]")
    test.skip(true, 'journey not implemented [TICKET=PREPRO01-105, EXPIRES=2026-12-31]');
Placeholder bodies annotate as the first comment inside the body:
    def test_x():
        # TICKET=PREPRO01-105 EXPIRES=2026-12-31 — real E2E pending backend
    it('does things', () => {
      // TICKET=PREPRO01-105 EXPIRES=2026-12-31 — real E2E pending backend
    });
The EXPIRES date is inclusive: a site expires the day AFTER its date.

What the gate scans
-------------------
* Python (roots: hub, tests, cli/tests, sdk/python, services; files
  ``test_*.py``/``*_test.py``): ``@pytest.mark.skip`` /
  ``@pytest.mark.skipif`` / ``@pytest.mark.xfail`` decorators and
  ``pytest.skip(...)``/``pytest.xfail(...)`` call sites. DYNAMIC markers
  added at collection time (the W16 ``auto_skip_unreachable_api`` hook)
  are not static debt — the environment policy governs them, this gate
  does not double-count them.
* TypeScript (roots: frontend/e2e, frontend/src, sdk/js/src; files
  ``*.spec.ts``/``*.test.ts``/``*.test.tsx``): ``test.skip(``/
  ``test.fixme(``/``describe.skip(`` sites (paren-depth scanner, the
  T.3 string-literal limitation documented there applies here too).
* Placeholders: Python test functions whose body (after docstring) holds
  only comments/``pass``/``...``; TS ``it``/``test`` blocks whose body is
  comment-only, or whose assertions are ALL export-existence stubs
  (``expect(typeof x).toBe('function')`` / ``toBeDefined()`` /
  ``toMatch(/^use/)`` naming checks — the Phase-105 hook-test class).
  These count as debt even when annotated (owned debt, not deliverables).

Buckets (ratcheted, per-bucket growth fails)
--------------------------------------------
``python_skip_sites``, ``python_skipif_sites``, ``ts_skip_sites``,
``python_placeholder_tests``, ``ts_placeholder_tests``. Annotated sites do
not grow the bucket — annotating debt is always safe and encouraged.

Baseline: ``scripts/skip_expiry_baseline.json`` (``--update`` after a fix
wave). Exit codes: 0 clean, 1 expired-or-growth, 2 usage/baseline error.
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from datetime import UTC, date, datetime
from pathlib import Path

DEFAULT_BASELINE = Path(__file__).resolve().parent / "skip_expiry_baseline.json"
DEFAULT_PY_ROOTS = ["hub", "tests", "cli/tests", "sdk/python", "services"]
DEFAULT_TS_ROOTS = ["frontend/e2e", "frontend/src", "sdk/js/src"]
_SKIP_DIRS = {
    "migrations",
    "__pycache__",
    "node_modules",
    "venv",
    ".venv",
    "site-packages",
    "dist",
    "build",
    ".git",
}

ANNOTATION_RE = re.compile(r"TICKET=([^\s,\]\}\)]+)\s+EXPIRES=(\d{4}-\d{2}-\d{2})")
TICKET_RE = re.compile(r"TICKET=([^\s,\]\}\)]+)")
EXPIRES_RE = re.compile(r"EXPIRES=(\d{4}-\d{2}-\d{2})")

_BUCKETS = [
    "python_skip_sites",
    "python_skipif_sites",
    "ts_skip_sites",
    "python_placeholder_tests",
    "ts_placeholder_tests",
]


class _Site:
    __slots__ = ("file", "line", "reason")

    def __init__(self, file: str, line: int, reason: str):
        self.file = file
        self.line = line
        self.reason = reason

    def annotation(self) -> tuple[str, date] | None:
        m = ANNOTATION_RE.search(self.reason or "")
        if m is None:
            return None
        ticket, expiry = m.group(1), m.group(2)
        try:
            return ticket, datetime.strptime(expiry, "%Y-%m-%d").date()
        except ValueError:
            return None


def _annotated(site: _Site) -> bool:
    return site.annotation() is not None


# ── Python extraction ────────────────────────────────────────────────────────


def _string_arg_value(node: ast.AST) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr) and _CURRENT_SOURCE:
        return ast.get_source_segment(_CURRENT_SOURCE[-1], node) or ""
    return None


# Source of the file currently being parsed (module-level holder so the
# AST-visitor helpers above can read it without threading state; list
# contents are mutated in place so no `global` statement is needed).
_CURRENT_SOURCE: list[str] = []


def _decorator_sites(tree: ast.AST, file: str) -> tuple[list[_Site], list[_Site]]:
    """Return (skip_sites, skipif_sites) from decorators."""
    skips: list[_Site] = []
    skipifs: list[_Site] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        for dec in node.decorator_list:
            target = dec
            if isinstance(dec, ast.Call):
                target = dec.func
            # Resolve pytest.mark.skip / skipif / xfail / bare pytest.skip
            if not isinstance(target, ast.Attribute) or target.attr not in {
                "skip",
                "skipif",
                "xfail",
            }:
                continue
            is_pytest = (
                isinstance(target.value, ast.Attribute)
                and target.value.attr == "mark"
                and isinstance(target.value.value, ast.Name)
                and target.value.value.id == "pytest"
            ) or (isinstance(target.value, ast.Name) and target.value.id == "pytest")
            if not is_pytest:
                continue
            reason = ""
            if isinstance(dec, ast.Call):
                for kw in dec.keywords:
                    if kw.arg == "reason":
                        reason = _string_arg_value(kw.value) or ""
                if not reason and target.attr == "skipif" and len(dec.args) > 1:
                    reason = _string_arg_value(dec.args[1]) or ""
                if not reason and dec.args:
                    reason = _string_arg_value(dec.args[0]) or ""
            site = _Site(file, node.lineno, reason)
            (skipifs if target.attr == "skipif" else skips).append(site)
    return skips, skipifs


def _is_guard_contract_skip(tree: ast.AST, node: ast.AST) -> bool:
    """True when a pytest.skip site is env-gated by the SANCTIONED guard
    contract instead of being skip/placeholder debt (W7.4):

    * an enclosing ``try`` whose handlers cover BOTH absence forms
      (RuntimeError, ModuleNotFoundError — the core/paid guard pattern
      from docs/test-infrastructure/guard-contract.md), or
    * an enclosing ``if`` testing ``is_core_only()`` / ``HUB_CORE_ONLY`` /
      ``apps.is_installed(...)`` with the skip inside that branch.

    These skips are permanent env-gating — they never expire and carry no
    TICKET/EXPIRES by design (the W16 carve-out principle: the governing
    policy is the guard contract + GATE-29, not the debt gate).
    """
    parents: dict[ast.AST, ast.AST] = {}
    for parent in ast.walk(tree):
        for child in ast.iter_child_nodes(parent):
            parents[child] = parent
    child = node
    while True:
        parent = parents.get(child)
        if parent is None:
            return False
        if isinstance(parent, ast.Try):
            covered = set()
            for handler in parent.handlers:
                if handler.type is None:
                    covered.update({"RuntimeError", "ModuleNotFoundError"})
                    continue
                names = handler.type.elts if isinstance(handler.type, ast.Tuple) else [handler.type]
                for n in names:
                    if isinstance(n, ast.Name) and n.id in ("Exception", "BaseException", "ImportError"):
                        if n.id in ("Exception", "BaseException"):
                            covered.update({"RuntimeError", "ModuleNotFoundError"})
                        else:
                            covered.add("ModuleNotFoundError")
                    elif isinstance(n, ast.Name) and n.id in ("RuntimeError", "ModuleNotFoundError"):
                        covered.add(n.id)
            if {"RuntimeError", "ModuleNotFoundError"} <= covered:
                return True
        if isinstance(parent, ast.If):
            test_text = ast.unparse(parent.test) if hasattr(ast, "unparse") else ""
            # The skip must be in the guarded branch's body (not a
            # sibling or the else-of-a-core-branch).
            if (
                "is_core_only" in test_text
                or "HUB_CORE_ONLY" in test_text
                or "is_installed" in test_text
            ) and any(c is child for c in parent.body):
                return True
        child = parent


def _call_sites(tree: ast.AST, file: str) -> list[_Site]:
    """pytest.skip(...) / pytest.xfail(...) call sites."""
    sites: list[_Site] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if not (
            isinstance(node.func, ast.Attribute)
            and node.func.attr in {"skip", "xfail"}
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "pytest"
        ):
            continue
        if _is_guard_contract_skip(tree, node):
            continue
        reason = ""
        if node.args:
            reason = _string_arg_value(node.args[0]) or ""
        sites.append(_Site(file, node.lineno, reason))
    return sites


def _function_body_comments(source_lines: list[str], node) -> str:
    """Raw comment text between a function's first and last line."""
    end = getattr(node, "end_lineno", node.lineno)
    return "\n".join(source_lines[node.lineno - 1 : end])


def _iter_test_defs(tree: ast.AST):
    """Test-shaped defs at module level and directly inside test classes.

    Nested helpers (a ``def test_handler`` inside another test's body) are
    NOT tests — including them would mis-count local fixtures as
    placeholders.
    """
    for stmt in tree.body:
        if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
            yield stmt
        elif isinstance(stmt, ast.ClassDef):
            for cstmt in stmt.body:
                if isinstance(cstmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    yield cstmt


def _python_placeholders(tree: ast.AST, source: str, file: str) -> list[_Site]:
    """Test functions whose body holds only docstring/pass/.../comments."""
    places: list[_Site] = []
    lines = source.splitlines()
    for node in _iter_test_defs(tree):
        if not node.name.startswith("test"):
            continue
        body = list(node.body)
        if (
            body
            and isinstance(body[0], ast.Expr)
            and isinstance(body[0].value, ast.Constant)
            and isinstance(body[0].value.value, str)
        ):
            body = body[1:]
        real = [
            stmt
            for stmt in body
            if not (
                isinstance(stmt, ast.Pass)
                or (
                    isinstance(stmt, ast.Expr)
                    and isinstance(stmt.value, ast.Constant)
                    and stmt.value.value is Ellipsis
                )
            )
        ]
        if real:
            continue
        comment_text = _function_body_comments(lines, node)
        places.append(_Site(file, node.lineno, comment_text))
    return places


def scan_python_file(path: Path) -> tuple[list[_Site], list[_Site], list[_Site]]:
    """Return (skip_sites, skipif_sites, placeholders) for one test file."""
    try:
        source = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return [], [], []
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return [], [], []
    _CURRENT_SOURCE.append(source)
    try:
        skips, skipifs = _decorator_sites(tree, str(path))
        skips += _call_sites(tree, str(path))
        places = _python_placeholders(tree, source, str(path))
    finally:
        _CURRENT_SOURCE.pop()
    return skips, skipifs, places


def scan_python_roots(roots: list[str]) -> dict[str, list[_Site]]:
    result: dict[str, list[_Site]] = {
        "python_skip_sites": [],
        "python_skipif_sites": [],
        "python_placeholder_tests": [],
    }
    for root in roots:
        base = Path(root)
        if not base.is_dir():
            continue
        for path in list(base.rglob("test_*.py")) + list(base.rglob("*_test.py")):
            if set(path.parts) & _SKIP_DIRS:
                continue
            skips, skipifs, places = scan_python_file(path)
            result["python_skip_sites"] += skips
            result["python_skipif_sites"] += skipifs
            result["python_placeholder_tests"] += places
    return result


# ── TypeScript extraction ────────────────────────────────────────────────────

_TS_SKIP_RE = re.compile(r"(?:test\.(?:skip|fixme)|describe\.skip|test\.describe\.skip)\s*\(")
_TS_TEST_RE = re.compile(r"(?<!\.)\b(it|test)\s*\(\s*(?=['\"`])")


def _matching_close(content: str, open_idx: int) -> int:
    """Index just past the `)` matching the `(` at open_idx (string-naive,
    T.3-documented: conservative direction)."""
    depth = 1
    j = open_idx + 1
    while j < len(content):
        ch = content[j]
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                return j + 1
        j += 1
    return len(content)


def _string_literals_in_call(call_text: str) -> list[str]:
    """Extract single/double-quoted string literals (order preserved)."""
    return re.findall(r"['\"`]([^'\"`]*)['\"`]", call_text)


def _strip_comments(text: str) -> str:
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    text = re.sub(r"//[^\n]*", "", text)
    return text


_STUB_LINE_RE = re.compile(
    r"^\s*(expect\s*\(\s*typeof\s+[^)]*\)\s*\.\s*toBe\s*\(\s*['\"]function['\"]\s*\)\s*;?"
    r"|expect\s*\([^)]*\)\s*\.\s*toBeDefined\s*\(\s*\)\s*;?"
    r"|expect\s*\([^)]*\)\s*\.\s*toMatch\s*\(\s*/?\^use"
    r"|const\s+[A-Za-z_$][\w$]*\s*=\s*Object\.keys\s*\([^)]*\)\s*;?"
    r"|for\s*\(\s*const\s+key\s+of\s+[A-Za-z_$][\w$]*\s*\)\s*\{?\s*$"
    r"|if\s*\(\s*typeof\s+[^)]*\)\s*\{?\s*$"
    r"|\}\s*$"
    r"|\{\s*$"
    r"|\}\s*;\s*$"
    r"|\s*$)"
)


def _strip_ts_callback_wrapper(text: str) -> str:
    """Remove the arrow/function wrapper around an it/test callback body.

    After comment-stripping, a body reads ``, () => { ... });`` — the
    wrapper tokens are not content. Drop the header (``, () => {`` /
    ``, function () {`` / ``, async () => {``) and the trailing
    ``});``/``}`` so only the inner statements remain.
    """
    cleaned = text
    cleaned = re.sub(r"^\s*,?\s*(?:async\s+)?(?:\([^)]*\)|\w+)?\s*=>\s*\{\s*", "", cleaned)
    cleaned = re.sub(r"^\s*,?\s*function\s*\([^)]*\)\s*\{\s*", "", cleaned)
    cleaned = re.sub(r"^\s*\{\s*", "", cleaned)
    cleaned = re.sub(r"\}\s*\)?\s*;?\s*$", "", cleaned)
    return cleaned


def _ts_placeholder_kind(body_text: str) -> str | None:
    """Classify a TS it/test body: 'comment-only' | 'export-stub' |
    'tautology-stub' | None."""
    stripped = _strip_comments(body_text)
    stripped = _strip_ts_callback_wrapper(stripped)
    if not stripped.strip():
        return "comment-only"
    lines = [ln for ln in stripped.splitlines() if ln.strip()]
    if not lines:
        return None
    # The W17 evidence class: every real call commented out, the body ends
    # in `expect(true).toBe(true)`-style placeholder assertions (identical
    # operands). check_assert_true_true blocks NEW ones; this classifies the
    # existing debt so the ratchet can own it.
    if all(re.fullmatch(r"expect\((.+?)\)\s*\.\s*toBe\s*\(\1\)\s*;?\s*", ln) for ln in lines):
        return "tautology-stub"
    # Every remaining line must be stub-shaped, and at least one
    # typeof-function expectation must be present.
    if (
        "typeof" not in stripped
        or "toBe('function')" not in stripped
        or any(not _STUB_LINE_RE.match(ln) for ln in lines)
    ):
        return None
    return "export-stub"


def scan_ts_file(path: Path) -> tuple[list[_Site], list[_Site]]:
    """Return (skip_sites, placeholders) for one TS spec/test file."""
    try:
        content = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return [], []
    skips: list[_Site] = []
    places: list[_Site] = []

    # Skip/fixme sites.
    for m in _TS_SKIP_RE.finditer(content):
        end = _matching_close(content, m.end() - 1)
        call_text = content[m.start() : end]
        literals = _string_literals_in_call(call_text)
        reason = literals[-1] if literals else ""
        line = content.count("\n", 0, m.start()) + 1
        skips.append(_Site(str(path), line, reason))

    # it/test blocks (placeholder scan).
    for m in _TS_TEST_RE.finditer(content):
        open_idx = content.find("(", m.end() - 1)
        if open_idx == -1:
            continue
        end = _matching_close(content, open_idx)
        call_text = content[open_idx:end]
        # Drop the title string; the remainder is the callback/body.
        first = re.search(r"['\"`]", call_text)
        if first is None:
            continue
        # find the closing quote of the title (naive: same quote char)
        quote = call_text[first.start()]
        close_idx = call_text.find(quote, first.start() + 1)
        if close_idx == -1:
            continue
        body_text = call_text[close_idx + 1 :]
        kind = _ts_placeholder_kind(body_text)
        if kind is None:
            continue
        line = content.count("\n", 0, m.start()) + 1
        places.append(_Site(str(path), line, body_text))
    return skips, places


def scan_ts_roots(roots: list[str]) -> dict[str, list[_Site]]:
    result: dict[str, list[_Site]] = {"ts_skip_sites": [], "ts_placeholder_tests": []}
    for root in roots:
        base = Path(root)
        if not base.is_dir():
            continue
        patterns = ["*.spec.ts", "*.test.ts", "*.test.tsx"]
        files = []
        for pattern in patterns:
            files += list(base.rglob(pattern))
        for path in files:
            if set(path.parts) & _SKIP_DIRS:
                continue
            skips, places = scan_ts_file(path)
            result["ts_skip_sites"] += skips
            result["ts_placeholder_tests"] += places
    return result


# ── Report + verify ──────────────────────────────────────────────────────────


def analyze_roots(python_roots: list[str], ts_roots: list[str]) -> dict:
    """Full scan → report dict. Buckets carry total/unannotated/annotated."""
    sites: dict[str, list[_Site]] = {}
    sites.update(scan_python_roots(python_roots))
    sites.update(scan_ts_roots(ts_roots))

    report: dict = {}
    expired: list[dict] = []
    unannotated_total = 0
    placeholder_total = 0
    for bucket in _BUCKETS:
        bucket_sites = sites[bucket]
        annotated = [s for s in bucket_sites if _annotated(s)]
        unannotated = [s for s in bucket_sites if not _annotated(s)]
        for s in annotated:
            ticket, expiry = s.annotation()
            assert expiry is not None
            if expiry < date.today():
                expired.append(
                    {
                        "file": s.file,
                        "line": s.line,
                        "reason": s.reason,
                        "ticket": ticket,
                        "expiry": expiry.isoformat(),
                    }
                )
        if bucket.endswith("placeholder_tests"):
            placeholder_total += len(bucket_sites)
        else:
            unannotated_total += len(unannotated)
        report[bucket] = {
            "total": len(bucket_sites),
            "unannotated": len(unannotated),
            "annotated": len(annotated),
        }
    report["expired"] = expired
    # Debt = unannotated sites (all buckets) + placeholder sites (owned or not).
    report["debt"] = unannotated_total + placeholder_total
    return report


def _load_baseline(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def verify(report: dict, baseline_path: Path, today: date | None = None) -> int:
    """0 clean; 1 expired or growth; 2 baseline unreadable."""
    today = today or date.today()
    if report["expired"]:
        print(
            f"GATE-40: {len(report['expired'])} EXPIRED scaffold annotation(s) — "
            "resolve the debt or extend the EXPIRES date:"
        )
        for site in report["expired"][:20]:
            print(
                f"  {site['file']}:{site['line']} "
                f"[{site['ticket']} EXPIRES={site['expiry']}] — {site['reason'][:80]}"
            )
        if len(report["expired"]) > 20:
            print(f"  ... and {len(report['expired']) - 20} more")
        return 1

    try:
        baseline = _load_baseline(baseline_path)
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(f"GATE-40: baseline missing or unreadable ({exc}) — run --update first")
        return 2

    growth = []
    for bucket in _BUCKETS:
        current = report[bucket]["unannotated"]
        base = int(baseline.get(bucket, 0))
        if current > base:
            growth.append(f"{bucket}: {current} > baseline {base}")
    if growth:
        print("GATE-40: unannotated skip/placeholder debt grew past the baseline:")
        for line in growth:
            print(f"  {line}")
        print(
            "Every skip/fixme/xfail reason must carry "
            "TICKET=<id> EXPIRES=<YYYY-MM-DD>; placeholder bodies annotate "
            "as a leading comment. Annotating debt always shrinks the bucket."
        )
        return 1

    print(
        f"GATE-40: clean — debt={report['debt']} "
        f"(unannotated skips + placeholder tests; per-bucket ratchet OK, 0 expired)"
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="GATE-40 — skip/placeholder debt owns a ticket and an expiry."
    )
    parser.add_argument("--python-roots", nargs="+", default=DEFAULT_PY_ROOTS)
    parser.add_argument("--ts-roots", nargs="+", default=DEFAULT_TS_ROOTS)
    parser.add_argument("--baseline", type=Path, default=DEFAULT_BASELINE)
    parser.add_argument(
        "--update",
        action="store_true",
        help="record the CURRENT unannotated counts as the new floor",
    )
    args = parser.parse_args(argv)

    report = analyze_roots(args.python_roots, args.ts_roots)

    if args.update:
        payload = {"generated_at": datetime.now(UTC).isoformat()}
        for bucket in _BUCKETS:
            payload[bucket] = report[bucket]["unannotated"]
        args.baseline.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        print(f"GATE-40: baseline written — debt={report['debt']}")
        return 0

    return verify(report, args.baseline)


if __name__ == "__main__":
    sys.exit(main())
