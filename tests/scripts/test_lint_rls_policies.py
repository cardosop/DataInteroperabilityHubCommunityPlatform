import subprocess
from pathlib import Path

SOURCE_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "lint_rls_policies.py"


def _run(command: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=cwd,
        check=True,
        text=True,
        capture_output=True,
    )


def _init_repo(repo: Path) -> None:
    _run(["git", "init"], cwd=repo)
    _run(["git", "config", "user.email", "test@example.com"], cwd=repo)
    _run(["git", "config", "user.name", "Test User"], cwd=repo)
    (repo / "scripts").mkdir(parents=True, exist_ok=True)
    (repo / "lint").mkdir(parents=True, exist_ok=True)
    (repo / "hub" / "apps" / "demo" / "migrations").mkdir(
        parents=True,
        exist_ok=True,
    )
    (repo / "hub" / "apps" / "demo" / "__init__.py").write_text(
        "",
        encoding="utf-8",
    )
    (repo / "hub" / "apps" / "demo" / "migrations" / "__init__.py").write_text(
        "",
        encoding="utf-8",
    )


def _write_script_copy(repo: Path, source_script: Path) -> None:
    destination = repo / "scripts" / "lint_rls_policies.py"
    destination.write_text(
        source_script.read_text(encoding="utf-8"),
        encoding="utf-8",
    )


def _commit_all(repo: Path, message: str) -> None:
    _run(["git", "add", "."], cwd=repo)
    _run(["git", "commit", "-m", message], cwd=repo)


def _default_allowlist(repo: Path, content: str = "tables: []\n") -> None:
    (repo / "lint" / "rls-policies-allowlist.yml").write_text(
        content,
        encoding="utf-8",
    )


def _run_linter(repo: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            "python3",
            "scripts/lint_rls_policies.py",
            "--repo-root",
            ".",
            "--base-ref",
            "HEAD~1",
            "--allowlist",
            "lint/rls-policies-allowlist.yml",
        ],
        cwd=repo,
        text=True,
        capture_output=True,
        check=False,
    )


