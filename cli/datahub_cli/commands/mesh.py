"""
Data Mesh management commands.
"""
import click
import json
from typing import Optional, Dict, Any
from ..api_client import api_client


@click.group()
def mesh():
    """Data Mesh management commands [Post-MVP]"""
    pass


@mesh.command('info')
@click.option('--format', 'output_format', type=click.Choice(['json', 'table']), default='table', help='Output format')
def mesh_info(output_format: str):
    """Get data mesh information"""
    try:
        data = {
            "status": "available",
            "message": "Mesh command module is registered and functional"
        }

        if output_format == 'json':
            click.echo(json.dumps(data, indent=2))
        else:
            click.echo("Status: Available")
            click.echo("Message: Mesh command module is registered and functional")
    except click.ClickException:
        raise
    except Exception as e:
        raise click.ClickException(f"Failed to get mesh info: {e}")


@mesh.group('domains')
def domains():
    """Domain management commands"""
    pass


@domains.command('list')
@click.option('--status', type=click.Choice(['ACTIVE', 'INACTIVE', 'ARCHIVED']), help='Filter by status')
@click.option('--owner-id', help='Filter by owner user ID')
@click.option('--search', help='Search in name and description')
@click.option('--ordering', help='Order by field (name, status, created_at, updated_at). Prefix with - for descending')
@click.option('--page', type=int, default=1, help='Page number (default: 1)')
@click.option('--page-size', type=int, default=20, help='Page size (default: 20, max: 100)')
@click.option('--format', 'output_format', type=click.Choice(['json', 'table']), default='table', help='Output format')
def list_domains(
    status: Optional[str],
    owner_id: Optional[str],
    search: Optional[str],
    ordering: Optional[str],
    page: int,
    page_size: int,
    output_format: str
):
    """List data mesh domains with filtering and pagination"""
    try:
        # Build query parameters
        params: Dict[str, Any] = {
            'page': page,
            'page_size': min(page_size, 100)  # Enforce max page size
        }

        if status:
            params['status'] = status
        if owner_id:
            params['owner_id'] = owner_id
        if search:
            params['search'] = search
        if ordering:
            params['ordering'] = ordering

        # API endpoint: /api/v1/mesh/domains/
        data = api_client.get('mesh/domains/', params=params)

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
                click.echo("No domains found.")
                return

            # Table format
            click.echo(f"{'ID':<40} {'Name':<30} {'Status':<12} {'Owner':<40} {'Created':<20}")
            click.echo("-" * 142)
            for domain_item in results:
                if not isinstance(domain_item, dict):
                    continue
                domain_id = domain_item.get('id', '')[:36] if domain_item.get('id') else 'N/A'
                name = (domain_item.get('name', '')[:28] + '..') if len(domain_item.get('name', '')) > 30 else domain_item.get('name', 'N/A')
                status_val = domain_item.get('status', 'N/A')
                owner = domain_item.get('owner', '')[:36] if domain_item.get('owner') else 'N/A'
                created = domain_item.get('created_at', '')[:19] if domain_item.get('created_at') else 'N/A'
                click.echo(f"{domain_id:<40} {name:<30} {status_val:<12} {owner:<40} {created:<20}")

            # Show pagination info
            if count > len(results):
                click.echo(f"\nShowing {len(results)} of {count} domains")
                if next_page:
                    click.echo(f"Next page: --page {page + 1}")
                if previous_page:
                    click.echo(f"Previous page: --page {page - 1}")
    except click.ClickException:
        raise
    except Exception as e:
        raise click.ClickException(f"Failed to list domains: {e}")


