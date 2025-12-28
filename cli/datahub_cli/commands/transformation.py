"""
Transformation management commands.
"""
import click
import json
import os
import time
from typing import Optional, Dict, Any
from ..api_client import api_client


@click.group()
def transformation():
    """Transformation management commands"""
    pass


@transformation.group('pipelines')
def pipelines():
    """Pipeline management commands"""
    pass


@pipelines.command('list')
@click.option('--status', type=click.Choice(['DRAFT', 'ACTIVE', 'INACTIVE', 'ARCHIVED']), help='Filter by status')
@click.option('--version', help='Filter by version')
@click.option('--search', help='Search in name and description')
@click.option('--ordering', help='Order by field (name, status, version, created_at, updated_at). Prefix with - for descending')
@click.option('--page', type=int, default=1, help='Page number (default: 1)')
@click.option('--page-size', type=int, default=20, help='Page size (default: 20, max: 100)')
@click.option('--format', 'output_format', type=click.Choice(['json', 'table']), default='table', help='Output format')
def list_pipelines(
    status: Optional[str],
    version: Optional[str],
    search: Optional[str],
    ordering: Optional[str],
    page: int,
    page_size: int,
    output_format: str
):
    """List transformation pipelines with filtering and pagination"""
    try:
        # Build query parameters
        params: Dict[str, Any] = {
            'page': page,
            'page_size': min(page_size, 100)  # Enforce max page size
        }

        if status:
            params['status'] = status
        if version:
            params['version'] = version
        if search:
            params['search'] = search
        if ordering:
            params['ordering'] = ordering

        # API endpoint: /api/v1/transformation/pipelines/
        data = api_client.get('transformation/pipelines/', params=params)

        # Handle paginated response
        if isinstance(data, dict) and 'results' in data:
            results: list = data.get('results', [])
            count: int = data.get('count', len(results))
            next_page: Optional[int] = data.get('next')
            previous_page: Optional[int] = data.get('previous')
        elif isinstance(data, list):
            results = data
            count = len(results)
            next_page = None
            previous_page = None
        else:
            results = []
            count = 0
            next_page = None
            previous_page = None

        if output_format == 'json':
            output: Dict[str, Any] = {
                'count': count,
                'next': next_page,
                'previous': previous_page,
                'results': results
            }
            click.echo(json.dumps(output, indent=2))
        else:
            if not results:
                click.echo("No pipelines found.")
                return

            # Table format
            click.echo(f"{'ID':<40} {'Name':<30} {'Status':<12} {'Version':<15} {'Created':<20}")
            click.echo("-" * 117)
            for pipeline_item in results:
                if not isinstance(pipeline_item, dict):
                    continue
                pipeline_id = pipeline_item.get('id', '')[:36] if pipeline_item.get('id') else 'N/A'
                name = (pipeline_item.get('name', '')[:28] + '..') if len(pipeline_item.get('name', '')) > 30 else pipeline_item.get('name', 'N/A')
                status_val = pipeline_item.get('status', 'N/A')
                version_val = pipeline_item.get('version', 'N/A')
                created = pipeline_item.get('created_at', '')[:19] if pipeline_item.get('created_at') else 'N/A'
                click.echo(f"{pipeline_id:<40} {name:<30} {status_val:<12} {version_val:<15} {created:<20}")

            # Show pagination info
            if count > len(results):
                click.echo(f"\nShowing {len(results)} of {count} pipelines")
                if next_page:
                    click.echo(f"Next page: --page {page + 1}")
                if previous_page:
                    click.echo(f"Previous page: --page {page - 1}")
    except click.ClickException:
        raise
    except Exception as e:
        raise click.ClickException(f"Failed to list pipelines: {e}")


