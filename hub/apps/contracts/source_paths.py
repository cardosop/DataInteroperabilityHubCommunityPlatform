"""
Source Path Tracing

Tracks JSON Pointer paths for all normalized fields during normalization.
"""
from typing import Dict, Any, List, Optional
import json


def create_source_path(field_path: List[str]) -> str:
    """
    Create JSON Pointer path from field path list.
    
    Args:
        field_path: List of field names (e.g., ['info', 'name'])
    
    Returns:
        JSON Pointer path (e.g., '/info/name')
    """
    if not field_path:
        return '/'
    
    # Escape special characters in JSON Pointer
    escaped_path = []
    for segment in field_path:
        # Replace ~ with ~0 and / with ~1
        escaped = segment.replace('~', '~0').replace('/', '~1')
        escaped_path.append(escaped)
    
    return '/' + '/'.join(escaped_path)


def resolve_json_pointer(data: Dict[str, Any], pointer: str) -> Optional[Any]:
    """
    Resolve JSON Pointer to value in data.
    
    Args:
        data: Data dictionary
        pointer: JSON Pointer path (e.g., '/info/name')
    
    Returns:
        Value at pointer path or None if not found
    """
    if not pointer or pointer == '/':
        return data
    
    # Remove leading /
    path = pointer.lstrip('/')
    if not path:
        return data
    
    # Split path and unescape
    segments = []
    for segment in path.split('/'):
        # Unescape ~0 to ~ and ~1 to /
        unescaped = segment.replace('~1', '/').replace('~0', '~')
        segments.append(unescaped)
    
    # Navigate through data
    current = data
    for segment in segments:
        if isinstance(current, dict):
            current = current.get(segment)
        elif isinstance(current, list):
            try:
                index = int(segment)
                if 0 <= index < len(current):
                    current = current[index]
                else:
                    return None
            except ValueError:
                return None
        else:
            return None
        
        if current is None:
            return None
    
    return current


class SourcePathTracker:
    """
    Tracks source paths for normalized fields.
    
    Maintains a mapping of HubContract field paths to original contract paths.
    """
    
    def __init__(self):
        self.paths: Dict[str, str] = {}  # hub_path -> source_path
    
    def add_mapping(self, hub_path: str, source_path: str):
        """
        Add mapping from HubContract path to source path.
        
        Args:
            hub_path: JSON Pointer path in HubContract
            source_path: JSON Pointer path in original contract
        """
        self.paths[hub_path] = source_path
    
    def add_mapping_from_lists(self, hub_path_list: List[str], source_path_list: List[str]):
        """
        Add mapping from path lists.
        
        Args:
            hub_path_list: List of field names for HubContract path
            source_path_list: List of field names for source path
        """
        hub_path = create_source_path(hub_path_list)
        source_path = create_source_path(source_path_list)
        self.add_mapping(hub_path, source_path)
    
    def get_source_path(self, hub_path: str) -> Optional[str]:
        """
        Get source path for a HubContract path.
        
        Args:
            hub_path: JSON Pointer path in HubContract
        
        Returns:
            Source path or None if not found
        """
        return self.paths.get(hub_path)
    
    def get_all_paths(self) -> Dict[str, str]:
        """
        Get all path mappings.
        
        Returns:
            Dictionary of all path mappings
        """
        return self.paths.copy()
    
    def to_extensions_format(self) -> Dict[str, Any]:
        """
        Convert path mappings to extensions._source_paths format.
        
        Returns:
            Dictionary in format suitable for extensions._source_paths
        """
        return {
            '_source_paths': self.paths
        }
    
    def from_extensions_format(self, extensions: Dict[str, Any]):
        """
        Load path mappings from extensions._source_paths format.
        
        Args:
            extensions: Extensions dictionary with _source_paths
        """
        if not isinstance(extensions, dict):
            return
        
        source_paths = extensions.get('_source_paths', {})
        if isinstance(source_paths, dict):
            self.paths.update(source_paths)


def track_field_mapping(
    tracker: SourcePathTracker,
    hub_section: str,
    hub_field: str,
    source_section: str,
    source_field: str
):
    """
    Track mapping of a field from source to HubContract.
    
    Args:
        tracker: SourcePathTracker instance
        hub_section: HubContract section name (e.g., 'info')
        hub_field: HubContract field name (e.g., 'name')
        source_section: Source section name (e.g., 'info' or '' for root level)
        source_field: Source field name (e.g., 'name')
    """
    hub_path = create_source_path([hub_section, hub_field])
    # If source_section is empty, field is at root level
    if not source_section:
        source_path = create_source_path([source_field])
    else:
        source_path = create_source_path([source_section, source_field])
    tracker.add_mapping(hub_path, source_path)


def add_source_paths_to_extensions(hub_contract: Dict[str, Any], tracker: SourcePathTracker) -> Dict[str, Any]:
    """
    Add source paths to HubContract extensions.
    
    Args:
        hub_contract: HubContract dictionary
        tracker: SourcePathTracker with path mappings
    
    Returns:
        HubContract with _source_paths added to extensions
    """
    if not isinstance(hub_contract, dict):
        hub_contract = {}
    
    # Ensure extensions section exists
    if 'extensions' not in hub_contract:
        hub_contract['extensions'] = {}
    
    # Add source paths
    source_paths_data = tracker.to_extensions_format()
    hub_contract['extensions'].update(source_paths_data)
    
    return hub_contract


def query_source_path(hub_contract: Dict[str, Any], hub_path: str) -> Optional[str]:
    """
    Query source path for a HubContract field path.
    
    Args:
        hub_contract: HubContract dictionary
        hub_path: JSON Pointer path in HubContract
    
    Returns:
        Source path or None if not found
    """
    extensions = hub_contract.get('extensions', {})
    if not isinstance(extensions, dict):
        return None
    
    source_paths = extensions.get('_source_paths', {})
    if not isinstance(source_paths, dict):
        return None
    
    return source_paths.get(hub_path)