@domains.command('create')
@click.option('--name', required=True, help='Domain name (required)')
@click.option('--description', help='Domain description')
@click.option('--owner-id', help='Owner user ID')
@click.option('--boundaries', help='Domain boundaries as JSON string')
@click.option('--capabilities', help='Domain capabilities as JSON string')
@click.option('--resource-quota', help='Resource quotas as JSON string')
@click.option('--status', type=click.Choice(['ACTIVE', 'INACTIVE', 'ARCHIVED']), default='ACTIVE', help='Domain status (default: ACTIVE)')
@click.option('--format', 'output_format', type=click.Choice(['json', 'table']), default='table', help='Output format')
def create_domain(
    name: str,
    description: Optional[str],
    owner_id: Optional[str],
    boundaries: Optional[str],
    capabilities: Optional[str],
    resource_quota: Optional[str],
    status: str,
    output_format: str
):
    """Create a new data mesh domain"""
    try:
        # Build request data
        data = {
            'name': name.strip(),
            'status': status
        }

        if description:
            data['description'] = description
        if owner_id:
            data['owner_id'] = owner_id
        if boundaries:
            try:
                data['boundaries'] = json.loads(boundaries)
            except json.JSONDecodeError:
                raise click.ClickException(f"Invalid JSON in --boundaries: {boundaries}")
        if capabilities:
            try:
                data['capabilities'] = json.loads(capabilities)
            except json.JSONDecodeError:
                raise click.ClickException(f"Invalid JSON in --capabilities: {capabilities}")
        if resource_quota:
            try:
                quota_dict = json.loads(resource_quota)
                # Validate quota values are numbers
                for key, val in quota_dict.items():
                    if not isinstance(val, (int, float)):
                        raise click.ClickException(f"Resource quota '{key}' must be a number")
                    if val < 0:
                        raise click.ClickException(f"Resource quota '{key}' cannot be negative")
                data['resource_quota'] = quota_dict
            except json.JSONDecodeError:
                raise click.ClickException(f"Invalid JSON in --resource-quota: {resource_quota}")

        # API endpoint: /api/v1/mesh/domains/
        result = api_client.post('mesh/domains/', json_data=data)

        if output_format == 'json':
            click.echo(json.dumps(result, indent=2))
        else:
            click.echo("Domain created successfully!")
            click.echo(f"Domain ID: {result.get('id')}")
            click.echo(f"Name: {result.get('name')}")
            click.echo(f"Status: {result.get('status')}")
            if result.get('description'):
                click.echo(f"Description: {result.get('description')}")
            if result.get('owner'):
                click.echo(f"Owner ID: {result.get('owner')}")
            if result.get('owner_email'):
                click.echo(f"Owner Email: {result.get('owner_email')}")
            if result.get('tenant_name'):
                click.echo(f"Tenant: {result.get('tenant_name')}")
            click.echo(f"Created: {result.get('created_at')}")
    except click.ClickException:
        raise
    except Exception as e:
        raise click.ClickException(f"Failed to create domain: {e}")


@domains.command('get')
@click.argument('domain_id')
@click.option('--format', 'output_format', type=click.Choice(['json', 'table']), default='table', help='Output format')
def get_domain(domain_id: str, output_format: str):
    """Get domain details by ID"""
    try:
        # API endpoint: /api/v1/mesh/domains/{id}/
        data = api_client.get(f'mesh/domains/{domain_id}/')

        if output_format == 'json':
            click.echo(json.dumps(data, indent=2))
        else:
            click.echo(f"Domain ID: {data.get('id')}")
            click.echo(f"Name: {data.get('name')}")
            click.echo(f"Status: {data.get('status')}")
            if data.get('description'):
                click.echo(f"Description: {data.get('description')}")
            if data.get('owner'):
                click.echo(f"Owner ID: {data.get('owner')}")
            if data.get('owner_email'):
                click.echo(f"Owner Email: {data.get('owner_email')}")
            if data.get('tenant_name'):
                click.echo(f"Tenant: {data.get('tenant_name')}")
            if data.get('boundaries'):
                click.echo(f"Boundaries: {json.dumps(data.get('boundaries'), indent=2)}")
            if data.get('capabilities'):
                click.echo(f"Capabilities: {json.dumps(data.get('capabilities'), indent=2)}")
            if data.get('resource_quota'):
                click.echo(f"Resource Quota: {json.dumps(data.get('resource_quota'), indent=2)}")
            if data.get('resource_usage'):
                click.echo(f"Resource Usage: {json.dumps(data.get('resource_usage'), indent=2)}")
            click.echo(f"Created: {data.get('created_at')}")
            click.echo(f"Updated: {data.get('updated_at')}")
    except click.ClickException:
        raise
    except Exception as e:
        raise click.ClickException(f"Failed to get domain: {e}")


