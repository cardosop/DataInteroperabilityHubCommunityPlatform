"""
Compliance management commands.
"""
import click
import json
import time
from typing import Optional, List, Dict, Any
from ..api_client import api_client


@click.group()
def compliance():
    """Compliance management commands"""
    pass


@compliance.command('run')
@click.option('--asset-id', help='Asset ID to run compliance check on')
@click.option('--dataset-id', help='Dataset ID to run compliance check on')
@click.option('--file-id', help='File ID for external/scan-only compliance check')
@click.option('--scan-mode', type=click.Choice(['internal', 'external']), default='internal', help='Scan mode (default: internal)')
@click.option('--regulations', help='Comma-separated list of regulations (e.g., GDPR,HIPAA,SOX,LGPD,CCPA)')
@click.option('--format', 'output_format', type=click.Choice(['json', 'table']), default='table', help='Output format')
def run_compliance_check(
    asset_id: Optional[str],
    dataset_id: Optional[str],
    file_id: Optional[str],
    scan_mode: str,
    regulations: Optional[str],
    output_format: str
):
    """Run a compliance check"""
    # Validate that at least one resource ID is provided
    if not asset_id and not dataset_id and not file_id:
        raise click.ClickException("At least one of --asset-id, --dataset-id, or --file-id must be provided")

    data: Dict[str, Any] = {
        'scan_mode': scan_mode
    }

    if asset_id:
        data['asset_id'] = asset_id
    if dataset_id:
        data['dataset_id'] = dataset_id
    if file_id:
        data['file_id'] = file_id

    # Parse regulations if provided
    if regulations:
        applicable_regulations = [r.strip() for r in regulations.split(',')]
        data['applicable_regulations'] = applicable_regulations

    try:
        # API endpoint: /api/v1/compliance/runs/
        result = api_client.post('compliance/runs/', json_data=data)

        if output_format == 'json':
            click.echo(json.dumps(result, indent=2))
        else:
            # API returns compliance run directly, with nested job object
            compliance_run_id = result.get('id')
            job = result.get('job', {})
            job_id = job.get('id') if isinstance(job, dict) else job

            click.echo(f"Compliance check started successfully!")
            click.echo(f"Compliance Run ID: {compliance_run_id}")
            if job_id:
                click.echo(f"Job ID: {job_id}")
            click.echo(f"Status: {result.get('status', 'PENDING')}")
            click.echo(f"Scan Mode: {scan_mode}")
            if regulations:
                click.echo(f"Regulations: {regulations}")
            if job_id:
                click.echo(f"\nMonitor progress with: datahub jobs watch {job_id}")
    except click.ClickException:
        raise
    except Exception as e:
        raise click.ClickException(f"Failed to run compliance check: {e}")


@compliance.command('get')
@click.argument('compliance_run_id')
@click.option('--format', 'output_format', type=click.Choice(['json', 'table']), default='table', help='Output format')
def get_compliance_run(compliance_run_id: str, output_format: str):
    """Get compliance run details and results"""
    try:
        # API endpoint: /api/v1/compliance/runs/{id}/
        data = api_client.get(f'compliance/runs/{compliance_run_id}/')

        if output_format == 'json':
            click.echo(json.dumps(data, indent=2))
        else:
            # Table format
            click.echo(f"Compliance Run ID: {data.get('id')}")
            click.echo(f"Status: {data.get('status')}")
            click.echo(f"Overall Status: {data.get('overall_status', 'UNKNOWN')}")
            click.echo(f"Risk Level: {data.get('risk_level', 'N/A')}")
            click.echo(f"Allowed to Store: {data.get('allowed_to_store', 'N/A')}")

            if data.get('asset_id'):
                click.echo(f"Asset ID: {data.get('asset_id')}")
            if data.get('dataset_id'):
                click.echo(f"Dataset ID: {data.get('dataset_id')}")
            if data.get('file_id'):
                click.echo(f"File ID: {data.get('file_id')}")
            if data.get('job_id'):
                click.echo(f"Job ID: {data.get('job_id')}")

            regulations = data.get('regulations', [])
            if regulations:
                click.echo(f"Regulations: {', '.join(regulations)}")

            click.echo(f"Started: {data.get('started_at', 'N/A')}")
            click.echo(f"Completed: {data.get('completed_at', 'N/A')}")

            # Show detected categories
            detected_categories = data.get('detected_categories_json', {})
            if detected_categories:
                click.echo(f"\nDetected Categories:")
                for category, count in detected_categories.items():
                    click.echo(f"  - {category}: {count}")

            # Show regulation mapping
            regulation_mapping = data.get('regulation_mapping_json', {})
            if regulation_mapping:
                click.echo(f"\nRegulation Mapping:")
                for regulation, details in regulation_mapping.items():
                    click.echo(f"  - {regulation}: {details}")
    except click.ClickException:
        raise
    except Exception as e:
        raise click.ClickException(f"Failed to get compliance run: {e}")


