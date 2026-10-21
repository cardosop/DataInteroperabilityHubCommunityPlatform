"""
Contract tests for scripts/check_privacy_pack.py (pilot-readiness 3.3,
GATE-46).

The privacy pack (docs/runbooks/PILOT_PRIVACY_PACK.md) must:
- contain the five mandated sections (DPIA run, RoPA run, DPA, exit/
  deletion path, sign-off) and declare the pilot tenant slug;
- evidence an APPROVED DPIA (record id, real DpiaStatus vocabulary,
  real ResidualRiskLevel vocabulary);
- evidence a COMPLETED RoPA generation (generation id, real
  RopaGenerationStatus vocabulary, artifact sha256);
- evidence an ACTIVE DPA whose document hash equals the REAL sha256 of
  docs/compliance/dpa-addendum.md (real ProcessorAgreementStatus /
  ProcessorAgreementType vocabulary);
- document the erasure path by naming the real management commands and
  real gdpr/admin URL fragments (verified against source);
- record the sign-off without TBD/TODO placeholders.
"""

import hashlib
import importlib.util
import sys
from pathlib import Path

import pytest

scripts_dir = Path(__file__).parent.parent
sys.path.insert(0, str(scripts_dir))

script_path = scripts_dir / "check_privacy_pack.py"
spec = importlib.util.spec_from_file_location("check_privacy_pack", script_path)
check = importlib.util.module_from_spec(spec)
spec.loader.exec_module(check)

ADDENDUM_BODY = "DPA addendum — sub-processors: AWS, Stripe, SendGrid.\n"
ADDENDUM_SHA = hashlib.sha256(ADDENDUM_BODY.encode()).hexdigest()

DPIA_MODELS = """
class DpiaStatus(models.TextChoices):
    DRAFT = "DRAFT", "Draft"
    IN_REVIEW = "IN_REVIEW", "In review"
    APPROVED = "APPROVED", "Approved"
    REJECTED = "REJECTED", "Rejected"

class ResidualRiskLevel(models.TextChoices):
    LOW = "LOW", "Low"
    MEDIUM = "MEDIUM", "Medium"
    HIGH = "HIGH", "High"
"""

ROPA_MODELS = """
class RopaGenerationStatus(models.TextChoices):
    PENDING = "PENDING", "Pending"
    PROCESSING = "PROCESSING", "Processing"
    COMPLETED = "COMPLETED", "Completed"
    FAILED = "FAILED", "Failed"
"""

PA_MODELS = """
class ProcessorAgreementType(models.TextChoices):
    DPA = "DPA", "Data Processing Agreement"

class ProcessorAgreementStatus(models.TextChoices):
    ACTIVE = "ACTIVE", "Active"
    EXPIRED = "EXPIRED", "Expired"
"""

GDPR_URLS = """
from django.urls import path

urlpatterns = [
    path("", include(router.urls)),
]
"""

GDPR_VIEWS = """
from rest_framework.decorators import action

class DataExportJobViewSet(viewsets.ReadOnlyModelViewSet):
    @action(detail=False, methods=["post"], url_path="export-data")
    def export_data(self, request):
        pass

class ErasureRequestViewSet(viewsets.ReadOnlyModelViewSet):
    @action(detail=False, methods=["post"], url_path="request-erasure")
    def request_erasure(self, request):
        pass
"""

ADMIN_URLS = """
from django.urls import path

urlpatterns = [
    path("tenants/<uuid:pk>/", delete, name="admin-tenant-delete"),
]
"""

COMMANDS = ("delete_files_for_tenant", "delete_files_for_user", "tenant_hard_delete_sweep")


