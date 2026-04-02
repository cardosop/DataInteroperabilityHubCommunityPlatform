"""
Contract management commands.
"""
import click
import json
import os
import yaml
from typing import Optional
from ..api_client import api_client
from ..odps_errors import (
    ODPSCLIError,
    ODPSValidationError,
    ODPSRefResolutionError,
    ODPSNormalizationError,
    ODPSExportError,
    ODPSLinkingError,
    ODPSParameterError,
    handle_api_error,
    validate_odps_version,
    validate_odcs_version,
    validate_contract_id,
    validate_file_format,
    validate_mutually_exclusive_options,
    validate_required_option,
)


@click.group()
def contracts():
    """Contract management commands"""
    pass


@contracts.command('list')
@click.option('--status', help='Filter by status (DRAFT, ACTIVE, ARCHIVED)')
@click.option('--asset-id', help='Filter by asset ID')
@click.option('--limit', type=int, default=20, help='Limit number of results')
@click.option('--offset', type=int, default=0, help='Offset for pagination')
@click.option('--format', 'output_format', type=click.Choice(['json', 'table']), default='table', help='Output format')
def list_contracts(status: Optional[str], asset_id: Optional[str], limit: int, offset: int, output_format: str):
    """List contracts"""
    params = {'limit': limit, 'offset': offset}
    if status:
        params['status'] = status
    if asset_id:
        params['asset_id'] = asset_id

    try:
        # API endpoint structure: /api/v1/contracts/ (contracts/ from api/urls.py + contracts from router)
        data = api_client.get('contracts/', params=params)
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
                click.echo("No contracts found.")
                return

            # Table format - include original_spec_type
            click.echo(f"{'ID':<40} {'Version':<10} {'Status':<15} {'Spec Type':<12} {'Asset ID':<40}")
            click.echo("-" * 117)
            for contract in results:
                spec_type = contract.get('original_spec_type', 'N/A')
                click.echo(
                    f"{contract.get('id', '')[:36]:<40} "
                    f"{contract.get('version', ''):<10} "
                    f"{contract.get('status', ''):<15} "
                    f"{spec_type:<12} "
                    f"{contract.get('asset_id', '')[:36] if contract.get('asset_id') else 'N/A':<40}"
                )
    except click.ClickException:
        raise
    except Exception as e:
        raise click.ClickException(f"Failed to list contracts: {e}")


@contracts.command('get')
@click.argument('contract_id')
@click.option('--format', 'output_format', type=click.Choice(['json', 'table']), default='table', help='Output format')
@click.option('--show-odps', is_flag=True, default=False, help='Show ODPS-specific fields (pricing plans, access methods)')
def get_contract(contract_id: str, output_format: str, show_odps: bool):
    """Get contract details"""
    try:
        # API endpoint: GET /api/v1/contracts/{id}/
        data = api_client.get(f'contracts/{contract_id}/')

        if output_format == 'json':
            click.echo(json.dumps(data, indent=2))
        else:
            # Table format
            click.echo(f"ID: {data.get('id')}")
            click.echo(f"Version: {data.get('version')}")
            click.echo(f"Status: {data.get('status')}")
            click.echo(f"Asset ID: {data.get('asset_id') or 'N/A'}")
            click.echo(f"Spec Type: {data.get('original_spec_type')}")
            click.echo(f"Format: {data.get('original_format')}")
            click.echo(f"Normalization Status: {data.get('normalization_status')}")
            if data.get('normalization_errors'):
                click.echo(f"Normalization Errors: {len(data.get('normalization_errors', []))}")
            if data.get('normalization_warnings'):
                click.echo(f"Normalization Warnings: {len(data.get('normalization_warnings', []))}")
            click.echo(f"Created: {data.get('created_at')}")
            click.echo(f"Updated: {data.get('updated_at')}")

            # Show ODPS-specific fields if requested
            if show_odps:
                _display_odps_fields(data)
    except click.ClickException:
        raise
    except Exception as e:
        raise click.ClickException(f"Failed to get contract: {e}")


def _detect_contract_spec_type(content: str, original_format: str) -> Optional[str]:
    """
    Detect contract specification type (ODPS or ODCS) from content.

    Uses the same detection logic as the backend spec_detection module.

    Args:
        content: Contract content as string
        original_format: Format of content ('JSON' or 'YAML')

    Returns:
        'ODPS' if ODPS contract detected, 'ODCS' if ODCS, None if cannot determine
    """
    try:
        # Parse content based on format
        if original_format.upper() == 'JSON':
            contract_data = json.loads(content)
        else:
            contract_data = yaml.safe_load(content)

        if not isinstance(contract_data, dict):
            return None

        # Check for ODPS indicators (from spec_detection.py logic)
        schema_url = contract_data.get("schema")
        if schema_url and isinstance(schema_url, str):
            schema_lower = schema_url.lower()
            if "opendataproducts.org/schema" in schema_lower:
                return "ODPS"
            if "schemas.opendataproducts.io/spec" in schema_lower:
                return "ODPS"
            if "open-data-product" in schema_lower:
                return "ODPS"

        # Check for product field (ODPS structure indicator)
        if "product" in contract_data:
            product = contract_data.get("product")
            if isinstance(product, dict) and "details" in product:
                return "ODPS"

        # Check for ODCS indicators (apiVersion and kind)
        if "apiVersion" in contract_data and "kind" in contract_data:
            return "ODCS"

        # Default to ODCS if no clear indicators
        return "ODCS"

    except (json.JSONDecodeError, yaml.YAMLError, Exception):
        # If parsing fails, cannot determine spec type
        return None


