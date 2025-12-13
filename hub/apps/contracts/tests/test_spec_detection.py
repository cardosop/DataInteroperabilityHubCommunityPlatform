"""
Unit Tests for Spec Detection and Metadata Tracking
"""
import pytest
from hub.apps.contracts.spec_detection import (
    detect_spec_type,
    extract_original_spec_metadata,
    extract_conformance_info,
    store_original_spec_metadata
)
from hub.apps.contracts.models import OriginalSpecType


class TestDetectSpecType:
    """Test spec type detection"""
    
    def test_detect_odcs(self):
        """Test detecting ODCS"""
        contract = {'apiVersion': 'odcs.io/v3.0.2', 'kind': 'DataContract'}
        spec_type, spec_version = detect_spec_type(contract)
        assert spec_type == OriginalSpecType.ODCS
        assert spec_version == '3.0.2'
    
    def test_detect_odcs_with_v_prefix(self):
        """Test detecting ODCS with v prefix"""
        contract = {'apiVersion': 'odcs.io/v3.0.2', 'kind': 'DataContract'}
        spec_type, spec_version = detect_spec_type(contract)
        assert spec_type == OriginalSpecType.ODCS
        assert 'v' not in spec_version or spec_version.startswith('v')


class TestExtractOriginalSpecMetadata:
    """Test extracting original spec metadata"""
    
    def test_extract_odcs_metadata(self):
        """Test extracting ODCS metadata"""
        contract = {'apiVersion': 'odcs.io/v3.0.2', 'kind': 'DataContract'}
        metadata = extract_original_spec_metadata(contract)
        assert metadata['type'] == OriginalSpecType.ODCS
        assert 'version' in metadata


class TestExtractConformanceInfo:
    """Test extracting conformance information"""
    
    def test_extract_dct_conforms_to(self):
        """Test extracting dct:conformsTo"""
        contract = {'dct:conformsTo': 'https://example.com/spec'}
        conforms_to = extract_conformance_info(contract, OriginalSpecType.ODCS)
        assert conforms_to is not None
        assert conforms_to['uri'] == 'https://example.com/spec'


class TestStoreOriginalSpecMetadata:
    """Test storing original spec metadata in HubContract"""
    
    def test_store_metadata(self):
        """Test storing metadata in HubContract"""
        hub_contract = {'id': 'test'}
        original_contract = {'apiVersion': 'odcs.io/v3.0.2', 'kind': 'DataContract', 'id': 'test'}
        result = store_original_spec_metadata(hub_contract, original_contract)
        assert 'original_spec' in result
        assert result['original_spec']['type'] == OriginalSpecType.ODCS

