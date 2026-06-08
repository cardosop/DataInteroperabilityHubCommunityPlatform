"""
Phase 260.7.H — KMS key rotation policy tests (closes pass-3 B3-6).

Pins three contracts:

1. **IaC contract**: every ``aws_kms_key`` resource declared in
   ``infrastructure/terraform/modules/kms/main.tf`` MUST set
   ``enable_key_rotation = true``. A future PR that removes the flag
   (or adds a new key without it) fails this test BEFORE merge.

2. **Runbook presence + content**: ``docs/runbooks/kms-rotation.md``
   exists and documents the 365-day rotation cadence + the
   ``meshant-file-storage`` key contract for the future when an S3
   CMK is added.

3. **Cross-reference**: the runbook references the Terraform module
   path so future readers can navigate from the policy doc to the
   IaC source of truth without grepping.

These are STATIC checks — no AWS API calls, no Terraform plan, no
mocks. The tests parse the IaC source files directly and assert on
their content. Runs on every CI build.
"""
from __future__ import annotations

import glob
import os
import re

PROJECT_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..")
)

KMS_MODULE_PATH = os.path.join(
    PROJECT_ROOT,
    "infrastructure",
    "terraform",
    "modules",
    "kms",
    "main.tf",
)
TERRAFORM_ROOT = os.path.join(PROJECT_ROOT, "infrastructure", "terraform")
RUNBOOK_PATH = os.path.join(
    PROJECT_ROOT,
    "docs",
    "runbooks",
    "kms-rotation.md",
)


def _all_terraform_files() -> list[str]:
    """Return every ``.tf`` file under ``infrastructure/terraform/``,
    excluding ``.terraform/`` cache dirs that local ``terraform init``
    materialises (they contain symlinks-as-copies of upstream provider
    code that would generate spurious matches).
    """
    paths = []
    for path in sorted(glob.glob(
        os.path.join(TERRAFORM_ROOT, "**", "*.tf"), recursive=True,
    )):
        # Skip the local provider/module cache that ``terraform init``
        # creates — contains copies of provider source we don't own.
        if "/.terraform/" in path:
            continue
        paths.append(path)
    return paths


# ---------------------------------------------------------------------------
# Terraform IaC contract
# ---------------------------------------------------------------------------


