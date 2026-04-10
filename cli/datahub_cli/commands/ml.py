"""
ML Model Registry management commands.
"""
import click
import json
import os
from typing import Optional
from ..api_client import api_client
from ..ml_errors import (
    ODHMLModelError,
    ODHMLModelValidationError,
    ODHMLModelNotFoundError,
    ODHMLModelConflictError,
    ODHMLModelParameterError,
    validate_uuid,
    validate_model_type,
    validate_model_status,
    validate_json,
    handle_ml_api_error,
)


@click.group()
def ml():
    """ML Model Registry management commands [Post-MVP]"""
    pass


@ml.group('models')
def models():
    """Model registry commands"""
    pass


@models.command('list')
@click.option('--asset-id', help='Filter by asset ID')
@click.option('--status', type=click.Choice(['TRAINING', 'TRAINED', 'DEPLOYED', 'FAILED', 'ARCHIVED']), help='Filter by status')
@click.option('--limit', type=int, default=20, help='Limit number of results')
@click.option('--offset', type=int, default=0, help='Offset for pagination')
@click.option('--format', 'output_format', type=click.Choice(['json', 'table']), default='table', help='Output format')
def list_models(asset_id: Optional[str], status: Optional[str], limit: int, offset: int, output_format: str):
    """List ML models"""
    from typing import Dict, Any
    params: Dict[str, Any] = {'limit': limit, 'offset': offset}
    if status:
        params['status'] = status
    if asset_id:
        # Validate UUID format
        try:
            validate_uuid(asset_id, 'asset-id')
        except ODHMLModelParameterError as e:
            raise click.ClickException(str(e))
        params['asset_id'] = asset_id

    try:
        # API endpoint: /api/v1/ml/models/
        data = api_client.get('ml/models/', params=params)
        # Handle both paginated response (dict with 'results') and direct list response
        if isinstance(data, dict):
            results = data.get('results', [])
        elif isinstance(data, list):
            results = data
        else:
            results = []

        if output_format == 'json':
            click.echo(json.dumps(results, indent=2))
        else:
            if not results:
                click.echo("No models found.")
                return

            # Table format
            click.echo(f"{'ID':<40} {'Name':<30} {'Version':<15} {'Type':<20} {'Status':<15} {'Asset ID':<40}")
            click.echo("-" * 170)
            for model in results:
                model_id = str(model.get('id', ''))[:36]
                name = str(model.get('odh_model_name', ''))[:28]
                version = str(model.get('odh_model_version', ''))[:13]
                model_type = str(model.get('model_type', ''))[:18]
                model_status = str(model.get('status', ''))[:13]
                asset_id_display = str(model.get('asset_id', ''))[:36] if model.get('asset_id') else 'N/A'
                click.echo(
                    f"{model_id:<40} "
                    f"{name:<30} "
                    f"{version:<15} "
                    f"{model_type:<20} "
                    f"{model_status:<15} "
                    f"{asset_id_display:<40}"
                )
    except click.ClickException:
        raise
    except Exception as e:
        # Try to handle as ML API error if it's a requests exception
        try:
            import requests
            if isinstance(e, requests.exceptions.HTTPError) and hasattr(e, 'response'):
                response = e.response
                if hasattr(response, 'text') and hasattr(response, 'status_code'):
                    raise handle_ml_api_error(response.text, response.status_code, 'ml/models/')
        except (ImportError, AttributeError):
            pass
        raise click.ClickException(f"Failed to list models: {e}")


@models.command('get')
@click.argument('model_id')
@click.option('--format', 'output_format', type=click.Choice(['json', 'table']), default='table', help='Output format')
def get_model(model_id: str, output_format: str):
    """Get model details"""
    # Validate UUID format
    try:
        validate_uuid(model_id, 'model-id')
    except ODHMLModelParameterError as e:
        raise click.ClickException(str(e))

    try:
        # API endpoint: /api/v1/ml/models/{id}/
        data = api_client.get(f'ml/models/{model_id}/')

        if output_format == 'json':
            click.echo(json.dumps(data, indent=2))
        else:
            # Table format
            click.echo(f"ID: {data.get('id')}")
            click.echo(f"ODH Model ID: {data.get('odh_model_id')}")
            click.echo(f"ODH Model Name: {data.get('odh_model_name')}")
            click.echo(f"ODH Model Version: {data.get('odh_model_version')}")
            click.echo(f"Model Type: {data.get('model_type')}")
            click.echo(f"Status: {data.get('status')}")
            click.echo(f"Asset ID: {data.get('asset_id') or 'N/A'}")
            click.echo(f"Contract ID: {data.get('contract_id') or 'N/A'}")
            if data.get('training_dataset_id'):
                click.echo(f"Training Dataset ID: {data.get('training_dataset_id')}")
            if data.get('training_job_id'):
                click.echo(f"Training Job ID: {data.get('training_job_id')}")
            click.echo(f"Created: {data.get('created_at')}")
            click.echo(f"Updated: {data.get('updated_at')}")
    except click.ClickException:
        raise
    except Exception as e:
        # Try to handle as ML API error if it's a requests exception
        try:
            import requests
            if isinstance(e, requests.exceptions.HTTPError) and hasattr(e, 'response'):
                response = e.response
                if hasattr(response, 'text') and hasattr(response, 'status_code'):
                    raise handle_ml_api_error(response.text, response.status_code, f'ml/models/{model_id}/')
        except (ImportError, AttributeError):
            pass
        raise click.ClickException(f"Failed to get model: {e}")


@models.command('create')
@click.option('--odh-model-id', required=True, help='ODH Model Registry model ID')
@click.option('--odh-model-name', required=True, help='ODH Model Registry model name')
@click.option('--odh-model-version', required=True, help='ODH Model Registry model version')
@click.option('--asset-id', help='Hub asset ID to link (optional)')
@click.option('--contract-id', help='Hub contract ID to link (optional)')
@click.option('--model-type', type=click.Choice([
    'CLASSIFICATION', 'REGRESSION', 'CLUSTERING', 'NLP',
    'COMPUTER_VISION', 'RECOMMENDATION', 'TIME_SERIES',
    'ANOMALY_DETECTION', 'OTHER'
]), required=True, help='Type of ML model')
@click.option('--format', 'output_format', type=click.Choice(['json', 'table']), default='table', help='Output format')
def create_model(
    odh_model_id: str,
    odh_model_name: str,
    odh_model_version: str,
    asset_id: Optional[str],
    contract_id: Optional[str],
    model_type: str,
    output_format: str
):
    """Create a new ML model link"""
    # Validate parameters
    try:
        validate_model_type(model_type)
        if asset_id:
            validate_uuid(asset_id, 'asset-id')
        if contract_id:
            validate_uuid(contract_id, 'contract-id')
    except ODHMLModelParameterError as e:
        raise click.ClickException(str(e))

    # Build request data
    # Note: odh_model_name is not sent to API - service fetches it from ODH
    # We validate it here for user convenience/documentation
    data = {
        'odh_model_id': odh_model_id,
        'odh_model_version': odh_model_version,
        'model_type': model_type
    }
    if asset_id:
        data['asset_id'] = asset_id
    if contract_id:
        data['contract_id'] = contract_id

    try:
        # API endpoint: /api/v1/ml/models/
        result = api_client.post('ml/models/', json_data=data)

        if output_format == 'json':
            click.echo(json.dumps(result, indent=2))
        else:
            click.echo("Model created successfully!")
            click.echo(f"ID: {result.get('id')}")
            click.echo(f"ODH Model ID: {result.get('odh_model_id')}")
            click.echo(f"ODH Model Name: {result.get('odh_model_name')}")
            click.echo(f"ODH Model Version: {result.get('odh_model_version')}")
            click.echo(f"Model Type: {result.get('model_type')}")
            click.echo(f"Status: {result.get('status')}")
            if result.get('asset_id'):
                click.echo(f"Asset ID: {result.get('asset_id')}")
            if result.get('contract_id'):
                click.echo(f"Contract ID: {result.get('contract_id')}")
    except click.ClickException:
        raise
    except Exception as e:
        # Try to handle as ML API error if it's a requests exception
        try:
            import requests
            if isinstance(e, requests.exceptions.HTTPError) and hasattr(e, 'response'):
                response = e.response
                if hasattr(response, 'text') and hasattr(response, 'status_code'):
                    raise handle_ml_api_error(response.text, response.status_code, 'ml/models/')
        except (ImportError, AttributeError):
            pass
        raise click.ClickException(f"Failed to create model: {e}")


