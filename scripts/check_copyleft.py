#!/usr/bin/env python3
"""Copyleft / third-party license audit for the SHIPPED closures (G7, P0-13).

Restored + expanded from the deleted 313.3.4 checker, which covered only
the requirements.txt closure. This checker covers:

  PY — requirements.txt + requirements-core.txt (image closure),
       sdk/python/pyproject.toml dependencies + optional-dependencies
       extras, cli/setup.py install_requires (published pip packages),
       and (advisory-only) requirements-dev.txt / requirements-docs.txt.
  NPM — frontend/package.json + sdk/js/package.json dependencies
       (frontend deps are bundled into the published SPA; SDK deps are
       npm declarations). devDependencies are advisory-only.

Policy (unchanged from 313.3.4, now machine-applied to every closure):

  * hard copyleft = GPL / AGPL / SSPL WITHOUT a permissive option or an
    LGPL option — a violation;
  * weak copyleft = LGPL (psycopg2, pyclamd precedent) and MPL
    (file-level) — accepted;
  * permissive or dual-licensed-with-a-permissive-option (MIT, BSD,
    Apache, ISC, Artistic, Public Domain, CC0, Unlicense, PSF, Zlib) —
    accepted;
  * UNKNOWN / unparseable / missing license data — UNRESOLVED. Fail-closed
    by default: a declared dependency whose license cannot be certified
    refuses the run (a publish without license evidence is refused, never
    assumed clean — same philosophy as the P.8 gitleaks gate).

Usage: python scripts/check_copyleft.py [--ci] [--full-closure]
       [--skip-py] [--skip-npm] [--venv PYTHON]
       [--requirement-files F ...] [--npm-roots DIR ...]
Exit 0 clean; 1 violation or unresolved shipped dependency; 2 usage.
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import subprocess
import sys
import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

# ── Closure sources ──────────────────────────────────────────────────────────

PY_SHIPPED_FILES = ["requirements.txt", "requirements-core.txt"]
PY_DEV_FILES = ["requirements-dev.txt", "requirements-docs.txt"]
NPM_ROOTS = ["frontend", "sdk/js"]

# ── License classification ───────────────────────────────────────────────────

_WEAK_RE = re.compile(
    r"(?:gnu\s+)?(?:lesser|library)\s+general\s+public|"
    r"lgpl|mozilla\s+public|mpl",
    re.IGNORECASE,
)
_HARD_RE = re.compile(
    r"server\s+side\s+public|sspl|"
    r"(?:gnu\s+)?affero\s+general\s+public|agpl|"
    r"(?:gnu\s+)?general\s+public|"
    r"(?<![a-z])gpl(?![a-z])",
    re.IGNORECASE,
)
_PERMISSIVE_RE = re.compile(
    r"\bmit\b|\bbsd\b|apache|\bisc\b|artistic|public\s+domain|\bcc0\b|"
    r"\bunlicense\b|python\s+software\s+foundation|\bpsf\b|python-2\.0|"
    r"\bzlib\b|\bw3c\b|zope\s+public|\bzpl\b",
    re.IGNORECASE,
)


def classify_license(license_text: str | None) -> str:
    """Return 'permissive' | 'weak-copyleft' | 'hard-copyleft' | 'unresolved'."""
    text = (license_text or "").strip()
    if not text or text.upper() in ("UNKNOWN", "NONE", "PROPRIETARY"):
        return "unresolved"
    # MPL is weak-copyleft (file-level) but doubles as a permissive option
    # in dual licenses — a permissive option anywhere wins first.
    if _PERMISSIVE_RE.search(text):
        return "permissive"
    if _WEAK_RE.search(text):
        return "weak-copyleft"
    if _HARD_RE.search(text):
        return "hard-copyleft"
    return "unresolved"


# ── Python closure parsing ───────────────────────────────────────────────────


def normalize_name(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name.lower()).strip("-")


def _req_names(text: str) -> set[str]:
    names: set[str] = set()
    for raw in text.splitlines():
        line = raw.split("#")[0].strip()
        if not line or line.startswith(("-", "--")):
            continue
        m = re.match(r"^([A-Za-z0-9_.-]+)", line)
        if m:
            names.add(normalize_name(m.group(1)))
    return names


def _pyproject_names(path: Path) -> tuple[set[str], set[str]]:
    """Return (shipped_names, dev_names) from a pyproject [project] block."""
    shipped: set[str] = set()
    dev: set[str] = set()
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError):
        return shipped, dev
    project = data.get("project", {})
    for dep in project.get("dependencies", []):
        shipped.add(normalize_name(re.split(r"[<>=!~;\[\s]", dep, maxsplit=1)[0]))
    for extra, deps in (project.get("optional-dependencies") or {}).items():
        target = dev if extra == "dev" else shipped
        for dep in deps:
            target.add(normalize_name(re.split(r"[<>=!~;\[\s]", dep, maxsplit=1)[0]))
    return shipped, dev


def _setup_py_names(path: Path) -> set[str]:
    """install_requires from setup.py, AST-parsed (real code, no regex guesses)."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError):
        return set()
    names: set[str] = set()
    for node in ast.walk(tree):
        if not (
            isinstance(node, ast.Assign)
            and any(
                isinstance(t, ast.Name) and t.id == "install_requires"
                for t in node.targets
            )
        ):
            continue
        if isinstance(node.value, (ast.List, ast.Tuple)):
            for elt in node.value.elts:
                if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                    names.add(normalize_name(re.split(r"[<>=!~;\[\s]", elt.value, maxsplit=1)[0]))
    return names


