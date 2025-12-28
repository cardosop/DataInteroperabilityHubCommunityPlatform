"""
Unit tests for Transformation CLI commands.

Tests command group registration, help text, and basic command structure.
"""
import pytest
import json
import os
import tempfile
from click.testing import CliRunner
from unittest.mock import Mock, patch, MagicMock
from datahub_cli.commands import transformation
from datahub_cli.main import cli
from datahub_cli.api_client import api_client


class TestTransformationCommandGroup:
    """Test transformation command group registration and structure"""

    @pytest.fixture
    def runner(self):
        """Create CLI runner"""
        return CliRunner()

    def test_transformation_command_group_registered(self, runner):
        """Test that transformation command group is registered in main CLI"""
        result = runner.invoke(cli, ['transformation', '--help'])
        assert result.exit_code == 0
        assert 'Transformation management commands' in result.output

    def test_transformation_command_group_help(self, runner):
        """Test transformation command group help text"""
        result = runner.invoke(transformation.transformation, ['--help'])
        assert result.exit_code == 0
        assert 'Transformation management commands' in result.output

    def test_transformation_command_group_importable(self):
        """Test that transformation command group can be imported"""
        from datahub_cli.commands.transformation import transformation as transformation_group
        assert transformation_group is not None
        assert callable(transformation_group)

    def test_transformation_command_group_in_main_cli(self):
        """Test that transformation command group is available in main CLI"""
        from datahub_cli.main import cli as main_cli

        # Check that transformation command is registered
        commands = [cmd.name for cmd in main_cli.commands.values()]
        assert 'transformation' in commands

    def test_transformation_command_group_in_commands_init(self):
        """Test that transformation is exported from commands __init__"""
        from datahub_cli.commands import transformation as transformation_module
        assert transformation_module is not None
        assert hasattr(transformation_module, 'transformation')

    def test_transformation_invalid_subcommand(self, runner):
        """Test handling invalid transformation subcommand"""
        result = runner.invoke(transformation.transformation, ['invalid-subcommand'])
        assert result.exit_code != 0
        assert 'No such command' in result.output or 'Usage:' in result.output

    def test_transformation_command_group_structure(self):
        """Test that transformation command group has correct structure"""
        from datahub_cli.commands.transformation import transformation as transformation_group

        # Should be a Click group
        assert hasattr(transformation_group, 'commands')
        # Initially empty, but structure is correct
        assert isinstance(transformation_group.commands, dict)

    def test_transformation_commands_in_main_cli_help(self, runner):
        """Test that transformation command appears in main CLI help"""
        result = runner.invoke(cli, ['--help'])
        assert result.exit_code == 0
        assert 'transformation' in result.output
        assert 'Transformation' in result.output

    def test_transformation_module_exported_correctly(self):
        """Test that transformation module is correctly exported from commands package"""
        from datahub_cli.commands import transformation
        from datahub_cli.commands.__init__ import __all__

        assert transformation is not None
        assert hasattr(transformation, 'transformation')
        assert 'transformation' in __all__

    def test_transformation_registered_in_main_py(self):
        """Test that transformation command is registered in main.py"""
        from datahub_cli.main import cli as main_cli

        # Verify transformation command is in the main CLI
        assert 'transformation' in main_cli.commands
        transformation_cmd = main_cli.commands['transformation']
        assert transformation_cmd is not None
        assert callable(transformation_cmd)


@pytest.fixture
def runner():
    """Create CLI runner"""
    return CliRunner()


@pytest.fixture
def mock_api_client():
    """Mock API client for testing"""
    with patch('datahub_cli.commands.transformation.api_client') as mock_client:
        yield mock_client


class TestTransformationPipelinesList:
    """Test transformation pipelines list command"""

    def test_list_pipelines_success_table_format(self, runner, mock_api_client):
        """Test listing pipelines in table format"""
        mock_data = {
            'count': 2,
            'next': None,
            'previous': None,
            'results': [
                {
                    'id': 'pipeline-1',
                    'name': 'Test Pipeline 1',
                    'status': 'ACTIVE',
                    'version': '1.0.0',
                    'created_at': '2025-01-01T00:00:00Z'
                },
                {
                    'id': 'pipeline-2',
                    'name': 'Test Pipeline 2',
                    'status': 'DRAFT',
                    'version': '1.1.0',
                    'created_at': '2025-01-01T01:00:00Z'
                }
            ]
        }
        mock_api_client.get.return_value = mock_data

        result = runner.invoke(cli, ['transformation', 'pipelines', 'list'])

        assert result.exit_code == 0
        assert 'pipeline-1' in result.output
        assert 'pipeline-2' in result.output
        assert 'Test Pipeline 1' in result.output
        assert 'ACTIVE' in result.output
        assert 'DRAFT' in result.output
        mock_api_client.get.assert_called_once()
        call_args = mock_api_client.get.call_args
        assert call_args[0][0] == 'transformation/pipelines/'
        assert call_args[1]['params']['page'] == 1
        assert call_args[1]['params']['page_size'] == 20

    def test_list_pipelines_success_json_format(self, runner, mock_api_client):
        """Test listing pipelines in JSON format"""
        mock_data = {
            'count': 1,
            'next': None,
            'previous': None,
            'results': [
                {
                    'id': 'pipeline-1',
                    'name': 'Test Pipeline',
                    'status': 'ACTIVE',
                    'version': '1.0.0'
                }
            ]
        }
        mock_api_client.get.return_value = mock_data

        result = runner.invoke(cli, ['transformation', 'pipelines', 'list', '--format', 'json'])

        assert result.exit_code == 0
        output_data = json.loads(result.output)
        assert 'count' in output_data
        assert 'results' in output_data
        assert len(output_data['results']) == 1
        assert output_data['results'][0]['id'] == 'pipeline-1'

    def test_list_pipelines_with_filters(self, runner, mock_api_client):
        """Test listing pipelines with filters"""
        mock_data = {'count': 0, 'results': []}
        mock_api_client.get.return_value = mock_data

        result = runner.invoke(cli, [
            'transformation', 'pipelines', 'list',
            '--status', 'ACTIVE',
            '--version', '1.0.0',
            '--search', 'test',
            '--ordering', '-created_at',
            '--page', '2',
            '--page-size', '50'
        ])

        assert result.exit_code == 0
        call_args = mock_api_client.get.call_args
        params = call_args[1]['params']
        assert params['status'] == 'ACTIVE'
        assert params['version'] == '1.0.0'
        assert params['search'] == 'test'
        assert params['ordering'] == '-created_at'
        assert params['page'] == 2
        assert params['page_size'] == 50

    def test_list_pipelines_empty_result(self, runner, mock_api_client):
        """Test listing pipelines with no results"""
        mock_data = {'count': 0, 'results': []}
        mock_api_client.get.return_value = mock_data

        result = runner.invoke(cli, ['transformation', 'pipelines', 'list'])

        assert result.exit_code == 0
        assert 'No pipelines found' in result.output

    def test_list_pipelines_pagination_info(self, runner, mock_api_client):
        """Test pagination info display"""
        mock_data = {
            'count': 50,
            'next': 2,
            'previous': None,
            'results': [{
                'id': f'pipeline-{i}',
                'name': f'Pipeline {i}',
                'status': 'ACTIVE',
                'version': '1.0.0',
                'created_at': '2025-01-01T00:00:00Z'
            } for i in range(20)]
        }
        mock_api_client.get.return_value = mock_data

        result = runner.invoke(cli, ['transformation', 'pipelines', 'list'])

        assert result.exit_code == 0
        assert 'Showing 20 of 50 pipelines' in result.output
        assert 'Next page: --page 2' in result.output

    def test_list_pipelines_api_error(self, runner, mock_api_client):
        """Test handling API errors"""
        mock_api_client.get.side_effect = Exception("API connection error")

        result = runner.invoke(cli, ['transformation', 'pipelines', 'list'])

        assert result.exit_code != 0
        assert 'Failed to list pipelines' in result.output


