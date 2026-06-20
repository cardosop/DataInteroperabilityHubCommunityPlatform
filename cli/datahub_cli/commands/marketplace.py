"""
Marketplace integration commands.
"""

import json
import os
import time

import click

from ..api_client import api_client
from ..marketplace_errors import (
    MarketplaceCLIError,
    MarketplaceConnectionError,
    MarketplaceValidationError,
    validate_asset_id,
    validate_connection_config,
    validate_connection_id,
    validate_mapping_id,
    validate_marketplace_type,
)


@click.group()
def marketplace():
    """Marketplace integration commands"""


@marketplace.group("connections")
def connections():
    """Marketplace connection management commands [Post-MVP]"""


@connections.command("create")
@click.option(
    "--marketplace-type",
    "marketplace_type",
    required=True,
    type=click.Choice(
        [
            "SNOWFLAKE_DATA_MARKETPLACE",
            "AWS_DATA_EXCHANGE",
            "DATABRICKS_MARKETPLACE",
            "GOOGLE_CLOUD_MARKETPLACE",
            "AZURE_MARKETPLACE",
            "DATA_WORLD",
            "KAGGLE",
            "QUANDL",
            "APIS_GURU",
            "RAPIDAPI",
            "PROGRAMMABLE_WEB",
            "DATA_GOV",
            "EUROPEAN_DATA_PORTAL",
            "CKAN_INSTANCE",
            "CUSTOM",
        ],
        case_sensitive=False,
    ),
    help="Marketplace type (e.g., SNOWFLAKE_DATA_MARKETPLACE, AWS_DATA_EXCHANGE)",
)
@click.option("--name", required=True, help="Connection name (unique per tenant)")
@click.option("--config", required=True, help="Connection configuration (JSON string or file path)")
@click.option(
    "--is-active/--no-is-active", "is_active", default=True, help="Whether connection is active"
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["json", "table"]),
    default="table",
    help="Output format",
)
def create_connection(
    marketplace_type: str, name: str, config: str, is_active: bool, output_format: str
):
    """Create a new marketplace connection"""
    try:
        # Validate marketplace type
        validate_marketplace_type(marketplace_type)

        # Parse config (can be JSON string or file path)
        config_data = _parse_config(config)

        # Validate config
        validate_connection_config(config_data)

        # Prepare request data
        data = {
            "marketplace_type": marketplace_type.upper(),
            "name": name.strip(),
            "config": config_data,
            "is_active": is_active,
        }

        # API endpoint: POST /api/v1/integrations/marketplace/connections/
        result = api_client.post("integrations/marketplace/connections/", json_data=data)

        if output_format == "json":
            click.echo(json.dumps(result, indent=2))
        else:
            click.echo("Connection created successfully!")
            click.echo(f"ID: {result.get('id')}")
            click.echo(f"Name: {result.get('name')}")
            click.echo(f"Marketplace Type: {result.get('marketplace_type')}")
            click.echo(f"Active: {result.get('is_active')}")
            click.echo(f"Created: {result.get('created_at')}")

    except (MarketplaceCLIError, MarketplaceValidationError):
        raise
    except click.ClickException:
        raise
    except Exception as e:
        raise MarketplaceConnectionError(
            message=f"Failed to create connection: {e!s}",
            error_code="CONNECTION_CREATE_FAILED",
            context={"marketplace_type": marketplace_type, "name": name},
            original_error=e,
        )


