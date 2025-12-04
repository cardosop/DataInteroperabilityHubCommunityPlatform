"""
Pytest configuration and fixtures for CLI tests.
"""
import pytest
import tempfile
import os
import yaml
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from datahub_cli.config import Config, CONFIG_FILE, CONFIG_DIR


@pytest.fixture
def temp_config_dir(tmp_path, monkeypatch):
    """Create a temporary config directory"""
    config_dir = tmp_path / ".datahub"
    config_dir.mkdir()
    config_file = config_dir / "config.yaml"
    
    # Patch the config paths at module level
    monkeypatch.setattr('datahub_cli.config.CONFIG_DIR', config_dir)
    monkeypatch.setattr('datahub_cli.config.CONFIG_FILE', config_file)
    
    return config_dir, config_file


@pytest.fixture
def mock_config(temp_config_dir):
    """Create a config instance (uses real Config, not a mock)"""
    from datahub_cli.config import config
    return config


@pytest.fixture
def mock_api_client():
    """Create a mock API client"""
    with patch('datahub_cli.api_client.api_client') as mock_client:
        yield mock_client


@pytest.fixture
def mock_auth_manager():
    """Create a mock auth manager"""
    with patch('datahub_cli.auth.auth_manager') as mock_auth:
        mock_auth.ensure_authenticated.return_value = True
        mock_auth.get_auth_headers.return_value = {
            'Authorization': 'Bearer test-token',
            'Content-Type': 'application/json'
        }
        yield mock_auth


@pytest.fixture
def sample_asset():
    """Sample asset data"""
    return {
        'id': '123e4567-e89b-12d3-a456-426614174000',
        'name': 'Test Asset',
        'key': 'test-asset',
        'status': 'DRAFT',
        'domain': 'test',
        'visibility': 'INTERNAL',
        'created_at': '2025-01-01T00:00:00Z',
        'updated_at': '2025-01-01T00:00:00Z'
    }


@pytest.fixture
def sample_contract():
    """Sample contract data"""
    return {
        'id': '223e4567-e89b-12d3-a456-426614174000',
        'version': 1,
        'status': 'DRAFT',
        'asset_id': '123e4567-e89b-12d3-a456-426614174000',
        'original_spec_type': 'ODCS',
        'original_format': 'YAML',
        'normalization_status': 'NORMALIZED_OK',
        'created_at': '2025-01-01T00:00:00Z',
        'updated_at': '2025-01-01T00:00:00Z'
    }


@pytest.fixture
def sample_file():
    """Sample file data"""
    return {
        'id': '323e4567-e89b-12d3-a456-426614174000',
        'name': 'test.csv',
        'size': 1024,
        'status': 'UPLOADED',
        'content_type': 'text/csv',
        'created_at': '2025-01-01T00:00:00Z'
    }


@pytest.fixture
def sample_job():
    """Sample job data"""
    return {
        'id': '423e4567-e89b-12d3-a456-426614174000',
        'type': 'DQ_RUN',
        'status': 'PENDING',
        'resource_type': 'DATASET',
        'resource_id': '123e4567-e89b-12d3-a456-426614174000',
        'created_at': '2025-01-01T00:00:00Z'
    }

