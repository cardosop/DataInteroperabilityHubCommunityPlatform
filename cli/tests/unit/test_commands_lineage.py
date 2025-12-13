"""
Comprehensive unit tests for lineage CLI commands.

Tests all lineage commands: contract, model, field, full, visualize, impact.
"""
import pytest
import json
from click.testing import CliRunner
from unittest.mock import Mock, patch
from datahub_cli.main import cli
from datahub_cli.commands import lineage
from datahub_cli.api_client import api_client


class TestLineageContract:
    """Test lineage contract command"""
    
    def test_get_contract_lineage_success_table_format(self, runner, mock_api_client):
        """Test getting contract-level lineage in table format"""
        mock_data = {
            'contracts': [
                {'namespace': 'ns1', 'name': 'contract1'},
                {'namespace': 'ns2', 'name': 'contract2'}
            ]
        }
        mock_api_client.get.return_value = mock_data
        
        result = runner.invoke(cli, ['lineage', 'contract', 'contract-1'])
        
        assert result.exit_code == 0
        assert 'Contract Lineage' in result.output
        assert 'Upstream Contracts (2)' in result.output
        assert 'ns1/contract1' in result.output
        mock_api_client.get.assert_called_once_with('contracts/contract-1/lineage/contracts/')
    
    def test_get_contract_lineage_success_json_format(self, runner, mock_api_client):
        """Test getting contract-level lineage in JSON format"""
        mock_data = {
            'contracts': [
                {'namespace': 'ns1', 'name': 'contract1'}
            ]
        }
        mock_api_client.get.return_value = mock_data
        
        result = runner.invoke(cli, ['lineage', 'contract', 'contract-1', '--format', 'json'])
        
        assert result.exit_code == 0
        output_data = json.loads(result.output)
        assert 'contracts' in output_data
        assert len(output_data['contracts']) == 1
    
    def test_get_contract_lineage_empty(self, runner, mock_api_client):
        """Test getting contract-level lineage when no upstream contracts exist"""
        mock_data = {'contracts': []}
        mock_api_client.get.return_value = mock_data
        
        result = runner.invoke(cli, ['lineage', 'contract', 'contract-1'])
        
        assert result.exit_code == 0
        assert 'No upstream contracts found' in result.output
    
    def test_get_contract_lineage_api_error(self, runner, mock_api_client):
        """Test handling API errors when getting contract lineage"""
        from click import ClickException
        mock_api_client.get.side_effect = ClickException("API error: Not found")
        
        result = runner.invoke(cli, ['lineage', 'contract', 'contract-1'])
        
        assert result.exit_code != 0
        assert 'Failed to get contract lineage' in result.output or 'API error' in result.output


class TestLineageModel:
    """Test lineage model command"""
    
    def test_get_model_lineage_success_table_format(self, runner, mock_api_client):
        """Test getting model-level lineage in table format"""
        mock_data = {
            'lineage': {
                'models': [
                    {'namespace': 'ns1', 'name': 'contract1', 'model_name': 'model1'},
                    {'namespace': 'ns2', 'name': 'contract2', 'model_name': 'model2'}
                ]
            }
        }
        mock_api_client.get.return_value = mock_data
        
        result = runner.invoke(cli, ['lineage', 'model', 'contract-1', 'model1'])
        
        assert result.exit_code == 0
        assert 'Model Lineage: model1' in result.output
        assert 'Upstream Models (2)' in result.output
        assert 'ns1/contract1/model1' in result.output
        mock_api_client.get.assert_called_once_with('contracts/contract-1/models/model1/lineage/')
    
    def test_get_model_lineage_success_json_format(self, runner, mock_api_client):
        """Test getting model-level lineage in JSON format"""
        mock_data = {
            'lineage': {
                'models': [
                    {'namespace': 'ns1', 'name': 'contract1', 'model_name': 'model1'}
                ]
            }
        }
        mock_api_client.get.return_value = mock_data
        
        result = runner.invoke(cli, ['lineage', 'model', 'contract-1', 'model1', '--format', 'json'])
        
        assert result.exit_code == 0
        output_data = json.loads(result.output)
        assert 'lineage' in output_data
    
    def test_get_model_lineage_empty(self, runner, mock_api_client):
        """Test getting model-level lineage when no upstream models exist"""
        mock_data = {'lineage': {'models': []}}
        mock_api_client.get.return_value = mock_data
        
        result = runner.invoke(cli, ['lineage', 'model', 'contract-1', 'model1'])
        
        assert result.exit_code == 0
        assert 'No upstream models found' in result.output
    
    def test_get_model_lineage_api_error(self, runner, mock_api_client):
        """Test handling API errors when getting model lineage"""
        from click import ClickException
        mock_api_client.get.side_effect = ClickException("API error: Not found")
        
        result = runner.invoke(cli, ['lineage', 'model', 'contract-1', 'model1'])
        
        assert result.exit_code != 0
        assert 'Failed to get model lineage' in result.output or 'API error' in result.output


