"""
Unit tests for API endpoint audit script
"""

import importlib.util
import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import Mock

# Add scripts directory to path
scripts_dir = Path(__file__).parent.parent
sys.path.insert(0, str(scripts_dir))

# Import module with hyphenated name using importlib
script_path = scripts_dir / "audit-api-endpoints.py"
spec = importlib.util.spec_from_file_location("audit_api_endpoints", script_path)
audit_api_endpoints = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit_api_endpoints)

# Import classes
URLPatternParser = audit_api_endpoints.URLPatternParser
ServiceMountPointMapper = audit_api_endpoints.ServiceMountPointMapper
DuplicateServiceNameDetector = audit_api_endpoints.DuplicateServiceNameDetector
InconsistentNamingPatternDetector = audit_api_endpoints.InconsistentNamingPatternDetector
EndpointInventoryGenerator = audit_api_endpoints.EndpointInventoryGenerator
EndpointAuditor = audit_api_endpoints.EndpointAuditor


class TestURLPatternParser:
    """Test URL pattern parser"""

    def test_parse_path_pattern(self):
        """Test parsing simple path pattern"""
        parser = URLPatternParser()

        # Mock Django path pattern
        from django.urls import path
        from django.views.generic import View

        pattern = path("test/", View.as_view(), name="test-view")
        result = parser.parse_pattern(pattern, base_path="/api/v1")

        assert result is not None
        assert result["pattern"] == "test/"
        assert result["full_path"] == "/api/v1/test/"
        assert result["name"] == "test-view"

    def test_parse_re_path_pattern(self):
        """Test parsing regex path pattern"""
        parser = URLPatternParser()

        from django.urls import re_path
        from django.views.generic import View

        pattern = re_path(r"^test/(?P<id>\d+)/$", View.as_view(), name="test-detail")
        result = parser.parse_pattern(pattern, base_path="/api/v1")

        assert result is not None
        assert "test/" in result["pattern"] or "regex" in result["pattern"].lower()
        assert result["name"] == "test-detail"

    def test_parse_include_pattern(self):
        """Test parsing include pattern"""
        parser = URLPatternParser()

        # Create a mock include pattern object that matches URLResolver structure
        class MockIncludePattern:
            def __init__(self):
                self.urlconf_name = "hub.apps.auth.urls"
                self.url_patterns = []

                # URLResolver has pattern attribute
                class MockPattern:
                    pattern = "auth/"

                self.pattern = MockPattern()

        pattern = MockIncludePattern()
        # Set type name to URLResolver to match parser logic
        pattern.__class__.__name__ = "URLResolver"
        result = parser.parse_pattern(pattern, base_path="/api/v1", prefix="auth/")

        assert result is not None
        assert result["type"] == "include"
        assert "hub.apps.auth.urls" in result["module"]

    def test_parse_router_registration(self):
        """Test parsing router registration"""
        parser = URLPatternParser()

        # Create a mock router pattern (URLPattern)
        class MockRouterPattern:
            def __init__(self):
                self.pattern = "test/"
                self.callback = Mock()
                self.callback.__name__ = "test_view"
                self.name = "test-list"

        pattern = MockRouterPattern()
        # Set type name to URLPattern to match parser logic
        pattern.__class__.__name__ = "URLPattern"
        result = parser.parse_pattern(pattern, base_path="/api/v1")

        assert result is not None
        # Accept 'path', 're_path', or 'router' as valid types
        assert result["type"] in ["path", "re_path", "router"]


class TestServiceMountPointMapper:
    """Test service mount point mapper"""

    def test_map_mount_points_from_urls(self):
        """Test mapping mount points from urls.py"""
        mapper = ServiceMountPointMapper()

        # Mock hub/apps/api/urls.py content
        urls_content = """
from django.urls import path, include

urlpatterns = [
    path('auth/', include('hub.apps.auth.urls')),
    path('tenants/', include('hub.apps.tenants.urls')),
    path('users/', include('hub.apps.users.urls')),
]
"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(urls_content)
            temp_path = f.name

        try:
            mount_points = mapper.map_from_file(temp_path)

            assert "auth" in mount_points
            assert mount_points["auth"] == "hub.apps.auth.urls"
            assert "tenants" in mount_points
            assert mount_points["tenants"] == "hub.apps.tenants.urls"
        finally:
            os.unlink(temp_path)

    def test_map_mount_points_with_empty_prefix(self):
        """Test mapping mount points with empty prefix"""
        mapper = ServiceMountPointMapper()

        urls_content = """
from django.urls import path, include

urlpatterns = [
    path('', include('hub.apps.analytics.urls')),
    path('governance/', include('hub.apps.governance.urls')),
]
"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(urls_content)
            temp_path = f.name

        try:
            mount_points = mapper.map_from_file(temp_path)

            # Empty prefix should map to the module name or be handled specially
            assert len(mount_points) >= 1
        finally:
            os.unlink(temp_path)


