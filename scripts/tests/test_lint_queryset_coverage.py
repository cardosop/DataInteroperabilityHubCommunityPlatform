"""
Contract tests for scripts/lint_queryset_coverage.py (G3 / W1.4a,
oss-release-remediation).

Before RLS arming (W1.20), every ViewSet over a tenant-scoped model must
filter its queryset by tenant EXPLICITLY — RLS would silently bless
implicit scoping. The pins run the REAL lint against real fixture trees:

1. a planted unfiltered viewset over a tenant-scoped model flips RED
   (exit 1, class named);
2. a viewset whose get_queryset filters by tenant is clean;
3. a viewset delegating to a scoping helper (the repo's mixin pattern)
   is clean;
4. an allowlisted class is clean;
5. the REAL tree is green (the live contract).
"""

import subprocess
import sys
from pathlib import Path

scripts_dir = Path(__file__).parent.parent
REPO_ROOT = scripts_dir.parent
script_path = scripts_dir / "lint_queryset_coverage.py"

_MODELS = """\
from django.db import models


class Tenant(models.Model):
    name = models.CharField(max_length=100)


class SecretRecord(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    payload = models.TextField()


class OtherRecord(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    note = models.TextField()
"""

_VIEWS_UNFILTERED = """\
from rest_framework import viewsets

from .models import SecretRecord


class LeakyRecordViewSet(viewsets.ModelViewSet):
    queryset = SecretRecord.objects.all()
    serializer_class = None
"""

_VIEWS_FILTERED = """\
from rest_framework import viewsets

from .models import SecretRecord


class SafeRecordViewSet(viewsets.ModelViewSet):
    queryset = SecretRecord.objects.all()
    serializer_class = None

    def get_queryset(self):
        tenant = getattr(self.request, "tenant", None)
        return SecretRecord.objects.filter(tenant=tenant)
"""

_VIEWS_HELPER = """\
from rest_framework import viewsets

from .models import SecretRecord


class ScopingMixin:
    def _resolve_queryset_tenant(self, request, model):
        return model.objects.filter(tenant_id=request.user.tenant_id)


class HelperScopedViewSet(ScopingMixin, viewsets.ModelViewSet):
    queryset = SecretRecord.objects.all()
    serializer_class = None

    def get_queryset(self):
        return self._resolve_queryset_tenant(self.request, SecretRecord)
"""


def _make_tree(tmp_path: Path, views_source: str) -> tuple[Path, Path]:
    tree = tmp_path / "tree"
    app = tree / "fixture-app"
    app.mkdir(parents=True)
    (app / "models.py").write_text(_MODELS)
    (app / "views.py").write_text(views_source)
    allow = tmp_path / "allowlist.yml"
    allow.write_text("version: 1\nentries: []\n")
    return tree, allow


def _run(tree: Path, allow: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [
            sys.executable,
            str(script_path),
            "--root",
            str(tree),
            "--allowlist",
            str(allow),
        ],
        capture_output=True,
        text=True,
        check=False,
    )


class TestPlantedGaps:
    def test_unfiltered_viewset_flips_red(self, tmp_path):
        tree, allow = _make_tree(tmp_path, _VIEWS_UNFILTERED)
        result = _run(tree, allow)
        assert result.returncode == 1
        assert "LeakyRecordViewSet" in result.stderr

    def test_filtered_viewset_is_clean(self, tmp_path):
        tree, allow = _make_tree(tmp_path, _VIEWS_FILTERED)
        result = _run(tree, allow)
        assert result.returncode == 0, result.stderr

    def test_helper_scoped_viewset_is_clean(self, tmp_path):
        tree, allow = _make_tree(tmp_path, _VIEWS_HELPER)
        result = _run(tree, allow)
        assert result.returncode == 0, result.stderr

    def test_allowlisted_class_is_clean(self, tmp_path):
        tree, allow = _make_tree(tmp_path, _VIEWS_UNFILTERED)
        allow.write_text(
            "version: 1\n"
            "entries:\n"
            "  - file: fixture-app/views.py\n"
            "    class: LeakyRecordViewSet\n"
            "    reason: fixture exception with a written reason\n"
        )
        result = _run(tree, allow)
        assert result.returncode == 0, result.stderr


class TestLiveTreeContract:
    def test_the_real_tree_is_clean(self):
        allow = REPO_ROOT / "lint" / "queryset-coverage-allowlist.yml"
        result = _run(REPO_ROOT / "hub" / "apps", allow)
        assert result.returncode == 0, (
            "the live tree has viewsets over tenant-scoped models without "
            "a proven tenant filter — fix the scope or allowlist the class "
            "with a written reason:\n"
            f"{result.stderr}"
        )