@models.command('update')
@click.argument('model_id')
@click.option('--asset-id', help='Hub asset ID to link (optional)')
@click.option('--contract-id', help='Hub contract ID to link (optional)')
@click.option('--status', type=click.Choice(['TRAINING', 'TRAINED', 'DEPLOYED', 'FAILED', 'ARCHIVED']), help='Model status (optional)')
@click.option('--format', 'output_format', type=click.Choice(['json', 'table']), default='table', help='Output format')
def update_model(
    model_id: str,
    asset_id: Optional[str],
    contract_id: Optional[str],
    status: Optional[str],
    output_format: str
):
    """Update ML model"""
    # Validate parameters
    try:
        validate_uuid(model_id, 'model-id')
        if asset_id:
            validate_uuid(asset_id, 'asset-id')
        if contract_id:
            validate_uuid(contract_id, 'contract-id')
        if status:
            validate_model_status(status)
    except ODHMLModelParameterError as e:
        raise click.ClickException(str(e))

    # Build request data
    data = {}
    if asset_id:
        data['asset_id'] = asset_id
    if contract_id:
        data['contract_id'] = contract_id
    if status:
        data['status'] = status

    if not data:
        raise click.ClickException("At least one field must be provided for update (--asset-id, --contract-id, or --status)")

    try:
        # API endpoint: /api/v1/ml/models/{id}/
        result = api_client.patch(f'ml/models/{model_id}/', json_data=data)

        if output_format == 'json':
            click.echo(json.dumps(result, indent=2))
        else:
            click.echo("Model updated successfully!")
            click.echo(f"ID: {result.get('id')}")
            click.echo(f"ODH Model Name: {result.get('odh_model_name')}")
            click.echo(f"ODH Model Version: {result.get('odh_model_version')}")
            click.echo(f"Model Type: {result.get('model_type')}")
            click.echo(f"Status: {result.get('status')}")
            if result.get('asset_id'):
                click.echo(f"Asset ID: {result.get('asset_id')}")
            if result.get('contract_id'):
                click.echo(f"Contract ID: {result.get('contract_id')}")
    except click.ClickException:
        raise
    except Exception as e:
        # Try to handle as ML API error if it's a requests exception
        try:
            import requests
            if isinstance(e, requests.exceptions.HTTPError) and hasattr(e, 'response'):
                response = e.response
                if hasattr(response, 'text') and hasattr(response, 'status_code'):
                    raise handle_ml_api_error(response.text, response.status_code, f'ml/models/{model_id}/')
        except (ImportError, AttributeError):
            pass
        raise click.ClickException(f"Failed to update model: {e}")


@models.command('delete')
@click.argument('model_id')
@click.option('--format', 'output_format', type=click.Choice(['json', 'table']), default='table', help='Output format')
def delete_model(model_id: str, output_format: str):
    """Delete ML model"""
    # Validate UUID format
    try:
        validate_uuid(model_id, 'model-id')
    except ODHMLModelParameterError as e:
        raise click.ClickException(str(e))

    try:
        # API endpoint: /api/v1/ml/models/{id}/
        result = api_client.delete(f'ml/models/{model_id}/')

        if output_format == 'json':
            click.echo(json.dumps(result if result else {}, indent=2))
        else:
            click.echo("Model deleted successfully!")
    except click.ClickException:
        raise
    except Exception as e:
        # Try to handle as ML API error if it's a requests exception
        try:
            import requests
            if isinstance(e, requests.exceptions.HTTPError) and hasattr(e, 'response'):
                response = e.response
                if hasattr(response, 'text') and hasattr(response, 'status_code'):
                    raise handle_ml_api_error(response.text, response.status_code, f'ml/models/{model_id}/')
        except (ImportError, AttributeError):
            pass
        raise click.ClickException(f"Failed to delete model: {e}")


@models.command('versions')
@click.argument('model_id')
@click.option('--format', 'output_format', type=click.Choice(['json', 'table']), default='table', help='Output format')
def list_model_versions(model_id: str, output_format: str):
    """List all versions of a model"""
    # Validate UUID format
    try:
        validate_uuid(model_id, 'model-id')
    except ODHMLModelParameterError as e:
        raise click.ClickException(str(e))

    try:
        # First get the model to find its ODH model ID
        model = api_client.get(f'ml/models/{model_id}/')
        odh_model_id = model.get('odh_model_id')

        if not odh_model_id:
            raise click.ClickException("Model does not have an ODH model ID")

        # Search for all models with the same ODH model ID
        # API endpoint: /api/v1/ml/models/ with search parameter
        params = {'search': odh_model_id}
        data = api_client.get('ml/models/', params=params)

        # Filter results to only include models with matching ODH model ID
        if isinstance(data, dict):
            results = data.get('results', [])
        elif isinstance(data, list):
            results = data
        else:
            results = []

        # Filter to exact ODH model ID match
        versions = [m for m in results if m.get('odh_model_id') == odh_model_id]

        if output_format == 'json':
            click.echo(json.dumps(versions, indent=2))
        else:
            if not versions:
                click.echo(f"No versions found for model {odh_model_id}.")
                return

            click.echo(f"Versions for ODH Model ID: {odh_model_id}")
            click.echo(f"{'ID':<40} {'Version':<20} {'Status':<15} {'Created':<25}")
            click.echo("-" * 100)
            for version in versions:
                version_id = str(version.get('id', ''))[:36]
                version_str = str(version.get('odh_model_version', ''))[:18]
                status_str = str(version.get('status', ''))[:13]
                created = str(version.get('created_at', ''))[:23]
                click.echo(
                    f"{version_id:<40} "
                    f"{version_str:<20} "
                    f"{status_str:<15} "
                    f"{created:<25}"
                )
    except click.ClickException:
        raise
    except Exception as e:
        # Try to handle as ML API error if it's a requests exception
        try:
            import requests
            if isinstance(e, requests.exceptions.HTTPError) and hasattr(e, 'response'):
                response = e.response
                if hasattr(response, 'text') and hasattr(response, 'status_code'):
                    raise handle_ml_api_error(response.text, response.status_code, f'ml/models/{model_id}/')
        except (ImportError, AttributeError):
            pass
        raise click.ClickException(f"Failed to list model versions: {e}")


@ml.group('inference')
def inference():
    """Inference deployment and prediction commands"""
    pass


