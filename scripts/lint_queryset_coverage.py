#!/usr/bin/env python3
"""
G3 / W1.4a (oss-release-remediation) — queryset-coverage lint.

Before RLS arming (W1.20), every ViewSet over a tenant-scoped model must
filter its queryset by tenant EXPLICITLY — an unfiltered viewset is the
cross-tenant leak surface that RLS would silently bless (RLS hides rows,
but the scope must be deliberate). This lint:

1. discovers the tenant-scoped models (the lint_rls_policies.py AST
   inventory — models with a tenant FK);
2. AST-discovers ModelViewSet/ReadOnlyModelViewSet/GenericViewSet
   subclasses across ``hub/apps``;
3. resolves each viewset's model (its ``queryset`` attribute or its
   serializer's ``Meta.model``);
4. proves a tenant filter: the viewset's own ``get_queryset``/queryset,
   or an ancestor's (repo classes resolved by name across the tree),
   carries a tenant-filter marker (``.filter(tenant…``,
   ``tenant_id=…``, ``get_request_tenant_id``, ``request.tenant``) and
   the queryset is not a bare ``Model.objects.all()``;
5. reports every viewset over a tenant-scoped model without a proven
   filter. Legitimate exceptions live in the allowlist
   (``lint/queryset-coverage-allowlist.yml``) with a written reason.

Exit 0 when the tree is clean; 1 otherwise.
"""

from __future__ import annotations

import argparse
import ast
import importlib.util
import re
import sys
from pathlib import Path

try:
    import yaml
except ImportError as exc:  # pragma: no cover
    raise SystemExit("requires PyYAML — `pip install pyyaml`") from exc

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SEARCH_ROOT = REPO_ROOT / "hub" / "apps"
DEFAULT_ALLOWLIST = REPO_ROOT / "lint" / "queryset-coverage-allowlist.yml"

VIEWSET_BASES = {"ModelViewSet", "ReadOnlyModelViewSet", "GenericViewSet", "ViewSet"}
_MODEL_RE = re.compile(r"([A-Z]\w*)\.objects")

# The tenant-filter markers: a queryset body proves scoping when any of
# these appears. `tenant_id=` covers the ORM field filter; the request
# markers cover get_request_tenant_id / request.tenant / user.tenant_id
# and friends.
FILTER_MARKERS = (
    ".filter(tenant",
    ".filter(Q(tenant",
    "tenant_id=",
    "get_request_tenant_id",
    "request.tenant",
    "user.tenant_id",
    "self.request.tenant",
)

# Helper methods the repo's scoping pattern delegates to — the helper's
# OWN body is checked for the markers (a call alone is not proof).
_HELPER_CALL_RE = re.compile(r"self\.([a-z_]+)\(self\.request")


def _discover_tenant_scoped_models(
    root: Path = DEFAULT_SEARCH_ROOT,
) -> dict[str, set[str]]:
    """{app_label: {ModelName}} via the RLS lint's inventory."""
    rls_path = REPO_ROOT / "scripts" / "lint_rls_policies.py"
    spec = importlib.util.spec_from_file_location("lint_rls_policies", rls_path)
    module = importlib.util.module_from_spec(spec)
    # Register before exec so dataclass type resolution finds the module.
    sys.modules["lint_rls_policies"] = module
    spec.loader.exec_module(module)
    models: dict[str, set[str]] = {}
    for app_dir in sorted(root.iterdir()):
        models_file = app_dir / "models.py"
        if not models_file.is_file():
            continue
        try:
            source = models_file.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        found = module._tenant_models_from_source(
            source, app_dir.name, str(models_file)
        )
        if found:
            models[app_dir.name] = set(found)
    return models


def _is_viewset(node: ast.ClassDef) -> bool:
    return any(
        (isinstance(base, ast.Name) and base.id in VIEWSET_BASES)
        or (isinstance(base, ast.Attribute) and base.attr in VIEWSET_BASES)
        for base in node.bases
    )


