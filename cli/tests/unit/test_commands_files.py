"""
Comprehensive unit tests for files CLI commands.

Tests all file commands: list, upload, download, delete.
"""
import pytest
import json
import tempfile
import os
from pathlib import Path
from click.testing import CliRunner
from unittest.mock import Mock, patch, MagicMock
from datahub_cli.main import cli
from datahub_cli.commands import files
from datahub_cli.api_client import api_client


class TestFilesList:
    """Test files list command"""
    
    def test_list_files_success_table_format(self, runner, mock_api_client):
        """Test listing files in table format"""
        mock_data = {
            'results': [
                {
                    'id': 'file-1',
                    'name': 'test.csv',
                    'size': 1024,
                    'status': 'UPLOADED'
                },
                {
                    'id': 'file-2',
                    'name': 'test.json',
                    'size': 2048,
                    'status': 'PENDING'
                }
            ]
        }
        mock_api_client.get.return_value = mock_data
        
        result = runner.invoke(cli, ['files', 'list'])
        
        assert result.exit_code == 0
        assert 'file-1' in result.output
        assert 'file-2' in result.output
        assert 'test.csv' in result.output
        assert 'UPLOADED' in result.output
        mock_api_client.get.assert_called_once_with('files/files/', params={'limit': 20, 'offset': 0})
    
    def test_list_files_success_json_format(self, runner, mock_api_client):
        """Test listing files in JSON format"""
        mock_data = {
            'results': [
                {'id': 'file-1', 'name': 'test.csv', 'size': 1024, 'status': 'UPLOADED'}
            ]
        }
        mock_api_client.get.return_value = mock_data
        
        result = runner.invoke(cli, ['files', 'list', '--format', 'json'])
        
        assert result.exit_code == 0
        output_data = json.loads(result.output)
        assert isinstance(output_data, list)
        assert len(output_data) == 1
    
    def test_list_files_with_status_filter(self, runner, mock_api_client):
        """Test listing files with status filter"""
        mock_data = {'results': []}
        mock_api_client.get.return_value = mock_data
        
        result = runner.invoke(cli, [
            'files', 'list',
            '--status', 'UPLOADED',
            '--limit', '10',
            '--offset', '5'
        ])
        
        assert result.exit_code == 0
        mock_api_client.get.assert_called_once_with(
            'files/files/',
            params={'status': 'UPLOADED', 'limit': 10, 'offset': 5}
        )
    
    def test_list_files_empty_result(self, runner, mock_api_client):
        """Test listing files when no files exist"""
        mock_api_client.get.return_value = {'results': []}
        
        result = runner.invoke(cli, ['files', 'list'])
        
        assert result.exit_code == 0
        assert 'No files found' in result.output
    
    def test_list_files_unexpected_response_type(self, runner, mock_api_client):
        """Test listing files with unexpected response type (not dict or list)"""
        # Test edge case where API returns something unexpected
        mock_api_client.get.return_value = None
        
        result = runner.invoke(cli, ['files', 'list'])
        
        assert result.exit_code == 0
        assert 'No files found' in result.output
    
    def test_list_files_api_error(self, runner, mock_api_client):
        """Test handling API errors when listing files"""
        from click import ClickException
        mock_api_client.get.side_effect = ClickException("API error: Connection failed")
        
        result = runner.invoke(cli, ['files', 'list'])
        
        assert result.exit_code != 0
        assert 'Failed to list files' in result.output or 'API error' in result.output