class TestTransformationPipelinesCreate:
    """Test transformation pipelines create command"""

    def test_create_pipeline_success_table_format(self, runner, mock_api_client):
        """Test creating a pipeline successfully in table format"""
        mock_response = {
            'id': 'pipeline-1',
            'name': 'New Pipeline',
            'status': 'DRAFT',
            'version': '1.0.0',
            'description': 'Test description',
            'created_at': '2025-01-01T00:00:00Z'
        }
        mock_api_client.post.return_value = mock_response

        # Create a temporary file with pipeline definition
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            pipeline_data = {
                'name': 'New Pipeline',
                'description': 'Test description',
                'pipeline_definition': {
                    'version': '1.0',
                    'steps': [
                        {'name': 'step1', 'type': 'filter'}
                    ]
                },
                'version': '1.0.0',
                'status': 'DRAFT'
            }
            json.dump(pipeline_data, f)
            temp_file = f.name

        try:
            result = runner.invoke(cli, [
                'transformation', 'pipelines', 'create',
                '--file', temp_file
            ])

            assert result.exit_code == 0
            assert 'Pipeline created successfully' in result.output
            assert 'pipeline-1' in result.output
            assert 'New Pipeline' in result.output
            assert 'DRAFT' in result.output
            mock_api_client.post.assert_called_once()
            call_args = mock_api_client.post.call_args
            assert call_args[0][0] == 'transformation/pipelines/'
            json_data = call_args[1]['json_data']
            assert json_data['name'] == 'New Pipeline'
            assert json_data['pipeline_definition'] == pipeline_data['pipeline_definition']
        finally:
            os.unlink(temp_file)

    def test_create_pipeline_success_json_format(self, runner, mock_api_client):
        """Test creating a pipeline successfully in JSON format"""
        mock_response = {
            'id': 'pipeline-1',
            'name': 'New Pipeline',
            'status': 'DRAFT',
            'version': '1.0.0'
        }
        mock_api_client.post.return_value = mock_response

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            pipeline_data = {
                'name': 'New Pipeline',
                'pipeline_definition': {
                    'version': '1.0',
                    'steps': [
                        {'name': 'step1', 'type': 'filter'}
                    ]
                }
            }
            json.dump(pipeline_data, f)
            temp_file = f.name

        try:
            result = runner.invoke(cli, [
                'transformation', 'pipelines', 'create',
                '--file', temp_file,
                '--format', 'json'
            ])

            assert result.exit_code == 0
            output_data = json.loads(result.output)
            assert output_data['id'] == 'pipeline-1'
            assert output_data['name'] == 'New Pipeline'
        finally:
            os.unlink(temp_file)

    def test_create_pipeline_missing_file(self, runner):
        """Test creating a pipeline without required file"""
        result = runner.invoke(cli, ['transformation', 'pipelines', 'create'])

        assert result.exit_code != 0
        assert 'Missing option' in result.output or 'required' in result.output.lower()

    def test_create_pipeline_invalid_json_file(self, runner):
        """Test creating a pipeline with invalid JSON file"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write('invalid json')
            temp_file = f.name

        try:
            result = runner.invoke(cli, [
                'transformation', 'pipelines', 'create',
                '--file', temp_file
            ])

            assert result.exit_code != 0
            assert 'Invalid JSON' in result.output or 'Failed to read' in result.output
        finally:
            os.unlink(temp_file)

    def test_create_pipeline_file_not_found(self, runner):
        """Test creating a pipeline with non-existent file"""
        result = runner.invoke(cli, [
            'transformation', 'pipelines', 'create',
            '--file', '/nonexistent/file.json'
        ])

        assert result.exit_code != 0
        assert 'does not exist' in result.output or 'not found' in result.output.lower() or 'Failed to read' in result.output

    def test_create_pipeline_api_error(self, runner, mock_api_client):
        """Test handling API errors"""
        mock_api_client.post.side_effect = Exception("API connection error")

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            pipeline_data = {
                'name': 'New Pipeline',
                'pipeline_definition': {
                    'version': '1.0',
                    'steps': [
                        {'name': 'step1', 'type': 'filter'}
                    ]
                }
            }
            json.dump(pipeline_data, f)
            temp_file = f.name

        try:
            result = runner.invoke(cli, [
                'transformation', 'pipelines', 'create',
                '--file', temp_file
            ])

            assert result.exit_code != 0
            assert 'Failed to create pipeline' in result.output or 'API' in result.output
        finally:
            os.unlink(temp_file)


class TestTransformationPipelinesGet:
    """Test transformation pipelines get command"""

    def test_get_pipeline_success_table_format(self, runner, mock_api_client):
        """Test getting a pipeline in table format"""
        mock_data = {
            'id': 'pipeline-1',
            'name': 'Test Pipeline',
            'status': 'ACTIVE',
            'version': '1.0.0',
            'description': 'Test description',
            'pipeline_definition': {
                'version': '1.0',
                'steps': []
            },
            'created_at': '2025-01-01T00:00:00Z',
            'updated_at': '2025-01-01T01:00:00Z'
        }
        mock_api_client.get.return_value = mock_data

        result = runner.invoke(cli, ['transformation', 'pipelines', 'get', 'pipeline-1'])

        assert result.exit_code == 0
        assert 'pipeline-1' in result.output
        assert 'Test Pipeline' in result.output
        assert 'ACTIVE' in result.output
        assert 'Test description' in result.output
        mock_api_client.get.assert_called_once_with('transformation/pipelines/pipeline-1/')

    def test_get_pipeline_success_json_format(self, runner, mock_api_client):
        """Test getting a pipeline in JSON format"""
        mock_data = {
            'id': 'pipeline-1',
            'name': 'Test Pipeline',
            'status': 'ACTIVE',
            'version': '1.0.0'
        }
        mock_api_client.get.return_value = mock_data

        result = runner.invoke(cli, ['transformation', 'pipelines', 'get', 'pipeline-1', '--format', 'json'])

        assert result.exit_code == 0
        output_data = json.loads(result.output)
        assert output_data['id'] == 'pipeline-1'
        assert output_data['name'] == 'Test Pipeline'

    def test_get_pipeline_not_found(self, runner, mock_api_client):
        """Test getting a non-existent pipeline"""
        mock_api_client.get.side_effect = Exception("Pipeline not found")

        result = runner.invoke(cli, ['transformation', 'pipelines', 'get', 'non-existent'])

        assert result.exit_code != 0
        assert 'Failed to get pipeline' in result.output


class TestTransformationPipelinesUpdate:
    """Test transformation pipelines update command"""

    def test_update_pipeline_success_table_format(self, runner, mock_api_client):
        """Test updating a pipeline successfully in table format"""
        mock_response = {
            'id': 'pipeline-1',
            'name': 'Updated Pipeline',
            'status': 'ACTIVE',
            'version': '1.1.0',
            'description': 'Updated description',
            'updated_at': '2025-01-01T02:00:00Z'
        }
        mock_api_client.patch.return_value = mock_response

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            pipeline_data = {
                'pipeline_definition': {
                    'version': '1.1',
                    'steps': [
                        {'name': 'step1', 'type': 'filter'},
                        {'name': 'step2', 'type': 'transform'}
                    ]
                }
            }
            json.dump(pipeline_data, f)
            temp_file = f.name

        try:
            result = runner.invoke(cli, [
                'transformation', 'pipelines', 'update', 'pipeline-1',
                '--file', temp_file
            ])

            assert result.exit_code == 0
            assert 'Pipeline updated successfully' in result.output
            assert 'pipeline-1' in result.output
            assert 'Updated Pipeline' in result.output
            assert 'ACTIVE' in result.output
            mock_api_client.patch.assert_called_once()
            call_args = mock_api_client.patch.call_args
            assert call_args[0][0] == 'transformation/pipelines/pipeline-1/'
            json_data = call_args[1]['json_data']
            assert 'pipeline_definition' in json_data
            assert json_data['pipeline_definition'] == pipeline_data['pipeline_definition']
        finally:
            os.unlink(temp_file)

    def test_update_pipeline_success_json_format(self, runner, mock_api_client):
        """Test updating a pipeline successfully in JSON format"""
        mock_response = {
            'id': 'pipeline-1',
            'name': 'Updated Pipeline',
            'status': 'ACTIVE',
            'version': '1.1.0'
        }
        mock_api_client.patch.return_value = mock_response

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            pipeline_data = {
                'pipeline_definition': {
                    'version': '1.1',
                    'steps': [
                        {'name': 'step1', 'type': 'filter'}
                    ]
                }
            }
            json.dump(pipeline_data, f)
            temp_file = f.name

        try:
            result = runner.invoke(cli, [
                'transformation', 'pipelines', 'update', 'pipeline-1',
                '--file', temp_file,
                '--format', 'json'
            ])

            assert result.exit_code == 0
            output_data = json.loads(result.output)
            assert output_data['id'] == 'pipeline-1'
            assert output_data['name'] == 'Updated Pipeline'
        finally:
            os.unlink(temp_file)

    def test_update_pipeline_missing_file(self, runner):
        """Test updating a pipeline without file"""
        result = runner.invoke(cli, ['transformation', 'pipelines', 'update', 'pipeline-1'])

        assert result.exit_code != 0
        assert 'Missing option' in result.output or 'required' in result.output.lower()

    def test_update_pipeline_invalid_json_file(self, runner):
        """Test updating a pipeline with invalid JSON file"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write('invalid json')
            temp_file = f.name

        try:
            result = runner.invoke(cli, [
                'transformation', 'pipelines', 'update', 'pipeline-1',
                '--file', temp_file
            ])

            assert result.exit_code != 0
            assert 'Invalid JSON' in result.output or 'Failed to read' in result.output
        finally:
            os.unlink(temp_file)

    def test_update_pipeline_api_error(self, runner, mock_api_client):
        """Test handling API errors"""
        mock_api_client.patch.side_effect = Exception("API connection error")

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            pipeline_data = {
                'pipeline_definition': {
                    'version': '1.1',
                    'steps': [
                        {'name': 'step1', 'type': 'filter'}
                    ]
                }
            }
            json.dump(pipeline_data, f)
            temp_file = f.name

        try:
            result = runner.invoke(cli, [
                'transformation', 'pipelines', 'update', 'pipeline-1',
                '--file', temp_file
            ])

            assert result.exit_code != 0
            assert 'Failed to update pipeline' in result.output or 'API' in result.output
        finally:
            os.unlink(temp_file)