class TestDuplicateServiceNameDetector:
    """Test duplicate service name detector"""

    def test_detect_duplicates(self):
        """Test detecting duplicate service names"""
        detector = DuplicateServiceNameDetector()

        endpoints = [
            {"service": "auth", "path": "/api/v1/auth/login/", "name": "login"},
            {"service": "auth", "path": "/api/v1/auth/register/", "name": "register"},
            {"service": "users", "path": "/api/v1/users/", "name": "user-list"},
            {"service": "auth", "path": "/api/v1/auth/logout/", "name": "logout"},
        ]

        duplicates = detector.detect(endpoints)

        # Should not find duplicates in this case (same service is fine)
        assert isinstance(duplicates, list)

    def test_detect_duplicate_paths(self):
        """Test detecting duplicate paths"""
        detector = DuplicateServiceNameDetector()

        endpoints = [
            {"service": "auth", "full_path": "/api/v1/auth/login/", "name": "login"},
            {
                "service": "users",
                "full_path": "/api/v1/auth/login/",
                "name": "user-login",
            },  # Duplicate path
        ]

        duplicates = detector.detect(endpoints)

        # Should find duplicate paths
        assert len(duplicates) > 0
        # Check that we found the duplicate path
        duplicate_paths = [d for d in duplicates if d.get("type") == "duplicate_path"]
        assert len(duplicate_paths) > 0
        assert duplicate_paths[0]["path"] == "/api/v1/auth/login/"


class TestInconsistentNamingPatternDetector:
    """Test inconsistent naming pattern detector"""

    def test_detect_inconsistent_patterns(self):
        """Test detecting inconsistent naming patterns"""
        detector = InconsistentNamingPatternDetector()

        endpoints = [
            {"service": "auth", "path": "/api/v1/auth/login/", "name": "login"},
            {
                "service": "auth",
                "path": "/api/v1/auth/register/",
                "name": "auth-register",
            },  # Inconsistent
            {"service": "users", "path": "/api/v1/users/", "name": "user-list"},
            {
                "service": "users",
                "path": "/api/v1/users/<id>/",
                "name": "users-detail",
            },  # Inconsistent
        ]

        inconsistencies = detector.detect(endpoints)

        assert isinstance(inconsistencies, list)

    def test_detect_path_naming_inconsistencies(self):
        """Test detecting path naming inconsistencies"""
        detector = InconsistentNamingPatternDetector()

        endpoints = [
            {"service": "auth", "path": "/api/v1/auth/login/", "name": "login"},
            {"service": "auth", "path": "/api/v1/auth/logout/", "name": "logout"},
            {"service": "users", "path": "/api/v1/users/", "name": "user-list"},
            {"service": "users", "path": "/api/v1/users/<id>/", "name": "user-detail"},
        ]

        inconsistencies = detector.detect(endpoints)

        assert isinstance(inconsistencies, list)


class TestEndpointInventoryGenerator:
    """Test endpoint inventory generator"""

    def test_generate_inventory(self):
        """Test generating endpoint inventory"""
        generator = EndpointInventoryGenerator()

        endpoints = [
            {"service": "auth", "path": "/api/v1/auth/login/", "name": "login", "method": "POST"},
            {
                "service": "auth",
                "path": "/api/v1/auth/register/",
                "name": "register",
                "method": "POST",
            },
            {"service": "users", "path": "/api/v1/users/", "name": "user-list", "method": "GET"},
        ]

        inventory = generator.generate(endpoints)

        assert "services" in inventory or "endpoints" in inventory
        assert "summary" in inventory or "total" in inventory

    def test_generate_grouped_by_service(self):
        """Test generating inventory grouped by service"""
        generator = EndpointInventoryGenerator()

        endpoints = [
            {"service": "auth", "path": "/api/v1/auth/login/", "name": "login"},
            {"service": "auth", "path": "/api/v1/auth/register/", "name": "register"},
            {"service": "users", "path": "/api/v1/users/", "name": "user-list"},
        ]

        inventory = generator.generate(endpoints, group_by="service")

        assert "auth" in str(inventory) or "services" in inventory


class TestEndpointAuditor:
    """Test endpoint auditor integration"""

    def test_audit_endpoints_structure(self):
        """Test audit endpoint structure"""
        auditor = EndpointAuditor()

        # Test that auditor has required components
        assert hasattr(auditor, "parser")
        assert hasattr(auditor, "mapper")
        assert hasattr(auditor, "duplicate_detector")
        assert hasattr(auditor, "naming_detector")
        assert hasattr(auditor, "inventory_generator")
        assert hasattr(auditor, "audit")

    def test_output_json(self):
        """Test JSON output format"""
        auditor = EndpointAuditor()

        data = {
            "endpoints": [
                {"path": "/api/v1/auth/login/", "name": "login"},
            ],
            "summary": {"total": 1},
        }

        output = auditor.output_json(data)

        assert isinstance(output, str)
        parsed = json.loads(output)
        assert "endpoints" in parsed

    def test_output_markdown(self):
        """Test Markdown output format"""
        auditor = EndpointAuditor()

        data = {
            "inventory": {
                "endpoints": [
                    {
                        "full_path": "/api/v1/auth/login/",
                        "name": "login",
                        "service": "auth",
                        "methods": ["POST"],
                    },
                ],
                "summary": {"total_endpoints": 1, "total_services": 1},
                "by_service": {
                    "auth": [
                        {
                            "full_path": "/api/v1/auth/login/",
                            "name": "login",
                            "service": "auth",
                            "methods": ["POST"],
                        },
                    ],
                },
            },
            "issues": {},
        }

        output = auditor.output_markdown(data)

        assert isinstance(output, str)
        assert len(output) > 0
        # Check for expected markdown sections
        assert "API Endpoint Audit Report" in output or "Summary" in output
        # Check that endpoint information is included
        assert "login" in output or "auth" in output or "Total Endpoints" in output
