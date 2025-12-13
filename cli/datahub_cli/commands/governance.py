"""
Governance management commands.
"""
import click
import json
from typing import Optional
from ..api_client import api_client


@click.group()
def governance():
    """Governance management commands"""
    pass


@governance.group('access-request')
def access_request():
    """Access request management commands"""
    pass


@access_request.command('create')
@click.option('--asset-id', help='Asset ID to request access for')
@click.option('--dataset-id', help='Dataset ID to request access for')
@click.option('--file-id', help='File ID to request access for')
@click.option('--reason', required=True, help='Reason for access request')
@click.option('--access-type', default='READ', type=click.Choice(['READ', 'WRITE', 'DOWNLOAD']), help='Type of access requested (default: READ)')
@click.option('--expires-at', help='Expiration date (ISO format, optional)')
@click.option('--format', 'output_format', type=click.Choice(['json', 'table']), default='table', help='Output format')
def create_access_request(
    asset_id: Optional[str],
    dataset_id: Optional[str],
    file_id: Optional[str],
    reason: str,
    access_type: str,
    expires_at: Optional[str],
    output_format: str
):
    """Create an access request"""
    # Validate that at least one resource ID is provided
    if not asset_id and not dataset_id and not file_id:
        raise click.ClickException("At least one of --asset-id, --dataset-id, or --file-id must be provided")
    
    data = {
        'reason': reason,
        'requested_access_type': access_type
    }
    
    if asset_id:
        data['asset_id'] = asset_id
    if dataset_id:
        data['dataset_id'] = dataset_id
    if file_id:
        data['file_id'] = file_id
    if expires_at:
        data['expires_at'] = expires_at
    
    try:
        # API endpoint: /api/v1/governance/access-requests/
        result = api_client.post('governance/access-requests/', json_data=data)
        
        if output_format == 'json':
            click.echo(json.dumps(result, indent=2))
        else:
            click.echo(f"Access request created successfully!")
            click.echo(f"Access Request ID: {result.get('id')}")
            click.echo(f"Status: {result.get('status')}")
            click.echo(f"Requested Access Type: {result.get('requested_access_type')}")
            if result.get('asset_id'):
                click.echo(f"Asset ID: {result.get('asset_id')}")
            if result.get('dataset_id'):
                click.echo(f"Dataset ID: {result.get('dataset_id')}")
            if result.get('file_id'):
                click.echo(f"File ID: {result.get('file_id')}")
            if result.get('expires_at'):
                click.echo(f"Expires At: {result.get('expires_at')}")
    except click.ClickException:
        raise
    except Exception as e:
        raise click.ClickException(f"Failed to create access request: {e}")


@access_request.command('get')
@click.argument('access_request_id')
@click.option('--format', 'output_format', type=click.Choice(['json', 'table']), default='table', help='Output format')
def get_access_request(access_request_id: str, output_format: str):
    """Get access request details"""
    try:
        # API endpoint: /api/v1/governance/access-requests/{id}/
        data = api_client.get(f'governance/access-requests/{access_request_id}/')
        
        if output_format == 'json':
            click.echo(json.dumps(data, indent=2))
        else:
            click.echo(f"Access Request ID: {data.get('id')}")
            click.echo(f"Status: {data.get('status')}")
            click.echo(f"Requested Access Type: {data.get('requested_access_type')}")
            click.echo(f"Reason: {data.get('reason')}")
            
            if data.get('asset_id'):
                click.echo(f"Asset ID: {data.get('asset_id')}")
            if data.get('dataset_id'):
                click.echo(f"Dataset ID: {data.get('dataset_id')}")
            if data.get('file_id'):
                click.echo(f"File ID: {data.get('file_id')}")
            
            if data.get('approved_by'):
                click.echo(f"Approved By: {data.get('approved_by')}")
                click.echo(f"Approved At: {data.get('approved_at')}")
            if data.get('rejected_by'):
                click.echo(f"Rejected By: {data.get('rejected_by')}")
                click.echo(f"Rejected At: {data.get('rejected_at')}")
                if data.get('rejection_reason'):
                    click.echo(f"Rejection Reason: {data.get('rejection_reason')}")
            
            if data.get('expires_at'):
                click.echo(f"Expires At: {data.get('expires_at')}")
            
            click.echo(f"Created: {data.get('created_at')}")
            click.echo(f"Updated: {data.get('updated_at')}")
    except click.ClickException:
        raise
    except Exception as e:
        raise click.ClickException(f"Failed to get access request: {e}")


