"""
Contract management commands.
"""
import click
import json
import os
from typing import Optional
from ..api_client import api_client


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
            
            # Table format
            click.echo(f"{'ID':<40} {'Version':<10} {'Status':<15} {'Asset ID':<40}")
            click.echo("-" * 105)
            for contract in results:
                click.echo(
                    f"{contract.get('id', '')[:36]:<40} "
                    f"{contract.get('version', ''):<10} "
                    f"{contract.get('status', ''):<15} "
                    f"{contract.get('asset_id', '')[:36] if contract.get('asset_id') else 'N/A':<40}"
                )
    except click.ClickException:
        raise
    except Exception as e:
        raise click.ClickException(f"Failed to list contracts: {e}")


@contracts.command('get')
@click.argument('contract_id')
@click.option('--format', 'output_format', type=click.Choice(['json', 'table']), default='table', help='Output format')
def get_contract(contract_id: str, output_format: str):
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
    except click.ClickException:
        raise
    except Exception as e:
        raise click.ClickException(f"Failed to get contract: {e}")


@contracts.command('create')
@click.option('--file', 'file_path', required=True, type=click.Path(exists=True), help='Path to contract file (YAML or JSON)')
@click.option('--asset-id', help='Asset ID to attach contract to')
@click.option('--format', 'output_format', type=click.Choice(['json', 'table']), default='table', help='Output format')
def create_contract(file_path: str, asset_id: Optional[str], output_format: str):
    """Create a new contract from file"""
    # Read file
    try:
        with open(file_path, 'r') as f:
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
    
    data = {
        'original_raw': content,
        'original_format': original_format
    }
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

