"""
Comprehensive unit tests for jobs CLI commands.

Tests all job commands: list, get, cancel, watch.
"""
import pytest
import json
import time
from click.testing import CliRunner
from unittest.mock import Mock, patch
from datahub_cli.main import cli
from datahub_cli.commands import jobs
from datahub_cli.api_client import api_client


class TestJobsList:
    """Test jobs list command"""
    
    def test_list_jobs_success_table_format(self, runner, mock_api_client):
        """Test listing jobs in table format"""
        mock_data = {
            'results': [
                {
                    'id': 'job-1',
                    'type': 'DQ_RUN',
                    'status': 'RUNNING',
                    'created_at': '2025-01-01T00:00:00Z'
                },
                {
                    'id': 'job-2',
                    'type': 'COMPLIANCE_CHECK',
                    'status': 'COMPLETED',
                    'created_at': '2025-01-01T01:00:00Z'
                }
            ]
        }
        mock_api_client.get.return_value = mock_data
        
        result = runner.invoke(cli, ['jobs', 'list'])
        
        assert result.exit_code == 0
        assert 'job-1' in result.output
        assert 'job-2' in result.output
        assert 'DQ_RUN' in result.output
        assert 'RUNNING' in result.output
        mock_api_client.get.assert_called_once_with('jobs/jobs/', params={'limit': 20, 'offset': 0})
    
    def test_list_jobs_success_json_format(self, runner, mock_api_client):
        """Test listing jobs in JSON format"""
        mock_data = {
            'results': [
                {'id': 'job-1', 'type': 'DQ_RUN', 'status': 'RUNNING'}
            ]
        }
        mock_api_client.get.return_value = mock_data
        
        result = runner.invoke(cli, ['jobs', 'list', '--format', 'json'])
        
        assert result.exit_code == 0
        output_data = json.loads(result.output)
        assert isinstance(output_data, list)
        assert len(output_data) == 1
    
    def test_list_jobs_with_filters(self, runner, mock_api_client):
        """Test listing jobs with type and status filters"""
        mock_data = {'results': []}
        mock_api_client.get.return_value = mock_data
        
        result = runner.invoke(cli, [
            'jobs', 'list',
            '--type', 'DQ_RUN',
            '--status', 'RUNNING',
            '--limit', '10',
            '--offset', '5'
        ])
        
        assert result.exit_code == 0
        mock_api_client.get.assert_called_once_with(
            'jobs/jobs/',
            params={'type': 'DQ_RUN', 'status': 'RUNNING', 'limit': 10, 'offset': 5}
        )
    
    def test_list_jobs_empty_result(self, runner, mock_api_client):
        """Test listing jobs when no jobs exist"""
        mock_api_client.get.return_value = {'results': []}
        
        result = runner.invoke(cli, ['jobs', 'list'])
        
        assert result.exit_code == 0
        assert 'No jobs found' in result.output
    
    def test_list_jobs_unexpected_response_type(self, runner, mock_api_client):
        """Test listing jobs with unexpected response type (not dict or list)"""
        # Test edge case where API returns something unexpected
        mock_api_client.get.return_value = None
        
        result = runner.invoke(cli, ['jobs', 'list'])
        
        assert result.exit_code == 0
        assert 'No jobs found' in result.output
    
    def test_list_jobs_api_error(self, runner, mock_api_client):
        """Test handling API errors when listing jobs"""
        from click import ClickException
        mock_api_client.get.side_effect = ClickException("API error: Connection failed")
        
        result = runner.invoke(cli, ['jobs', 'list'])
        
        assert result.exit_code != 0
        assert 'Failed to list jobs' in result.output or 'API error' in result.output


