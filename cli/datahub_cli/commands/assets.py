"""
Asset management commands.
"""
import click
import json
from typing import Optional
from ..api_client import api_client


@click.group()
def assets():
    """Asset management commands"""
    pass


@assets.command('list')
@click.option('--status', help='Filter by status (DRAFT, ACTIVE, ARCHIVED)')
@click.option('--domain', help='Filter by domain')
@click.option('--limit', type=int, default=20, help='Limit number of results')
@click.option('--offset', type=int, default=0, help='Offset for pagination')
@click.option('--format', 'output_format', type=click.Choice(['json', 'table']), default='table', help='Output format')
def list_assets(status: Optional[str], domain: Optional[str], limit: int, offset: int, output_format: str):
    """List assets"""
    params = {'limit': limit, 'offset': offset}
    if status:
        params['status'] = status
    if domain:
        params['domain'] = domain
    
    try:
        # API endpoint structure: /api/v1/assets/ (assets/ from api/urls.py + assets from router)
        data = api_client.get('assets/', params=params)
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
                click.echo("No assets found.")
                return
            
            # Table format
            click.echo(f"{'ID':<40} {'Name':<30} {'Status':<15} {'Domain':<20}")
            click.echo("-" * 105)
            for asset in results:
                # Ensure asset is a dict and handle None values safely
                if not isinstance(asset, dict):
                    continue
                asset_id = str(asset.get('id', ''))[:36] if asset.get('id') else ''
                asset_name = str(asset.get('name', ''))[:28] if asset.get('name') else ''
                asset_status = str(asset.get('status', ''))[:15] if asset.get('status') else ''
                asset_domain = str(asset.get('domain', ''))[:18] if asset.get('domain') else ''
                click.echo(
                    f"{asset_id:<40} "
                    f"{asset_name:<30} "
                    f"{asset_status:<15} "
                    f"{asset_domain:<20}"
                )
    except click.ClickException:
        raise
    except Exception as e:
        raise click.ClickException(f"Failed to list assets: {e}")


@assets.command('get')
@click.argument('asset_id')
@click.option('--include', help='Comma-separated list of related resources (contract,datasets,latest_dq,latest_compliance)')
@click.option('--format', 'output_format', type=click.Choice(['json', 'table']), default='table', help='Output format')
def get_asset(asset_id: str, include: Optional[str], output_format: str):
    """Get asset details"""
    params = {}
    if include:
        params['include'] = include
    
    try:
        # API endpoint structure: /api/v1/assets/{id}/ (assets/ from api/urls.py + assets from router)
        data = api_client.get(f'assets/{asset_id}/', params=params)
        
        if output_format == 'json':
            click.echo(json.dumps(data, indent=2))
        else:
            # Table format
            click.echo(f"ID: {data.get('id')}")
            click.echo(f"Name: {data.get('name')}")
            click.echo(f"Key: {data.get('key')}")
            click.echo(f"Status: {data.get('status')}")
            click.echo(f"Domain: {data.get('domain')}")
            click.echo(f"Visibility: {data.get('visibility')}")
            if data.get('description'):
                click.echo(f"Description: {data.get('description')}")
            click.echo(f"Created: {data.get('created_at')}")
            click.echo(f"Updated: {data.get('updated_at')}")
    except click.ClickException:
        raise
    except Exception as e:
        raise click.ClickException(f"Failed to get asset: {e}")


@assets.command('create')
@click.option('--name', required=True, help='Asset name')
@click.option('--key', required=True, help='Asset key (unique identifier)')
@click.option('--description', help='Asset description')
@click.option('--domain', help='Asset domain')
@click.option('--visibility', type=click.Choice(['INTERNAL', 'PUBLIC']), default='INTERNAL', help='Asset visibility')
@click.option('--format', 'output_format', type=click.Choice(['json', 'table']), default='table', help='Output format')
def create_asset(name: str, key: str, description: Optional[str], domain: Optional[str], visibility: str, output_format: str):
    """Create a new asset"""
    data = {
        'name': name,
        'key': key,
        'visibility': visibility
    }
    if description:
        data['description'] = description
    if domain:
        data['domain'] = domain
    
    try:
        # API endpoint structure: /api/v1/assets/ (assets/ from api/urls.py + assets from router)
        result = api_client.post('assets/', json_data=data)
        
        if output_format == 'json':
            click.echo(json.dumps(result, indent=2))
        else:
            click.echo(f"Asset created successfully!")
            click.echo(f"ID: {result.get('id')}")
            click.echo(f"Name: {result.get('name')}")
            click.echo(f"Status: {result.get('status')}")
    except click.ClickException:
        raise
    except Exception as e:
        raise click.ClickException(f"Failed to create asset: {e}")


@assets.command('update')
@click.argument('asset_id')
@click.option('--name', help='Asset name')
@click.option('--description', help='Asset description')
@click.option('--domain', help='Asset domain')
@click.option('--visibility', type=click.Choice(['INTERNAL', 'PUBLIC']), help='Asset visibility')
@click.option('--format', 'output_format', type=click.Choice(['json', 'table']), default='table', help='Output format')
def update_asset(asset_id: str, name: Optional[str], description: Optional[str], domain: Optional[str], visibility: Optional[str], output_format: str):
    """Update an asset"""
    data = {}
    if name:
        data['name'] = name
    if description is not None:
        data['description'] = description
    if domain:
        data['domain'] = domain
    if visibility:
        data['visibility'] = visibility
    
    if not data:
        raise click.ClickException("No fields to update")
    
    try:
        # API endpoint structure: /api/v1/assets/{id}/ (assets/ from api/urls.py + assets from router)
        result = api_client.patch(f'assets/{asset_id}/', json_data=data)
        
        if output_format == 'json':
            click.echo(json.dumps(result, indent=2))
        else:
            click.echo(f"Asset updated successfully!")
            click.echo(f"ID: {result.get('id')}")
            click.echo(f"Name: {result.get('name')}")
    except click.ClickException:
        raise
    except Exception as e:
        raise click.ClickException(f"Failed to update asset: {e}")


@assets.command('delete')
@click.argument('asset_id')
@click.option('--confirm', is_flag=True, help='Skip confirmation prompt')
def delete_asset(asset_id: str, confirm: bool):
    """Delete an asset"""
    if not confirm:
        if not click.confirm(f"Are you sure you want to delete asset {asset_id}?"):
            click.echo("Cancelled.")
            return
    
    try:
        # API endpoint structure: /api/v1/assets/{id}/ (assets/ from api/urls.py + assets from router)
        api_client.delete(f'assets/{asset_id}/')
        click.echo(f"Asset {asset_id} deleted successfully!")
    except click.ClickException:
        raise
    except Exception as e:
        raise click.ClickException(f"Failed to delete asset: {e}")


@assets.command('activate')
@click.argument('asset_id')
@click.option('--format', 'output_format', type=click.Choice(['json', 'table']), default='table', help='Output format')
def activate_asset(asset_id: str, output_format: str):
    """Activate an asset"""
    try:
        # API endpoint structure: /api/v1/assets/{id}/activate/ (assets/ from api/urls.py + assets from router)
        result = api_client.post(f'assets/{asset_id}/activate/')
        
        if output_format == 'json':
            click.echo(json.dumps(result, indent=2))
        else:
            click.echo(f"Asset activated successfully!")
            click.echo(f"ID: {result.get('id')}")
            click.echo(f"Status: {result.get('status')}")
    except click.ClickException:
        raise
    except Exception as e:
        raise click.ClickException(f"Failed to activate asset: {e}")