@contracts.command('create')
@click.option('--file', 'file_path', required=True, type=click.Path(exists=True), help='Path to contract file (YAML or JSON)')
@click.option('--asset-id', help='Asset ID to attach contract to')
@click.option('--spec-type', 'spec_type_override', type=click.Choice(['ODPS', 'ODCS']), help='Override auto-detected spec type (ODPS or ODCS)')
@click.option('--format', 'output_format', type=click.Choice(['json', 'table']), default='table', help='Output format')
def create_contract(file_path: str, asset_id: Optional[str], spec_type_override: Optional[str], output_format: str):
    """Create a new contract from file

    Automatically detects contract specification type (ODPS or ODCS) from content.
    Use --spec-type to override auto-detection.
    """
    # Read file
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        raise click.ClickException(f"Failed to read file: {e}")

    # Determine format
    if file_path.endswith('.json'):
        original_format = 'JSON'
    elif file_path.endswith('.yaml') or file_path.endswith('.yml'):
        original_format = 'YAML'
    else:
        # Try to detect format
        content_stripped = content.strip()
        if content_stripped.startswith('{'):
            original_format = 'JSON'
        else:
            original_format = 'YAML'

    # Auto-detect spec type if not overridden
    detected_spec_type = None
    if not spec_type_override:
        detected_spec_type = _detect_contract_spec_type(content, original_format)
        if detected_spec_type:
            click.echo(f"Auto-detected spec type: {detected_spec_type}", err=True)

    # Use override or detected spec type
    spec_type = spec_type_override or detected_spec_type

    data = {
        'original_raw': content,
        'original_format': original_format
    }
    if spec_type:
        data['original_spec_type'] = spec_type
    if asset_id:
        data['asset_id'] = asset_id

    try:
        # API endpoint: POST /api/v1/contracts/
        result = api_client.post('contracts/', json_data=data)

        if output_format == 'json':
            click.echo(json.dumps(result, indent=2))
        else:
            click.echo(f"Contract created successfully!")
            click.echo(f"ID: {result.get('id')}")
            click.echo(f"Version: {result.get('version')}")
            click.echo(f"Status: {result.get('status')}")
            click.echo(f"Spec Type: {result.get('original_spec_type', 'N/A')}")
            click.echo(f"Normalization Status: {result.get('normalization_status')}")
            if result.get('normalization_errors'):
                click.echo(f"Normalization Errors: {len(result.get('normalization_errors', []))}")
    except click.ClickException:
        raise
    except Exception as e:
        raise click.ClickException(f"Failed to create contract: {e}")


@contracts.command('validate')
@click.argument('contract_id')
@click.option('--format', 'output_format', type=click.Choice(['json', 'table']), default='table', help='Output format')
def validate_contract(contract_id: str, output_format: str):
    """Validate a contract"""
    try:
        # API endpoint structure: /api/v1/contracts/{id}/validate/ (contracts/ from api/urls.py + contracts from router)
        result = api_client.post(f'contracts/{contract_id}/validate/')

        if output_format == 'json':
            click.echo(json.dumps(result, indent=2))
        else:
            validation_status = result.get('validation_status', 'UNKNOWN')
            click.echo(f"Validation Status: {validation_status}")

            errors = result.get('errors', [])
            warnings = result.get('warnings', [])

            if errors:
                click.echo(f"\nErrors ({len(errors)}):")
                for error in errors[:10]:  # Show first 10
                    click.echo(f"  - {error}")
                if len(errors) > 10:
                    click.echo(f"  ... and {len(errors) - 10} more")

            if warnings:
                click.echo(f"\nWarnings ({len(warnings)}):")
                for warning in warnings[:10]:  # Show first 10
                    click.echo(f"  - {warning}")
                if len(warnings) > 10:
                    click.echo(f"  ... and {len(warnings) - 10} more")

            if not errors and not warnings:
                click.echo("Contract is valid!")
    except click.ClickException:
        raise
    except Exception as e:
        raise click.ClickException(f"Failed to validate contract: {e}")


@contracts.command('lint')
@click.argument('contract_id')
@click.option('--format', 'output_format', type=click.Choice(['json', 'table']), default='table', help='Output format')
def lint_contract(contract_id: str, output_format: str):
    """Lint a contract"""
    try:
        # API endpoint structure: /api/v1/contracts/{id}/lint/ (contracts/ from api/urls.py + contracts from router)
        result = api_client.post(f'contracts/{contract_id}/lint/')

        if output_format == 'json':
            click.echo(json.dumps(result, indent=2))
        else:
            lint_status = result.get('lint_status', 'UNKNOWN')
            click.echo(f"Lint Status: {lint_status}")

            issues = result.get('issues', [])
            if issues:
                click.echo(f"\nIssues ({len(issues)}):")
                for issue in issues[:20]:  # Show first 20
                    click.echo(f"  - {issue}")
                if len(issues) > 20:
                    click.echo(f"  ... and {len(issues) - 20} more")
            else:
                click.echo("No linting issues found!")
    except click.ClickException:
        raise
    except Exception as e:
        raise click.ClickException(f"Failed to lint contract: {e}")