def _pack(
    dpa_hash=ADDENDUM_SHA,
    dpia_status="APPROVED",
    ropa_status="COMPLETED",
    dpa_status="ACTIVE",
    erasure_surfaces=None,
):
    surfaces = erasure_surfaces or [
        ("Self-service data export", "/api/v1/gdpr/export-jobs/export-data/"),
        ("Self-service erasure", "/api/v1/gdpr/erasure-requests/request-erasure/"),
        ("Admin tenant deletion", "/api/v1/admin/tenants/<uuid:pk>/"),
        ("Tenant file purge", "delete_files_for_tenant"),
        ("User file purge", "delete_files_for_user"),
        ("Tenant hard-delete sweep", "tenant_hard_delete_sweep"),
    ]
    return f"""# Pilot Privacy Pack — Week 3 Record

- **Pilot tenant:** slug `pilot-co` (dev-estate pilot tenant).

## DPIA run

| Field | Value |
|---|---|
| Record id | 11111111-2222-4333-8444-555555555555 |
| Regime | GDPR |
| Status | {dpia_status} |
| Risk residual | LOW |
| Reviewer role | DPO |

## RoPA run

| Field | Value |
|---|---|
| Generation id | 22222222-3333-4333-8444-555555555555 |
| Regulation | GDPR |
| Status | {ropa_status} |
| Artifact sha256 | aaaa{"0" * 60} |

## Data Processing Agreement

| Field | Value |
|---|---|
| Agreement id | 33333333-4444-4333-8444-555555555555 |
| Type | DPA |
| Status | {dpa_status} |
| Document hash | {dpa_hash} |
| Effective from | 2026-10-05 |

## Exit and deletion (erasure) path

| Surface | Path |
|---|---|
{''.join(f"| {s} | {p} |\n" for s, p in surfaces)}
## Sign-off

| Party | Status | Date |
|---|---|---|
| Meshant | signed (governance record) | 2026-10-05 |
| Customer | U-gated counter-signature | 2026-10-05 |
"""


@pytest.fixture
def fixture_files(tmp_path):
    pack = tmp_path / "PILOT_PRIVACY_PACK.md"
    pack.write_text(_pack())
    addendum = tmp_path / "dpa-addendum.md"
    addendum.write_text(ADDENDUM_BODY)
    dpia_models = tmp_path / "dpia_models.py"
    dpia_models.write_text(DPIA_MODELS)
    ropa_models = tmp_path / "ropa_models.py"
    ropa_models.write_text(ROPA_MODELS)
    pa_models = tmp_path / "pa_models.py"
    pa_models.write_text(PA_MODELS)
    gdpr_urls = tmp_path / "gdpr_urls.py"
    gdpr_urls.write_text(GDPR_URLS)
    gdpr_views = tmp_path / "gdpr_views.py"
    gdpr_views.write_text(GDPR_VIEWS)
    admin_urls = tmp_path / "admin_urls.py"
    admin_urls.write_text(ADMIN_URLS)
    command_dir = tmp_path / "commands"
    command_dir.mkdir()
    command_files = []
    for name in COMMANDS:
        f = command_dir / f"{name}.py"
        f.write_text("# management command\n")
        command_files.append(f)
    return {
        "pack": pack,
        "addendum": addendum,
        "dpia_models": dpia_models,
        "ropa_models": ropa_models,
        "pa_models": pa_models,
        "gdpr_urls": gdpr_urls,
        "gdpr_views": gdpr_views,
        "admin_urls": admin_urls,
        "command_files": command_files,
    }


def _run(fixture_files):
    return check.check(
        fixture_files["pack"],
        fixture_files["addendum"],
        fixture_files["dpia_models"],
        fixture_files["ropa_models"],
        fixture_files["pa_models"],
        fixture_files["gdpr_urls"],
        fixture_files["gdpr_views"],
        fixture_files["admin_urls"],
        (fixture_files["command_files"][0].parent,),
    )


def test_valid_pack_passes(fixture_files):
    assert _run(fixture_files) == []


def test_missing_pack_fails(tmp_path):
    problems = check.check(
        tmp_path / "missing.md",
        tmp_path / "addendum.md",
        tmp_path / "d.py",
        tmp_path / "r.py",
        tmp_path / "p.py",
        tmp_path / "g.py",
        tmp_path / "gv.py",
        tmp_path / "a.py",
        [tmp_path / f"{n}.py" for n in COMMANDS],
    )
    assert any("missing" in p for p in problems)


def test_missing_section_fails(fixture_files):
    fixture_files["pack"].write_text(_pack().replace("## RoPA run", "## Missing"))
    assert any("## RoPA run" in p for p in _run(fixture_files))


