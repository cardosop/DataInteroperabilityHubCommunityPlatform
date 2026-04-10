"""
BaaS (Backend as a Service) management commands.

Provides commands for managing API keys and developer portal resources.
"""
import click
import json
from datetime import datetime
from typing import Optional
from ..api_client import api_client
from ..baas_errors import (
    BaaSCLIError,
    BaaSValidationError,
    BaaSNotFoundError,
    handle_baas_api_error,
)


@click.group()
def baas():
    """BaaS (Backend as a Service) management commands [Post-MVP]"""
    pass


@baas.group('api-keys')
def api_keys():
    """API key management commands"""
    pass


@baas.group('usage')
def usage():
    """Usage tracking commands"""
    pass


@api_keys.command('create')
@click.option('--name', required=True, help='API key name (required, must be unique)')
@click.option('--tier', type=click.Choice(['FREE', 'PRO', 'ENTERPRISE'], case_sensitive=False), default='FREE', help='API tier (default: FREE)')
@click.option('--expires-at', help='Expiration date in ISO format (e.g., 2025-12-31T23:59:59Z). Optional.')
@click.option('--format', 'output_format', type=click.Choice(['json', 'table']), default='table', help='Output format')
def create_api_key(name: str, tier: str, expires_at: Optional[str], output_format: str):
    """
    Create a new API key.

    The API key value is shown only once in the response. Save it securely.
    """
    # Validate name
    if not name or not name.strip():
        raise BaaSValidationError(
            message="API key name cannot be empty",
            error_code="INVALID_NAME",
            context={'name': name},
            suggestion="Provide a non-empty name for the API key"
        )

    # Validate and parse expiration date if provided
    parsed_expires_at = None
    if expires_at:
        try:
            # Try to parse ISO format
            parsed_expires_at = datetime.fromisoformat(expires_at.replace('Z', '+00:00'))
            # Check if expiration is in the future
            from datetime import timezone
            if parsed_expires_at <= datetime.now(timezone.utc):
                raise BaaSValidationError(
                    message="Expiration date must be in the future",
                    error_code="INVALID_EXPIRATION_DATE",
                    context={'expires_at': expires_at},
                    suggestion="Provide a future date in ISO format (e.g., 2025-12-31T23:59:59Z)"
                )
        except ValueError as e:
            raise BaaSValidationError(
                message=f"Invalid expiration date format: {expires_at}",
                error_code="INVALID_DATE_FORMAT",
                context={'expires_at': expires_at},
                suggestion="Use ISO format (e.g., 2025-12-31T23:59:59Z)",
                original_error=e
            )

    # Prepare request data
    data = {
        'name': name.strip(),
        'tier': tier.upper()
    }
    if parsed_expires_at:
        # Convert back to ISO format string
        data['expires_at'] = parsed_expires_at.isoformat()

    try:
        # API endpoint: POST /api/v1/baas/api-keys/
        result = api_client.post('baas/api-keys/', json_data=data)

        if output_format == 'json':
            click.echo(json.dumps(result, indent=2, default=str))
        else:
            click.echo("API key created successfully!")
            click.echo("")
            click.echo("⚠️  IMPORTANT: Save this API key securely. It will not be shown again.")
            click.echo("")
            click.echo(f"ID: {result.get('id')}")
            click.echo(f"Name: {result.get('name')}")
            click.echo(f"API Key: {result.get('api_key')}")
            click.echo(f"Tier: {result.get('tier')}")
            if result.get('expires_at'):
                click.echo(f"Expires At: {result.get('expires_at')}")
            click.echo(f"Created At: {result.get('created_at')}")
            click.echo("")
            click.echo("💡 Use this API key with: datahub config set api_key <key>")

    except click.ClickException:
        raise
    except Exception as e:
        # Try to handle as BaaS error
        if isinstance(e, BaaSCLIError):
            raise
        # Check if it's an API error response
        if hasattr(e, 'response') and hasattr(e.response, 'text'):
            raise handle_baas_api_error(e.response.text, e.response.status_code, 'baas/api-keys/')
        raise BaaSCLIError(
            message=f"Failed to create API key: {str(e)}",
            error_code="API_KEY_CREATE_FAILED",
            context={'name': name, 'tier': tier},
            original_error=e
        )


@api_keys.command('list')
@click.option('--tier', type=click.Choice(['FREE', 'PRO', 'ENTERPRISE'], case_sensitive=False), help='Filter by tier')
@click.option('--limit', type=int, default=20, help='Limit number of results (default: 20)')
@click.option('--offset', type=int, default=0, help='Offset for pagination (default: 0)')
@click.option('--format', 'output_format', type=click.Choice(['json', 'table']), default='table', help='Output format')
def list_api_keys(tier: Optional[str], limit: int, offset: int, output_format: str):
    """List API keys"""
    params = {'limit': limit, 'offset': offset}
    if tier:
        params['tier'] = tier.upper()

    try:
        # API endpoint: GET /api/v1/baas/api-keys/
        data = api_client.get('baas/api-keys/', params=params)

        # Handle both paginated response (dict with 'results') and direct list response
        if isinstance(data, dict):
            results = data.get('results', [])
            total_count = data.get('count', len(results))
        elif isinstance(data, list):
            results = data
            total_count = len(results)
        else:
            results = []
            total_count = 0

        if output_format == 'json':
            click.echo(json.dumps(results, indent=2, default=str))
        else:
            if not results:
                click.echo("No API keys found.")
                return

            # Table format
            click.echo(f"{'ID':<40} {'Name':<30} {'Tier':<12} {'Status':<12} {'Expires At':<20}")
            click.echo("-" * 114)
            for api_key in results:
                api_key_id = str(api_key.get('id', ''))[:36]
                name = api_key.get('name', '')[:28]
                tier_name = api_key.get('tier', 'N/A')
                is_active = api_key.get('is_active', False)
                status = 'ACTIVE' if is_active else 'INACTIVE'
                expires_at = api_key.get('expires_at', '')
                if expires_at:
                    # Format date for display
                    try:
                        dt = datetime.fromisoformat(expires_at.replace('Z', '+00:00'))
                        expires_at = dt.strftime('%Y-%m-%d %H:%M')
                    except (ValueError, AttributeError):
                        pass
                else:
                    expires_at = 'Never'

                click.echo(
                    f"{api_key_id:<40} "
                    f"{name:<30} "
                    f"{tier_name:<12} "
                    f"{status:<12} "
                    f"{expires_at:<20}"
                )

            if isinstance(data, dict) and total_count > len(results):
                click.echo("")
                click.echo(f"Showing {len(results)} of {total_count} API keys")

    except click.ClickException:
        raise
    except Exception as e:
        # Try to handle as BaaS error
        if isinstance(e, BaaSCLIError):
            raise
        # Check if it's an API error response
        if hasattr(e, 'response') and hasattr(e.response, 'text'):
            raise handle_baas_api_error(e.response.text, e.response.status_code, 'baas/api-keys/')
        raise BaaSCLIError(
            message=f"Failed to list API keys: {str(e)}",
            error_code="API_KEY_LIST_FAILED",
            original_error=e
        )