@connections.command("list")
@click.option("--marketplace-type", "marketplace_type", help="Filter by marketplace type")
@click.option(
    "--is-active", "is_active", type=click.Choice(["true", "false"]), help="Filter by active status"
)
@click.option(
    "--limit", type=int, default=50, help="Limit number of results (default: 50, max: 100)"
)
@click.option("--offset", type=int, default=0, help="Offset for pagination")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["json", "table"]),
    default="table",
    help="Output format",
)
def list_connections(
    marketplace_type: str | None, is_active: str | None, limit: int, offset: int, output_format: str
):
    """List marketplace connections"""
    try:
        # Build query parameters
        params = {"limit": limit, "offset": offset}
        if marketplace_type:
            validate_marketplace_type(marketplace_type)
            params["marketplace_type"] = marketplace_type.upper()
        if is_active is not None:
            params["is_active"] = is_active.lower() == "true"

        # API endpoint: GET /api/v1/integrations/marketplace/connections/
        data = api_client.get("integrations/marketplace/connections/", params=params)

        # Handle paginated response
        if isinstance(data, dict):
            results = data.get("results", [])
            count = data.get("count", len(results))
        elif isinstance(data, list):
            results = data
            count = len(results)
        else:
            results = []
            count = 0

        if output_format == "json":
            click.echo(json.dumps(results, indent=2))
        else:
            if not results:
                click.echo("No connections found.")
                return

            # Table format
            click.echo(
                f"{'ID':<40} {'Name':<30} {'Marketplace Type':<30} {'Active':<10} {'Created':<20}"
            )
            click.echo("-" * 130)
            for conn in results:
                conn_id = str(conn.get("id", ""))[:36]
                name = str(conn.get("name", ""))[:28]
                mkt_type = str(conn.get("marketplace_type", ""))[:28]
                active = "Yes" if conn.get("is_active") else "No"
                created = str(conn.get("created_at", ""))[:19] if conn.get("created_at") else "N/A"
                click.echo(f"{conn_id:<40} {name:<30} {mkt_type:<30} {active:<10} {created:<20}")

            if isinstance(data, dict) and count > len(results):
                click.echo(f"\nShowing {len(results)} of {count} connections")

    except (MarketplaceCLIError, MarketplaceValidationError):
        raise
    except click.ClickException:
        raise
    except Exception as e:
        raise MarketplaceConnectionError(
            message=f"Failed to list connections: {e!s}",
            error_code="CONNECTION_LIST_FAILED",
            context={},
            original_error=e,
        )


@connections.command("get")
@click.argument("connection_id")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["json", "table"]),
    default="table",
    help="Output format",
)
def get_connection(connection_id: str, output_format: str):
    """Get marketplace connection details"""
    try:
        # Validate connection ID
        validate_connection_id(connection_id)

        # API endpoint: GET /api/v1/integrations/marketplace/connections/{id}/
        data = api_client.get(f"integrations/marketplace/connections/{connection_id}/")

        if output_format == "json":
            click.echo(json.dumps(data, indent=2))
        else:
            # Table format
            click.echo(f"ID: {data.get('id')}")
            click.echo(f"Name: {data.get('name')}")
            click.echo(f"Marketplace Type: {data.get('marketplace_type')}")
            click.echo(f"Active: {data.get('is_active')}")
            click.echo(f"Created: {data.get('created_at')}")
            click.echo(f"Updated: {data.get('updated_at')}")
            if data.get("tenant_name"):
                click.echo(f"Tenant: {data.get('tenant_name')}")

    except (MarketplaceCLIError, MarketplaceValidationError):
        raise
    except click.ClickException:
        raise
    except Exception as e:
        raise MarketplaceConnectionError(
            message=f"Failed to get connection: {e!s}",
            error_code="CONNECTION_GET_FAILED",
            context={"connection_id": connection_id},
            original_error=e,
        )


@connections.command("update")
@click.argument("connection_id")
@click.option("--name", help="Connection name")
@click.option("--config", help="Connection configuration (JSON string or file path)")
@click.option(
    "--is-active/--no-is-active", "is_active", default=None, help="Whether connection is active"
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["json", "table"]),
    default="table",
    help="Output format",
)
def update_connection(
    connection_id: str,
    name: str | None,
    config: str | None,
    is_active: bool | None,
    output_format: str,
):
    """Update a marketplace connection"""
    try:
        # Validate connection ID
        validate_connection_id(connection_id)

        # Build update data (only include provided fields)
        data = {}
        if name is not None:
            if not name.strip():
                raise MarketplaceValidationError(
                    message="Connection name cannot be empty",
                    error_code="EMPTY_NAME",
                    context={"connection_id": connection_id},
                    suggestion="Provide a non-empty connection name",
                )
            data["name"] = name.strip()

        if config is not None:
            config_data = _parse_config(config)
            validate_connection_config(config_data)
            data["config"] = config_data

        if is_active is not None:
            data["is_active"] = is_active

        if not data:
            raise MarketplaceValidationError(
                message="No fields to update",
                error_code="NO_UPDATE_FIELDS",
                context={"connection_id": connection_id},
                suggestion="Provide at least one field to update (--name, --config, or --is-active)",
            )

        # API endpoint: PATCH /api/v1/integrations/marketplace/connections/{id}/
        result = api_client.patch(
            f"integrations/marketplace/connections/{connection_id}/", json_data=data
        )

        if output_format == "json":
            click.echo(json.dumps(result, indent=2))
        else:
            click.echo("Connection updated successfully!")
            click.echo(f"ID: {result.get('id')}")
            click.echo(f"Name: {result.get('name')}")
            click.echo(f"Marketplace Type: {result.get('marketplace_type')}")
            click.echo(f"Active: {result.get('is_active')}")
            click.echo(f"Updated: {result.get('updated_at')}")

    except (MarketplaceCLIError, MarketplaceValidationError):
        raise
    except click.ClickException:
        raise
    except Exception as e:
        raise MarketplaceConnectionError(
            message=f"Failed to update connection: {e!s}",
            error_code="CONNECTION_UPDATE_FAILED",
            context={"connection_id": connection_id},
            original_error=e,
        )