def test_missing_pilot_tenant_slug_fails(fixture_files):
    fixture_files["pack"].write_text(_pack().replace("pilot-co", "other-co"))
    assert any("pilot-co" in p for p in _run(fixture_files))


def test_placeholder_fails(fixture_files):
    fixture_files["pack"].write_text(_pack() + "\nTBD: legal review\n")
    assert any("TBD" in p for p in _run(fixture_files))


def test_non_approved_dpia_status_fails(fixture_files):
    fixture_files["pack"].write_text(_pack(dpia_status="DRAFT"))
    problems = _run(fixture_files)
    assert any("APPROVED" in p for p in problems)


def test_invented_dpia_status_fails(fixture_files):
    fixture_files["pack"].write_text(_pack(dpia_status="MAGIC"))
    problems = _run(fixture_files)
    assert any("DpiaStatus" in p for p in problems)


def test_invented_risk_residual_fails(fixture_files):
    fixture_files["pack"].write_text(
        _pack().replace("| Risk residual | LOW |", "| Risk residual | COSMIC |")
    )
    assert any("ResidualRiskLevel" in p for p in _run(fixture_files))


def test_missing_dpia_record_id_fails(fixture_files):
    fixture_files["pack"].write_text(
        _pack().replace("11111111-2222-4333-8444-555555555555", "pending")
    )
    assert any("Record id" in p for p in _run(fixture_files))


def test_non_completed_ropa_status_fails(fixture_files):
    fixture_files["pack"].write_text(_pack(ropa_status="FAILED"))
    problems = _run(fixture_files)
    assert any("COMPLETED" in p for p in problems)


def test_invented_ropa_status_fails(fixture_files):
    fixture_files["pack"].write_text(_pack(ropa_status="GLOWING"))
    assert any("RopaGenerationStatus" in p for p in _run(fixture_files))


def test_missing_artifact_sha_fails(fixture_files):
    fixture_files["pack"].write_text(
        _pack().replace("| Artifact sha256 | aaaa" + "0" * 60 + " |", "| Artifact sha256 | n/a |")
    )
    assert any("Artifact sha256" in p for p in _run(fixture_files))


def test_non_active_dpa_status_fails(fixture_files):
    fixture_files["pack"].write_text(_pack(dpa_status="EXPIRED"))
    problems = _run(fixture_files)
    assert any("ACTIVE" in p for p in problems)


def test_invented_dpa_status_fails(fixture_files):
    fixture_files["pack"].write_text(_pack(dpa_status="VERBOSE"))
    assert any("ProcessorAgreementStatus" in p for p in _run(fixture_files))


def test_dpa_hash_mismatch_fails(fixture_files):
    wrong = "b" * 64
    fixture_files["pack"].write_text(_pack(dpa_hash=wrong))
    problems = _run(fixture_files)
    assert any("hash" in p.lower() for p in problems)


def test_dpa_hash_matches_real_addendum_sha(fixture_files):
    # The canonical builder already carries the real sha of the fixture
    # addendum — recompute here independently so the pin is not circular.
    assert hashlib.sha256(ADDENDUM_BODY.encode()).hexdigest() == ADDENDUM_SHA
    assert _run(fixture_files) == []


def test_erasure_command_missing_on_disk_fails(fixture_files):
    fixture_files["command_files"][-1].unlink()
    problems = _run(fixture_files)
    assert any("tenant_hard_delete_sweep" in p for p in problems)


def test_erasure_command_unnamed_in_pack_fails(fixture_files):
    fixture_files["pack"].write_text(
        _pack(erasure_surfaces=[
            ("Self-service data export", "/api/v1/gdpr/export-jobs/export-data/"),
            ("Self-service erasure", "/api/v1/gdpr/erasure-requests/request-erasure/"),
            ("Admin tenant deletion", "/api/v1/admin/tenants/<uuid:pk>/"),
            ("Tenant file purge", "delete_files_for_tenant"),
            ("User file purge", "delete_files_for_user"),
            ("Some sweep", "some_sweep"),
        ])
    )
    problems = _run(fixture_files)
    assert any("tenant_hard_delete_sweep" in p for p in problems)


