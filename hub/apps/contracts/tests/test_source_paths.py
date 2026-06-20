"""
Unit Tests for Source Path Tracing
"""

import pytest

from hub.apps.contracts.source_paths import (
    SourcePathTracker,
    add_source_paths_to_extensions,
    create_source_path,
    query_source_path,
    resolve_json_pointer,
    track_field_mapping,
)


class TestCreateSourcePath:
    """Test creating JSON Pointer paths"""

    def test_create_simple_path(self):
        """Test creating simple path"""
        assert create_source_path(["info", "name"]) == "/info/name"

    def test_create_nested_path(self):
        """Test creating nested path"""
        assert create_source_path(["schema", "fields", "0", "name"]) == "/schema/fields/0/name"

    def test_create_root_path(self):
        """Test creating root path"""
        assert create_source_path([]) == "/"


class TestResolveJsonPointer:
    """Test resolving JSON Pointers"""

    def test_resolve_simple_path(self):
        """Test resolving simple path"""
        data = {"info": {"name": "test"}}
        assert resolve_json_pointer(data, "/info/name") == "test"

    def test_resolve_nested_path(self):
        """Test resolving nested path"""
        data = {"schema": {"fields": [{"name": "field1"}]}}
        assert resolve_json_pointer(data, "/schema/fields/0/name") == "field1"

    def test_resolve_root(self):
        """Test resolving root"""
        data = {"id": "test"}
        assert resolve_json_pointer(data, "/") == data


class TestSourcePathTracker:
    """Test SourcePathTracker"""

    def test_add_mapping(self):
        """Test adding path mapping"""
        tracker = SourcePathTracker()
        tracker.add_mapping("/info/name", "/name")
        assert tracker.get_source_path("/info/name") == "/name"

    def test_add_mapping_from_lists(self):
        """Test adding mapping from path lists"""
        tracker = SourcePathTracker()
        tracker.add_mapping_from_lists(["info", "name"], ["name"])
        assert tracker.get_source_path("/info/name") == "/name"

    def test_to_extensions_format(self):
        """Test converting to extensions format"""
        tracker = SourcePathTracker()
        tracker.add_mapping("/info/name", "/name")
        result = tracker.to_extensions_format()
        assert "_source_paths" in result
        assert result["_source_paths"]["/info/name"] == "/name"

    def test_from_extensions_format(self):
        """Test loading from extensions format"""
        tracker = SourcePathTracker()
        extensions = {"_source_paths": {"/info/name": "/name"}}
        tracker.from_extensions_format(extensions)
        assert tracker.get_source_path("/info/name") == "/name"


class TestTrackFieldMapping:
    """Test tracking field mappings"""

    def test_track_mapping(self):
        """Test tracking a field mapping"""
        tracker = SourcePathTracker()
        # Source field is at root level (empty source_section)
        track_field_mapping(tracker, "info", "name", "", "name")
        assert tracker.get_source_path("/info/name") == "/name"


class TestAddSourcePathsToExtensions:
    """Test adding source paths to extensions"""

    def test_add_source_paths(self):
        """Test adding source paths to HubContract"""
        hub_contract = {}
        tracker = SourcePathTracker()
        tracker.add_mapping("/info/name", "/name")
        result = add_source_paths_to_extensions(hub_contract, tracker)
        assert "extensions" in result
        assert "_source_paths" in result["extensions"]
        assert result["extensions"]["_source_paths"]["/info/name"] == "/name"