@api_keys.command('get')
@click.argument('api_key_id')
@click.option('--format', 'output_format', type=click.Choice(['json', 'table']), default='table', help='Output format')
def get_api_key(api_key_id: str, output_format: str):
    """
    Get API key details.

    Note: The API key value is NOT displayed for security reasons.
    """
    # Validate API key ID
    if not api_key_id or not api_key_id.strip():
        raise BaaSValidationError(
            message="API key ID cannot be empty",
            error_code="INVALID_API_KEY_ID",
            context={'api_key_id': api_key_id},
            suggestion="Provide a valid API key ID"
        )

    try:
        # API endpoint: GET /api/v1/baas/api-keys/{id}/
        data = api_client.get(f'baas/api-keys/{api_key_id.strip()}/')

        # Security: Ensure API key value is not in response
        if 'api_key' in data:
            # Remove it if present (shouldn't be, but be safe)
            data = {k: v for k, v in data.items() if k != 'api_key'}

        if output_format == 'json':
            click.echo(json.dumps(data, indent=2, default=str))
        else:
            # Table format
            click.echo(f"ID: {data.get('id')}")
            click.echo(f"Name: {data.get('name')}")
            click.echo(f"Tier: {data.get('tier')}")
            click.echo(f"Status: {'ACTIVE' if data.get('is_active') else 'INACTIVE'}")
            if data.get('expires_at'):
                click.echo(f"Expires At: {data.get('expires_at')}")
            else:
                click.echo("Expires At: Never")
            if data.get('revoked_at'):
                click.echo(f"Revoked At: {data.get('revoked_at')}")
            click.echo(f"Created At: {data.get('created_at')}")
            click.echo(f"Updated At: {data.get('updated_at')}")
            click.echo("")
            click.echo("Note: API key value is not displayed for security reasons.")

    except click.ClickException:
        raise
    except Exception as e:
        # Try to handle as BaaS error
        if isinstance(e, BaaSCLIError):
            raise
        # Check if it's an API error response
        if hasattr(e, 'response') and hasattr(e.response, 'text'):
            raise handle_baas_api_error(e.response.text, e.response.status_code, f'baas/api-keys/{api_key_id}/')
        # Check for 404 specifically
        if '404' in str(e) or 'not found' in str(e).lower():
            raise BaaSNotFoundError(
                message=f"API key not found: {api_key_id}",
                error_code="API_KEY_NOT_FOUND",
                context={'api_key_id': api_key_id},
                suggestion="Check that the API key ID is correct"
            )
        raise BaaSCLIError(
            message=f"Failed to get API key: {str(e)}",
            error_code="API_KEY_GET_FAILED",
            context={'api_key_id': api_key_id},
            original_error=e
        )


@api_keys.command('update')
@click.argument('api_key_id')
@click.option('--name', help='Update API key name')
@click.option('--tier', type=click.Choice(['FREE', 'PRO', 'ENTERPRISE'], case_sensitive=False), help='Update API tier')
@click.option('--expires-at', help='Update expiration date in ISO format (e.g., 2025-12-31T23:59:59Z)')
@click.option('--format', 'output_format', type=click.Choice(['json', 'table']), default='table', help='Output format')
def update_api_key(api_key_id: str, name: Optional[str], tier: Optional[str], expires_at: Optional[str], output_format: str):
    """Update an API key"""
    # Validate API key ID
    if not api_key_id or not api_key_id.strip():
        raise BaaSValidationError(
            message="API key ID cannot be empty",
            error_code="INVALID_API_KEY_ID",
            context={'api_key_id': api_key_id},
            suggestion="Provide a valid API key ID"
        )

    # Check that at least one field is provided
    if not any([name, tier, expires_at]):
        raise BaaSValidationError(
            message="At least one field (--name, --tier, or --expires-at) must be provided",
            error_code="MISSING_UPDATE_FIELDS",
            context={'api_key_id': api_key_id},
            suggestion="Provide at least one field to update"
        )

    # Prepare update data
    data = {}
    if name:
        if not name.strip():
            raise BaaSValidationError(
                message="API key name cannot be empty",
                error_code="INVALID_NAME",
                context={'name': name},
                suggestion="Provide a non-empty name for the API key"
            )
        data['name'] = name.strip()

    if tier:
        data['tier'] = tier.upper()

    if expires_at:
        try:
            # Validate and parse expiration date
            parsed_expires_at = datetime.fromisoformat(expires_at.replace('Z', '+00:00'))
            from datetime import timezone
            if parsed_expires_at <= datetime.now(timezone.utc):
                raise BaaSValidationError(
                    message="Expiration date must be in the future",
                    error_code="INVALID_EXPIRATION_DATE",
                    context={'expires_at': expires_at},
                    suggestion="Provide a future date in ISO format (e.g., 2025-12-31T23:59:59Z)"
                )
            data['expires_at'] = parsed_expires_at.isoformat()
        except ValueError as e:
            raise BaaSValidationError(
                message=f"Invalid expiration date format: {expires_at}",
                error_code="INVALID_DATE_FORMAT",
                context={'expires_at': expires_at},
                suggestion="Use ISO format (e.g., 2025-12-31T23:59:59Z)",
                original_error=e
            )

    try:
        # API endpoint: PUT /api/v1/baas/api-keys/{id}/
        result = api_client.patch(f'baas/api-keys/{api_key_id.strip()}/', json_data=data)

        if output_format == 'json':
            click.echo(json.dumps(result, indent=2, default=str))
        else:
            click.echo("API key updated successfully!")
            click.echo(f"ID: {result.get('id')}")
            click.echo(f"Name: {result.get('name')}")
            click.echo(f"Tier: {result.get('tier')}")
            if result.get('expires_at'):
                click.echo(f"Expires At: {result.get('expires_at')}")
            else:
                click.echo("Expires At: Never")
            click.echo(f"Updated At: {result.get('updated_at')}")

    except click.ClickException:
        raise
    except Exception as e:
        # Try to handle as BaaS error
        if isinstance(e, BaaSCLIError):
            raise
        # Check if it's an API error response
        if hasattr(e, 'response') and hasattr(e.response, 'text'):
            raise handle_baas_api_error(e.response.text, e.response.status_code, f'baas/api-keys/{api_key_id}/')
        # Check for 404 specifically
        if '404' in str(e) or 'not found' in str(e).lower():
            raise BaaSNotFoundError(
                message=f"API key not found: {api_key_id}",
                error_code="API_KEY_NOT_FOUND",
                context={'api_key_id': api_key_id},
                suggestion="Check that the API key ID is correct"
            )
        raise BaaSCLIError(
            message=f"Failed to update API key: {str(e)}",
            error_code="API_KEY_UPDATE_FAILED",
            context={'api_key_id': api_key_id},
            original_error=e
        )


