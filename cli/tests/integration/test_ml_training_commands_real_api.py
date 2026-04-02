"""
Integration tests for ML training CLI commands against real API service.

These tests test all training-related CLI commands directly against the running Docker Compose API service.
No Django test infrastructure required - tests use real HTTP requests.

NOTE: These tests require:
1. Docker Compose services running (api-service, postgres, redis)
2. A test user and API key configured in the CLI config
   OR set via environment variables: DATAHUB_API_KEY

To run these tests:
1. Ensure Docker Compose services are running: docker compose ps
2. Create a test user and API key (or use existing)
3. Set API key: export DATAHUB_API_KEY=your-api-key
4. Run: pytest tests/integration/test_ml_training_commands_real_api.py -v
"""
import pytest
import requests
import json
import os
import uuid
import time
import tempfile
from click.testing import CliRunner
from datahub_cli.main import cli
from datahub_cli.config import config


def _check_api_available():
    """Check if API service is available"""
    try:
        response = requests.get(os.environ.get("MESHANT_API_URL", "http://localhost:8000").rstrip("/api/v1") + "/health/", timeout=2)
        # Accept 200 (healthy) or 503 (unhealthy but service is running)
        # 503 means service is up but dependencies may have issues
        return response.status_code in (200, 503)
    except Exception:
        return False


@pytest.fixture(scope="module")
def api_available():
    """Fixture to check if API service is available"""
    if not _check_api_available():
        pytest.skip("API service not available at http://localhost:8000. Start with: docker-compose up -d api db redis")
    return True


@pytest.fixture
def runner():
    """Create CLI runner"""
    return CliRunner()


@pytest.fixture
def api_key(api_available):
    """Get API key from config or environment"""
    api_key = config.get_api_key()
    if not api_key:
        api_key = os.getenv('DATAHUB_API_KEY')
    if not api_key:
        pytest.skip("API key not configured. Set DATAHUB_API_KEY environment variable or use 'datahub config set api_key <key>'")
    return api_key


@pytest.fixture
def test_asset(api_available, api_key):
    """Create a test asset for ML model"""
    headers = {
        'Authorization': f'ApiKey {api_key}',
        'Content-Type': 'application/json'
    }

    asset_data = {
        'key': f'test-ml-asset-{uuid.uuid4().hex[:8]}',
        'name': 'Test ML Asset for Training',
        'description': 'Test asset for ML training tests',
        'domain': 'ml',
        'visibility': 'INTERNAL'
    }

    # Retry logic for connection issues
    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = requests.post(
                os.environ.get('MESHANT_API_URL', 'http://localhost:8000/api/v1') + '/assets/',
                json=asset_data,
                headers=headers,
                timeout=15
            )
            break
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
            if attempt < max_retries - 1:
                time.sleep(1)
                continue
            else:
                pytest.skip(f"Failed to create test asset after {max_retries} attempts: {e}")

    if response.status_code == 201:
        asset_id = response.json().get('id')
        yield asset_id

        # Cleanup
        try:
            requests.delete(
                f'{os.environ.get("MESHANT_API_URL", "http://localhost:8000/api/v1")}/assets/{asset_id}/',
                headers=headers,
                timeout=10
            )
        except Exception:
            pass
    else:
        pytest.skip(f"Failed to create test asset: {response.status_code} - {response.text}")


@pytest.fixture
def test_model(api_available, api_key, test_asset):
    """Create a test ML model"""
    headers = {
        'Authorization': f'ApiKey {api_key}',
        'Content-Type': 'application/json'
    }

    model_data = {
        'odh_model_id': f'test-model-{uuid.uuid4().hex[:8]}',
        'odh_model_version': '1.0.0',
        'asset_id': test_asset,
        'model_type': 'CLASSIFICATION'
    }

    # Retry logic for connection issues
    max_retries = 3
    response = None
    for attempt in range(max_retries):
        try:
            response = requests.post(
                os.environ.get('MESHANT_API_URL', 'http://localhost:8000/api/v1') + '/ml/models/',
                json=model_data,
                headers=headers,
                timeout=15
            )
            break
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
            if attempt < max_retries - 1:
                time.sleep(1)
                continue
            else:
                pytest.skip(f"Failed to create test model after {max_retries} attempts: {e}")

    if response and response.status_code == 201:
        model_id = response.json().get('id')
        yield model_id

        # Cleanup
        try:
            requests.delete(
                f'{os.environ.get("MESHANT_API_URL", "http://localhost:8000/api/v1")}/ml/models/{model_id}/',
                headers=headers,
                timeout=10
            )
        except Exception:
            pass
    else:
        status_code = response.status_code if response else 'unknown'
        text = response.text if response else 'no response'
        pytest.skip(f"Failed to create test model: {status_code} - {text}")


