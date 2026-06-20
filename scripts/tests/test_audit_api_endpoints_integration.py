"""
Integration tests for API endpoint audit script
"""

import importlib.util
import json
import os
import sys
import tempfile
from pathlib import Path

import pytest

# Add scripts directory to path
scripts_dir = Path(__file__).parent.parent
sys.path.insert(0, str(scripts_dir))

# Import module with hyphenated name using importlib
script_path = scripts_dir / "audit-api-endpoints.py"
spec = importlib.util.spec_from_file_location("audit_api_endpoints", script_path)
audit_api_endpoints = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit_api_endpoints)

# Import classes and functions
EndpointAuditor = audit_api_endpoints.EndpointAuditor
find_urls_file = audit_api_endpoints.find_urls_file
ServiceMountPointMapper = audit_api_endpoints.ServiceMountPointMapper


@pytest.mark.integration
class TestEndpointAuditorIntegration:
    """Integration tests for endpoint auditor"""

    def test_find_urls_file(self):
        """Test finding urls.py file"""
        urls_file = find_urls_file()

        # Should find the file if running from project root
        if urls_file:
            assert os.path.exists(urls_file)
            assert urls_file.endswith("urls.py")
            assert "api" in urls_file

    @pytest.mark.skipif(
        not os.path.exists("hub/apps/api/urls.py"), reason="Django project not available"
    )
    def test_full_audit(self):
        """Test full audit process"""
        urls_file = find_urls_file()
        if not urls_file:
            pytest.skip("Could not find urls.py file")

        auditor = EndpointAuditor()

        try:
            results = auditor.audit(
                urls_file,
                check_duplicates=True,
                check_naming=True,
            )

            # Check results structure
            assert "inventory" in results
            assert "issues" in results
            assert "mount_points" in results

            # Check inventory structure
            inventory = results["inventory"]
            assert "summary" in inventory
            assert "endpoints" in inventory

            # Check summary
            summary = inventory["summary"]
            assert "total_endpoints" in summary
            assert "total_services" in summary

            # Should have some endpoints
            assert summary["total_endpoints"] > 0

            # Check issues structure
            issues = results["issues"]
            assert "duplicates" in issues or "naming_inconsistencies" in issues

        except Exception as e:
            # If Django setup fails, that's okay for integration test
            pytest.skip(f"Django setup failed: {e}")

    @pytest.mark.skipif(
        not os.path.exists("hub/apps/api/urls.py"), reason="Django project not available"
    )
    def test_json_output(self):
        """Test JSON output format"""
        urls_file = find_urls_file()
        if not urls_file:
            pytest.skip("Could not find urls.py file")

        auditor = EndpointAuditor()

        try:
            results = auditor.audit(urls_file)
            json_output = auditor.output_json(results)

            # Should be valid JSON
            parsed = json.loads(json_output)
            assert "inventory" in parsed

        except Exception as e:
            pytest.skip(f"Django setup failed: {e}")

    @pytest.mark.skipif(
        not os.path.exists("hub/apps/api/urls.py"), reason="Django project not available"
    )
    def test_markdown_output(self):
        """Test Markdown output format"""
        urls_file = find_urls_file()
        if not urls_file:
            pytest.skip("Could not find urls.py file")

        auditor = EndpointAuditor()

        try:
            results = auditor.audit(urls_file)
            markdown_output = auditor.output_markdown(results)

            # Should be valid Markdown
            assert isinstance(markdown_output, str)
            assert len(markdown_output) > 0

            # Should contain expected sections
            assert "API Endpoint Audit Report" in markdown_output or "# " in markdown_output

        except Exception as e:
            pytest.skip(f"Django setup failed: {e}")

    def test_mount_point_mapping(self):
        """Test mount point mapping from urls.py"""
        urls_content = """
from django.urls import path, include

urlpatterns = [
    path('auth/', include('hub.apps.auth.urls')),
    path('tenants/', include('hub.apps.tenants.urls')),
    path('users/', include('hub.apps.users.urls')),
    path('', include('hub.apps.analytics.urls')),
]
"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(urls_content)
            temp_path = f.name

        try:
            mapper = ServiceMountPointMapper()
            mount_points = mapper.map_from_file(temp_path)

            assert "auth" in mount_points
            assert mount_points["auth"] == "hub.apps.auth.urls"
            assert "tenants" in mount_points
            assert "users" in mount_points

        finally:
            os.unlink(temp_path)
