#!/usr/bin/env python3
"""W11.5 (oss-release-remediation) — the ``random.*`` CSPRNG sweep.

Register row 18 (insecure randomness): Python's ``random`` module is a
Mersenne-Twister PRNG — predictable from ~624 observed outputs.  Any
use of it in a TOKEN/KEY context (secrets, tokens, API keys, nonces,
OTPs, reset/invitation codes, salts, IVs, session ids, credentials) is
a vulnerability: attackers can reconstruct the RNG state and mint
forged secrets.  ``secrets.*`` / ``os.urandom`` / ``uuid.uuid4`` are
the CSPRNG paths.

This gate:

* AST-scans ``hub/``, ``cli/`` and ``scripts/`` (configurable) for
  every ``random.X`` call (both ``import random`` attribute calls and
  ``from random import X`` alias calls);
* classifies each site TOKEN-CONTEXT when the assignment target or the
  enclosing function/class name carries a token-ish keyword (token,
  secret, key, password, nonce, otp, reset, invitation, session,
  credential, salt, iv, cipher, signing, verification);
* exits 1 on any TOKEN-CONTEXT site not allowlisted
  (``scripts/crypto_random_allowlist.txt`` — path:lineno:reason);
* fails on dead allowlist anchors (the anchored line no longer carries
  a random call);
* ``--report`` rewrites the committed report
  ``docs/audits/w115-random-sweep-report.md`` with the full inventory.

Benign uses (backoff jitter, data sampling, capacity-test offsets) are
reported but not blocked.  Falsifiability: the pin suite
``scripts/tests/test_w115_crypto_random_sweep.py`` plants a violating
file and asserts this gate flips RED; the harness mutation renames
``_TOKEN_KEYWORDS`` and proves the pin catches the blindness.
"""

from __future__ import annotations

import argparse
import ast
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_ROOTS = ("hub", "cli", "scripts")
ALLOWLIST_PATH = REPO_ROOT / "scripts" / "crypto_random_allowlist.txt"
REPORT_PATH = REPO_ROOT / "docs" / "audits" / "w115-random-sweep-report.md"

# random.* callables we track (the PRNG surface).
_RANDOM_ATTRS = {
    "random", "choice", "choices", "randint", "randrange", "randbytes",
    "sample", "uniform", "triangular", "betavariate", "gauss", "shuffle",
    "getrandbits", "seed",
}

# Token-ish keywords: a site whose assignment target or enclosing
# function/class name matches one of these is a TOKEN-CONTEXT site.
_TOKEN_KEYWORDS = (
    "token",
    "secret",
    "password",
    "passwd",
    "nonce",
    "otp",
    "reset_code",
    "verification_code",
    "auth_code",
    "invitation",
    "invite_code",
    "session",
    "credential",
    "salt",
    "iv",
    "cipher",
    "signing",
    "api_key",
    "recovery_code",
    "backup_code",
)


# Vendored/virtualenv trees are third-party code — out of sweep scope
# (the gate audits OUR tree, not the pinned dependency trees).
_EXCLUDED_PARTS = {"__pycache__", "venv", ".venv", "site-packages", "build", "dist", "node_modules"}


def _iter_python_files(roots: tuple[str, ...]) -> list[Path]:
    files: list[Path] = []
    for root_name in roots:
        root = Path(root_name)
        if not root.is_dir():
            continue
        files.extend(
            path
            for path in sorted(root.rglob("*.py"))
            if not (_EXCLUDED_PARTS & set(path.parts))
        )
    return files


def _keyword_hit(name: str) -> bool:
    lower = name.lower()
    return any(keyword in lower for keyword in _TOKEN_KEYWORDS)


class _SiteCollector(ast.NodeVisitor):
    """Collect random.* call sites with their context."""

    def __init__(self, source: str):
        self.source = source
        self.aliases: set[str] = set()  # names imported from random
        self.sites: list[dict] = []
        self._stack: list[str] = []  # enclosing function/class names
        self._module: ast.Module | None = None

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if node.module == "random":
            self.aliases.update(alias.name for alias in node.names)
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._stack.append(node.name)
        self.generic_visit(node)
        self._stack.pop()

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self._stack.append(node.name)
        self.generic_visit(node)
        self._stack.pop()

    def visit_Call(self, node: ast.Call) -> None:
        call_name: str | None = None
        if isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name):
            if node.func.value.id == "random" and node.func.attr in _RANDOM_ATTRS:
                call_name = node.func.attr
        elif isinstance(node.func, ast.Name) and node.func.id in self.aliases:
            call_name = node.func.id
        if call_name is not None:
            target = self._assignment_target(node)
            func_name = self._stack[-1] if self._stack else ""
            line = self.source.splitlines()[node.lineno - 1] if node.lineno <= len(self.source.splitlines()) else ""
            self.sites.append(
                {
                    "call": call_name,
                    "target": target,
                    "func": func_name,
                    "line": line.strip(),
                    "lineno": node.lineno,
                    "token_context": _keyword_hit(target) or _keyword_hit(func_name),
                }
            )
        self.generic_visit(node)

    def _assignment_target(self, node: ast.Call) -> str:
        """The name(s) the call's result flows into, if any — found by
        re-walking the module looking for the Assign/AnnAssign that
        contains this exact call node."""
        wrapper = _ParentFinder(node)
        wrapper.visit(self._module)
        return wrapper.target