@connections.command("delete")
@click.argument("connection_id")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["json", "table"]),
    default="table",
    help="Output format",
)
def delete_connection(connection_id: str, output_format: str):
    """Delete a marketplace connection"""
    try:
        # Validate connection ID
        validate_connection_id(connection_id)

        # API endpoint: DELETE /api/v1/integrations/marketplace/connections/{id}/
        api_client.delete(f"integrations/marketplace/connections/{connection_id}/")

        if output_format == "json":
            click.echo(
                json.dumps(
                    {"success": True, "message": "Connection deleted successfully"}, indent=2
                )
            )
        else:
            click.echo("Connection deleted successfully!")

    except (MarketplaceCLIError, MarketplaceValidationError):
        raise
    except click.ClickException:
        raise
    except Exception as e:
        raise MarketplaceConnectionError(
            message=f"Failed to delete connection: {e!s}",
            error_code="CONNECTION_DELETE_FAILED",
            context={"connection_id": connection_id},
            original_error=e,
        )


@connections.command("test")
@click.argument("connection_id")
@click.option(
    "--config",
    help="Optional test configuration (JSON string or file path). If not provided, uses connection config.",
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["json", "table"]),
    default="table",
    help="Output format",
)
def test_connection(connection_id: str, config: str | None, output_format: str):
    """Test a marketplace connection"""
    try:
        # Validate connection ID
        validate_connection_id(connection_id)

        # Prepare request data
        data = {}
        if config is not None:
            config_data = _parse_config(config)
            validate_connection_config(config_data)
            data["config"] = config_data

        # API endpoint: POST /api/v1/integrations/marketplace/connections/{id}/test/
        result = api_client.post(
            f"integrations/marketplace/connections/{connection_id}/test/",
            json_data=data if data else None,
        )

        if output_format == "json":
            click.echo(json.dumps(result, indent=2))
        else:
            # Table format
            success = result.get("success", False)
            message = result.get("message", "Unknown result")
            tested_at = result.get("tested_at", "N/A")

            if success:
                click.echo("✓ Connection test successful!")
                click.echo(f"Message: {message}")
                click.echo(f"Tested at: {tested_at}")
                if result.get("details"):
                    details = result.get("details", {})
                    if details.get("marketplace_type"):
                        click.echo(f"Marketplace Type: {details.get('marketplace_type')}")
                    if details.get("response_time_ms"):
                        click.echo(f"Response Time: {details.get('response_time_ms')} ms")
            else:
                click.echo("✗ Connection test failed!")
                click.echo(f"Message: {message}")
                click.echo(f"Tested at: {tested_at}")
                if result.get("error"):
                    click.echo(f"Error: {result.get('error')}")

    except (MarketplaceCLIError, MarketplaceValidationError):
        raise
    except click.ClickException:
        raise
    except Exception as e:
        raise MarketplaceConnectionError(
            message=f"Failed to test connection: {e!s}",
            error_code="CONNECTION_TEST_FAILED",
            context={"connection_id": connection_id},
            original_error=e,
        )


def _parse_config(config: str) -> dict:
    """
    Parse configuration from JSON string or file path.

    Args:
        config: JSON string or file path

    Returns:
        Configuration dictionary

    Raises:
        MarketplaceValidationError: If config cannot be parsed
    """
    # Try to parse as JSON string first
    try:
        return json.loads(config)
    except json.JSONDecodeError:
        pass

    # If not valid JSON, try as file path
    if os.path.exists(config):
        try:
            with open(config, encoding="utf-8") as f:
                content = f.read()
                return json.loads(content)
        except OSError as e:
            raise MarketplaceValidationError(
                message=f"Failed to read config file: {e!s}",
                error_code="CONFIG_FILE_READ_ERROR",
                context={"file_path": config},
                suggestion="Check that the file exists and you have read permissions",
                original_error=e,
            )
        except json.JSONDecodeError as e:
            raise MarketplaceValidationError(
                message=f"Invalid JSON in config file: {e!s}",
                error_code="INVALID_JSON_CONFIG_FILE",
                context={"file_path": config},
                suggestion="Ensure the config file contains valid JSON",
                original_error=e,
            )
    else:
        # Not a file and not valid JSON
        raise MarketplaceValidationError(
            message=f"Configuration must be valid JSON or a file path. Got: {config[:100]}",
            error_code="INVALID_CONFIG_FORMAT",
            context={"config": config[:100]},
            suggestion="Provide configuration as a JSON string or path to a JSON file",
        )


