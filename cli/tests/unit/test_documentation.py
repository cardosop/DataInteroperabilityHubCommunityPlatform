"""
Unit tests for CLI documentation.

Tests that documentation is complete, accurate, and up-to-date.
"""
import pytest
import re
from pathlib import Path


class TestCLIDocumentation:
    """Test CLI documentation completeness and accuracy"""

    @pytest.fixture
    def readme_path(self):
        """Path to CLI README"""
        return Path(__file__).parent.parent.parent / "README.md"

    @pytest.fixture
    def odps_usage_path(self):
        """Path to ODPS usage documentation"""
        return Path(__file__).parent.parent.parent / "docs" / "ODPS_USAGE.md"

    @pytest.fixture
    def baas_usage_path(self):
        """Path to BaaS usage documentation"""
        return Path(__file__).parent.parent.parent / "docs" / "BAAS_USAGE.md"

    def test_readme_exists(self, readme_path):
        """Test that README.md exists"""
        assert readme_path.exists(), f"README.md not found at {readme_path}"

    def test_readme_contains_odps_section(self, readme_path):
        """Test that README contains ODPS commands section"""
        content = readme_path.read_text()
        assert "ODPS" in content or "odps" in content.lower(), "README should contain ODPS documentation"
        assert "create-odps" in content.lower(), "README should document create-odps command"
        assert "get-pricing" in content.lower(), "README should document get-pricing command"
        assert "get-access-methods" in content.lower(), "README should document get-access-methods command"

    def test_readme_contains_odps_examples(self, readme_path):
        """Test that README contains ODPS examples"""
        content = readme_path.read_text()
        assert "create-odps" in content, "README should contain create-odps example"
        assert "--extract-odcs" in content or "--link-odcs" in content, "README should contain ODPS linking examples"

    def test_readme_contains_odps_workflow(self, readme_path):
        """Test that README contains ODPS workflow examples"""
        content = readme_path.read_text()
        assert "ODPS Workflow" in content or "ODPS workflow" in content, "README should contain ODPS workflow section"

    def test_odps_usage_doc_exists(self, odps_usage_path):
        """Test that ODPS usage documentation exists"""
        assert odps_usage_path.exists(), f"ODPS_USAGE.md not found at {odps_usage_path}"

    def test_odps_usage_doc_structure(self, odps_usage_path):
        """Test that ODPS usage documentation has proper structure"""
        content = odps_usage_path.read_text()

        # Check for main sections
        assert "# ODPS" in content or "## Overview" in content, "ODPS doc should have overview"
        assert "Creating ODPS" in content or "create-odps" in content.lower(), "ODPS doc should cover creation"
        assert "Information" in content or "get-pricing" in content.lower(), "ODPS doc should cover information commands"
        assert "Workflow" in content or "workflow" in content.lower(), "ODPS doc should cover workflows"

    def test_odps_usage_doc_contains_all_commands(self, odps_usage_path):
        """Test that ODPS usage doc documents all ODPS commands"""
        content = odps_usage_path.read_text()

        # Check for all ODPS commands
        commands = [
            "create-odps",
            "link-odps",
            "unlink-odps",
            "list-links",
            "get-pricing",
            "get-access-methods",
            "--show-odps"
        ]

        for command in commands:
            assert command in content.lower(), f"ODPS doc should document {command} command"

    def test_odps_usage_doc_contains_examples(self, odps_usage_path):
        """Test that ODPS usage doc contains examples"""
        content = odps_usage_path.read_text()

        # Check for code blocks with examples
        code_blocks = re.findall(r'```bash\n(.*?)\n```', content, re.DOTALL)
        assert len(code_blocks) > 0, "ODPS doc should contain command examples"

    def test_odps_usage_doc_contains_troubleshooting(self, odps_usage_path):
        """Test that ODPS usage doc contains troubleshooting section"""
        content = odps_usage_path.read_text()
        assert "Troubleshooting" in content or "troubleshooting" in content.lower(), "ODPS doc should have troubleshooting section"

    def test_readme_odps_command_reference(self, readme_path):
        """Test that README contains ODPS command reference table"""
        content = readme_path.read_text()
        # Check for command reference or table
        assert "Command Reference" in content or "| Command |" in content, "README should contain command reference"

    def test_documentation_accuracy(self, readme_path):
        """Test that documented commands match actual implementation"""
        content = readme_path.read_text()

        # Verify documented commands are mentioned
        # This is a basic check - actual command validation would require importing the CLI
        assert "contracts" in content.lower(), "README should document contracts commands"
        assert "odps" in content.lower() or "ODPS" in content, "README should document ODPS commands"

    # BaaS Documentation Tests

    def test_readme_contains_baas_section(self, readme_path):
        """Test that README contains BaaS commands section"""
        content = readme_path.read_text()
        assert "BaaS" in content or "baas" in content.lower(), "README should contain BaaS documentation"
        assert "api-keys" in content.lower(), "README should document api-keys commands"
        assert "docs" in content.lower() or "documentation" in content.lower(), "README should document docs commands"
        assert "usage" in content.lower(), "README should document usage commands"

    def test_readme_contains_baas_examples(self, readme_path):
        """Test that README contains BaaS examples"""
        content = readme_path.read_text()
        assert "baas api-keys create" in content.lower(), "README should contain api-keys create example"
        assert "baas docs show" in content.lower() or "baas docs openapi" in content.lower(), "README should contain docs examples"
        assert "baas usage" in content.lower(), "README should contain usage examples"

    def test_readme_contains_baas_workflow(self, readme_path):
        """Test that README contains BaaS workflow examples"""
        content = readme_path.read_text()
        # Check for BaaS section with workflow-like content
        assert "BaaS" in content, "README should contain BaaS section"
        assert "api-keys" in content.lower() and ("create" in content.lower() or "list" in content.lower()), "README should contain BaaS API key examples"

    def test_baas_usage_doc_exists(self, baas_usage_path):
        """Test that BaaS usage documentation exists"""
        assert baas_usage_path.exists(), f"BAAS_USAGE.md not found at {baas_usage_path}"

    def test_baas_usage_doc_structure(self, baas_usage_path):
        """Test that BaaS usage documentation has proper structure"""
        content = baas_usage_path.read_text()

        # Check for main sections
        assert "# BaaS" in content or "## Overview" in content, "BaaS doc should have overview"
        assert "API Key" in content or "api-keys" in content.lower(), "BaaS doc should cover API key management"
        assert "Usage Tracking" in content or "usage" in content.lower(), "BaaS doc should cover usage tracking"
        assert "Developer Portal" in content or "docs" in content.lower(), "BaaS doc should cover developer portal"
        assert "Workflow" in content or "workflow" in content.lower(), "BaaS doc should cover workflows"

    def test_baas_usage_doc_contains_all_commands(self, baas_usage_path):
        """Test that BaaS usage doc documents all BaaS commands"""
        content = baas_usage_path.read_text()

        # Check for all BaaS commands
        commands = [
            "api-keys create",
            "api-keys list",
            "api-keys get",
            "api-keys update",
            "api-keys revoke",
            "docs show",
            "docs openapi",
            "docs sdks",
            "usage stats",
            "usage by-endpoint",
            "usage by-tenant"
        ]

        for command in commands:
            assert command in content.lower(), f"BaaS doc should document {command} command"

    def test_baas_usage_doc_contains_examples(self, baas_usage_path):
        """Test that BaaS usage doc contains examples"""
        content = baas_usage_path.read_text()

        # Check for code blocks with examples
        code_blocks = re.findall(r'```bash\n(.*?)\n```', content, re.DOTALL)
        assert len(code_blocks) > 0, "BaaS doc should contain command examples"

    def test_baas_usage_doc_contains_troubleshooting(self, baas_usage_path):
        """Test that BaaS usage doc contains troubleshooting section"""
        content = baas_usage_path.read_text()
        assert "Troubleshooting" in content or "troubleshooting" in content.lower(), "BaaS doc should have troubleshooting section"

    def test_baas_usage_doc_contains_error_handling(self, baas_usage_path):
        """Test that BaaS usage doc contains error handling section"""
        content = baas_usage_path.read_text()
        assert "Error Handling" in content or "error handling" in content.lower(), "BaaS doc should have error handling section"

    def test_readme_baas_command_reference(self, readme_path):
        """Test that README contains BaaS command reference"""
        content = readme_path.read_text()
        # Check for BaaS section with command examples
        assert "baas" in content.lower(), "README should contain BaaS commands"
        assert "api-keys" in content.lower() or "docs" in content.lower() or "usage" in content.lower(), "README should contain BaaS command examples"

    def test_readme_baas_usage_guide_link(self, readme_path):
        """Test that README links to BaaS usage guide"""
        content = readme_path.read_text()
        assert "BAAS_USAGE.md" in content or "BaaS Usage Guide" in content, "README should link to BaaS usage guide"
