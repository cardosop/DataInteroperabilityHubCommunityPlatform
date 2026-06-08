#!/usr/bin/env python3
"""Lint tenant-scoped model additions for missing RLS CREATE POLICY migrations.

This linter enforces a pairing rule for *new* tenant-scoped Django models:
if a model with a tenant foreign key is introduced, the same change set must
include a migration containing a CREATE POLICY statement that targets the
model's table (unless explicitly allowlisted).
"""

from __future__ import annotations

import argparse
import ast
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import yaml


APP_PY_SOURCE_PATH_RE = re.compile(
    r"^hub/apps/(?P<app>[a-zA-Z0-9_]+)/(?P<rel>[a-zA-Z0-9_/]+\.py)$"
)
MIGRATION_PATH_RE = re.compile(r"^hub/apps/[a-zA-Z0-9_]+/migrations/.*\.py$")


@dataclass(frozen=True)
class TenantModel:
    app_label: str
    model_name: str
    table_name: str
    file_path: str


def _run_git(repo_root: Path, args: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(repo_root), *args],
        text=True,
        capture_output=True,
        check=check,
    )


def _git_output(repo_root: Path, args: list[str]) -> str:
    result = _run_git(repo_root, args)
    return result.stdout.strip()


def _resolve_merge_base(repo_root: Path, base_ref: str) -> str:
    result = _run_git(repo_root, ["merge-base", base_ref, "HEAD"], check=False)
    if result.returncode != 0:
        raise RuntimeError(
            f"Unable to resolve merge-base for '{base_ref}'. stderr: {result.stderr.strip()}"
        )
    return result.stdout.strip()


def _changed_files_since(repo_root: Path, merge_base: str) -> list[str]:
    output = _git_output(repo_root, ["diff", "--name-only", f"{merge_base}..HEAD"])
    if not output:
        return []
    return [line.strip() for line in output.splitlines() if line.strip()]


def _file_at_ref(repo_root: Path, ref: str, path: str) -> str:
    result = _run_git(repo_root, ["show", f"{ref}:{path}"], check=False)
    if result.returncode != 0:
        return ""
    return result.stdout


def _is_models_model(base: ast.expr) -> bool:
    if isinstance(base, ast.Attribute):
        return base.attr == "Model"
    if isinstance(base, ast.Name):
        return base.id == "Model"
    return False


def _extract_meta_flag(meta_cls: ast.ClassDef, flag_name: str) -> bool | None:
    for stmt in meta_cls.body:
        if isinstance(stmt, ast.Assign):
            for target in stmt.targets:
                if isinstance(target, ast.Name) and target.id == flag_name:
                    try:
                        value = ast.literal_eval(stmt.value)
                    except Exception:
                        return None
                    if isinstance(value, bool):
                        return value
                    return None
    return None


def _extract_meta_db_table(meta_cls: ast.ClassDef) -> str | None:
    for stmt in meta_cls.body:
        if isinstance(stmt, ast.Assign):
            for target in stmt.targets:
                if isinstance(target, ast.Name) and target.id == "db_table":
                    try:
                        value = ast.literal_eval(stmt.value)
                    except Exception:
                        return None
                    if isinstance(value, str):
                        return value
                    return None
    return None


def _call_is_tenant_fk(call: ast.Call) -> bool:
    field_name: str | None = None
    if isinstance(call.func, ast.Attribute):
        field_name = call.func.attr
    elif isinstance(call.func, ast.Name):
        field_name = call.func.id

    if field_name not in {"ForeignKey", "OneToOneField"}:
        return False

    if call.args:
        first = call.args[0]
        if isinstance(first, ast.Name) and first.id == "Tenant":
            return True
        if isinstance(first, ast.Constant) and isinstance(first.value, str):
            if first.value in {"Tenant", "tenants.Tenant"} or first.value.endswith(".Tenant"):
                return True

    for keyword in call.keywords:
        if keyword.arg == "to":
            value = keyword.value
            if isinstance(value, ast.Name) and value.id == "Tenant":
                return True
            if isinstance(value, ast.Constant) and isinstance(value.value, str):
                if value.value in {"Tenant", "tenants.Tenant"} or value.value.endswith(".Tenant"):
                    return True

    return False


def _table_name_for_model(app_label: str, model_name: str, db_table: str | None) -> str:
    if db_table:
        return db_table
    return f"{app_label}_{model_name.lower()}"