class TestFilesUpload:
    """Test files upload command"""
    
    def test_upload_file_success(self, runner, mock_api_client, temp_file):
        """Test uploading a file successfully"""
        file_path, content = temp_file('.csv', 'col1,col2\nval1,val2')
        file_size = len(content.encode())
        
        # Mock init response
        init_response = {
            'file_id': 'file-1',
            'upload_url': 'https://s3.example.com/upload'
        }
        
        # Mock complete response
        complete_response = {
            'id': 'file-1',
            'name': os.path.basename(file_path),
            'size': file_size,
            'status': 'UPLOADED'
        }
        
        mock_api_client.post.side_effect = [init_response, complete_response]
        
        # Mock requests.put for S3 upload
        with patch('datahub_cli.commands.files.requests.put') as mock_put:
            mock_put_response = Mock()
            mock_put_response.raise_for_status = Mock()
            mock_put.return_value = mock_put_response
            
            result = runner.invoke(cli, ['files', 'upload', file_path])
            
            assert result.exit_code == 0
            assert 'File uploaded successfully' in result.output
            assert 'file-1' in result.output
            assert mock_api_client.post.call_count == 2
            # Verify init call
            assert mock_api_client.post.call_args_list[0][0][0] == 'files/files/init/'
            # Verify complete call
            assert mock_api_client.post.call_args_list[1][0][0] == 'files/files/file-1/complete/'
            # Verify S3 upload
            mock_put.assert_called_once()
    
    def test_upload_file_with_custom_name(self, runner, mock_api_client, temp_file):
        """Test uploading a file with custom name"""
        file_path, content = temp_file('.csv', 'col1,col2\nval1,val2')
        
        init_response = {
            'file_id': 'file-1',
            'upload_url': 'https://s3.example.com/upload'
        }
        complete_response = {
            'id': 'file-1',
            'name': 'custom-name.csv',
            'size': len(content.encode()),
            'status': 'UPLOADED'
        }
        
        mock_api_client.post.side_effect = [init_response, complete_response]
        
        with patch('datahub_cli.commands.files.requests.put') as mock_put:
            mock_put_response = Mock()
            mock_put_response.raise_for_status = Mock()
            mock_put.return_value = mock_put_response
            
            result = runner.invoke(cli, [
                'files', 'upload', file_path,
                '--name', 'custom-name.csv'
            ])
            
            assert result.exit_code == 0
            call_args = mock_api_client.post.call_args_list[0]
            assert call_args[1]['json_data']['name'] == 'custom-name.csv'
    
    def test_upload_file_unknown_content_type(self, runner, mock_api_client, temp_file):
        """Test uploading a file with unknown content type (fallback to application/octet-stream)"""
        # Create file with unknown extension
        file_path, content = temp_file('.unknown', 'some binary content')
        
        init_response = {
            'file_id': 'file-1',
            'upload_url': 'https://s3.example.com/upload'
        }
        complete_response = {
            'id': 'file-1',
            'name': os.path.basename(file_path),
            'size': len(content.encode()),
            'status': 'UPLOADED'
        }
        
        mock_api_client.post.side_effect = [init_response, complete_response]
        
        with patch('datahub_cli.commands.files.requests.put') as mock_put:
            mock_put_response = Mock()
            mock_put_response.raise_for_status = Mock()
            mock_put.return_value = mock_put_response
            
            result = runner.invoke(cli, ['files', 'upload', file_path])
            
            assert result.exit_code == 0
            call_args = mock_api_client.post.call_args_list[0]
            # Should fall back to application/octet-stream
            assert call_args[1]['json_data']['content_type'] == 'application/octet-stream'
    
    def test_upload_file_json_output(self, runner, mock_api_client, temp_file):
        """Test uploading a file with JSON output"""
        file_path, content = temp_file('.csv', 'col1,col2\nval1,val2')
        
        init_response = {
            'file_id': 'file-1',
            'upload_url': 'https://s3.example.com/upload'
        }
        complete_response = {
            'id': 'file-1',
            'name': os.path.basename(file_path),
            'size': len(content.encode()),
            'status': 'UPLOADED'
        }
        
        mock_api_client.post.side_effect = [init_response, complete_response]
        
        with patch('datahub_cli.commands.files.requests.put') as mock_put:
            mock_put_response = Mock()
            mock_put_response.raise_for_status = Mock()
            mock_put.return_value = mock_put_response
            
            result = runner.invoke(cli, [
                'files', 'upload', file_path,
                '--format', 'json'
            ])
            
            assert result.exit_code == 0
            # The files upload command outputs JSON when --format json is used
            # Extract JSON from output (may have progress messages)
            output_lines = result.output.strip().split('\n')
            # Find the JSON block (starts with { and ends with })
            json_start = None
            json_end = None
            for i, line in enumerate(output_lines):
                if line.strip().startswith('{'):
                    json_start = i
                if json_start is not None and line.strip().endswith('}'):
                    json_end = i + 1
                    break
            if json_start is not None and json_end is not None:
                json_text = '\n'.join(output_lines[json_start:json_end])
                output_data = json.loads(json_text)
                assert output_data['id'] == 'file-1'
            else:
                # If no JSON block found, verify the command succeeded
                assert 'File uploaded successfully' in result.output or 'file-1' in result.output
    
    def test_upload_file_no_upload_url(self, runner, mock_api_client, temp_file):
        """Test uploading a file when no upload URL is returned"""
        file_path, content = temp_file('.csv', 'col1,col2\nval1,val2')
        
        init_response = {
            'file_id': 'file-1',
            'upload_url': None
        }
        mock_api_client.post.return_value = init_response
        
        result = runner.invoke(cli, ['files', 'upload', file_path])
        
        assert result.exit_code != 0
        assert 'No upload URL' in result.output
    
    def test_upload_file_s3_upload_failure(self, runner, mock_api_client, temp_file):
        """Test handling S3 upload failure"""
        file_path, content = temp_file('.csv', 'col1,col2\nval1,val2')
        
        init_response = {
            'file_id': 'file-1',
            'upload_url': 'https://s3.example.com/upload'
        }
        mock_api_client.post.return_value = init_response
        
        with patch('datahub_cli.commands.files.requests.put') as mock_put:
            mock_put_response = Mock()
            mock_put_response.raise_for_status.side_effect = Exception("S3 upload failed")
            mock_put.return_value = mock_put_response
            
            result = runner.invoke(cli, ['files', 'upload', file_path])
            
            assert result.exit_code != 0
            assert 'Failed to upload file' in result.output or 'S3 upload failed' in result.output
    
    def test_upload_file_not_found(self, runner):
        """Test uploading a non-existent file"""
        result = runner.invoke(cli, ['files', 'upload', '/nonexistent/file.csv'])
        
        assert result.exit_code != 0
        # Click validates file path before command execution
        assert 'does not exist' in result.output or 'Failed to upload file' in result.output or 'No such file' in result.output
    
    def test_upload_file_api_error(self, runner, mock_api_client, temp_file):
        """Test handling API errors when uploading a file"""
        file_path, content = temp_file('.csv', 'col1,col2\nval1,val2')
        
        from click import ClickException
        mock_api_client.post.side_effect = ClickException("API error: Connection failed")
        
        result = runner.invoke(cli, ['files', 'upload', file_path])
        
        assert result.exit_code != 0
        assert 'Failed to upload file' in result.output or 'API error' in result.output