@marketplace.group("sync")
def sync():
    """Marketplace sync job commands [Post-MVP]"""


@sync.command("start")
@click.option("--connection-id", required=True, help="Marketplace connection ID")
@click.option(
    "--direction",
    required=True,
    type=click.Choice(["PUSH", "PULL", "BIDIRECTIONAL"], case_sensitive=False),
    help="Sync direction",
)
@click.option("--asset-ids", help="Comma-separated asset IDs (required for PUSH)")
@click.option("--listing-ids", help="Comma-separated listing IDs (for PULL)")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["json", "table"]),
    default="table",
    help="Output format",
)
def sync_start(
    connection_id: str,
    direction: str,
    asset_ids: str | None,
    listing_ids: str | None,
    output_format: str,
):
    """
    Start a marketplace sync job.

    For PUSH direction: --asset-ids is required
    For PULL direction: --listing-ids is optional
    """
    # Validate direction-specific requirements
    direction_upper = direction.upper()

    # Parse comma-separated IDs first to check for empty strings
    # Check if asset_ids was provided (even if empty string)
    asset_ids_provided = asset_ids is not None
    parsed_asset_ids = None
    if asset_ids_provided:
        if not asset_ids.strip():
            raise click.ClickException("--asset-ids cannot be empty")
        parsed_asset_ids = [aid.strip() for aid in asset_ids.split(",") if aid.strip()]
        if not parsed_asset_ids:
            raise click.ClickException("--asset-ids cannot be empty")

    # Check if listing_ids was provided (even if empty string)
    listing_ids_provided = listing_ids is not None
    parsed_listing_ids = None
    if listing_ids_provided:
        if not listing_ids.strip():
            raise click.ClickException("--listing-ids cannot be empty")
        parsed_listing_ids = [lid.strip() for lid in listing_ids.split(",") if lid.strip()]
        if not parsed_listing_ids:
            raise click.ClickException("--listing-ids cannot be empty")

    # Now validate direction-specific requirements
    if direction_upper == "PUSH":
        if not parsed_asset_ids:
            raise click.ClickException("--asset-ids is required for PUSH direction")
        if parsed_listing_ids:
            raise click.ClickException("--listing-ids cannot be used with PUSH direction")
    elif direction_upper == "PULL":
        if parsed_asset_ids:
            raise click.ClickException("--asset-ids cannot be used with PULL direction")
    elif direction_upper == "BIDIRECTIONAL":
        if not parsed_asset_ids:
            raise click.ClickException("--asset-ids is required for BIDIRECTIONAL direction")

    # Build request payload
    payload = {"connection_id": connection_id, "direction": direction_upper}

    if parsed_asset_ids:
        payload["asset_ids"] = parsed_asset_ids

    if parsed_listing_ids:
        payload["listing_ids"] = parsed_listing_ids

    try:
        data = api_client.post("integrations/marketplace/sync/", json_data=payload)

        if output_format == "json":
            click.echo(json.dumps(data, indent=2))
        else:
            # Table format
            click.echo("Sync job created successfully!")
            click.echo(f"ID: {data.get('id')}")
            click.echo(f"Connection: {data.get('connection_name', 'N/A')}")
            click.echo(f"Direction: {data.get('direction_display', data.get('direction', 'N/A'))}")
            click.echo(f"Status: {data.get('status_display', data.get('status', 'N/A'))}")
            click.echo(f"Created: {data.get('created_at', 'N/A')}")
    except click.ClickException:
        raise
    except Exception as e:
        raise click.ClickException(f"Failed to start sync job: {e}")


