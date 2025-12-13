"""
Unit Tests for Context Fields Promotion
"""
import pytest
from hub.apps.contracts.context_fields import (
    promote_context_fields,
    extract_context_fields_from_extensions
)


class TestPromoteContextFields:
    """Test promoting context fields from extensions to info"""
    
    def test_promote_status(self):
        """Test promoting status field"""
        hub_contract = {'info': {}}
        original = {'extensions': {'status': 'ACTIVE'}}
        result = promote_context_fields(hub_contract, original)
        assert result['info']['status'] == 'ACTIVE'
    
    def test_promote_domain(self):
        """Test promoting domain field"""
        hub_contract = {'info': {}}
        original = {'extensions': {'domain': 'example.com'}}
        result = promote_context_fields(hub_contract, original)
        assert result['info']['domain'] == 'example.com'
    
    def test_promote_tenant(self):
        """Test promoting tenant field"""
        hub_contract = {'info': {}}
        original = {'extensions': {'tenant': 'tenant-123'}}
        result = promote_context_fields(hub_contract, original)
        assert result['info']['tenant'] == 'tenant-123'
    
    def test_promote_multiple_fields(self):
        """Test promoting multiple context fields"""
        hub_contract = {'info': {}}
        original = {
            'extensions': {
                'status': 'ACTIVE',
                'domain': 'example.com',
                'tenant': 'tenant-123'
            }
        }
        result = promote_context_fields(hub_contract, original)
        assert result['info']['status'] == 'ACTIVE'
        assert result['info']['domain'] == 'example.com'
        assert result['info']['tenant'] == 'tenant-123'
    
    def test_promote_from_top_level(self):
        """Test promoting from top-level of original contract"""
        hub_contract = {'info': {}}
        original = {'status': 'ACTIVE', 'domain': 'example.com'}
        result = promote_context_fields(hub_contract, original)
        assert result['info']['status'] == 'ACTIVE'
        assert result['info']['domain'] == 'example.com'
    
    def test_do_not_overwrite_existing(self):
        """Test that existing info fields are not overwritten"""
        hub_contract = {'info': {'status': 'DRAFT'}}
        original = {'extensions': {'status': 'ACTIVE'}}
        result = promote_context_fields(hub_contract, original)
        assert result['info']['status'] == 'DRAFT'  # Should not overwrite


class TestExtractContextFieldsFromExtensions:
    """Test extracting context fields from extensions"""
    
    def test_extract_all_fields(self):
        """Test extracting all context fields"""
        extensions = {
            'status': 'ACTIVE',
            'domain': 'example.com',
            'tenant': 'tenant-123',
            'dataProduct': 'product-1',
            'links': [],
            'authoritativeDefinitions': {}
        }
        result = extract_context_fields_from_extensions(extensions)
        assert len(result) == 6
        assert result['status'] == 'ACTIVE'
        assert result['domain'] == 'example.com'