@api_keys.command('revoke')
@click.argument('api_key_id')
@click.option('--format', 'output_format', type=click.Choice(['json', 'table']), default='table', help='Output format')
def revoke_api_key(api_key_id: str, output_format: str):
    """Revoke an API key (soft delete)"""
    # Validate API key ID
    if not api_key_id or not api_key_id.strip():
        raise BaaSValidationError(
            message="API key ID cannot be empty",
            error_code="INVALID_API_KEY_ID",
            context={'api_key_id': api_key_id},
            suggestion="Provide a valid API key ID"
        )

    try:
        # API endpoint: DELETE /api/v1/baas/api-keys/{id}/
        result = api_client.delete(f'baas/api-keys/{api_key_id.strip()}/')

        if output_format == 'json':
            click.echo(json.dumps(result if result else {'status': 'revoked'}, indent=2, default=str))
        else:
            click.echo(f"API key revoked successfully: {api_key_id}")

    except click.ClickException:
        raise
    except Exception as e:
        # Try to handle as BaaS error
        if isinstance(e, BaaSCLIError):
            raise
        # Check if it's an API error response
        if hasattr(e, 'response') and hasattr(e.response, 'text'):
            raise handle_baas_api_error(e.response.text, e.response.status_code, f'baas/api-keys/{api_key_id}/')
        # Check for 404 specifically
        if '404' in str(e) or 'not found' in str(e).lower():
            raise BaaSNotFoundError(
                message=f"API key not found: {api_key_id}",
                error_code="API_KEY_NOT_FOUND",
                context={'api_key_id': api_key_id},
                suggestion="Check that the API key ID is correct"
            )
        raise BaaSCLIError(
            message=f"Failed to revoke API key: {str(e)}",
            error_code="API_KEY_REVOKE_FAILED",
            context={'api_key_id': api_key_id},
            original_error=e
        )


def _validate_date_format(date_str: str, param_name: str) -> datetime:
    """
    Validate and parse ISO date format.

    Args:
        date_str: Date string in ISO format
        param_name: Name of the parameter (for error messages)

    Returns:
        Parsed datetime object

    Raises:
        BaaSValidationError: If date format is invalid
    """
    if not date_str or not date_str.strip():
        raise BaaSValidationError(
            message=f"{param_name} cannot be empty",
            error_code="INVALID_DATE_FORMAT",
            context={param_name: date_str},
            suggestion="Provide a date in ISO format (e.g., 2025-12-31T23:59:59Z)"
        )

    try:
        # Try to parse ISO format
        parsed_date = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        return parsed_date
    except ValueError as e:
        raise BaaSValidationError(
            message=f"Invalid {param_name} format: {date_str}",
            error_code="INVALID_DATE_FORMAT",
            context={param_name: date_str},
            suggestion="Use ISO format (e.g., 2025-12-31T23:59:59Z)",
            original_error=e
        )


def _validate_api_key_id(api_key_id: Optional[str]) -> Optional[str]:
    """
    Validate API key ID format.

    Args:
        api_key_id: API key ID string (UUID format expected)

    Returns:
        Stripped API key ID if valid, None if None

    Raises:
        BaaSValidationError: If API key ID format is invalid
    """
    if api_key_id is None:
        return None

    if not api_key_id or not api_key_id.strip():
        raise BaaSValidationError(
            message="API key ID cannot be empty",
            error_code="INVALID_API_KEY_ID",
            context={'api_key_id': api_key_id},
            suggestion="Provide a valid API key ID (UUID format)"
        )

    # Basic UUID format validation (36 characters with dashes)
    stripped_id = api_key_id.strip()
    if len(stripped_id) != 36 or stripped_id.count('-') != 4:
        raise BaaSValidationError(
            message=f"Invalid API key ID format: {api_key_id}",
            error_code="INVALID_API_KEY_ID",
            context={'api_key_id': api_key_id},
            suggestion="API key ID must be in UUID format (e.g., 123e4567-e89b-12d3-a456-426614174000)"
        )

    return stripped_id