def _model_from_queryset(node: ast.ClassDef) -> str | None:
    for stmt in node.body:
        if isinstance(stmt, (ast.Assign, ast.AnnAssign)) and isinstance(
            stmt.targets[0] if isinstance(stmt, ast.Assign) else stmt.target, ast.Name
        ):
            target = stmt.targets[0] if isinstance(stmt, ast.Assign) else stmt.target
            if target.id == "queryset" and isinstance(stmt.value, ast.Call):
                match = _MODEL_RE.search(ast.unparse(stmt.value))
                if match:
                    return match.group(1)
    return None


def _model_from_serializer(node: ast.ClassDef) -> str | None:
    for stmt in node.body:
        if (
            isinstance(stmt, ast.Assign)
            and any(
                isinstance(t, ast.Name) and t.id == "serializer_class"
                for t in stmt.targets
            )
            and isinstance(stmt.value, ast.Name)
        ):
            return stmt.value.id  # resolved to Meta.model later
    return None


def _class_index(root: Path) -> dict[str, tuple[Path, ast.ClassDef]]:
    """{ClassName: (file, node)} across the search-root non-test python files."""
    index: dict[str, tuple[Path, ast.ClassDef]] = {}
    for path in sorted(root.rglob("*.py")):
        if "tests" in path.parts or "migrations" in path.parts:
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (UnicodeDecodeError, SyntaxError):
            continue
        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                index.setdefault(node.name, (path, node))
    return index


def _serializer_meta_model(index: dict, serializer_name: str) -> str | None:
    entry = index.get(serializer_name)
    if not entry:
        return None
    node = entry[1]
    for child in node.body:
        if isinstance(child, ast.ClassDef) and child.name == "Meta":
            for stmt in child.body:
                if (
                    isinstance(stmt, ast.Assign)
                    and any(
                        isinstance(t, ast.Name) and t.id == "model"
                        for t in stmt.targets
                    )
                    and isinstance(stmt.value, ast.Name)
                ):
                    return stmt.value.id
    return None


def _has_tenant_filter(text: str) -> bool:
    return any(marker in text for marker in FILTER_MARKERS)


def _ancestor_filters(
    node: ast.ClassDef,
    index: dict[str, tuple[Path, ast.ClassDef]],
    seen: set[str] | None = None,
) -> bool:
    seen = seen or set()
    for base in node.bases:
        name = (
            base.id
            if isinstance(base, ast.Name)
            else (base.attr if isinstance(base, ast.Attribute) else None)
        )
        if not name or name in VIEWSET_BASES or name in seen:
            continue
        seen.add(name)
        entry = index.get(name)
        if not entry:
            continue
        ancestor = entry[1]
        for stmt in ancestor.body:
            if (
                isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef))
                and stmt.name == "get_queryset"
                and _has_tenant_filter(ast.unparse(stmt))
            ):
                return True
            if isinstance(stmt, (ast.Assign, ast.AnnAssign)):
                target = (
                    stmt.targets[0] if isinstance(stmt, ast.Assign) else stmt.target
                )
                if (
                    isinstance(target, ast.Name)
                    and target.id == "queryset"
                    and isinstance(stmt.value, ast.Call)
                    and _MODEL_RE.search(ast.unparse(stmt.value))
                    and not ast.unparse(stmt.value).endswith(".all()")
                ):
                    return True
        if _ancestor_filters(ancestor, index, seen):
            return True
    return False


def _viewset_filters_itself(node: ast.ClassDef, index: dict | None = None) -> bool:
    has_list_machinery = any(
        isinstance(base, ast.Name)
        and base.id in {"ModelViewSet", "ReadOnlyModelViewSet"}
        for base in node.bases
    )
    for stmt in node.body:
        if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
            body = ast.unparse(stmt)
            if stmt.name == "get_queryset":
                if _has_tenant_filter(body) or _helper_body_has_filter(body, index):
                    return True
            elif not has_list_machinery and _has_tenant_filter(body):
                # GenericViewSet actions resolve the tenant per-action
                # (get_request_tenant_id etc.) — no list endpoint exists.
                return True
        if isinstance(stmt, (ast.Assign, ast.AnnAssign)):
            target = stmt.targets[0] if isinstance(stmt, ast.Assign) else stmt.target
            if (
                isinstance(target, ast.Name)
                and target.id == "queryset"
                and isinstance(stmt.value, ast.Call)
            ):
                text = ast.unparse(stmt.value)
                if _has_tenant_filter(text):
                    return True
                if _MODEL_RE.search(text) and not text.endswith(".all()"):
                    return True
    return False


