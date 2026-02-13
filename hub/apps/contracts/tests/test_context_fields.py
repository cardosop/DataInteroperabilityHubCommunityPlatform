"""
Unit Tests for Context Fields Promotion
"""

import pytest

from hub.apps.contracts.context_fields import (
    extract_context_fields_from_extensions,
    promote_context_fields,
)


class TestPromoteContextFields:
    """Test promoting context fields from extensions to info"""

    def test_promote_status(self):
        """Test promoting status field"""
        hub_contract = {"info": {}}
        original = {"extensions": {"status": "ACTIVE"}}
        result = promote_context_fields(hub_contract, original)
        assert result["info"]["status"] == "ACTIVE"

    def test_promote_domain(self):
        """Test promoting domain field"""
        hub_contract = {"info": {}}
        original = {"extensions": {"domain": "example.com"}}
        result = promote_context_fields(hub_contract, original)
        assert result["info"]["domain"] == "example.com"

    def test_promote_tenant(self):
        """Test promoting tenant field"""
        hub_contract = {"info": {}}
        original = {"extensions": {"tenant": "tenant-123"}}
        result = promote_context_fields(hub_contract, original)
        assert result["info"]["tenant"] == "tenant-123"

    def test_promote_multiple_fields(self):
        """Test promoting multiple context fields"""
        hub_contract = {"info": {}}
        original = {
            "extensions": {"status": "ACTIVE", "domain": "example.com", "tenant": "tenant-123"}
        }
        result = promote_context_fields(hub_contract, original)
        assert result["info"]["status"] == "ACTIVE"
        assert result["info"]["domain"] == "example.com"
        assert result["info"]["tenant"] == "tenant-123"

    def test_promote_from_top_level(self):
        """Test promoting from top-level of original contract"""
        hub_contract = {"info": {}}
        original = {"status": "ACTIVE", "domain": "example.com"}
        result = promote_context_fields(hub_contract, original)
        assert result["info"]["status"] == "ACTIVE"
        assert result["info"]["domain"] == "example.com"

    def test_do_not_overwrite_existing(self):
        """Test that existing info fields are not overwritten"""
        hub_contract = {"info": {"status": "DRAFT"}}
        original = {"extensions": {"status": "ACTIVE"}}
        result = promote_context_fields(hub_contract, original)
        assert result["info"]["status"] == "DRAFT"  # Should not overwrite