@usage.command('stats')
@click.option('--api-key-id', help='Filter by API key ID')
@click.option('--start-date', help='Start date in ISO format (e.g., 2025-01-01T00:00:00Z)')
@click.option('--end-date', help='End date in ISO format (e.g., 2025-12-31T23:59:59Z)')
@click.option('--format', 'output_format', type=click.Choice(['json', 'table']), default='table', help='Output format')
def usage_stats(api_key_id: Optional[str], start_date: Optional[str], end_date: Optional[str], output_format: str):
    """
    Get usage statistics.

    Displays aggregated usage statistics including total requests, success rate, and average response time.
    """
    # Validate API key ID if provided
    validated_api_key_id = _validate_api_key_id(api_key_id) if api_key_id else None

    # Validate and parse dates if provided
    parsed_start_date = None
    if start_date:
        parsed_start_date = _validate_date_format(start_date, 'start_date')

    parsed_end_date = None
    if end_date:
        parsed_end_date = _validate_date_format(end_date, 'end_date')

    # Validate date range
    if parsed_start_date and parsed_end_date and parsed_start_date > parsed_end_date:
        raise BaaSValidationError(
            message="Start date must be before or equal to end date",
            error_code="INVALID_DATE_RANGE",
            context={'start_date': start_date, 'end_date': end_date},
            suggestion="Ensure start_date is before end_date"
        )

    # Build query parameters
    params = {}
    if validated_api_key_id:
        params['api_key_id'] = validated_api_key_id
    if parsed_start_date:
        params['start_date'] = parsed_start_date.isoformat()
    if parsed_end_date:
        params['end_date'] = parsed_end_date.isoformat()

    try:
        # API endpoint: GET /api/v1/baas/usage/stats/
        data = api_client.get('baas/usage/stats/', params=params)

        if output_format == 'json':
            click.echo(json.dumps(data, indent=2, default=str))
        else:
            # Table format
            total_requests = data.get('total_requests', 0)
            success_count = data.get('success_count', 0)
            error_count = data.get('error_count', 0)
            success_rate = data.get('success_rate', 0.0)
            avg_response_time_ms = data.get('avg_response_time_ms', 0.0)
            total_request_bytes = data.get('total_request_bytes', 0)
            total_response_bytes = data.get('total_response_bytes', 0)

            click.echo("Usage Statistics")
            click.echo("=" * 50)
            click.echo(f"Total Requests: {total_requests:,}")
            click.echo(f"Successful: {success_count:,}")
            click.echo(f"Errors: {error_count:,}")
            click.echo(f"Success Rate: {success_rate:.2f}%")
            click.echo(f"Average Response Time: {avg_response_time_ms:.2f} ms")
            click.echo(f"Total Request Size: {total_request_bytes:,} bytes")
            click.echo(f"Total Response Size: {total_response_bytes:,} bytes")

    except click.ClickException:
        raise
    except Exception as e:
        # Try to handle as BaaS error
        if isinstance(e, BaaSCLIError):
            raise
        # Check if it's an API error response
        if hasattr(e, 'response') and hasattr(e.response, 'text'):
            raise handle_baas_api_error(e.response.text, e.response.status_code, 'baas/usage/stats/')
        raise BaaSCLIError(
            message=f"Failed to get usage statistics: {str(e)}",
            error_code="USAGE_STATS_FAILED",
            context={'api_key_id': api_key_id, 'start_date': start_date, 'end_date': end_date},
            original_error=e
        )


@usage.command('by-endpoint')
@click.option('--api-key-id', help='Filter by API key ID')
@click.option('--start-date', help='Start date in ISO format (e.g., 2025-01-01T00:00:00Z)')
@click.option('--end-date', help='End date in ISO format (e.g., 2025-12-31T23:59:59Z)')
@click.option('--format', 'output_format', type=click.Choice(['json', 'table']), default='table', help='Output format')
def usage_by_endpoint(api_key_id: Optional[str], start_date: Optional[str], end_date: Optional[str], output_format: str):
    """
    Get usage breakdown by endpoint.

    Displays usage statistics grouped by API endpoint and HTTP method.
    """
    # Validate API key ID if provided
    validated_api_key_id = _validate_api_key_id(api_key_id) if api_key_id else None

    # Validate and parse dates if provided
    parsed_start_date = None
    if start_date:
        parsed_start_date = _validate_date_format(start_date, 'start_date')

    parsed_end_date = None
    if end_date:
        parsed_end_date = _validate_date_format(end_date, 'end_date')

    # Validate date range
    if parsed_start_date and parsed_end_date and parsed_start_date > parsed_end_date:
        raise BaaSValidationError(
            message="Start date must be before or equal to end date",
            error_code="INVALID_DATE_RANGE",
            context={'start_date': start_date, 'end_date': end_date},
            suggestion="Ensure start_date is before end_date"
        )

    # Build query parameters
    params = {}
    if validated_api_key_id:
        params['api_key_id'] = validated_api_key_id
    if parsed_start_date:
        params['start_date'] = parsed_start_date.isoformat()
    if parsed_end_date:
        params['end_date'] = parsed_end_date.isoformat()

    try:
        # API endpoint: GET /api/v1/baas/usage/by-endpoint/
        data = api_client.get('baas/usage/by-endpoint/', params=params)

        # Handle both list and dict responses
        if isinstance(data, dict):
            results = data.get('results', [])
        elif isinstance(data, list):
            results = data
        else:
            results = []

        if output_format == 'json':
            click.echo(json.dumps(results, indent=2, default=str))
        else:
            if not results:
                click.echo("No usage data found for the specified filters.")
                return

            # Table format
            click.echo(f"{'Endpoint':<50} {'Method':<10} {'Requests':<12} {'Success':<12} {'Errors':<12} {'Avg Time (ms)':<15}")
            click.echo("-" * 111)
            for item in results:
                endpoint = str(item.get('endpoint', ''))[:48]
                method = str(item.get('method', ''))[:8]
                total_requests = item.get('total_requests', 0)
                success_count = item.get('success_count', 0)
                error_count = item.get('error_count', 0)
                avg_response_time = item.get('avg_response_time_ms', 0.0)

                click.echo(
                    f"{endpoint:<50} "
                    f"{method:<10} "
                    f"{total_requests:<12,} "
                    f"{success_count:<12,} "
                    f"{error_count:<12,} "
                    f"{avg_response_time:<15.2f}"
                )

    except click.ClickException:
        raise
    except Exception as e:
        # Try to handle as BaaS error
        if isinstance(e, BaaSCLIError):
            raise
        # Check if it's an API error response
        if hasattr(e, 'response') and hasattr(e.response, 'text'):
            raise handle_baas_api_error(e.response.text, e.response.status_code, 'baas/usage/by-endpoint/')
        raise BaaSCLIError(
            message=f"Failed to get usage by endpoint: {str(e)}",
            error_code="USAGE_BY_ENDPOINT_FAILED",
            context={'api_key_id': api_key_id, 'start_date': start_date, 'end_date': end_date},
            original_error=e
        )


