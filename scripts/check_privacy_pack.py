#!/usr/bin/env python3
"""
GATE-46 (pilot-readiness 3.3) — the pilot privacy-pack contract checker.

The Week-3 privacy pack (docs/runbooks/PILOT_PRIVACY_PACK.md) must:
- contain the five mandated sections (DPIA run, RoPA run, DPA, exit/
  deletion path, sign-off) and declare the pilot tenant slug
  (``pilot-co``);
- evidence an APPROVED DPIA — record id, regime, a real ``DpiaStatus``
  value, a real ``ResidualRiskLevel`` value (AST-parsed from
  hub/apps/dpia/models.py — no drift, no invented vocabulary);
- evidence a COMPLETED RoPA generation — generation id, regulation, a
  real ``RopaGenerationStatus`` value, and the artefact's sha256
  (AST-parsed from hub/apps/ropa/models.py);
- evidence an ACTIVE DPA whose document hash equals the REAL sha256 of
  docs/compliance/dpa-addendum.md — the governance record is pinned to
  the actual legal addendum (real ``ProcessorAgreementStatus`` /
  ``ProcessorAgreementType`` vocabulary, AST-parsed from
  hub/apps/processor_agreements/models.py);
- document the erasure path by naming the real management commands
  (files must exist under hub/apps/*/management/commands/) and real URL
  fragments (AST-parsed from hub/apps/gdpr/urls.py and
  hub/apps/tenants/admin_urls.py) — a documented surface that does not
  exist in source is a problem;
- record the sign-off with dates and both parties, without TBD/TODO
  placeholders.

Exit 0 when the pack satisfies the contract; 1 otherwise, each problem
named.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import re
import sys
from pathlib import Path

PACK_DEFAULT = Path("docs/runbooks/PILOT_PRIVACY_PACK.md")
ADDENDUM_DEFAULT = Path("docs/compliance/dpa-addendum.md")
DPIA_MODELS_DEFAULT = Path("hub/apps/dpia/models.py")
ROPA_MODELS_DEFAULT = Path("hub/apps/ropa/models.py")
PA_MODELS_DEFAULT = Path("hub/apps/processor_agreements/models.py")
GDPR_URLS_DEFAULT = Path("hub/apps/gdpr/urls.py")
GDPR_VIEWS_DEFAULT = Path("hub/apps/gdpr/views.py")
ADMIN_URLS_DEFAULT = Path("hub/apps/tenants/admin_urls.py")
COMMAND_DIRS_DEFAULT = (
    Path("hub/apps/files/management/commands"),
    Path("hub/apps/tenants/management/commands"),
)

PILOT_TENANT_SLUG = "pilot-co"

REQUIRED_SECTIONS = (
    "## DPIA run",
    "## RoPA run",
    "## Data Processing Agreement",
    "## Exit and deletion (erasure) path",
    "## Sign-off",
)

# The erasure machinery the pack's exit/deletion path MUST name — every
# one verified against the real source (file existence / URL module).
ERASURE_COMMANDS = (
    "delete_files_for_tenant",
    "delete_files_for_user",
    "tenant_hard_delete_sweep",
)

_PLACEHOLDER_RE = re.compile(r"\b(TBD|TODO|PLACEHOLDER|XXX)\b", re.I)
_UUID_RE = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")
_SHA256_RE = re.compile(r"\b[0-9a-f]{64}\b")
_DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")


def _section(text: str, heading: str) -> str:
    """The text between a ``## heading`` line and the next one."""
    marker = text.split(heading, 1)
    if len(marker) < 2:
        return ""
    return marker[1].split("## ", 1)[0]


def _evidence_table(section_text: str) -> dict[str, str]:
    """Parse the ``| Field | Value |`` evidence rows of a section."""
    out: dict[str, str] = {}
    for line in section_text.splitlines():
        match = re.match(r"\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*$", line)
        if match:
            field, value = match.group(1).strip(), match.group(2).strip()
            out[field.casefold()] = value
    return out