@contracts.command('create-odps')
@click.option('--file', 'file_path', required=True, type=click.Path(exists=True), help='Path to ODPS file (YAML or JSON)')
@click.option('--extract-odcs', is_flag=True, default=False, help='Automatically extract ODCS from ODPS product.contract (Product-First flow)')
@click.option('--link-odcs', 'link_odcs_id', type=str, help='Link ODPS to existing ODCS contract by ID')
@click.option('--format', 'input_format', type=click.Choice(['YAML', 'JSON', 'yaml', 'json']), help='Input format (YAML or JSON). Auto-detected from file extension if not specified')
@click.option('--version', 'odps_version', type=str, help='ODPS version (e.g., 4.1). Used for validation/documentation. Version in document takes precedence')
@click.option('--resolve-external-refs/--no-resolve-external-refs', default=True, help='Resolve external $ref references (default: True)')
@click.option('--asset-id', help='Asset ID to attach contracts to')
@click.option('--output-format', 'output_format', type=click.Choice(['json', 'table']), default='table', help='Output format')
def create_odps(
    file_path: str,
    extract_odcs: bool,
    link_odcs_id: Optional[str],
    input_format: Optional[str],
    odps_version: Optional[str],
    resolve_external_refs: bool,
    asset_id: Optional[str],
    output_format: str
):
    """
    Create ODPS (Open Data Product Standard) contract.

    Supports two flows:
    1. Product-First flow (--extract-odcs): Automatically extracts ODCS from ODPS product.contract
    2. Link flow (--link-odcs <id>): Links ODPS to an existing ODCS contract

    These options are mutually exclusive.
    """
    try:
        # Validate parameters
        validate_mutually_exclusive_options('extract-odcs', extract_odcs, 'link-odcs', link_odcs_id)
        # Check that either extract_odcs or link_odcs_id is provided
        if not extract_odcs and not link_odcs_id:
            raise ODPSParameterError(
                message="Must specify either --extract-odcs or --link-odcs",
                error_code="MISSING_REQUIRED_OPTION",
                context={'extract_odcs': extract_odcs, 'link_odcs_id': link_odcs_id},
                suggestion="Provide either --extract-odcs or --link-odcs"
            )

        if link_odcs_id:
            validate_contract_id(link_odcs_id, 'odcs')

        if odps_version:
            validate_odps_version(odps_version)

        # Validate file format
        if input_format:
            original_format = input_format.upper()
        else:
            original_format = validate_file_format(file_path)

        # Read file
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except IOError as e:
            raise ODPSParameterError(
                message=f"Failed to read file: {file_path}",
                error_code="FILE_READ_ERROR",
                context={'file_path': file_path},
                suggestion="Check that the file exists and you have read permissions",
                original_error=e
            )

        if extract_odcs:
            # Product-First flow: Use /api/v1/contracts/products/ endpoint
            data = {
                'original_raw': content,
                'original_format': original_format,
                'resolve_external_refs': resolve_external_refs
            }
            if asset_id:
                data['asset_id'] = asset_id
            if odps_version:
                # Note: Version is typically in the document itself, but we can add it as metadata
                # The API will validate the version matches the document
                data['odps_version'] = odps_version

            try:
                # Use request() to get raw Response object so we can check status code
                response_obj = api_client.request('POST', 'contracts/products/', json_data=data, timeout=30)

                # Check status code
                if response_obj.status_code == 202:
                    # Async workflow - get workflow_instance_id from response
                    result = api_client._handle_response(response_obj)
                    workflow_instance_id = result.get('workflow_instance_id')
                elif response_obj.status_code == 201:
                    # Synchronous response (legacy compatibility)
                    result = api_client._handle_response(response_obj)
                    workflow_instance_id = None
                else:
                    # Error response
                    result = api_client._handle_response(response_obj)
                    workflow_instance_id = None
            except click.ClickException as e:
                # Try to parse as ODPS error
                error_msg = str(e)
                if 'API error' in error_msg:
                    # Extract error code and message
                    raise handle_api_error(error_msg, 400, 'contracts/products/')
                raise

            # Check if async workflow (202 Accepted)
            if workflow_instance_id:
                # Async workflow - poll for completion
                if not workflow_instance_id:
                    raise ODPSExportError(
                        message="Workflow started but no workflow_instance_id returned",
                        error_code="MISSING_WORKFLOW_ID",
                        context={'response': response_obj.json() if hasattr(response_obj, 'json') else str(response_obj)}
                    )

                if output_format == 'table':
                    click.echo(f"Product creation workflow started (async)")
                    click.echo(f"Workflow Instance ID: {workflow_instance_id}")
                    click.echo("Polling for completion...")

                # Poll for completion
                import time
                max_poll_time = 300  # 5 minutes max
                poll_interval = 2  # Poll every 2 seconds
                start_time = time.time()

                while time.time() - start_time < max_poll_time:
                    try:
                        status_result = api_client.get(f'contracts/products/workflows/{workflow_instance_id}/status/')
                        status = status_result.get('status')

                        if status == 'COMPLETED':
                            # Workflow completed - get results
                            result = status_result
                            break
                        elif status in ['FAILED', 'CANCELLED', 'ROLLED_BACK']:
                            error_msg = status_result.get('message') or f"Workflow {status.lower()}"
                            raise ODPSExportError(
                                message=f"Product creation workflow {status.lower()}: {error_msg}",
                                error_code="WORKFLOW_FAILED",
                                context={'workflow_instance_id': workflow_instance_id, 'status': status}
                            )
                        # Still running - continue polling
                        time.sleep(poll_interval)
                    except click.ClickException as e:
                        # If 404, workflow might not be ready yet
                        if '404' in str(e) or 'not found' in str(e).lower():
                            time.sleep(poll_interval)
                            continue
                        raise
                else:
                    # Timeout
                    raise ODPSExportError(
                        message=f"Workflow did not complete within {max_poll_time} seconds",
                        error_code="WORKFLOW_TIMEOUT",
                        context={'workflow_instance_id': workflow_instance_id},
                        suggestion=f"Check workflow status manually: contracts/products/workflows/{workflow_instance_id}/status/"
                    )
            else:
                # Synchronous response (shouldn't happen with new async API, but handle for compatibility)
                result = api_client._handle_response(response_obj)

            if output_format == 'json':
                click.echo(json.dumps(result, indent=2))
            else:
                odps_contract = result.get('odps_contract') or {}
                odcs_contract = result.get('odcs_contract') or {}
                workflow_id = result.get('workflow_instance_id')

                click.echo("ODPS product created successfully (Product-First flow)!")
                click.echo("\nODPS Contract:")
                click.echo(f"  ID: {odps_contract.get('id')}")
                click.echo(f"  Version: {odps_contract.get('version')}")
                click.echo(f"  Status: {odps_contract.get('status')}")
                click.echo(f"  Spec Type: {odps_contract.get('original_spec_type')}")
                click.echo(f"  Format: {odps_contract.get('original_format')}")
                click.echo(f"  Normalization Status: {odps_contract.get('normalization_status')}")

                click.echo("\nODCS Contract (extracted):")
                click.echo(f"  ID: {odcs_contract.get('id')}")
                click.echo(f"  Version: {odcs_contract.get('version')}")
                click.echo(f"  Status: {odcs_contract.get('status')}")
                click.echo(f"  Spec Type: {odcs_contract.get('original_spec_type')}")
                click.echo(f"  Normalization Status: {odcs_contract.get('normalization_status')}")

                if workflow_id:
                    click.echo(f"\nWorkflow Instance ID: {workflow_id}")

                if odps_contract.get('normalization_errors'):
                    click.echo(f"\nODPS Normalization Errors: {len(odps_contract.get('normalization_errors', []))}")
                if odcs_contract.get('normalization_errors'):
                    click.echo(f"ODCS Normalization Errors: {len(odcs_contract.get('normalization_errors', []))}")

        else:
            # Link flow: Use /api/v1/contracts/{odcs_id}/link-odps/ endpoint
            data = {
                'original_raw': content,
                'original_format': original_format,
                'resolve_external_refs': resolve_external_refs
            }
            if odps_version:
                data['odps_version'] = odps_version

            try:
                result = api_client.post(f'contracts/{link_odcs_id}/link-odps/', json_data=data)
            except click.ClickException as e:
                # Try to parse as ODPS error
                error_msg = str(e)
                if 'API error' in error_msg:
                    # Extract error code and message
                    raise handle_api_error(error_msg, 400, f'contracts/{link_odcs_id}/link-odps/')
                raise

            if output_format == 'json':
                click.echo(json.dumps(result, indent=2))
            else:
                click.echo("ODPS contract created and linked successfully!")
                click.echo(f"ID: {result.get('id')}")
                click.echo(f"Version: {result.get('version')}")
                click.echo(f"Status: {result.get('status')}")
                click.echo(f"Spec Type: {result.get('original_spec_type')}")
                click.echo(f"Format: {result.get('original_format')}")
                click.echo(f"Normalization Status: {result.get('normalization_status')}")
                click.echo(f"Linked to ODCS Contract: {link_odcs_id}")

                if result.get('normalization_errors'):
                    click.echo(f"Normalization Errors: {len(result.get('normalization_errors', []))}")

    except (ODPSCLIError, ODPSParameterError):
        raise
    except click.ClickException:
        raise
    except Exception as e:
        raise ODPSCLIError(
            message=f"Failed to create ODPS contract: {str(e)}",
            error_code="ODPS_CREATE_FAILED",
            context={'file_path': file_path},
            original_error=e
        )


