"""
Unit Tests for Source Path Tracing
"""
import pytest
from hub.apps.contracts.source_paths import (
    create_source_path,
    resolve_json_pointer,
    SourcePathTracker,
    track_field_mapping,
    add_source_paths_to_extensions,
    query_source_path
)


class TestCreateSourcePath:
    """Test creating JSON Pointer paths"""
    
    def test_create_simple_path(self):
        """Test creating simple path"""
        assert create_source_path(['info', 'name']) == '/info/name'
    
    def test_create_nested_path(self):
        """Test creating nested path"""
        assert create_source_path(['schema', 'fields', '0', 'name']) == '/schema/fields/0/name'
    
    def test_create_root_path(self):
        """Test creating root path"""
        assert create_source_path([]) == '/'


class TestResolveJsonPointer:
    """Test resolving JSON Pointers"""
    
    def test_resolve_simple_path(self):
        """Test resolving simple path"""
        data = {'info': {'name': 'test'}}
        assert resolve_json_pointer(data, '/info/name') == 'test'
    
    def test_resolve_nested_path(self):
        """Test resolving nested path"""
        data = {'schema': {'fields': [{'name': 'field1'}]}}
        assert resolve_json_pointer(data, '/schema/fields/0/name') == 'field1'
    
    def test_resolve_root(self):
        """Test resolving root"""
        data = {'id': 'test'}
        assert resolve_json_pointer(data, '/') == data


class TestSourcePathTracker:
    """Test SourcePathTracker"""
    
    def test_add_mapping(self):
        """Test adding path mapping"""
        tracker = SourcePathTracker()
        tracker.add_mapping('/info/name', '/name')
        assert tracker.get_source_path('/info/name') == '/name'
    
    def test_add_mapping_from_lists(self):
        """Test adding mapping from path lists"""
        tracker = SourcePathTracker()
        tracker.add_mapping_from_lists(['info', 'name'], ['name'])
        assert tracker.get_source_path('/info/name') == '/name'
    
    def test_to_extensions_format(self):
        """Test converting to extensions format"""
        tracker = SourcePathTracker()
        tracker.add_mapping('/info/name', '/name')
        result = tracker.to_extensions_format()
        assert '_source_paths' in result
        assert result['_source_paths']['/info/name'] == '/name'
    
    def test_from_extensions_format(self):
        """Test loading from extensions format"""
        tracker = SourcePathTracker()
        extensions = {'_source_paths': {'/info/name': '/name'}}
        tracker.from_extensions_format(extensions)
        assert tracker.get_source_path('/info/name') == '/name'


class TestTrackFieldMapping:
    """Test tracking field mappings"""
    
    def test_track_mapping(self):
        """Test tracking a field mapping"""
        tracker = SourcePathTracker()
        # Source field is at root level (empty source_section)
        track_field_mapping(tracker, 'info', 'name', '', 'name')
        assert tracker.get_source_path('/info/name') == '/name'


class TestAddSourcePathsToExtensions:
    """Test adding source paths to extensions"""
    
    def test_add_source_paths(self):
        """Test adding source paths to HubContract"""
        hub_contract = {}
        tracker = SourcePathTracker()
        tracker.add_mapping('/info/name', '/name')
        result = add_source_paths_to_extensions(hub_contract, tracker)
        assert 'extensions' in result
        assert '_source_paths' in result['extensions']
        assert result['extensions']['_source_paths']['/info/name'] == '/name'


class TestQuerySourcePath:
    """Test querying source paths"""
    
    def test_query_existing_path(self):
        """Test querying existing source path"""
        hub_contract = {
            'extensions': {
                '_source_paths': {
                    '/info/name': '/name'
                }
            }
        }
        assert query_source_path(hub_contract, '/info/name') == '/name'
    
    def test_query_missing_path(self):
        """Test querying missing source path"""
        hub_contract = {'extensions': {'_source_paths': {}}}
        assert query_source_path(hub_contract, '/info/name') is None