def _read(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def _extract_kms_key_blocks(tf_source: str) -> list[tuple[str, str]]:
    """Return ``[(resource_name, body), ...]`` for every ``aws_kms_key``
    resource declared in *tf_source*.

    Body matching uses a brace-balanced regex (no nested-resource
    support — Terraform doesn't allow nested `resource` blocks anyway,
    so a simple "find first matching `}` at column 0" is sufficient).
    """
    blocks = []
    # Pattern: resource "aws_kms_key" "<name>" {
    pattern = re.compile(
        r'resource\s+"aws_kms_key"\s+"([^"]+)"\s*\{', re.MULTILINE
    )
    for match in pattern.finditer(tf_source):
        name = match.group(1)
        # Find the matching closing `}` by walking forward and
        # counting braces. Start at the open `{` immediately after
        # the match.
        body_start = match.end()
        depth = 1
        i = body_start
        while i < len(tf_source) and depth > 0:
            c = tf_source[i]
            if c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
            i += 1
        body = tf_source[body_start : i - 1]
        blocks.append((name, body))
    return blocks


def test_terraform_kms_module_exists():
    """Phase 260.7.H — the KMS module file the runbook references
    MUST exist at the expected path. A future repository-restructure
    that moves the module would break the runbook's link AND this
    test (which is the regression guard)."""
    assert os.path.isfile(KMS_MODULE_PATH), (
        f"KMS Terraform module not found at {KMS_MODULE_PATH!r}; the "
        "runbook at docs/runbooks/kms-rotation.md references this path"
    )


def test_all_platform_kms_keys_have_rotation_enabled():
    """Phase 260.7.H — every ``aws_kms_key`` resource ANYWHERE under
    ``infrastructure/terraform/`` MUST set ``enable_key_rotation = true``.
    This is the LOAD-BEARING contract of the rotation policy: AWS KMS
    rotates symmetric CMKs on a 365-day cadence ONLY when this flag
    is set.

    Phase 260.7.H.R1 GAP-A — fixed scope to walk ALL ``.tf`` files,
    not just the canonical ``modules/kms/main.tf``. Pre-R1 the test
    only validated the kms module, missing the legacy
    ``infrastructure/terraform/s3/main.tf::aws_kms_key.meshant_s3``
    declaration (which fortunately has rotation enabled today, but a
    future regression there would have been silent). Same shape of
    bug as 260.7.G.R1 GAP-A: the audit found ONE call site of a
    contract, the implementation fixed that one, the symmetric
    second site was overlooked.

    The test is intentionally static (parses Terraform source, no
    AWS API call) so it runs in any CI environment without AWS
    credentials. Catches the regression class where a future PR
    either adds a new ``aws_kms_key`` without rotation OR removes
    the flag from an existing one — anywhere in the IaC tree.
    """
    tf_files = _all_terraform_files()
    assert tf_files, (
        f"No .tf files found under {TERRAFORM_ROOT!r}. The IaC tree "
        "may have been restructured; update this test's traversal."
    )

    found_keys: list[tuple[str, str, str]] = []  # (relpath, name, body)
    for path in tf_files:
        src = _read(path)
        for name, body in _extract_kms_key_blocks(src):
            relpath = os.path.relpath(path, PROJECT_ROOT)
            found_keys.append((relpath, name, body))

    assert found_keys, (
        "No aws_kms_key resources found anywhere in "
        f"{TERRAFORM_ROOT!r}. The platform must declare at least one "
        "CMK (the existing app_encryption key); if all keys have been "
        "removed, this test should be deleted with explicit reasoning."
    )

    failures: list[str] = []
    for relpath, name, body in found_keys:
        # Match: enable_key_rotation = true
        # Tolerate whitespace + boolean casing.
        match = re.search(
            r'enable_key_rotation\s*=\s*(true|false)',
            body,
            re.IGNORECASE,
        )
        if match is None:
            failures.append(
                f"  - {relpath}::aws_kms_key.{name} does NOT declare "
                "enable_key_rotation"
            )
            continue
        value = match.group(1).lower()
        if value != "true":
            failures.append(
                f"  - {relpath}::aws_kms_key.{name} has "
                f"enable_key_rotation = {value!r} (MUST be true)"
            )

    assert not failures, (
        "Phase 260.7.H runbook policy violation — every customer-managed "
        "KMS key MUST set enable_key_rotation = true:\n"
        + "\n".join(failures)
    )


# ---------------------------------------------------------------------------
# Runbook presence + content
# ---------------------------------------------------------------------------


def test_kms_rotation_runbook_exists():
    """Phase 260.7.H.2 — the runbook at the expected path MUST exist.
    Pins the file's location so future audits can grep for it without
    knowing the exact name."""
    assert os.path.isfile(RUNBOOK_PATH), (
        f"KMS rotation runbook not found at {RUNBOOK_PATH!r}; "
        "Phase 260.7.H.2 mandates this exact filename"
    )


def test_runbook_documents_365_day_cadence():
    """Phase 260.7.H.2 — the runbook MUST document the 365-day rotation
    cadence. AWS KMS rotates symmetric CMKs every 365 days (this is
    AWS's fixed cadence; the platform cannot configure a different
    interval). Pinning the documentation surface here so a future
    edit that drops the cadence reference fails CI."""
    src = _read(RUNBOOK_PATH)
    assert "365-day" in src or "365 days" in src, (
        "Runbook MUST document the 365-day rotation cadence "
        "(per Phase 260.7.H.2 spec). The cadence is AWS-fixed; the "
        "documentation is the operational surface that operators "
        "consult to confirm the policy."
    )


def test_runbook_documents_meshant_file_storage_key_contract():
    """Phase 260.7.H.1 — the runbook MUST reference the
    ``meshant-file-storage`` key contract (the future S3 CMK). Even
    though the key doesn't exist in IaC TODAY (the S3 bucket uses
    SSE-S3 / AES256), the runbook pins the policy so when the key IS
    added, the implementer follows the documented pattern
    (enable_key_rotation = true)."""
    src = _read(RUNBOOK_PATH)
    assert "meshant-file-storage" in src, (
        "Runbook MUST reference the ``meshant-file-storage`` key name "
        "(per Phase 260.7.H.1 spec). The reference doubles as the "
        "future-state contract: when a CMK for S3 file-storage is "
        "added, it MUST follow the documented rotation policy."
    )


def test_runbook_links_to_terraform_module():
    """Phase 260.7.H — the runbook MUST link to the Terraform module
    path so readers can navigate from policy → IaC source of truth.
    Catches the doc-drift class where the IaC moves but the runbook
    is left stale."""
    src = _read(RUNBOOK_PATH)
    # Match either a markdown link or a plain path reference.
    assert "infrastructure/terraform/modules/kms" in src, (
        "Runbook MUST reference the Terraform KMS module path "
        "(infrastructure/terraform/modules/kms) so readers can "
        "navigate from the policy doc to the IaC source of truth."
    )


def test_runbook_documents_verification_command():
    """Phase 260.7.H — the runbook MUST document the AWS CLI command
    operators run to verify rotation status. Operational doc must
    include the actual command (not just describe what to do)."""
    src = _read(RUNBOOK_PATH)
    assert "aws kms get-key-rotation-status" in src, (
        "Runbook MUST include the ``aws kms get-key-rotation-status`` "
        "verification command — operators consult the doc to copy-paste "
        "the command, not paraphrase it from a description."
    )


# ---------------------------------------------------------------------------
# Cross-reference: the runbook's claim about the existing key matches
# the IaC's actual state.
# ---------------------------------------------------------------------------


def test_runbook_app_encryption_key_claim_matches_terraform():
    """The runbook claims that the existing ``app_encryption`` key has
    rotation enabled. Verify the Terraform source actually reflects
    that — catches the drift where the runbook's coverage matrix says
    "✅ Enabled" but the IaC was changed to disable rotation."""
    src = _read(KMS_MODULE_PATH)
    blocks = _extract_kms_key_blocks(src)
    by_name = {name: body for name, body in blocks}

    assert "app_encryption" in by_name, (
        "Terraform module is expected to declare ``aws_kms_key.app_encryption`` "
        "(per the runbook's coverage matrix). If the resource was renamed, "
        "update both the runbook and this test together."
    )
    body = by_name["app_encryption"]
    assert re.search(
        r'enable_key_rotation\s*=\s*true', body, re.IGNORECASE,
    ), (
        "Runbook claims ``app_encryption`` has rotation enabled, but the "
        "Terraform source disagrees — the runbook is stale OR the IaC "
        "regressed. Investigate which side is wrong."
    )