@contracts.command('export')
@click.argument('contract_id')
@click.option('--format', 'format_type', type=click.Choice(['odps', 'odcs', 'hubcontract']), default='hubcontract', help='Export format (default: hubcontract)')
@click.option('--output-format', 'output_format', type=click.Choice(['json', 'yaml']), default='json', help='Output format: json or yaml (default: json)')
@click.option('--version', 'version_param', type=str, help='ODPS or ODCS version for export (e.g., 4.1 for ODPS, 3.0.2 for ODCS). Required when --format=odps or --format=odcs')
@click.option('--cli-format', 'output_format_cli', type=click.Choice(['json', 'table']), default='table', help='CLI output format (default: table)')
def export_contract(contract_id: str, format_type: str, output_format: str, version_param: Optional[str], output_format_cli: str):
    """
    Export a contract in various formats.

    Supported formats:
    - hubcontract: HubContract normalized format (default)
    - odcs: ODCS format
    - odps: ODPS format

    Output formats: json or yaml
    """
    try:
        # Validate parameters
        validate_contract_id(contract_id)

        # Validate version based on format type
        if format_type == 'odps' and version_param:
            validate_odps_version(version_param)
        elif format_type == 'odcs' and version_param:
            validate_odcs_version(version_param)

        # Build query parameters
        params = {
            'format': format_type,
            'output_format': output_format
        }
        if version_param and format_type in ('odps', 'odcs'):
            params['version'] = version_param

        # Call export endpoint
        # API endpoint: /api/v1/contracts/{id}/export/
        # Use request method to get raw response
        response = api_client.request('GET', f'contracts/{contract_id}/export/', params=params)

        # Handle response with format-specific error handling
        if response.status_code >= 400:
            # Try to parse error response
            error_data = {}
            try:
                error_data = response.json()
            except:
                error_data = {'error': {'message': response.text or 'Unknown error'}}

            # Use handle_api_error for better error parsing and context
            error_msg = error_data.get('error', {}).get('message', 'Unknown error')
            error_code = error_data.get('error', {}).get('code', 'UNKNOWN_ERROR')

            # Add format-specific context to error
            error_context = {
                'contract_id': contract_id,
                'format': format_type,
                'output_format': output_format
            }
            if version_param:
                error_context['version'] = version_param
                if format_type == 'odcs':
                    error_context['odcs_version'] = version_param
                elif format_type == 'odps':
                    error_context['odps_version'] = version_param

            # Use handle_api_error for structured error handling
            try:
                odps_error = handle_api_error(
                    response.text or json.dumps(error_data),
                    response.status_code,
                    f'contracts/{contract_id}/export/'
                )
                # Enhance error context with format-specific information
                odps_error.context.update(error_context)
                raise odps_error
            except ODPSCLIError:
                raise
            except Exception:
                # Fallback to ClickException if handle_api_error doesn't return ODPS error
                raise click.ClickException(f"API error ({error_code}): {error_msg}")

        # Get content type to determine if it's JSON or YAML
        content_type = response.headers.get('Content-Type', '').lower()
        content = response.text

        # Validate response content for ODCS format
        if format_type == 'odcs' and content:
            # Basic validation: check if content looks like ODCS
            # For JSON format, should have apiVersion and kind fields
            # For YAML format, should have apiVersion and kind fields
            if output_format == 'json':
                try:
                    content_dict = json.loads(content)
                    if 'apiVersion' not in content_dict or 'kind' not in content_dict:
                        # Not a critical error, but log a warning
                        click.echo("Warning: Exported content may not be valid ODCS format", err=True)
                except json.JSONDecodeError:
                    # Invalid JSON - this is an error
                    raise ODPSExportError(
                        message="Invalid JSON response from ODCS export",
                        error_code="INVALID_ODCS_RESPONSE",
                        context={
                            'contract_id': contract_id,
                            'format': format_type,
                            'output_format': output_format,
                            'version': version_param
                        },
                        suggestion="The API returned invalid JSON. Check API logs or contact support."
                    )
            elif output_format == 'yaml':
                # For YAML, check if it contains ODCS indicators
                if 'apiVersion' not in content and 'kind' not in content:
                    click.echo("Warning: Exported content may not be valid ODCS format", err=True)

        if output_format_cli == 'json':
            # Return raw response content
            click.echo(content)
        else:
            # Table format - show export info
            click.echo(f"Contract exported successfully!")
            click.echo(f"Contract ID: {contract_id}")
            click.echo(f"Format: {format_type}")
            click.echo(f"Output Format: {output_format}")
            if version_param:
                if format_type == 'odps':
                    click.echo(f"ODPS Version: {version_param}")
                elif format_type == 'odcs':
                    click.echo(f"ODCS Version: {version_param}")
            click.echo(f"\nContent ({len(content)} bytes):")
            click.echo("-" * 80)
            # Show first 500 characters of content
            if len(content) > 500:
                click.echo(content[:500])
                click.echo(f"\n... ({len(content) - 500} more characters)")
            else:
                click.echo(content)

    except (ODPSCLIError, ODPSParameterError):
        raise
    except click.ClickException:
        raise
    except Exception as e:
        # Enhanced error context for ODCS exports
        error_context = {
            'contract_id': contract_id,
            'format': format_type,
            'output_format': output_format
        }
        if version_param:
            error_context['version'] = version_param
            if format_type == 'odcs':
                error_context['odcs_version'] = version_param

        error_code = "ODCS_EXPORT_FAILED" if format_type == 'odcs' else "ODPS_EXPORT_FAILED"
        raise ODPSExportError(
            message=f"Failed to export contract as {format_type.upper()}: {str(e)}",
            error_code=error_code,
            context=error_context,
            original_error=e
        )