@pipelines.command('create')
@click.option('--file', 'file_path', required=True, type=click.Path(exists=True, readable=True), help='Path to pipeline definition JSON file (required)')
@click.option('--format', 'output_format', type=click.Choice(['json', 'table']), default='table', help='Output format')
def create_pipeline(file_path: str, output_format: str):
    """Create a new transformation pipeline from a JSON file"""
    try:
        # Read and parse pipeline definition file
        if not os.path.exists(file_path):
            raise click.ClickException(f"File not found: {file_path}")

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                pipeline_data = json.load(f)
        except json.JSONDecodeError as e:
            raise click.ClickException(f"Invalid JSON in file: {e}")
        except Exception as e:
            raise click.ClickException(f"Failed to read file: {e}")

        # Validate pipeline_data structure
        if not isinstance(pipeline_data, dict):
            raise click.ClickException("Pipeline definition must be a JSON object")

        # Extract pipeline fields from the JSON file
        # The file should contain: name, description (optional), pipeline_definition, version (optional), status (optional), metadata (optional)
        pipeline_definition = pipeline_data.get('pipeline_definition')
        if not pipeline_definition:
            # If pipeline_definition is not present, assume the entire file is the pipeline_definition
            pipeline_definition = pipeline_data
            # Extract other fields if they exist at top level
            name = pipeline_data.get('name')
            if not name:
                raise click.ClickException("Pipeline definition must contain 'name' field or 'pipeline_definition' with 'name'")
        else:
            name = pipeline_data.get('name')
            if not name:
                raise click.ClickException("Pipeline definition must contain 'name' field")

        # Build request data
        data: Dict[str, Any] = {
            'name': name.strip(),
            'pipeline_definition': pipeline_definition
        }

        # Add optional fields
        if 'description' in pipeline_data:
            data['description'] = pipeline_data['description']
        if 'version' in pipeline_data:
            data['version'] = pipeline_data['version']
        if 'status' in pipeline_data:
            data['status'] = pipeline_data['status']
        if 'metadata' in pipeline_data:
            data['metadata'] = pipeline_data['metadata']

        # API endpoint: /api/v1/transformation/pipelines/
        result = api_client.post('transformation/pipelines/', json_data=data)

        if output_format == 'json':
            click.echo(json.dumps(result, indent=2))
        else:
            click.echo("Pipeline created successfully!")
            click.echo(f"Pipeline ID: {result.get('id')}")
            click.echo(f"Name: {result.get('name')}")
            click.echo(f"Status: {result.get('status')}")
            if result.get('description'):
                click.echo(f"Description: {result.get('description')}")
            if result.get('version'):
                click.echo(f"Version: {result.get('version')}")
            click.echo(f"Created: {result.get('created_at')}")
    except click.ClickException:
        raise
    except Exception as e:
        raise click.ClickException(f"Failed to create pipeline: {e}")


@pipelines.command('get')
@click.argument('pipeline_id')
@click.option('--format', 'output_format', type=click.Choice(['json', 'table']), default='table', help='Output format')
def get_pipeline(pipeline_id: str, output_format: str):
    """Get pipeline details by ID"""
    try:
        # API endpoint: /api/v1/transformation/pipelines/{id}/
        data = api_client.get(f'transformation/pipelines/{pipeline_id}/')

        if output_format == 'json':
            click.echo(json.dumps(data, indent=2))
        else:
            click.echo(f"Pipeline ID: {data.get('id')}")
            click.echo(f"Name: {data.get('name')}")
            click.echo(f"Status: {data.get('status')}")
            if data.get('description'):
                click.echo(f"Description: {data.get('description')}")
            if data.get('version'):
                click.echo(f"Version: {data.get('version')}")
            if data.get('pipeline_definition'):
                click.echo(f"Pipeline Definition: {json.dumps(data.get('pipeline_definition'), indent=2)}")
            if data.get('metadata'):
                click.echo(f"Metadata: {json.dumps(data.get('metadata'), indent=2)}")
            click.echo(f"Created: {data.get('created_at')}")
            click.echo(f"Updated: {data.get('updated_at')}")
    except click.ClickException:
        raise
    except Exception as e:
        raise click.ClickException(f"Failed to get pipeline: {e}")