def _tenant_models_from_source(source: str, app_label: str, file_path: str) -> dict[str, TenantModel]:
    if not source.strip():
        return {}

    tree = ast.parse(source)
    found: dict[str, TenantModel] = {}
    for node in tree.body:
        if not isinstance(node, ast.ClassDef):
            continue

        if not any(_is_models_model(base) for base in node.bases):
            continue

        meta_class = next(
            (child for child in node.body if isinstance(child, ast.ClassDef) and child.name == "Meta"),
            None,
        )
        if meta_class is not None:
            if _extract_meta_flag(meta_class, "abstract") is True:
                continue
            if _extract_meta_flag(meta_class, "managed") is False:
                continue
            db_table = _extract_meta_db_table(meta_class)
        else:
            db_table = None

        has_tenant_fk = False
        for stmt in node.body:
            if isinstance(stmt, ast.Assign):
                if isinstance(stmt.value, ast.Call) and _call_is_tenant_fk(stmt.value):
                    has_tenant_fk = True
            elif isinstance(stmt, ast.AnnAssign):
                if isinstance(stmt.value, ast.Call) and _call_is_tenant_fk(stmt.value):
                    has_tenant_fk = True
            if has_tenant_fk:
                break

        if has_tenant_fk:
            found[node.name] = TenantModel(
                app_label=app_label,
                model_name=node.name,
                table_name=_table_name_for_model(app_label, node.name, db_table),
                file_path=file_path,
            )

    return found


def _parse_allowlist(allowlist_path: Path) -> set[str]:
    if not allowlist_path.exists():
        return set()

    payload = yaml.safe_load(allowlist_path.read_text(encoding="utf-8"))
    if payload is None:
        return set()
    if not isinstance(payload, dict):
        raise RuntimeError("Allowlist file must contain a top-level mapping.")

    entries = payload.get("tables", [])
    if not isinstance(entries, list):
        raise RuntimeError("Allowlist key 'tables' must be a list.")

    allowed_tables: set[str] = set()
    for item in entries:
        if isinstance(item, str):
            allowed_tables.add(item.strip().lower())
            continue
        if isinstance(item, dict):
            table = item.get("table")
            if isinstance(table, str) and table.strip():
                allowed_tables.add(table.strip().lower())
                continue
        raise RuntimeError(
            "Allowlist entries must be either table strings or mappings with a 'table' key."
        )
    return allowed_tables


def _policy_matches_table(sql_text: str, table_name: str) -> bool:
    normalized_sql_text = sql_text.replace('\\"', '"').replace("\\'", "'")
    table_pattern = re.escape(table_name.lower())
    statement_pattern = re.compile(
        r"create\s+policy\b[\s\S]*?(?:;|$)",
        flags=re.IGNORECASE,
    )
    target_patterns = [
        re.compile(
            rf"\bon\s+(?:public\.)?[\"']?{table_pattern}[\"']?\b",
            flags=re.IGNORECASE,
        ),
        re.compile(
            rf"\bon\s+\"public\"\s*\.\s*\"{table_pattern}\"",
            flags=re.IGNORECASE,
        ),
    ]
    for statement_match in statement_pattern.finditer(normalized_sql_text):
        statement = statement_match.group(0)
        if any(pattern.search(statement) for pattern in target_patterns):
            return True
    return False


def _find_policy_tables_in_migrations(repo_root: Path, migration_paths: list[str], tables: set[str]) -> dict[str, str]:
    matches: dict[str, str] = {}
    if not tables:
        return matches

    remaining = set(tables)
    for migration_path in migration_paths:
        migration_file = repo_root / migration_path
        if not migration_file.exists():
            continue
        content = migration_file.read_text(encoding="utf-8", errors="ignore")
        for table in list(remaining):
            if _policy_matches_table(content, table):
                matches[table] = migration_path
                remaining.remove(table)
        if not remaining:
            break
    return matches