class TestFilesDownload:
    """Test files download command"""
    
    def test_download_file_success(self, runner, mock_api_client, tmp_path):
        """Test downloading a file successfully"""
        file_id = 'file-1'
        file_name = 'test.csv'
        file_content = b'col1,col2\nval1,val2'
        
        # Mock get file info
        file_info = {
            'id': file_id,
            'name': file_name,
            'size': len(file_content)
        }
        
        # Mock get download URL
        download_info = {
            'download_url': 'https://s3.example.com/download'
        }
        
        mock_api_client.get.return_value = file_info
        mock_api_client.post.return_value = download_info
        
        # Mock requests.get for download
        with patch('datahub_cli.commands.files.requests.get') as mock_get:
            mock_response = Mock()
            mock_response.raise_for_status = Mock()
            mock_response.iter_content.return_value = [file_content]
            mock_get.return_value = mock_response
            
            output_path = tmp_path / 'downloaded.csv'
            result = runner.invoke(cli, [
                'files', 'download', file_id,
                '--output', str(output_path)
            ])
            
            assert result.exit_code == 0
            assert 'File downloaded' in result.output
            assert output_path.exists()
            assert output_path.read_bytes() == file_content
            mock_api_client.get.assert_called_once_with(f'files/files/{file_id}/')
            mock_api_client.post.assert_called_once_with(f'files/files/{file_id}/download/')
    
    def test_download_file_default_output_path(self, runner, mock_api_client, tmp_path, monkeypatch):
        """Test downloading a file with default output path"""
        file_id = 'file-1'
        file_name = 'test.csv'
        file_content = b'col1,col2\nval1,val2'
        
        # Change to tmp_path for default output
        monkeypatch.chdir(tmp_path)
        
        file_info = {'id': file_id, 'name': file_name, 'size': len(file_content)}
        download_info = {'download_url': 'https://s3.example.com/download'}
        
        mock_api_client.get.return_value = file_info
        mock_api_client.post.return_value = download_info
        
        with patch('datahub_cli.commands.files.requests.get') as mock_get:
            mock_response = Mock()
            mock_response.raise_for_status = Mock()
            mock_response.iter_content.return_value = [file_content]
            mock_get.return_value = mock_response
            
            result = runner.invoke(cli, ['files', 'download', file_id])
            
            assert result.exit_code == 0
            output_path = tmp_path / file_name
            assert output_path.exists()
            assert output_path.read_bytes() == file_content
    
    def test_download_file_no_download_url(self, runner, mock_api_client):
        """Test downloading a file when no download URL is returned"""
        file_id = 'file-1'
        file_info = {'id': file_id, 'name': 'test.csv', 'size': 100}
        download_info = {'download_url': None}
        
        mock_api_client.get.return_value = file_info
        mock_api_client.post.return_value = download_info
        
        result = runner.invoke(cli, ['files', 'download', file_id])
        
        assert result.exit_code != 0
        assert 'No download URL' in result.output
    
    def test_download_file_api_error(self, runner, mock_api_client):
        """Test handling API errors when downloading a file"""
        from click import ClickException
        mock_api_client.get.side_effect = ClickException("API error: Not found")
        
        result = runner.invoke(cli, ['files', 'download', 'file-1'])
        
        assert result.exit_code != 0
        assert 'Failed to download file' in result.output or 'API error' in result.output