@inference.command('deploy')
@click.option('--model-id', required=True, help='ML model ID to deploy')
@click.option('--config', help='Deployment configuration (JSON string or file path)')
@click.option('--format', 'output_format', type=click.Choice(['json', 'table']), default='table', help='Output format')
def deploy_model(model_id: str, config: Optional[str], output_format: str):
    """Deploy a model for inference"""
    # Validate parameters
    try:
        validate_uuid(model_id, 'model-id')
    except ODHMLModelParameterError as e:
        raise click.ClickException(str(e))

    # Parse config
    config_data = {}
    if config:
        # Check if config is a file path
        if os.path.exists(config):
            try:
                with open(config, 'r', encoding='utf-8') as f:
                    config_data = json.load(f)
            except Exception as e:
                raise click.ClickException(f"Failed to read config file: {e}")
        else:
            # Try to parse as JSON string
            try:
                config_data = validate_json(config, 'config')
            except ODHMLModelParameterError as e:
                raise click.ClickException(str(e))

    # Build request data
    from typing import Dict, Any
    data: Dict[str, Any] = {'model_id': model_id}
    if config_data:
        data['config'] = config_data

    try:
        # API endpoint: /api/v1/ml/inference/deployments/
        result = api_client.post('ml/inference/deployments/', json_data=data)

        if output_format == 'json':
            click.echo(json.dumps(result, indent=2))
        else:
            click.echo("Model deployed successfully!")
            click.echo(f"Deployment ID: {result.get('deployment_id')}")
            click.echo(f"Model ID: {result.get('model_id')}")
            click.echo(f"Status: {result.get('status')}")
            if result.get('replicas'):
                click.echo(f"Replicas: {result.get('replicas')}")
            if result.get('endpoint'):
                click.echo(f"Endpoint: {result.get('endpoint')}")
    except (ODHMLModelError, click.ClickException):
        raise
    except Exception as e:
        # Error should already be handled by api_client._handle_response
        # But if it's not, provide a user-friendly message
        error_msg = str(e)
        if 'Not authenticated' in error_msg or 'Authentication' in error_msg:
            raise click.ClickException(error_msg)
        raise click.ClickException(f"Failed to deploy model: {error_msg}")


@inference.command('predict')
@click.option('--deployment-id', required=True, help='Deployment ID')
@click.option('--input-data', 'input_data', required=True, help='Input data (JSON string or file path)')
@click.option('--format', 'output_format', type=click.Choice(['json', 'table']), default='table', help='Output format')
def predict(deployment_id: str, input_data: str, output_format: str):
    """Run inference prediction on a deployed model"""
    # Parse input data
    if os.path.exists(input_data):
        # Input is a file path
        try:
            with open(input_data, 'r', encoding='utf-8') as f:
                input_json = json.load(f)
        except Exception as e:
            raise click.ClickException(f"Failed to read input file: {e}")
    else:
        # Try to parse as JSON string
        try:
            input_json = validate_json(input_data, 'input')
        except ODHMLModelParameterError as e:
            raise click.ClickException(str(e))

    # Build request data
    data = {
        'deployment_id': deployment_id,
        'input': input_json
    }

    try:
        # API endpoint: /api/v1/ml/inference/deployments/predict/
        result = api_client.post('ml/inference/deployments/predict/', json_data=data)

        if output_format == 'json':
            click.echo(json.dumps(result, indent=2))
        else:
            click.echo("Prediction completed successfully!")
            click.echo(f"Deployment ID: {result.get('deployment_id')}")
            click.echo(f"Status: {result.get('status')}")
            output = result.get('output', {})
            if output:
                click.echo("\nOutput:")
                click.echo(json.dumps(output, indent=2))
    except (ODHMLModelError, click.ClickException):
        raise
    except Exception as e:
        # Error should already be handled by api_client._handle_response
        # But if it's not, provide a user-friendly message
        error_msg = str(e)
        if 'Not authenticated' in error_msg or 'Authentication' in error_msg:
            raise click.ClickException(error_msg)
        raise click.ClickException(f"Failed to run prediction: {error_msg}")


@inference.command('list')
@click.option('--model-id', help='Filter by model ID')
@click.option('--status', help='Filter by deployment status')
@click.option('--limit', type=int, default=20, help='Limit number of results')
@click.option('--offset', type=int, default=0, help='Offset for pagination')
@click.option('--format', 'output_format', type=click.Choice(['json', 'table']), default='table', help='Output format')
def list_deployments(model_id: Optional[str], status: Optional[str], limit: int, offset: int, output_format: str):
    """List inference deployments"""
    from typing import Dict, Any
    params: Dict[str, Any] = {'limit': limit, 'offset': offset}
    if status:
        params['status'] = status
    if model_id:
        # Validate UUID format
        try:
            validate_uuid(model_id, 'model-id')
        except ODHMLModelParameterError as e:
            raise click.ClickException(str(e))
        params['model_id'] = model_id

    try:
        # API endpoint: /api/v1/ml/inference/deployments/
        data = api_client.get('ml/inference/deployments/', params=params)
        # Handle both paginated response (dict with 'results') and direct list response
        if isinstance(data, dict):
            results = data.get('results', [])
        elif isinstance(data, list):
            results = data
        else:
            results = []

        if output_format == 'json':
            click.echo(json.dumps(results, indent=2))
        else:
            if not results:
                click.echo("No deployments found.")
                return

            # Table format
            click.echo(f"{'Deployment ID':<40} {'Model ID':<40} {'Status':<20} {'Replicas':<10} {'Endpoint':<50}")
            click.echo("-" * 160)
            for deployment in results:
                deployment_id = str(deployment.get('deployment_id', ''))[:38]
                model_id_display = str(deployment.get('model_id', ''))[:38]
                status_str = str(deployment.get('status', ''))[:18]
                replicas = str(deployment.get('replicas', 0))[:8]
                endpoint = str(deployment.get('endpoint', ''))[:48] if deployment.get('endpoint') else 'N/A'
                click.echo(
                    f"{deployment_id:<40} "
                    f"{model_id_display:<40} "
                    f"{status_str:<20} "
                    f"{replicas:<10} "
                    f"{endpoint:<50}"
                )
    except (ODHMLModelError, click.ClickException):
        raise
    except Exception as e:
        # Error should already be handled by api_client._handle_response
        # But if it's not, provide a user-friendly message
        error_msg = str(e)
        if 'Not authenticated' in error_msg or 'Authentication' in error_msg:
            raise click.ClickException(error_msg)
        raise click.ClickException(f"Failed to list deployments: {error_msg}")


@inference.command('get')
@click.argument('deployment_id')
@click.option('--format', 'output_format', type=click.Choice(['json', 'table']), default='table', help='Output format')
def get_deployment(deployment_id: str, output_format: str):
    """Get deployment details"""
    try:
        # API endpoint: /api/v1/ml/inference/deployments/{id}/
        data = api_client.get(f'ml/inference/deployments/{deployment_id}/')

        if output_format == 'json':
            click.echo(json.dumps(data, indent=2))
        else:
            # Table format
            click.echo(f"Deployment ID: {data.get('deployment_id')}")
            click.echo(f"Model ID: {data.get('model_id')}")
            click.echo(f"Status: {data.get('status')}")
            if data.get('replicas') is not None:
                click.echo(f"Replicas: {data.get('replicas')}")
            if data.get('endpoint'):
                click.echo(f"Endpoint: {data.get('endpoint')}")
            if data.get('created_at'):
                click.echo(f"Created: {data.get('created_at')}")
            if data.get('updated_at'):
                click.echo(f"Updated: {data.get('updated_at')}")
    except (ODHMLModelError, click.ClickException):
        raise
    except Exception as e:
        # Error should already be handled by api_client._handle_response
        # But if it's not, provide a user-friendly message
        error_msg = str(e)
        if 'Not authenticated' in error_msg or 'Authentication' in error_msg:
            raise click.ClickException(error_msg)
        raise click.ClickException(f"Failed to get deployment: {error_msg}")


@inference.command('undeploy')
@click.argument('deployment_id')
@click.option('--format', 'output_format', type=click.Choice(['json', 'table']), default='table', help='Output format')
def undeploy(deployment_id: str, output_format: str):
    """Undeploy a model"""
    try:
        # API endpoint: /api/v1/ml/inference/deployments/{id}/
        result = api_client.delete(f'ml/inference/deployments/{deployment_id}/')

        if output_format == 'json':
            click.echo(json.dumps(result if result else {}, indent=2))
        else:
            click.echo("Deployment undeployed successfully!")
    except (ODHMLModelError, click.ClickException):
        raise
    except Exception as e:
        # Error should already be handled by api_client._handle_response
        # But if it's not, provide a user-friendly message
        error_msg = str(e)
        if 'Not authenticated' in error_msg or 'Authentication' in error_msg:
            raise click.ClickException(error_msg)
        raise click.ClickException(f"Failed to undeploy deployment: {error_msg}")


