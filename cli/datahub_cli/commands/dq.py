"""
Data Quality management commands.
"""
import click
import json
import time
from typing import Optional
from ..api_client import api_client


@click.group()
def dq():
    """Data Quality management commands"""
    pass


@dq.command('run')
@click.option('--asset-id', help='Asset ID to run DQ check on')
@click.option('--dataset-id', help='Dataset ID to run DQ check on')
@click.option('--file-id', help='File ID for external/scan-only DQ check')
@click.option('--profile-key', default='intake_basic_gx', help='DQ profile key (default: intake_basic_gx)')
@click.option('--format', 'output_format', type=click.Choice(['json', 'table']), default='table', help='Output format')
def run_dq(asset_id: Optional[str], dataset_id: Optional[str], file_id: Optional[str], profile_key: str, output_format: str):
    """Run a Data Quality check"""
    # Validate that at least one resource ID is provided
    if not asset_id and not dataset_id and not file_id:
        raise click.ClickException("At least one of --asset-id, --dataset-id, or --file-id must be provided")
    
    data = {
        'profile_key': profile_key
    }
    if asset_id:
        data['asset_id'] = asset_id
    if dataset_id:
        data['dataset_id'] = dataset_id
    if file_id:
        data['file_id'] = file_id
        data['run_scope'] = 'EXTERNAL'
    
    try:
        # API endpoint structure: /api/v1/dq-runs/ (dq-runs from api/urls.py)
        result = api_client.post('dq-runs/', json_data=data)
        
        if output_format == 'json':
            click.echo(json.dumps(result, indent=2))
        else:
            dq_run = result.get('dq_run', {})
            job = result.get('job', {})
            
            click.echo(f"DQ check started successfully!")
            click.echo(f"DQ Run ID: {dq_run.get('id')}")
            click.echo(f"Job ID: {job.get('id')}")
            click.echo(f"Status: {dq_run.get('status', 'PENDING')}")
            click.echo(f"Profile: {dq_run.get('profile_key', profile_key)}")
            if job.get('id'):
                click.echo(f"\nMonitor progress with: datahub jobs watch {job.get('id')}")
    except click.ClickException:
        raise
    except Exception as e:
        raise click.ClickException(f"Failed to run DQ check: {e}")


@dq.command('get')
@click.argument('dq_run_id')
@click.option('--format', 'output_format', type=click.Choice(['json', 'table']), default='table', help='Output format')
def get_dq_run(dq_run_id: str, output_format: str):
    """Get DQ run details and results"""
    try:
        # API endpoint structure: /api/v1/dq-runs/{id}/ (dq-runs from api/urls.py)
        data = api_client.get(f'dq-runs/{dq_run_id}/')
        
        if output_format == 'json':
            click.echo(json.dumps(data, indent=2))
        else:
            # Table format
            click.echo(f"DQ Run ID: {data.get('id')}")
            click.echo(f"Status: {data.get('status')}")
            click.echo(f"Overall Status: {data.get('overall_status', 'UNKNOWN')}")
            click.echo(f"Quality Score: {data.get('quality_score', 'N/A')}")
            click.echo(f"Profile: {data.get('profile_key', 'N/A')}")
            if data.get('asset_id'):
                click.echo(f"Asset ID: {data.get('asset_id')}")
            if data.get('dataset_id'):
                click.echo(f"Dataset ID: {data.get('dataset_id')}")
            if data.get('job_id'):
                click.echo(f"Job ID: {data.get('job_id')}")
            
            click.echo(f"Started: {data.get('started_at', 'N/A')}")
            click.echo(f"Completed: {data.get('completed_at', 'N/A')}")
            
            # Show check results summary
            checks = data.get('checks_json', [])
            if checks:
                click.echo(f"\nChecks ({len(checks)}):")
                passed = sum(1 for c in checks if c.get('status') == 'PASS')
                failed = sum(1 for c in checks if c.get('status') == 'FAIL')
                warnings = sum(1 for c in checks if c.get('status') == 'WARN')
                click.echo(f"  Passed: {passed}")
                click.echo(f"  Failed: {failed}")
                click.echo(f"  Warnings: {warnings}")
                
                # Show failed checks
                failed_checks = [c for c in checks if c.get('status') == 'FAIL']
                if failed_checks:
                    click.echo(f"\nFailed Checks:")
                    for check in failed_checks[:10]:  # Show first 10
                        check_name = check.get('name', 'Unknown')
                        category = check.get('category', 'UNKNOWN')
                        click.echo(f"  - {check_name} ({category})")
                    if len(failed_checks) > 10:
                        click.echo(f"  ... and {len(failed_checks) - 10} more")
    except click.ClickException:
        raise
    except Exception as e:
        raise click.ClickException(f"Failed to get DQ run: {e}")