@pipelines.command('update')
@click.argument('pipeline_id')
@click.option('--file', 'file_path', required=True, type=click.Path(exists=True, readable=True), help='Path to pipeline definition JSON file (required)')
@click.option('--format', 'output_format', type=click.Choice(['json', 'table']), default='table', help='Output format')
def update_pipeline(pipeline_id: str, file_path: str, output_format: str):
    """Update an existing transformation pipeline from a JSON file"""
    try:
        # Read and parse pipeline definition file
        if not os.path.exists(file_path):
            raise click.ClickException(f"File not found: {file_path}")

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                pipeline_data = json.load(f)
        except json.JSONDecodeError as e:
            raise click.ClickException(f"Invalid JSON in file: {e}")
        except Exception as e:
            raise click.ClickException(f"Failed to read file: {e}")

        # Validate pipeline_data structure
        if not isinstance(pipeline_data, dict):
            raise click.ClickException("Pipeline definition must be a JSON object")

        # Build request data (only include provided fields)
        data: Dict[str, Any] = {}

        # Extract pipeline fields from the JSON file
        # The file should contain: name (optional), description (optional), pipeline_definition (optional), version (optional), status (optional), metadata (optional)
        if 'name' in pipeline_data:
            data['name'] = pipeline_data['name'].strip()
        if 'description' in pipeline_data:
            data['description'] = pipeline_data['description']
        if 'pipeline_definition' in pipeline_data:
            data['pipeline_definition'] = pipeline_data['pipeline_definition']
        elif not any(key in pipeline_data for key in ['name', 'description', 'version', 'status', 'metadata']):
            # If pipeline_definition is not present and no other fields, assume the entire file is the pipeline_definition
            data['pipeline_definition'] = pipeline_data
        if 'version' in pipeline_data:
            data['version'] = pipeline_data['version']
        if 'status' in pipeline_data:
            data['status'] = pipeline_data['status']
        if 'metadata' in pipeline_data:
            data['metadata'] = pipeline_data['metadata']

        if not data:
            raise click.ClickException("At least one field must be provided for update")

        # API endpoint: /api/v1/transformation/pipelines/{id}/
        result = api_client.patch(f'transformation/pipelines/{pipeline_id}/', json_data=data)

        if output_format == 'json':
            click.echo(json.dumps(result, indent=2))
        else:
            click.echo("Pipeline updated successfully!")
            click.echo(f"Pipeline ID: {result.get('id')}")
            click.echo(f"Name: {result.get('name')}")
            click.echo(f"Status: {result.get('status')}")
            if result.get('description'):
                click.echo(f"Description: {result.get('description')}")
            if result.get('version'):
                click.echo(f"Version: {result.get('version')}")
            click.echo(f"Updated: {result.get('updated_at')}")
    except click.ClickException:
        raise
    except Exception as e:
        raise click.ClickException(f"Failed to update pipeline: {e}")


@pipelines.command('delete')
@click.argument('pipeline_id')
@click.option('--format', 'output_format', type=click.Choice(['json', 'table']), default='table', help='Output format')
@click.confirmation_option(prompt='Are you sure you want to delete this pipeline?')
def delete_pipeline(pipeline_id: str, output_format: str):
    """Delete a transformation pipeline"""
    try:
        # API endpoint: /api/v1/transformation/pipelines/{id}/
        result = api_client.delete(f'transformation/pipelines/{pipeline_id}/')

        if output_format == 'json':
            click.echo(json.dumps(result, indent=2))
        else:
            click.echo(f"Pipeline {pipeline_id} deleted successfully!")
    except click.ClickException:
        raise
    except Exception as e:
        raise click.ClickException(f"Failed to delete pipeline: {e}")


# Execution commands group
@transformation.group('executions')
def executions():
    """Execution management commands"""
    pass


@executions.command('create')
@click.argument('pipeline_id')
@click.option('--input-asset', required=True, help='Input asset ID')
@click.option('--execution-mode', type=click.Choice(['SYNC', 'ASYNC']), default='ASYNC', help='Execution mode (SYNC or ASYNC)')
@click.option('--format', 'output_format', type=click.Choice(['json', 'table']), default='table', help='Output format')
def create_execution(pipeline_id: str, input_asset: str, execution_mode: str, output_format: str):
    """Create a new transformation execution"""
    try:
        result = api_client.post(
            f'transformation/pipelines/{pipeline_id}/execute/',
            json_data={
                'asset_id': input_asset,
                'execution_mode': execution_mode
            }
        )

        if output_format == 'json':
            click.echo(json.dumps(result, indent=2))
        else:
            click.echo(f"Execution created successfully!")
            click.echo(f"Execution ID: {result.get('execution_id', 'N/A')}")
            click.echo(f"Status: {result.get('status', 'N/A')}")
            click.echo(f"Pipeline ID: {result.get('pipeline_id', 'N/A')}")
            click.echo(f"Asset ID: {result.get('asset_id', 'N/A')}")
    except click.ClickException:
        raise
    except Exception as e:
        raise click.ClickException(f"Failed to create execution: {e}")


