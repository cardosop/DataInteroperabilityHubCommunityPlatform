"""
End-to-end tests for complete ML training workflows.

These tests verify complete user workflows:
1. Submit training job → List jobs → Get job → Get logs → Cancel job

These tests require:
- Real API service running
- API key configured
- ODH Training Operator (may skip if not available)

No mocks or stubs - all tests use real implementations.
"""
import pytest
import json
import uuid
import time
import tempfile
from click.testing import CliRunner
from datahub_cli.main import cli
from datahub_cli.config import config


def _check_api_available():
    """Check if API service is available"""
    try:
        import requests
        response = requests.get('http://localhost:8000/health/', timeout=2)
        # Accept 200 (healthy) or 503 (unhealthy but service is running)
        # 503 means service is up but dependencies may have issues
        return response.status_code in (200, 503)
    except Exception:
        return False


@pytest.fixture(scope='module')
def api_available():
    """Check if API is available before running tests"""
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
        import os
        api_key = os.getenv('DATAHUB_API_KEY')
    if not api_key:
        pytest.skip("API key not configured. Set DATAHUB_API_KEY environment variable or use 'datahub config set api_key <key>'")
    return api_key


@pytest.fixture
def test_asset(api_available, api_key):
    """Create a test asset for ML model"""
    import requests

    headers = {
        'Authorization': f'ApiKey {api_key}',
        'Content-Type': 'application/json'
    }

    asset_data = {
        'key': f'test-ml-asset-{uuid.uuid4().hex[:8]}',
        'name': 'Test ML Asset for Training E2E',
        'description': 'Test asset for ML training E2E tests',
        'domain': 'ml',
        'visibility': 'INTERNAL'
    }

    max_retries = 3
    response = None
    for attempt in range(max_retries):
        try:
            response = requests.post(
                'http://localhost:8000/api/v1/assets/',
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

    if response and response.status_code == 201:
        asset_id = response.json().get('id')
        yield asset_id

        # Cleanup
        try:
            requests.delete(
                f'http://localhost:8000/api/v1/assets/{asset_id}/',
                headers=headers,
                timeout=10
            )
        except Exception:
            pass
    else:
        status_code = response.status_code if response else 'unknown'
        text = response.text if response else 'no response'
        pytest.skip(f"Failed to create test asset: {status_code} - {text}")


@pytest.fixture
def test_model(api_available, api_key, test_asset):
    """Create a test ML model"""
    import requests

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

    max_retries = 3
    response = None
    for attempt in range(max_retries):
        try:
            response = requests.post(
                'http://localhost:8000/api/v1/ml/models/',
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
                f'http://localhost:8000/api/v1/ml/models/{model_id}/',
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
    import requests

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
                'http://localhost:8000/api/v1/files/init/',
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
        pytest.fail(f"File initialization response missing file_id: {text}")

    if not file_id:
        text = file_init_response.text if file_init_response else 'no response'
        pytest.fail(f"File initialization response missing file_id: {text}")

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
                f'http://localhost:8000/api/v1/files/{file_id}/complete/',
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
            f'http://localhost:8000/api/v1/files/{file_id}/',
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
                'http://localhost:8000/api/v1/datasets/',
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
                f'http://localhost:8000/api/v1/datasets/{dataset_id}/',
                headers=headers,
                timeout=10
            )
        except Exception:
            pass
        try:
            requests.delete(
                f'http://localhost:8000/api/v1/files/{file_id}/',
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


class TestMLTrainingWorkflowsE2E:
    """End-to-end tests for complete ML training workflows"""

    def test_complete_training_workflow_submit_list_get_logs_cancel(
        self, runner, api_available, api_key, test_model, test_dataset
    ):
        """
        Test complete training workflow: submit → list → get → logs → cancel

        This test verifies the entire lifecycle of training job management.
        """
        config_data = {
            'epochs': 10,
            'batch_size': 32,
            'learning_rate': 0.001
        }
        config_json = json.dumps(config_data)

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

            # Verify job appears in list
            list_data = json.loads(list_result.output)
            if isinstance(list_data, list):
                job_ids = [job.get('job_id') for job in list_data]
            else:
                job_ids = [job.get('job_id') for job in list_data.get('results', [])]
            assert job_id in job_ids, f"Job {job_id} not found in list"

            # Step 3: Get training job details
            get_result = runner.invoke(cli, [
                'ml', 'training', 'get',
                job_id,
                '--format', 'json'
            ])
            assert get_result.exit_code == 0, f"Get failed: {get_result.output}"

            # Verify job details
            get_data = json.loads(get_result.output)
            assert get_data.get('job_id') == job_id, "Job ID mismatch"
            assert 'status' in get_data, "Status missing from job details"

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

        except json.JSONDecodeError as e:
            pytest.fail(f"Failed to parse JSON response: {e}\nOutput: {submit_result.output}")
        except Exception as e:
            pytest.fail(
                f"Workflow test failed: {e}\n"
                f"ODH Training Operator may not be configured properly. "
                f"Check service status: docker compose ps odh-training-operator"
            )

    def test_training_workflow_with_file_config(
        self, runner, api_available, api_key, test_model, test_dataset
    ):
        """Test training workflow using config file instead of JSON string"""
        config_data = {
            'epochs': 5,
            'batch_size': 16,
            'learning_rate': 0.0005
        }

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(config_data, f)
            config_file = f.name

        try:
            # Submit with file config
            submit_result = runner.invoke(cli, [
                'ml', 'training', 'submit',
                '--model-id', test_model,
                '--dataset-id', test_dataset,
                '--config', config_file,
                '--format', 'json'
            ])

            # May fail due to ODH, but file reading should work
            if submit_result.exit_code != 0:
                if 'ODH' in submit_result.output or 'Training Operator' in submit_result.output:
                    pytest.fail(
                        f"ODH Training Operator is not available. Error: {submit_result.output}\n"
                        f"Check service status: docker compose ps odh-training-operator"
                    )
                else:
                    # Verify it's not a file reading error
                    assert 'Failed to read config file' not in submit_result.output, \
                        f"File reading failed: {submit_result.output}"
        finally:
            import os
            os.unlink(config_file)

    def test_training_workflow_progress_tracking(
        self, runner, api_available, api_key, test_model, test_dataset
    ):
        """Test that training job progress can be tracked"""
        config_json = json.dumps({'epochs': 10, 'batch_size': 32})

        # Submit job
        submit_result = runner.invoke(cli, [
            'ml', 'training', 'submit',
            '--model-id', test_model,
            '--dataset-id', test_dataset,
            '--config', config_json,
            '--format', 'json'
        ])

        if submit_result.exit_code != 0:
            if 'ODH' in submit_result.output:
                pytest.fail(
                    f"ODH Training Operator is not available. Error: {submit_result.output}\n"
                    f"Check service status: docker compose ps odh-training-operator"
                )
            else:
                pytest.fail(f"Failed to submit: {submit_result.output}")

        try:
            submit_data = json.loads(submit_result.output)
            job_id = submit_data.get('job_id')

            if not job_id:
                pytest.skip("No job ID returned")

            # Wait a bit for job to start
            time.sleep(2)

            # Get job status multiple times to track progress
            for i in range(3):
                get_result = runner.invoke(cli, [
                    'ml', 'training', 'get',
                    job_id,
                    '--format', 'json'
                ])

                if get_result.exit_code == 0:
                    get_data = json.loads(get_result.output)
                    status = get_data.get('status')
                    progress = get_data.get('progress')

                    # Verify progress tracking works
                    assert status is not None, "Status should be present"
                    if progress is not None:
                        assert 0.0 <= progress <= 1.0, f"Progress should be between 0 and 1, got {progress}"

                time.sleep(1)

        except json.JSONDecodeError as e:
            pytest.fail(
                f"Failed to parse response: {e}\n"
                f"Response: {submit_result.output}\n"
                f"ODH Training Operator may not be configured properly."
            )
        except Exception as e:
            pytest.fail(
                f"Progress tracking test failed: {e}\n"
                f"ODH Training Operator may not be configured properly."
            )