def test_fails_when_new_tenant_model_has_no_policy(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    _write_script_copy(repo, SOURCE_SCRIPT)
    _default_allowlist(repo)
    (repo / "hub" / "apps" / "demo" / "models.py").write_text(
        "from django.db import models\n\n",
        encoding="utf-8",
    )
    _commit_all(repo, "base")

    (repo / "hub" / "apps" / "demo" / "models.py").write_text(
        "from django.db import models\n"
        "from hub.apps.tenants.models import Tenant\n\n"
        "class CustomerOrder(models.Model):\n"
        "    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)\n",
        encoding="utf-8",
    )
    (repo / "hub" / "apps" / "demo" / "migrations" / "0001_initial.py").write_text(
        "from django.db import migrations\n", encoding="utf-8"
    )
    _commit_all(repo, "add tenant model without policy")

    result = _run_linter(repo)
    assert result.returncode == 1
    assert "demo_customerorder" in result.stdout + result.stderr


def test_passes_when_policy_exists_for_new_tenant_model(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    _write_script_copy(repo, SOURCE_SCRIPT)
    _default_allowlist(repo)
    (repo / "hub" / "apps" / "demo" / "models.py").write_text(
        "from django.db import models\n\n",
        encoding="utf-8",
    )
    _commit_all(repo, "base")

    (repo / "hub" / "apps" / "demo" / "models.py").write_text(
        "from django.db import models\n"
        "from hub.apps.tenants.models import Tenant\n\n"
        "class CustomerOrder(models.Model):\n"
        "    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)\n",
        encoding="utf-8",
    )
    (repo / "hub" / "apps" / "demo" / "migrations" / "0002_rls.py").write_text(
        "from django.db import migrations\n\n"
        "class Migration(migrations.Migration):\n"
        "    operations = [\n"
        "        migrations.RunSQL(\n"
        '            "CREATE POLICY demo_customerorder_tenant_isolation '
        "ON demo_customerorder USING "
        "(tenant_id = current_setting('app.current_tenant_id')::uuid)\",\n"
        '            reverse_sql="DROP POLICY IF EXISTS '
        'demo_customerorder_tenant_isolation ON demo_customerorder",\n'
        "        )\n"
        "    ]\n",
        encoding="utf-8",
    )
    _commit_all(repo, "add tenant model with policy")

    result = _run_linter(repo)
    assert result.returncode == 0


def test_passes_when_table_is_allowlisted(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    _write_script_copy(repo, SOURCE_SCRIPT)
    _default_allowlist(
        repo,
        "tables:\n  - table: demo_customerorder\n    reason: global cross-tenant catalog table\n",
    )
    (repo / "hub" / "apps" / "demo" / "models.py").write_text(
        "from django.db import models\n\n",
        encoding="utf-8",
    )
    _commit_all(repo, "base")

    (repo / "hub" / "apps" / "demo" / "models.py").write_text(
        "from django.db import models\n"
        "from hub.apps.tenants.models import Tenant\n\n"
        "class CustomerOrder(models.Model):\n"
        "    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)\n",
        encoding="utf-8",
    )
    _commit_all(repo, "add tenant model allowlisted")

    result = _run_linter(repo)
    assert result.returncode == 0


def test_ignores_existing_tenant_model_from_base(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    _write_script_copy(repo, SOURCE_SCRIPT)
    _default_allowlist(repo)
    (repo / "hub" / "apps" / "demo" / "models.py").write_text(
        "from django.db import models\n"
        "from hub.apps.tenants.models import Tenant\n\n"
        "class CustomerOrder(models.Model):\n"
        "    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)\n",
        encoding="utf-8",
    )
    _commit_all(repo, "base with existing tenant model")

    (repo / "README.md").write_text(
        "unchanged model baseline\n",
        encoding="utf-8",
    )
    _commit_all(repo, "touch unrelated file")

    result = _run_linter(repo)
    assert result.returncode == 0


def test_detects_tenant_fk_even_with_nonstandard_field_name(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    _write_script_copy(repo, SOURCE_SCRIPT)
    _default_allowlist(repo)
    (repo / "hub" / "apps" / "demo" / "models.py").write_text(
        "from django.db import models\n\n",
        encoding="utf-8",
    )
    _commit_all(repo, "base")

    (repo / "hub" / "apps" / "demo" / "models.py").write_text(
        "from django.db import models\n"
        "from hub.apps.tenants.models import Tenant\n\n"
        "class CustomerOrder(models.Model):\n"
        "    owner_tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)\n",
        encoding="utf-8",
    )
    _commit_all(repo, "add tenant model with nonstandard fk field name")

    result = _run_linter(repo)
    assert result.returncode == 1
    assert "demo_customerorder" in result.stdout + result.stderr


def test_policy_detection_handles_quoted_public_schema_table_name(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    _write_script_copy(repo, SOURCE_SCRIPT)
    _default_allowlist(repo)
    (repo / "hub" / "apps" / "demo" / "models.py").write_text(
        "from django.db import models\n\n",
        encoding="utf-8",
    )
    _commit_all(repo, "base")

    (repo / "hub" / "apps" / "demo" / "models.py").write_text(
        "from django.db import models\n"
        "from hub.apps.tenants.models import Tenant\n\n"
        "class CustomerOrder(models.Model):\n"
        "    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)\n",
        encoding="utf-8",
    )
    (repo / "hub" / "apps" / "demo" / "migrations" / "0002_rls.py").write_text(
        "from django.db import migrations\n\n"
        "class Migration(migrations.Migration):\n"
        "    operations = [\n"
        "        migrations.RunSQL(\n"
        '            "CREATE POLICY demo_customerorder_tenant_isolation '
        'ON \\"public\\".\\"demo_customerorder\\" '
        "USING (tenant_id = current_setting('app.current_tenant_id')::uuid)\",\n"
        '            reverse_sql="DROP POLICY IF EXISTS '
        'demo_customerorder_tenant_isolation ON \\"public\\".\\"demo_customerorder\\"",\n'
        "        )\n"
        "    ]\n",
        encoding="utf-8",
    )
    _commit_all(repo, "add tenant model with quoted public policy")

    result = _run_linter(repo)
    assert result.returncode == 0


def test_detects_missing_policy_for_tenant_model_in_models_package(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    _write_script_copy(repo, SOURCE_SCRIPT)
    _default_allowlist(repo)

    models_pkg = repo / "hub" / "apps" / "demo" / "models"
    models_pkg.mkdir(parents=True, exist_ok=True)
    (models_pkg / "__init__.py").write_text(
        "",
        encoding="utf-8",
    )
    _commit_all(repo, "base")

    (models_pkg / "orders.py").write_text(
        "from django.db import models\n"
        "from hub.apps.tenants.models import Tenant\n\n"
        "class CustomerOrder(models.Model):\n"
        "    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)\n",
        encoding="utf-8",
    )
    _commit_all(repo, "add tenant model in models package without policy")

    result = _run_linter(repo)
    assert result.returncode == 1
    assert "demo_customerorder" in result.stdout + result.stderr


def test_detects_missing_policy_for_tenant_model_in_nonstandard_app_file(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    _write_script_copy(repo, SOURCE_SCRIPT)
    _default_allowlist(repo)

    (repo / "hub" / "apps" / "demo" / "models.py").write_text(
        "from django.db import models\n\n",
        encoding="utf-8",
    )
    _commit_all(repo, "base")

    (repo / "hub" / "apps" / "demo" / "custom_model_defs.py").write_text(
        "from django.db import models\n"
        "from hub.apps.tenants.models import Tenant\n\n"
        "class ExternalOrder(models.Model):\n"
        "    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)\n",
        encoding="utf-8",
    )
    _commit_all(repo, "add tenant model in nonstandard app file")

    result = _run_linter(repo)
    assert result.returncode == 1
    assert "demo_externalorder" in result.stdout + result.stderr


def test_detects_tenant_fk_via_string_reference(tmp_path: Path) -> None:
    """Phase 277.B.053 — linter must detect ``ForeignKey("tenants.Tenant")``."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    _write_script_copy(repo, SOURCE_SCRIPT)
    _default_allowlist(repo)
    (repo / "hub" / "apps" / "demo" / "models.py").write_text(
        "from django.db import models\n\n",
        encoding="utf-8",
    )
    _commit_all(repo, "base")

    (repo / "hub" / "apps" / "demo" / "models.py").write_text(
        "from django.db import models\n\n"
        "class CustomerOrder(models.Model):\n"
        '    tenant = models.ForeignKey("tenants.Tenant", on_delete=models.CASCADE)\n',
        encoding="utf-8",
    )
    _commit_all(repo, "add tenant model via string reference without policy")

    result = _run_linter(repo)
    assert result.returncode == 1
    assert "demo_customerorder" in result.stdout + result.stderr


def test_detects_tenant_fk_via_onetoone_string_reference(tmp_path: Path) -> None:
    """Phase 277.B.053 — linter must detect ``OneToOneField("tenants.Tenant")``."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    _write_script_copy(repo, SOURCE_SCRIPT)
    _default_allowlist(repo)
    (repo / "hub" / "apps" / "demo" / "models.py").write_text(
        "from django.db import models\n\n",
        encoding="utf-8",
    )
    _commit_all(repo, "base")

    (repo / "hub" / "apps" / "demo" / "models.py").write_text(
        "from django.db import models\n\n"
        "class TenantProfile(models.Model):\n"
        '    tenant = models.OneToOneField("tenants.Tenant", on_delete=models.CASCADE)\n',
        encoding="utf-8",
    )
    _commit_all(repo, "add tenant model via OneToOne string ref without policy")

    result = _run_linter(repo)
    assert result.returncode == 1
    assert "demo_tenantprofile" in result.stdout + result.stderr


def test_detects_tenant_fk_via_kwarg_to(tmp_path: Path) -> None:
    """Phase 277.B.053 — linter must detect ``ForeignKey(..., to="tenants.Tenant")``."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    _write_script_copy(repo, SOURCE_SCRIPT)
    _default_allowlist(repo)
    (repo / "hub" / "apps" / "demo" / "models.py").write_text(
        "from django.db import models\n\n",
        encoding="utf-8",
    )
    _commit_all(repo, "base")

    (repo / "hub" / "apps" / "demo" / "models.py").write_text(
        "from django.db import models\n\n"
        "class CustomerOrder(models.Model):\n"
        '    owner = models.ForeignKey(to="tenants.Tenant", on_delete=models.CASCADE)\n',
        encoding="utf-8",
    )
    _commit_all(repo, "add tenant model via kwarg to= without policy")

    result = _run_linter(repo)
    assert result.returncode == 1
    assert "demo_customerorder" in result.stdout + result.stderr