@inference.command('metrics')
@click.argument('deployment_id')
@click.option('--start-time', help='Start time for metrics (ISO 8601 format)')
@click.option('--end-time', help='End time for metrics (ISO 8601 format)')
@click.option('--format', 'output_format', type=click.Choice(['json', 'table']), default='table', help='Output format')
def get_metrics(deployment_id: str, start_time: Optional[str], end_time: Optional[str], output_format: str):
    """Get inference metrics for a deployment"""
    from typing import Dict, Any
    params: Dict[str, Any] = {}
    if start_time:
        params['start_time'] = start_time
    if end_time:
        params['end_time'] = end_time

    try:
        # API endpoint: /api/v1/ml/inference/deployments/{id}/metrics/
        data = api_client.get(f'ml/inference/deployments/{deployment_id}/metrics/', params=params)

        if output_format == 'json':
            click.echo(json.dumps(data, indent=2))
        else:
            # Table format
            click.echo(f"Metrics for Deployment: {deployment_id}")
            click.echo(f"Total Requests: {data.get('total_requests', 0)}")
            click.echo(f"Successful Requests: {data.get('successful_requests', 0)}")
            click.echo(f"Failed Requests: {data.get('failed_requests', 0)}")
            if data.get('error_rate') is not None:
                click.echo(f"Error Rate: {data.get('error_rate'):.2f}%")
            if data.get('latency_ms') is not None:
                click.echo(f"Average Latency: {data.get('latency_ms'):.2f} ms")
            if data.get('accuracy') is not None:
                click.echo(f"Accuracy: {data.get('accuracy'):.2f}")
            if data.get('metrics'):
                click.echo("\nAdditional Metrics:")
                click.echo(json.dumps(data.get('metrics'), indent=2))
    except (ODHMLModelError, click.ClickException):
        raise
    except Exception as e:
        # Error should already be handled by api_client._handle_response
        # But if it's not, provide a user-friendly message
        error_msg = str(e)
        if 'Not authenticated' in error_msg or 'Authentication' in error_msg:
            raise click.ClickException(error_msg)
        raise click.ClickException(f"Failed to get metrics: {error_msg}")


@ml.group('training')
def training():
    """Training job commands"""
    pass


@training.command('submit')
@click.option('--model-id', required=True, help='ML model ID')
@click.option('--dataset-id', required=True, help='Training dataset ID')
@click.option('--config', required=True, help='Training configuration (JSON string or file path)')
@click.option('--format', 'output_format', type=click.Choice(['json', 'table']), default='table', help='Output format')
def submit_training(model_id: str, dataset_id: str, config: str, output_format: str):
    """Submit a training job"""
    import os

    # Validate UUIDs
    try:
        validate_uuid(model_id, 'model-id')
        validate_uuid(dataset_id, 'dataset-id')
    except ODHMLModelParameterError as e:
        raise click.ClickException(str(e))

    # Parse config - can be JSON string or file path
    training_config = None
    if os.path.exists(config):
        # Read from file
        try:
            with open(config, 'r') as f:
                import json
                training_config = json.load(f)
        except Exception as e:
            raise click.ClickException(f"Failed to read config file: {e}")
    else:
        # Try to parse as JSON string
        try:
            import json
            training_config = json.loads(config)
        except json.JSONDecodeError:
            raise click.ClickException(f"Invalid JSON in config: {config}")

    # Validate config is a dict
    if not isinstance(training_config, dict):
        raise click.ClickException("Config must be a JSON object")

    try:
        # API endpoint: /api/v1/ml/training/jobs/
        data = {
            'model_id': model_id,
            'dataset_id': dataset_id,
            'config': training_config
        }
        result = api_client.post('ml/training/jobs/', json_data=data)

        if output_format == 'json':
            click.echo(json.dumps(result, indent=2))
        else:
            click.echo("Training job submitted successfully!")
            click.echo(f"Job ID: {result.get('job_id')}")
            click.echo(f"Hub Job ID: {result.get('hub_job_id')}")
            click.echo(f"Status: {result.get('status')}")
            click.echo(f"Model ID: {result.get('model_id')}")
            click.echo(f"Dataset ID: {result.get('dataset_id')}")
            click.echo(f"Submitted At: {result.get('submitted_at')}")
    except click.ClickException:
        raise
    except Exception as e:
        # Try to handle as ML API error if it's a requests exception
        try:
            import requests
            if isinstance(e, requests.exceptions.HTTPError) and hasattr(e, 'response'):
                response = e.response
                if hasattr(response, 'text') and hasattr(response, 'status_code'):
                    raise handle_ml_api_error(response.text, response.status_code, 'ml/training/jobs/')
        except (ImportError, AttributeError):
            pass
        raise click.ClickException(f"Failed to submit training job: {e}")


@training.command('list')
@click.option('--model-id', help='Filter by model ID')
@click.option('--status', help='Filter by status')
@click.option('--limit', type=int, default=20, help='Limit number of results')
@click.option('--offset', type=int, default=0, help='Offset for pagination')
@click.option('--format', 'output_format', type=click.Choice(['json', 'table']), default='table', help='Output format')
def list_training_jobs(model_id: Optional[str], status: Optional[str], limit: int, offset: int, output_format: str):
    """List training jobs"""
    from typing import Dict, Any
    params: Dict[str, Any] = {'limit': limit, 'offset': offset}

    if model_id:
        try:
            validate_uuid(model_id, 'model-id')
        except ODHMLModelParameterError as e:
            raise click.ClickException(str(e))
        params['model_id'] = model_id

    if status:
        params['status'] = status

    try:
        # API endpoint: /api/v1/ml/training/jobs/
        data = api_client.get('ml/training/jobs/', params=params)

        # Handle paginated response
        if isinstance(data, dict):
            results = data.get('results', [])
        elif isinstance(data, list):
            results = data
        else:
            results = []

        if output_format == 'json':
            click.echo(json.dumps(results, indent=2))
        else:
            if not results:
                click.echo("No training jobs found.")
                return

            # Table format
            click.echo(f"{'Job ID':<40} {'Model ID':<40} {'Status':<15} {'Progress':<10} {'Submitted At':<25}")
            click.echo("-" * 130)
            for job in results:
                job_id = str(job.get('job_id', ''))[:36]
                model_id_display = str(job.get('model_id', ''))[:36]
                job_status = str(job.get('status', ''))[:13]
                progress = f"{job.get('progress', 0.0):.1%}" if job.get('progress') is not None else 'N/A'
                submitted_at = str(job.get('submitted_at', ''))[:23] if job.get('submitted_at') else 'N/A'
                click.echo(
                    f"{job_id:<40} "
                    f"{model_id_display:<40} "
                    f"{job_status:<15} "
                    f"{progress:<10} "
                    f"{submitted_at:<25}"
                )
    except click.ClickException:
        raise
    except Exception as e:
        # Try to handle as ML API error if it's a requests exception
        try:
            import requests
            if isinstance(e, requests.exceptions.HTTPError) and hasattr(e, 'response'):
                response = e.response
                if hasattr(response, 'text') and hasattr(response, 'status_code'):
                    raise handle_ml_api_error(response.text, response.status_code, 'ml/training/jobs/')
        except (ImportError, AttributeError):
            pass
        raise click.ClickException(f"Failed to list training jobs: {e}")