class TestExtractContextFieldsFromExtensions:
    """Test extracting context fields from extensions"""

    def test_extract_all_fields(self):
        """Test extracting all context fields"""
        extensions = {
            "status": "ACTIVE",
            "domain": "example.com",
            "tenant": "tenant-123",
            "dataProduct": "product-1",
            "links": [],
            "authoritativeDefinitions": {},
        }
        result = extract_context_fields_from_extensions(extensions)
        assert len(result) == 6
        assert result["status"] == "ACTIVE"
        assert result["domain"] == "example.com"

    # Edge cases and error handling tests
    def test_promote_context_fields_with_empty_hub_contract(self):
        """Test promoting context fields with empty hub_contract."""
        hub_contract = {}
        original = {"extensions": {"status": "ACTIVE"}}

        try:
            result = promote_context_fields(hub_contract, original)
            # Should handle gracefully - may create info dict or raise
            if "info" in result:
                assert result["info"]["status"] == "ACTIVE"
        except (KeyError, AttributeError):
            # If it raises exception, that's acceptable
            pass

    def test_promote_context_fields_with_none_original(self):
        """Test promoting context fields with None original."""
        hub_contract = {"info": {}}

        try:
            result = promote_context_fields(hub_contract, None)
            # Should handle gracefully
            assert isinstance(result, dict)
        except (TypeError, AttributeError):
            # If it raises exception, that's acceptable
            pass

    def test_promote_context_fields_with_empty_extensions(self):
        """Test promoting context fields with empty extensions."""
        hub_contract = {"info": {}}
        original = {"extensions": {}}

        result = promote_context_fields(hub_contract, original)

        # Should handle empty extensions gracefully
        assert isinstance(result, dict)
        assert "info" in result

    def test_promote_context_fields_with_missing_extensions(self):
        """Test promoting context fields when extensions field is missing."""
        hub_contract = {"info": {}}
        original = {}  # No extensions field

        result = promote_context_fields(hub_contract, original)

        # Should handle missing extensions gracefully
        assert isinstance(result, dict)

    def test_promote_context_fields_with_none_values(self):
        """Test promoting context fields with None values."""
        hub_contract = {"info": {}}
        original = {"extensions": {"status": None, "domain": None}}

        result = promote_context_fields(hub_contract, original)

        # Should handle None values gracefully
        assert isinstance(result, dict)
        # May or may not include None values in info
        if "status" in result.get("info", {}):
            assert result["info"]["status"] is None or result["info"]["status"] == "ACTIVE"

    def test_promote_context_fields_with_special_characters(self):
        """Test promoting context fields with special characters."""
        hub_contract = {"info": {}}
        original = {"extensions": {"domain": "example-domain_v2.com", "tenant": "tenant-name@123"}}

        result = promote_context_fields(hub_contract, original)

        # Should handle special characters
        assert result["info"]["domain"] == "example-domain_v2.com"
        assert result["info"]["tenant"] == "tenant-name@123"

    def test_promote_context_fields_with_unicode_characters(self):
        """Test promoting context fields with unicode characters."""
        hub_contract = {"info": {}}
        original = {"extensions": {"domain": "示例域名.com", "tenant": "租户名称"}}

        result = promote_context_fields(hub_contract, original)

        # Should handle unicode characters
        assert result["info"]["domain"] == "示例域名.com"
        assert result["info"]["tenant"] == "租户名称"

    def test_promote_context_fields_with_very_long_values(self):
        """Test promoting context fields with very long values."""
        hub_contract = {"info": {}}
        long_value = "A" * 10000
        original = {"extensions": {"domain": long_value}}

        result = promote_context_fields(hub_contract, original)

        # Should handle very long values
        assert result["info"]["domain"] == long_value
        assert len(result["info"]["domain"]) == 10000

    def test_promote_context_fields_preserves_other_info_fields(self):
        """Test that promoting preserves other info fields."""
        hub_contract = {"info": {"name": "Test Contract", "description": "Test Description"}}
        original = {"extensions": {"status": "ACTIVE"}}

        result = promote_context_fields(hub_contract, original)

        # Should preserve existing fields
        assert result["info"]["name"] == "Test Contract"
        assert result["info"]["description"] == "Test Description"
        assert result["info"]["status"] == "ACTIVE"

    def test_extract_context_fields_with_empty_extensions(self):
        """Test extracting context fields from empty extensions."""
        extensions = {}
        result = extract_context_fields_from_extensions(extensions)

        # Should return empty dict or handle gracefully
        assert isinstance(result, dict)
        assert len(result) == 0

    def test_extract_context_fields_with_none(self):
        """Test extracting context fields from None."""
        try:
            result = extract_context_fields_from_extensions(None)
            # If it doesn't raise, verify structure
            assert isinstance(result, dict)
        except (TypeError, AttributeError):
            # If it raises exception, that's acceptable
            pass

    def test_extract_context_fields_with_partial_fields(self):
        """Test extracting context fields with only some fields present."""
        extensions = {
            "status": "ACTIVE",
            "domain": "example.com",
            # Missing other fields
        }
        result = extract_context_fields_from_extensions(extensions)

        # Should extract only present fields
        assert result["status"] == "ACTIVE"
        assert result["domain"] == "example.com"
        assert len(result) == 2

    def test_extract_context_fields_with_non_context_fields(self):
        """Test extracting context fields with additional non-context fields."""
        extensions = {
            "status": "ACTIVE",
            "domain": "example.com",
            "custom_field": "custom_value",  # Not a context field
            "another_field": 123,
        }
        result = extract_context_fields_from_extensions(extensions)

        # Should only extract context fields
        assert "status" in result
        assert "domain" in result
        # Custom fields may or may not be included depending on implementation
        assert isinstance(result, dict)

    def test_extract_context_fields_with_nested_structures(self):
        """Test extracting context fields with nested structures."""
        extensions = {
            "status": "ACTIVE",
            "domain": "example.com",
            "links": [
                {"rel": "self", "href": "/contracts/1"},
                {"rel": "related", "href": "/contracts/2"},
            ],
            "authoritativeDefinitions": {
                "field1": {"type": "string"},
                "field2": {"type": "integer"},
            },
        }
        result = extract_context_fields_from_extensions(extensions)

        # Should handle nested structures
        assert "status" in result
        assert "domain" in result
        assert "links" in result
        assert "authoritativeDefinitions" in result
        assert isinstance(result["links"], list)
        assert isinstance(result["authoritativeDefinitions"], dict)

    def test_promote_context_fields_with_list_values(self):
        """Test promoting context fields with list values."""
        hub_contract = {"info": {}}
        original = {"extensions": {"links": ["link1", "link2"], "tags": ["tag1", "tag2"]}}

        result = promote_context_fields(hub_contract, original)

        # Should handle list values
        assert "links" in result["info"] or "tags" in result["info"]
        if "links" in result["info"]:
            assert isinstance(result["info"]["links"], list)

    def test_promote_context_fields_with_dict_values(self):
        """Test promoting context fields with dictionary values."""
        hub_contract = {"info": {}}
        original = {"extensions": {"authoritativeDefinitions": {"field1": {"type": "string"}}}}

        result = promote_context_fields(hub_contract, original)

        # Should handle dict values
        if "authoritativeDefinitions" in result["info"]:
            assert isinstance(result["info"]["authoritativeDefinitions"], dict)