class TestTransformationPipelinesDelete:
    """Test transformation pipelines delete command"""

    def test_delete_pipeline_success_table_format(self, runner, mock_api_client):
        """Test deleting a pipeline successfully in table format"""
        mock_api_client.delete.return_value = {}

        result = runner.invoke(cli, ['transformation', 'pipelines', 'delete', 'pipeline-1'], input='y\n')

        assert result.exit_code == 0
        assert 'deleted successfully' in result.output
        assert 'pipeline-1' in result.output
        mock_api_client.delete.assert_called_once_with('transformation/pipelines/pipeline-1/')

    def test_delete_pipeline_success_json_format(self, runner, mock_api_client):
        """Test deleting a pipeline successfully in JSON format"""
        mock_api_client.delete.return_value = {}

        result = runner.invoke(cli, [
            'transformation', 'pipelines', 'delete', 'pipeline-1',
            '--format', 'json'
        ], input='y\n')

        assert result.exit_code == 0
        # Output includes confirmation prompt, extract JSON part if present
        output_lines = result.output.strip().split('\n')
        json_found = False
        for line in output_lines:
            line = line.strip()
            if line.startswith('{') and line.endswith('}'):
                try:
                    json.loads(line)
                    json_found = True
                    break
                except json.JSONDecodeError:
                    pass

        # If no JSON found, should contain success message
        if not json_found:
            assert 'deleted successfully' in result.output.lower() or 'pipeline-1' in result.output

    def test_delete_pipeline_cancelled(self, runner, mock_api_client):
        """Test cancelling pipeline deletion"""
        result = runner.invoke(cli, ['transformation', 'pipelines', 'delete', 'pipeline-1'], input='n\n')

        # Should exit without deleting
        assert not mock_api_client.delete.called

    def test_delete_pipeline_api_error(self, runner, mock_api_client):
        """Test handling API errors"""
        mock_api_client.delete.side_effect = Exception("API connection error")

        result = runner.invoke(cli, ['transformation', 'pipelines', 'delete', 'pipeline-1'], input='y\n')

        assert result.exit_code != 0
        assert 'Failed to delete pipeline' in result.output


class TestTransformationPipelinesCommandStructure:
    """Test transformation pipelines command group structure"""

    def test_pipelines_command_group_exists(self, runner):
        """Test that pipelines command group exists"""
        result = runner.invoke(cli, ['transformation', 'pipelines', '--help'])
        assert result.exit_code == 0
        assert 'Pipeline management commands' in result.output

    def test_pipelines_list_command_exists(self, runner):
        """Test that pipelines list command exists"""
        result = runner.invoke(cli, ['transformation', 'pipelines', 'list', '--help'])
        assert result.exit_code == 0

    def test_pipelines_create_command_exists(self, runner):
        """Test that pipelines create command exists"""
        result = runner.invoke(cli, ['transformation', 'pipelines', 'create', '--help'])
        assert result.exit_code == 0

    def test_pipelines_get_command_exists(self, runner):
        """Test that pipelines get command exists"""
        result = runner.invoke(cli, ['transformation', 'pipelines', 'get', '--help'])
        assert result.exit_code == 0

    def test_pipelines_update_command_exists(self, runner):
        """Test that pipelines update command exists"""
        result = runner.invoke(cli, ['transformation', 'pipelines', 'update', '--help'])
        assert result.exit_code == 0

    def test_pipelines_delete_command_exists(self, runner):
        """Test that pipelines delete command exists"""
        result = runner.invoke(cli, ['transformation', 'pipelines', 'delete', '--help'])
        assert result.exit_code == 0


class TestTransformationExecutionsCreate:
    """Test transformation executions create command"""

    def test_create_execution_success_table_format(self, runner, mock_api_client):
        """Test creating an execution successfully in table format"""
        mock_response = {
            'execution_id': 'exec-1',
            'status': 'PENDING',
            'pipeline_id': 'pipeline-1',
            'asset_id': 'asset-1'
        }
        mock_api_client.post.return_value = mock_response

        result = runner.invoke(cli, [
            'transformation', 'executions', 'create', 'pipeline-1',
            '--input-asset', 'asset-1'
        ])

        assert result.exit_code == 0
        assert 'exec-1' in result.output
        assert 'PENDING' in result.output
        assert 'pipeline-1' in result.output
        assert 'asset-1' in result.output
        mock_api_client.post.assert_called_once()
        call_args = mock_api_client.post.call_args
        assert call_args[0][0] == 'transformation/pipelines/pipeline-1/execute/'
        json_data = call_args[1]['json_data']
        assert json_data['asset_id'] == 'asset-1'
        assert json_data.get('execution_mode', 'ASYNC') == 'ASYNC'

    def test_create_execution_success_json_format(self, runner, mock_api_client):
        """Test creating an execution successfully in JSON format"""
        mock_response = {
            'execution_id': 'exec-1',
            'status': 'PENDING',
            'pipeline_id': 'pipeline-1',
            'asset_id': 'asset-1'
        }
        mock_api_client.post.return_value = mock_response

        result = runner.invoke(cli, [
            'transformation', 'executions', 'create', 'pipeline-1',
            '--input-asset', 'asset-1',
            '--format', 'json'
        ])

        assert result.exit_code == 0
        output_data = json.loads(result.output)
        assert output_data['execution_id'] == 'exec-1'
        assert output_data['status'] == 'PENDING'
        assert output_data['pipeline_id'] == 'pipeline-1'

    def test_create_execution_with_sync_mode(self, runner, mock_api_client):
        """Test creating an execution with SYNC execution mode"""
        mock_response = {
            'execution_id': 'exec-1',
            'status': 'RUNNING',
            'pipeline_id': 'pipeline-1',
            'asset_id': 'asset-1'
        }
        mock_api_client.post.return_value = mock_response

        result = runner.invoke(cli, [
            'transformation', 'executions', 'create', 'pipeline-1',
            '--input-asset', 'asset-1',
            '--execution-mode', 'SYNC'
        ])

        assert result.exit_code == 0
        call_args = mock_api_client.post.call_args
        json_data = call_args[1]['json_data']
        assert json_data['execution_mode'] == 'SYNC'

    def test_create_execution_missing_input_asset(self, runner):
        """Test creating an execution without required input-asset"""
        result = runner.invoke(cli, [
            'transformation', 'executions', 'create', 'pipeline-1'
        ])

        assert result.exit_code != 0
        assert 'Missing option' in result.output or 'required' in result.output.lower()

    def test_create_execution_api_error(self, runner, mock_api_client):
        """Test handling API errors when creating execution"""
        from click import ClickException
        mock_api_client.post.side_effect = ClickException("API error: Pipeline not found")

        result = runner.invoke(cli, [
            'transformation', 'executions', 'create', 'pipeline-1',
            '--input-asset', 'asset-1'
        ])

        assert result.exit_code != 0
        assert 'Failed to create execution' in result.output or 'API error' in result.output