@usage.command('by-tenant')
@click.option('--start-date', help='Start date in ISO format (e.g., 2025-01-01T00:00:00Z)')
@click.option('--end-date', help='End date in ISO format (e.g., 2025-12-31T23:59:59Z)')
@click.option('--format', 'output_format', type=click.Choice(['json', 'table']), default='table', help='Output format')
def usage_by_tenant(start_date: Optional[str], end_date: Optional[str], output_format: str):
    """
    Get usage breakdown by tenant (admin only).

    Displays usage statistics grouped by tenant. This command requires admin privileges.
    """
    # Validate and parse dates if provided
    parsed_start_date = None
    if start_date:
        parsed_start_date = _validate_date_format(start_date, 'start_date')

    parsed_end_date = None
    if end_date:
        parsed_end_date = _validate_date_format(end_date, 'end_date')

    # Validate date range
    if parsed_start_date and parsed_end_date and parsed_start_date > parsed_end_date:
        raise BaaSValidationError(
            message="Start date must be before or equal to end date",
            error_code="INVALID_DATE_RANGE",
            context={'start_date': start_date, 'end_date': end_date},
            suggestion="Ensure start_date is before end_date"
        )

    # Build query parameters
    params = {}
    if parsed_start_date:
        params['start_date'] = parsed_start_date.isoformat()
    if parsed_end_date:
        params['end_date'] = parsed_end_date.isoformat()

    try:
        # API endpoint: GET /api/v1/baas/usage/by-tenant/
        data = api_client.get('baas/usage/by-tenant/', params=params)

        # Handle both list and dict responses
        if isinstance(data, dict):
            results = data.get('results', [])
        elif isinstance(data, list):
            results = data
        else:
            results = []

        if output_format == 'json':
            click.echo(json.dumps(results, indent=2, default=str))
        else:
            if not results:
                click.echo("No usage data found for the specified filters.")
                return

            # Table format
            click.echo(f"{'Tenant ID':<40} {'Tenant Name':<30} {'Requests':<12} {'Success':<12} {'Errors':<12} {'Avg Time (ms)':<15}")
            click.echo("-" * 121)
            for item in results:
                tenant_id = str(item.get('tenant_id', ''))[:36]
                tenant_name = str(item.get('tenant_name', 'N/A'))[:28]
                total_requests = item.get('total_requests', 0)
                success_count = item.get('success_count', 0)
                error_count = item.get('error_count', 0)
                avg_response_time = item.get('avg_response_time_ms', 0.0)

                click.echo(
                    f"{tenant_id:<40} "
                    f"{tenant_name:<30} "
                    f"{total_requests:<12,} "
                    f"{success_count:<12,} "
                    f"{error_count:<12,} "
                    f"{avg_response_time:<15.2f}"
                )

    except click.ClickException:
        raise
    except Exception as e:
        # Try to handle as BaaS error
        if isinstance(e, BaaSCLIError):
            raise
        # Check if it's an API error response
        if hasattr(e, 'response') and hasattr(e.response, 'text'):
            raise handle_baas_api_error(e.response.text, e.response.status_code, 'baas/usage/by-tenant/')
        raise BaaSCLIError(
            message=f"Failed to get usage by tenant: {str(e)}",
            error_code="USAGE_BY_TENANT_FAILED",
            context={'start_date': start_date, 'end_date': end_date},
            original_error=e
        )


@baas.group('docs')
def docs():
    """Developer portal documentation commands"""
    pass