@sync.command("list")
@click.option("--connection-id", help="Filter by connection ID")
@click.option(
    "--status", help="Filter by status (PENDING, RUNNING, COMPLETED, FAILED, PARTIAL, CANCELLED)"
)
@click.option(
    "--direction",
    type=click.Choice(["PUSH", "PULL", "BIDIRECTIONAL"], case_sensitive=False),
    help="Filter by direction",
)
@click.option("--limit", type=int, default=20, help="Limit number of results")
@click.option("--offset", type=int, default=0, help="Offset for pagination")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["json", "table"]),
    default="table",
    help="Output format",
)
def sync_list(
    connection_id: str | None,
    status: str | None,
    direction: str | None,
    limit: int,
    offset: int,
    output_format: str,
):
    """List marketplace sync jobs"""
    params = {"limit": limit, "offset": offset}

    if connection_id:
        params["connection_id"] = connection_id

    if status:
        params["status"] = status.upper()

    if direction:
        params["direction"] = direction.upper()

    try:
        data = api_client.get("integrations/marketplace/sync/", params=params)

        # Handle both paginated response (dict with 'results') and direct list response
        if isinstance(data, dict):
            results = data.get("results", [])
        elif isinstance(data, list):
            results = data
        else:
            results = []

        if output_format == "json":
            click.echo(json.dumps(results, indent=2))
        else:
            if not results:
                click.echo("No sync jobs found.")
                return

            # Table format
            click.echo(
                f"{'ID':<40} {'Connection':<30} {'Direction':<15} {'Status':<15} {'Progress':<15} {'Created':<25}"
            )
            click.echo("-" * 140)
            for job in results:
                job_id = str(job.get("id", ""))[:36] if job.get("id") else ""
                connection = (
                    str(job.get("connection_name", job.get("connection_id", "")))[:28]
                    if job.get("connection_name") or job.get("connection_id")
                    else ""
                )
                direction = (
                    str(job.get("direction_display", job.get("direction", "")))[:13]
                    if job.get("direction_display") or job.get("direction")
                    else ""
                )
                status = (
                    str(job.get("status_display", job.get("status", "")))[:13]
                    if job.get("status_display") or job.get("status")
                    else ""
                )

                # Calculate progress percentage
                items_synced = job.get("items_synced", 0) or 0
                items_failed = job.get("items_failed", 0) or 0
                total_items = items_synced + items_failed
                if total_items > 0:
                    progress = f"{(items_synced / total_items * 100):.1f}%"
                else:
                    progress = "0.0%"

                created = job.get("created_at", "")[:19] if job.get("created_at") else "N/A"

                click.echo(
                    f"{job_id:<40} "
                    f"{connection:<30} "
                    f"{direction:<15} "
                    f"{status:<15} "
                    f"{progress:<15} "
                    f"{created:<25}"
                )
    except click.ClickException:
        raise
    except Exception as e:
        raise click.ClickException(f"Failed to list sync jobs: {e}")


@sync.command("get")
@click.argument("sync_job_id")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["json", "table"]),
    default="table",
    help="Output format",
)
@click.option("--watch", is_flag=True, help="Watch for real-time updates (polling)")
def sync_get(sync_job_id: str, output_format: str, watch: bool):
    """Get marketplace sync job details"""
    try:

        def fetch_and_display():
            data = api_client.get(f"integrations/marketplace/sync/{sync_job_id}/")

            if output_format == "json":
                click.echo(json.dumps(data, indent=2))
            else:
                # Table format
                click.echo(f"ID: {data.get('id')}")
                click.echo(
                    f"Connection: {data.get('connection_name', data.get('connection_id', 'N/A'))}"
                )
                click.echo(
                    f"Direction: {data.get('direction_display', data.get('direction', 'N/A'))}"
                )
                click.echo(f"Status: {data.get('status_display', data.get('status', 'N/A'))}")

                # Progress information
                items_synced = data.get("items_synced", 0) or 0
                items_failed = data.get("items_failed", 0) or 0
                total_items = items_synced + items_failed

                click.echo(f"Items Synced: {items_synced}")
                click.echo(f"Items Failed: {items_failed}")

                if total_items > 0:
                    progress_pct = items_synced / total_items * 100
                    click.echo(f"Progress: {progress_pct:.1f}%")
                else:
                    click.echo("Progress: 0.0%")

                # Errors
                errors = data.get("errors", [])
                if errors:
                    click.echo(f"Errors: {len(errors)}")
                    for i, error in enumerate(errors[:5], 1):  # Show first 5 errors
                        if isinstance(error, dict):
                            error_msg = error.get("message", str(error))
                        else:
                            error_msg = str(error)
                        click.echo(f"  {i}. {error_msg[:100]}")
                    if len(errors) > 5:
                        click.echo(f"  ... and {len(errors) - 5} more errors")

                click.echo(f"Created: {data.get('created_at', 'N/A')}")
                if data.get("updated_at"):
                    click.echo(f"Updated: {data.get('updated_at', 'N/A')}")
                if data.get("completed_at"):
                    click.echo(f"Completed: {data.get('completed_at', 'N/A')}")

                # Metadata
                metadata = data.get("metadata", {})
                if metadata:
                    click.echo(f"Metadata: {json.dumps(metadata, indent=2)}")

            return data

        if watch:
            # Polling mode - update every 2 seconds
            try:
                while True:
                    # Clear screen (works on most terminals)
                    click.clear()
                    click.echo(f"Watching sync job {sync_job_id} (Press Ctrl+C to stop)...")
                    click.echo("-" * 80)

                    data = fetch_and_display()

                    # Check if job is in terminal state
                    status = data.get("status", "").upper()
                    if status in ["COMPLETED", "FAILED", "CANCELLED"]:
                        click.echo("\nSync job reached terminal state. Stopping watch.")
                        break

                    time.sleep(2)
            except KeyboardInterrupt:
                click.echo("\nWatch stopped by user.")
        else:
            fetch_and_display()

    except click.ClickException:
        raise
    except Exception as e:
        raise click.ClickException(f"Failed to get sync job: {e}")