@training.command('get')
@click.argument('job_id')
@click.option('--format', 'output_format', type=click.Choice(['json', 'table']), default='table', help='Output format')
def get_training_job(job_id: str, output_format: str):
    """Get training job details"""
    try:
        # API endpoint: /api/v1/ml/training/jobs/{id}/
        data = api_client.get(f'ml/training/jobs/{job_id}/')

        if output_format == 'json':
            click.echo(json.dumps(data, indent=2))
        else:
            # Table format with progress
            click.echo(f"Job ID: {data.get('job_id')}")
            click.echo(f"Hub Job ID: {data.get('hub_job_id') or 'N/A'}")
            click.echo(f"Model ID: {data.get('model_id')}")
            click.echo(f"Dataset ID: {data.get('dataset_id') or 'N/A'}")
            click.echo(f"Status: {data.get('status')}")
            progress = data.get('progress')
            if progress is not None:
                click.echo(f"Progress: {progress:.1%}")
            else:
                click.echo("Progress: N/A")
            click.echo(f"Submitted At: {data.get('submitted_at') or 'N/A'}")
            if data.get('started_at'):
                click.echo(f"Started At: {data.get('started_at')}")
            if data.get('completed_at'):
                click.echo(f"Completed At: {data.get('completed_at')}")
            if data.get('metrics'):
                click.echo(f"Metrics: {json.dumps(data.get('metrics'), indent=2)}")
            if data.get('logs_url'):
                click.echo(f"Logs URL: {data.get('logs_url')}")
            if data.get('error'):
                click.echo(f"Error: {data.get('error')}")
    except click.ClickException:
        raise
    except Exception as e:
        # Try to handle as ML API error if it's a requests exception
        try:
            import requests
            if isinstance(e, requests.exceptions.HTTPError) and hasattr(e, 'response'):
                response = e.response
                if hasattr(response, 'text') and hasattr(response, 'status_code'):
                    raise handle_ml_api_error(response.text, response.status_code, f'ml/training/jobs/{job_id}/')
        except (ImportError, AttributeError):
            pass
        raise click.ClickException(f"Failed to get training job: {e}")


@training.command('cancel')
@click.argument('job_id')
@click.option('--format', 'output_format', type=click.Choice(['json', 'table']), default='table', help='Output format')
def cancel_training_job(job_id: str, output_format: str):
    """Cancel a training job"""
    try:
        # API endpoint: /api/v1/ml/training/jobs/{id}/cancel/
        result = api_client.post(f'ml/training/jobs/{job_id}/cancel/')

        if output_format == 'json':
            click.echo(json.dumps(result, indent=2))
        else:
            click.echo("Training job cancelled successfully!")
            if result.get('detail'):
                click.echo(result.get('detail'))
    except click.ClickException:
        raise
    except Exception as e:
        # Try to handle as ML API error if it's a requests exception
        try:
            import requests
            if isinstance(e, requests.exceptions.HTTPError) and hasattr(e, 'response'):
                response = e.response
                if hasattr(response, 'text') and hasattr(response, 'status_code'):
                    raise handle_ml_api_error(response.text, response.status_code, f'ml/training/jobs/{job_id}/cancel/')
        except (ImportError, AttributeError):
            pass
        raise click.ClickException(f"Failed to cancel training job: {e}")


@training.command('logs')
@click.argument('job_id')
@click.option('--lines', type=int, help='Number of log lines to retrieve')
@click.option('--format', 'output_format', type=click.Choice(['json', 'table']), default='table', help='Output format')
def get_training_logs(job_id: str, lines: Optional[int], output_format: str):
    """Get training job logs"""
    params = {}
    if lines:
        params['lines'] = lines

    try:
        # API endpoint: /api/v1/ml/training/jobs/{id}/logs/
        data = api_client.get(f'ml/training/jobs/{job_id}/logs/', params=params)

        if output_format == 'json':
            click.echo(json.dumps(data, indent=2))
        else:
            # Display logs
            logs = data.get('logs', [])
            if not logs:
                click.echo("No logs available.")
                return

            for log_entry in logs:
                if isinstance(log_entry, dict):
                    timestamp = log_entry.get('timestamp', '')
                    level = log_entry.get('level', '')
                    message = log_entry.get('message', '')
                    click.echo(f"[{timestamp}] [{level}] {message}")
                else:
                    click.echo(str(log_entry))
    except click.ClickException:
        raise
    except Exception as e:
        # Try to handle as ML API error if it's a requests exception
        try:
            import requests
            if isinstance(e, requests.exceptions.HTTPError) and hasattr(e, 'response'):
                response = e.response
                if hasattr(response, 'text') and hasattr(response, 'status_code'):
                    raise handle_ml_api_error(response.text, response.status_code, f'ml/training/jobs/{job_id}/logs/')
        except (ImportError, AttributeError):
            pass
        raise click.ClickException(f"Failed to get training logs: {e}")


@ml.group('serving')
def serving():
    """Model serving commands for deploying models as API endpoints"""
    pass


@serving.command('deploy')
@click.option('--model-id', required=True, help='ML model ID to deploy for serving')
@click.option('--endpoint', help='Custom endpoint path (optional)')
@click.option('--format', 'output_format', type=click.Choice(['json', 'table']), default='table', help='Output format')
def deploy_model_serving(model_id: str, endpoint: Optional[str], output_format: str):
    """Deploy a model for serving as an API endpoint"""
    # Validate parameters
    try:
        validate_uuid(model_id, 'model-id')
    except ODHMLModelParameterError as e:
        raise click.ClickException(str(e))

    # Build request data
    from typing import Dict, Any
    data: Dict[str, Any] = {'model_id': model_id}
    if endpoint:
        data['endpoint'] = endpoint

    try:
        # API endpoint: /api/v1/ml/inference/deployments/
        result = api_client.post('ml/inference/deployments/', json_data=data)

        if output_format == 'json':
            click.echo(json.dumps(result, indent=2))
        else:
            click.echo("Model deployed for serving successfully!")
            click.echo(f"Serving ID: {result.get('serving_id')}")
            click.echo(f"Model ID: {result.get('model_id')}")
            click.echo(f"Status: {result.get('status')}")
            if result.get('endpoint'):
                click.echo(f"Endpoint URL: {result.get('endpoint')}")
    except click.ClickException:
        raise
    except Exception as e:
        # Try to handle as ML API error if it's a requests exception
        try:
            import requests
            if isinstance(e, requests.exceptions.HTTPError) and hasattr(e, 'response'):
                response = e.response
                if hasattr(response, 'text') and hasattr(response, 'status_code'):
                    raise handle_ml_api_error(response.text, response.status_code, 'ml/inference/deployments/')
        except (ImportError, AttributeError):
            pass
        raise click.ClickException(f"Failed to deploy model for serving: {e}")