class TestLineageField:
    """Test lineage field command"""
    
    def test_get_field_lineage_success_table_format(self, runner, mock_api_client):
        """Test getting field-level lineage in table format"""
        mock_data = {
            'lineage': {
                'input_fields': [
                    {'namespace': 'ns1', 'name': 'contract1', 'model_name': 'model1', 'field': 'field1'},
                    {'namespace': 'ns2', 'name': 'contract2', 'model_name': 'model2', 'field': 'field2'}
                ]
            }
        }
        mock_api_client.get.return_value = mock_data
        
        result = runner.invoke(cli, ['lineage', 'field', 'contract-1', 'model1', 'field1'])
        
        assert result.exit_code == 0
        assert 'Field Lineage: model1.field1' in result.output
        assert 'Input Fields (2)' in result.output
        assert 'ns1/contract1/model1.field1' in result.output
        mock_api_client.get.assert_called_once_with('contracts/contract-1/fields/model1/field1/lineage/')
    
    def test_get_field_lineage_success_json_format(self, runner, mock_api_client):
        """Test getting field-level lineage in JSON format"""
        mock_data = {
            'lineage': {
                'input_fields': [
                    {'namespace': 'ns1', 'name': 'contract1', 'model_name': 'model1', 'field': 'field1'}
                ]
            }
        }
        mock_api_client.get.return_value = mock_data
        
        result = runner.invoke(cli, ['lineage', 'field', 'contract-1', 'model1', 'field1', '--format', 'json'])
        
        assert result.exit_code == 0
        output_data = json.loads(result.output)
        assert 'lineage' in output_data
    
    def test_get_field_lineage_empty(self, runner, mock_api_client):
        """Test getting field-level lineage when no input fields exist"""
        mock_data = {'lineage': {'input_fields': []}}
        mock_api_client.get.return_value = mock_data
        
        result = runner.invoke(cli, ['lineage', 'field', 'contract-1', 'model1', 'field1'])
        
        assert result.exit_code == 0
        assert 'No input fields found' in result.output
    
    def test_get_field_lineage_api_error(self, runner, mock_api_client):
        """Test handling API errors when getting field lineage"""
        from click import ClickException
        mock_api_client.get.side_effect = ClickException("API error: Not found")
        
        result = runner.invoke(cli, ['lineage', 'field', 'contract-1', 'model1', 'field1'])
        
        assert result.exit_code != 0
        assert 'Failed to get field lineage' in result.output or 'API error' in result.output


