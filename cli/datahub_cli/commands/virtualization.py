"""
Virtualization management commands.
"""
import click
import json
import os
from typing import Optional, Dict, Any
from ..api_client import api_client


@click.group()
def virtualization():
    """Virtualization management commands"""
    pass


@virtualization.command('info')
@click.option('--format', 'output_format', type=click.Choice(['json', 'table']), default='table', help='Output format')
def virtualization_info(output_format: str):
    """Get virtualization information"""
    try:
        data = {
            "status": "available",
            "message": "Virtualization command module is registered and functional"
        }

        if output_format == 'json':
            click.echo(json.dumps(data, indent=2))
        else:
            click.echo("Status: Available")
            click.echo("Message: Virtualization command module is registered and functional")
    except click.ClickException:
        raise
    except Exception as e:
        raise click.ClickException(f"Failed to get virtualization info: {e}")


@virtualization.group('datasets')
def datasets():
    """Virtual dataset management commands"""
    pass


@datasets.command('list')
@click.option('--status', type=click.Choice(['DRAFT', 'ACTIVE', 'INACTIVE', 'ARCHIVED']), help='Filter by status')
@click.option('--query-type', type=click.Choice(['SQL', 'SPARQL', 'FEDERATED', 'GRAPHQL', 'REST']), help='Filter by query type')
@click.option('--owner', help='Filter by owner/created_by user ID')
@click.option('--search', help='Search in name, description, and query fields')
@click.option('--ordering', help='Order by field (name, query_type, status, version, created_at, updated_at). Prefix with - for descending')
@click.option('--page', type=int, default=1, help='Page number (default: 1)')
@click.option('--page-size', type=int, default=20, help='Page size (default: 20, max: 100)')
@click.option('--format', 'output_format', type=click.Choice(['json', 'table']), default='table', help='Output format')
def list_datasets(
    status: Optional[str],
    query_type: Optional[str],
    owner: Optional[str],
    search: Optional[str],
    ordering: Optional[str],
    page: int,
    page_size: int,
    output_format: str
):
    """List virtual datasets with filtering and pagination"""
    try:
        # Build query parameters
        params: Dict[str, Any] = {
            'page': page,
            'page_size': min(page_size, 100)  # Enforce max page size
        }

        if status:
            params['status'] = status
        if query_type:
            params['query_type'] = query_type
        if owner:
            params['owner'] = owner
        if search:
            params['search'] = search
        if ordering:
            params['ordering'] = ordering

        # API endpoint: /api/v1/virtualization/datasets/
        data = api_client.get('virtualization/datasets/', params=params)

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
                click.echo("No virtual datasets found.")
                return

            # Table format
            click.echo(f"{'ID':<40} {'Name':<30} {'Query Type':<12} {'Status':<12} {'Version':<15} {'Created':<20}")
            click.echo("-" * 149)
            for dataset_item in results:
                if not isinstance(dataset_item, dict):
                    continue
                dataset_id = dataset_item.get('id', '')[:36] if dataset_item.get('id') else 'N/A'
                name = (dataset_item.get('name', '')[:28] + '..') if len(dataset_item.get('name', '')) > 30 else dataset_item.get('name', 'N/A')
                query_type_val = dataset_item.get('query_type', 'N/A')
                status_val = dataset_item.get('status', 'N/A')
                version_val = dataset_item.get('version', 'N/A')
                created = dataset_item.get('created_at', '')[:19] if dataset_item.get('created_at') else 'N/A'
                click.echo(f"{dataset_id:<40} {name:<30} {query_type_val:<12} {status_val:<12} {version_val:<15} {created:<20}")

            # Show pagination info
            if count > len(results):
                click.echo(f"\nShowing {len(results)} of {count} virtual datasets")
                if next_page:
                    click.echo(f"Next page: --page {page + 1}")
                if previous_page:
                    click.echo(f"Previous page: --page {page - 1}")
    except click.ClickException:
        raise
    except Exception as e:
        raise click.ClickException(f"Failed to list virtual datasets: {e}")