@dq.command('list')
@click.option('--asset-id', help='Filter by asset ID')
@click.option('--dataset-id', help='Filter by dataset ID')
@click.option('--status', help='Filter by status (PENDING, RUNNING, SUCCEEDED, FAILED)')
@click.option('--limit', type=int, default=20, help='Limit number of results')
@click.option('--offset', type=int, default=0, help='Offset for pagination')
@click.option('--format', 'output_format', type=click.Choice(['json', 'table']), default='table', help='Output format')
def list_dq_runs(asset_id: Optional[str], dataset_id: Optional[str], status: Optional[str], limit: int, offset: int, output_format: str):
    """List DQ runs"""
    params = {'limit': limit, 'offset': offset}
    if asset_id:
        params['asset_id'] = asset_id
    if dataset_id:
        params['dataset_id'] = dataset_id
    if status:
        params['status'] = status
    
    try:
        # API endpoint structure: /api/v1/dq-runs/ (dq-runs from api/urls.py)
        data = api_client.get('dq-runs/', params=params)
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
                click.echo("No DQ runs found.")
                return
            
            # Table format
            click.echo(f"{'ID':<40} {'Status':<15} {'Overall Status':<15} {'Score':<10} {'Profile':<20}")
            click.echo("-" * 100)
            for dq_run in results:
                click.echo(
                    f"{dq_run.get('id', '')[:36]:<40} "
                    f"{dq_run.get('status', '')[:13]:<15} "
                    f"{dq_run.get('overall_status', 'UNKNOWN')[:13]:<15} "
                    f"{dq_run.get('quality_score', 'N/A'):<10} "
                    f"{dq_run.get('profile_key', '')[:18]:<20}"
                )
    except click.ClickException:
        raise
    except Exception as e:
        raise click.ClickException(f"Failed to list DQ runs: {e}")


@dq.command('watch')
@click.argument('dq_run_id')
@click.option('--interval', type=int, default=2, help='Polling interval in seconds')
@click.option('--timeout', type=int, default=300, help='Timeout in seconds')
@click.option('--format', 'output_format', type=click.Choice(['json', 'table']), default='table', help='Output format')
def watch_dq_run(dq_run_id: str, interval: int, timeout: int, output_format: str):
    """Watch a DQ run until completion"""
    start_time = time.time()
    
    try:
        while True:
            # Check timeout
            if time.time() - start_time > timeout:
                raise click.ClickException(f"Timeout waiting for DQ run {dq_run_id} to complete")
            
            # Get DQ run status
            # API endpoint structure: /api/v1/dq-runs/{id}/ (dq-runs from api/urls.py)
            data = api_client.get(f'dq-runs/{dq_run_id}/')
            status = data.get('status')
            
            if output_format == 'table':
                overall_status = data.get('overall_status', 'UNKNOWN')
                quality_score = data.get('quality_score', 'N/A')
                click.echo(f"DQ Run {dq_run_id}: {status} | Overall: {overall_status} | Score: {quality_score}")
            
            # Check if DQ run is complete
            if status in ['SUCCEEDED', 'FAILED']:
                if output_format == 'json':
                    click.echo(json.dumps(data, indent=2))
                else:
                    click.echo(f"\nDQ run {status.lower()}!")
                    if status == 'SUCCEEDED':
                        click.echo(f"Overall Status: {data.get('overall_status', 'UNKNOWN')}")
                        click.echo(f"Quality Score: {data.get('quality_score', 'N/A')}")
                        checks = data.get('checks_json', [])
                        if checks:
                            passed = sum(1 for c in checks if c.get('status') == 'PASS')
                            failed = sum(1 for c in checks if c.get('status') == 'FAIL')
                            click.echo(f"Checks: {passed} passed, {failed} failed")
                    elif status == 'FAILED':
                        if data.get('error_message'):
                            click.echo(f"Error: {data.get('error_message')}")
                return
            
            # Wait before next poll
            time.sleep(interval)
    except click.ClickException:
        raise
    except KeyboardInterrupt:
        click.echo("\nWatching cancelled by user.")
        raise
    except Exception as e:
        raise click.ClickException(f"Failed to watch DQ run: {e}")