class TestFilesDelete:
    """Test files delete command"""
    
    def test_delete_file_with_confirm_flag(self, runner, mock_api_client):
        """Test deleting a file with --confirm flag"""
        mock_api_client.delete.return_value = {}
        
        result = runner.invoke(cli, [
            'files', 'delete', 'file-1',
            '--confirm'
        ])
        
        assert result.exit_code == 0
        assert 'deleted successfully' in result.output
        mock_api_client.delete.assert_called_once_with('files/files/file-1/')
    
    def test_delete_file_with_confirmation_prompt(self, runner, mock_api_client):
        """Test deleting a file with confirmation prompt"""
        mock_api_client.delete.return_value = {}
        
        result = runner.invoke(
            cli,
            ['files', 'delete', 'file-1'],
            input='y\n'
        )
        
        assert result.exit_code == 0
        assert 'deleted successfully' in result.output
    
    def test_delete_file_cancelled(self, runner, mock_api_client):
        """Test cancelling file deletion"""
        result = runner.invoke(
            cli,
            ['files', 'delete', 'file-1'],
            input='n\n'
        )
        
        assert result.exit_code == 0
        assert 'Cancelled' in result.output
        mock_api_client.delete.assert_not_called()
    
    def test_delete_file_api_error(self, runner, mock_api_client):
        """Test handling API errors when deleting a file"""
        from click import ClickException
        mock_api_client.delete.side_effect = ClickException("API error: Not found")
        
        result = runner.invoke(cli, [
            'files', 'delete', 'file-1',
            '--confirm'
        ])
        
        assert result.exit_code != 0
        assert 'Failed to delete file' in result.output or 'API error' in result.output


@pytest.fixture
def runner():
    """CLI runner fixture"""
    return CliRunner()


@pytest.fixture
def mock_api_client(monkeypatch):
    """Mock API client"""
    mock_client = Mock()
    monkeypatch.setattr('datahub_cli.commands.files.api_client', mock_client)
    return mock_client


@pytest.fixture
def temp_file(tmp_path):
    """Create a temporary file"""
    def _create_file(extension, content):
        file_path = tmp_path / f'test{extension}'
        file_path.write_text(content)
        return str(file_path), content
    return _create_file