class TestTransformationExecutionsList:
    """Test transformation executions list command"""

    def test_list_executions_success_table_format(self, runner, mock_api_client):
        """Test listing executions in table format"""
        mock_data = {
            'count': 2,
            'next': None,
            'previous': None,
            'results': [
                {
                    'id': 'exec-1',
                    'pipeline_id': 'pipeline-1',
                    'asset_id': 'asset-1',
                    'status': 'RUNNING',
                    'started_at': '2025-01-01T00:00:00Z',
                    'created_at': '2025-01-01T00:00:00Z'
                },
                {
                    'id': 'exec-2',
                    'pipeline_id': 'pipeline-1',
                    'asset_id': 'asset-2',
                    'status': 'COMPLETED',
                    'started_at': '2025-01-01T01:00:00Z',
                    'completed_at': '2025-01-01T02:00:00Z',
                    'created_at': '2025-01-01T01:00:00Z'
                }
            ]
        }
        mock_api_client.get.return_value = mock_data

        result = runner.invoke(cli, [
            'transformation', 'executions', 'list',
            '--pipeline-id', 'pipeline-1'
        ])

        assert result.exit_code == 0
        assert 'exec-1' in result.output
        assert 'exec-2' in result.output
        assert 'RUNNING' in result.output
        assert 'COMPLETED' in result.output
        mock_api_client.get.assert_called_once()
        call_args = mock_api_client.get.call_args
        assert call_args[0][0] == 'transformation/pipelines/pipeline-1/executions/'
        params = call_args[1].get('params', {})
        assert params.get('page') == 1
        assert params.get('page_size') == 20

    def test_list_executions_success_json_format(self, runner, mock_api_client):
        """Test listing executions in JSON format"""
        mock_data = {
            'count': 1,
            'next': None,
            'previous': None,
            'results': [
                {
                    'id': 'exec-1',
                    'pipeline_id': 'pipeline-1',
                    'status': 'RUNNING'
                }
            ]
        }
        mock_api_client.get.return_value = mock_data

        result = runner.invoke(cli, [
            'transformation', 'executions', 'list',
            '--pipeline-id', 'pipeline-1',
            '--format', 'json'
        ])

        assert result.exit_code == 0
        output_data = json.loads(result.output)
        assert 'count' in output_data
        assert 'results' in output_data
        assert len(output_data['results']) == 1
        assert output_data['results'][0]['id'] == 'exec-1'

    def test_list_executions_with_status_filter(self, runner, mock_api_client):
        """Test listing executions with status filter"""
        mock_data = {'count': 0, 'results': []}
        mock_api_client.get.return_value = mock_data

        result = runner.invoke(cli, [
            'transformation', 'executions', 'list',
            '--pipeline-id', 'pipeline-1',
            '--status', 'COMPLETED',
            '--page', '2',
            '--page-size', '50'
        ])

        assert result.exit_code == 0
        call_args = mock_api_client.get.call_args
        params = call_args[1].get('params', {})
        assert params['status'] == 'COMPLETED'
        assert params['page'] == 2
        assert params['page_size'] == 50

    def test_list_executions_empty_result(self, runner, mock_api_client):
        """Test listing executions with no results"""
        mock_data = {'count': 0, 'results': []}
        mock_api_client.get.return_value = mock_data

        result = runner.invoke(cli, [
            'transformation', 'executions', 'list',
            '--pipeline-id', 'pipeline-1'
        ])

        assert result.exit_code == 0
        assert 'No executions found' in result.output

    def test_list_executions_missing_pipeline_id(self, runner):
        """Test listing executions without required pipeline-id"""
        result = runner.invoke(cli, ['transformation', 'executions', 'list'])

        assert result.exit_code != 0
        assert 'Missing option' in result.output or 'required' in result.output.lower()

    def test_list_executions_api_error(self, runner, mock_api_client):
        """Test handling API errors when listing executions"""
        from click import ClickException
        mock_api_client.get.side_effect = ClickException("API error: Pipeline not found")

        result = runner.invoke(cli, [
            'transformation', 'executions', 'list',
            '--pipeline-id', 'pipeline-1'
        ])

        assert result.exit_code != 0
        assert 'Failed to list executions' in result.output or 'API error' in result.output


class TestTransformationExecutionsGet:
    """Test transformation executions get command"""

    def test_get_execution_success_table_format(self, runner, mock_api_client):
        """Test getting an execution in table format"""
        mock_data = {
            'id': 'exec-1',
            'pipeline_id': 'pipeline-1',
            'asset_id': 'asset-1',
            'status': 'COMPLETED',
            'started_at': '2025-01-01T00:00:00Z',
            'completed_at': '2025-01-01T02:00:00Z',
            'created_at': '2025-01-01T00:00:00Z',
            'metrics': {'rows_processed': 1000}
        }
        mock_api_client.get.return_value = mock_data

        result = runner.invoke(cli, ['transformation', 'executions', 'get', 'exec-1'])

        assert result.exit_code == 0
        assert 'exec-1' in result.output
        assert 'pipeline-1' in result.output
        assert 'asset-1' in result.output
        assert 'COMPLETED' in result.output
        mock_api_client.get.assert_called_once_with('transformation/executions/exec-1/')

    def test_get_execution_success_json_format(self, runner, mock_api_client):
        """Test getting an execution in JSON format"""
        mock_data = {
            'id': 'exec-1',
            'pipeline_id': 'pipeline-1',
            'status': 'RUNNING'
        }
        mock_api_client.get.return_value = mock_data

        result = runner.invoke(cli, [
            'transformation', 'executions', 'get', 'exec-1',
            '--format', 'json'
        ])

        assert result.exit_code == 0
        output_data = json.loads(result.output)
        assert output_data['id'] == 'exec-1'
        assert output_data['pipeline_id'] == 'pipeline-1'
        assert output_data['status'] == 'RUNNING'

    def test_get_execution_with_error(self, runner, mock_api_client):
        """Test getting an execution with error message"""
        mock_data = {
            'id': 'exec-1',
            'status': 'FAILED',
            'error_message': 'Execution failed due to timeout'
        }
        mock_api_client.get.return_value = mock_data

        result = runner.invoke(cli, ['transformation', 'executions', 'get', 'exec-1'])

        assert result.exit_code == 0
        assert 'exec-1' in result.output
        assert 'FAILED' in result.output
        assert 'Execution failed due to timeout' in result.output

    def test_get_execution_not_found(self, runner, mock_api_client):
        """Test getting a non-existent execution"""
        from click import ClickException
        mock_api_client.get.side_effect = ClickException("API error: Execution not found")

        result = runner.invoke(cli, ['transformation', 'executions', 'get', 'non-existent'])

        assert result.exit_code != 0
        assert 'Failed to get execution' in result.output or 'API error' in result.output

    def test_get_execution_api_error(self, runner, mock_api_client):
        """Test handling API errors when getting execution"""
        from click import ClickException
        mock_api_client.get.side_effect = ClickException("API error: Connection failed")

        result = runner.invoke(cli, ['transformation', 'executions', 'get', 'exec-1'])

        assert result.exit_code != 0
        assert 'Failed to get execution' in result.output or 'API error' in result.output


class TestTransformationExecutionsCancel:
    """Test transformation executions cancel command"""

    def test_cancel_execution_success_table_format(self, runner, mock_api_client):
        """Test cancelling an execution successfully in table format"""
        mock_response = {
            'execution_id': 'exec-1',
            'status': 'CANCELLED',
            'message': 'Execution cancelled successfully'
        }
        mock_api_client.post.return_value = mock_response

        result = runner.invoke(cli, ['transformation', 'executions', 'cancel', 'exec-1'])

        assert result.exit_code == 0
        assert 'exec-1' in result.output
        assert 'CANCELLED' in result.output
        assert 'cancelled successfully' in result.output.lower()
        mock_api_client.post.assert_called_once_with('transformation/executions/exec-1/cancel/')

    def test_cancel_execution_success_json_format(self, runner, mock_api_client):
        """Test cancelling an execution successfully in JSON format"""
        mock_response = {
            'execution_id': 'exec-1',
            'status': 'CANCELLED',
            'message': 'Execution cancelled successfully'
        }
        mock_api_client.post.return_value = mock_response

        result = runner.invoke(cli, [
            'transformation', 'executions', 'cancel', 'exec-1',
            '--format', 'json'
        ])

        assert result.exit_code == 0
        output_data = json.loads(result.output)
        assert output_data['execution_id'] == 'exec-1'
        assert output_data['status'] == 'CANCELLED'

    def test_cancel_execution_already_completed(self, runner, mock_api_client):
        """Test cancelling an execution that is already completed"""
        # API returns 400 when execution cannot be cancelled
        from click import ClickException
        mock_api_client.post.side_effect = ClickException(
            "API error (400): Execution cannot be cancelled (current status: COMPLETED)"
        )

        result = runner.invoke(cli, ['transformation', 'executions', 'cancel', 'exec-1'])

        assert result.exit_code != 0
        assert 'Failed to cancel execution' in result.output or 'cannot be cancelled' in result.output.lower()

    def test_cancel_execution_not_found(self, runner, mock_api_client):
        """Test cancelling a non-existent execution"""
        from click import ClickException
        mock_api_client.post.side_effect = ClickException("API error: Execution not found")

        result = runner.invoke(cli, ['transformation', 'executions', 'cancel', 'non-existent'])

        assert result.exit_code != 0
        assert 'Failed to cancel execution' in result.output or 'API error' in result.output

    def test_cancel_execution_api_error(self, runner, mock_api_client):
        """Test handling API errors when cancelling execution"""
        from click import ClickException
        mock_api_client.post.side_effect = ClickException("API error: Connection failed")

        result = runner.invoke(cli, ['transformation', 'executions', 'cancel', 'exec-1'])

        assert result.exit_code != 0
        assert 'Failed to cancel execution' in result.output or 'API error' in result.output


