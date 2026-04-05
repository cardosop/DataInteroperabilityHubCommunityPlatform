"""
Tests for service decoupling

Verifies that views use services instead of direct model imports.
"""
import ast
import os
from pathlib import Path
from django.test import TestCase
from django.conf import settings


class DecouplingTest(TestCase):
    """Test that views use services instead of direct model imports."""
    
    def _get_app_path(self, app_name: str, filename: str) -> Path:
        """Get absolute path to a file in an app."""
        # Get the base directory (project root)
        # BASE_DIR points to project root, so apps are at hub/apps/
        base_dir = Path(settings.BASE_DIR)
        return base_dir / "hub" / "apps" / app_name / filename
    
    def test_datasets_views_no_cross_app_imports(self):
        """Test that datasets/views.py doesn't import models from other apps."""
        views_path = self._get_app_path("datasets", "views.py")
        if not views_path.exists():
            self.skipTest(f"datasets/views.py not found at {views_path}")
        
        with open(views_path) as f:
            content = f.read()
        
        # Check for cross-app model imports (excluding conditional imports in try blocks)
        forbidden_patterns = [
            "from hub.apps.files.models import",
            "from hub.apps.assets.models import",
            "from hub.apps.contracts.models import",
        ]
        
        # Check top-level imports only (not inside functions/methods/try blocks).
        # A line is "top-level" when its indentation is zero.
        lines = content.split('\n')
        for i, line in enumerate(lines):
            # Only check non-indented import lines (module-scope)
            if line and not line[0].isspace():
                for pattern in forbidden_patterns:
                    if pattern in line:
                        self.fail(
                            f"Found forbidden import at line {i+1}: {line}. "
                            f"Use services instead. Pattern: {pattern}"
                        )
    
    def test_marketplace_views_no_cross_app_imports(self):
        """Test that marketplace/views.py doesn't import models from other apps."""
        views_path = self._get_app_path("marketplace", "views.py")
        if not views_path.exists():
            self.skipTest(f"marketplace/views.py not found at {views_path}")
        
        with open(views_path) as f:
            content = f.read()
        
        # Check top-level imports only (not inside functions/methods/try blocks).
        # A line is "top-level" when its indentation is zero.
        lines = content.split('\n')
        forbidden_in_main_scope = [
            "from hub.apps.tenants.models import",
            "from hub.apps.assets.models import",
            "from hub.apps.contracts.models import",
        ]

        for i, line in enumerate(lines):
            if line and not line[0].isspace():
                for pattern in forbidden_in_main_scope:
                    if pattern in line:
                        self.fail(
                            f"Found forbidden import at line {i+1}: "
                            f"{line}. Use services instead. "
                            f"Pattern: {pattern}"
                        )
        
        # Verify service imports exist
        self.assertIn(
            "from hub.apps.tenants.services import",
            content,
            "Should import TenantService instead of Tenant model"
        )
        self.assertIn(
            "from hub.apps.assets.services import",
            content,
            "Should import AssetService instead of Asset model"
        )
        self.assertIn(
            "from hub.apps.contracts.services import",
            content,
            "Should import ContractService instead of Contract model"
        )