@dq.command('scorecard')
@click.argument('asset_id')
@click.option('--format', 'output_format', type=click.Choice(['json', 'table']), default='table', help='Output format')
def get_scorecard(asset_id: str, output_format: str):
    """Get DQ scorecard for an asset"""
    try:
        # API endpoint structure: /api/v1/dq/scorecards/{asset_id}/ (dq from api/urls.py)
        data = api_client.get(f'dq/scorecards/{asset_id}/')
        
        if output_format == 'json':
            click.echo(json.dumps(data, indent=2))
        else:
            # Table format
            click.echo(f"Asset ID: {asset_id}")
            click.echo(f"Overall Quality Score: {data.get('overall_score', 'N/A')}")
            click.echo(f"Status: {data.get('status', 'N/A')}")
            
            recent_runs = data.get('recent_runs', [])
            if recent_runs:
                click.echo(f"\nRecent DQ Runs ({len(recent_runs)}):")
                for run in recent_runs[:5]:  # Show last 5
                    click.echo(f"  - {run.get('id', '')[:36]}: {run.get('overall_status', 'UNKNOWN')} (Score: {run.get('quality_score', 'N/A')})")
    except click.ClickException:
        raise
    except Exception as e:
        raise click.ClickException(f"Failed to get DQ scorecard: {e}")


@dq.command('alerts')
@click.option('--list', 'list_alerts', is_flag=True, help='List alerting rules')
@click.option('--create', is_flag=True, help='Create alerting rule (interactive)')
@click.option('--asset-id', help='Asset ID for alerting rule')
@click.option('--threshold', type=float, help='Quality score threshold')
@click.option('--format', 'output_format', type=click.Choice(['json', 'table']), default='table', help='Output format')
def manage_alerts(list_alerts: bool, create: bool, asset_id: Optional[str], threshold: Optional[float], output_format: str):
    """Manage DQ alerting rules"""
    if list_alerts:
        # List alerting rules
        try:
            # API endpoint structure: /api/v1/dq/alerting-rules/ (dq from api/urls.py)
            data = api_client.get('dq/alerting-rules/')
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
                    click.echo("No alerting rules found.")
                    return
                
                # Table format
                click.echo(f"{'ID':<40} {'Asset ID':<40} {'Threshold':<15} {'Status':<15}")
                click.echo("-" * 110)
                for rule in results:
                    click.echo(
                        f"{rule.get('id', '')[:36]:<40} "
                        f"{rule.get('asset_id', 'N/A')[:36]:<40} "
                        f"{rule.get('threshold', 'N/A'):<15} "
                        f"{rule.get('status', 'ACTIVE')[:13]:<15}"
                    )
        except click.ClickException:
            raise
        except Exception as e:
            raise click.ClickException(f"Failed to list alerting rules: {e}")
    elif create:
        # Create alerting rule
        if not asset_id or threshold is None:
            raise click.ClickException("--asset-id and --threshold are required for creating alerting rules")
        
        data = {
            'asset_id': asset_id,
            'threshold': threshold
        }
        
        try:
            # API endpoint structure: /api/v1/dq/alerting-rules/ (dq from api/urls.py)
            result = api_client.post('dq/alerting-rules/', json_data=data)
            
            if output_format == 'json':
                click.echo(json.dumps(result, indent=2))
            else:
                click.echo(f"Alerting rule created successfully!")
                click.echo(f"ID: {result.get('id')}")
                click.echo(f"Asset ID: {result.get('asset_id')}")
                click.echo(f"Threshold: {result.get('threshold')}")
        except click.ClickException:
            raise
        except Exception as e:
            raise click.ClickException(f"Failed to create alerting rule: {e}")
    else:
        # Default: list alerts
        click.echo("Use --list to list alerting rules or --create to create one")
        click.echo("Example: datahub dq alerts --list")
        click.echo("Example: datahub dq alerts --create --asset-id <id> --threshold 80.0")