class TestTransformationExecutionsWatch:
    """Test transformation executions watch command"""

    @patch('datahub_cli.commands.transformation.time.sleep')
    def test_watch_execution_completion_success(self, mock_sleep, runner, mock_api_client):
        """Test watching an execution until completion"""
        mock_api_client.get.side_effect = [
            {
                'id': 'exec-1',
                'status': 'RUNNING',
                'progress_percentage': 50.0,
                'current_step': 2,
                'total_steps': 4
            },
            {
                'id': 'exec-1',
                'status': 'COMPLETED',
                'progress_percentage': 100.0,
                'current_step': 4,
                'total_steps': 4
            }
        ]

        result = runner.invoke(cli, [
            'transformation', 'executions', 'watch', 'exec-1',
            '--interval', '1',
            '--timeout', '10'
        ])

        assert result.exit_code == 0
        assert 'exec-1' in result.output
        assert 'COMPLETED' in result.output
        assert 'completed successfully' in result.output.lower()
        assert mock_api_client.get.call_count >= 2

    @patch('datahub_cli.commands.transformation.time.sleep')
    def test_watch_execution_failure(self, mock_sleep, runner, mock_api_client):
        """Test watching an execution that fails"""
        mock_api_client.get.side_effect = [
            {
                'id': 'exec-1',
                'status': 'RUNNING',
                'progress_percentage': 50.0
            },
            {
                'id': 'exec-1',
                'status': 'FAILED',
                'error_message': 'Execution failed due to timeout',
                'progress_percentage': 50.0
            }
        ]

        result = runner.invoke(cli, [
            'transformation', 'executions', 'watch', 'exec-1',
            '--interval', '1',
            '--timeout', '10'
        ])

        assert result.exit_code == 0
        assert 'FAILED' in result.output
        assert 'Execution failed due to timeout' in result.output

    @patch('datahub_cli.commands.transformation.time.sleep')
    def test_watch_execution_cancelled(self, mock_sleep, runner, mock_api_client):
        """Test watching an execution that gets cancelled"""
        mock_api_client.get.side_effect = [
            {
                'id': 'exec-1',
                'status': 'RUNNING',
                'progress_percentage': 30.0
            },
            {
                'id': 'exec-1',
                'status': 'CANCELLED',
                'progress_percentage': 30.0
            }
        ]

        result = runner.invoke(cli, [
            'transformation', 'executions', 'watch', 'exec-1',
            '--interval', '1',
            '--timeout', '10'
        ])

        assert result.exit_code == 0
        assert 'CANCELLED' in result.output
        assert 'cancelled' in result.output.lower()

    @patch('datahub_cli.commands.transformation.time.sleep')
    def test_watch_execution_timeout(self, mock_sleep, runner, mock_api_client):
        """Test watching an execution that times out"""
        # Mock time.sleep to advance time
        import time
        start_time = time.time()
        call_count = [0]

        def mock_time():
            call_count[0] += 1
            return start_time + (call_count[0] * 2)

        with patch('datahub_cli.commands.transformation.time.time', side_effect=mock_time):
            mock_api_client.get.return_value = {
                'id': 'exec-1',
                'status': 'RUNNING',
                'progress_percentage': 50.0
            }

            result = runner.invoke(cli, [
                'transformation', 'executions', 'watch', 'exec-1',
                '--interval', '1',
                '--timeout', '5'
            ])

            assert result.exit_code != 0
            assert 'Timeout' in result.output or 'timeout' in result.output.lower()

    @patch('datahub_cli.commands.transformation.time.sleep')
    def test_watch_execution_json_output(self, mock_sleep, runner, mock_api_client):
        """Test watching an execution with JSON output format"""
        mock_api_client.get.side_effect = [
            {
                'id': 'exec-1',
                'status': 'RUNNING',
                'progress_percentage': 50.0
            },
            {
                'id': 'exec-1',
                'status': 'COMPLETED',
                'progress_percentage': 100.0
            }
        ]

        result = runner.invoke(cli, [
            'transformation', 'executions', 'watch', 'exec-1',
            '--format', 'json',
            '--interval', '1',
            '--timeout', '10'
        ])

        assert result.exit_code == 0
        # Output should contain JSON with COMPLETED status
        # Try to parse the entire output as JSON (may be multi-line)
        try:
            output_data = json.loads(result.output.strip())
            assert output_data['status'] == 'COMPLETED'
            json_found = True
        except json.JSONDecodeError:
            # If entire output is not JSON, try to find JSON in output
            output_lines = result.output.strip().split('\n')
            json_found = False
            # Try to parse each line or combination of lines
            for i in range(len(output_lines)):
                for j in range(i + 1, len(output_lines) + 1):
                    try:
                        json_str = '\n'.join(output_lines[i:j])
                        output_data = json.loads(json_str)
                        if output_data.get('status') == 'COMPLETED':
                            json_found = True
                            break
                    except json.JSONDecodeError:
                        continue
                if json_found:
                    break
        assert json_found

    @patch('datahub_cli.commands.transformation.time.sleep')
    def test_watch_execution_progress_updates(self, mock_sleep, runner, mock_api_client):
        """Test watching an execution with progress updates"""
        mock_api_client.get.side_effect = [
            {
                'id': 'exec-1',
                'status': 'RUNNING',
                'progress_percentage': 25.0,
                'current_step': 1,
                'total_steps': 4
            },
            {
                'id': 'exec-1',
                'status': 'RUNNING',
                'progress_percentage': 50.0,
                'current_step': 2,
                'total_steps': 4
            },
            {
                'id': 'exec-1',
                'status': 'RUNNING',
                'progress_percentage': 75.0,
                'current_step': 3,
                'total_steps': 4
            },
            {
                'id': 'exec-1',
                'status': 'COMPLETED',
                'progress_percentage': 100.0,
                'current_step': 4,
                'total_steps': 4
            }
        ]

        result = runner.invoke(cli, [
            'transformation', 'executions', 'watch', 'exec-1',
            '--interval', '1',
            '--timeout', '10'
        ])

        assert result.exit_code == 0
        assert '25.0' in result.output or '25%' in result.output
        assert '50.0' in result.output or '50%' in result.output
        assert '75.0' in result.output or '75%' in result.output
        assert '100.0' in result.output or '100%' in result.output
        assert 'COMPLETED' in result.output

    @patch('datahub_cli.commands.transformation.time.sleep')
    def test_watch_execution_keyboard_interrupt(self, mock_sleep, runner, mock_api_client):
        """Test handling keyboard interrupt while watching an execution"""
        mock_api_client.get.side_effect = KeyboardInterrupt()

        result = runner.invoke(cli, [
            'transformation', 'executions', 'watch', 'exec-1',
            '--interval', '1',
            '--timeout', '10'
        ])

        # KeyboardInterrupt should be caught and handled gracefully
        assert 'cancelled' in result.output.lower() or result.exit_code in [0, 130]

    @patch('datahub_cli.commands.transformation.time.sleep')
    def test_watch_execution_api_error(self, mock_sleep, runner, mock_api_client):
        """Test handling API errors when watching an execution"""
        from click import ClickException
        mock_api_client.get.side_effect = ClickException("API error: Execution not found")

        result = runner.invoke(cli, [
            'transformation', 'executions', 'watch', 'exec-1',
            '--interval', '1',
            '--timeout', '10'
        ])

        assert result.exit_code != 0
        assert 'Failed to watch execution' in result.output or 'API error' in result.output


class TestTransformationExecutionsCommandStructure:
    """Test transformation executions command group structure"""

    def test_executions_command_group_exists(self, runner):
        """Test that executions command group exists"""
        result = runner.invoke(cli, ['transformation', 'executions', '--help'])
        assert result.exit_code == 0
        assert 'Execution management commands' in result.output

    def test_executions_create_command_exists(self, runner):
        """Test that executions create command exists"""
        result = runner.invoke(cli, ['transformation', 'executions', 'create', '--help'])
        assert result.exit_code == 0

    def test_executions_list_command_exists(self, runner):
        """Test that executions list command exists"""
        result = runner.invoke(cli, ['transformation', 'executions', 'list', '--help'])
        assert result.exit_code == 0

    def test_executions_get_command_exists(self, runner):
        """Test that executions get command exists"""
        result = runner.invoke(cli, ['transformation', 'executions', 'get', '--help'])
        assert result.exit_code == 0

    def test_executions_cancel_command_exists(self, runner):
        """Test that executions cancel command exists"""
        result = runner.invoke(cli, ['transformation', 'executions', 'cancel', '--help'])
        assert result.exit_code == 0

    def test_executions_watch_command_exists(self, runner):
        """Test that executions watch command exists"""
        result = runner.invoke(cli, ['transformation', 'executions', 'watch', '--help'])
        assert result.exit_code == 0