@datasets.command('create')
@click.option('--file', 'file_path', required=True, type=click.Path(exists=True, readable=True), help='Path to dataset definition JSON file (required)')
@click.option('--format', 'output_format', type=click.Choice(['json', 'table']), default='table', help='Output format')
def create_dataset(file_path: str, output_format: str):
    """Create a new virtual dataset from a JSON file"""
    try:
        # Read and parse dataset definition file
        if not os.path.exists(file_path):
            raise click.ClickException(f"File not found: {file_path}")

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                dataset_data = json.load(f)
        except json.JSONDecodeError as e:
            raise click.ClickException(f"Invalid JSON in file: {e}")
        except Exception as e:
            raise click.ClickException(f"Failed to read file: {e}")

        # Validate dataset_data structure
        if not isinstance(dataset_data, dict):
            raise click.ClickException("Dataset definition must be a JSON object")

        # Validate required fields
        if 'name' not in dataset_data:
            raise click.ClickException("Dataset definition must contain 'name' field")
        if 'query' not in dataset_data:
            raise click.ClickException("Dataset definition must contain 'query' field")
        if 'query_type' not in dataset_data:
            raise click.ClickException("Dataset definition must contain 'query_type' field")

        # Validate query_type
        valid_query_types = ['SQL', 'SPARQL', 'FEDERATED', 'GRAPHQL', 'REST']
        query_type = dataset_data.get('query_type', '').upper()
        if query_type not in valid_query_types:
            raise click.ClickException(f"Invalid query_type: {query_type}. Must be one of: {', '.join(valid_query_types)}")

        # Build request data
        data: Dict[str, Any] = {
            'name': dataset_data['name'].strip(),
            'query': dataset_data['query'],
            'query_type': query_type
        }

        # Add optional fields
        if 'description' in dataset_data:
            data['description'] = dataset_data['description']
        if 'schema' in dataset_data:
            data['schema'] = dataset_data['schema']
        if 'sources' in dataset_data:
            data['sources'] = dataset_data['sources']
        if 'version' in dataset_data:
            data['version'] = dataset_data['version']
        if 'status' in dataset_data:
            data['status'] = dataset_data['status']

        # API endpoint: /api/v1/virtualization/datasets/
        result = api_client.post('virtualization/datasets/', json_data=data)

        if output_format == 'json':
            click.echo(json.dumps(result, indent=2))
        else:
            click.echo("Virtual dataset created successfully!")
            click.echo(f"Dataset ID: {result.get('id')}")
            click.echo(f"Name: {result.get('name')}")
            click.echo(f"Query Type: {result.get('query_type')}")
            click.echo(f"Status: {result.get('status')}")
            if result.get('description'):
                click.echo(f"Description: {result.get('description')}")
            if result.get('version'):
                click.echo(f"Version: {result.get('version')}")
            click.echo(f"Created: {result.get('created_at')}")
    except click.ClickException:
        raise
    except Exception as e:
        raise click.ClickException(f"Failed to create virtual dataset: {e}")