@domains.command('update')
@click.argument('domain_id')
@click.option('--name', help='Domain name')
@click.option('--description', help='Domain description')
@click.option('--owner-id', help='Owner user ID')
@click.option('--boundaries', help='Domain boundaries as JSON string')
@click.option('--capabilities', help='Domain capabilities as JSON string')
@click.option('--resource-quota', help='Resource quotas as JSON string')
@click.option('--status', type=click.Choice(['ACTIVE', 'INACTIVE', 'ARCHIVED']), help='Domain status')
@click.option('--format', 'output_format', type=click.Choice(['json', 'table']), default='table', help='Output format')
def update_domain(
    domain_id: str,
    name: Optional[str],
    description: Optional[str],
    owner_id: Optional[str],
    boundaries: Optional[str],
    capabilities: Optional[str],
    resource_quota: Optional[str],
    status: Optional[str],
    output_format: str
):
    """Update an existing data mesh domain"""
    try:
        # Build request data (only include provided fields)
        data = {}

        if name:
            data['name'] = name.strip()
        if description is not None:  # Allow empty string
            data['description'] = description
        if owner_id:
            data['owner_id'] = owner_id
        if boundaries:
            try:
                data['boundaries'] = json.loads(boundaries)
            except json.JSONDecodeError:
                raise click.ClickException(f"Invalid JSON in --boundaries: {boundaries}")
        if capabilities:
            try:
                data['capabilities'] = json.loads(capabilities)
            except json.JSONDecodeError:
                raise click.ClickException(f"Invalid JSON in --capabilities: {capabilities}")
        if resource_quota:
            try:
                quota_dict = json.loads(resource_quota)
                # Validate quota values are numbers
                for key, val in quota_dict.items():
                    if not isinstance(val, (int, float)):
                        raise click.ClickException(f"Resource quota '{key}' must be a number")
                    if val < 0:
                        raise click.ClickException(f"Resource quota '{key}' cannot be negative")
                data['resource_quota'] = quota_dict
            except json.JSONDecodeError:
                raise click.ClickException(f"Invalid JSON in --resource-quota: {resource_quota}")
        if status:
            data['status'] = status

        if not data:
            raise click.ClickException("At least one field must be provided for update")

        # API endpoint: /api/v1/mesh/domains/{id}/
        result = api_client.patch(f'mesh/domains/{domain_id}/', json_data=data)

        if output_format == 'json':
            click.echo(json.dumps(result, indent=2))
        else:
            click.echo("Domain updated successfully!")
            click.echo(f"Domain ID: {result.get('id')}")
            click.echo(f"Name: {result.get('name')}")
            click.echo(f"Status: {result.get('status')}")
            if result.get('description'):
                click.echo(f"Description: {result.get('description')}")
            if result.get('owner'):
                click.echo(f"Owner ID: {result.get('owner')}")
            click.echo(f"Updated: {result.get('updated_at')}")
    except click.ClickException:
        raise
    except Exception as e:
        raise click.ClickException(f"Failed to update domain: {e}")


@domains.command('delete')
@click.argument('domain_id')
@click.option('--format', 'output_format', type=click.Choice(['json', 'table']), default='table', help='Output format')
@click.confirmation_option(prompt='Are you sure you want to delete this domain?')
def delete_domain(domain_id: str, output_format: str):
    """Delete a data mesh domain"""
    try:
        # API endpoint: /api/v1/mesh/domains/{id}/
        result = api_client.delete(f'mesh/domains/{domain_id}/')

        if output_format == 'json':
            click.echo(json.dumps(result, indent=2))
        else:
            click.echo(f"Domain {domain_id} deleted successfully!")
    except click.ClickException:
        raise
    except Exception as e:
        raise click.ClickException(f"Failed to delete domain: {e}")


@mesh.group('topology')
def topology():
    """Topology management commands"""
    pass