class TestTransformationPreviewGenerate:
    """Test transformation preview generate command"""

    def test_generate_preview_success_table_format(self, runner, mock_api_client):
        """Test generating a preview successfully in table format"""
        mock_response = {
            'preview_id': 'preview-123',
            'pipeline_id': 'pipeline-1',
            'asset_id': 'asset-1',
            'cached': False,
            'analysis': {
                'row_count_changes': {'input': 100, 'output': 95},
                'schema_changes': {'added': ['new_col'], 'removed': ['old_col']},
                'quality_impact': {'score': 0.95}
            }
        }
        mock_api_client.post.return_value = mock_response

        result = runner.invoke(cli, [
            'transformation', 'preview', 'generate', 'pipeline-1',
            '--input-asset', 'asset-1'
        ])

        assert result.exit_code == 0
        assert 'Preview generated successfully!' in result.output
        assert 'preview-123' in result.output
        assert 'pipeline-1' in result.output
        assert 'asset-1' in result.output
        mock_api_client.post.assert_called_once()
        call_args = mock_api_client.post.call_args
        assert call_args[0][0] == 'transformation/pipelines/pipeline-1/preview/'
        json_data = call_args[1]['json_data']
        assert json_data['asset_id'] == 'asset-1'
        assert json_data['sample_size'] == 100
        assert json_data['sampling_method'] == 'first_n'

    def test_generate_preview_success_json_format(self, runner, mock_api_client):
        """Test generating a preview successfully in JSON format"""
        mock_response = {
            'preview_id': 'preview-123',
            'pipeline_id': 'pipeline-1',
            'asset_id': 'asset-1',
            'cached': False,
            'analysis': {}
        }
        mock_api_client.post.return_value = mock_response

        result = runner.invoke(cli, [
            'transformation', 'preview', 'generate', 'pipeline-1',
            '--input-asset', 'asset-1',
            '--format', 'json'
        ])

        assert result.exit_code == 0
        output_data = json.loads(result.output)
        assert output_data['preview_id'] == 'preview-123'
        assert output_data['pipeline_id'] == 'pipeline-1'
        assert output_data['asset_id'] == 'asset-1'

    def test_generate_preview_with_custom_sample_size(self, runner, mock_api_client):
        """Test generating a preview with custom sample size"""
        mock_response = {
            'preview_id': 'preview-123',
            'pipeline_id': 'pipeline-1',
            'asset_id': 'asset-1',
            'cached': False
        }
        mock_api_client.post.return_value = mock_response

        result = runner.invoke(cli, [
            'transformation', 'preview', 'generate', 'pipeline-1',
            '--input-asset', 'asset-1',
            '--sample-size', '500'
        ])

        assert result.exit_code == 0
        call_args = mock_api_client.post.call_args
        json_data = call_args[1]['json_data']
        assert json_data['sample_size'] == 500

    def test_generate_preview_with_random_sampling(self, runner, mock_api_client):
        """Test generating a preview with random sampling method"""
        mock_response = {
            'preview_id': 'preview-123',
            'pipeline_id': 'pipeline-1',
            'asset_id': 'asset-1',
            'cached': False
        }
        mock_api_client.post.return_value = mock_response

        result = runner.invoke(cli, [
            'transformation', 'preview', 'generate', 'pipeline-1',
            '--input-asset', 'asset-1',
            '--sampling-method', 'random'
        ])

        assert result.exit_code == 0
        call_args = mock_api_client.post.call_args
        json_data = call_args[1]['json_data']
        assert json_data['sampling_method'] == 'random'

    def test_generate_preview_missing_input_asset(self, runner):
        """Test generating a preview without required input-asset"""
        result = runner.invoke(cli, [
            'transformation', 'preview', 'generate', 'pipeline-1'
        ])

        assert result.exit_code != 0
        assert 'Missing option' in result.output or 'required' in result.output.lower()

    def test_generate_preview_api_error(self, runner, mock_api_client):
        """Test handling API errors when generating preview"""
        from click import ClickException
        mock_api_client.post.side_effect = ClickException("API error: Pipeline not found")

        result = runner.invoke(cli, [
            'transformation', 'preview', 'generate', 'pipeline-1',
            '--input-asset', 'asset-1'
        ])

        assert result.exit_code != 0
        assert 'Failed to generate preview' in result.output or 'API error' in result.output

    def test_generate_preview_with_cached_result(self, runner, mock_api_client):
        """Test generating a preview that returns cached result"""
        mock_response = {
            'preview_id': 'preview-123',
            'pipeline_id': 'pipeline-1',
            'asset_id': 'asset-1',
            'cached': True,
            'analysis': {}
        }
        mock_api_client.post.return_value = mock_response

        result = runner.invoke(cli, [
            'transformation', 'preview', 'generate', 'pipeline-1',
            '--input-asset', 'asset-1'
        ])

        assert result.exit_code == 0
        assert 'Cached' in result.output or 'cached' in result.output.lower()


class TestTransformationPreviewGet:
    """Test transformation preview get command"""

    def test_get_preview_success_table_format(self, runner, mock_api_client):
        """Test getting a preview successfully in table format"""
        mock_data = {
            'preview_id': 'preview-123',
            'pipeline_id': 'pipeline-1',
            'asset_id': 'asset-1',
            'generated_at': '2025-01-01T00:00:00Z',
            'expires_at': '2025-01-01T01:00:00Z',
            'analysis': {
                'row_count_changes': {'input': 100, 'output': 95},
                'schema_changes': {'added': ['new_col']},
                'quality_impact': {'score': 0.95}
            },
            'input_sample': [{'col1': 'val1'}, {'col1': 'val2'}],
            'output_sample': [{'col1': 'val1'}, {'col1': 'val2'}]
        }
        mock_api_client.get.return_value = mock_data

        result = runner.invoke(cli, ['transformation', 'preview', 'get', 'preview-123'])

        assert result.exit_code == 0
        assert 'preview-123' in result.output
        assert 'pipeline-1' in result.output
        assert 'asset-1' in result.output
        assert 'Analysis:' in result.output
        assert 'Row count changes' in result.output or 'row_count_changes' in result.output
        assert '2 rows' in result.output  # input_sample and output_sample
        mock_api_client.get.assert_called_once_with('transformation/previews/preview-123/')

    def test_get_preview_success_json_format(self, runner, mock_api_client):
        """Test getting a preview successfully in JSON format"""
        mock_data = {
            'preview_id': 'preview-123',
            'pipeline_id': 'pipeline-1',
            'asset_id': 'asset-1',
            'analysis': {}
        }
        mock_api_client.get.return_value = mock_data

        result = runner.invoke(cli, [
            'transformation', 'preview', 'get', 'preview-123',
            '--format', 'json'
        ])

        assert result.exit_code == 0
        output_data = json.loads(result.output)
        assert output_data['preview_id'] == 'preview-123'
        assert output_data['pipeline_id'] == 'pipeline-1'
        assert output_data['asset_id'] == 'asset-1'

    def test_get_preview_with_analysis(self, runner, mock_api_client):
        """Test getting a preview with detailed analysis"""
        mock_data = {
            'preview_id': 'preview-123',
            'pipeline_id': 'pipeline-1',
            'asset_id': 'asset-1',
            'analysis': {
                'row_count_changes': {
                    'input_rows': 1000,
                    'output_rows': 950,
                    'change_percentage': -5.0
                },
                'schema_changes': {
                    'added_columns': ['new_col1', 'new_col2'],
                    'removed_columns': ['old_col'],
                    'modified_columns': ['modified_col']
                },
                'quality_impact': {
                    'score_before': 0.85,
                    'score_after': 0.92,
                    'improvement': 0.07
                }
            }
        }
        mock_api_client.get.return_value = mock_data

        result = runner.invoke(cli, ['transformation', 'preview', 'get', 'preview-123'])

        assert result.exit_code == 0
        assert 'Analysis:' in result.output
        assert 'row_count_changes' in result.output or 'Row count' in result.output
        assert 'schema_changes' in result.output or 'Schema' in result.output
        assert 'quality_impact' in result.output or 'Quality' in result.output

    def test_get_preview_not_found(self, runner, mock_api_client):
        """Test getting a non-existent preview"""
        from click import ClickException
        mock_api_client.get.side_effect = ClickException("API error: Preview not found")

        result = runner.invoke(cli, ['transformation', 'preview', 'get', 'non-existent'])

        assert result.exit_code != 0
        assert 'Failed to get preview' in result.output or 'API error' in result.output

    def test_get_preview_api_error(self, runner, mock_api_client):
        """Test handling API errors when getting preview"""
        from click import ClickException
        mock_api_client.get.side_effect = ClickException("API error: Connection failed")

        result = runner.invoke(cli, ['transformation', 'preview', 'get', 'preview-123'])

        assert result.exit_code != 0
        assert 'Failed to get preview' in result.output or 'API error' in result.output


class TestTransformationPreviewCommandStructure:
    """Test transformation preview command group structure"""

    def test_preview_command_group_exists(self, runner):
        """Test that preview command group exists"""
        result = runner.invoke(cli, ['transformation', 'preview', '--help'])
        assert result.exit_code == 0
        assert 'Preview management commands' in result.output

    def test_preview_generate_command_exists(self, runner):
        """Test that preview generate command exists"""
        result = runner.invoke(cli, ['transformation', 'preview', 'generate', '--help'])
        assert result.exit_code == 0
        assert 'Generate a preview' in result.output or 'preview' in result.output.lower()

    def test_preview_get_command_exists(self, runner):
        """Test that preview get command exists"""
        result = runner.invoke(cli, ['transformation', 'preview', 'get', '--help'])
        assert result.exit_code == 0
        assert 'Get preview result' in result.output or 'preview' in result.output.lower()