@serving.command('predict')
@click.option('--model-id', required=True, help='ML model ID')
@click.option('--input', required=True, help='Input data (JSON string or file path)')
@click.option('--format', 'output_format', type=click.Choice(['json', 'table']), default='table', help='Output format')
def predict_serving(model_id: str, input: str, output_format: str):
    """Run inference prediction on a served model"""
    # Validate parameters
    try:
        validate_uuid(model_id, 'model-id')
    except ODHMLModelParameterError as e:
        raise click.ClickException(str(e))

    # Parse input data
    input_json = None
    if os.path.exists(input):
        # Input is a file path
        try:
            with open(input, 'r', encoding='utf-8') as f:
                input_json = json.load(f)
        except Exception as e:
            raise click.ClickException(f"Failed to read input file: {e}")
    else:
        # Try to parse as JSON string
        try:
            input_json = validate_json(input, 'input')
        except ODHMLModelParameterError as e:
            raise click.ClickException(str(e))

    # Resolve deployment_id from model_id — the predict endpoint requires
    # deployment_id, not model_id.  List deployments for this model and
    # pick the first READY one (fall back to any deployment).
    deployment_id = None
    try:
        deps = api_client.get(
            'ml/inference/deployments/',
            params={'model_id': model_id, 'status': 'READY', 'limit': 1},
        )
        results = deps.get('results', []) if isinstance(deps, dict) else deps
        if results:
            deployment_id = results[0].get('deployment_id')
        if not deployment_id:
            # Fall back: any deployment for this model
            deps = api_client.get(
                'ml/inference/deployments/',
                params={'model_id': model_id, 'limit': 1},
            )
            results = deps.get('results', []) if isinstance(deps, dict) else deps
            if results:
                deployment_id = results[0].get('deployment_id')
    except Exception:
        pass  # Will fail below with a clear message

    if not deployment_id:
        raise click.ClickException(f"No deployment found for model {model_id}")

    data = {
        'deployment_id': deployment_id,
        'input': input_json
    }

    try:
        # API endpoint: /api/v1/ml/inference/deployments/predict/
        result = api_client.post('ml/inference/deployments/predict/', json_data=data)

        if output_format == 'json':
            click.echo(json.dumps(result, indent=2))
        else:
            click.echo("Prediction completed successfully!")
            click.echo(f"Model ID: {result.get('model_id')}")
            click.echo(f"Status: {result.get('status')}")
            output = result.get('output', {})
            if output:
                click.echo("\nOutput:")
                click.echo(json.dumps(output, indent=2))
    except click.ClickException:
        raise
    except Exception as e:
        # Try to handle as ML API error if it's a requests exception
        try:
            import requests
            if isinstance(e, requests.exceptions.HTTPError) and hasattr(e, 'response'):
                response = e.response
                if hasattr(response, 'text') and hasattr(response, 'status_code'):
                    raise handle_ml_api_error(response.text, response.status_code, 'ml/inference/deployments/predict/')
        except (ImportError, AttributeError):
            pass
        raise click.ClickException(f"Failed to run prediction: {e}")


@serving.command('list')
@click.option('--model-id', help='Filter by model ID')
@click.option('--status', help='Filter by serving status')
@click.option('--limit', type=int, default=20, help='Limit number of results')
@click.option('--offset', type=int, default=0, help='Offset for pagination')
@click.option('--format', 'output_format', type=click.Choice(['json', 'table']), default='table', help='Output format')
def list_serving(model_id: Optional[str], status: Optional[str], limit: int, offset: int, output_format: str):
    """List model serving deployments"""
    from typing import Dict, Any
    params: Dict[str, Any] = {'limit': limit, 'offset': offset}
    if status:
        params['status'] = status
    if model_id:
        # Validate UUID format
        try:
            validate_uuid(model_id, 'model-id')
        except ODHMLModelParameterError as e:
            raise click.ClickException(str(e))
        params['model_id'] = model_id

    try:
        # API endpoint: /api/v1/ml/inference/deployments/
        data = api_client.get('ml/inference/deployments/', params=params)
        # Handle both paginated response (dict with 'results') and direct list response
        if isinstance(data, dict):
            results = data.get('results', [])
        elif isinstance(data, list):
            results = data
        else:
            results = []

        if output_format == 'json':
            click.echo(json.dumps(results, indent=2))
        else:
            if not results:
                click.echo("No serving deployments found.")
                return

            # Table format
            click.echo(f"{'Serving ID':<40} {'Model ID':<40} {'Status':<20} {'Endpoint':<50}")
            click.echo("-" * 150)
            for serving in results:
                serving_id = str(serving.get('serving_id', ''))[:38]
                model_id_display = str(serving.get('model_id', ''))[:38]
                status_str = str(serving.get('status', ''))[:18]
                endpoint = str(serving.get('endpoint', ''))[:48] if serving.get('endpoint') else 'N/A'
                click.echo(
                    f"{serving_id:<40} "
                    f"{model_id_display:<40} "
                    f"{status_str:<20} "
                    f"{endpoint:<50}"
                )
    except click.ClickException:
        raise
    except Exception as e:
        # Try to handle as ML API error if it's a requests exception
        try:
            import requests
            if isinstance(e, requests.exceptions.HTTPError) and hasattr(e, 'response'):
                response = e.response
                if hasattr(response, 'text') and hasattr(response, 'status_code'):
                    raise handle_ml_api_error(response.text, response.status_code, 'ml/inference/deployments/')
        except (ImportError, AttributeError):
            pass
        raise click.ClickException(f"Failed to list serving deployments: {e}")


@serving.command('get')
@click.argument('serving_id')
@click.option('--format', 'output_format', type=click.Choice(['json', 'table']), default='table', help='Output format')
def get_serving(serving_id: str, output_format: str):
    """Get serving deployment details"""
    try:
        # API endpoint: /api/v1/ml/inference/deployments/{id}/
        data = api_client.get(f'ml/inference/deployments/{serving_id}/')

        if output_format == 'json':
            click.echo(json.dumps(data, indent=2))
        else:
            # Table format
            click.echo(f"Serving ID: {data.get('serving_id')}")
            click.echo(f"Model ID: {data.get('model_id')}")
            click.echo(f"Status: {data.get('status')}")
            if data.get('endpoint'):
                click.echo(f"Endpoint: {data.get('endpoint')}")
            if data.get('created_at'):
                click.echo(f"Created: {data.get('created_at')}")
            if data.get('updated_at'):
                click.echo(f"Updated: {data.get('updated_at')}")
            # Display metrics if available
            if data.get('metrics'):
                click.echo("\nMetrics:")
                metrics = data.get('metrics', {})
                if metrics.get('accuracy') is not None:
                    click.echo(f"  Accuracy: {metrics.get('accuracy'):.2f}")
                if metrics.get('latency_ms') is not None:
                    click.echo(f"  Latency: {metrics.get('latency_ms'):.2f} ms")
                if metrics.get('error_rate') is not None:
                    click.echo(f"  Error Rate: {metrics.get('error_rate'):.2f}%")
    except click.ClickException:
        raise
    except Exception as e:
        # Try to handle as ML API error if it's a requests exception
        try:
            import requests
            if isinstance(e, requests.exceptions.HTTPError) and hasattr(e, 'response'):
                response = e.response
                if hasattr(response, 'text') and hasattr(response, 'status_code'):
                    raise handle_ml_api_error(response.text, response.status_code, f'ml/inference/deployments/{serving_id}/')
        except (ImportError, AttributeError):
            pass
        raise click.ClickException(f"Failed to get serving deployment: {e}")


@serving.command('undeploy')
@click.argument('serving_id')
@click.option('--format', 'output_format', type=click.Choice(['json', 'table']), default='table', help='Output format')
def undeploy_serving(serving_id: str, output_format: str):
    """Undeploy a model serving deployment"""
    try:
        # API endpoint: /api/v1/ml/inference/deployments/{id}/
        result = api_client.delete(f'ml/inference/deployments/{serving_id}/')

        if output_format == 'json':
            click.echo(json.dumps(result if result else {}, indent=2))
        else:
            click.echo("Serving deployment undeployed successfully!")
    except click.ClickException:
        raise
    except Exception as e:
        # Try to handle as ML API error if it's a requests exception
        try:
            import requests
            if isinstance(e, requests.exceptions.HTTPError) and hasattr(e, 'response'):
                response = e.response
                if hasattr(response, 'text') and hasattr(response, 'status_code'):
                    raise handle_ml_api_error(response.text, response.status_code, f'ml/inference/deployments/{serving_id}/')
        except (ImportError, AttributeError):
            pass
        raise click.ClickException(f"Failed to undeploy serving deployment: {e}")