class TestJobsGet:
    """Test jobs get command"""
    
    def test_get_job_success_table_format(self, runner, mock_api_client):
        """Test getting a job in table format"""
        mock_data = {
            'id': 'job-1',
            'type': 'DQ_RUN',
            'status': 'COMPLETED',
            'resource_type': 'DATASET',
            'resource_id': 'dataset-1',
            'created_at': '2025-01-01T00:00:00Z',
            'started_at': '2025-01-01T00:01:00Z',
            'completed_at': '2025-01-01T00:02:00Z'
        }
        mock_api_client.get.return_value = mock_data
        
        result = runner.invoke(cli, ['jobs', 'get', 'job-1'])
        
        assert result.exit_code == 0
        assert 'job-1' in result.output
        assert 'DQ_RUN' in result.output
        assert 'COMPLETED' in result.output
        assert 'DATASET' in result.output
        mock_api_client.get.assert_called_once_with('jobs/jobs/job-1/')
    
    def test_get_job_with_error_message(self, runner, mock_api_client):
        """Test getting a job with error message"""
        mock_data = {
            'id': 'job-1',
            'type': 'DQ_RUN',
            'status': 'FAILED',
            'error_message': 'Job execution failed'
        }
        mock_api_client.get.return_value = mock_data
        
        result = runner.invoke(cli, ['jobs', 'get', 'job-1'])
        
        assert result.exit_code == 0
        assert 'FAILED' in result.output
        assert 'Job execution failed' in result.output
    
    def test_get_job_success_json_format(self, runner, mock_api_client):
        """Test getting a job in JSON format"""
        mock_data = {
            'id': 'job-1',
            'type': 'DQ_RUN',
            'status': 'COMPLETED'
        }
        mock_api_client.get.return_value = mock_data
        
        result = runner.invoke(cli, ['jobs', 'get', 'job-1', '--format', 'json'])
        
        assert result.exit_code == 0
        output_data = json.loads(result.output)
        assert output_data['id'] == 'job-1'
    
    def test_get_job_api_error(self, runner, mock_api_client):
        """Test handling API errors when getting a job"""
        from click import ClickException
        mock_api_client.get.side_effect = ClickException("API error: Not found")
        
        result = runner.invoke(cli, ['jobs', 'get', 'job-1'])
        
        assert result.exit_code != 0
        assert 'Failed to get job' in result.output or 'API error' in result.output


class TestJobsCancel:
    """Test jobs cancel command"""
    
    def test_cancel_job_success_table_format(self, runner, mock_api_client):
        """Test cancelling a job in table format"""
        mock_result = {
            'id': 'job-1',
            'status': 'CANCELLED'
        }
        mock_api_client.post.return_value = mock_result
        
        result = runner.invoke(cli, ['jobs', 'cancel', 'job-1'])
        
        assert result.exit_code == 0
        assert 'cancelled successfully' in result.output
        assert 'CANCELLED' in result.output
        mock_api_client.post.assert_called_once_with('jobs/jobs/job-1/cancel/')
    
    def test_cancel_job_json_output(self, runner, mock_api_client):
        """Test cancelling a job with JSON output"""
        mock_result = {'id': 'job-1', 'status': 'CANCELLED'}
        mock_api_client.post.return_value = mock_result
        
        result = runner.invoke(cli, ['jobs', 'cancel', 'job-1', '--format', 'json'])
        
        assert result.exit_code == 0
        output_data = json.loads(result.output)
        assert output_data['status'] == 'CANCELLED'
    
    def test_cancel_job_api_error(self, runner, mock_api_client):
        """Test handling API errors when cancelling a job"""
        from click import ClickException
        mock_api_client.post.side_effect = ClickException("API error: Not found")
        
        result = runner.invoke(cli, ['jobs', 'cancel', 'job-1'])
        
        assert result.exit_code != 0
        assert 'Failed to cancel job' in result.output or 'API error' in result.output