@docs.command('show')
@click.option('--format', 'output_format', type=click.Choice(['json', 'html', 'markdown'], case_sensitive=False), default='html', help='Output format (default: html)')
def show_docs(output_format: str):
    """
    Display API documentation.

    Shows API documentation overview with links to OpenAPI schema and SDKs.
    """
    try:
        # API endpoint: GET /api/v1/baas/docs/
        data = api_client.get('baas/docs/')

        if output_format.lower() == 'json':
            click.echo(json.dumps(data, indent=2, default=str))
        elif output_format.lower() == 'html':
            # Generate HTML output
            html_content = f"""<!DOCTYPE html>
<html>
<head>
    <title>{data.get('title', 'API Documentation')}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 40px; }}
        h1 {{ color: #333; }}
        h2 {{ color: #666; margin-top: 30px; }}
        .endpoint {{ background: #f5f5f5; padding: 10px; margin: 10px 0; border-left: 3px solid #007bff; }}
        .tier {{ display: inline-block; padding: 5px 10px; margin: 5px; background: #e9ecef; border-radius: 3px; }}
    </style>
</head>
<body>
    <h1>{data.get('title', 'API Documentation')}</h1>
    <p><strong>Version:</strong> {data.get('version', 'N/A')}</p>
    <p>{data.get('description', '')}</p>

    <h2>Endpoints</h2>
    <div class="endpoint">
        <strong>OpenAPI Schema (JSON):</strong> <a href="{data.get('endpoints', {}).get('openapi_schema', '')}">{data.get('endpoints', {}).get('openapi_schema', '')}</a>
    </div>
    <div class="endpoint">
        <strong>OpenAPI Schema (YAML):</strong> <a href="{data.get('endpoints', {}).get('openapi_yaml', '')}">{data.get('endpoints', {}).get('openapi_yaml', '')}</a>
    </div>
    <div class="endpoint">
        <strong>Swagger UI:</strong> <a href="{data.get('endpoints', {}).get('swagger_ui', '')}">{data.get('endpoints', {}).get('swagger_ui', '')}</a>
    </div>
    <div class="endpoint">
        <strong>ReDoc:</strong> <a href="{data.get('endpoints', {}).get('redoc', '')}">{data.get('endpoints', {}).get('redoc', '')}</a>
    </div>
    <div class="endpoint">
        <strong>SDKs:</strong> <a href="{data.get('endpoints', {}).get('sdks', '')}">{data.get('endpoints', {}).get('sdks', '')}</a>
    </div>

    <h2>Authentication</h2>
    <p><strong>Type:</strong> {data.get('authentication', {}).get('type', 'N/A')}</p>
    <p><strong>Header:</strong> {data.get('authentication', {}).get('header', 'N/A')}</p>
    <p>{data.get('authentication', {}).get('description', '')}</p>

    <h2>Rate Limiting</h2>
    <p>{data.get('rate_limiting', {}).get('description', '')}</p>
    <div>
"""
            tiers = data.get('rate_limiting', {}).get('tiers', {})
            for tier_name, tier_limit in tiers.items():
                html_content += f'        <span class="tier"><strong>{tier_name}:</strong> {tier_limit}</span>\n'

            html_content += """    </div>

    <h2>Resources</h2>
    <ul>
"""
            resources = data.get('resources', {})
            for resource_name, resource_url in resources.items():
                html_content += f'        <li><strong>{resource_name.replace("_", " ").title()}:</strong> <a href="{resource_url}">{resource_url}</a></li>\n'

            html_content += """    </ul>
</body>
</html>"""
            click.echo(html_content)
        else:  # markdown
            # Generate Markdown output
            md_content = f"""# {data.get('title', 'API Documentation')}

**Version:** {data.get('version', 'N/A')}

{data.get('description', '')}

## Endpoints

- **OpenAPI Schema (JSON):** [{data.get('endpoints', {}).get('openapi_schema', '')}]({data.get('endpoints', {}).get('openapi_schema', '')})
- **OpenAPI Schema (YAML):** [{data.get('endpoints', {}).get('openapi_yaml', '')}]({data.get('endpoints', {}).get('openapi_yaml', '')})
- **Swagger UI:** [{data.get('endpoints', {}).get('swagger_ui', '')}]({data.get('endpoints', {}).get('swagger_ui', '')})
- **ReDoc:** [{data.get('endpoints', {}).get('redoc', '')}]({data.get('endpoints', {}).get('redoc', '')})
- **SDKs:** [{data.get('endpoints', {}).get('sdks', '')}]({data.get('endpoints', {}).get('sdks', '')})

## Authentication

**Type:** {data.get('authentication', {}).get('type', 'N/A')}

**Header:** `{data.get('authentication', {}).get('header', 'N/A')}`

{data.get('authentication', {}).get('description', '')}

## Rate Limiting

{data.get('rate_limiting', {}).get('description', '')}

"""
            tiers = data.get('rate_limiting', {}).get('tiers', {})
            for tier_name, tier_limit in tiers.items():
                md_content += f"- **{tier_name}:** {tier_limit}\n"

            md_content += "\n## Resources\n\n"
            resources = data.get('resources', {})
            for resource_name, resource_url in resources.items():
                md_content += f"- **{resource_name.replace('_', ' ').title()}:** [{resource_url}]({resource_url})\n"

            click.echo(md_content)

    except click.ClickException:
        raise
    except Exception as e:
        # Try to handle as BaaS error
        if isinstance(e, BaaSCLIError):
            raise
        # Check if it's an API error response
        if hasattr(e, 'response') and hasattr(e.response, 'text'):
            raise handle_baas_api_error(e.response.text, e.response.status_code, 'baas/docs/')
        raise BaaSCLIError(
            message=f"Failed to get API documentation: {str(e)}",
            error_code="DOCS_GET_FAILED",
            original_error=e
        )


@docs.command('openapi')
@click.option('--format', 'output_format', type=click.Choice(['json', 'yaml'], case_sensitive=False), default='json', help='Output format (default: json)')
def show_openapi(output_format: str):
    """
    Display OpenAPI schema.

    Shows the OpenAPI 3.0 schema for the API.
    """
    try:
        if output_format.lower() == 'json':
            # API endpoint: GET /api/v1/baas/docs/openapi.json/
            data = api_client.get('baas/docs/openapi.json/')
            click.echo(json.dumps(data, indent=2, default=str))
        else:  # yaml
            # Try to get YAML format from the API
            # First try the YAML endpoint: /api-docs/openapi.yaml
            try:
                response = api_client.request('GET', 'api-docs/openapi.yaml')
                if response.status_code == 200:
                    click.echo(response.text)
                else:
                    # Fallback: get JSON and convert to YAML
                    try:
                        import yaml
                        data = api_client.get('baas/docs/openapi.json/')
                        click.echo(yaml.dump(data, default_flow_style=False, allow_unicode=True))
                    except ImportError:
                        raise BaaSCLIError(
                            message="YAML format requires PyYAML. Please install it with: pip install pyyaml",
                            error_code="YAML_FORMAT_UNAVAILABLE",
                            suggestion="Install PyYAML or use JSON format"
                        )
            except (click.ClickException, BaaSCLIError):
                # API request failed, try to convert JSON to YAML as fallback
                try:
                    import yaml
                    data = api_client.get('baas/docs/openapi.json/')
                    click.echo(yaml.dump(data, default_flow_style=False, allow_unicode=True))
                except ImportError:
                    raise BaaSCLIError(
                        message="YAML format requires PyYAML. Please install it with: pip install pyyaml",
                        error_code="YAML_FORMAT_UNAVAILABLE",
                        suggestion="Install PyYAML or use JSON format"
                    )
                except Exception as conv_error:
                    raise BaaSCLIError(
                        message=f"Failed to convert OpenAPI schema to YAML: {str(conv_error)}",
                        error_code="YAML_CONVERSION_FAILED",
                        original_error=conv_error
                    )
            except ImportError:
                # yaml module not available for conversion
                raise BaaSCLIError(
                    message="YAML format requires PyYAML. Please install it with: pip install pyyaml",
                    error_code="YAML_FORMAT_UNAVAILABLE",
                    suggestion="Install PyYAML or use JSON format"
                )
            except Exception as yaml_error:
                # If YAML endpoint fails, try to convert JSON to YAML
                try:
                    import yaml
                    data = api_client.get('baas/docs/openapi.json/')
                    click.echo(yaml.dump(data, default_flow_style=False, allow_unicode=True))
                except ImportError:
                    raise BaaSCLIError(
                        message="YAML format requires PyYAML. Please install it with: pip install pyyaml",
                        error_code="YAML_FORMAT_UNAVAILABLE",
                        suggestion="Install PyYAML or use JSON format"
                    )
                except Exception as conv_error:
                    raise BaaSCLIError(
                        message=f"Failed to convert OpenAPI schema to YAML: {str(conv_error)}",
                        error_code="YAML_CONVERSION_FAILED",
                        original_error=conv_error
                    )

    except click.ClickException:
        raise
    except Exception as e:
        # Try to handle as BaaS error
        if isinstance(e, BaaSCLIError):
            raise
        # Check if it's an API error response
        if hasattr(e, 'response') and hasattr(e.response, 'text'):
            raise handle_baas_api_error(e.response.text, e.response.status_code, 'baas/docs/openapi.json/')
        raise BaaSCLIError(
            message=f"Failed to get OpenAPI schema: {str(e)}",
            error_code="OPENAPI_GET_FAILED",
            original_error=e
        )