@topology.command('get')
@click.option('--include-health-metrics/--no-include-health-metrics', default=True, help='Include health metrics in response (default: true)')
@click.option('--format', 'output_format', type=click.Choice(['json', 'table']), default='table', help='Output format')
def get_topology(include_health_metrics: bool, output_format: str):
    """Get complete data mesh topology including all domains, relationships, and health metrics"""
    try:
        # Build query parameters
        params: Dict[str, Any] = {
            'include_health_metrics': str(include_health_metrics).lower()
        }

        # API endpoint: /api/v1/mesh/topology/
        data = api_client.get('mesh/topology/', params=params)

        if output_format == 'json':
            click.echo(json.dumps(data, indent=2))
        else:
            # Table format - display summary and key information
            summary = data.get('summary', {})
            metadata = data.get('metadata', {})
            nodes = data.get('nodes', [])
            edges = data.get('edges', [])

            click.echo("=" * 80)
            click.echo("MESH TOPOLOGY SUMMARY")
            click.echo("=" * 80)
            click.echo(f"Total Domains: {summary.get('total_domains', 0)}")
            click.echo(f"Active Domains: {summary.get('active_domains', 0)}")
            click.echo(f"Total Relationships: {summary.get('total_relationships', 0)}")
            avg_health = summary.get('average_health_score')
            if avg_health is not None:
                click.echo(f"Average Health Score: {avg_health:.2f}")
            else:
                click.echo("Average Health Score: N/A")

            if metadata.get('generated_at'):
                click.echo(f"Generated At: {metadata.get('generated_at')}")

            click.echo("\n" + "=" * 80)
            click.echo("DOMAINS")
            click.echo("=" * 80)

            if not nodes:
                click.echo("No domains found.")
            else:
                click.echo(f"{'ID':<40} {'Name':<30} {'Status':<12} {'Health Score':<15}")
                click.echo("-" * 97)
                for node in nodes:
                    if not isinstance(node, dict):
                        continue
                    node_id = str(node.get('id', ''))[:36] if node.get('id') else 'N/A'
                    name = (node.get('name', '')[:28] + '..') if len(node.get('name', '')) > 30 else node.get('name', 'N/A')
                    status = node.get('status', 'N/A')
                    health_metrics = node.get('health_metrics', {})
                    health_score = health_metrics.get('health_score') if health_metrics else None
                    health_str = f"{health_score:.2f}" if health_score is not None else "N/A"
                    click.echo(f"{node_id:<40} {name:<30} {status:<12} {health_str:<15}")

            click.echo("\n" + "=" * 80)
            click.echo("RELATIONSHIPS")
            click.echo("=" * 80)

            if not edges:
                click.echo("No relationships found.")
            else:
                click.echo(f"{'Source Domain ID':<40} {'Target Domain ID':<40} {'Type':<20} {'Weight':<10}")
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
        raise click.ClickException(f"Failed to get topology: {e}")


@topology.command('get-domain')
@click.argument('domain_id')
@click.option('--format', 'output_format', type=click.Choice(['json', 'table']), default='table', help='Output format')
def get_domain_topology(domain_id: str, output_format: str):
    """Get topology view for a specific domain including its relationships and health metrics"""
    try:
        # API endpoint: /api/v1/mesh/topology/{domain_id}/
        data = api_client.get(f'mesh/topology/{domain_id}/')

        if output_format == 'json':
            click.echo(json.dumps(data, indent=2))
        else:
            # Table format - display domain and relationships
            domain = data.get('domain', {})
            relationships = data.get('relationships', [])
            health_metrics = data.get('health_metrics', {})

            click.echo("=" * 80)
            click.echo("DOMAIN TOPOLOGY")
            click.echo("=" * 80)

            click.echo(f"Domain ID: {domain.get('id')}")
            click.echo(f"Name: {domain.get('name')}")
            click.echo(f"Status: {domain.get('status')}")
            if domain.get('description'):
                click.echo(f"Description: {domain.get('description')}")
            if domain.get('owner_id'):
                click.echo(f"Owner ID: {domain.get('owner_id')}")
            if domain.get('created_at'):
                click.echo(f"Created At: {domain.get('created_at')}")

            click.echo("\n" + "-" * 80)
            click.echo("HEALTH METRICS")
            click.echo("-" * 80)

            if health_metrics:
                health_score = health_metrics.get('health_score')
                if health_score is not None:
                    click.echo(f"Health Score: {health_score:.2f}")
                else:
                    click.echo("Health Score: N/A")

                compliance_status = health_metrics.get('compliance_status')
                if compliance_status:
                    click.echo(f"Compliance Status: {compliance_status}")

                violations_count = health_metrics.get('violations_count')
                if violations_count is not None:
                    click.echo(f"Violations Count: {violations_count}")
            else:
                click.echo("No health metrics available.")

            click.echo("\n" + "-" * 80)
            click.echo("RELATIONSHIPS")
            click.echo("-" * 80)

            if not relationships:
                click.echo("No relationships found.")
            else:
                click.echo(f"{'Source Domain ID':<40} {'Target Domain ID':<40} {'Type':<20} {'Weight':<10}")
                click.echo("-" * 110)
                for rel in relationships:
                    if not isinstance(rel, dict):
                        continue
                    source = str(rel.get('source', ''))[:36] if rel.get('source') else 'N/A'
                    target = str(rel.get('target', ''))[:36] if rel.get('target') else 'N/A'
                    rel_type = rel.get('type', 'N/A')
                    weight = rel.get('weight', 'N/A')
                    click.echo(f"{source:<40} {target:<40} {rel_type:<20} {weight:<10}")
    except click.ClickException:
        raise
    except Exception as e:
        raise click.ClickException(f"Failed to get domain topology: {e}")