def _enum_members(path: Path, class_name: str) -> set[str]:
    """Enum member values, AST-parsed from the model module (no Django
    import — the TextChoices classes are module-level literals)."""
    if not path.exists():
        return set()
    tree = ast.parse(path.read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            members: set[str] = set()
            for stmt in node.body:
                if (
                    isinstance(stmt, ast.Assign)
                    and isinstance(stmt.value, ast.Tuple)
                    and stmt.value.elts
                    and isinstance(stmt.value.elts[0], ast.Constant)
                    and isinstance(stmt.value.elts[0].value, str)
                ):
                    members.add(stmt.value.elts[0].value)
            return members
    return set()


def _url_fragments(path: Path) -> set[str]:
    """First-argument string literals of every path()/re_path() call."""
    if not path.exists():
        return set()
    tree = ast.parse(path.read_text())
    out: set[str] = set()
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id in {"path", "re_path"}
            and node.args
            and isinstance(node.args[0], ast.Constant)
            and isinstance(node.args[0].value, str)
        ):
            out.add(node.args[0].value)
    return out


def _action_url_paths(path: Path) -> set[str]:
    """``url_path=`` literals of @action-decorated DRF routes — the gdpr
    surface registers its endpoints through the router, not path() calls,
    so the real fragments live in the views module."""
    if not path.exists():
        return set()
    tree = ast.parse(path.read_text())
    out: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Name) and func.id == "action":
            for kw in node.keywords:
                if (
                    kw.arg == "url_path"
                    and isinstance(kw.value, ast.Constant)
                    and isinstance(kw.value.value, str)
                ):
                    out.add(kw.value.value)
    return out


