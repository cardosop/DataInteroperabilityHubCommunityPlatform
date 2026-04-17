"""
Tests for check_mvp_doc_boundary.py — validates that the boundary
checker catches deprecated SDK identifiers and external doc links.
"""

import sys
from pathlib import Path

import pytest

# Add scripts/ to path so we can import the checker
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from check_mvp_doc_boundary import (
    _check_external_doc_links,
    _check_wrong_sdk_identifiers,
)


class TestWrongSdkIdentifiers:
    def test_catches_datahub_sdk(self):
        errors = []
        _check_wrong_sdk_identifiers(
            "from datahub_sdk import MeshantClient",
            "test.md",
            errors,
        )
        assert len(errors) >= 1
        assert "datahub_sdk" in errors[0]

    def test_catches_meshant_client(self):
        errors = []
        _check_wrong_sdk_identifiers(
            "client = MeshantClient()",
            "test.md",
            errors,
        )
        assert len(errors) == 1
        assert "MeshantClient" in errors[0]

    def test_passes_correct_imports(self):
        errors = []
        _check_wrong_sdk_identifiers(
            "from datahub_interoperability import DataHubClient",
            "test.md",
            errors,
        )
        assert errors == []


class TestExternalDocLinks:
    @pytest.mark.parametrize(
        "link",
        [
            "[guide](../../RUNBOOKS.md)",
            "[ref](../../SECURITY_AND_COMPLIANCE.md)",
            "[dev](../../DEVELOPER_GUIDE.md#setup)",
            "[ops](../../DEPLOYMENT_AND_OPERATIONS.md)",
            "[stub](../../OPERATIONS.md)",
            "[api](../../API_ENDPOINTS_REFERENCE.md)",
        ],
    )
    def test_catches_external_links(self, link):
        errors = []
        _check_external_doc_links(link, "test.md", errors)
        assert len(errors) == 1
        assert "external doc" in errors[0]

    def test_passes_internal_links(self):
        errors = []
        _check_external_doc_links(
            "[api ref](../../api-reference/assets.md)",
            "test.md",
            errors,
        )
        assert errors == []

    def test_passes_plain_text_mention(self):
        errors = []
        _check_external_doc_links(
            "The RUNBOOKS.md file was previously used.",
            "test.md",
            errors,
        )
        assert errors == []