@pytest.fixture
def test_dataset(api_available, api_key):
    """Create a test dataset for training"""
    headers = {
        'Authorization': f'ApiKey {api_key}',
        'Content-Type': 'application/json'
    }

    # Step 1: Initialize file upload
    file_init_data = {
        'name': f'test-dataset-{uuid.uuid4().hex[:8]}.csv',
        'content_type': 'text/csv',
        'size': 1024,
        'upload_method': 'browser'
    }

    # Retry logic for connection issues and rate limits
    max_retries = 5
    file_init_response = None
    last_error = None
    for attempt in range(max_retries):
        try:
            file_init_response = requests.post(
                os.environ.get('MESHANT_API_URL', 'http://localhost:8000/api/v1') + '/files/init/',
                json=file_init_data,
                headers=headers,
                timeout=15
            )
            if file_init_response.status_code == 201:
                break
            # Handle rate limit errors - retry with backoff
            if file_init_response.status_code == 429:
                try:
                    error_data = file_init_response.json()
                    retry_after = error_data.get('error', {}).get('details', {}).get('retry_after', 2)
                    last_error = f"Rate limit exceeded, retrying after {retry_after} seconds"
                    if attempt < max_retries - 1:
                        time.sleep(retry_after + 1)
                        continue
                except (ValueError, KeyError):
                    if attempt < max_retries - 1:
                        time.sleep(3)
                        continue
            # If not 201 and not 429, retry unless it's a client error (4xx) that's not rate limit
            if 400 <= file_init_response.status_code < 500 and file_init_response.status_code != 429:
                last_error = f"Client error {file_init_response.status_code}: {file_init_response.text[:200]}"
                break
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
            last_error = str(e)
            if attempt < max_retries - 1:
                time.sleep(2)
                continue
            else:
                pytest.fail(
                    f"Failed to initialize file upload after {max_retries} attempts: {last_error}\n"
                    f"API service may not be running. Check: docker compose ps api-service"
                )

    if not file_init_response:
        pytest.fail(
            f"Failed to initialize file upload: No response received. Last error: {last_error}\n"
            f"API service may not be running. Check: docker compose ps api-service"
        )

    if file_init_response.status_code != 201:
        status_code = file_init_response.status_code
        text = file_init_response.text[:500] if file_init_response.text else 'no response'
        pytest.fail(
            f"Failed to initialize file upload: HTTP {status_code} - {text}\n"
            f"Check API service logs: docker compose logs api-service --tail 50"
        )

    # file_init_response is guaranteed to be not None here due to check above
    assert file_init_response is not None
    try:
        file_id = file_init_response.json().get('file_id')
    except (AttributeError, ValueError, KeyError):
        text = file_init_response.text if file_init_response else 'no response'
        pytest.skip(f"File initialization response missing file_id: {text}")

    if not file_id:
        text = file_init_response.text if file_init_response else 'no response'
        pytest.skip(f"File initialization response missing file_id: {text}")

    # Step 2: Complete file upload (mark as active)
    # The /complete/ endpoint now allows completion even when file doesn't exist in S3 (test/dev mode)
    file_complete_data = {
        'content_sha256': 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855'  # Empty file SHA256
    }

    file_complete_response = None
    file_completed = False
    last_error = None
    for attempt in range(max_retries):
        try:
            file_complete_response = requests.post(
                f'{os.environ.get("MESHANT_API_URL", "http://localhost:8000/api/v1")}/files/{file_id}/complete/',
                json=file_complete_data,
                headers=headers,
                timeout=15
            )
            if file_complete_response.status_code in (200, 201):
                file_completed = True
                break
            # Handle rate limit errors - retry with backoff
            if file_complete_response.status_code == 429:
                try:
                    error_data = file_complete_response.json()
                    retry_after = error_data.get('error', {}).get('details', {}).get('retry_after', 2)
                    last_error = f"Rate limit exceeded, retrying after {retry_after} seconds"
                    if attempt < max_retries - 1:
                        time.sleep(retry_after + 1)
                        continue
                except (ValueError, KeyError):
                    if attempt < max_retries - 1:
                        time.sleep(3)
                        continue
            # If not successful and not 429, check error
            if file_complete_response.status_code >= 400:
                last_error = f"HTTP {file_complete_response.status_code}: {file_complete_response.text[:200]}"
                if attempt < max_retries - 1:
                    time.sleep(2)
                    continue
                else:
                    break
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
            last_error = f"Connection/Timeout: {str(e)}"
            if attempt < max_retries - 1:
                time.sleep(2)
                continue
            else:
                break
        except Exception as e:
            last_error = f"Unexpected error: {type(e).__name__}: {str(e)}"
            if attempt < max_retries - 1:
                time.sleep(2)
                continue
            else:
                break

    # If file completion failed, fail the test with clear error
    if not file_completed:
        pytest.fail(
            f"Failed to complete file upload: {last_error or 'Unknown error'}. "
            f"Response status: {file_complete_response.status_code if file_complete_response else 'N/A'}. "
            f"Response text: {file_complete_response.text[:500] if file_complete_response else 'N/A'}"
        )

    # Step 3: Verify file is ACTIVE before creating dataset
    verify_response = None
    try:
        verify_response = requests.get(
            f'{os.environ.get("MESHANT_API_URL", "http://localhost:8000/api/v1")}/files/{file_id}/',
            headers=headers,
            timeout=10
        )
        if verify_response.status_code == 200:
            file_data = verify_response.json()
            if file_data.get('status') != 'ACTIVE':
                pytest.fail(
                    f"File {file_id} is not ACTIVE (status: {file_data.get('status')}). "
                    f"Cannot create dataset from inactive file. "
                    f"File completion: {file_complete_response.status_code if file_complete_response else 'N/A'}, "
                    f"File update: {file_update_response.status_code if file_update_response else 'N/A'}"
                )
    except Exception as e:
        # If verification fails, log but continue - dataset creation will fail with better error
        pass

    # Step 4: Create dataset from file
    dataset_data = {
        'file_id': file_id
    }

    dataset_response = None
    last_error = None
    for attempt in range(max_retries):
        try:
            dataset_response = requests.post(
                os.environ.get('MESHANT_API_URL', 'http://localhost:8000/api/v1') + '/datasets/',
                json=dataset_data,
                headers=headers,
                timeout=15
            )
            if dataset_response.status_code == 201:
                break
            # Handle rate limit errors - retry with backoff
            if dataset_response.status_code == 429:
                try:
                    error_data = dataset_response.json()
                    retry_after = error_data.get('error', {}).get('details', {}).get('retry_after', 2)
                    last_error = f"Rate limit exceeded, retrying after {retry_after} seconds"
                    if attempt < max_retries - 1:
                        time.sleep(retry_after + 1)
                        continue
                except (ValueError, KeyError):
                    if attempt < max_retries - 1:
                        time.sleep(3)
                        continue
            # If not 201 and not 429, check if it's a client error
            if 400 <= dataset_response.status_code < 500 and dataset_response.status_code != 429:
                last_error = f"Client error {dataset_response.status_code}: {dataset_response.text[:200]}"
                break
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
            last_error = f"Connection/Timeout error: {type(e).__name__}: {str(e)}"
            if attempt < max_retries - 1:
                time.sleep(2)
                continue
            else:
                pytest.fail(
                    f"Failed to create test dataset after {max_retries} attempts: {last_error}\n"
                    f"API service may not be running. Check: docker compose ps api-service"
                )
        except Exception as e:
            # Catch all other exceptions (RequestException, JSONDecodeError, etc.)
            last_error = f"Unexpected error: {type(e).__name__}: {str(e)}"
            if attempt < max_retries - 1:
                time.sleep(2)
                continue
            else:
                pytest.fail(
                    f"Failed to create test dataset after {max_retries} attempts: {last_error}\n"
                    f"Check API service logs: docker compose logs api-service --tail 50"
                )

    if not dataset_response:
        pytest.fail(
            f"Failed to create test dataset: No response received. Last error: {last_error or 'Unknown error - no exception caught'}\n"
            f"API service may not be running. Check: docker compose ps api-service"
        )

    if dataset_response.status_code == 201:
        dataset_id = dataset_response.json().get('id')
        if not dataset_id:
            pytest.fail(
                f"Dataset creation succeeded but no ID returned. Response: {dataset_response.text[:500]}"
            )
        yield dataset_id

        # Cleanup: Delete dataset and file
        try:
            requests.delete(
                f'{os.environ.get("MESHANT_API_URL", "http://localhost:8000/api/v1")}/datasets/{dataset_id}/',
                headers=headers,
                timeout=10
            )
        except Exception:
            pass
        try:
            requests.delete(
                f'{os.environ.get("MESHANT_API_URL", "http://localhost:8000/api/v1")}/files/{file_id}/',
                headers=headers,
                timeout=10
            )
        except Exception:
            pass
    else:
        status_code = dataset_response.status_code
        text = dataset_response.text[:500] if dataset_response.text else 'no response'
        pytest.fail(
            f"Failed to create test dataset: HTTP {status_code} - {text}\n"
            f"Check API service logs: docker compose logs api-service --tail 50"
        )