@datasets.command('get')
@click.argument('dataset_id')
@click.option('--format', 'output_format', type=click.Choice(['json', 'table']), default='table', help='Output format')
def get_dataset(dataset_id: str, output_format: str):
    """Get virtual dataset details by ID"""
    try:
        # API endpoint: /api/v1/virtualization/datasets/{id}/
        data = api_client.get(f'virtualization/datasets/{dataset_id}/')

        if output_format == 'json':
            click.echo(json.dumps(data, indent=2))
        else:
            click.echo(f"Dataset ID: {data.get('id')}")
            click.echo(f"Name: {data.get('name')}")
            click.echo(f"Query Type: {data.get('query_type')}")
            click.echo(f"Status: {data.get('status')}")
            if data.get('description'):
                click.echo(f"Description: {data.get('description')}")
            if data.get('query'):
                click.echo(f"Query: {data.get('query')}")
            if data.get('version'):
                click.echo(f"Version: {data.get('version')}")
            if data.get('schema'):
                click.echo(f"Schema: {json.dumps(data.get('schema'), indent=2)}")
            if data.get('sources'):
                click.echo(f"Sources: {json.dumps(data.get('sources'), indent=2)}")
            if data.get('created_by'):
                click.echo(f"Created By: {data.get('created_by')}")
            click.echo(f"Created: {data.get('created_at')}")
            click.echo(f"Updated: {data.get('updated_at')}")
    except click.ClickException:
        raise
    except Exception as e:
        raise click.ClickException(f"Failed to get virtual dataset: {e}")


@datasets.command('update')
@click.argument('dataset_id')
@click.option('--file', 'file_path', required=True, type=click.Path(exists=True, readable=True), help='Path to dataset definition JSON file (required)')
@click.option('--format', 'output_format', type=click.Choice(['json', 'table']), default='table', help='Output format')
def update_dataset(dataset_id: str, file_path: str, output_format: str):
    """Update an existing virtual dataset from a JSON file"""
    try:
        # Read and parse dataset definition file
        if not os.path.exists(file_path):
            raise click.ClickException(f"File not found: {file_path}")

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                dataset_data = json.load(f)
        except json.JSONDecodeError as e:
            raise click.ClickException(f"Invalid JSON in file: {e}")
        except Exception as e:
            raise click.ClickException(f"Failed to read file: {e}")

        # Validate dataset_data structure
        if not isinstance(dataset_data, dict):
            raise click.ClickException("Dataset definition must be a JSON object")

        # Validate query_type if provided
        if 'query_type' in dataset_data:
            valid_query_types = ['SQL', 'SPARQL', 'FEDERATED', 'GRAPHQL', 'REST']
            query_type = dataset_data.get('query_type', '').upper()
            if query_type not in valid_query_types:
                raise click.ClickException(f"Invalid query_type: {query_type}. Must be one of: {', '.join(valid_query_types)}")

        # Build request data (only include provided fields)
        data: Dict[str, Any] = {}

        if 'name' in dataset_data:
            data['name'] = dataset_data['name'].strip()
        if 'description' in dataset_data:
            data['description'] = dataset_data['description']
        if 'query' in dataset_data:
            data['query'] = dataset_data['query']
        if 'query_type' in dataset_data:
            data['query_type'] = dataset_data['query_type'].upper()
        if 'schema' in dataset_data:
            data['schema'] = dataset_data['schema']
        if 'sources' in dataset_data:
            data['sources'] = dataset_data['sources']
        if 'version' in dataset_data:
            data['version'] = dataset_data['version']
        if 'status' in dataset_data:
            data['status'] = dataset_data['status']

        if not data:
            raise click.ClickException("At least one field must be provided for update")

        # API endpoint: /api/v1/virtualization/datasets/{id}/
        result = api_client.patch(f'virtualization/datasets/{dataset_id}/', json_data=data)

        if output_format == 'json':
            click.echo(json.dumps(result, indent=2))
        else:
            click.echo("Virtual dataset updated successfully!")
            click.echo(f"Dataset ID: {result.get('id')}")
            click.echo(f"Name: {result.get('name')}")
            click.echo(f"Query Type: {result.get('query_type')}")
            click.echo(f"Status: {result.get('status')}")
            if result.get('description'):
                click.echo(f"Description: {result.get('description')}")
            if result.get('version'):
                click.echo(f"Version: {result.get('version')}")
            click.echo(f"Updated: {result.get('updated_at')}")
    except click.ClickException:
        raise
    except Exception as e:
        raise click.ClickException(f"Failed to update virtual dataset: {e}")