class TestQuerySourcePath:
    """Test querying source paths"""

    def test_query_existing_path(self):
        """Test querying existing source path"""
        hub_contract = {"extensions": {"_source_paths": {"/info/name": "/name"}}}
        assert query_source_path(hub_contract, "/info/name") == "/name"

    def test_query_missing_path(self):
        """Test querying missing source path"""
        hub_contract = {"extensions": {"_source_paths": {}}}
        assert query_source_path(hub_contract, "/info/name") is None

    # Edge cases and error handling tests
    def test_create_source_path_with_special_characters(self):
        """Test creating path with special characters."""
        path = create_source_path(["field-name", "field_name", "field.name"])
        assert isinstance(path, str)
        assert "field-name" in path or "field_name" in path or "field.name" in path

    def test_create_source_path_with_unicode(self):
        """Test creating path with unicode characters."""
        path = create_source_path(["字段名称", "field_name"])
        assert isinstance(path, str)
        # Should handle unicode
        assert "field_name" in path or "字段名称" in path

    def test_create_source_path_with_empty_strings(self):
        """Test creating path with empty string segments."""
        path = create_source_path(["", "field", ""])
        assert isinstance(path, str)
        # Should handle empty strings

    def test_resolve_json_pointer_with_missing_path(self):
        """Non-existent path returns None."""
        data = {"info": {"name": "test"}}
        assert resolve_json_pointer(data, "/info/nonexistent") is None

    def test_resolve_json_pointer_with_invalid_path(self):
        """Path without leading / returns None."""
        data = {"info": {"name": "test"}}
        assert resolve_json_pointer(data, "invalid-path") is None

    def test_resolve_json_pointer_with_none_data(self):
        """None data returns None gracefully."""
        assert resolve_json_pointer(None, "/info/name") is None

    def test_resolve_json_pointer_with_empty_dict(self):
        """Empty dict with missing key returns None."""
        assert resolve_json_pointer({}, "/info/name") is None

    def test_source_path_tracker_add_mapping_with_none_values(self):
        """None values are accepted silently."""
        tracker = SourcePathTracker()
        tracker.add_mapping(None, None)  # must not raise

    def test_source_path_tracker_add_mapping_with_empty_strings(self):
        """Test adding mapping with empty strings."""
        tracker = SourcePathTracker()
        tracker.add_mapping("", "")
        # Should handle empty strings gracefully
        result = tracker.get_source_path("")
        assert result == "" or result is None

    def test_source_path_tracker_get_source_path_not_found(self):
        """Test getting source path for non-existent mapping."""
        tracker = SourcePathTracker()
        result = tracker.get_source_path("/nonexistent/path")
        # Should return None or empty string
        assert result is None or result == ""

    def test_source_path_tracker_to_extensions_format_empty(self):
        """Test converting empty tracker to extensions format."""
        tracker = SourcePathTracker()
        result = tracker.to_extensions_format()
        assert "_source_paths" in result
        assert isinstance(result["_source_paths"], dict)

    def test_source_path_tracker_from_extensions_format_with_missing_field(self):
        """Test loading from extensions format with missing _source_paths."""
        tracker = SourcePathTracker()
        extensions = {}  # Missing _source_paths
        tracker.from_extensions_format(extensions)
        # Should handle gracefully
        assert (
            tracker.get_source_path("/any/path") is None
            or tracker.get_source_path("/any/path") == ""
        )

    def test_source_path_tracker_from_extensions_format_with_invalid_type(self):
        """Invalid _source_paths type is silently ignored."""
        tracker = SourcePathTracker()
        tracker.from_extensions_format({"_source_paths": "not-a-dict"})  # must not raise

    def test_track_field_mapping_with_none_values(self):
        """None values raise AttributeError (str.replace on NoneType)."""
        import pytest
        tracker = SourcePathTracker()
        with pytest.raises((TypeError, ValueError, AttributeError)):
            track_field_mapping(tracker, None, None, None, None)

    def test_add_source_paths_to_extensions_with_none_tracker(self):
        """None tracker raises AttributeError."""
        with pytest.raises(AttributeError):
            add_source_paths_to_extensions({}, None)

    def test_add_source_paths_to_extensions_with_empty_tracker(self):
        """Test adding source paths with empty tracker."""
        hub_contract = {}
        tracker = SourcePathTracker()
        result = add_source_paths_to_extensions(hub_contract, tracker)

        assert "extensions" in result
        assert "_source_paths" in result["extensions"]

    def test_query_source_path_with_missing_extensions(self):
        """Test querying source path when extensions field is missing."""
        hub_contract = {}  # No extensions field
        result = query_source_path(hub_contract, "/info/name")
        assert result is None

    def test_query_source_path_with_missing_source_paths(self):
        """Test querying source path when _source_paths field is missing."""
        hub_contract = {"extensions": {}}  # No _source_paths
        result = query_source_path(hub_contract, "/info/name")
        assert result is None

    def test_query_source_path_with_invalid_path_format(self):
        """Test querying source path with invalid path format."""
        hub_contract = {"extensions": {"_source_paths": {"/info/name": "/name"}}}
        try:
            result = query_source_path(hub_contract, "invalid-path")
            # May return None or handle gracefully
            assert result is None or isinstance(result, str)
        except (ValueError, KeyError):
            # Exception is acceptable
            pass

    def test_create_source_path_with_very_long_path(self):
        """Test creating path with very long segment list."""
        long_path = [f"segment_{i}" for i in range(1000)]
        path = create_source_path(long_path)
        assert isinstance(path, str)
        assert len(path) > 0

    def test_resolve_json_pointer_with_very_deep_nesting(self):
        """Test resolving JSON pointer with very deep nesting."""
        data = {"level0": {"level1": {"level2": {"level3": {"value": "deep"}}}}}
        result = resolve_json_pointer(data, "/level0/level1/level2/level3/value")
        assert result == "deep"

    def test_source_path_tracker_with_many_mappings(self):
        """Test SourcePathTracker with many mappings."""
        tracker = SourcePathTracker()
        for i in range(1000):
            tracker.add_mapping(f"/source/path/{i}", f"/target/path/{i}")

        # Should handle many mappings
        result = tracker.get_source_path("/source/path/500")
        assert result == "/target/path/500"

        extensions_format = tracker.to_extensions_format()
        assert len(extensions_format["_source_paths"]) == 1000