@docs.command('sdks')
@click.option('--format', 'output_format', type=click.Choice(['json', 'table'], case_sensitive=False), default='table', help='Output format (default: table)')
def show_sdks(output_format: str):
    """
    Display SDK download links.

    Shows download links for SDKs in various languages (Python, JavaScript).
    """
    try:
        # API endpoint: GET /api/v1/baas/docs/sdks/
        data = api_client.get('baas/docs/sdks/')

        if output_format.lower() == 'json':
            click.echo(json.dumps(data, indent=2, default=str))
        else:  # table format
            if not data:
                click.echo("No SDKs available.")
                return

            # Table format
            click.echo(f"{'Language':<20} {'Name':<30} {'Install Command':<40} {'Download URL':<50}")
            click.echo("-" * 140)

            # SDKs are returned as a dict with language keys
            for language_key, sdk_info in data.items():
                language = sdk_info.get('language', language_key)
                name = sdk_info.get('name', 'N/A')
                install_cmd = sdk_info.get('install_command', 'N/A')
                download_url = sdk_info.get('download_url', 'N/A')

                # Truncate long values for display
                language = language[:18]
                name = name[:28]
                install_cmd = install_cmd[:38]
                download_url = download_url[:48]

                click.echo(
                    f"{language:<20} "
                    f"{name:<30} "
                    f"{install_cmd:<40} "
                    f"{download_url:<50}"
                )

            click.echo("")
            click.echo("💡 Use the download URLs to get SDK code, or use install commands for package managers.")

    except click.ClickException:
        raise
    except Exception as e:
        # Try to handle as BaaS error
        if isinstance(e, BaaSCLIError):
            raise
        # Check if it's an API error response
        if hasattr(e, 'response') and hasattr(e.response, 'text'):
            raise handle_baas_api_error(e.response.text, e.response.status_code, 'baas/docs/sdks/')
        raise BaaSCLIError(
            message=f"Failed to get SDK links: {str(e)}",
            error_code="SDKS_GET_FAILED",
            original_error=e
        )


# ── 118E.5: Customers + Billing Reports ─────────────────


@baas.group("customers")
def customers():
    """Customer management commands"""
    pass


@customers.command("list")
@click.option("--limit", type=int, default=20)
@click.option("--offset", type=int, default=0)
@click.option(
    "--format", "output_format",
    type=click.Choice(["json", "table"]),
    default="table",
)
def list_customers(
    limit: int, offset: int, output_format: str,
):
    """List BaaS customers"""
    params = {"limit": limit, "offset": offset}
    try:
        data = api_client.get(
            "baas/customers/", params=params,
        )
        results = (
            data.get("results", [])
            if isinstance(data, dict) else
            data if isinstance(data, list) else []
        )
        if output_format == "json":
            click.echo(json.dumps(results, indent=2))
        else:
            if not results:
                click.echo("No customers found.")
                return
            click.echo(
                f"{'ID':<40} {'Name':<25} "
                f"{'Email':<30}"
            )
            click.echo("-" * 95)
            for c in results:
                if not isinstance(c, dict):
                    continue
                click.echo(
                    f"{str(c.get('id', ''))[:36]:<40} "
                    f"{str(c.get('name', ''))[:23]:<25} "
                    f"{str(c.get('email', ''))[:28]:<30}"
                )
    except click.ClickException:
        raise
    except Exception as e:
        raise click.ClickException(
            f"Failed to list customers: {e}"
        )


@customers.command("usage")
@click.argument("customer_id")
@click.option(
    "--period",
    help="Billing period (e.g. 2026-03)",
)
@click.option(
    "--format", "output_format",
    type=click.Choice(["json", "table"]),
    default="table",
)
def customer_usage(
    customer_id: str,
    period: Optional[str],
    output_format: str,
):
    """Get usage for a specific customer"""
    params = {}
    if period:
        params["period"] = period
    try:
        data = api_client.get(
            f"baas/customers/{customer_id}/usage/",
            params=params,
        )
        if output_format == "json":
            click.echo(json.dumps(data, indent=2))
        else:
            click.echo(
                f"Customer: {customer_id}"
            )
            records = (
                data.get("results", data)
                if isinstance(data, dict) else data
            )
            if isinstance(records, list):
                for r in records:
                    click.echo(
                        f"  {r.get('metric', 'N/A')}: "
                        f"{r.get('quantity', 0)}"
                    )
            else:
                click.echo(json.dumps(data, indent=2))
    except click.ClickException:
        raise
    except Exception as e:
        raise click.ClickException(
            f"Failed to get customer usage: {e}"
        )