@datasets.command('delete')
@click.argument('dataset_id')
@click.option('--format', 'output_format', type=click.Choice(['json', 'table']), default='table', help='Output format')
@click.confirmation_option(prompt='Are you sure you want to delete this virtual dataset?')
def delete_dataset(dataset_id: str, output_format: str):
    """Delete a virtual dataset"""
    try:
        # API endpoint: /api/v1/virtualization/datasets/{id}/
        result = api_client.delete(f'virtualization/datasets/{dataset_id}/')

        if output_format == 'json':
            click.echo(json.dumps(result, indent=2))
        else:
            click.echo("Virtual dataset deleted successfully!")
            if result and isinstance(result, dict):
                if result.get('id'):
                    click.echo(f"Deleted dataset ID: {result.get('id')}")
    except click.ClickException:
        raise
    except Exception as e:
        raise click.ClickException(f"Failed to delete virtual dataset: {e}")


@virtualization.group('queries')
def queries():
    """Query execution management commands"""
    pass


@queries.command('execute')
@click.argument('dataset_id')
@click.option('--query', 'query_string', help='Query string to execute (optional, uses dataset query if not provided)')
@click.option('--parameters', help='Query parameters as JSON string')
@click.option('--execution-mode', type=click.Choice(['SYNC', 'ASYNC', 'SCHEDULED', 'MANUAL', 'AUTOMATED']), help='Execution mode')
@click.option('--force-async', is_flag=True, help='Force asynchronous execution even for small queries')
@click.option('--timeout-seconds', type=int, help='Query timeout in seconds (default: 300 for sync, 3600 for async)')
@click.option('--format', 'output_format', type=click.Choice(['json', 'table']), default='table', help='Output format')
def execute_query(
    dataset_id: str,
    query_string: Optional[str],
    parameters: Optional[str],
    execution_mode: Optional[str],
    force_async: bool,
    timeout_seconds: Optional[int],
    output_format: str
):
    """Execute a query on a virtual dataset"""
    try:
        # Build request data
        data: Dict[str, Any] = {}

        if query_string:
            data['query'] = query_string
        if parameters:
            try:
                data['parameters'] = json.loads(parameters)
            except json.JSONDecodeError:
                raise click.ClickException(f"Invalid JSON in --parameters: {parameters}")
        if execution_mode:
            data['execution_mode'] = execution_mode
        if force_async:
            data['force_async'] = True
        if timeout_seconds:
            if timeout_seconds < 1 or timeout_seconds > 86400:
                raise click.ClickException("Timeout must be between 1 and 86400 seconds")
            data['timeout_seconds'] = timeout_seconds

        # API endpoint: /api/v1/virtualization/datasets/{id}/queries/
        result = api_client.post(f'virtualization/datasets/{dataset_id}/queries/', json_data=data)

        if output_format == 'json':
            click.echo(json.dumps(result, indent=2))
        else:
            click.echo("Query execution started successfully!")
            click.echo(f"Execution ID: {result.get('id')}")
            click.echo(f"Status: {result.get('status')}")
            click.echo(f"Execution Mode: {result.get('execution_mode')}")
            if result.get('virtual_dataset_name'):
                click.echo(f"Dataset: {result.get('virtual_dataset_name')}")
            if result.get('started_at'):
                click.echo(f"Started: {result.get('started_at')}")
    except click.ClickException:
        raise
    except Exception as e:
        raise click.ClickException(f"Failed to execute query: {e}")