@access_request.command('list')
@click.option('--asset-id', help='Filter by asset ID')
@click.option('--status', type=click.Choice(['PENDING', 'APPROVED', 'REJECTED', 'REVOKED']), help='Filter by status')
@click.option('--limit', default=20, help='Limit number of results (default: 20)')
@click.option('--offset', default=0, help='Offset for pagination (default: 0)')
@click.option('--format', 'output_format', type=click.Choice(['json', 'table']), default='table', help='Output format')
def list_access_requests(
    asset_id: Optional[str],
    status: Optional[str],
    limit: int,
    offset: int,
    output_format: str
):
    """List access requests"""
    try:
        params = {
            'limit': limit,
            'offset': offset
        }
        
        if asset_id:
            params['asset_id'] = asset_id
        if status:
            params['status'] = status
        
        # API endpoint: /api/v1/governance/access-requests/
        data = api_client.get('governance/access-requests/', params=params)
        
        if output_format == 'json':
            click.echo(json.dumps(data, indent=2))
        else:
            results = data.get('results', []) if isinstance(data, dict) else data
            if not isinstance(results, list):
                results = []
            
            if not results:
                click.echo("No access requests found.")
                return
            
            click.echo(f"Found {len(results)} access request(s):\n")
            for req in results:
                click.echo(f"ID: {req.get('id')}")
                click.echo(f"  Status: {req.get('status')}")
                click.echo(f"  Access Type: {req.get('requested_access_type')}")
                if req.get('asset_id'):
                    click.echo(f"  Asset ID: {req.get('asset_id')}")
                if req.get('dataset_id'):
                    click.echo(f"  Dataset ID: {req.get('dataset_id')}")
                click.echo(f"  Created: {req.get('created_at')}")
                click.echo()
    except click.ClickException:
        raise
    except Exception as e:
        raise click.ClickException(f"Failed to list access requests: {e}")


@access_request.command('approve')
@click.argument('access_request_id')
@click.option('--comments', help='Approval comments (optional)')
@click.option('--format', 'output_format', type=click.Choice(['json', 'table']), default='table', help='Output format')
def approve_access_request(access_request_id: str, comments: Optional[str], output_format: str):
    """Approve an access request"""
    try:
        data = {}
        if comments:
            data['comments'] = comments
        
        # API endpoint: /api/v1/governance/access-requests/{id}/approve/
        result = api_client.post(f'governance/access-requests/{access_request_id}/approve/', json_data=data)
        
        if output_format == 'json':
            click.echo(json.dumps(result, indent=2))
        else:
            click.echo(f"Access request approved successfully!")
            click.echo(f"Access Request ID: {result.get('id')}")
            click.echo(f"Status: {result.get('status')}")
            if result.get('approved_at'):
                click.echo(f"Approved At: {result.get('approved_at')}")
    except click.ClickException:
        raise
    except Exception as e:
        raise click.ClickException(f"Failed to approve access request: {e}")


@access_request.command('reject')
@click.argument('access_request_id')
@click.option('--reason', required=True, help='Rejection reason')
@click.option('--format', 'output_format', type=click.Choice(['json', 'table']), default='table', help='Output format')
def reject_access_request(access_request_id: str, reason: str, output_format: str):
    """Reject an access request"""
    try:
        data = {
            'reason': reason
        }
        
        # API endpoint: /api/v1/governance/access-requests/{id}/reject/
        result = api_client.post(f'governance/access-requests/{access_request_id}/reject/', json_data=data)
        
        if output_format == 'json':
            click.echo(json.dumps(result, indent=2))
        else:
            click.echo(f"Access request rejected successfully!")
            click.echo(f"Access Request ID: {result.get('id')}")
            click.echo(f"Status: {result.get('status')}")
            if result.get('rejected_at'):
                click.echo(f"Rejected At: {result.get('rejected_at')}")
            if result.get('rejection_reason'):
                click.echo(f"Rejection Reason: {result.get('rejection_reason')}")
    except click.ClickException:
        raise
    except Exception as e:
        raise click.ClickException(f"Failed to reject access request: {e}")