@sync.command("cancel")
@click.argument("sync_job_id")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["json", "table"]),
    default="table",
    help="Output format",
)
def sync_cancel(sync_job_id: str, output_format: str):
    """Cancel a marketplace sync job"""
    try:
        data = api_client.post(f"integrations/marketplace/sync/{sync_job_id}/cancel/", json_data={})

        if output_format == "json":
            click.echo(json.dumps(data, indent=2))
        else:
            # Table format
            click.echo("Sync job cancelled successfully!")
            click.echo(f"ID: {data.get('id')}")
            click.echo(f"Status: {data.get('status_display', data.get('status', 'N/A'))}")
            click.echo(f"Updated: {data.get('updated_at', 'N/A')}")
    except click.ClickException:
        raise
    except Exception as e:
        raise click.ClickException(f"Failed to cancel sync job: {e}")


@marketplace.group("connectors")
def connectors():
    """Marketplace connector management commands [Post-MVP]"""


@connectors.command("list")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["json", "table"]),
    default="table",
    help="Output format",
)
def list_connectors(output_format: str):
    """List available marketplace connector types"""
    try:
        # API endpoint: GET /api/v1/integrations/marketplace/connectors/
        data = api_client.get("integrations/marketplace/connectors/")

        connectors = data.get("connectors", [])

        if output_format == "json":
            click.echo(json.dumps(connectors, indent=2))
        else:
            if not connectors:
                click.echo("No connectors found.")
                return

            # Table format
            click.echo(f"{'Type':<35} {'Display Name':<35} {'Sync Directions':<25} {'Status':<15}")
            click.echo("-" * 110)
            for connector in connectors:
                connector_type = str(connector.get("type", ""))[:33]
                display_name = str(connector.get("display_name", ""))[:33]
                sync_directions = ", ".join(connector.get("supported_sync_directions", []))[:23]
                status = str(connector.get("status", ""))[:13]
                click.echo(
                    f"{connector_type:<35} {display_name:<35} {sync_directions:<25} {status:<15}"
                )

    except (MarketplaceCLIError, MarketplaceValidationError):
        raise
    except click.ClickException:
        raise
    except Exception as e:
        raise MarketplaceConnectionError(
            message=f"Failed to list connectors: {e!s}",
            error_code="CONNECTOR_LIST_FAILED",
            context={},
            original_error=e,
        )