@contracts.command('get-pricing')
@click.argument('contract_id')
@click.option('--format', 'output_format', type=click.Choice(['json', 'table']), default='table', help='Output format')
def get_pricing(contract_id: str, output_format: str):
    """Get pricing information for a contract (ODPS pricing plans)"""
    try:
        # API endpoint structure: /api/v1/contracts/{id}/
        data = api_client.get(f'contracts/{contract_id}/')

        # Extract ODPS pricing plans
        hub_contract = data.get('hub_contract_json', {})
        marketplace = hub_contract.get('marketplace', {})
        x_odps = marketplace.get('x_odps', {})
        pricing_plans = x_odps.get('pricing_plans', [])

        if output_format == 'json':
            result = {
                'contract_id': contract_id,
                'pricing_plans': pricing_plans
            }
            click.echo(json.dumps(result, indent=2))
        else:
            if not pricing_plans:
                click.echo(f"No pricing plans found for contract {contract_id}")
                click.echo("Note: This contract may not be an ODPS contract or may not have pricing information.")
                return

            click.echo(f"Pricing Plans for Contract: {contract_id}")
            click.echo("=" * 80)
            for i, plan in enumerate(pricing_plans, 1):
                click.echo(f"\nPlan {i}:")
                click.echo(f"  Plan ID: {plan.get('planID', 'N/A')}")
                click.echo(f"  Name: {plan.get('name', 'N/A')}")
                if 'price' in plan:
                    currency = plan.get('currency', 'USD')
                    click.echo(f"  Price: {plan['price']} {currency}")
                if 'billingPeriod' in plan:
                    click.echo(f"  Billing Period: {plan['billingPeriod']}")
                if 'isDefault' in plan and plan['isDefault']:
                    click.echo(f"  Default: Yes")
                if 'description' in plan:
                    click.echo(f"  Description: {plan['description']}")
                # Display any additional fields
                for key, value in plan.items():
                    if key not in ['planID', 'name', 'price', 'currency', 'billingPeriod', 'isDefault', 'description']:
                        click.echo(f"  {key}: {value}")
    except click.ClickException:
        raise
    except Exception as e:
        raise click.ClickException(f"Failed to get pricing: {e}")


@contracts.command('get-access-methods')
@click.argument('contract_id')
@click.option('--format', 'output_format', type=click.Choice(['json', 'table']), default='table', help='Output format')
def get_access_methods(contract_id: str, output_format: str):
    """Get access methods for a contract (ODPS access methods)"""
    try:
        # API endpoint structure: /api/v1/contracts/{id}/
        data = api_client.get(f'contracts/{contract_id}/')

        # Extract ODPS access methods
        hub_contract = data.get('hub_contract_json', {})
        marketplace = hub_contract.get('marketplace', {})
        x_odps = marketplace.get('x_odps', {})
        access_methods = x_odps.get('access_methods', {})

        if output_format == 'json':
            result = {
                'contract_id': contract_id,
                'access_methods': access_methods
            }
            click.echo(json.dumps(result, indent=2))
        else:
            if not access_methods:
                click.echo(f"No access methods found for contract {contract_id}")
                click.echo("Note: This contract may not be an ODPS contract or may not have access method information.")
                return

            click.echo(f"Access Methods for Contract: {contract_id}")
            click.echo("=" * 80)
            for method_name, method_data in access_methods.items():
                click.echo(f"\n{method_name.upper()}:")
                if isinstance(method_data, dict):
                    for key, value in method_data.items():
                        if isinstance(value, (dict, list)):
                            click.echo(f"  {key}:")
                            click.echo(json.dumps(value, indent=4).replace('\n', '\n    '))
                        else:
                            click.echo(f"  {key}: {value}")
                else:
                    click.echo(f"  {method_data}")
    except click.ClickException:
        raise
    except Exception as e:
        raise click.ClickException(f"Failed to get access methods: {e}")


def _display_odps_fields(data: dict):
    """Display ODPS-specific fields from contract data"""
    hub_contract = data.get('hub_contract_json', {})
    marketplace = hub_contract.get('marketplace', {})
    x_odps = marketplace.get('x_odps', {})

    if not x_odps:
        click.echo("\nODPS Information: Not available (contract may not be ODPS or may not have ODPS marketplace data)")
        return

    click.echo("\n" + "=" * 80)
    click.echo("ODPS Information")
    click.echo("=" * 80)

    # Display pricing plans
    pricing_plans = x_odps.get('pricing_plans', [])
    if pricing_plans:
        click.echo(f"\nPricing Plans ({len(pricing_plans)}):")
        for i, plan in enumerate(pricing_plans, 1):
            click.echo(f"  {i}. {plan.get('name', plan.get('planID', 'Unnamed Plan'))}")
            if 'price' in plan:
                currency = plan.get('currency', 'USD')
                click.echo(f"     Price: {plan['price']} {currency}")
            if 'billingPeriod' in plan:
                click.echo(f"     Billing: {plan['billingPeriod']}")
            if plan.get('isDefault'):
                click.echo(f"     Default: Yes")
    else:
        click.echo("\nPricing Plans: None")

    # Display access methods
    access_methods = x_odps.get('access_methods', {})
    if access_methods:
        click.echo(f"\nAccess Methods ({len(access_methods)}):")
        for method_name, method_data in access_methods.items():
            click.echo(f"  - {method_name}")
            if isinstance(method_data, dict):
                if 'type' in method_data:
                    click.echo(f"    Type: {method_data['type']}")
                if 'endpoint' in method_data:
                    click.echo(f"    Endpoint: {method_data['endpoint']}")
                if 'protocol' in method_data:
                    click.echo(f"    Protocol: {method_data['protocol']}")
    else:
        click.echo("\nAccess Methods: None")

    # Display payment gateways if available
    payment_gateways = x_odps.get('payment_gateways', {})
    if payment_gateways:
        click.echo(f"\nPayment Gateways ({len(payment_gateways)}):")
        for gateway_name, gateway_data in payment_gateways.items():
            click.echo(f"  - {gateway_name}")
            if isinstance(gateway_data, dict):
                if 'enabled' in gateway_data:
                    click.echo(f"    Enabled: {gateway_data['enabled']}")
                if 'provider' in gateway_data:
                    click.echo(f"    Provider: {gateway_data['provider']}")