def check(
    pack_path: Path,
    addendum_path: Path,
    dpia_models: Path,
    ropa_models: Path,
    pa_models: Path,
    gdpr_urls: Path,
    gdpr_views: Path,
    admin_urls: Path,
    command_dirs: tuple[Path, ...],
) -> list[str]:
    problems: list[str] = []
    if not pack_path.exists():
        return [f"privacy pack missing: {pack_path}"]
    text = pack_path.read_text()

    for section in REQUIRED_SECTIONS:
        if section not in text:
            problems.append(f"missing mandated section {section!r}")
    if PILOT_TENANT_SLUG not in text:
        problems.append(
            f"pilot tenant slug {PILOT_TENANT_SLUG!r} not declared in the pack"
        )
    for match in _PLACEHOLDER_RE.findall(text):
        problems.append(f"unresolved placeholder {match!r}")

    dpia_statuses = _enum_members(dpia_models, "DpiaStatus")
    risk_levels = _enum_members(dpia_models, "ResidualRiskLevel")
    ropa_statuses = _enum_members(ropa_models, "RopaGenerationStatus")
    pa_statuses = _enum_members(pa_models, "ProcessorAgreementStatus")
    pa_types = _enum_members(pa_models, "ProcessorAgreementType")

    # ── DPIA run ──────────────────────────────────────────────────────
    dpia = _evidence_table(_section(text, "## DPIA run"))
    record_id = dpia.get("record id", "")
    if not _UUID_RE.fullmatch(record_id):
        problems.append(f"DPIA section: 'Record id' is not a UUID (got {record_id!r})")
    dpia_status = dpia.get("status", "")
    if dpia_status not in dpia_statuses:
        problems.append(
            f"DPIA status {dpia_status!r} is not a real DpiaStatus member "
            f"(known: {sorted(dpia_statuses)})"
        )
    elif dpia_status != "APPROVED":
        problems.append(f"DPIA status must be APPROVED (got {dpia_status!r})")
    risk = dpia.get("risk residual", "")
    if risk not in risk_levels:
        problems.append(
            f"DPIA 'Risk residual' {risk!r} is not a real ResidualRiskLevel "
            f"member (known: {sorted(risk_levels)})"
        )
    if not dpia.get("regime"):
        problems.append("DPIA section: 'Regime' evidence row missing")

    # ── RoPA run ──────────────────────────────────────────────────────
    ropa = _evidence_table(_section(text, "## RoPA run"))
    generation_id = ropa.get("generation id", "")
    if not _UUID_RE.fullmatch(generation_id):
        problems.append(
            f"RoPA section: 'Generation id' is not a UUID (got {generation_id!r})"
        )
    ropa_status = ropa.get("status", "")
    if ropa_status not in ropa_statuses:
        problems.append(
            f"RoPA status {ropa_status!r} is not a real RopaGenerationStatus "
            f"member (known: {sorted(ropa_statuses)})"
        )
    elif ropa_status != "COMPLETED":
        problems.append(f"RoPA status must be COMPLETED (got {ropa_status!r})")
    if ropa.get("regulation", "").upper() != "GDPR":
        problems.append("RoPA section: 'Regulation' must be GDPR")
    artifact_sha = ropa.get("artifact sha256", "")
    if not _SHA256_RE.fullmatch(artifact_sha):
        problems.append(
            f"RoPA section: 'Artifact sha256' is not a 64-char hex digest "
            f"(got {artifact_sha!r})"
        )

    # ── DPA ───────────────────────────────────────────────────────────
    dpa = _evidence_table(_section(text, "## Data Processing Agreement"))
    agreement_id = dpa.get("agreement id", "")
    if not _UUID_RE.fullmatch(agreement_id):
        problems.append(
            f"DPA section: 'Agreement id' is not a UUID (got {agreement_id!r})"
        )
    agreement_type = dpa.get("type", "")
    if agreement_type not in pa_types:
        problems.append(
            f"DPA 'Type' {agreement_type!r} is not a real ProcessorAgreementType "
            f"member (known: {sorted(pa_types)})"
        )
    elif agreement_type != "DPA":
        problems.append(f"DPA 'Type' must be DPA (got {agreement_type!r})")
    dpa_status = dpa.get("status", "")
    if dpa_status not in pa_statuses:
        problems.append(
            f"DPA status {dpa_status!r} is not a real ProcessorAgreementStatus "
            f"member (known: {sorted(pa_statuses)})"
        )
    elif dpa_status != "ACTIVE":
        problems.append(f"DPA status must be ACTIVE (got {dpa_status!r})")
    document_hash = dpa.get("document hash", "")
    if not _SHA256_RE.fullmatch(document_hash):
        problems.append(
            f"DPA section: 'Document hash' is not a 64-char hex digest "
            f"(got {document_hash!r})"
        )
    elif not addendum_path.exists():
        problems.append(f"DPA addendum missing: {addendum_path}")
    else:
        real_sha = hashlib.sha256(addendum_path.read_bytes()).hexdigest()
        if document_hash.lower() != real_sha:
            problems.append(
                f"DPA 'Document hash' does not match the sha256 of "
                f"{addendum_path} (pack says {document_hash}, file is {real_sha})"
            )

    # ── Exit and deletion (erasure) path ──────────────────────────────
    erasure = _section(text, "## Exit and deletion (erasure) path")
    # The surface table's second column holds the documented path; the
    # first column is the human name. Parse rows preserving both columns.
    documented_paths = [
        match.group(2).strip()
        for match in (
            re.match(r"\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*$", line)
            for line in erasure.splitlines()
        )
        # Skip the header row ("Surface") and separator rows ("---").
        if match
        and match.group(1).strip() != "Surface"
        and set(match.group(1).strip()) != {"-"}
    ]
    gdpr_fragments = _url_fragments(gdpr_urls) | _action_url_paths(gdpr_views)
    admin_fragments = _url_fragments(admin_urls)
    if not gdpr_fragments:
        problems.append(
            f"no URL fragments extracted from {gdpr_urls} / {gdpr_views}"
        )
    if not admin_fragments:
        problems.append(f"no URL fragments extracted from {admin_urls}")
    real_fragments = {f.rstrip("/") for f in gdpr_fragments | admin_fragments}
    real_names = set(ERASURE_COMMANDS)
    # Doc → source: every documented surface must exist (command file or
    # registered URL fragment). The pack documents FULL paths (with the
    # /api/v1/admin/ mount prefix) while the URL modules register bare
    # fragments, so resolution is segment-boundary suffix matching.
    def _resolves(candidate: str, fragment: str) -> bool:
        return candidate == fragment or candidate.endswith(f"/{fragment}")

    for path in documented_paths:
        if path in real_names:
            continue
        candidate = path.removeprefix("/api/v1/").rstrip("/")
        if not any(_resolves(candidate, f) for f in real_fragments):
            problems.append(
                f"erasure surface {path!r} is not registered in source "
                f"(known fragments: {sorted(real_fragments)})"
            )
    # Source → doc: every real GDPR surface must be documented (the gdpr
    # actions ARE the erasure/export surface); the admin module registers
    # the whole platform-admin API, so at least ONE admin fragment (the
    # tenant-deletion surface) must be documented.
    for name in ERASURE_COMMANDS:
        if not any((d / f"{name}.py").exists() for d in command_dirs):
            problems.append(f"erasure command {name!r} does not exist in source")
        if not any(name in path for path in documented_paths):
            problems.append(f"erasure path does not document the {name!r} command")
    gdpr_only = _url_fragments(gdpr_urls) | _action_url_paths(gdpr_views)
    for fragment in sorted(gdpr_only):
        if not any(fragment in path for path in documented_paths):
            problems.append(
                f"erasure path does not document the real gdpr surface "
                f"{fragment!r} (registered in {gdpr_views})"
            )
    if not any(
        f.rstrip("/") in path for f in admin_fragments for path in documented_paths
    ):
        problems.append(
            f"erasure path does not document the admin tenant-deletion surface "
            f"(registered in {admin_urls})"
        )

    # ── Sign-off ──────────────────────────────────────────────────────
    signoff = _section(text, "## Sign-off")
    if not _DATE_RE.search(signoff):
        problems.append("Sign-off section has no date")
    if "Meshant" not in signoff or "Customer" not in signoff:
        problems.append("Sign-off section must record both parties (Meshant + Customer)")
    return problems


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, default=PACK_DEFAULT)
    parser.add_argument("--addendum", type=Path, default=ADDENDUM_DEFAULT)
    parser.add_argument("--dpia-models", type=Path, default=DPIA_MODELS_DEFAULT)
    parser.add_argument("--ropa-models", type=Path, default=ROPA_MODELS_DEFAULT)
    parser.add_argument("--pa-models", type=Path, default=PA_MODELS_DEFAULT)
    parser.add_argument("--gdpr-urls", type=Path, default=GDPR_URLS_DEFAULT)
    parser.add_argument("--gdpr-views", type=Path, default=GDPR_VIEWS_DEFAULT)
    parser.add_argument("--admin-urls", type=Path, default=ADMIN_URLS_DEFAULT)
    parser.add_argument("--command-dirs", type=Path, nargs="+", default=COMMAND_DIRS_DEFAULT)
    args = parser.parse_args()
    problems = check(
        args.report,
        args.addendum,
        args.dpia_models,
        args.ropa_models,
        args.pa_models,
        args.gdpr_urls,
        args.gdpr_views,
        args.admin_urls,
        tuple(args.command_dirs),
    )
    if problems:
        for problem in problems:
            print(f"FAIL: {problem}")
        print(f"GATE-46 FAILED: {len(problems)} problem(s)")
        sys.exit(1)
    print(f"GATE-46 PASSED: {args.report} satisfies the privacy-pack contract")
    sys.exit(0)


if __name__ == "__main__":
    main()