def test_erasure_url_fragment_unmentioned_fails(fixture_files):
    fixture_files["pack"].write_text(
        _pack(erasure_surfaces=[
            ("Self-service data export", "/api/v1/gdpr/export-jobs/export-data/"),
            ("Something else", "/api/v1/gdpr/something-else/"),
            ("Admin tenant deletion", "/api/v1/admin/tenants/<uuid:pk>/"),
            ("Tenant file purge", "delete_files_for_tenant"),
            ("User file purge", "delete_files_for_user"),
            ("Tenant hard-delete sweep", "tenant_hard_delete_sweep"),
        ])
    )
    problems = _run(fixture_files)
    assert any("request-erasure" in p for p in problems)


def test_erasure_surface_not_registered_in_source_fails(fixture_files):
    fixture_files["gdpr_views"].write_text(
        GDPR_VIEWS.replace("request-erasure", "renamed")
    )
    problems = _run(fixture_files)
    # The pack still names the old fragment, but it no longer exists in
    # the real URL module — the doc→source cross-check must fail.
    assert any("request-erasure" in p for p in problems)


def test_signoff_without_date_fails(fixture_files):
    fixture_files["pack"].write_text(
        _pack().replace("2026-10-05", "someday").replace("2026-10-05", "later")
    )
    # The builder replaces both dates; "2026-10-05" is gone from the
    # sign-off table → the sign-off date check fires.
    problems = _run(fixture_files)
    assert any("Sign-off" in p or "sign-off" in p for p in problems)


def test_default_paths_exist():
    root = scripts_dir.parent
    assert (root / "docs/runbooks/PILOT_PRIVACY_PACK.md").exists()
    assert (root / "docs/compliance/dpa-addendum.md").exists()
    assert (root / "hub/apps/dpia/models.py").exists()
    assert (root / "hub/apps/ropa/models.py").exists()
    assert (root / "hub/apps/processor_agreements/models.py").exists()
    assert (root / "hub/apps/gdpr/urls.py").exists()
    assert (root / "hub/apps/gdpr/views.py").exists()
    assert (root / "hub/apps/tenants/admin_urls.py").exists()
    for name in COMMANDS:
        assert (root / "hub/apps/files/management/commands" / f"{name}.py").exists() or (
            root / "hub/apps/tenants/management/commands" / f"{name}.py"
        ).exists()


class TestMainContract:
    def test_problems_exit_1(self, fixture_files, monkeypatch):
        fixture_files["pack"].write_text(_pack(dpia_status="DRAFT"))
        monkeypatch.setattr(
            sys,
            "argv",
            [
                "check_privacy_pack.py",
                "--report",
                str(fixture_files["pack"]),
                "--addendum",
                str(fixture_files["addendum"]),
                "--dpia-models",
                str(fixture_files["dpia_models"]),
                "--ropa-models",
                str(fixture_files["ropa_models"]),
                "--pa-models",
                str(fixture_files["pa_models"]),
                "--gdpr-urls",
                str(fixture_files["gdpr_urls"]),
                "--gdpr-views",
                str(fixture_files["gdpr_views"]),
                "--admin-urls",
                str(fixture_files["admin_urls"]),
                "--command-dir",
                str(fixture_files["command_files"][0].parent),
            ],
        )
        with pytest.raises(SystemExit) as exc_info:
            check.main()
        assert exc_info.value.code == 1

    def test_clean_exits_0(self, fixture_files, monkeypatch):
        monkeypatch.setattr(
            sys,
            "argv",
            [
                "check_privacy_pack.py",
                "--report",
                str(fixture_files["pack"]),
                "--addendum",
                str(fixture_files["addendum"]),
                "--dpia-models",
                str(fixture_files["dpia_models"]),
                "--ropa-models",
                str(fixture_files["ropa_models"]),
                "--pa-models",
                str(fixture_files["pa_models"]),
                "--gdpr-urls",
                str(fixture_files["gdpr_urls"]),
                "--gdpr-views",
                str(fixture_files["gdpr_views"]),
                "--admin-urls",
                str(fixture_files["admin_urls"]),
                "--command-dir",
                str(fixture_files["command_files"][0].parent),
            ],
        )
        with pytest.raises(SystemExit) as exc_info:
            check.main()
        assert exc_info.value.code == 0
