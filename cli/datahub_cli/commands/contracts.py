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
        # API endpoint structure: /api/v1/contracts/contracts/ (contracts/ from api/urls.py + contracts from router)
        data = api_client.get('contracts/contracts/', params=params)
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
        # API endpoint structure: /api/v1/contracts/contracts/{id}/ (contracts/ from api/urls.py + contracts from router)
        data = api_client.get(f'contracts/contracts/{contract_id}/')

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
        # API endpoint structure: /api/v1/contracts/contracts/ (contracts/ from api/urls.py + contracts from router)
        result = api_client.post('contracts/contracts/', json_data=data)

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
        # API endpoint structure: /api/v1/contracts/contracts/{id}/validate/ (contracts/ from api/urls.py + contracts from router)
        result = api_client.post(f'contracts/contracts/{contract_id}/validate/')

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
        # API endpoint structure: /api/v1/contracts/contracts/{id}/lint/ (contracts/ from api/urls.py + contracts from router)
        result = api_client.post(f'contracts/contracts/{contract_id}/lint/')

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
        validate_required_option('extract-odcs', extract_odcs, alternative='link-odcs')

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
                result = api_client.post('contracts/products/', json_data=data)
            except click.ClickException as e:
                # Try to parse as ODPS error
                error_msg = str(e)
                if 'API error' in error_msg:
                    # Extract error code and message
                    raise handle_api_error(error_msg, 400, 'contracts/products/')
                raise

            if output_format == 'json':
                click.echo(json.dumps(result, indent=2))
            else:
                odps_contract = result.get('odps_contract', {})
                odcs_contract = result.get('odcs_contract', {})
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
                result = api_client.post(f'contracts/contracts/{link_odcs_id}/link-odps/', json_data=data)
            except click.ClickException as e:
                # Try to parse as ODPS error
                error_msg = str(e)
                if 'API error' in error_msg:
                    # Extract error code and message
                    raise handle_api_error(error_msg, 400, f'contracts/contracts/{link_odcs_id}/link-odps/')
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
@click.option('--version', 'odps_version', type=str, help='ODPS version for export (e.g., 4.1). Only used when --format=odps')
@click.option('--cli-format', 'output_format_cli', type=click.Choice(['json', 'table']), default='table', help='CLI output format (default: table)')
def export_contract(contract_id: str, format_type: str, output_format: str, odps_version: Optional[str], output_format_cli: str):
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
        if odps_version and format_type == 'odps':
            validate_odps_version(odps_version)

        # Build query parameters
        params = {
            'format': format_type,
            'output_format': output_format
        }
        if odps_version and format_type == 'odps':
            params['version'] = odps_version

        # Call export endpoint
        # API endpoint: /api/v1/contracts/contracts/{id}/export/
        # Use request method to get raw response
        response = api_client.request('GET', f'contracts/contracts/{contract_id}/export/', params=params)

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

        # Get content type to determine if it's JSON or YAML
        content_type = response.headers.get('Content-Type', '')
        content = response.text

        if output_format_cli == 'json':
            # Return raw JSON response
            click.echo(content)
        else:
            # Table format - show export info
            click.echo(f"Contract exported successfully!")
            click.echo(f"Contract ID: {contract_id}")
            click.echo(f"Format: {format_type}")
            click.echo(f"Output Format: {output_format}")
            if odps_version:
                click.echo(f"ODPS Version: {odps_version}")
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
        raise ODPSExportError(
            message=f"Failed to export contract: {str(e)}",
            error_code="ODPS_EXPORT_FAILED",
            context={'contract_id': contract_id, 'format': format_type},
            original_error=e
        )


@contracts.command('get-pricing')
@click.argument('contract_id')
@click.option('--format', 'output_format', type=click.Choice(['json', 'table']), default='table', help='Output format')
def get_pricing(contract_id: str, output_format: str):
    """Get pricing information for a contract (ODPS pricing plans)"""
    try:
        # API endpoint structure: /api/v1/contracts/contracts/{id}/
        data = api_client.get(f'contracts/contracts/{contract_id}/')

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
        # API endpoint structure: /api/v1/contracts/contracts/{id}/
        data = api_client.get(f'contracts/contracts/{contract_id}/')

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
        # API endpoint: /api/v1/contracts/contracts/{id}/download/
        # Use request method to get raw response
        response = api_client.request('GET', f'contracts/contracts/{contract_id}/download/', params=params)

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
            f'contracts/contracts/{odcs_id}/link-odps/',
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
        result = api_client.post(f'contracts/contracts/{odcs_id}/unlink-odps/')

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
        result = api_client.get(f'contracts/contracts/{contract_id}/links/')

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