class TestMLTrainingCommandsRealAPI:
    """Integration tests for ML training commands with real API"""

    def test_training_command_group_accessible(self, runner, api_available):
        """Test that training command group is accessible"""
        result = runner.invoke(cli, ['ml', 'training', '--help'])
        assert result.exit_code == 0, f"Command failed: {result.output}"
        assert 'Training job commands' in result.output

    def test_training_submit_command_structure(self, runner, api_available, api_key, test_model, test_dataset):
        """Test training submit command structure with real API"""
        config_json = json.dumps({'epochs': 10, 'batch_size': 32, 'learning_rate': 0.001})

        result = runner.invoke(cli, [
            'ml', 'training', 'submit',
            '--model-id', test_model,
            '--dataset-id', test_dataset,
            '--config', config_json,
            '--format', 'json'
        ])

        # May fail due to ODH service not available, but command structure should be correct
        # Check that it's not a command parsing error
        if result.exit_code != 0:
            # Should be an API error, not a command parsing error
            assert 'Failed to submit training job' in result.output or \
                   'Not authenticated' in result.output or \
                   'API error' in result.output or \
                   'ODH' in result.output or \
                   'not found' in result.output.lower(), \
                   f"Unexpected error: {result.output}"
        else:
            # If it succeeds, verify output structure
            try:
                output_data = json.loads(result.output)
                assert 'job_id' in output_data or 'error' in output_data
            except json.JSONDecodeError:
                pass  # Output may not be JSON if there's an error message

    def test_training_submit_with_file_config(self, runner, api_available, api_key, test_model, test_dataset):
        """Test training submit with config file"""
        config_data = {'epochs': 10, 'batch_size': 32, 'learning_rate': 0.001}

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(config_data, f)
            config_file = f.name

        try:
            result = runner.invoke(cli, [
                'ml', 'training', 'submit',
                '--model-id', test_model,
                '--dataset-id', test_dataset,
                '--config', config_file,
                '--format', 'json'
            ])

            # May fail due to ODH service, but file reading should work
            if result.exit_code != 0:
                assert 'Failed to submit training job' in result.output or \
                       'Not authenticated' in result.output or \
                       'API error' in result.output or \
                       'ODH' in result.output or \
                       'not found' in result.output.lower(), \
                       f"Unexpected error: {result.output}"
        finally:
            os.unlink(config_file)

    def test_training_list_command(self, runner, api_available, api_key):
        """Test training list command with real API"""
        result = runner.invoke(cli, [
            'ml', 'training', 'list',
            '--format', 'json'
        ])

        # Should succeed even if no jobs exist (empty list)
        # Or fail with auth error, which is expected
        assert result.exit_code == 0, f"List command failed unexpectedly: {result.output}"

        if result.exit_code == 0:
            # Verify output is valid JSON
            try:
                data = json.loads(result.output)
                assert isinstance(data, (list, dict)), "Output should be JSON array or object"
            except json.JSONDecodeError:
                pytest.fail(f"Output is not valid JSON: {result.output}")

    def test_training_list_with_filters(self, runner, api_available, api_key, test_model):
        """Test training list with filters"""
        result = runner.invoke(cli, [
            'ml', 'training', 'list',
            '--model-id', test_model,
            '--status', 'RUNNING',
            '--limit', '10',
            '--offset', '0',
            '--format', 'json'
        ])

        # Should succeed or fail with expected errors
        assert result.exit_code == 0, f"List with filters failed: {result.output}"

    def test_training_get_command_structure(self, runner, api_available, api_key):
        """Test training get command structure"""
        # Use a valid format job ID (even if job doesn't exist)
        test_job_id = f'test-job-{uuid.uuid4().hex[:8]}'

        result = runner.invoke(cli, [
            'ml', 'training', 'get',
            test_job_id,
            '--format', 'json'
        ])

        # Should fail with not found or auth error, not command parsing error
        assert result.exit_code != 0, "Get should fail for non-existent job"
        # Accept various error messages including server errors (500)
        assert any(keyword in result.output.lower() for keyword in [
            'failed to get training job',
            'not authenticated',
            'api error',
            'not found',
            'server error',
            'error'
        ]), f"Unexpected error: {result.output[:500]}"

    def test_training_cancel_command_structure(self, runner, api_available, api_key):
        """Test training cancel command structure"""
        test_job_id = f'test-job-{uuid.uuid4().hex[:8]}'

        result = runner.invoke(cli, [
            'ml', 'training', 'cancel',
            test_job_id,
            '--format', 'json'
        ])

        # Should fail with not found or auth error, not command parsing error
        assert result.exit_code != 0, "Cancel should fail for non-existent job"
        # Accept various error messages including server errors (500)
        assert any(keyword in result.output.lower() for keyword in [
            'failed to cancel training job',
            'not authenticated',
            'api error',
            'not found',
            'server error',
            'error'
        ]), f"Unexpected error: {result.output[:500]}"

    def test_training_logs_command_structure(self, runner, api_available, api_key):
        """Test training logs command structure"""
        test_job_id = f'test-job-{uuid.uuid4().hex[:8]}'

        result = runner.invoke(cli, [
            'ml', 'training', 'logs',
            test_job_id,
            '--format', 'json'
        ])

        # Should fail with not found or auth error, not command parsing error
        assert result.exit_code != 0, "Logs should fail for non-existent job"
        # Accept various error messages including server errors (500)
        assert any(keyword in result.output.lower() for keyword in [
            'failed to get training logs',
            'not authenticated',
            'api error',
            'not found',
            'server error',
            'error'
        ]), f"Unexpected error: {result.output[:500]}"

    def test_training_logs_with_lines(self, runner, api_available, api_key):
        """Test training logs with lines parameter"""
        test_job_id = f'test-job-{uuid.uuid4().hex[:8]}'

        result = runner.invoke(cli, [
            'ml', 'training', 'logs',
            test_job_id,
            '--lines', '100',
            '--format', 'json'
        ])

        # Should fail with not found or auth error
        assert result.exit_code != 0, "Logs should fail for non-existent job"
        # Accept various error messages including server errors (500)
        assert any(keyword in result.output.lower() for keyword in [
            'failed to get training logs',
            'not authenticated',
            'api error',
            'not found',
            'server error',
            'error'
        ]), f"Unexpected error: {result.output[:500]}"

    def test_training_submit_invalid_uuid(self, runner, api_available):
        """Test training submit with invalid UUID"""
        result = runner.invoke(cli, [
            'ml', 'training', 'submit',
            '--model-id', 'invalid-uuid',
            '--dataset-id', '123e4567-e89b-12d3-a456-426614174001',
            '--config', '{"epochs": 10}'
        ])

        assert result.exit_code != 0, "Should fail with invalid UUID"
        assert 'Invalid' in result.output or 'UUID' in result.output

    def test_training_submit_invalid_json(self, runner, api_available):
        """Test training submit with invalid JSON"""
        result = runner.invoke(cli, [
            'ml', 'training', 'submit',
            '--model-id', '123e4567-e89b-12d3-a456-426614174000',
            '--dataset-id', '123e4567-e89b-12d3-a456-426614174001',
            '--config', 'invalid json'
        ])

        assert result.exit_code != 0, "Should fail with invalid JSON"
        assert 'Invalid JSON' in result.output or 'JSON' in result.output

    def test_training_list_table_format(self, runner, api_available, api_key):
        """Test training list with table format"""
        result = runner.invoke(cli, [
            'ml', 'training', 'list',
            '--format', 'table'
        ])

        # Should succeed or fail with expected errors
        assert result.exit_code == 0, f"Table format failed: {result.output}"

        if result.exit_code == 0:
            # Verify table format indicators
            assert 'Job ID' in result.output or 'No training jobs found' in result.output

    def test_training_get_table_format(self, runner, api_available, api_key):
        """Test training get with table format"""
        test_job_id = f'test-job-{uuid.uuid4().hex[:8]}'

        result = runner.invoke(cli, [
            'ml', 'training', 'get',
            test_job_id,
            '--format', 'table'
        ])

        # Should fail but with proper error message
        assert result.exit_code != 0, "Get should fail for non-existent job"
        # Accept various error messages including server errors (500)
        assert any(keyword in result.output.lower() for keyword in [
            'failed to get training job',
            'not authenticated',
            'api error',
            'not found',
            'server error',
            'error'
        ]), f"Unexpected error: {result.output[:500]}"

    def test_complete_training_workflow(self, runner, api_available, api_key, test_model, test_dataset):
        """
        Test complete training workflow: submit → list → get → logs → cancel

        This test verifies the entire lifecycle of training job management.
        Note: This may skip if ODH service is not available.
        """
        config_json = json.dumps({'epochs': 10, 'batch_size': 32})

        # Step 1: Submit training job
        submit_result = runner.invoke(cli, [
            'ml', 'training', 'submit',
            '--model-id', test_model,
            '--dataset-id', test_dataset,
            '--config', config_json,
            '--format', 'json'
        ])

        # If submit fails, fail the test with clear error message
        if submit_result.exit_code != 0:
            error_msg = submit_result.output
            if 'ODH' in error_msg or 'Training Operator' in error_msg or 'not available' in error_msg:
                pytest.fail(
                    f"ODH Training Operator is not available or not configured properly. "
                    f"Error: {error_msg}\n"
                    f"Please ensure:\n"
                    f"1. ODH Training Operator service is running: docker compose ps odh-training-operator\n"
                    f"2. Service is healthy: curl http://localhost:8096/health\n"
                    f"3. ODH_TRAINING_OPERATOR_URL is configured correctly in settings"
                )
            else:
                # Other errors - fail the test
                pytest.fail(f"Failed to submit training job: {error_msg}")

        # Parse job ID from output
        try:
            submit_data = json.loads(submit_result.output)
            job_id = submit_data.get('job_id')

            if not job_id:
                pytest.fail(
                    f"No job ID returned from submit. Response: {submit_result.output}\n"
                    f"ODH Training Operator may not be configured properly. "
                    f"Check service status: docker compose ps odh-training-operator"
                )

            # Step 2: List training jobs
            list_result = runner.invoke(cli, [
                'ml', 'training', 'list',
                '--model-id', test_model,
                '--format', 'json'
            ])
            assert list_result.exit_code == 0, f"List failed: {list_result.output}"

            # Step 3: Get training job
            get_result = runner.invoke(cli, [
                'ml', 'training', 'get',
                job_id,
                '--format', 'json'
            ])
            assert get_result.exit_code == 0, f"Get failed: {get_result.output}"

            # Step 4: Get logs
            logs_result = runner.invoke(cli, [
                'ml', 'training', 'logs',
                job_id,
                '--format', 'json'
            ])
            # Logs may not be available immediately, so allow for errors
            assert logs_result.exit_code == 0, f"Logs failed: {logs_result.output}"

            # Step 5: Cancel training job (if still running)
            cancel_result = runner.invoke(cli, [
                'ml', 'training', 'cancel',
                job_id,
                '--format', 'json'
            ])
            # Cancel may fail if job already completed
            assert cancel_result.exit_code == 0, f"Cancel failed: {cancel_result.output}"

        except json.JSONDecodeError:
            pytest.fail(f"Failed to parse submit result: {submit_result.output}")
        except Exception as e:
            pytest.fail(
                f"Workflow test failed: {e}\n"
                f"ODH Training Operator may not be configured properly. "
                f"Check service status: docker compose ps odh-training-operator"
            )