@queries.command('list')
@click.option('--dataset-id', 'dataset_id', help='Filter by virtual dataset ID')
@click.option('--status', type=click.Choice(['PENDING', 'RUNNING', 'COMPLETED', 'FAILED', 'CANCELLED']), help='Filter by status')
@click.option('--page', type=int, default=1, help='Page number (default: 1)')
@click.option('--page-size', type=int, default=20, help='Page size (default: 20, max: 100)')
@click.option('--format', 'output_format', type=click.Choice(['json', 'table']), default='table', help='Output format')
def list_queries(
    dataset_id: Optional[str],
    status: Optional[str],
    page: int,
    page_size: int,
    output_format: str
):
    """List query executions with filtering and pagination"""
    try:
        # Build query parameters
        params: Dict[str, Any] = {
            'page': page,
            'page_size': min(page_size, 100)  # Enforce max page size
        }

        if dataset_id:
            params['virtual_dataset_id'] = dataset_id
        if status:
            params['status'] = status

        # API endpoint: /api/v1/virtualization/queries/
        data = api_client.get('virtualization/queries/', params=params)

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
                click.echo("No query executions found.")
                return

            # Table format
            click.echo(f"{'ID':<40} {'Dataset':<30} {'Status':<12} {'Mode':<12} {'Started':<20}")
            click.echo("-" * 114)
            for query_item in results:
                if not isinstance(query_item, dict):
                    continue
                query_id = query_item.get('id', '')[:36] if query_item.get('id') else 'N/A'
                dataset_name = (query_item.get('virtual_dataset_name', '')[:28] + '..') if len(query_item.get('virtual_dataset_name', '')) > 30 else query_item.get('virtual_dataset_name', 'N/A')
                status_val = query_item.get('status', 'N/A')
                mode_val = query_item.get('execution_mode', 'N/A')
                started = query_item.get('started_at', '')[:19] if query_item.get('started_at') else 'N/A'
                click.echo(f"{query_id:<40} {dataset_name:<30} {status_val:<12} {mode_val:<12} {started:<20}")

            # Show pagination info
            if count > len(results):
                click.echo(f"\nShowing {len(results)} of {count} query executions")
                if next_page:
                    click.echo(f"Next page: --page {page + 1}")
                if previous_page:
                    click.echo(f"Previous page: --page {page - 1}")
    except click.ClickException:
        raise
    except Exception as e:
        raise click.ClickException(f"Failed to list query executions: {e}")


@queries.command('get')
@click.argument('execution_id')
@click.option('--format', 'output_format', type=click.Choice(['json', 'table']), default='table', help='Output format')
def get_query(execution_id: str, output_format: str):
    """Get query execution details by ID"""
    try:
        # API endpoint: /api/v1/virtualization/queries/{id}/
        data = api_client.get(f'virtualization/queries/{execution_id}/')

        if output_format == 'json':
            click.echo(json.dumps(data, indent=2))
        else:
            click.echo(f"Execution ID: {data.get('id')}")
            click.echo(f"Status: {data.get('status')}")
            click.echo(f"Execution Mode: {data.get('execution_mode')}")
            if data.get('virtual_dataset_name'):
                click.echo(f"Dataset: {data.get('virtual_dataset_name')}")
            if data.get('query'):
                click.echo(f"Query: {data.get('query')}")
            if data.get('parameters'):
                click.echo(f"Parameters: {json.dumps(data.get('parameters'), indent=2)}")
            if data.get('started_at'):
                click.echo(f"Started: {data.get('started_at')}")
            if data.get('completed_at'):
                click.echo(f"Completed: {data.get('completed_at')}")
            if data.get('metrics'):
                click.echo(f"Metrics: {json.dumps(data.get('metrics'), indent=2)}")
            if data.get('execution_log'):
                click.echo(f"Execution Log: {data.get('execution_log')}")
    except click.ClickException:
        raise
    except Exception as e:
        raise click.ClickException(f"Failed to get query execution: {e}")