class TestTransformationWranglingStart:
    """Test transformation wrangling start command"""

    def test_start_wrangling_success_table_format(self, runner, mock_api_client):
        """Test starting a wrangling session successfully in table format"""
        mock_response = {
            'session_id': 'session-123',
            'operation_id': 'op-456',
            'applied_operations_count': 1,
            'can_undo': False,
            'can_redo': False,
            'wrangling_script': '# Data Wrangling Script\nimport pandas as pd'
        }
        mock_api_client.post.return_value = mock_response

        result = runner.invoke(cli, [
            'transformation', 'wrangling', 'start', 'asset-123'
        ])

        assert result.exit_code == 0
        assert 'Wrangling session started successfully!' in result.output
        assert 'session-123' in result.output
        assert 'op-456' in result.output
        assert '1' in result.output  # applied_operations_count
        mock_api_client.post.assert_called_once()
        call_args = mock_api_client.post.call_args
        assert call_args[0][0] == 'transformation/wrangling/'
        json_data = call_args[1]['json_data']
        assert json_data['asset_id'] == 'asset-123'
        assert json_data['operation']['type'] == 'FILTER'
        assert json_data['operation']['parameters']['condition'] == '1 == 1'

    def test_start_wrangling_success_json_format(self, runner, mock_api_client):
        """Test starting a wrangling session successfully in JSON format"""
        mock_response = {
            'session_id': 'session-123',
            'operation_id': 'op-456',
            'applied_operations_count': 1,
            'can_undo': False,
            'can_redo': False
        }
        mock_api_client.post.return_value = mock_response

        result = runner.invoke(cli, [
            'transformation', 'wrangling', 'start', 'asset-123',
            '--format', 'json'
        ])

        assert result.exit_code == 0
        output_data = json.loads(result.output)
        assert output_data['session_id'] == 'session-123'
        assert output_data['operation_id'] == 'op-456'

    def test_start_wrangling_api_error(self, runner, mock_api_client):
        """Test handling API errors when starting wrangling session"""
        from click import ClickException
        mock_api_client.post.side_effect = ClickException("API error: Asset not found")

        result = runner.invoke(cli, [
            'transformation', 'wrangling', 'start', 'asset-123'
        ])

        assert result.exit_code != 0
        assert 'Failed to start wrangling session' in result.output or 'API error' in result.output


class TestTransformationWranglingApply:
    """Test transformation wrangling apply command"""

    def test_apply_wrangling_success_table_format(self, runner, mock_api_client):
        """Test applying a wrangling operation successfully in table format"""
        # Mock session get response
        mock_session = {
            'id': 'session-123',
            'asset_id': 'asset-456'
        }
        # Mock apply response
        mock_response = {
            'session_id': 'session-123',
            'operation_id': 'op-789',
            'applied_operations_count': 2,
            'can_undo': True,
            'can_redo': False,
            'result': {
                'sample_data': [{'col1': 'val1'}, {'col1': 'val2'}],
                'row_count': 100
            },
            'wrangling_script': '# Updated script'
        }
        mock_api_client.get.return_value = mock_session
        mock_api_client.post.return_value = mock_response

        operation_json = '{"type": "FILTER", "parameters": {"condition": "age > 18"}}'
        result = runner.invoke(cli, [
            'transformation', 'wrangling', 'apply', 'session-123',
            '--operation', operation_json
        ])

        assert result.exit_code == 0
        assert 'Operation applied successfully!' in result.output
        assert 'session-123' in result.output
        assert 'op-789' in result.output
        assert '2' in result.output  # applied_operations_count
        assert '2 rows' in result.output  # sample_data
        assert '100' in result.output  # row_count
        assert mock_api_client.get.called  # Should get session first
        assert mock_api_client.post.called  # Should apply operation

    def test_apply_wrangling_success_json_format(self, runner, mock_api_client):
        """Test applying a wrangling operation successfully in JSON format"""
        mock_session = {'id': 'session-123', 'asset_id': 'asset-456'}
        mock_response = {
            'session_id': 'session-123',
            'operation_id': 'op-789',
            'applied_operations_count': 2
        }
        mock_api_client.get.return_value = mock_session
        mock_api_client.post.return_value = mock_response

        operation_json = '{"type": "FILTER", "parameters": {"condition": "age > 18"}}'
        result = runner.invoke(cli, [
            'transformation', 'wrangling', 'apply', 'session-123',
            '--operation', operation_json,
            '--format', 'json'
        ])

        assert result.exit_code == 0
        output_data = json.loads(result.output)
        assert output_data['session_id'] == 'session-123'
        assert output_data['operation_id'] == 'op-789'

    def test_apply_wrangling_invalid_json(self, runner, mock_api_client):
        """Test applying wrangling with invalid JSON"""
        result = runner.invoke(cli, [
            'transformation', 'wrangling', 'apply', 'session-123',
            '--operation', 'invalid json'
        ])

        assert result.exit_code != 0
        assert 'Invalid operation JSON' in result.output

    def test_apply_wrangling_missing_type(self, runner, mock_api_client):
        """Test applying wrangling with missing type field"""
        operation_json = '{"parameters": {"condition": "age > 18"}}'
        result = runner.invoke(cli, [
            'transformation', 'wrangling', 'apply', 'session-123',
            '--operation', operation_json
        ])

        assert result.exit_code != 0
        assert 'must have \'type\' field' in result.output

    def test_apply_wrangling_missing_parameters(self, runner, mock_api_client):
        """Test applying wrangling with missing parameters field"""
        operation_json = '{"type": "FILTER"}'
        result = runner.invoke(cli, [
            'transformation', 'wrangling', 'apply', 'session-123',
            '--operation', operation_json
        ])

        assert result.exit_code != 0
        assert 'must have \'parameters\' field' in result.output

    def test_apply_wrangling_session_not_found(self, runner, mock_api_client):
        """Test applying wrangling when session not found"""
        from click import ClickException
        mock_api_client.get.side_effect = ClickException("API error: Session not found")

        operation_json = '{"type": "FILTER", "parameters": {"condition": "age > 18"}}'
        result = runner.invoke(cli, [
            'transformation', 'wrangling', 'apply', 'session-123',
            '--operation', operation_json
        ])

        assert result.exit_code != 0
        assert 'Failed to apply wrangling operation' in result.output or 'API error' in result.output

    def test_apply_wrangling_api_error(self, runner, mock_api_client):
        """Test handling API errors when applying wrangling operation"""
        from click import ClickException
        mock_session = {'id': 'session-123', 'asset_id': 'asset-456'}
        mock_api_client.get.return_value = mock_session
        mock_api_client.post.side_effect = ClickException("API error: Operation failed")

        operation_json = '{"type": "FILTER", "parameters": {"condition": "age > 18"}}'
        result = runner.invoke(cli, [
            'transformation', 'wrangling', 'apply', 'session-123',
            '--operation', operation_json
        ])

        assert result.exit_code != 0
        assert 'Failed to apply wrangling operation' in result.output or 'API error' in result.output


class TestTransformationWranglingUndo:
    """Test transformation wrangling undo command"""

    def test_undo_wrangling_success_table_format(self, runner, mock_api_client):
        """Test undoing a wrangling operation successfully in table format"""
        mock_response = {
            'session_id': 'session-123',
            'undone_operation': {
                'type': 'FILTER',
                'parameters': {'condition': 'age > 18'}
            },
            'applied_operations_count': 1,
            'can_undo': False,
            'can_redo': True
        }
        mock_api_client.post.return_value = mock_response

        result = runner.invoke(cli, [
            'transformation', 'wrangling', 'undo', 'session-123'
        ])

        assert result.exit_code == 0
        assert 'Operation undone successfully!' in result.output
        assert 'session-123' in result.output
        assert 'FILTER' in result.output  # undone_operation type
        assert '1' in result.output  # applied_operations_count
        mock_api_client.post.assert_called_once_with('transformation/wrangling/session-123/undo/')

    def test_undo_wrangling_success_json_format(self, runner, mock_api_client):
        """Test undoing a wrangling operation successfully in JSON format"""
        mock_response = {
            'session_id': 'session-123',
            'undone_operation': {'type': 'FILTER'},
            'applied_operations_count': 1,
            'can_undo': False,
            'can_redo': True
        }
        mock_api_client.post.return_value = mock_response

        result = runner.invoke(cli, [
            'transformation', 'wrangling', 'undo', 'session-123',
            '--format', 'json'
        ])

        assert result.exit_code == 0
        output_data = json.loads(result.output)
        assert output_data['session_id'] == 'session-123'
        assert output_data['undone_operation']['type'] == 'FILTER'

    def test_undo_wrangling_cannot_undo(self, runner, mock_api_client):
        """Test undoing when no operations to undo"""
        from click import ClickException
        mock_api_client.post.side_effect = ClickException(
            "API error (400): Cannot undo: no operations to undo"
        )

        result = runner.invoke(cli, [
            'transformation', 'wrangling', 'undo', 'session-123'
        ])

        assert result.exit_code != 0
        assert 'Failed to undo wrangling operation' in result.output or 'API error' in result.output

    def test_undo_wrangling_api_error(self, runner, mock_api_client):
        """Test handling API errors when undoing wrangling operation"""
        from click import ClickException
        mock_api_client.post.side_effect = ClickException("API error: Session not found")

        result = runner.invoke(cli, [
            'transformation', 'wrangling', 'undo', 'session-123'
        ])

        assert result.exit_code != 0
        assert 'Failed to undo wrangling operation' in result.output or 'API error' in result.output