@mesh.group('policies')
def policies():
    """Policy management commands for data mesh domains"""
    pass


@policies.command('apply')
@click.argument('domain_id')
@click.option('--policy', 'policy_id', required=True, help='Policy ID to apply (required)')
@click.option('--overrides', help='Policy overrides as JSON string (conditions, effect, priority, etc.)')
@click.option('--format', 'output_format', type=click.Choice(['json', 'table']), default='table', help='Output format')
def apply_policy(domain_id: str, policy_id: str, overrides: Optional[str], output_format: str):
    """Apply a policy to a data mesh domain"""
    try:
        # Build request data
        data: Dict[str, Any] = {
            'policy_id': policy_id.strip()
        }

        if overrides:
            try:
                overrides_dict = json.loads(overrides)
                if not isinstance(overrides_dict, dict):
                    raise click.ClickException("Overrides must be a JSON object")
                # Ensure overrides is a proper dict for JSON serialization
                data['overrides'] = dict(overrides_dict)
            except json.JSONDecodeError as e:
                raise click.ClickException(f"Invalid JSON in --overrides: {e}")

        # API endpoint: /api/v1/mesh/domains/{domain_id}/policies/apply/
        result = api_client.post(f'mesh/domains/{domain_id}/policies/apply/', json_data=data)

        if output_format == 'json':
            click.echo(json.dumps(result, indent=2))
        else:
            click.echo("Policy applied successfully!")
            click.echo(f"Policy Application ID: {result.get('id')}")
            click.echo(f"Policy ID: {result.get('policy_id')}")
            click.echo(f"Domain ID: {result.get('domain_id')}")
            click.echo(f"Status: {result.get('status')}")
            if result.get('overrides'):
                click.echo(f"Overrides: {json.dumps(result.get('overrides'), indent=2)}")
            if result.get('applied_at'):
                click.echo(f"Applied At: {result.get('applied_at')}")
            if result.get('applied_by'):
                click.echo(f"Applied By: {result.get('applied_by')}")
    except click.ClickException:
        raise
    except Exception as e:
        raise click.ClickException(f"Failed to apply policy: {e}")


@policies.command('list')
@click.argument('domain_id')
@click.option('--status', type=click.Choice(['PENDING', 'APPLIED', 'FAILED', 'REVOKED']), help='Filter by policy application status')
@click.option('--page', type=int, default=1, help='Page number (default: 1)')
@click.option('--page-size', type=int, default=20, help='Page size (default: 20, max: 100)')
@click.option('--format', 'output_format', type=click.Choice(['json', 'table']), default='table', help='Output format')
def list_policies(
    domain_id: str,
    status: Optional[str],
    page: int,
    page_size: int,
    output_format: str
):
    """List policies applied to a data mesh domain"""
    try:
        # Build query parameters
        params: Dict[str, Any] = {
            'page': page,
            'page_size': min(page_size, 100)  # Enforce max page size
        }

        if status:
            params['status'] = status

        # API endpoint: /api/v1/mesh/domains/{domain_id}/policies/
        data = api_client.get(f'mesh/domains/{domain_id}/policies/', params=params)

        # Handle paginated response
        if isinstance(data, dict) and 'results' in data:
            results: list = data.get('results', [])
            count: int = data.get('count', len(results))
            page_number: int = data.get('page', page)
            page_size_actual: int = data.get('page_size', page_size)
            total_pages: int = data.get('total_pages', 1)
        elif isinstance(data, list):
            results = data
            count = len(results)
            page_number = 1
            page_size_actual = len(results)
            total_pages = 1
        else:
            results = []
            count = 0
            page_number = 1
            page_size_actual = 0
            total_pages = 0

        if output_format == 'json':
            output: Dict[str, Any] = {
                'count': count,
                'page': page_number,
                'page_size': page_size_actual,
                'total_pages': total_pages,
                'results': results
            }
            click.echo(json.dumps(output, indent=2))
        else:
            if not results:
                click.echo("No policies found.")
                return

            # Table format
            click.echo(f"{'Policy ID':<40} {'Policy Name':<30} {'Status':<12} {'Applied At':<20} {'Applied By':<40}")
            click.echo("-" * 142)
            for policy_item in results:
                if not isinstance(policy_item, dict):
                    continue
                policy_id = policy_item.get('policy_id', '')[:36] if policy_item.get('policy_id') else 'N/A'
                policy_name = (policy_item.get('policy_name', '')[:28] + '..') if len(policy_item.get('policy_name', '')) > 30 else policy_item.get('policy_name', 'N/A')
                status_val = policy_item.get('status', 'N/A')
                applied_at = policy_item.get('applied_at', '')[:19] if policy_item.get('applied_at') else 'N/A'
                applied_by = policy_item.get('applied_by', '')[:36] if policy_item.get('applied_by') else 'N/A'
                click.echo(f"{policy_id:<40} {policy_name:<30} {status_val:<12} {applied_at:<20} {applied_by:<40}")

            # Show pagination info
            if count > len(results):
                click.echo(f"\nShowing {len(results)} of {count} policies (Page {page_number} of {total_pages})")
                if page_number < total_pages:
                    click.echo(f"Next page: --page {page_number + 1}")
                if page_number > 1:
                    click.echo(f"Previous page: --page {page_number - 1}")
    except click.ClickException:
        raise
    except Exception as e:
        raise click.ClickException(f"Failed to list policies: {e}")