def lint_rls_policy_pairing(repo_root: Path, base_ref: str, allowlist_path: Path, fail_on_new: bool = False) -> int:
    merge_base = _resolve_merge_base(repo_root, base_ref)
    changed_files = _changed_files_since(repo_root, merge_base)

    changed_model_paths: list[str] = []
    for path in changed_files:
        match = APP_PY_SOURCE_PATH_RE.match(path)
        if not match:
            continue
        rel = match.group("rel")
        if rel.startswith("migrations/"):
            continue
        if rel.startswith("tests/") or "/tests/" in rel:
            continue
        changed_model_paths.append(path)
    changed_migration_paths = [p for p in changed_files if MIGRATION_PATH_RE.match(p)]

    new_tenant_models: list[TenantModel] = []
    for model_path in changed_model_paths:
        match = APP_PY_SOURCE_PATH_RE.match(model_path)
        if not match:
            continue
        app_label = match.group("app")
        current_path = repo_root / model_path
        if not current_path.exists():
            # File was deleted — skip (deleted files can't introduce new
            # tenant-scoped models needing RLS coverage).
            continue
        current_source = current_path.read_text(encoding="utf-8")
        base_source = _file_at_ref(repo_root, merge_base, model_path)
        current_models = _tenant_models_from_source(current_source, app_label, model_path)
        base_models = _tenant_models_from_source(base_source, app_label, model_path)

        for model_name, current_model in current_models.items():
            if model_name not in base_models:
                new_tenant_models.append(current_model)

    if not new_tenant_models:
        print(f"OK: no new tenant-scoped models found since {base_ref} ({merge_base[:12]}).")
        return 0

    allowlist_tables = _parse_allowlist(allowlist_path)
    table_names = {candidate.table_name for candidate in new_tenant_models}
    found_policies = _find_policy_tables_in_migrations(repo_root, changed_migration_paths, table_names)

    missing: list[TenantModel] = []
    for candidate in new_tenant_models:
        table_key = candidate.table_name.lower()
        if table_key in allowlist_tables:
            continue
        if table_key in found_policies:
            continue
        missing.append(candidate)

    print(
        f"Detected {len(new_tenant_models)} new tenant-scoped model(s) since {base_ref} ({merge_base[:12]})."
    )
    for candidate in new_tenant_models:
        print(
            f"  - {candidate.app_label}.{candidate.model_name} "
            f"(table: {candidate.table_name}, file: {candidate.file_path})"
        )

    if not missing:
        print("OK: every new tenant-scoped model has a CREATE POLICY migration or allowlist entry.")
        if fail_on_new and new_tenant_models:
            print(
                f"\nINFO: --fail-on-new is set. {len(new_tenant_models)} new model(s) detected. "
                "PR must include RLS policy for each."
            )
            return 1
        return 0

    print("\nERROR: missing CREATE POLICY coverage for new tenant-scoped tables:")
    for candidate in missing:
        print(
            f"  - {candidate.table_name} (model {candidate.app_label}.{candidate.model_name})"
        )
    print(
        "\nAdd a migration with CREATE POLICY ... ON <table> ... "
        "or add a justified exception to the allowlist."
    )
    return 1


def _default_base_ref() -> str:
    github_base_ref = os.environ.get("GITHUB_BASE_REF")
    if github_base_ref:
        return f"origin/{github_base_ref}"
    return "origin/main"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Lint new tenant-scoped models for paired RLS CREATE POLICY migrations.",
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path.cwd(),
        help="Repository root path (defaults to current working directory).",
    )
    parser.add_argument(
        "--base-ref",
        default=_default_base_ref(),
        help="Git base ref used for diff/merge-base (default: origin/main or origin/$GITHUB_BASE_REF).",
    )
    parser.add_argument(
        "--fail-on-new",
        action="store_true",
        default=False,
        help="TR.M.4 — exit non-zero when any new tenant-scoped model is found "
             "(regardless of whether it has RLS policy). Use for CI enforcement "
             "that every new model ships its RLS policy in the same PR.",
    )
    parser.add_argument(
        "--allowlist",
        type=Path,
        default=Path("lint/rls-policies-allowlist.yml"),
        help="Path to YAML allowlist file.",
    )
    args = parser.parse_args()

    repo_root = args.repo_root.resolve()
    allowlist_path = args.allowlist
    if not allowlist_path.is_absolute():
        allowlist_path = repo_root / allowlist_path

    try:
        return lint_rls_policy_pairing(
            repo_root, args.base_ref, allowlist_path,
            fail_on_new=args.fail_on_new,
        )
    except Exception as exc:
        print(f"ERROR: lint execution failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