class TestLineageFull:
    """Test lineage full command"""
    
    def test_get_full_lineage_success_table_format(self, runner, mock_api_client):
        """Test getting full lineage in table format"""
        mock_data = {
            'upstream': {'contracts': []},
            'downstream': {'contracts': []}
        }
        mock_api_client.get.return_value = mock_data
        
        result = runner.invoke(cli, ['lineage', 'full', 'contract-1'])
        
        assert result.exit_code == 0
        assert 'Full Lineage' in result.output
        mock_api_client.get.assert_called_once_with(
            'contracts/contract-1/lineage/full/',
            params={'max_contract_depth': 10, 'max_model_depth': 10, 'max_field_depth': 10}
        )
    
    def test_get_full_lineage_with_custom_depths(self, runner, mock_api_client):
        """Test getting full lineage with custom depth parameters"""
        mock_data = {'upstream': {}, 'downstream': {}}
        mock_api_client.get.return_value = mock_data
        
        result = runner.invoke(cli, [
            'lineage', 'full', 'contract-1',
            '--max-contract-depth', '5',
            '--max-model-depth', '3',
            '--max-field-depth', '2'
        ])
        
        assert result.exit_code == 0
        mock_api_client.get.assert_called_once_with(
            'contracts/contract-1/lineage/full/',
            params={'max_contract_depth': 5, 'max_model_depth': 3, 'max_field_depth': 2}
        )
    
    def test_get_full_lineage_success_json_format(self, runner, mock_api_client):
        """Test getting full lineage in JSON format"""
        mock_data = {
            'upstream': {'contracts': []},
            'downstream': {'contracts': []}
        }
        mock_api_client.get.return_value = mock_data
        
        result = runner.invoke(cli, ['lineage', 'full', 'contract-1', '--format', 'json'])
        
        assert result.exit_code == 0
        output_data = json.loads(result.output)
        assert 'upstream' in output_data
        assert 'downstream' in output_data
    
    def test_get_full_lineage_api_error(self, runner, mock_api_client):
        """Test handling API errors when getting full lineage"""
        from click import ClickException
        mock_api_client.get.side_effect = ClickException("API error: Not found")
        
        result = runner.invoke(cli, ['lineage', 'full', 'contract-1'])
        
        assert result.exit_code != 0
        assert 'Failed to get full lineage' in result.output or 'API error' in result.output


class TestLineageVisualize:
    """Test lineage visualize command"""
    
    def test_visualize_lineage_json_format(self, runner, mock_api_client):
        """Test visualizing lineage in JSON format"""
        # The visualize command uses api_client.request which returns a response object
        # We need to mock the response properly
        mock_response = Mock()
        mock_response.json.return_value = {'nodes': [], 'edges': []}
        mock_response.text = '{"nodes": [], "edges": []}'
        mock_api_client.request = Mock(return_value=mock_response)
        
        result = runner.invoke(cli, ['lineage', 'visualize', 'contract-1', '--format', 'json'])
        
        assert result.exit_code == 0
        mock_api_client.request.assert_called_once_with(
            'GET',
            'contracts/contract-1/lineage/visualization/',
            params={'format': 'json'}
        )
    
    def test_visualize_lineage_dot_format(self, runner, mock_api_client):
        """Test visualizing lineage in DOT format"""
        mock_response = Mock()
        mock_response.text = 'digraph { }'
        mock_api_client.request = Mock(return_value=mock_response)
        
        result = runner.invoke(cli, ['lineage', 'visualize', 'contract-1', '--format', 'dot'])
        
        assert result.exit_code == 0
        assert 'digraph' in result.output
        mock_api_client.request.assert_called_once_with(
            'GET',
            'contracts/contract-1/lineage/visualization/',
            params={'format': 'dot'}
        )
    
    def test_visualize_lineage_mermaid_format(self, runner, mock_api_client):
        """Test visualizing lineage in Mermaid format"""
        mock_response = Mock()
        mock_response.text = 'graph TD'
        mock_api_client.request = Mock(return_value=mock_response)
        
        result = runner.invoke(cli, ['lineage', 'visualize', 'contract-1', '--format', 'mermaid'])
        
        assert result.exit_code == 0
        assert 'graph TD' in result.output
    
    def test_visualize_lineage_api_error(self, runner, mock_api_client):
        """Test handling API errors when visualizing lineage"""
        from click import ClickException
        mock_api_client.request = Mock(side_effect=ClickException("API error: Not found"))
        
        result = runner.invoke(cli, ['lineage', 'visualize', 'contract-1'])
        
        assert result.exit_code != 0
        assert 'Failed to get lineage visualization' in result.output or 'API error' in result.output