@policies.command('remove')
@click.argument('domain_id')
@click.argument('policy_id')
@click.option('--reason', help='Reason for removing the policy')
@click.option('--format', 'output_format', type=click.Choice(['json', 'table']), default='table', help='Output format')
def remove_policy(domain_id: str, policy_id: str, reason: Optional[str], output_format: str):
    """Remove a policy from a data mesh domain"""
    try:
        # Build request data
        data = {}
        if reason:
            data['reason'] = reason.strip()

        # API endpoint: /api/v1/mesh/domains/{domain_id}/policies/{policy_id}
        result = api_client.delete(f'mesh/domains/{domain_id}/policies/{policy_id}/', json_data=data if data else None)

        if output_format == 'json':
            click.echo(json.dumps(result, indent=2))
        else:
            click.echo("Policy removed successfully!")
            if result:
                click.echo(f"Policy Application ID: {result.get('id')}")
                click.echo(f"Policy ID: {result.get('policy_id')}")
                click.echo(f"Domain ID: {result.get('domain_id')}")
                click.echo(f"Status: {result.get('status')}")
            else:
                click.echo(f"Policy {policy_id} removed from domain {domain_id}")
    except click.ClickException:
        raise
    except Exception as e:
        raise click.ClickException(f"Failed to remove policy: {e}")


@mesh.group('compliance')
def compliance():
    """Compliance management commands for data mesh domains"""
    pass


@compliance.command('check')
@click.argument('domain_id')
@click.option('--asset-id', help='Optional asset ID to check compliance for specific asset')
@click.option('--format', 'output_format', type=click.Choice(['json', 'table']), default='table', help='Output format')
def check_compliance(domain_id: str, asset_id: Optional[str], output_format: str):
    """Check compliance status for a data mesh domain"""
    try:
        # Build request data
        data = {}
        if asset_id:
            data['asset_id'] = asset_id.strip()

        # API endpoint: /api/v1/mesh/domains/{domain_id}/compliance/check/
        result = api_client.post(f'mesh/domains/{domain_id}/compliance/check/', json_data=data)

        if output_format == 'json':
            click.echo(json.dumps(result, indent=2))
        else:
            # Table format
            click.echo("Compliance check completed successfully!")
            click.echo(f"Report ID: {result.get('id', 'N/A')}")
            click.echo(f"Domain ID: {result.get('domain_id', 'N/A')}")
            if result.get('asset_id'):
                click.echo(f"Asset ID: {result.get('asset_id')}")
            click.echo(f"Compliance Status: {result.get('compliance_status', 'N/A')}")
            click.echo(f"Risk Level: {result.get('risk_level', 'N/A')}")
            click.echo(f"Violation Count: {result.get('violation_count', 0)}")

            if result.get('summary'):
                click.echo(f"Summary: {result.get('summary')}")

            if result.get('generated_at'):
                click.echo(f"Generated At: {result.get('generated_at')}")

            # Show violations if any
            violations = result.get('violations', [])
            if violations:
                click.echo(f"\nViolations ({len(violations)}):")
                for i, violation in enumerate(violations[:10], 1):  # Show first 10
                    if isinstance(violation, dict):
                        violation_type = violation.get('type', 'N/A')
                        violation_desc = violation.get('description', 'N/A')
                        click.echo(f"  {i}. [{violation_type}] {violation_desc}")
                    else:
                        click.echo(f"  {i}. {violation}")
                if len(violations) > 10:
                    click.echo(f"  ... and {len(violations) - 10} more violations")
    except click.ClickException:
        raise
    except Exception as e:
        raise click.ClickException(f"Failed to check compliance: {e}")