@serving.command('metrics')
@click.argument('serving_id')
@click.option('--format', 'output_format', type=click.Choice(['json', 'table']), default='table', help='Output format')
def get_serving_metrics(serving_id: str, output_format: str):
    """Get quality metrics for a serving deployment"""
    try:
        # API endpoint: /api/v1/ml/inference/deployments/{id}/metrics/
        data = api_client.get(f'ml/inference/deployments/{serving_id}/metrics/')

        if output_format == 'json':
            click.echo(json.dumps(data, indent=2))
        else:
            # Table format
            click.echo(f"Metrics for Serving Deployment: {serving_id}")
            if data.get('accuracy') is not None:
                click.echo(f"Accuracy: {data.get('accuracy'):.2f}")
            if data.get('latency_ms') is not None:
                click.echo(f"Average Latency: {data.get('latency_ms'):.2f} ms")
            if data.get('error_rate') is not None:
                click.echo(f"Error Rate: {data.get('error_rate'):.2f}%")
            if data.get('data_drift') is not None:
                click.echo(f"Data Drift: {data.get('data_drift'):.2f}")
            if data.get('total_requests') is not None:
                click.echo(f"Total Requests: {data.get('total_requests')}")
            if data.get('successful_requests') is not None:
                click.echo(f"Successful Requests: {data.get('successful_requests')}")
            if data.get('failed_requests') is not None:
                click.echo(f"Failed Requests: {data.get('failed_requests')}")
            if data.get('metrics'):
                click.echo("\nAdditional Metrics:")
                click.echo(json.dumps(data.get('metrics'), indent=2))
    except click.ClickException:
        raise
    except Exception as e:
        # Try to handle as ML API error if it's a requests exception
        try:
            import requests
            if isinstance(e, requests.exceptions.HTTPError) and hasattr(e, 'response'):
                response = e.response
                if hasattr(response, 'text') and hasattr(response, 'status_code'):
                    raise handle_ml_api_error(response.text, response.status_code, f'ml/inference/deployments/{serving_id}/metrics/')
        except (ImportError, AttributeError):
            pass
        raise click.ClickException(f"Failed to get serving metrics: {e}")


@serving.group('ab-test')
def ab_test():
    """A/B testing commands for model serving"""
    pass


@ab_test.command('create')
@click.option('--model-id', required=True, help='Base model ID')
@click.option('--variant-id', required=True, help='Variant model ID')
@click.option('--traffic-split', required=True, help='Traffic split (e.g., "50:50" or "70:30")')
@click.option('--format', 'output_format', type=click.Choice(['json', 'table']), default='table', help='Output format')
def create_ab_test(model_id: str, variant_id: str, traffic_split: str, output_format: str):
    """Create an A/B test for model serving"""
    # Validate parameters
    try:
        validate_uuid(model_id, 'model-id')
        validate_uuid(variant_id, 'variant-id')
    except ODHMLModelParameterError as e:
        raise click.ClickException(str(e))

    # Validate traffic split format (e.g., "50:50" or "70:30")
    try:
        parts = traffic_split.split(':')
        if len(parts) != 2:
            raise ValueError("Traffic split must be in format 'X:Y' (e.g., '50:50')")
        base_percent = int(parts[0].strip())
        variant_percent = int(parts[1].strip())
        if base_percent < 0 or base_percent > 100 or variant_percent < 0 or variant_percent > 100:
            raise ValueError("Traffic split percentages must be between 0 and 100")
        if base_percent + variant_percent != 100:
            raise ValueError("Traffic split percentages must sum to 100")
    except ValueError as e:
        raise click.ClickException(f"Invalid traffic split format: {e}. Use format 'X:Y' where X+Y=100 (e.g., '50:50')")

    # Build request data
    data = {
        'model_id': model_id,
        'variant_id': variant_id,
        'traffic_split': f"{base_percent}:{variant_percent}"
    }

    try:
        # API endpoint: /api/v1/ml/inference/ab-tests/
        result = api_client.post('ml/inference/ab-tests/', json_data=data)

        if output_format == 'json':
            click.echo(json.dumps(result, indent=2))
        else:
            click.echo("A/B test created successfully!")
            click.echo(f"A/B Test ID: {result.get('ab_test_id')}")
            click.echo(f"Base Model ID: {result.get('model_id')}")
            click.echo(f"Variant Model ID: {result.get('variant_id')}")
            click.echo(f"Traffic Split: {base_percent}:{variant_percent}")
            click.echo(f"Status: {result.get('status')}")
    except click.ClickException:
        raise
    except Exception as e:
        # Try to handle as ML API error if it's a requests exception
        try:
            import requests
            if isinstance(e, requests.exceptions.HTTPError) and hasattr(e, 'response'):
                response = e.response
                if hasattr(response, 'text') and hasattr(response, 'status_code'):
                    raise handle_ml_api_error(response.text, response.status_code, 'ml/inference/ab-tests/')
        except (ImportError, AttributeError):
            pass
        raise click.ClickException(f"Failed to create A/B test: {e}")


@ab_test.command('list')
@click.option('--model-id', help='Filter by model ID')
@click.option('--format', 'output_format', type=click.Choice(['json', 'table']), default='table', help='Output format')
def list_ab_tests(model_id: Optional[str], output_format: str):
    """List A/B tests"""
    from typing import Dict, Any
    params: Dict[str, Any] = {}
    if model_id:
        # Validate UUID format
        try:
            validate_uuid(model_id, 'model-id')
        except ODHMLModelParameterError as e:
            raise click.ClickException(str(e))
        params['model_id'] = model_id

    try:
        # API endpoint: /api/v1/ml/inference/ab-tests/
        data = api_client.get('ml/inference/ab-tests/', params=params)
        # Handle both paginated response (dict with 'results') and direct list response
        if isinstance(data, dict):
            results = data.get('results', [])
        elif isinstance(data, list):
            results = data
        else:
            results = []

        if output_format == 'json':
            click.echo(json.dumps(results, indent=2))
        else:
            if not results:
                click.echo("No A/B tests found.")
                return

            # Table format
            click.echo(f"{'A/B Test ID':<40} {'Base Model ID':<40} {'Variant Model ID':<40} {'Traffic Split':<20} {'Status':<15}")
            click.echo("-" * 155)
            for ab_test in results:
                ab_test_id = str(ab_test.get('ab_test_id', ''))[:38]
                base_model_id = str(ab_test.get('model_id', ''))[:38]
                variant_model_id = str(ab_test.get('variant_id', ''))[:38]
                traffic_split = ab_test.get('traffic_split', {})
                if isinstance(traffic_split, dict):
                    split_str = f"{traffic_split.get('base', 0)}:{traffic_split.get('variant', 0)}"
                else:
                    split_str = str(traffic_split)[:18]
                status_str = str(ab_test.get('status', ''))[:13]
                click.echo(
                    f"{ab_test_id:<40} "
                    f"{base_model_id:<40} "
                    f"{variant_model_id:<40} "
                    f"{split_str:<20} "
                    f"{status_str:<15}"
                )
    except click.ClickException:
        raise
    except Exception as e:
        # Try to handle as ML API error if it's a requests exception
        try:
            import requests
            if isinstance(e, requests.exceptions.HTTPError) and hasattr(e, 'response'):
                response = e.response
                if hasattr(response, 'text') and hasattr(response, 'status_code'):
                    raise handle_ml_api_error(response.text, response.status_code, 'ml/inference/ab-tests/')
        except (ImportError, AttributeError):
            pass
        raise click.ClickException(f"Failed to list A/B tests: {e}")


