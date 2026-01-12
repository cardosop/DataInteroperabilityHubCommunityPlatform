"""
CKAN Marketplace Test Fixtures

This module provides test fixtures for CKAN connector tests including:
- CKAN API response samples
- Test dataset (package) samples
- Test resource samples
- Fixture loading utilities
"""

from pathlib import Path
import json
from typing import Dict, Any, Optional

# Base directory for CKAN fixtures
FIXTURES_DIR = Path(__file__).parent


def load_fixture(relative_path: str) -> Dict[str, Any]:
    """
    Load a JSON fixture file.

    Args:
        relative_path: Path relative to fixtures directory (e.g., 'api_responses/status_show.json')

    Returns:
        Dictionary containing fixture data

    Raises:
        FileNotFoundError: If fixture file doesn't exist
        json.JSONDecodeError: If fixture file is invalid JSON
    """
    fixture_path = FIXTURES_DIR / relative_path
    if not fixture_path.exists():
        raise FileNotFoundError(f"Fixture not found: {fixture_path}")

    with open(fixture_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def get_api_response_fixture(action: str) -> Dict[str, Any]:
    """
    Get a CKAN API response fixture.

    Args:
        action: CKAN API action name (e.g., 'status_show', 'package_show')

    Returns:
        Dictionary containing API response data
    """
    return load_fixture(f'api_responses/{action}.json')


def get_dataset_fixture(name: str) -> Dict[str, Any]:
    """
    Get a test dataset (package) fixture.

    Args:
        name: Dataset fixture name (e.g., 'sample_dataset', 'multilingual_dataset')

    Returns:
        Dictionary containing dataset data
    """
    return load_fixture(f'datasets/{name}.json')


def get_resource_fixture(name: str) -> Dict[str, Any]:
    """
    Get a test resource fixture.

    Args:
        name: Resource fixture name (e.g., 'sample_resource', 'csv_resource')

    Returns:
        Dictionary containing resource data
    """
    return load_fixture(f'resources/{name}.json')