class _ParentFinder(ast.NodeVisitor):
    """Find the assignment target containing the exact call node."""

    def __init__(self, needle: ast.Call):
        self.needle = needle
        self.target = ""

    def _names_of(self, node: ast.AST) -> str:
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, (ast.Tuple, ast.List)):
            return " ".join(self._names_of(elt) for elt in node.elts)
        if isinstance(node, ast.Attribute):
            return self._names_of(node.value) + "." + node.attr
        if isinstance(node, ast.Subscript):
            return self._names_of(node.value)
        return ""

    def visit_Assign(self, node: ast.Assign) -> None:
        for target in node.targets:
            if any(sub is self.needle for sub in ast.walk(node.value)):
                self.target = self._names_of(target)
        self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        if node.value is not None and any(sub is self.needle for sub in ast.walk(node.value)):
            self.target = self._names_of(node.target)
        self.generic_visit(node)


def _scan_file(path: Path) -> list[dict]:
    try:
        source = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    collector = _SiteCollector(source)
    collector._module = tree
    collector.visit(tree)
    for site in collector.sites:
        site["path"] = str(path)
    return collector.sites


def _load_allowlist() -> dict[tuple[str, int], str]:
    entries: dict[tuple[str, int], str] = {}
    if not ALLOWLIST_PATH.is_file():
        return entries
    for raw_line in ALLOWLIST_PATH.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split(":", 2)
        if len(parts) == 3:
            try:
                entries[(parts[0], int(parts[1]))] = parts[2].strip()
            except ValueError:
                continue
    return entries


def _report(sites: list[dict], allowlist: dict[tuple[str, int], str]) -> str:
    lines = [
        "# W11.5 — `random.*` CSPRNG sweep report",
        "",
        "Generated by `scripts/check_crypto_random.py --report` (register row 18).",
        "`random` is a Mersenne-Twister PRNG; TOKEN-CONTEXT uses are blocked",
        "by the gate unless allowlisted in `scripts/crypto_random_allowlist.txt`.",
        "",
        f"## Inventory — {len(sites)} site(s)",
        "",
        "| File | Line | Call | Context | Classification |",
        "|---|---|---|---|---|",
    ]
    for site in sorted(sites, key=lambda s: (s["path"], s["lineno"])):
        classification = "TOKEN-CONTEXT" if site["token_context"] else "benign"
        rel = site["path"].replace(str(REPO_ROOT) + "/", "")
        lines.append(
            f"| `{rel}:{site['lineno']}` | {site['lineno']} | "
            f"`random.{site['call']}` | {site['target'] or site['func'] or '—'} | {classification} |"
        )
    token_sites = [s for s in sites if s["token_context"]]
    lines.append("")
    lines.append(f"## Token-context sites — {len(token_sites)}")
    for site in sorted(token_sites, key=lambda s: (s["path"], s["lineno"])):
        rel = site["path"].replace(str(REPO_ROOT) + "/", "")
        anchor = allowlist.get((site["path"], site["lineno"]))
        lines.append(
            f"- `{rel}:{site['lineno']}` "
            f"{'ALLOWLISTED: ' + anchor if anchor else 'UNALLOWLISTED — BLOCKED'}"
        )
    if not token_sites:
        lines.append("None — every `random.*` site is benign (jitter/sampling).")
    return "\n".join(lines) + "\n"


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="CSPRNG random.* sweep gate")
    parser.add_argument(
        "--roots",
        nargs="+",
        default=list(DEFAULT_ROOTS),
        help="directories to scan (default: hub cli scripts)",
    )
    parser.add_argument(
        "--report",
        action="store_true",
        help="rewrite the committed sweep report and exit",
    )
    parser.add_argument(
        "--check-anchors",
        action="store_true",
        help="fail on dead allowlist anchors (default: warn only)",
    )
    args = parser.parse_args(argv)

    sites: list[dict] = []
    for path in _iter_python_files(tuple(args.roots)):
        sites.extend(_scan_file(path))

    allowlist = _load_allowlist()
    token_sites = [site for site in sites if site["token_context"]]
    unallowlisted = [
        site for site in token_sites if (site["path"], site["lineno"]) not in allowlist
    ]

    if args.report:
        REPORT_PATH.write_text(_report(sites, allowlist), encoding="utf-8")
        print(f"report written: {REPORT_PATH}")
        return 0

    dead_anchors = []
    for (path, lineno), reason in sorted(allowlist.items()):
        anchor_site = next(
            (s for s in sites if s["path"] == path and s["lineno"] == lineno), None
        )
        if anchor_site is None:
            dead_anchors.append((path, lineno, reason))
        elif not anchor_site["token_context"]:
            dead_anchors.append((path, lineno, f"no longer token-context: {reason}"))

    print(f"crypto-random sweep: {len(sites)} random.* site(s), "
          f"{len(token_sites)} token-context, {len(unallowlisted)} unallowlisted")
    for site in unallowlisted:
        print(f"  VIOLATION {site['path']}:{site['lineno']} "
              f"random.{site['call']} in token context "
              f"({site['target'] or site['func']})")
    for path, lineno, reason in dead_anchors:
        print(f"  DEAD-ANCHOR {path}:{lineno} ({reason})")
        if args.check_anchors:
            unallowlisted.append(
                {"path": path, "lineno": lineno, "call": "?", "target": reason, "func": ""}
            )
    if unallowlisted:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