class TestLineageImpact:
    """Test lineage impact command"""
    
    def test_get_impact_analysis_success_table_format(self, runner, mock_api_client):
        """Test getting impact analysis in table format"""
        mock_data = {
            'impact_score': 85,
            'affected_assets': [
                {'id': 'asset-1'},
                {'id': 'asset-2'},
                {'id': 'asset-3'}
            ]
        }
        mock_api_client.get.return_value = mock_data
        
        result = runner.invoke(cli, ['lineage', 'impact', 'contract-1'])
        
        assert result.exit_code == 0
        assert 'Impact Analysis' in result.output
        assert 'Impact Score: 85' in result.output
        assert 'Affected Assets: 3' in result.output
        mock_api_client.get.assert_called_once_with(
            'contracts/contract-1/impact-analysis/',
            params={'depth': 10, 'include_fields': True}
        )
    
    def test_get_impact_analysis_with_custom_params(self, runner, mock_api_client):
        """Test getting impact analysis with custom parameters"""
        mock_data = {'impact_score': 0, 'affected_assets': []}
        mock_api_client.get.return_value = mock_data
        
        # Note: --no-include-fields is a flag that sets include_fields to False
        # But the default is True, so we need to check how the flag is handled
        result = runner.invoke(cli, [
            'lineage', 'impact', 'contract-1',
            '--depth', '5'
        ])
        
        assert result.exit_code == 0
        # Verify the call was made with custom depth
        assert mock_api_client.get.called
        call_args = mock_api_client.get.call_args
        assert call_args[0][0] == 'contracts/contract-1/impact-analysis/'
        assert call_args[1]['params']['depth'] == 5
        # include_fields defaults to True
        assert call_args[1]['params']['include_fields'] == True
    
    def test_get_impact_analysis_many_assets(self, runner, mock_api_client):
        """Test getting impact analysis with many affected assets (truncation)"""
        mock_data = {
            'impact_score': 90,
            'affected_assets': [{'id': f'asset-{i}'} for i in range(15)]
        }
        mock_api_client.get.return_value = mock_data
        
        result = runner.invoke(cli, ['lineage', 'impact', 'contract-1'])
        
        assert result.exit_code == 0
        assert 'Affected Assets: 15' in result.output
        assert '... and 5 more' in result.output
    
    def test_get_impact_analysis_success_json_format(self, runner, mock_api_client):
        """Test getting impact analysis in JSON format"""
        mock_data = {
            'impact_score': 85,
            'affected_assets': [{'id': 'asset-1'}]
        }
        mock_api_client.get.return_value = mock_data
        
        result = runner.invoke(cli, ['lineage', 'impact', 'contract-1', '--format', 'json'])
        
        assert result.exit_code == 0
        output_data = json.loads(result.output)
        assert output_data['impact_score'] == 85
    
    def test_get_impact_analysis_api_error(self, runner, mock_api_client):
        """Test handling API errors when getting impact analysis"""
        from click import ClickException
        mock_api_client.get.side_effect = ClickException("API error: Not found")
        
        result = runner.invoke(cli, ['lineage', 'impact', 'contract-1'])
        
        assert result.exit_code != 0
        assert 'Failed to get impact analysis' in result.output or 'API error' in result.output


@pytest.fixture
def runner():
    """CLI runner fixture"""
    return CliRunner()


@pytest.fixture
def mock_api_client(monkeypatch):
    """Mock API client"""
    mock_client = Mock()
    monkeypatch.setattr('datahub_cli.commands.lineage.api_client', mock_client)
    return mock_client

