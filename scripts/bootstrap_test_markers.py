#!/usr/bin/env python3
"""
AST-based marker bootstrap for Meshant's 37K+ test functions.
Classifies every test function/class into exactly one Tier-1 marker.
Modes: --check (dry-run) | --apply (modify files) | --path <dir>
"""
import argparse, ast, os, re, sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TEST_DIRS = [ROOT / "hub/apps", ROOT / "tests", ROOT / "cli/tests",
             ROOT / "sdk/python/tests", ROOT / "services"]

# DB-dependent patterns → integration (unless e2e path)
DB_PATTERNS = [r'\bTestCase\b', r'\bTransactionTestCase\b', r'\bLiveServerTestCase\b',
               r'\bAPITestCase\b', r'\bAPILiveServerTestCase\b', r'django_db']
E2E_PATHS = ["tests/e2e/", "tests/chaos/"]
UNIT_PATHS = ["cli/tests/unit/", "sdk/python/tests/unit/"]
INTEGRATION_PATHS = ["tests/resilience/", "tests/security/", "tests/isolation/",
    "tests/regression/", "tests/concurrency/", "tests/pact/", "services/"]


def find_test_files(root: Path) -> list[Path]:
    out = []
    for dirpath, _, filenames in os.walk(root):
        for fn in filenames:
            fp = Path(dirpath) / fn
            if fp.suffix == ".py" and (fn.startswith("test_") or fn.endswith("_tests.py")):
                out.append(fp)
    return out


def uses_db(source: str) -> bool:
    return any(re.search(pat, source) for pat in DB_PATTERNS)


def has_tier1_marker(file_path: Path) -> str | None:
    try:
        c = file_path.read_text(encoding="utf-8")
    except Exception:
        return None
    for m in ("unit", "integration", "e2e"):
        if f"pytest.mark.{m}" in c:
            return m
    return None


def classify_file(file_path: Path) -> str | None:
    rel = str(file_path.relative_to(ROOT))
    for ep in E2E_PATHS:
        if ep in rel:
            return "e2e"
    for up in UNIT_PATHS:
        if up in rel:
            return "unit"
    try:
        src = file_path.read_text(encoding="utf-8")
    except Exception:
        return None
    for ip in INTEGRATION_PATHS:
        if ip in rel:
            return "integration"
    if uses_db(src):
        return "integration"
    if "hub/apps/" in rel and "/tests/" in rel:
        return "unit"
    if "cli/tests/" in rel:
        if any(kw in src for kw in ("APIClient", "requests.post", "requests.get",
                                      "TestClient", "api_client", "real_api")):
            return "integration"
        return "unit"
    if "sdk/python/tests/" in rel:
        if "unit" in rel.lower() or "mock" in rel.lower():
            return "unit"
        return "integration"
    if "tests/i18n/" in rel:
        return "unit" if not uses_db(src) else "integration"
    return None


def count_test_nodes(file_path: Path) -> int:
    try:
        tree = ast.parse(file_path.read_text(encoding="utf-8"))
    except Exception:
        return 0
    return sum(1 for n in ast.walk(tree)
               if isinstance(n, (ast.FunctionDef, ast.ClassDef))
               and (n.name.startswith("test_") or (isinstance(n, ast.ClassDef) and n.name.startswith("Test"))))


def apply_marker_to_file(file_path: Path, marker: str) -> int:
    """Add @pytest.mark.<marker> decorator to test functions/classes.
    Returns number of nodes decorated."""
    try:
        src = file_path.read_text(encoding="utf-8")
    except Exception:
        return 0
    try:
        tree = ast.parse(src, filename=str(file_path))
    except SyntaxError:
        return 0

    test_nodes = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name.startswith("test_"):
            test_nodes.append(node)
        elif isinstance(node, ast.ClassDef) and node.name.startswith("Test"):
            test_nodes.append(node)

    # Filter: skip already-classified
    to_decorate = []
    for node in test_nodes:
        already = False
        for d in node.decorator_list:
            if isinstance(d, ast.Call) and hasattr(d.func, 'attr'):
                a = d.func
                parts = []
                while isinstance(a, ast.Attribute):
                    parts.append(a.attr)
                    a = a.value
                if isinstance(a, ast.Name):
                    parts.append(a.id)
                    parts.reverse()
                    if len(parts) >= 3 and parts[:2] == ["pytest", "mark"] and parts[2] in ("unit","integration","e2e"):
                        already = True
                        break
        if not already:
            to_decorate.append(node)

    if not to_decorate:
        return 0

    # Apply: add decorator lines (reverse line order to preserve positions)
    to_decorate.sort(key=lambda n: n.lineno, reverse=True)
    lines = src.splitlines(keepends=True)
    for node in to_decorate:
        idx = node.lineno - 1
        indent = lines[idx][:len(lines[idx]) - len(lines[idx].lstrip())]
        lines.insert(idx, f"{indent}@pytest.mark.{marker}\n")

    file_path.write_text("".join(lines), encoding="utf-8")
    return len(to_decorate)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--check", action="store_true")
    p.add_argument("--apply", action="store_true")
    p.add_argument("--path", type=str)
    p.add_argument("--json", action="store_true")
    args = p.parse_args()
    if not args.check and not args.apply:
        p.error("Need --check or --apply")

    roots = [ROOT / args.path] if args.path else TEST_DIRS
    roots = [r for r in roots if r.is_dir()]
    all_files = []
    for r in roots:
        all_files.extend(find_test_files(r))
    all_files = sorted(set(all_files))

    stats = defaultdict(int)
    total_nodes = 0
    results = []

    for fp in all_files:
        classification = classify_file(fp)
        stats["scanned"] += 1
        if classification is None:
            stats["unclassified"] += 1
            continue
        stats[f"to_{classification}"] += 1
        existing = has_tier1_marker(fp)
        if existing:
            if existing != classification:
                stats["mismatch"] += 1
                results.append(f"MISMATCH {fp.relative_to(ROOT)}: is {classification} but marked {existing}")
            else:
                stats["already_ok"] += 1
            continue
        stats["needs_marker"] += 1
        nodes = count_test_nodes(fp)
        total_nodes += nodes
        if args.apply:
            applied = apply_marker_to_file(fp, classification)
            stats["applied_files"] += 1
            stats["applied_nodes"] += applied
        results.append(f"  {classification:12s} {fp.relative_to(ROOT)} ({nodes} test nodes)")

    if args.json:
        import json
        print(json.dumps(dict(stats)))
        return

    print(f"\n{'='*60}")
    print(f"Marker Bootstrap — {'DRY-RUN' if args.check else 'APPLIED'}")
    print(f"{'='*60}")
    print(f"Files scanned:     {stats['scanned']:>6}")
    print(f"Already correct:   {stats['already_ok']:>6}")
    print(f"Needs marker:      {stats['needs_marker']:>6}  ({total_nodes} test functions)")
    print(f"  → unit:          {stats['to_unit']:>6}")
    print(f"  → integration:   {stats['to_integration']:>6}")
    print(f"  → e2e:           {stats['to_e2e']:>6}")
    if stats['mismatch']:
        print(f"Mismatches:        {stats['mismatch']:>6}")
    if stats['unclassified']:
        print(f"Unclassified:      {stats['unclassified']:>6}")
    if args.apply:
        print(f"\nMarkers applied:   {stats['applied_files']} files, {stats['applied_nodes']} nodes")

    return 0