@queries.command('cancel')
@click.argument('execution_id')
@click.option('--format', 'output_format', type=click.Choice(['json', 'table']), default='table', help='Output format')
def cancel_query(execution_id: str, output_format: str):
    """Cancel a running or pending query execution"""
    try:
        # API endpoint: /api/v1/virtualization/queries/{id}/cancel/
        result = api_client.post(f'virtualization/queries/{execution_id}/cancel/')

        if output_format == 'json':
            click.echo(json.dumps(result, indent=2))
        else:
            click.echo("Query execution cancelled successfully!")
            if result and isinstance(result, dict):
                if result.get('execution_id'):
                    click.echo(f"Execution ID: {result.get('execution_id')}")
                if result.get('status'):
                    click.echo(f"Status: {result.get('status')}")
                if result.get('message'):
                    click.echo(f"Message: {result.get('message')}")
    except click.ClickException:
        raise
    except Exception as e:
        raise click.ClickException(f"Failed to cancel query execution: {e}")


@queries.command('result')
@click.argument('execution_id')
@click.option('--format', 'output_format', type=click.Choice(['json', 'csv', 'parquet']), default='json', help='Result output format (default: json)')
@click.option('--page', type=int, help='Page number (for paginated results)')
@click.option('--page-size', type=int, help='Page size (for paginated results)')
@click.option('--output', 'output_file', type=click.Path(), help='Save result to file (for CSV/Parquet formats)')
def get_result(
    execution_id: str,
    output_format: str,
    page: Optional[int],
    page_size: Optional[int],
    output_file: Optional[str]
):
    """Get query execution result in specified format"""
    try:
        # Build query parameters
        params: Dict[str, Any] = {
            'output_format': output_format
        }

        if page:
            params['page'] = page
        if page_size:
            params['page_size'] = page_size

        # API endpoint: /api/v1/virtualization/queries/{id}/result/
        result = api_client.get(f'virtualization/queries/{execution_id}/result/', params=params)

        # Handle different output formats
        if output_format == 'json':
            # JSON format - output directly
            if output_file:
                with open(output_file, 'w', encoding='utf-8') as f:
                    json.dump(result, f, indent=2)
                click.echo(f"Result saved to {output_file}")
            else:
                click.echo(json.dumps(result, indent=2))
        elif output_format == 'csv':
            # CSV format - result should contain CSV data
            if output_file:
                # Save to file
                if isinstance(result, dict) and 'data' in result:
                    # If result is a dict with 'data' field containing CSV string
                    csv_data = result.get('data', '')
                    if isinstance(csv_data, str):
                        with open(output_file, 'w', encoding='utf-8') as f:
                            f.write(csv_data)
                    else:
                        # If data is a list, convert to CSV
                        import csv
                        with open(output_file, 'w', encoding='utf-8', newline='') as f:
                            if csv_data and len(csv_data) > 0:
                                first_row = csv_data[0]
                                if isinstance(first_row, dict):
                                    writer = csv.DictWriter(f, fieldnames=first_row.keys())
                                    writer.writeheader()
                                    for row in csv_data:
                                        writer.writerow(row if isinstance(row, dict) else {'value': row})
                                else:
                                    # If not a dict, write as simple CSV
                                    writer = csv.writer(f)
                                    for row in csv_data:
                                        writer.writerow([row] if not isinstance(row, (list, tuple)) else row)
                else:
                    # If result is already a string
                    with open(output_file, 'w', encoding='utf-8') as f:
                        f.write(str(result))
                click.echo(f"Result saved to {output_file}")
            else:
                # Output to stdout
                if isinstance(result, dict) and 'data' in result:
                    click.echo(result.get('data', ''))
                else:
                    click.echo(str(result))
        elif output_format == 'parquet':
            # Parquet format - must save to file
            if not output_file:
                raise click.ClickException("--output is required for parquet format")

            # Parquet data is typically returned as base64-encoded bytes or file path
            if isinstance(result, dict) and 'data' in result:
                parquet_data = result.get('data', '')
                if isinstance(parquet_data, str):
                    # If base64 encoded, decode it
                    import base64
                    try:
                        decoded_data = base64.b64decode(parquet_data)
                        with open(output_file, 'wb') as f:
                            f.write(decoded_data)
                        click.echo(f"Result saved to {output_file}")
                    except Exception:
                        # If not base64, treat as file path or error
                        raise click.ClickException(f"Failed to decode parquet data: {parquet_data[:100]}")
                else:
                    # If bytes, write directly
                    with open(output_file, 'wb') as f:
                        f.write(parquet_data)
                    click.echo(f"Result saved to {output_file}")
            else:
                raise click.ClickException("Parquet format not supported or result format unexpected")
    except click.ClickException:
        raise
    except Exception as e:
            raise click.ClickException(f"Failed to get query result: {e}")