class TestJobsWatch:
    """Test jobs watch command"""
    
    @patch('datahub_cli.commands.jobs.time.sleep')
    def test_watch_job_completion_success(self, mock_sleep, runner, mock_api_client):
        """Test watching a job until completion"""
        # First call: job is running
        # Second call: job is completed
        mock_api_client.get.side_effect = [
            {'id': 'job-1', 'status': 'RUNNING'},
            {'id': 'job-1', 'status': 'COMPLETED'}
        ]
        
        result = runner.invoke(cli, [
            'jobs', 'watch', 'job-1',
            '--interval', '1',
            '--timeout', '10'
        ])
        
        assert result.exit_code == 0
        assert 'COMPLETED' in result.output or 'completed' in result.output
        assert mock_api_client.get.call_count == 2
        mock_sleep.assert_called_once_with(1)
    
    @patch('datahub_cli.commands.jobs.time.sleep')
    def test_watch_job_failure(self, mock_sleep, runner, mock_api_client):
        """Test watching a job until failure"""
        mock_api_client.get.side_effect = [
            {'id': 'job-1', 'status': 'RUNNING'},
            {'id': 'job-1', 'status': 'FAILED', 'error_message': 'Job failed'}
        ]
        
        result = runner.invoke(cli, [
            'jobs', 'watch', 'job-1',
            '--interval', '1',
            '--timeout', '10'
        ])
        
        assert result.exit_code == 0
        assert 'FAILED' in result.output or 'failed' in result.output
        assert 'Job failed' in result.output
    
    @patch('datahub_cli.commands.jobs.time.sleep')
    def test_watch_job_cancelled(self, mock_sleep, runner, mock_api_client):
        """Test watching a job until cancellation"""
        mock_api_client.get.side_effect = [
            {'id': 'job-1', 'status': 'RUNNING'},
            {'id': 'job-1', 'status': 'CANCELLED'}
        ]
        
        result = runner.invoke(cli, [
            'jobs', 'watch', 'job-1',
            '--interval', '1',
            '--timeout', '10'
        ])
        
        assert result.exit_code == 0
        assert 'CANCELLED' in result.output or 'cancelled' in result.output
    
    @patch('datahub_cli.commands.jobs.time.sleep')
    def test_watch_job_timeout(self, mock_sleep, runner, mock_api_client):
        """Test watching a job that times out"""
        # Mock time.time to simulate timeout
        with patch('datahub_cli.commands.jobs.time.time') as mock_time:
            mock_time.side_effect = [0, 301]  # Start at 0, timeout at 301 seconds
            mock_api_client.get.return_value = {'id': 'job-1', 'status': 'RUNNING'}
            
            result = runner.invoke(cli, [
                'jobs', 'watch', 'job-1',
                '--interval', '1',
                '--timeout', '300'
            ])
            
            assert result.exit_code != 0
            assert 'Timeout' in result.output or 'timeout' in result.output
    
    @patch('datahub_cli.commands.jobs.time.sleep')
    def test_watch_job_json_output(self, mock_sleep, runner, mock_api_client):
        """Test watching a job with JSON output"""
        mock_api_client.get.side_effect = [
            {'id': 'job-1', 'status': 'RUNNING'},
            {'id': 'job-1', 'status': 'COMPLETED'}
        ]
        
        result = runner.invoke(cli, [
            'jobs', 'watch', 'job-1',
            '--format', 'json',
            '--interval', '1',
            '--timeout', '10'
        ])
        
        assert result.exit_code == 0
        output_data = json.loads(result.output)
        assert output_data['status'] == 'COMPLETED'
    
    @patch('datahub_cli.commands.jobs.time.sleep')
    def test_watch_job_keyboard_interrupt(self, mock_sleep, runner, mock_api_client):
        """Test handling keyboard interrupt while watching a job"""
        mock_api_client.get.side_effect = KeyboardInterrupt()
        
        result = runner.invoke(cli, [
            'jobs', 'watch', 'job-1',
            '--interval', '1',
            '--timeout', '10'
        ])
        
        # KeyboardInterrupt should be caught and handled gracefully
        # Exit code may vary, but should not crash
        assert 'cancelled' in result.output.lower() or result.exit_code in [0, 130]
    
    def test_watch_job_api_error(self, runner, mock_api_client):
        """Test handling API errors when watching a job"""
        from click import ClickException
        mock_api_client.get.side_effect = ClickException("API error: Not found")
        
        result = runner.invoke(cli, [
            'jobs', 'watch', 'job-1',
            '--interval', '1',
            '--timeout', '10'
        ])
        
        assert result.exit_code != 0
        assert 'Failed to watch job' in result.output or 'API error' in result.output


@pytest.fixture
def runner():
    """CLI runner fixture"""
    return CliRunner()


@pytest.fixture
def mock_api_client(monkeypatch):
    """Mock API client"""
    mock_client = Mock()
    monkeypatch.setattr('datahub_cli.commands.jobs.api_client', mock_client)
    return mock_client