class TestTransformationWranglingRedo:
    """Test transformation wrangling redo command"""

    def test_redo_wrangling_success_table_format(self, runner, mock_api_client):
        """Test redoing a wrangling operation successfully in table format"""
        mock_response = {
            'session_id': 'session-123',
            'redone_operation': {
                'type': 'FILTER',
                'parameters': {'condition': 'age > 18'}
            },
            'applied_operations_count': 2,
            'can_undo': True,
            'can_redo': False
        }
        mock_api_client.post.return_value = mock_response

        result = runner.invoke(cli, [
            'transformation', 'wrangling', 'redo', 'session-123'
        ])

        assert result.exit_code == 0
        assert 'Operation redone successfully!' in result.output
        assert 'session-123' in result.output
        assert 'FILTER' in result.output  # redone_operation type
        assert '2' in result.output  # applied_operations_count
        mock_api_client.post.assert_called_once_with('transformation/wrangling/session-123/redo/')

    def test_redo_wrangling_success_json_format(self, runner, mock_api_client):
        """Test redoing a wrangling operation successfully in JSON format"""
        mock_response = {
            'session_id': 'session-123',
            'redone_operation': {'type': 'FILTER'},
            'applied_operations_count': 2,
            'can_undo': True,
            'can_redo': False
        }
        mock_api_client.post.return_value = mock_response

        result = runner.invoke(cli, [
            'transformation', 'wrangling', 'redo', 'session-123',
            '--format', 'json'
        ])

        assert result.exit_code == 0
        output_data = json.loads(result.output)
        assert output_data['session_id'] == 'session-123'
        assert output_data['redone_operation']['type'] == 'FILTER'

    def test_redo_wrangling_cannot_redo(self, runner, mock_api_client):
        """Test redoing when no operations to redo"""
        from click import ClickException
        mock_api_client.post.side_effect = ClickException(
            "API error (400): Cannot redo: no operations to redo"
        )

        result = runner.invoke(cli, [
            'transformation', 'wrangling', 'redo', 'session-123'
        ])

        assert result.exit_code != 0
        assert 'Failed to redo wrangling operation' in result.output or 'API error' in result.output

    def test_redo_wrangling_api_error(self, runner, mock_api_client):
        """Test handling API errors when redoing wrangling operation"""
        from click import ClickException
        mock_api_client.post.side_effect = ClickException("API error: Session not found")

        result = runner.invoke(cli, [
            'transformation', 'wrangling', 'redo', 'session-123'
        ])

        assert result.exit_code != 0
        assert 'Failed to redo wrangling operation' in result.output or 'API error' in result.output


class TestTransformationWranglingGet:
    """Test transformation wrangling get command"""

    def test_get_wrangling_success_table_format(self, runner, mock_api_client):
        """Test getting a wrangling session successfully in table format"""
        mock_data = {
            'id': 'session-123',
            'name': 'Test Session',
            'description': 'Test description',
            'asset_id': 'asset-456',
            'asset_name': 'Test Asset',
            'applied_operations_count': 3,
            'history_position': 2,
            'can_undo': True,
            'can_redo': False,
            'operation_history': [
                {'type': 'FILTER', 'timestamp': '2025-01-01T00:00:00Z'},
                {'type': 'SORT', 'timestamp': '2025-01-01T01:00:00Z'},
                {'type': 'TRANSFORM', 'timestamp': '2025-01-01T02:00:00Z'}
            ],
            'wrangling_script': '# Data Wrangling Script',
            'current_state': {'row_count': 100},
            'created_at': '2025-01-01T00:00:00Z',
            'updated_at': '2025-01-01T02:00:00Z'
        }
        mock_api_client.get.return_value = mock_data

        result = runner.invoke(cli, [
            'transformation', 'wrangling', 'get', 'session-123'
        ])

        assert result.exit_code == 0
        assert 'session-123' in result.output
        assert 'Test Session' in result.output
        assert 'Test description' in result.output
        assert 'asset-456' in result.output
        assert 'Test Asset' in result.output
        assert '3' in result.output  # applied_operations_count
        assert 'FILTER' in result.output
        assert 'SORT' in result.output
        assert 'TRANSFORM' in result.output
        assert 'Data Wrangling Script' in result.output
        mock_api_client.get.assert_called_once_with('transformation/wrangling/session-123/')

    def test_get_wrangling_success_json_format(self, runner, mock_api_client):
        """Test getting a wrangling session successfully in JSON format"""
        mock_data = {
            'id': 'session-123',
            'name': 'Test Session',
            'asset_id': 'asset-456',
            'applied_operations_count': 3
        }
        mock_api_client.get.return_value = mock_data

        result = runner.invoke(cli, [
            'transformation', 'wrangling', 'get', 'session-123',
            '--format', 'json'
        ])

        assert result.exit_code == 0
        output_data = json.loads(result.output)
        assert output_data['id'] == 'session-123'
        assert output_data['name'] == 'Test Session'
        assert output_data['asset_id'] == 'asset-456'

    def test_get_wrangling_with_long_history(self, runner, mock_api_client):
        """Test getting a wrangling session with long operation history"""
        # Create a history with more than 10 operations
        long_history = [
            {'type': f'OP{i}', 'timestamp': f'2025-01-01T{i:02d}:00:00Z'}
            for i in range(15)
        ]
        mock_data = {
            'id': 'session-123',
            'name': 'Test Session',
            'asset_id': 'asset-456',
            'applied_operations_count': 15,
            'operation_history': long_history
        }
        mock_api_client.get.return_value = mock_data

        result = runner.invoke(cli, [
            'transformation', 'wrangling', 'get', 'session-123'
        ])

        assert result.exit_code == 0
        assert '15 operations' in result.output
        assert '... and 5 more operations' in result.output

    def test_get_wrangling_not_found(self, runner, mock_api_client):
        """Test getting a non-existent wrangling session"""
        from click import ClickException
        mock_api_client.get.side_effect = ClickException("API error: Session not found")

        result = runner.invoke(cli, [
            'transformation', 'wrangling', 'get', 'non-existent'
        ])

        assert result.exit_code != 0
        assert 'Failed to get wrangling session' in result.output or 'API error' in result.output

    def test_get_wrangling_api_error(self, runner, mock_api_client):
        """Test handling API errors when getting wrangling session"""
        from click import ClickException
        mock_api_client.get.side_effect = ClickException("API error: Connection failed")

        result = runner.invoke(cli, [
            'transformation', 'wrangling', 'get', 'session-123'
        ])

        assert result.exit_code != 0
        assert 'Failed to get wrangling session' in result.output or 'API error' in result.output


class TestTransformationWranglingCommandStructure:
    """Test transformation wrangling command group structure"""

    def test_wrangling_command_group_exists(self, runner):
        """Test that wrangling command group exists"""
        result = runner.invoke(cli, ['transformation', 'wrangling', '--help'])
        assert result.exit_code == 0
        assert 'Wrangling session management commands' in result.output

    def test_wrangling_start_command_exists(self, runner):
        """Test that wrangling start command exists"""
        result = runner.invoke(cli, ['transformation', 'wrangling', 'start', '--help'])
        assert result.exit_code == 0
        assert 'Start a new wrangling session' in result.output or 'wrangling' in result.output.lower()

    def test_wrangling_apply_command_exists(self, runner):
        """Test that wrangling apply command exists"""
        result = runner.invoke(cli, ['transformation', 'wrangling', 'apply', '--help'])
        assert result.exit_code == 0
        assert 'Apply a wrangling operation' in result.output or 'wrangling' in result.output.lower()

    def test_wrangling_undo_command_exists(self, runner):
        """Test that wrangling undo command exists"""
        result = runner.invoke(cli, ['transformation', 'wrangling', 'undo', '--help'])
        assert result.exit_code == 0
        assert 'Undo the last operation' in result.output or 'undo' in result.output.lower()

    def test_wrangling_redo_command_exists(self, runner):
        """Test that wrangling redo command exists"""
        result = runner.invoke(cli, ['transformation', 'wrangling', 'redo', '--help'])
        assert result.exit_code == 0
        assert 'Redo the next operation' in result.output or 'redo' in result.output.lower()

    def test_wrangling_get_command_exists(self, runner):
        """Test that wrangling get command exists"""
        result = runner.invoke(cli, ['transformation', 'wrangling', 'get', '--help'])
        assert result.exit_code == 0
        assert 'Get detailed information' in result.output or 'wrangling' in result.output.lower()