@compliance.command('list')
@click.option('--asset-id', help='Filter by asset ID')
@click.option('--status', type=click.Choice(['PENDING', 'RUNNING', 'SUCCEEDED', 'FAILED']), help='Filter by status')
@click.option('--limit', default=20, help='Limit number of results (default: 20)')
@click.option('--offset', default=0, help='Offset for pagination (default: 0)')
@click.option('--format', 'output_format', type=click.Choice(['json', 'table']), default='table', help='Output format')
def list_compliance_runs(
    asset_id: Optional[str],
    status: Optional[str],
    limit: int,
    offset: int,
    output_format: str
):
    """List compliance runs"""
    try:
        params: Dict[str, Any] = {
            'limit': limit,
            'offset': offset
        }

        if asset_id:
            params['asset_id'] = asset_id
        if status:
            params['status'] = status

        # API endpoint: /api/v1/compliance/runs/
        data = api_client.get('compliance/runs/', params=params)

        if output_format == 'json':
            click.echo(json.dumps(data, indent=2))
        else:
            results = data.get('results', []) if isinstance(data, dict) else data
            if not isinstance(results, list):
                results = []

            if not results:
                click.echo("No compliance runs found.")
                return

            click.echo(f"Found {len(results)} compliance run(s):\n")
            for run in results:
                click.echo(f"ID: {run.get('id')}")
                click.echo(f"  Status: {run.get('status')}")
                click.echo(f"  Overall Status: {run.get('overall_status', 'N/A')}")
                click.echo(f"  Risk Level: {run.get('risk_level', 'N/A')}")
                if run.get('asset_id'):
                    click.echo(f"  Asset ID: {run.get('asset_id')}")
                if run.get('dataset_id'):
                    click.echo(f"  Dataset ID: {run.get('dataset_id')}")
                click.echo(f"  Created: {run.get('created_at', 'N/A')}")
                click.echo()
    except click.ClickException:
        raise
    except Exception as e:
        raise click.ClickException(f"Failed to list compliance runs: {e}")


@compliance.command('report')
@click.option('--asset-id', help='Asset ID to generate report for')
@click.option('--regulation', type=click.Choice(['GDPR', 'HIPAA', 'SOX', 'LGPD', 'CCPA']), required=True, help='Regulation type')
@click.option('--format', 'output_format', type=click.Choice(['json', 'table']), default='table', help='Output format')
def generate_compliance_report(asset_id: Optional[str], regulation: str, output_format: str):
    """Generate a compliance report for a regulation"""
    if not asset_id:
        raise click.ClickException("--asset-id is required for generating compliance reports")

    try:
        # First, get the asset to check compliance status
        asset_data = api_client.get(f'assets/{asset_id}/')

        # Get latest compliance run for the asset
        compliance_runs = api_client.get('compliance/runs/', params={'asset_id': asset_id, 'limit': 1})
        runs = compliance_runs.get('results', []) if isinstance(compliance_runs, dict) else compliance_runs
        if not isinstance(runs, list):
            runs = []

        if not runs:
            click.echo(f"No compliance runs found for asset {asset_id}")
            return

        latest_run = runs[0]

        # Generate report based on regulation
        report_data = {
            'asset_id': asset_id,
            'asset_name': asset_data.get('name', 'N/A'),
            'regulation': regulation,
            'compliance_run_id': latest_run.get('id'),
            'overall_status': latest_run.get('overall_status'),
            'risk_level': latest_run.get('risk_level'),
            'allowed_to_store': latest_run.get('allowed_to_store'),
            'detected_categories': latest_run.get('detected_categories_json', {}),
            'regulation_mapping': latest_run.get('regulation_mapping_json', {}),
            'completed_at': latest_run.get('completed_at')
        }

        if output_format == 'json':
            click.echo(json.dumps(report_data, indent=2))
        else:
            click.echo(f"Compliance Report: {regulation}")
            click.echo(f"{'=' * 50}")
            click.echo(f"Asset: {report_data['asset_name']} ({asset_id})")
            click.echo(f"Regulation: {regulation}")
            click.echo(f"Overall Status: {report_data['overall_status']}")
            click.echo(f"Risk Level: {report_data['risk_level']}")
            click.echo(f"Allowed to Store: {report_data['allowed_to_store']}")
            click.echo(f"Completed: {report_data['completed_at']}")

            if report_data['detected_categories']:
                click.echo(f"\nDetected Categories:")
                for category, count in report_data['detected_categories'].items():
                    click.echo(f"  - {category}: {count}")

            regulation_details = report_data['regulation_mapping'].get(regulation, {})
            if regulation_details:
                click.echo(f"\n{regulation} Details:")
                for key, value in regulation_details.items():
                    click.echo(f"  - {key}: {value}")
    except click.ClickException:
        raise
    except Exception as e:
        raise click.ClickException(f"Failed to generate compliance report: {e}")