@ab_test.command('get')
@click.argument('ab_test_id')
@click.option('--format', 'output_format', type=click.Choice(['json', 'table']), default='table', help='Output format')
def get_ab_test(ab_test_id: str, output_format: str):
    """Get A/B test details"""
    try:
        # API endpoint: /api/v1/ml/inference/ab-tests/{id}/
        data = api_client.get(f'ml/inference/ab-tests/{ab_test_id}/')

        if output_format == 'json':
            click.echo(json.dumps(data, indent=2))
        else:
            # Table format
            click.echo(f"A/B Test ID: {data.get('ab_test_id')}")
            click.echo(f"Base Model ID: {data.get('model_id')}")
            click.echo(f"Variant Model ID: {data.get('variant_id')}")
            traffic_split = data.get('traffic_split', {})
            if isinstance(traffic_split, dict):
                click.echo(f"Traffic Split: {traffic_split.get('base', 0)}:{traffic_split.get('variant', 0)}")
            else:
                click.echo(f"Traffic Split: {traffic_split}")
            click.echo(f"Status: {data.get('status')}")
            if data.get('created_at'):
                click.echo(f"Created: {data.get('created_at')}")
            if data.get('updated_at'):
                click.echo(f"Updated: {data.get('updated_at')}")
            # Display metrics for each variant if available
            if data.get('metrics'):
                click.echo("\nMetrics:")
                metrics = data.get('metrics', {})
                if metrics.get('base'):
                    click.echo("  Base Model:")
                    base_metrics = metrics.get('base', {})
                    if base_metrics.get('accuracy') is not None:
                        click.echo(f"    Accuracy: {base_metrics.get('accuracy'):.2f}")
                    if base_metrics.get('latency_ms') is not None:
                        click.echo(f"    Latency: {base_metrics.get('latency_ms'):.2f} ms")
                    if base_metrics.get('error_rate') is not None:
                        click.echo(f"    Error Rate: {base_metrics.get('error_rate'):.2f}%")
                if metrics.get('variant'):
                    click.echo("  Variant Model:")
                    variant_metrics = metrics.get('variant', {})
                    if variant_metrics.get('accuracy') is not None:
                        click.echo(f"    Accuracy: {variant_metrics.get('accuracy'):.2f}")
                    if variant_metrics.get('latency_ms') is not None:
                        click.echo(f"    Latency: {variant_metrics.get('latency_ms'):.2f} ms")
                    if variant_metrics.get('error_rate') is not None:
                        click.echo(f"    Error Rate: {variant_metrics.get('error_rate'):.2f}%")
    except click.ClickException:
        raise
    except Exception as e:
        # Try to handle as ML API error if it's a requests exception
        try:
            import requests
            if isinstance(e, requests.exceptions.HTTPError) and hasattr(e, 'response'):
                response = e.response
                if hasattr(response, 'text') and hasattr(response, 'status_code'):
                    raise handle_ml_api_error(response.text, response.status_code, f'ml/inference/ab-tests/{ab_test_id}/')
        except (ImportError, AttributeError):
            pass
        raise click.ClickException(f"Failed to get A/B test: {e}")


# ── 118E.7: deploy/undeploy/rollback/plan/marketplace ────


@ml.command("deploy")
@click.argument("model_id")
@click.option(
    "--config-file",
    type=click.Path(exists=True),
    help="Deployment config JSON file",
)
@click.option(
    "--format", "output_format",
    type=click.Choice(["json", "table"]),
    default="table",
)
def deploy_model(
    model_id: str,
    config_file: Optional[str],
    output_format: str,
):
    """Deploy an ML model"""
    payload = {}
    if config_file:
        with open(config_file, "r") as f:
            payload = json.loads(f.read())
    try:
        data = api_client.post(
            f"ml/models/{model_id}/deploy/",
            json_data=payload,
            timeout=120,
        )
        if output_format == "json":
            click.echo(json.dumps(data, indent=2))
        else:
            click.echo("Model deployed successfully!")
            click.echo(f"Model ID: {model_id}")
            click.echo(f"Status: {data.get('status')}")
    except click.ClickException:
        raise
    except Exception as e:
        raise click.ClickException(
            f"Failed to deploy model: {e}"
        )


@ml.command("undeploy")
@click.argument("model_id")
def undeploy_model(model_id: str):
    """Undeploy an ML model"""
    try:
        api_client.post(
            f"ml/models/{model_id}/undeploy/",
        )
        click.echo(f"Model {model_id} undeployed.")
    except click.ClickException:
        raise
    except Exception as e:
        raise click.ClickException(
            f"Failed to undeploy model: {e}"
        )


@ml.command("rollback")
@click.argument("model_odh_id")
@click.option(
    "--version", "target_version",
    required=True,
    help="Version to rollback to",
)
def rollback_model(
    model_odh_id: str, target_version: str,
):
    """Rollback an ML model to a previous version"""
    try:
        data = api_client.post(
            f"ml/models/{model_odh_id}/rollback/",
            json_data={"version": target_version},
        )
        click.echo(
            f"Model rolled back to version "
            f"{target_version}."
        )
        click.echo(f"Status: {data.get('status')}")
    except click.ClickException:
        raise
    except Exception as e:
        raise click.ClickException(
            f"Failed to rollback model: {e}"
        )


@ml.group("plan")
def ml_plan():
    """ML plan and limits commands"""
    pass


@ml_plan.command("show")
@click.option(
    "--format", "output_format",
    type=click.Choice(["json", "table"]),
    default="table",
)
def show_ml_plan(output_format: str):
    """Show current ML subscription plan"""
    try:
        data = api_client.get(
            "billing/subscription/ml/current/",
        )
        if output_format == "json":
            click.echo(json.dumps(data, indent=2))
        else:
            click.echo(
                f"Plan: {data.get('plan_name')} "
                f"({data.get('plan_slug')})"
            )
            click.echo(f"Status: {data.get('status')}")
    except click.ClickException:
        raise
    except Exception as e:
        raise click.ClickException(
            f"Failed to get ML plan: {e}"
        )


@ml_plan.command("limits")
@click.option(
    "--format", "output_format",
    type=click.Choice(["json", "table"]),
    default="table",
)
def show_ml_limits(output_format: str):
    """Show ML plan limits"""
    try:
        data = api_client.get(
            "billing/subscription/ml/current/",
        )
        limits = data.get("limits", {})
        ml_limits = {
            k: v for k, v in limits.items()
            if "ml" in k
        }

        if output_format == "json":
            click.echo(json.dumps(ml_limits, indent=2))
        else:
            if not ml_limits:
                click.echo("No ML limits on plan.")
                return
            click.echo(
                f"{'Limit':<45} {'Value':<15}"
            )
            click.echo("-" * 60)
            for k, v in sorted(ml_limits.items()):
                val = (
                    "Unlimited" if v is None
                    else str(v)
                )
                click.echo(f"{k:<45} {val:<15}")
    except click.ClickException:
        raise
    except Exception as e:
        raise click.ClickException(
            f"Failed to get ML limits: {e}"
        )


@ml.command("marketplace-publish")
@click.argument("model_id")
@click.option(
    "--pricing-model",
    type=click.Choice([
        "FREE", "FREE_AUTO_APPROVE",
        "REQUEST_APPROVAL",
    ]),
    default="REQUEST_APPROVAL",
)
@click.option(
    "--format", "output_format",
    type=click.Choice(["json", "table"]),
    default="table",
)
def marketplace_publish(
    model_id: str, pricing_model: str,
    output_format: str,
):
    """Publish an ML model to the marketplace"""
    try:
        data = api_client.post(
            f"ml/models/{model_id}"
            f"/marketplace-publish/",
            json_data={
                "pricing_model": pricing_model,
            },
        )
        if output_format == "json":
            click.echo(json.dumps(data, indent=2))
        else:
            click.echo("Model published to marketplace!")
            click.echo(
                f"Listing ID: {data.get('listing_id')}"
            )
    except click.ClickException:
        raise
    except Exception as e:
        raise click.ClickException(
            f"Failed to publish model: {e}"
        )
