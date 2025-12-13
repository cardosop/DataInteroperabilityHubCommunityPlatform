"""
Performance optimization utilities for contract operations.

Implements optimizations for:
- Large contract JSON handling
- Query result optimization
- Batch operations
"""
import json
from typing import Any, Dict, List, Optional
from django.db.models import QuerySet
from django.conf import settings

# Maximum contract JSON size before optimization (1MB)
MAX_CONTRACT_JSON_SIZE = getattr(settings, 'MAX_CONTRACT_JSON_SIZE', 1024 * 1024)

# Chunk size for batch operations
BATCH_CHUNK_SIZE = getattr(settings, 'BATCH_CHUNK_SIZE', 100)


def optimize_large_contract_json(hub_contract: Dict[str, Any]) -> Dict[str, Any]:
    """
    Optimize large contract JSON by compressing or removing unnecessary data.
    
    Args:
        hub_contract: HubContract dictionary
    
    Returns:
        Optimized HubContract dictionary
    """
    # Calculate current size
    json_str = json.dumps(hub_contract)
    size_bytes = len(json_str.encode('utf-8'))
    
    # If size is acceptable, return as-is
    if size_bytes <= MAX_CONTRACT_JSON_SIZE:
        return hub_contract
    
    # Create optimized version
    optimized = hub_contract.copy()
    
    # Remove or compress large fields
    # 1. Compress sample_data if present (move to external storage)
    if 'sample_data' in optimized:
        # In production, move to external storage and keep reference
        # For now, remove if too large
        sample_data_str = json.dumps(optimized['sample_data'])
        if len(sample_data_str.encode('utf-8')) > 100 * 1024:  # >100KB
            optimized['sample_data'] = None
            optimized['sample_data_ref'] = 'external_storage'
    
    # 2. Compress extensions if present
    if 'extensions' in optimized:
        extensions_str = json.dumps(optimized['extensions'])
        if len(extensions_str.encode('utf-8')) > 100 * 1024:
            # Keep only essential extensions
            essential_keys = ['odcs', 'source_paths']
            optimized['extensions'] = {
                k: v for k, v in optimized['extensions'].items()
                if k in essential_keys
            }
    
    # 3. Remove verbose metadata if present
    if 'normalization' in optimized:
        norm_data = optimized['normalization']
        if isinstance(norm_data, dict) and 'coverage' in norm_data:
            # Keep only summary, remove detailed coverage
            coverage = norm_data['coverage']
            if isinstance(coverage, dict):
                norm_data['coverage'] = {
                    'overall': coverage.get('overall'),
                    'sections': {}  # Remove detailed section data
                }
    
    return optimized


def batch_process_contracts(
    queryset: QuerySet,
    batch_size: int = BATCH_CHUNK_SIZE,
    processor: Optional[callable] = None
) -> List[Any]:
    """
    Process contracts in batches to avoid memory issues.
    
    Args:
        queryset: Django queryset
        batch_size: Number of contracts per batch
        processor: Optional function to process each contract
    
    Returns:
        List of processed results
    """
    results = []
    total = queryset.count()
    
    for offset in range(0, total, batch_size):
        batch = queryset[offset:offset + batch_size]
        
        if processor:
            batch_results = [processor(contract) for contract in batch]
            results.extend(batch_results)
        else:
            results.extend(list(batch))
    
    return results


def optimize_queryset_for_large_json(queryset: QuerySet) -> QuerySet:
    """
    Optimize queryset to handle large JSONB fields efficiently.
    
    Args:
        queryset: Django queryset
    
    Returns:
        Optimized queryset
    """
    # Use defer() to exclude large JSONB field from initial query if not needed
    # queryset = queryset.defer('hub_contract_json')
    
    # Or use only() to select only needed fields
    # queryset = queryset.only('id', 'status', 'created_at')
    
    # For now, return as-is (can be optimized based on specific use case)
    return queryset


def estimate_contract_json_size(hub_contract: Dict[str, Any]) -> int:
    """
    Estimate size of contract JSON in bytes.
    
    Args:
        hub_contract: HubContract dictionary
    
    Returns:
        Estimated size in bytes
    """
    json_str = json.dumps(hub_contract)
    return len(json_str.encode('utf-8'))


def should_optimize_contract(hub_contract: Dict[str, Any]) -> bool:
    """
    Check if contract should be optimized.
    
    Args:
        hub_contract: HubContract dictionary
    
    Returns:
        True if contract should be optimized
    """
    size = estimate_contract_json_size(hub_contract)
    return size > MAX_CONTRACT_JSON_SIZE


def compress_contract_json(hub_contract: Dict[str, Any], compression_level: int = 6) -> bytes:
    """
    Compress contract JSON using gzip.
    
    Args:
        hub_contract: HubContract dictionary
        compression_level: Gzip compression level (0-9)
    
    Returns:
        Compressed bytes
    """
    import gzip
    
    json_str = json.dumps(hub_contract)
    json_bytes = json_str.encode('utf-8')
    
    compressed = gzip.compress(json_bytes, compresslevel=compression_level)
    return compressed


def decompress_contract_json(compressed: bytes) -> Dict[str, Any]:
    """
    Decompress contract JSON from gzip.
    
    Args:
        compressed: Compressed bytes
    
    Returns:
        HubContract dictionary
    """
    import gzip
    
    decompressed = gzip.decompress(compressed)
    json_str = decompressed.decode('utf-8')
    return json.loads(json_str)