@executions.command('list')
@click.option('--pipeline-id', required=True, help='Pipeline ID to list executions for')
@click.option('--status', help='Filter by status (PENDING, RUNNING, COMPLETED, FAILED, CANCELLED)')
@click.option('--page', type=int, default=1, help='Page number')
@click.option('--page-size', type=int, default=20, help='Number of items per page')
@click.option('--format', 'output_format', type=click.Choice(['json', 'table']), default='table', help='Output format')
def list_executions(pipeline_id: str, status: Optional[str], page: int, page_size: int, output_format: str):
    """List transformation executions for a pipeline"""
    try:
        params: Dict[str, Any] = {'page': page, 'page_size': page_size}
        if status:
            params['status'] = status

        data = api_client.get(f'transformation/pipelines/{pipeline_id}/executions/', params=params)

        # Handle paginated response
        if isinstance(data, dict):
            results = data.get('results', [])
            count = data.get('count', len(results))
        elif isinstance(data, list):
            results = data
            count = len(results)
        else:
            results = []
            count = 0

        if output_format == 'json':
            click.echo(json.dumps(data, indent=2))
        else:
            if not results:
                click.echo("No executions found.")
                return

            # Table format
            click.echo(f"{'ID':<40} {'Status':<15} {'Asset ID':<40} {'Started':<25}")
            click.echo("-" * 120)
            for execution in results:
                exec_id = execution.get('id', '')[:36]
                exec_status = execution.get('status', '')[:13]
                asset_id = execution.get('asset_id', '')[:36]
                started = execution.get('started_at', '')[:19] if execution.get('started_at') else 'N/A'
                click.echo(
                    f"{exec_id:<40} "
                    f"{exec_status:<15} "
                    f"{asset_id:<40} "
                    f"{started:<25}"
                )

            # Pagination info
            if isinstance(data, dict) and count > len(results):
                click.echo(f"\nShowing {len(results)} of {count} executions")
                if data.get('next'):
                    click.echo(f"Next page: --page {data['next']}")
                if data.get('previous'):
                    click.echo(f"Previous page: --page {data['previous']}")
    except click.ClickException:
        raise
    except Exception as e:
        raise click.ClickException(f"Failed to list executions: {e}")


@executions.command('get')
@click.argument('execution_id')
@click.option('--format', 'output_format', type=click.Choice(['json', 'table']), default='table', help='Output format')
def get_execution(execution_id: str, output_format: str):
    """Get execution details"""
    try:
        data = api_client.get(f'transformation/executions/{execution_id}/')

        if output_format == 'json':
            click.echo(json.dumps(data, indent=2))
        else:
            # Table format
            click.echo(f"ID: {data.get('id')}")
            click.echo(f"Pipeline ID: {data.get('pipeline_id')}")
            click.echo(f"Asset ID: {data.get('asset_id')}")
            click.echo(f"Status: {data.get('status')}")
            click.echo(f"Created: {data.get('created_at')}")
            if data.get('started_at'):
                click.echo(f"Started: {data.get('started_at')}")
            if data.get('completed_at'):
                click.echo(f"Completed: {data.get('completed_at')}")
            if data.get('error_message'):
                click.echo(f"Error: {data.get('error_message')}")
            if data.get('metrics'):
                click.echo(f"Metrics: {json.dumps(data.get('metrics'), indent=2)}")
    except click.ClickException:
        raise
    except Exception as e:
        raise click.ClickException(f"Failed to get execution: {e}")