def _helper_body_has_filter(body: str, index: dict | None) -> bool:
    """True when a scoping helper the body delegates to
    (``self.<helper>(self.request, ...)``) carries a marker in its own
    body — the repo's mixin-helper pattern."""
    if index is None:
        return False
    for match in _HELPER_CALL_RE.finditer(body):
        helper_name = match.group(1)
        for _, class_node in index.values():
            if not isinstance(class_node, ast.ClassDef):
                continue
            for stmt in class_node.body:
                if (
                    isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef))
                    and stmt.name == helper_name
                    and _has_tenant_filter(ast.unparse(stmt))
                ):
                    return True
    return False


def collect_gaps(root: Path, tenant_models: dict[str, set[str]]) -> list[str]:
    """Every unfiltered viewset over a tenant-scoped model, as
    `file:line: ClassName (model=ModelName, app=app_label)`."""
    index = _class_index(root)
    gaps: list[str] = []
    for path in sorted(root.rglob("*.py")):
        if "tests" in path.parts or "migrations" in path.parts:
            continue
        app_label = path.relative_to(root).parts[0]
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (UnicodeDecodeError, SyntaxError):
            continue
        for node in tree.body:
            if not isinstance(node, ast.ClassDef) or not _is_viewset(node):
                continue
            model_name = _model_from_queryset(node)
            if not model_name:
                serializer = _model_from_serializer(node)
                model_name = (
                    _serializer_meta_model(index, serializer) if serializer else None
                )
            if not model_name:
                continue
            if model_name not in tenant_models.get(app_label, set()) and not any(
                model_name in models for models in tenant_models.values()
            ):
                continue
            if _viewset_filters_itself(node, index) or _ancestor_filters(node, index):
                continue
            # Repo-relative for the live tree; root-relative for fixture
            # trees outside the repo (the pins).
            try:
                rel_path = str(path.relative_to(REPO_ROOT))
            except ValueError:
                rel_path = str(path.relative_to(root))
            gaps.append(
                f"{rel_path}:{node.lineno}: " f"{node.name} (model={model_name})"
            )
    return gaps


def _load_allowlist(path: Path) -> set[tuple[str, str]]:
    if not path.exists():
        return set()
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    entries = raw.get("entries", []) or []
    allowed: set[tuple[str, str]] = set()
    for i, entry in enumerate(entries):
        if (
            not isinstance(entry, dict)
            or not entry.get("file")
            or not entry.get("class")
            or not entry.get("reason")
        ):
            raise SystemExit(
                f"{path}: entry {i} requires non-empty file, class, reason"
            )
        allowed.add((entry["file"], entry["class"]))
    return allowed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=DEFAULT_SEARCH_ROOT)
    parser.add_argument("--allowlist", type=Path, default=DEFAULT_ALLOWLIST)
    args = parser.parse_args()

    tenant_models = _discover_tenant_scoped_models(args.root.resolve())
    if not tenant_models:
        print("lint-queryset-coverage: no tenant-scoped models found — vacuous run")
        return 1

    allowed = _load_allowlist(args.allowlist)
    gaps = []
    for gap in collect_gaps(args.root.resolve(), tenant_models):
        parts = gap.split(":", 2)
        rel_file = parts[0]
        class_name = parts[2].split(" (model=")[0].strip().rsplit(" ", 1)[-1]
        if (rel_file, class_name) in allowed:
            continue
        gaps.append(gap)

    try:
        allowlist_disp = str(args.allowlist.relative_to(REPO_ROOT))
    except ValueError:
        allowlist_disp = str(args.allowlist)

    if gaps:
        print(
            "::error::lint-queryset-coverage detected ViewSets over "
            "tenant-scoped models without a proven tenant filter. RLS "
            "arming (W1.20) must not bless implicit scoping — add the "
            f"filter or allowlist the class in {allowlist_disp} with a "
            "written reason.",
            file=sys.stderr,
        )
        for g in gaps:
            print(f"  - {g}", file=sys.stderr)
        return 1

    print(
        "lint-queryset-coverage: no unfiltered viewsets over tenant-scoped "
        f"models ({len(allowed)} allowlisted)."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
