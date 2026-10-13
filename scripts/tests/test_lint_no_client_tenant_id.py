"""
Contract tests for scripts/lint_no_client_tenant_id.py (Phase 260
acceptance #3, extended W1.2b / oss-release-remediation).

The lint forbids client-supplied ``tenant_id`` reads for tenant scoping —
the root cause of the Phase 260.A cross-tenant leaks. W1.2b extends the
pattern set with the ``serializer.validated_data`` envelope (register,
event replay, public DSAR) and pins the whole contract against REAL
fixture trees (no mocks):

1. a planted violation flips the lint RED (exit 1, site named);
2. an allowlisted site passes (the defence-in-depth contract);
3. the validated_data pattern forms ARE caught;
4. the REAL tree is green (the live contract — every remaining site is
   allowlisted with a written reason).
"""

import subprocess
import sys
from pathlib import Path

scripts_dir = Path(__file__).parent.parent
REPO_ROOT = scripts_dir.parent
script_path = scripts_dir / "lint_no_client_tenant_id.py"

_PLANTED_VIEW = """\
from rest_framework.views import APIView
from rest_framework.response import Response


class PlantedLeakView(APIView):
    def post(self, request):
        tenant_id = request.data.get("tenant_id")
        return Response({"tenant_id": tenant_id})
"""

_PLANTED_VALIDATED_DATA = """\
from rest_framework.views import APIView
from rest_framework.response import Response


class PlantedSerializerLeakView(APIView):
    def post(self, request, serializer):
        tenant_id = serializer.validated_data.get("tenant_id")
        return Response({"tenant_id": tenant_id})
"""

_PLANTED_VALIDATED_DATA_SUBSCRIPT = """\
from rest_framework.views import APIView
from rest_framework.response import Response


class PlantedSubscriptLeakView(APIView):
    def post(self, request, serializer):
        tenant_id = str(serializer.validated_data["tenant_id"])
        return Response({"tenant_id": tenant_id})
"""


def _run_lint(root: Path, allowlist: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [
            sys.executable,
            str(script_path),
            "--root",
            str(root),
            "--allowlist",
            str(allowlist),
        ],
        capture_output=True,
        text=True,
        check=False,
    )


def _make_fixture(tmp_path: Path, source: str) -> Path:
    tree = tmp_path / "fixture-app"
    views = tree / "views.py"
    views.parent.mkdir(parents=True)
    views.write_text(source)
    allow = tmp_path / "allowlist.yml"
    allow.write_text("version: 1\nentries: []\n")
    return tree


class TestPatternSet:
    def test_request_data_envelope_is_caught(self, tmp_path):
        tree = _make_fixture(tmp_path, _PLANTED_VIEW)
        result = _run_lint(tree, tmp_path / "allowlist.yml")
        assert result.returncode == 1
        assert "views.py:7" in result.stderr

    def test_validated_data_get_is_caught(self, tmp_path):
        tree = _make_fixture(tmp_path, _PLANTED_VALIDATED_DATA)
        result = _run_lint(tree, tmp_path / "allowlist.yml")
        assert result.returncode == 1, (
            "the serializer.validated_data.get('tenant_id') envelope is "
            "not caught — the register/event-replay/DSAR pattern class "
            "(W1.2b extension)"
        )
        assert "views.py:7" in result.stderr

    def test_validated_data_subscript_is_caught(self, tmp_path):
        tree = _make_fixture(tmp_path, _PLANTED_VALIDATED_DATA_SUBSCRIPT)
        result = _run_lint(tree, tmp_path / "allowlist.yml")
        assert result.returncode == 1, (
            "the serializer.validated_data['tenant_id'] subscript form "
            "is not caught (W1.2b extension)"
        )


class TestAllowlistContract:
    def test_allowlisted_site_passes(self, tmp_path):
        tree = _make_fixture(tmp_path, _PLANTED_VIEW)
        allow = tmp_path / "allowlist.yml"
        allow.write_text(
            "version: 1\n"
            "entries:\n"
            "  - file: views.py\n"
            "    line: 7\n"
            "    reason: fixture rejection guard\n"
        )
        result = _run_lint(tree, allow)
        assert result.returncode == 0, result.stderr

    def test_drifted_anchor_flips_red(self, tmp_path):
        # The anchor rot class the W1.2b repair fixes: the same site at a
        # NEW line is a violation again.
        tree = _make_fixture(tmp_path, _PLANTED_VIEW)
        allow = tmp_path / "allowlist.yml"
        allow.write_text(
            "version: 1\n"
            "entries:\n"
            "  - file: views.py\n"
            "    line: 6\n"
            "    reason: fixture rejection guard (stale anchor)\n"
        )
        result = _run_lint(tree, allow)
        assert result.returncode == 1
        assert "views.py:7" in result.stderr


class TestLiveTreeContract:
    def test_the_real_tree_is_green(self):
        allowlist = REPO_ROOT / "lint" / "no-client-tenant-id-allowlist.yml"
        result = _run_lint(REPO_ROOT / "hub" / "apps", allowlist)
        assert result.returncode == 0, (
            "the live tree has unallowlisted client-tenant_id reads — "
            "fix the site or add a written-reason allowlist entry:\n"
            f"{result.stderr}"
        )