@executions.command('cancel')
@click.argument('execution_id')
@click.option('--format', 'output_format', type=click.Choice(['json', 'table']), default='table', help='Output format')
def cancel_execution(execution_id: str, output_format: str):
    """Cancel a transformation execution"""
    try:
        result = api_client.post(f'transformation/executions/{execution_id}/cancel/')

        if output_format == 'json':
            click.echo(json.dumps(result, indent=2))
        else:
            click.echo(f"Execution {execution_id} cancelled successfully!")
            click.echo(f"Status: {result.get('status')}")
            if result.get('message'):
                click.echo(f"Message: {result.get('message')}")
    except click.ClickException:
        raise
    except Exception as e:
        raise click.ClickException(f"Failed to cancel execution: {e}")


@executions.command('watch')
@click.argument('execution_id')
@click.option('--interval', type=int, default=2, help='Polling interval in seconds')
@click.option('--timeout', type=int, default=300, help='Timeout in seconds')
@click.option('--format', 'output_format', type=click.Choice(['json', 'table']), default='table', help='Output format')
def watch_execution(execution_id: str, interval: int, timeout: int, output_format: str):
    """Watch an execution until completion with progress updates"""
    start_time = time.time()

    try:
        while True:
            # Check timeout
            if time.time() - start_time > timeout:
                raise click.ClickException(f"Timeout waiting for execution {execution_id} to complete")

            # Get execution status
            data = api_client.get(f'transformation/executions/{execution_id}/')
            status = data.get('status')

            # Use execution data for progress (it may contain progress_percentage)
            # Only call progress endpoint if execution data doesn't have progress info
            progress_data = data
            if 'progress_percentage' not in data and 'current_step' not in data:
                # Try to get progress information from dedicated endpoint
                try:
                    progress_data = api_client.get(f'transformation/executions/{execution_id}/progress/')
                except Exception:
                    # Progress endpoint not available, use execution data
                    progress_data = data

            if output_format == 'table':
                # Display status and progress
                progress_info = ""
                if progress_data:
                    progress_pct = progress_data.get('progress_percentage')
                    current_step = progress_data.get('current_step')
                    total_steps = progress_data.get('total_steps')
                    if progress_pct is not None:
                        progress_info = f" - Progress: {progress_pct:.1f}%"
                    if current_step is not None and total_steps is not None:
                        progress_info += f" (Step {current_step}/{total_steps})"
                click.echo(f"Execution {execution_id}: {status}{progress_info}")
            # In JSON format, we only output JSON at the end when execution completes

            # Check if execution is complete
            if status in ['COMPLETED', 'FAILED', 'CANCELLED']:
                if output_format == 'json':
                    # Output final execution data as JSON
                    click.echo(json.dumps(data, indent=2))
                else:
                    click.echo(f"\nExecution {status.lower()}!")
                    if status == 'COMPLETED':
                        click.echo("Execution completed successfully.")
                        if progress_data and progress_data.get('metrics'):
                            click.echo(f"Metrics: {json.dumps(progress_data.get('metrics'), indent=2)}")
                    elif status == 'FAILED':
                        if data.get('error_message'):
                            click.echo(f"Error: {data.get('error_message')}")
                    elif status == 'CANCELLED':
                        click.echo("Execution was cancelled.")
                return

            # Wait before next poll
            time.sleep(interval)
    except click.ClickException:
        raise
    except KeyboardInterrupt:
        click.echo("\nWatching cancelled by user.")
        raise
    except Exception as e:
            raise click.ClickException(f"Failed to watch execution: {e}")


# Preview commands group
@transformation.group('preview')
def preview():
    """Preview management commands"""
    pass