@contracts.command('download')
@click.argument('contract_id')
@click.option('--format', 'format_type', type=click.Choice(['odps', 'odcs', 'hubcontract']), default='hubcontract', help='Download format (default: hubcontract)')
@click.option('--output-format', 'output_format', type=click.Choice(['json', 'yaml']), default='json', help='Output format: json or yaml (default: json)')
@click.option('--version', 'odps_version', type=str, help='ODPS version for download (e.g., 4.1). Only used when --format=odps')
@click.option('--output', 'output_path', type=click.Path(), help='Output file path. If not specified, uses contract name with appropriate extension')
def download_contract(contract_id: str, format_type: str, output_format: str, odps_version: Optional[str], output_path: Optional[str]):
    """
    Download a contract as a file in various formats.

    Supported formats:
    - hubcontract: HubContract normalized format (default)
    - odcs: ODCS format
    - odps: ODPS format

    Output formats: json or yaml
    """

    try:
        # Validate parameters
        validate_contract_id(contract_id)
        if odps_version and format_type == 'odps':
            validate_odps_version(odps_version)
        # Build query parameters
        params = {
            'format': format_type,
            'output_format': output_format
        }
        if odps_version and format_type == 'odps':
            params['version'] = odps_version

        # Call download endpoint
        # API endpoint: /api/v1/contracts/{id}/download/
        # Use request method to get raw response
        response = api_client.request('GET', f'contracts/{contract_id}/download/', params=params)

        # Handle response
        if response.status_code >= 400:
            error_data = {}
            try:
                error_data = response.json()
            except:
                error_data = {'error': {'message': response.text or 'Unknown error'}}

            error_msg = error_data.get('error', {}).get('message', 'Unknown error')
            error_code = error_data.get('error', {}).get('code', 'UNKNOWN_ERROR')
            raise click.ClickException(f"API error ({error_code}): {error_msg}")

        # Get filename from Content-Disposition header or generate one
        content_disposition = response.headers.get('Content-Disposition', '')
        filename = None
        if content_disposition:
            # Parse Content-Disposition: attachment; filename="contract.odps.json"
            import re
            match = re.search(r'filename="?([^"]+)"?', content_disposition)
            if match:
                filename = match.group(1)

        # If no filename from header, generate one
        if not filename:
            extension = 'yaml' if output_format == 'yaml' else 'json'
            filename = f"contract-{contract_id[:8]}.{format_type}.{extension}"

        # Use provided output path or filename
        if output_path:
            final_path = output_path
        else:
            final_path = filename

        # Write file
        try:
            with open(final_path, 'wb') as f:
                f.write(response.content)
        except IOError as e:
            raise ODPSExportError(
                message=f"Failed to write file: {final_path}",
                error_code="FILE_WRITE_FAILED",
                context={'file_path': final_path, 'contract_id': contract_id},
                suggestion="Check that you have write permissions for the output directory",
                original_error=e
            )

        click.echo(f"Contract downloaded successfully!")
        click.echo(f"Contract ID: {contract_id}")
        click.echo(f"Format: {format_type}")
        click.echo(f"Output Format: {output_format}")
        if odps_version:
            click.echo(f"ODPS Version: {odps_version}")
        click.echo(f"Saved to: {final_path}")
        click.echo(f"Size: {len(response.content)} bytes")

    except (ODPSCLIError, ODPSParameterError):
        raise
    except click.ClickException:
        raise
    except Exception as e:
        raise ODPSExportError(
            message=f"Failed to download contract: {str(e)}",
            error_code="ODPS_DOWNLOAD_FAILED",
            context={'contract_id': contract_id, 'format': format_type},
            original_error=e
        )


@contracts.command('link-odps')
@click.argument('odcs_id')
@click.argument('odps_id')
@click.option('--format', 'output_format', type=click.Choice(['json', 'table']), default='table', help='Output format')
def link_odps(odcs_id: str, odps_id: str, output_format: str):
    """
    Link an existing ODPS contract to an ODCS contract.

    This creates a bidirectional link between the ODCS and ODPS contracts.
    The ODCS contract must exist and be of type ODCS.
    The ODPS contract must exist and be of type ODPS.
    """
    try:
        # Validate parameters
        validate_contract_id(odcs_id, 'odcs')
        validate_contract_id(odps_id, 'odps')
        # API endpoint: POST /api/v1/contracts/{odcs_id}/link-odps/
        # Body: {"odps_contract_id": odps_id}
        result = api_client.post(
            f'contracts/{odcs_id}/link-odps/',
            json_data={'odps_contract_id': odps_id}
        )

        if output_format == 'json':
            click.echo(json.dumps(result, indent=2))
        else:
            click.echo("ODPS contract linked successfully!")
            click.echo(f"ODCS Contract ID: {odcs_id}")
            click.echo(f"ODPS Contract ID: {result.get('id', odps_id)}")
            click.echo(f"ODPS Version: {result.get('version', 'N/A')}")
            click.echo(f"ODPS Status: {result.get('status', 'N/A')}")
            click.echo(f"ODPS Spec Type: {result.get('original_spec_type', 'N/A')}")
            click.echo(f"Normalization Status: {result.get('normalization_status', 'N/A')}")
    except (ODPSCLIError, ODPSParameterError):
        raise
    except click.ClickException:
        raise
    except Exception as e:
        raise ODPSLinkingError(
            message=f"Failed to link ODPS contract: {str(e)}",
            error_code="ODPS_LINKING_FAILED",
            context={'odcs_id': odcs_id, 'odps_id': odps_id},
            original_error=e
        )


@contracts.command('unlink-odps')
@click.argument('odcs_id')
@click.option('--format', 'output_format', type=click.Choice(['json', 'table']), default='table', help='Output format')
def unlink_odps(odcs_id: str, output_format: str):
    """
    Unlink ODPS contract from ODCS contract.

    This removes the bidirectional link between the ODCS and ODPS contracts.
    The ODCS contract must exist and be of type ODCS.
    """
    try:
        # API endpoint: POST /api/v1/contracts/{odcs_id}/unlink-odps/
        result = api_client.post(f'contracts/{odcs_id}/unlink-odps/')

        if output_format == 'json':
            click.echo(json.dumps(result, indent=2))
        else:
            click.echo("ODPS contract unlinked successfully!")
            click.echo(f"ODCS Contract ID: {odcs_id}")
            if result.get('message'):
                click.echo(f"Message: {result.get('message')}")
    except (ODPSCLIError, ODPSParameterError):
        raise
    except click.ClickException:
        raise
    except Exception as e:
        raise ODPSLinkingError(
            message=f"Failed to unlink ODPS contract: {str(e)}",
            error_code="ODPS_UNLINKING_FAILED",
            context={'odcs_id': odcs_id},
            original_error=e
        )


@contracts.command('list-links')
@click.argument('contract_id')
@click.option('--format', 'output_format', type=click.Choice(['json', 'table']), default='table', help='Output format')
def list_links(contract_id: str, output_format: str):
    """
    List all links for a contract (ODPS and ODCS links).

    Shows both ODPS links (if this is an ODCS contract) and ODCS links
    (if this is an ODPS contract).
    """
    try:
        # API endpoint: GET /api/v1/contracts/{contract_id}/links/
        result = api_client.get(f'contracts/{contract_id}/links/')

        if output_format == 'json':
            click.echo(json.dumps(result, indent=2))
        else:
            odps_link = result.get('odps_link')
            odcs_link = result.get('odcs_link')

            click.echo(f"Contract ID: {contract_id}")
            click.echo("")

            if odps_link:
                click.echo("ODPS Link:")
                click.echo(f"  ID: {odps_link.get('id')}")
                click.echo(f"  Version: {odps_link.get('version', 'N/A')}")
                click.echo(f"  Status: {odps_link.get('status', 'N/A')}")
                click.echo(f"  Spec Type: {odps_link.get('original_spec_type', 'N/A')}")
                click.echo(f"  Normalization Status: {odps_link.get('normalization_status', 'N/A')}")
            else:
                click.echo("ODPS Link: None")

            click.echo("")

            if odcs_link:
                click.echo("ODCS Link:")
                click.echo(f"  ID: {odcs_link.get('id')}")
                click.echo(f"  Version: {odcs_link.get('version', 'N/A')}")
                click.echo(f"  Status: {odcs_link.get('status', 'N/A')}")
                click.echo(f"  Spec Type: {odcs_link.get('original_spec_type', 'N/A')}")
                click.echo(f"  Normalization Status: {odcs_link.get('normalization_status', 'N/A')}")
            else:
                click.echo("ODCS Link: None")

            if not odps_link and not odcs_link:
                click.echo("\nNo links found for this contract.")
    except (ODPSCLIError, ODPSParameterError):
        raise
    except click.ClickException:
        raise
    except Exception as e:
        raise ODPSCLIError(
            message=f"Failed to list contract links: {str(e)}",
            error_code="ODPS_LIST_LINKS_FAILED",
            context={'contract_id': contract_id},
            original_error=e
        )