@connectors.command("info")
@click.argument("connector_type")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["json", "table"]),
    default="table",
    help="Output format",
)
def get_connector_info(connector_type: str, output_format: str):
    """Get detailed information about a marketplace connector type"""
    try:
        # Validate connector type
        validate_marketplace_type(connector_type)

        # API endpoint: GET /api/v1/integrations/marketplace/connectors/{type}/
        data = api_client.get(f"integrations/marketplace/connectors/{connector_type.upper()}/")

        if output_format == "json":
            click.echo(json.dumps(data, indent=2))
        else:
            # Table format
            click.echo(f"Type: {data.get('type', 'N/A')}")
            click.echo(f"Display Name: {data.get('display_name', 'N/A')}")
            click.echo(f"Status: {data.get('status', 'N/A')}")
            click.echo(f"Description: {data.get('description', 'N/A')}")

            sync_directions = data.get("supported_sync_directions", [])
            if sync_directions:
                click.echo(f"Supported Sync Directions: {', '.join(sync_directions)}")
            else:
                click.echo("Supported Sync Directions: None")

            capabilities = data.get("capabilities", {})
            if capabilities:
                click.echo("\nCapabilities:")
                for capability, enabled in capabilities.items():
                    status_icon = "✓" if enabled else "✗"
                    click.echo(f"  {status_icon} {capability.capitalize()}")

            config_reqs = data.get("configuration_requirements", {})
            if config_reqs:
                click.echo("\nConfiguration Requirements:")
                required = config_reqs.get("required", [])
                if required:
                    click.echo(f"  Required: {', '.join(required)}")
                optional = config_reqs.get("optional", [])
                if optional:
                    click.echo(f"  Optional: {', '.join(optional)}")

    except (MarketplaceCLIError, MarketplaceValidationError):
        raise
    except click.ClickException as e:
        # Check if it's a 404 error by examining the error message
        error_msg = str(e).lower()
        if "404" in error_msg or "not found" in error_msg:
            raise MarketplaceValidationError(
                message=f"Connector type not found: {connector_type}",
                error_code="CONNECTOR_NOT_FOUND",
                context={"connector_type": connector_type},
                suggestion="Use 'datahub marketplace connectors list' to see available connector types",
            )
        raise
    except Exception as e:
        # Check if it's a 404 error by examining the error message
        error_msg = str(e).lower()
        if "404" in error_msg or "not found" in error_msg:
            raise MarketplaceValidationError(
                message=f"Connector type not found: {connector_type}",
                error_code="CONNECTOR_NOT_FOUND",
                context={"connector_type": connector_type},
                suggestion="Use 'datahub marketplace connectors list' to see available connector types",
            )
        raise MarketplaceConnectionError(
            message=f"Failed to get connector information: {e!s}",
            error_code="CONNECTOR_INFO_FAILED",
            context={"connector_type": connector_type},
            original_error=e,
        )


@marketplace.group("mappings")
def mappings():
    """Marketplace mapping management commands [Post-MVP]"""