def collect_python_closures(
    requirement_files: list[Path] | None,
    repo_root: Path,
) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    """Return (shipped {name: [source...]}, dev {name: [source...]})."""
    shipped: dict[str, list[str]] = {}
    dev: dict[str, list[str]] = {}
    if requirement_files is not None:
        for f in requirement_files:
            if not Path(f).is_file():
                shipped.setdefault(f"<missing-requirement-file:{f}>", []).append(str(f))
                continue
            for name in _req_names(Path(f).read_text(encoding="utf-8")):
                shipped.setdefault(name, []).append(str(f))
        return shipped, dev
    for rel in PY_SHIPPED_FILES:
        f = repo_root / rel
        if f.is_file():
            for name in _req_names(f.read_text(encoding="utf-8")):
                shipped.setdefault(name, []).append(rel)
    for rel in PY_DEV_FILES:
        f = repo_root / rel
        if f.is_file():
            for name in _req_names(f.read_text(encoding="utf-8")):
                dev.setdefault(name, []).append(rel)
    sdk_shipped, sdk_dev = _pyproject_names(repo_root / "sdk/python/pyproject.toml")
    for name in sdk_shipped:
        shipped.setdefault(name, []).append("sdk/python/pyproject.toml")
    for name in sdk_dev:
        dev.setdefault(name, []).append("sdk/python/pyproject.toml [dev]")
    for name in _setup_py_names(repo_root / "cli/setup.py"):
        shipped.setdefault(name, []).append("cli/setup.py")
    return shipped, dev


# ── License resolution ───────────────────────────────────────────────────────


_METADATA_DUMP = (
    "import importlib.metadata as m, json; "
    "print(json.dumps(["
    "{'name': d.metadata.get('Name') or '', "
    "'version': d.version, "
    "'license': d.metadata.get('License') or '', "
    "'license_expression': d.metadata.get('License-Expression') or '', "
    "'classifiers': [c for c in (d.metadata.get_all('Classifier') or []) "
    "if c.startswith('License')]} "
    "for d in m.distributions()]))"
)