@baas.group("billing-reports")
def billing_reports():
    """Billing report commands"""
    pass


@billing_reports.command("list")
@click.option("--limit", type=int, default=20)
@click.option("--offset", type=int, default=0)
@click.option(
    "--format", "output_format",
    type=click.Choice(["json", "table"]),
    default="table",
)
def list_billing_reports(
    limit: int, offset: int, output_format: str,
):
    """List billing reports"""
    params = {"limit": limit, "offset": offset}
    try:
        data = api_client.get(
            "baas/billing-reports/", params=params,
        )
        results = (
            data.get("results", [])
            if isinstance(data, dict) else
            data if isinstance(data, list) else []
        )
        if output_format == "json":
            click.echo(json.dumps(results, indent=2))
        else:
            if not results:
                click.echo("No billing reports found.")
                return
            click.echo(
                f"{'ID':<40} {'Period':<15} "
                f"{'Status':<12} {'Total':<15}"
            )
            click.echo("-" * 82)
            for r in results:
                if not isinstance(r, dict):
                    continue
                click.echo(
                    f"{str(r.get('id', ''))[:36]:<40} "
                    f"{str(r.get('period', '')):<15} "
                    f"{str(r.get('status', '')):<12} "
                    f"{str(r.get('total_amount', '')):<15}"
                )
    except click.ClickException:
        raise
    except Exception as e:
        raise click.ClickException(
            f"Failed to list billing reports: {e}"
        )


@billing_reports.command("get")
@click.argument("report_id")
@click.option(
    "--format", "output_format",
    type=click.Choice(["json", "table"]),
    default="table",
)
def get_billing_report(
    report_id: str, output_format: str,
):
    """Get billing report details"""
    try:
        data = api_client.get(
            f"baas/billing-reports/{report_id}/",
        )
        if output_format == "json":
            click.echo(json.dumps(data, indent=2))
        else:
            click.echo(f"ID: {data.get('id')}")
            click.echo(f"Period: {data.get('period')}")
            click.echo(f"Status: {data.get('status')}")
            click.echo(
                f"Total: {data.get('total_amount')}"
            )
            click.echo(
                f"Created: {data.get('created_at')}"
            )
    except click.ClickException:
        raise
    except Exception as e:
        raise click.ClickException(
            f"Failed to get billing report: {e}"
        )


@billing_reports.command("generate")
@click.option(
    "--period", required=True,
    help="Billing period (e.g. 2026-03)",
)
@click.option(
    "--format", "output_format",
    type=click.Choice(["json", "table"]),
    default="table",
)
def generate_billing_report(
    period: str, output_format: str,
):
    """Generate a billing report"""
    try:
        data = api_client.post(
            "baas/billing-reports/",
            json_data={"period": period},
        )
        if output_format == "json":
            click.echo(json.dumps(data, indent=2))
        else:
            click.echo("Report generated!")
            click.echo(f"ID: {data.get('id')}")
            click.echo(f"Status: {data.get('status')}")
    except click.ClickException:
        raise
    except Exception as e:
        raise click.ClickException(
            f"Failed to generate report: {e}"
        )


@billing_reports.command("finalize")
@click.argument("report_id")
def finalize_billing_report(report_id: str):
    """Finalize a billing report"""
    try:
        api_client.post(
            f"baas/billing-reports/{report_id}"
            f"/finalize/",
        )
        click.echo(f"Report {report_id} finalized.")
    except click.ClickException:
        raise
    except Exception as e:
        raise click.ClickException(
            f"Failed to finalize report: {e}"
        )


@billing_reports.command("export")
@click.argument("report_id")
@click.option(
    "--format", "export_fmt",
    type=click.Choice(["csv", "pdf"]),
    default="csv",
)
def export_billing_report(
    report_id: str, export_fmt: str,
):
    """Export a billing report"""
    try:
        data = api_client.post(
            f"baas/billing-reports/{report_id}"
            f"/export/",
            json_data={"format": export_fmt},
        )
        url = data.get("download_url")
        if url:
            click.echo(f"Download URL: {url}")
        else:
            click.echo(json.dumps(data, indent=2))
    except click.ClickException:
        raise
    except Exception as e:
        raise click.ClickException(
            f"Failed to export report: {e}"
        )


@billing_reports.command("send")
@click.argument("report_id")
@click.option(
    "--email", required=True,
    help="Recipient email",
)
def send_billing_report(
    report_id: str, email: str,
):
    """Send a billing report via email"""
    try:
        api_client.post(
            f"baas/billing-reports/{report_id}"
            f"/send/",
            json_data={"email": email},
        )
        click.echo(
            f"Report {report_id} sent to {email}."
        )
    except click.ClickException:
        raise
    except Exception as e:
        raise click.ClickException(
            f"Failed to send report: {e}"
        )


# ── 118E.6: api-keys rotate ─────────────────────────────


@api_keys.command("rotate")
@click.argument("api_key_id")
@click.option(
    "--grace-hours", type=int, default=24,
    help="Hours old key remains valid (default: 24)",
)
@click.option(
    "--format", "output_format",
    type=click.Choice(["json", "table"]),
    default="table",
)
def rotate_api_key(
    api_key_id: str, grace_hours: int,
    output_format: str,
):
    """Rotate an API key with grace period"""
    try:
        data = api_client.post(
            f"baas/api-keys/{api_key_id}/rotate/",
            json_data={
                "grace_period_hours": grace_hours,
            },
        )
        if output_format == "json":
            click.echo(json.dumps(data, indent=2))
        else:
            click.echo("API key rotated!")
            click.echo(
                f"New Key: {data.get('api_key')}"
            )
            click.echo(
                f"Grace Period: {grace_hours}h"
            )
            click.echo(
                "Save the new key — it won't be "
                "shown again."
            )
    except click.ClickException:
        raise
    except Exception as e:
        raise click.ClickException(
            f"Failed to rotate API key: {e}"
        )