@contracts.command('get-payment-gateways')
@click.argument('contract_id')
@click.option('--format', 'output_format', type=click.Choice(['json', 'table']), default='table', help='Output format')
def get_payment_gateways(contract_id: str, output_format: str):
    """
    Get payment gateways from an ODPS contract.

    Returns all payment gateways configured in the contract's marketplace section.
    The contract must be an ODPS contract (original_spec_type must be 'ODPS').
    """
    try:
        # Validate contract ID
        validate_contract_id(contract_id)

        # API endpoint: GET /api/v1/contracts/{contract_id}/payment-gateways/
        # Note: Router uses basename="contract", so URL is contracts/{id}/payment-gateways/ (not contracts/{id}/payment-gateways/)
        try:
            result = api_client.get(f'contracts/{contract_id}/payment-gateways/')
        except Exception as e:
            # Handle API errors - api_client.get() may raise ClickException or other exceptions
            # Re-raise ClickException as-is, wrap others
            if isinstance(e, click.ClickException):
                raise
            raise ODPSCLIError(
                message=f"Failed to get payment gateways: {str(e)}",
                error_code="GET_PAYMENT_GATEWAYS_FAILED",
                context={'contract_id': contract_id},
                original_error=e
            )

        payment_gateways = result.get('payment_gateways', {})

        if output_format == 'json':
            click.echo(json.dumps(payment_gateways, indent=2))
        else:
            # Table format
            if not payment_gateways:
                click.echo(f"No payment gateways found for contract {contract_id}.")
                click.echo("Note: Payment gateways are only available for ODPS contracts.")
                return

            click.echo(f"Payment Gateways for Contract: {contract_id}")
            click.echo("")
            click.echo(f"{'Gateway ID':<30} {'Type':<20} {'Enabled':<10} {'Webhook URL':<50}")
            click.echo("-" * 110)

            for gateway_id, gateway_config in payment_gateways.items():
                gateway_type = gateway_config.get('type', 'N/A')
                enabled = gateway_config.get('enabled', False)
                enabled_str = 'Yes' if enabled else 'No'
                webhook_url = gateway_config.get('webhook_url') or 'N/A'
                # Truncate webhook URL if too long
                if webhook_url and webhook_url != 'N/A' and len(webhook_url) > 48:
                    webhook_url = webhook_url[:45] + '...'

                click.echo(
                    f"{gateway_id:<30} "
                    f"{gateway_type:<20} "
                    f"{enabled_str:<10} "
                    f"{webhook_url:<50}"
                )

            click.echo("")
            click.echo(f"Total: {len(payment_gateways)} payment gateway(s)")

    except (ODPSCLIError, ODPSParameterError):
        raise
    except click.ClickException:
        raise
    except Exception as e:
        raise ODPSCLIError(
            message=f"Failed to get payment gateways: {str(e)}",
            error_code="GET_PAYMENT_GATEWAYS_FAILED",
            context={'contract_id': contract_id},
            original_error=e
        )