def metadata_license_map(python: str) -> dict[str, tuple[str, str]]:
    """The target interpreter's own distribution metadata →
    {normalized_name: (version, license)}.

    Stdlib-only (importlib.metadata), so the audit has no external-tool
    dependency: the license string prefers the Metadata ``License`` field
    and falls back to the License:: classifiers — pip-licenses' own
    classifier-first ordering was the root cause of the SPARQLWrapper
    "W3C License"→Other/Proprietary misreport (P0-13).
    """
    try:
        proc = subprocess.run(
            [python, "-c", _METADATA_DUMP],
            capture_output=True,
            text=True,
            timeout=600,
            check=False,
        )
    except OSError as exc:
        raise RuntimeError(f"metadata dump failed for {python}: {exc}") from exc
    if proc.returncode != 0 or not proc.stdout.strip():
        raise RuntimeError(f"metadata dump failed for {python}: {proc.stderr[-200:]}")
    result: dict[str, tuple[str, str]] = {}
    for entry in json.loads(proc.stdout):
        name = entry.get("name") or ""
        # Join every metadata signal and let the classifier's option
        # rules decide (a permissive option anywhere wins). Single-source
        # preference fails both ways: "Dual License" (legacy field)
        # hides the real BSD/Apache options carried by the classifiers,
        # and classifiers-only misreports owlrl's real W3C license field
        # as Other/Proprietary.
        license_text = "; ".join(
            signal
            for signal in (
                (entry.get("license_expression") or "").strip(),
                (entry.get("license") or "").strip(),
                "; ".join(entry.get("classifiers") or []),
            )
            if signal
        )
        result[normalize_name(name)] = (
            entry.get("version") or "",
            license_text,
        )
    return result


# ── npm resolution ───────────────────────────────────────────────────────────