@preview.command('generate')
@click.argument('pipeline_id')
@click.option('--input-asset', 'asset_id', required=True, help='Input asset ID (required)')
@click.option('--sample-size', type=int, default=100, help='Number of rows to sample (default: 100)')
@click.option('--sampling-method', type=click.Choice(['first_n', 'random']), default='first_n', help='Sampling method: first_n or random (default: first_n)')
@click.option('--format', 'output_format', type=click.Choice(['json', 'table']), default='table', help='Output format')
def generate_preview(
    pipeline_id: str,
    asset_id: str,
    sample_size: int,
    sampling_method: str,
    output_format: str
):
    """Generate a preview of transformation pipeline execution on sample data"""
    try:
        # Build request data
        data: Dict[str, Any] = {
            'asset_id': asset_id,
            'sample_size': sample_size,
            'sampling_method': sampling_method
        }

        # API endpoint: /api/v1/transformation/pipelines/{id}/preview/
        result = api_client.post(f'transformation/pipelines/{pipeline_id}/preview/', json_data=data)

        if output_format == 'json':
            click.echo(json.dumps(result, indent=2))
        else:
            click.echo("Preview generated successfully!")
            click.echo(f"Preview ID: {result.get('preview_id')}")
            click.echo(f"Pipeline ID: {result.get('pipeline_id')}")
            click.echo(f"Asset ID: {result.get('asset_id')}")
            if result.get('cached'):
                click.echo("Status: Cached (using existing preview)")
            else:
                click.echo("Status: Generated (new preview)")
            if result.get('analysis'):
                analysis = result.get('analysis', {})
                click.echo("\nAnalysis:")
                if 'row_count_changes' in analysis:
                    click.echo(f"  Row count changes: {json.dumps(analysis['row_count_changes'], indent=4)}")
                if 'schema_changes' in analysis:
                    click.echo(f"  Schema changes: {json.dumps(analysis['schema_changes'], indent=4)}")
                if 'quality_impact' in analysis:
                    click.echo(f"  Quality impact: {json.dumps(analysis['quality_impact'], indent=4)}")
    except click.ClickException:
        raise
    except Exception as e:
        raise click.ClickException(f"Failed to generate preview: {e}")


@preview.command('get')
@click.argument('preview_id')
@click.option('--format', 'output_format', type=click.Choice(['json', 'table']), default='table', help='Output format')
def get_preview(preview_id: str, output_format: str):
    """Get preview result by preview ID"""
    try:
        # API endpoint: /api/v1/transformation/previews/{preview_id}/
        data = api_client.get(f'transformation/previews/{preview_id}/')

        if output_format == 'json':
            click.echo(json.dumps(data, indent=2))
        else:
            click.echo(f"Preview ID: {data.get('preview_id')}")
            click.echo(f"Pipeline ID: {data.get('pipeline_id')}")
            click.echo(f"Asset ID: {data.get('asset_id')}")
            if data.get('generated_at'):
                click.echo(f"Generated: {data.get('generated_at')}")
            if data.get('expires_at'):
                click.echo(f"Expires: {data.get('expires_at')}")
            if data.get('analysis'):
                analysis = data.get('analysis', {})
                click.echo("\nAnalysis:")
                if 'row_count_changes' in analysis:
                    click.echo(f"  Row count changes: {json.dumps(analysis['row_count_changes'], indent=4)}")
                if 'schema_changes' in analysis:
                    click.echo(f"  Schema changes: {json.dumps(analysis['schema_changes'], indent=4)}")
                if 'quality_impact' in analysis:
                    click.echo(f"  Quality impact: {json.dumps(analysis['quality_impact'], indent=4)}")
            if data.get('input_sample'):
                click.echo(f"\nInput Sample: {len(data.get('input_sample', []))} rows")
            if data.get('output_sample'):
                click.echo(f"Output Sample: {len(data.get('output_sample', []))} rows")
    except click.ClickException:
        raise
    except Exception as e:
        raise click.ClickException(f"Failed to get preview: {e}")



# Wrangling commands group
@transformation.group('wrangling')
def wrangling():
    """Wrangling session management commands"""
    pass