@compliance.command('report')
@click.argument('domain_id')
@click.option('--report-id', help='Specific compliance report ID to retrieve')
@click.option('--format', 'output_format', type=click.Choice(['json', 'table']), default='table', help='Output format')
def get_compliance_report(domain_id: str, report_id: Optional[str], output_format: str):
    """Get compliance report for a data mesh domain"""
    try:
        if report_id:
            # Get specific report by ID
            # API endpoint: /api/v1/mesh/domains/{domain_id}/compliance/reports/{report_id}/
            result = api_client.get(f'mesh/domains/{domain_id}/compliance/reports/{report_id}/')
        else:
            # Get latest report (first from list)
            # API endpoint: /api/v1/mesh/domains/{domain_id}/compliance/reports/
            data = api_client.get(f'mesh/domains/{domain_id}/compliance/reports/', params={'page_size': 1})

            # Handle paginated response
            if isinstance(data, dict) and 'results' in data:
                results: list = data.get('results', [])
            elif isinstance(data, list):
                results = data
            else:
                results = []

            if not results:
                click.echo("No compliance reports found for this domain.")
                click.echo("Run 'mesh compliance check <domain-id>' to generate a compliance report.")
                return

            # Get the latest report (first in list)
            # Type checker: results is guaranteed to be non-empty here due to check above
            # Access first element safely
            first_result: Any = results[0] if len(results) > 0 else {}
            latest_report_id = first_result.get('id') if isinstance(first_result, dict) else None
            if not latest_report_id:
                click.echo("No compliance reports found for this domain.")
                return

            # API endpoint: /api/v1/mesh/domains/{domain_id}/compliance/reports/{report_id}/
            result = api_client.get(f'mesh/domains/{domain_id}/compliance/reports/{latest_report_id}/')

        if output_format == 'json':
            click.echo(json.dumps(result, indent=2))
        else:
            # Table format
            click.echo("Compliance Report")
            click.echo("=" * 50)
            click.echo(f"Report ID: {result.get('id', 'N/A')}")
            click.echo(f"Domain ID: {result.get('domain_id', 'N/A')}")
            if result.get('asset_id'):
                click.echo(f"Asset ID: {result.get('asset_id')}")
            click.echo(f"Compliance Status: {result.get('compliance_status', 'N/A')}")
            click.echo(f"Risk Level: {result.get('risk_level', 'N/A')}")
            click.echo(f"Violation Count: {result.get('violation_count', 0)}")

            if result.get('summary'):
                click.echo(f"\nSummary: {result.get('summary')}")

            if result.get('generated_at'):
                click.echo(f"Generated At: {result.get('generated_at')}")

            # Show violations if any
            violations = result.get('violations', [])
            if violations:
                click.echo(f"\nViolations ({len(violations)}):")
                for i, violation in enumerate(violations, 1):
                    if isinstance(violation, dict):
                        violation_type = violation.get('type', 'N/A')
                        violation_desc = violation.get('description', 'N/A')
                        violation_severity = violation.get('severity', 'N/A')
                        click.echo(f"  {i}. [{violation_type}] {violation_severity}: {violation_desc}")
                    else:
                        click.echo(f"  {i}. {violation}")

            # Show regulation mapping if available
            regulation_mapping = result.get('regulation_mapping', {})
            if regulation_mapping:
                click.echo(f"\nRegulation Mapping:")
                for regulation, details in regulation_mapping.items():
                    if isinstance(details, dict):
                        click.echo(f"  {regulation}: {details}")
                    else:
                        click.echo(f"  {regulation}: {details}")
    except click.ClickException:
        raise
    except Exception as e:
        raise click.ClickException(f"Failed to get compliance report: {e}")