@virtualization.group('topology')
def topology():
    """Virtualization topology management commands"""
    pass


@topology.command('get')
@click.option('--include-health-metrics/--no-include-health-metrics', default=True, help='Include health metrics in response (default: true)')
@click.option('--format', 'output_format', type=click.Choice(['json', 'table']), default='table', help='Output format')
def get_topology(include_health_metrics: bool, output_format: str):
    """Get complete virtualization topology including all virtual datasets, relationships, and health metrics"""
    try:
        # Build query parameters
        params: Dict[str, Any] = {
            'include_health_metrics': str(include_health_metrics).lower()
        }

        # API endpoint: /api/v1/virtualization/topology/
        data = api_client.get('virtualization/topology/', params=params)

        if output_format == 'json':
            click.echo(json.dumps(data, indent=2))
        else:
            # Table format - display summary and key information
            summary = data.get('summary', {})
            metadata = data.get('metadata', {})
            nodes = data.get('nodes', [])
            edges = data.get('edges', [])

            click.echo("=" * 80)
            click.echo("VIRTUALIZATION TOPOLOGY SUMMARY")
            click.echo("=" * 80)
            click.echo(f"Total Datasets: {summary.get('total_datasets', 0)}")
            click.echo(f"Active Datasets: {summary.get('active_datasets', 0)}")
            click.echo(f"Total Relationships: {summary.get('total_relationships', 0)}")
            avg_health = summary.get('average_health_score')
            if avg_health is not None:
                click.echo(f"Average Health Score: {avg_health:.2f}")
            else:
                click.echo("Average Health Score: N/A")

            if metadata.get('generated_at'):
                click.echo(f"Generated At: {metadata.get('generated_at')}")

            click.echo("\n" + "=" * 80)
            click.echo("VIRTUAL DATASETS")
            click.echo("=" * 80)

            if not nodes:
                click.echo("No virtual datasets found.")
            else:
                click.echo(f"{'ID':<40} {'Name':<30} {'Query Type':<15} {'Status':<12} {'Health Score':<15}")
                click.echo("-" * 112)
                for node in nodes:
                    if not isinstance(node, dict):
                        continue
                    node_id = str(node.get('id', ''))[:36] if node.get('id') else 'N/A'
                    name = (node.get('name', '')[:28] + '..') if len(node.get('name', '')) > 30 else node.get('name', 'N/A')
                    query_type = node.get('query_type', 'N/A')
                    status = node.get('status', 'N/A')
                    health_metrics = node.get('health_metrics', {})
                    health_score = health_metrics.get('health_score') if health_metrics else None
                    health_str = f"{health_score:.2f}" if health_score is not None else "N/A"
                    click.echo(f"{node_id:<40} {name:<30} {query_type:<15} {status:<12} {health_str:<15}")

            click.echo("\n" + "=" * 80)
            click.echo("RELATIONSHIPS")
            click.echo("=" * 80)

            if not edges:
                click.echo("No relationships found.")
            else:
                click.echo(f"{'Source Dataset ID':<40} {'Target Dataset ID':<40} {'Type':<20} {'Weight':<10}")
                click.echo("-" * 110)
                for edge in edges:
                    if not isinstance(edge, dict):
                        continue
                    source = str(edge.get('source', ''))[:36] if edge.get('source') else 'N/A'
                    target = str(edge.get('target', ''))[:36] if edge.get('target') else 'N/A'
                    rel_type = edge.get('type', 'N/A')
                    weight = edge.get('weight', 'N/A')
                    click.echo(f"{source:<40} {target:<40} {rel_type:<20} {weight:<10}")
    except click.ClickException:
        raise
    except Exception as e:
        raise click.ClickException(f"Failed to get virtualization topology: {e}")