@contracts.command('get-product-strategy')
@click.argument('contract_id')
@click.option('--format', 'output_format', type=click.Choice(['json', 'table']), default='table', help='Output format')
def get_product_strategy(contract_id: str, output_format: str):
    """
    Get product strategy from an ODPS contract (ODPS 4.1+).

    Returns the product strategy configured in the contract.
    The contract must be an ODPS contract with version 4.1 or higher.
    """
    try:
        # Validate contract ID
        validate_contract_id(contract_id)

        # API endpoint: GET /api/v1/contracts/{contract_id}/product-strategy/
        # Note: Router uses basename="contract", so URL is contracts/{id}/product-strategy/ (not contracts/{id}/product-strategy/)
        try:
            result = api_client.get(f'contracts/{contract_id}/product-strategy/')
        except Exception as e:
            # Handle API errors - api_client.get() may raise ClickException or other exceptions
            # Re-raise ClickException as-is, wrap others
            if isinstance(e, click.ClickException):
                raise
            raise ODPSCLIError(
                message=f"Failed to get product strategy: {str(e)}",
                error_code="GET_PRODUCT_STRATEGY_FAILED",
                context={'contract_id': contract_id},
                original_error=e
            )

        product_strategy = result.get('product_strategy')

        if output_format == 'json':
            click.echo(json.dumps(product_strategy, indent=2) if product_strategy else 'null')
        else:
            # Table format
            if not product_strategy:
                click.echo(f"No product strategy found for contract {contract_id}.")
                click.echo("Note: Product strategy is only available for ODPS 4.1+ contracts.")
                return

            click.echo(f"Product Strategy for Contract: {contract_id}")
            click.echo("")

            # Display objectives
            objectives = product_strategy.get('objectives', [])
            if objectives:
                click.echo("Objectives:")
                if isinstance(objectives, list):
                    for i, objective in enumerate(objectives, 1):
                        if isinstance(objective, dict):
                            obj_name = objective.get('name', 'N/A')
                            obj_desc = objective.get('description', '')
                            click.echo(f"  {i}. {obj_name}")
                            if obj_desc:
                                click.echo(f"     {obj_desc}")
                        else:
                            click.echo(f"  {i}. {objective}")
                else:
                    click.echo(f"  {objectives}")
                click.echo("")

            # Display strategic alignment
            strategic_alignment = product_strategy.get('strategicAlignment', [])
            if strategic_alignment:
                click.echo("Strategic Alignment:")
                if isinstance(strategic_alignment, list):
                    for i, alignment in enumerate(strategic_alignment, 1):
                        if isinstance(alignment, dict):
                            align_name = alignment.get('name', 'N/A')
                            align_desc = alignment.get('description', '')
                            click.echo(f"  {i}. {align_name}")
                            if align_desc:
                                click.echo(f"     {align_desc}")
                        else:
                            click.echo(f"  {i}. {alignment}")
                else:
                    click.echo(f"  {strategic_alignment}")
                click.echo("")

            # Display product KPIs
            product_kpis = product_strategy.get('productKPIs', [])
            if product_kpis:
                click.echo("Product KPIs:")
                if isinstance(product_kpis, list):
                    for i, kpi in enumerate(product_kpis, 1):
                        if isinstance(kpi, dict):
                            kpi_name = kpi.get('name', 'N/A')
                            kpi_value = kpi.get('targetValue', 'N/A')
                            kpi_unit = kpi.get('unit', '')
                            kpi_desc = kpi.get('description', '')
                            click.echo(f"  {i}. {kpi_name}: {kpi_value} {kpi_unit}".strip())
                            if kpi_desc:
                                click.echo(f"     {kpi_desc}")
                        else:
                            click.echo(f"  {i}. {kpi}")
                else:
                    click.echo(f"  {product_kpis}")
                click.echo("")

            # Display target audience
            target_audience = product_strategy.get('targetAudience', {})
            if target_audience:
                click.echo("Target Audience:")
                if isinstance(target_audience, dict):
                    for key, value in target_audience.items():
                        click.echo(f"  {key}: {value}")
                else:
                    click.echo(f"  {target_audience}")
                click.echo("")

            # Display value proposition
            value_proposition = product_strategy.get('valueProposition', {})
            if value_proposition:
                click.echo("Value Proposition:")
                if isinstance(value_proposition, dict):
                    for key, value in value_proposition.items():
                        click.echo(f"  {key}: {value}")
                else:
                    click.echo(f"  {value_proposition}")
                click.echo("")

            # Summary
            sections = []
            if objectives:
                sections.append(f"{len(objectives) if isinstance(objectives, list) else 1} objective(s)")
            if strategic_alignment:
                sections.append(f"{len(strategic_alignment) if isinstance(strategic_alignment, list) else 1} alignment(s)")
            if product_kpis:
                sections.append(f"{len(product_kpis) if isinstance(product_kpis, list) else 1} KPI(s)")
            if target_audience:
                sections.append("target audience")
            if value_proposition:
                sections.append("value proposition")

            if sections:
                click.echo(f"Summary: {', '.join(sections)}")

    except (ODPSCLIError, ODPSParameterError):
        raise
    except click.ClickException:
        raise
    except Exception as e:
        raise ODPSCLIError(
            message=f"Failed to get product strategy: {str(e)}",
            error_code="GET_PRODUCT_STRATEGY_FAILED",
            context={'contract_id': contract_id},
            original_error=e
        )


@contracts.command('get-product-details')
@click.argument('contract_id')
@click.option('--lang', default='en', help='Language code (ISO 639-1, e.g., "en", "fi", "es"). Default: "en"')
@click.option('--format', 'output_format', type=click.Choice(['json', 'table']), default='table', help='Output format')
def get_product_details(contract_id: str, lang: str, output_format: str):
    """
    Get product details from an ODPS contract for a specific language.

    Returns the product details configured in the contract for the specified language.
    The contract must be an ODPS contract.
    """
    try:
        # Validate contract ID
        validate_contract_id(contract_id)

        # Validate language code (ISO 639-1: 2 characters)
        if not isinstance(lang, str) or len(lang) != 2:
            raise ODPSParameterError(
                message=f"Invalid language code: {lang}. Must be a valid ISO 639-1 code (2 characters)",
                error_code="INVALID_LANGUAGE_CODE",
                context={'lang': lang}
            )
        lang = lang.lower()

        # API endpoint: GET /api/v1/contracts/{contract_id}/product-details/?lang={lang}
        # Note: Router uses basename="contract" with empty prefix, so URL is contracts/{id}/product-details/
        # The base URL already includes /api/v1, and contracts/ is from api/urls.py, so we just need {id}/product-details/
        try:
            result = api_client.get(f'contracts/{contract_id}/product-details/', params={'lang': lang})
        except Exception as e:
            # Handle API errors - api_client.get() may raise ClickException or other exceptions
            # Re-raise ClickException as-is, wrap others
            if isinstance(e, click.ClickException):
                raise
            raise ODPSCLIError(
                message=f"Failed to get product details: {str(e)}",
                error_code="GET_PRODUCT_DETAILS_FAILED",
                context={'contract_id': contract_id, 'lang': lang},
                original_error=e
            )

        product_details = result.get('product_details')

        if output_format == 'json':
            click.echo(json.dumps(product_details, indent=2) if product_details else 'null')
        else:
            # Table format
            if not product_details:
                click.echo(f"No product details found for contract {contract_id} in language '{lang}'.")
                click.echo("Note: Product details may not be available for all languages.")
                return

            click.echo(f"Product Details for Contract: {contract_id} (Language: {lang})")
            click.echo("")

            # Display product ID
            product_id = product_details.get('productID') or product_details.get('product_id')
            if product_id:
                click.echo(f"Product ID: {product_id}")

            # Display name
            name = product_details.get('name')
            if name:
                click.echo(f"Name: {name}")

            # Display description
            description = product_details.get('description')
            if description:
                click.echo(f"Description: {description}")

            # Display product version
            product_version = product_details.get('productVersion') or product_details.get('product_version')
            if product_version:
                click.echo(f"Version: {product_version}")

            # Display category
            category = product_details.get('category')
            if category:
                click.echo(f"Category: {category}")

            # Display tags
            tags = product_details.get('tags')
            if tags:
                if isinstance(tags, list):
                    if tags:
                        click.echo(f"Tags: {', '.join(str(tag) for tag in tags)}")
                else:
                    click.echo(f"Tags: {tags}")

            # Display any additional fields
            known_fields = {'productID', 'product_id', 'name', 'description', 'productVersion', 'product_version', 'category', 'tags'}
            additional_fields = {k: v for k, v in product_details.items() if k not in known_fields}
            if additional_fields:
                click.echo("")
                click.echo("Additional Fields:")
                for key, value in additional_fields.items():
                    if isinstance(value, (dict, list)):
                        click.echo(f"  {key}: {json.dumps(value, indent=2)}")
                    else:
                        click.echo(f"  {key}: {value}")

    except (ODPSParameterError, ODPSCLIError) as e:
        raise
    except click.ClickException:
        raise
    except Exception as e:
        raise ODPSCLIError(
            message=f"Unexpected error getting product details: {str(e)}",
            error_code="GET_PRODUCT_DETAILS_UNEXPECTED_ERROR",
            context={'contract_id': contract_id, 'lang': lang},
            original_error=e
        )