@mappings.command("list")
@click.option("--connection-id", "connection_id", help="Filter by connection ID")
@click.option("--asset-id", "asset_id", help="Filter by hub asset ID")
@click.option(
    "--limit", type=int, default=50, help="Limit number of results (default: 50, max: 100)"
)
@click.option("--offset", type=int, default=0, help="Offset for pagination")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["json", "table"]),
    default="table",
    help="Output format",
)
def list_mappings(
    connection_id: str | None, asset_id: str | None, limit: int, offset: int, output_format: str
):
    """List marketplace mappings"""
    try:
        # Validate parameters
        if limit <= 0:
            raise MarketplaceValidationError(
                message="Limit must be greater than 0",
                error_code="INVALID_LIMIT",
                context={"limit": limit},
                suggestion="Provide a positive limit value (1-100)",
            )
        if limit > 100:
            raise MarketplaceValidationError(
                message="Limit cannot exceed 100",
                error_code="LIMIT_TOO_LARGE",
                context={"limit": limit},
                suggestion="Use a limit between 1 and 100",
            )
        if offset < 0:
            raise MarketplaceValidationError(
                message="Offset must be greater than or equal to 0",
                error_code="INVALID_OFFSET",
                context={"offset": offset},
                suggestion="Provide a non-negative offset value",
            )

        # Build query parameters
        params = {"page_size": limit, "page": (offset // limit) + 1 if limit > 0 else 1}

        if connection_id:
            validate_connection_id(connection_id)
            params["connection_id"] = connection_id

        if asset_id:
            validate_asset_id(asset_id)
            params["hub_asset_id"] = asset_id

        # API endpoint: GET /api/v1/integrations/marketplace/mappings/
        data = api_client.get("integrations/marketplace/mappings/", params=params)

        # Handle paginated response
        if isinstance(data, dict):
            results = data.get("results", [])
            count = data.get("count", len(results))
        elif isinstance(data, list):
            results = data
            count = len(results)
        else:
            results = []
            count = 0

        if output_format == "json":
            click.echo(json.dumps(results, indent=2))
        else:
            if not results:
                click.echo("No mappings found.")
                return

            # Table format
            click.echo(
                f"{'ID':<40} {'Connection':<30} {'Asset':<30} {'External Listing':<30} {'Last Synced':<20}"
            )
            click.echo("-" * 150)
            for mapping in results:
                mapping_id = str(mapping.get("id", ""))[:36]
                connection = mapping.get("connection", {})
                connection_name = str(connection.get("name", ""))[:28] if connection else "N/A"
                hub_asset = mapping.get("hub_asset", {})
                asset_name = str(hub_asset.get("name", ""))[:28] if hub_asset else "N/A"
                external_listing = str(mapping.get("external_listing_id", ""))[:28]
                last_synced = (
                    str(mapping.get("last_synced_at", ""))[:19]
                    if mapping.get("last_synced_at")
                    else "N/A"
                )
                click.echo(
                    f"{mapping_id:<40} {connection_name:<30} {asset_name:<30} {external_listing:<30} {last_synced:<20}"
                )

            if isinstance(data, dict) and count > len(results):
                click.echo(f"\nShowing {len(results)} of {count} mappings")

    except (MarketplaceCLIError, MarketplaceValidationError):
        raise
    except click.ClickException:
        raise
    except Exception as e:
        raise MarketplaceConnectionError(
            message=f"Failed to list mappings: {e!s}",
            error_code="MAPPING_LIST_FAILED",
            context={},
            original_error=e,
        )


@mappings.command("get")
@click.argument("mapping_id")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["json", "table"]),
    default="table",
    help="Output format",
)
def get_mapping(mapping_id: str, output_format: str):
    """Get marketplace mapping details"""
    try:
        # Validate mapping ID
        validate_mapping_id(mapping_id)

        # API endpoint: GET /api/v1/integrations/marketplace/mappings/{id}/
        data = api_client.get(f"integrations/marketplace/mappings/{mapping_id}/")

        if output_format == "json":
            click.echo(json.dumps(data, indent=2))
        else:
            # Table format
            click.echo(f"ID: {data.get('id')}")

            connection = data.get("connection", {})
            if connection:
                click.echo(f"Connection ID: {connection.get('id')}")
                click.echo(f"Connection Name: {connection.get('name')}")
                click.echo(f"Marketplace Type: {connection.get('marketplace_type')}")

            hub_asset = data.get("hub_asset", {})
            if hub_asset:
                click.echo(f"Hub Asset ID: {hub_asset.get('id')}")
                click.echo(f"Hub Asset Name: {hub_asset.get('name')}")
                click.echo(f"Hub Asset Status: {hub_asset.get('status')}")

            click.echo(f"External Listing ID: {data.get('external_listing_id')}")

            external_resource_ids = data.get("external_resource_ids", [])
            if external_resource_ids:
                click.echo(f"External Resource IDs: {', '.join(external_resource_ids)}")

            sync_metadata = data.get("sync_metadata", {})
            if sync_metadata:
                click.echo(f"Last Sync Status: {sync_metadata.get('last_sync_status', 'N/A')}")
                last_sync_errors = sync_metadata.get("last_sync_errors", [])
                if last_sync_errors:
                    click.echo(f"Last Sync Errors: {len(last_sync_errors)} error(s)")
                    for i, error in enumerate(last_sync_errors[:5], 1):
                        error_msg = (
                            error if isinstance(error, str) else error.get("message", str(error))
                        )
                        click.echo(f"  {i}. {error_msg[:100]}")
                    if len(last_sync_errors) > 5:
                        click.echo(f"  ... and {len(last_sync_errors) - 5} more errors")

            if data.get("last_synced_at"):
                click.echo(f"Last Synced: {data.get('last_synced_at')}")
            click.echo(f"Created: {data.get('created_at')}")
            if data.get("updated_at"):
                click.echo(f"Updated: {data.get('updated_at')}")

    except (MarketplaceCLIError, MarketplaceValidationError):
        raise
    except click.ClickException:
        raise
    except Exception as e:
        raise MarketplaceConnectionError(
            message=f"Failed to get mapping: {e!s}",
            error_code="MAPPING_GET_FAILED",
            context={"mapping_id": mapping_id},
            original_error=e,
        )


@mappings.command("delete")
@click.argument("mapping_id")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["json", "table"]),
    default="table",
    help="Output format",
)
def delete_mapping(mapping_id: str, output_format: str):
    """Delete a marketplace mapping"""
    try:
        # Validate mapping ID
        validate_mapping_id(mapping_id)

        # API endpoint: DELETE /api/v1/integrations/marketplace/mappings/{id}/
        api_client.delete(f"integrations/marketplace/mappings/{mapping_id}/")

        if output_format == "json":
            click.echo(
                json.dumps({"success": True, "message": "Mapping deleted successfully"}, indent=2)
            )
        else:
            click.echo("Mapping deleted successfully!")

    except (MarketplaceCLIError, MarketplaceValidationError):
        raise
    except click.ClickException:
        raise
    except Exception as e:
        raise MarketplaceConnectionError(
            message=f"Failed to delete mapping: {e!s}",
            error_code="MAPPING_DELETE_FAILED",
            context={"mapping_id": mapping_id},
            original_error=e,
        )