@topology.command('get-dataset')
@click.argument('dataset_id')
@click.option('--format', 'output_format', type=click.Choice(['json', 'table']), default='table', help='Output format')
def get_dataset_topology(dataset_id: str, output_format: str):
    """Get topology view for a specific virtual dataset including its relationships and health metrics"""
    try:
        # API endpoint: /api/v1/virtualization/topology/{dataset_id}/
        data = api_client.get(f'virtualization/topology/{dataset_id}/')

        if output_format == 'json':
            click.echo(json.dumps(data, indent=2))
        else:
            # Table format - display dataset and relationships
            dataset = data.get('dataset', {})
            relationships = data.get('relationships', [])
            health_metrics = data.get('health_metrics', {})

            click.echo("=" * 80)
            click.echo("VIRTUAL DATASET TOPOLOGY")
            click.echo("=" * 80)

            # Dataset information
            click.echo("\nDataset Information:")
            click.echo(f"  ID: {dataset.get('id', 'N/A')}")
            click.echo(f"  Name: {dataset.get('name', 'N/A')}")
            if dataset.get('description'):
                click.echo(f"  Description: {dataset.get('description')}")
            click.echo(f"  Query Type: {dataset.get('query_type', 'N/A')}")
            click.echo(f"  Status: {dataset.get('status', 'N/A')}")
            click.echo(f"  Version: {dataset.get('version', 'N/A')}")
            if dataset.get('created_at'):
                click.echo(f"  Created: {dataset.get('created_at')}")
            if dataset.get('updated_at'):
                click.echo(f"  Updated: {dataset.get('updated_at')}")

            # Health metrics
            if health_metrics:
                click.echo("\nHealth Metrics:")
                health_score = health_metrics.get('health_score')
                if health_score is not None:
                    click.echo(f"  Health Score: {health_score:.2f}")
                else:
                    click.echo("  Health Score: N/A")

                total_executions = health_metrics.get('total_executions', 0)
                success_rate = health_metrics.get('success_rate')
                avg_duration_ms = health_metrics.get('avg_duration_ms')

                click.echo(f"  Total Executions: {total_executions}")
                if success_rate is not None:
                    click.echo(f"  Success Rate: {success_rate:.2f}%")
                else:
                    click.echo("  Success Rate: N/A")
                if avg_duration_ms is not None:
                    click.echo(f"  Average Duration: {avg_duration_ms:.2f} ms")
                else:
                    click.echo("  Average Duration: N/A")

            # Relationships
            click.echo("\n" + "=" * 80)
            click.echo("RELATIONSHIPS")
            click.echo("=" * 80)

            if not relationships:
                click.echo("No relationships found.")
            else:
                click.echo(f"{'Related Dataset ID':<40} {'Type':<20} {'Direction':<15} {'Weight':<10}")
                click.echo("-" * 85)
                for rel in relationships:
                    if not isinstance(rel, dict):
                        continue
                    related_id = str(rel.get('dataset_id', ''))[:36] if rel.get('dataset_id') else 'N/A'
                    rel_type = rel.get('type', 'N/A')
                    direction = rel.get('direction', 'N/A')
                    weight = rel.get('weight', 'N/A')
                    click.echo(f"{related_id:<40} {rel_type:<20} {direction:<15} {weight:<10}")
    except click.ClickException:
        raise
    except Exception as e:
        raise click.ClickException(f"Failed to get dataset topology: {e}")