@wrangling.command('start')
@click.argument('asset_id')
@click.option('--format', 'output_format', type=click.Choice(['json', 'table']), default='table', help='Output format')
def start_wrangling(asset_id: str, output_format: str):
    """
    Start a new wrangling session for an asset.
    
    Creates a new wrangling session by performing an initial no-op operation.
    The session can then be used for interactive data wrangling operations.
    """
    try:
        # Create a session by performing an initial operation
        # We use a simple operation that doesn't modify data to initialize the session
        # The API requires an operation, so we use a filter that matches all rows
        initial_operation = {
            "type": "FILTER",
            "parameters": {
                "condition": "1 == 1"  # Always true filter (no-op)
            }
        }
        
        # API endpoint: /api/v1/transformation/wrangling/
        result = api_client.post(
            'transformation/wrangling/',
            json_data={
                'asset_id': asset_id,
                'operation': initial_operation
            }
        )

        if output_format == 'json':
            click.echo(json.dumps(result, indent=2))
        else:
            click.echo("Wrangling session started successfully!")
            click.echo(f"Session ID: {result.get('session_id')}")
            click.echo(f"Operation ID: {result.get('operation_id')}")
            click.echo(f"Applied operations: {result.get('applied_operations_count', 0)}")
            click.echo(f"Can undo: {result.get('can_undo', False)}")
            click.echo(f"Can redo: {result.get('can_redo', False)}")
            if result.get('wrangling_script'):
                click.echo(f"\nWrangling script:\n{result.get('wrangling_script')}")
    except click.ClickException:
        raise
    except Exception as e:
        raise click.ClickException(f"Failed to start wrangling session: {e}")


@wrangling.command('apply')
@click.argument('session_id')
@click.option('--operation', required=True, help='Operation JSON string (e.g., \'{"type": "FILTER", "parameters": {"condition": "age > 18"}}\')')
@click.option('--format', 'output_format', type=click.Choice(['json', 'table']), default='table', help='Output format')
def apply_wrangling(session_id: str, operation: str, output_format: str):
    """
    Apply a wrangling operation to a session.
    
    OPERATION should be a JSON string containing the operation definition.
    Example: '{"type": "FILTER", "parameters": {"condition": "age > 18"}}'
    """
    try:
        # Parse operation JSON
        try:
            operation_dict = json.loads(operation)
        except json.JSONDecodeError as e:
            raise click.ClickException(f"Invalid operation JSON: {e}")

        # Validate operation structure
        if not isinstance(operation_dict, dict):
            raise click.ClickException("Operation must be a JSON object")
        if 'type' not in operation_dict:
            raise click.ClickException("Operation must have 'type' field")
        if 'parameters' not in operation_dict:
            raise click.ClickException("Operation must have 'parameters' field")

        # Get session to retrieve asset_id
        session_data = api_client.get(f'transformation/wrangling/{session_id}/')
        asset_id = session_data.get('asset_id')

        if not asset_id:
            raise click.ClickException("Session does not have an associated asset")

        # API endpoint: /api/v1/transformation/wrangling/
        result = api_client.post(
            'transformation/wrangling/',
            json_data={
                'asset_id': asset_id,
                'operation': operation_dict,
                'session_id': session_id
            }
        )

        if output_format == 'json':
            click.echo(json.dumps(result, indent=2))
        else:
            click.echo("Operation applied successfully!")
            click.echo(f"Session ID: {result.get('session_id')}")
            click.echo(f"Operation ID: {result.get('operation_id')}")
            click.echo(f"Applied operations: {result.get('applied_operations_count', 0)}")
            click.echo(f"Can undo: {result.get('can_undo', False)}")
            click.echo(f"Can redo: {result.get('can_redo', False)}")
            if result.get('result'):
                result_data = result.get('result', {})
                if 'sample_data' in result_data:
                    sample_rows = len(result_data.get('sample_data', []))
                    click.echo(f"Sample data: {sample_rows} rows")
                if 'row_count' in result_data:
                    click.echo(f"Row count: {result_data.get('row_count')}")
            if result.get('wrangling_script'):
                click.echo(f"\nWrangling script:\n{result.get('wrangling_script')}")
    except click.ClickException:
        raise
    except Exception as e:
        raise click.ClickException(f"Failed to apply wrangling operation: {e}")