def collect_npm_closure(root: Path) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    """Return (shipped {name: [source]}, dev {name: [source]}) for one npm root."""
    shipped: dict[str, list[str]] = {}
    dev: dict[str, list[str]] = {}
    pkg_file = root / "package.json"
    if not pkg_file.is_file():
        return shipped, dev
    try:
        pkg = json.loads(pkg_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return shipped, dev
    for name in pkg.get("dependencies", {}):
        shipped[name] = [f"{root.name}/package.json [dependencies]"]
    for name in pkg.get("devDependencies", {}):
        dev[name] = [f"{root.name}/package.json [devDependencies]"]
    return shipped, dev


def load_allowlist(path: Path | None) -> dict[str, dict[str, str]]:
    """Committed allowlist: package-name → {license, note}.

    Entries cover wheels whose metadata carries no license information
    (UNKNOWN to every tool) but whose license is verifiable from the
    upstream source (PyPI/GitHub) — each entry cites its source in
    ``note``. The allowlist applies to UNRESOLVED classifications only:
    it can never override a detected GPL/AGPL/SSPL.
    """
    if path is None:
        path = REPO_ROOT / "scripts/copyleft_license_allowlist.json"
    if not Path(path).is_file():
        return {}
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def npm_license(root: Path, name: str) -> str | None:
    """The license field of node_modules/<name>/package.json (real walk)."""
    pkg_file = root / "node_modules" / name / "package.json"
    if not pkg_file.is_file():
        return None
    try:
        data = json.loads(pkg_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    lic = data.get("license")
    if isinstance(lic, str):
        return lic
    if isinstance(lic, list):
        return " OR ".join(str(item) for item in lic)
    if isinstance(lic, dict):
        return str(lic.get("type") or "")
    return None


# ── Main ─────────────────────────────────────────────────────────────────────


def run(args: argparse.Namespace) -> int:
    violations: list[str] = []
    advisories: list[str] = []
    clean_notes: list[str] = []

    # ── Python side ──
    if not args.skip_py:
        shipped, dev = collect_python_closures(args.requirement_files, REPO_ROOT)
        if args.full_closure:
            shipped = {}
        allowlist = load_allowlist(args.allowlist)
        try:
            lic_map = metadata_license_map(args.venv)
        except RuntimeError as exc:
            if args.ci:
                print(f"copyleft audit FAILED — tooling unavailable in CI: {exc}")
                return 1
            print(f"copyleft audit SKIPPED — {exc}")
            return 0
        audit_names = set(lic_map) if args.full_closure else set(shipped)
        for name in sorted(audit_names):
            if name not in lic_map:
                violations.append(
                    f"[unresolved] {name} — declared but not installed "
                    f"(sources: {', '.join(shipped.get(name, []))})"
                )
                continue
            version, lic = lic_map[name]
            kind = classify_license(lic)
            line = f"{name} {version} — {lic}"
            if kind == "hard-copyleft":
                violations.append(f"[hard-copyleft] {line}")
            elif kind == "unresolved":
                if name in allowlist:
                    verified = allowlist[name]
                    verified_kind = classify_license(verified["license"])
                    clean_notes.append(
                        f"[ok {verified_kind} via allowlist] {line} — "
                        f"{verified['note']}"
                    )
                else:
                    violations.append(f"[unresolved] {line}")
            elif name in dev:
                advisories.append(f"[advisory {kind}] {line}")
            else:
                clean_notes.append(f"[ok {kind}] {line}")
        for name in sorted(set(shipped) - set(audit_names)):
            violations.append(
                f"[unresolved] {name} — declared but not installed "
                f"(sources: {', '.join(shipped[name])})"
            )
        for name in sorted(set(dev) - set(shipped) - set(audit_names)):
            advisories.append(f"[advisory unresolved] {name} — dev closure, not installed")

    # ── npm side ──
    if not args.skip_npm:
        npm_roots = (
            [Path(r) for r in args.npm_roots]
            if args.npm_roots is not None
            else [REPO_ROOT / r for r in NPM_ROOTS]
        )
        for root in npm_roots:
            if not root.is_dir():
                violations.append(f"[unresolved] npm root missing: {root}")
        npm_shipped: dict[str, list[str]] = {}
        npm_dev: dict[str, list[str]] = {}
        for root in npm_roots:
            s, d = collect_npm_closure(root)
            for name, srcs in s.items():
                npm_shipped.setdefault(name, []).extend(srcs)
            for name, srcs in d.items():
                npm_dev.setdefault(name, []).extend(srcs)
        for name in sorted(npm_shipped):
            lic = None
            for root in npm_roots:
                lic = npm_license(root, name)
                if lic is not None:
                    break
            if lic is None:
                violations.append(
                    f"[unresolved] npm:{name} — no license field in "
                    f"node_modules ({', '.join(npm_shipped[name])})"
                )
                continue
            kind = classify_license(lic)
            if kind == "hard-copyleft":
                violations.append(f"[hard-copyleft] npm:{name} — {lic}")
            elif kind == "unresolved":
                violations.append(f"[unresolved] npm:{name} — {lic!r}")
            else:
                clean_notes.append(f"[ok {kind}] npm:{name} — {lic}")
        for name in sorted(npm_dev):
            lic = None
            for root in npm_roots:
                lic = npm_license(root, name)
                if lic is not None:
                    break
            kind = classify_license(lic) if lic is not None else "unresolved"
            if kind == "hard-copyleft":
                advisories.append(f"[advisory hard-copyleft] npm-dev:{name} — {lic}")
            elif kind == "unresolved":
                advisories.append(f"[advisory unresolved] npm-dev:{name}")

    for line in advisories:
        print(line)
    for line in clean_notes:
        print(line)
    if violations:
        print(f"copyleft audit FAILED — {len(violations)} violation(s):")
        for line in violations:
            print(f"  {line}")
        return 1
    print(
        f"copyleft audit clean: {len(clean_notes)} licensed closure entries, "
        f"{len(advisories)} advisory(ies), 0 hard-copyleft/unresolved in the "
        "shipped closure"
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Copyleft / third-party license audit for the shipped closures."
    )
    parser.add_argument("--ci", action="store_true", help="fail closed on missing tooling")
    parser.add_argument(
        "--full-closure",
        action="store_true",
        help="audit EVERY installed package (CI installed-closure mode), "
        "not only the declared names",
    )
    parser.add_argument("--skip-py", action="store_true")
    parser.add_argument("--skip-npm", action="store_true")
    parser.add_argument(
        "--venv",
        default=sys.executable,
        help="python of the venv whose installed packages are audited",
    )
    parser.add_argument(
        "--requirement-files",
        nargs="+",
        type=Path,
        help="override the python requirement sources (fixture mode)",
    )
    parser.add_argument(
        "--npm-roots",
        nargs="+",
        type=Path,
        help="override the npm roots (fixture mode)",
    )
    parser.add_argument(
        "--allowlist",
        type=Path,
        help="override the license allowlist (default scripts/copyleft_license_allowlist.json)",
    )
    return run(parser.parse_args(argv))


if __name__ == "__main__":
    sys.exit(main())
