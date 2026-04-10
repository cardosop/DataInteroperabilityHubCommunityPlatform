from tests.pytest_mvp_skip import skip_if_mvp_mode

pytestmark = skip_if_mvp_mode

"""
Unit tests for ML training CLI commands.

Tests all training commands with comprehensive coverage:
- submit, list, get, cancel, logs
- Parameter validation
- Error handling
- Output formatting
"""
import pytest
import json
import os
import tempfile
from click.testing import CliRunner
from unittest.mock import Mock, patch, MagicMock
from datahub_cli.main import cli
from datahub_cli.api_client import api_client


class TestMLTrainingCommands:
    """Unit tests for ML training commands"""

    @pytest.fixture
    def runner(self):
        """Create CLI runner"""
        return CliRunner()

    @pytest.fixture
    def mock_api_client(self):
        """Mock API client"""
        with patch.object(api_client, 'post') as mock_post, \
             patch.object(api_client, 'get') as mock_get:
            yield {'post': mock_post, 'get': mock_get}

    def test_training_command_group_accessible(self, runner):
        """Test that training command group is accessible"""
        result = runner.invoke(cli, ['ml', 'training', '--help'])
        assert result.exit_code == 0, f"Command failed: {result.output}"
        assert 'Training job commands' in result.output

    def test_training_submit_command_help(self, runner):
        """Test that training submit command has correct help text"""
        result = runner.invoke(cli, ['ml', 'training', 'submit', '--help'])
        assert result.exit_code == 0, f"Command failed: {result.output}"
        assert 'Submit a training job' in result.output
        assert '--model-id' in result.output
        assert '--dataset-id' in result.output
        assert '--config' in result.output
        assert '--format' in result.output

    def test_training_submit_with_json_string_config(self, runner, mock_api_client):
        """Test training submit with JSON string config"""
        mock_api_client['post'].return_value = {
            'job_id': 'test-job-123',
            'hub_job_id': 'hub-job-456',
            'status': 'SUBMITTED',
            'model_id': 'model-uuid',
            'dataset_id': 'dataset-uuid',
            'submitted_at': '2024-01-01T00:00:00Z'
        }

        config_json = '{"epochs": 10, "batch_size": 32}'
        result = runner.invoke(cli, [
            'ml', 'training', 'submit',
            '--model-id', '123e4567-e89b-12d3-a456-426614174000',
            '--dataset-id', '123e4567-e89b-12d3-a456-426614174001',
            '--config', config_json,
            '--format', 'json'
        ])

        assert result.exit_code == 0, f"Command failed: {result.output}"
        mock_api_client['post'].assert_called_once()
        call_args = mock_api_client['post'].call_args
        assert call_args[0][0] == 'ml/training/jobs/'
        assert call_args[1]['json_data']['model_id'] == '123e4567-e89b-12d3-a456-426614174000'
        assert call_args[1]['json_data']['dataset_id'] == '123e4567-e89b-12d3-a456-426614174001'
        assert call_args[1]['json_data']['config'] == {'epochs': 10, 'batch_size': 32}

    def test_training_submit_with_file_config(self, runner, mock_api_client):
        """Test training submit with config file"""
        mock_api_client['post'].return_value = {
            'job_id': 'test-job-123',
            'hub_job_id': 'hub-job-456',
            'status': 'SUBMITTED',
            'model_id': 'model-uuid',
            'dataset_id': 'dataset-uuid',
            'submitted_at': '2024-01-01T00:00:00Z'
        }

        config_data = {'epochs': 10, 'batch_size': 32, 'learning_rate': 0.001}
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(config_data, f)
            config_file = f.name

        try:
            result = runner.invoke(cli, [
                'ml', 'training', 'submit',
                '--model-id', '123e4567-e89b-12d3-a456-426614174000',
                '--dataset-id', '123e4567-e89b-12d3-a456-426614174001',
                '--config', config_file,
                '--format', 'json'
            ])

            assert result.exit_code == 0, f"Command failed: {result.output}"
            mock_api_client['post'].assert_called_once()
            call_args = mock_api_client['post'].call_args
            assert call_args[1]['json_data']['config'] == config_data
        finally:
            os.unlink(config_file)

    def test_training_submit_invalid_uuid(self, runner):
        """Test training submit with invalid UUID"""
        result = runner.invoke(cli, [
            'ml', 'training', 'submit',
            '--model-id', 'invalid-uuid',
            '--dataset-id', '123e4567-e89b-12d3-a456-426614174001',
            '--config', '{"epochs": 10}'
        ])

        assert result.exit_code != 0, "Should fail with invalid UUID"
        assert 'Invalid' in result.output or 'UUID' in result.output

    def test_training_submit_invalid_json(self, runner):
        """Test training submit with invalid JSON"""
        result = runner.invoke(cli, [
            'ml', 'training', 'submit',
            '--model-id', '123e4567-e89b-12d3-a456-426614174000',
            '--dataset-id', '123e4567-e89b-12d3-a456-426614174001',
            '--config', 'invalid json'
        ])

        assert result.exit_code != 0, "Should fail with invalid JSON"
        assert 'Invalid JSON' in result.output or 'JSON' in result.output

    def test_training_list_command_help(self, runner):
        """Test that training list command has correct help text"""
        result = runner.invoke(cli, ['ml', 'training', 'list', '--help'])
        assert result.exit_code == 0, f"Command failed: {result.output}"
        assert 'List training jobs' in result.output
        assert '--model-id' in result.output
        assert '--status' in result.output
        assert '--limit' in result.output
        assert '--offset' in result.output
        assert '--format' in result.output

    def test_training_list_success(self, runner, mock_api_client):
        """Test training list command success"""
        mock_api_client['get'].return_value = {
            'results': [
                {
                    'job_id': 'job-1',
                    'model_id': 'model-1',
                    'status': 'RUNNING',
                    'progress': 0.5,
                    'submitted_at': '2024-01-01T00:00:00Z'
                },
                {
                    'job_id': 'job-2',
                    'model_id': 'model-2',
                    'status': 'COMPLETED',
                    'progress': 1.0,
                    'submitted_at': '2024-01-01T01:00:00Z'
                }
            ],
            'count': 2,
            'limit': 20,
            'offset': 0
        }

        result = runner.invoke(cli, ['ml', 'training', 'list', '--format', 'json'])

        assert result.exit_code == 0, f"Command failed: {result.output}"
        mock_api_client['get'].assert_called_once()
        call_args = mock_api_client['get'].call_args
        assert call_args[0][0] == 'ml/training/jobs/'
        assert call_args[1]['params']['limit'] == 20
        assert call_args[1]['params']['offset'] == 0

    def test_training_list_with_filters(self, runner, mock_api_client):
        """Test training list with filters"""
        mock_api_client['get'].return_value = {'results': [], 'count': 0}

        result = runner.invoke(cli, [
            'ml', 'training', 'list',
            '--model-id', '123e4567-e89b-12d3-a456-426614174000',
            '--status', 'RUNNING',
            '--limit', '10',
            '--offset', '5'
        ])

        assert result.exit_code == 0, f"Command failed: {result.output}"
        call_args = mock_api_client['get'].call_args
        assert call_args[1]['params']['model_id'] == '123e4567-e89b-12d3-a456-426614174000'
        assert call_args[1]['params']['status'] == 'RUNNING'
        assert call_args[1]['params']['limit'] == 10
        assert call_args[1]['params']['offset'] == 5

    def test_training_get_command_help(self, runner):
        """Test that training get command has correct help text"""
        result = runner.invoke(cli, ['ml', 'training', 'get', '--help'])
        assert result.exit_code == 0, f"Command failed: {result.output}"
        assert 'Get training job details' in result.output
        assert 'JOB_ID' in result.output
        assert '--format' in result.output

    def test_training_get_success(self, runner, mock_api_client):
        """Test training get command success"""
        mock_api_client['get'].return_value = {
            'job_id': 'test-job-123',
            'hub_job_id': 'hub-job-456',
            'model_id': 'model-uuid',
            'dataset_id': 'dataset-uuid',
            'status': 'RUNNING',
            'progress': 0.75,
            'submitted_at': '2024-01-01T00:00:00Z',
            'started_at': '2024-01-01T00:05:00Z',
            'metrics': {'accuracy': 0.95},
            'logs_url': 'http://example.com/logs'
        }

        result = runner.invoke(cli, [
            'ml', 'training', 'get',
            'test-job-123',
            '--format', 'json'
        ])

        assert result.exit_code == 0, f"Command failed: {result.output}"
        mock_api_client['get'].assert_called_once()
        call_args = mock_api_client['get'].call_args
        assert call_args[0][0] == 'ml/training/jobs/test-job-123/'

    def test_training_cancel_command_help(self, runner):
        """Test that training cancel command has correct help text"""
        result = runner.invoke(cli, ['ml', 'training', 'cancel', '--help'])
        assert result.exit_code == 0, f"Command failed: {result.output}"
        assert 'Cancel a training job' in result.output
        assert 'JOB_ID' in result.output

    def test_training_cancel_success(self, runner, mock_api_client):
        """Test training cancel command success"""
        mock_api_client['post'].return_value = {'detail': 'Training job cancelled successfully'}

        result = runner.invoke(cli, [
            'ml', 'training', 'cancel',
            'test-job-123',
            '--format', 'table'
        ])

        assert result.exit_code == 0, f"Command failed: {result.output}"
        mock_api_client['post'].assert_called_once()
        call_args = mock_api_client['post'].call_args
        assert call_args[0][0] == 'ml/training/jobs/test-job-123/cancel/'
        assert 'cancelled successfully' in result.output.lower()

    def test_training_logs_command_help(self, runner):
        """Test that training logs command has correct help text"""
        result = runner.invoke(cli, ['ml', 'training', 'logs', '--help'])
        assert result.exit_code == 0, f"Command failed: {result.output}"
        assert 'Get training job logs' in result.output
        assert 'JOB_ID' in result.output
        assert '--lines' in result.output

    def test_training_logs_success(self, runner, mock_api_client):
        """Test training logs command success"""
        mock_api_client['get'].return_value = {
            'logs': [
                {'timestamp': '2024-01-01T00:00:00Z', 'level': 'INFO', 'message': 'Training started'},
                {'timestamp': '2024-01-01T00:01:00Z', 'level': 'INFO', 'message': 'Epoch 1 completed'}
            ]
        }

        result = runner.invoke(cli, [
            'ml', 'training', 'logs',
            'test-job-123',
            '--lines', '100',
            '--format', 'table'
        ])

        assert result.exit_code == 0, f"Command failed: {result.output}"
        mock_api_client['get'].assert_called_once()
        call_args = mock_api_client['get'].call_args
        assert call_args[0][0] == 'ml/training/jobs/test-job-123/logs/'
        assert call_args[1]['params']['lines'] == 100
        assert 'Training started' in result.output

    def test_training_logs_with_lines(self, runner, mock_api_client):
        """Test training logs with lines parameter"""
        mock_api_client['get'].return_value = {'logs': []}

        result = runner.invoke(cli, [
            'ml', 'training', 'logs',
            'test-job-123',
            '--lines', '50'
        ])

        assert result.exit_code == 0, f"Command failed: {result.output}"
        call_args = mock_api_client['get'].call_args
        assert call_args[1]['params']['lines'] == 50

    def test_training_list_empty_results(self, runner, mock_api_client):
        """Test training list with empty results"""
        mock_api_client['get'].return_value = {'results': [], 'count': 0}

        result = runner.invoke(cli, ['ml', 'training', 'list', '--format', 'table'])

        assert result.exit_code == 0, f"Command failed: {result.output}"
        assert 'No training jobs found' in result.output

    def test_training_list_table_format(self, runner, mock_api_client):
        """Test training list with table format"""
        mock_api_client['get'].return_value = {
            'results': [
                {
                    'job_id': 'job-1',
                    'model_id': 'model-1',
                    'status': 'RUNNING',
                    'progress': 0.5,
                    'submitted_at': '2024-01-01T00:00:00Z'
                }
            ],
            'count': 1
        }

        result = runner.invoke(cli, ['ml', 'training', 'list', '--format', 'table'])

        assert result.exit_code == 0, f"Command failed: {result.output}"
        assert 'Job ID' in result.output
        assert 'Model ID' in result.output
        assert 'Status' in result.output
        assert 'Progress' in result.output

    def test_training_get_table_format(self, runner, mock_api_client):
        """Test training get with table format"""
        mock_api_client['get'].return_value = {
            'job_id': 'test-job-123',
            'hub_job_id': 'hub-job-456',
            'model_id': 'model-uuid',
            'dataset_id': 'dataset-uuid',
            'status': 'RUNNING',
            'progress': 0.75,
            'submitted_at': '2024-01-01T00:00:00Z'
        }

        result = runner.invoke(cli, ['ml', 'training', 'get', 'test-job-123', '--format', 'table'])

        assert result.exit_code == 0, f"Command failed: {result.output}"
        assert 'Job ID:' in result.output
        assert 'Status:' in result.output
        assert 'Progress:' in result.output

    def test_training_submit_table_format(self, runner, mock_api_client):
        """Test training submit with table format"""
        mock_api_client['post'].return_value = {
            'job_id': 'test-job-123',
            'hub_job_id': 'hub-job-456',
            'status': 'SUBMITTED',
            'model_id': 'model-uuid',
            'dataset_id': 'dataset-uuid',
            'submitted_at': '2024-01-01T00:00:00Z'
        }

        result = runner.invoke(cli, [
            'ml', 'training', 'submit',
            '--model-id', '123e4567-e89b-12d3-a456-426614174000',
            '--dataset-id', '123e4567-e89b-12d3-a456-426614174001',
            '--config', '{"epochs": 10}',
            '--format', 'table'
        ])

        assert result.exit_code == 0, f"Command failed: {result.output}"
        assert 'submitted successfully' in result.output.lower()
        assert 'Job ID:' in result.output
        assert 'Status:' in result.output