@wrangling.command('undo')
@click.argument('session_id')
@click.option('--format', 'output_format', type=click.Choice(['json', 'table']), default='table', help='Output format')
def undo_wrangling(session_id: str, output_format: str):
    """Undo the last operation in a wrangling session"""
    try:
        # API endpoint: /api/v1/transformation/wrangling/{session_id}/undo/
        result = api_client.post(f'transformation/wrangling/{session_id}/undo/')

        if output_format == 'json':
            click.echo(json.dumps(result, indent=2))
        else:
            click.echo("Operation undone successfully!")
            click.echo(f"Session ID: {result.get('session_id')}")
            if result.get('undone_operation'):
                undone_op = result.get('undone_operation', {})
                click.echo(f"Undone operation type: {undone_op.get('type', 'N/A')}")
            click.echo(f"Applied operations: {result.get('applied_operations_count', 0)}")
            click.echo(f"Can undo: {result.get('can_undo', False)}")
            click.echo(f"Can redo: {result.get('can_redo', False)}")
    except click.ClickException:
        raise
    except Exception as e:
        raise click.ClickException(f"Failed to undo wrangling operation: {e}")


@wrangling.command('redo')
@click.argument('session_id')
@click.option('--format', 'output_format', type=click.Choice(['json', 'table']), default='table', help='Output format')
def redo_wrangling(session_id: str, output_format: str):
    """Redo the next operation in a wrangling session"""
    try:
        # API endpoint: /api/v1/transformation/wrangling/{session_id}/redo/
        result = api_client.post(f'transformation/wrangling/{session_id}/redo/')

        if output_format == 'json':
            click.echo(json.dumps(result, indent=2))
        else:
            click.echo("Operation redone successfully!")
            click.echo(f"Session ID: {result.get('session_id')}")
            if result.get('redone_operation'):
                redone_op = result.get('redone_operation', {})
                click.echo(f"Redone operation type: {redone_op.get('type', 'N/A')}")
            click.echo(f"Applied operations: {result.get('applied_operations_count', 0)}")
            click.echo(f"Can undo: {result.get('can_undo', False)}")
            click.echo(f"Can redo: {result.get('can_redo', False)}")
    except click.ClickException:
        raise
    except Exception as e:
        raise click.ClickException(f"Failed to redo wrangling operation: {e}")


@wrangling.command('get')
@click.argument('session_id')
@click.option('--format', 'output_format', type=click.Choice(['json', 'table']), default='table', help='Output format')
def get_wrangling(session_id: str, output_format: str):
    """Get detailed information about a wrangling session"""
    try:
        # API endpoint: /api/v1/transformation/wrangling/{session_id}/
        data = api_client.get(f'transformation/wrangling/{session_id}/')

        if output_format == 'json':
            click.echo(json.dumps(data, indent=2))
        else:
            click.echo(f"Session ID: {data.get('id')}")
            click.echo(f"Name: {data.get('name', 'N/A')}")
            if data.get('description'):
                click.echo(f"Description: {data.get('description')}")
            click.echo(f"Asset ID: {data.get('asset_id')}")
            if data.get('asset_name'):
                click.echo(f"Asset Name: {data.get('asset_name')}")
            click.echo(f"Applied operations: {data.get('applied_operations_count', 0)}")
            click.echo(f"History position: {data.get('history_position', -1)}")
            click.echo(f"Can undo: {data.get('can_undo', False)}")
            click.echo(f"Can redo: {data.get('can_redo', False)}")
            if data.get('operation_history'):
                history = data.get('operation_history', [])
                click.echo(f"\nOperation history ({len(history)} operations):")
                for i, op in enumerate(history[:10]):  # Show first 10 operations
                    op_type = op.get('type', 'UNKNOWN')
                    op_timestamp = op.get('timestamp', 'N/A')
                    click.echo(f"  {i+1}. {op_type} ({op_timestamp})")
                if len(history) > 10:
                    click.echo(f"  ... and {len(history) - 10} more operations")
            if data.get('wrangling_script'):
                click.echo(f"\nWrangling script:\n{data.get('wrangling_script')}")
            if data.get('current_state'):
                click.echo(f"\nCurrent state: {json.dumps(data.get('current_state'), indent=2)}")
            click.echo(f"Created: {data.get('created_at')}")
            click.echo(f"Updated: {data.get('updated_at')}")
    except click.ClickException:
        raise
    except Exception as e:
        raise click.ClickException(f"Failed to get wrangling session: {e}")
