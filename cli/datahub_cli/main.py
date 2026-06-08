"""
DataHub CLI main entry point.
"""

import sys

import click

from .auth import auth_manager
from .commands import (
    assets,
    audit,
    auth as auth_cmd,
    baas,
    billing,
    breach,
    capabilities,
    compliance,
    consent,
    contracts,
    datasets,
    developer,
    dpia,
    dq,
    drafts,
    dsar,
    events,
    federated_import,
    files,
    gdpr,
    governance,
    graphql as graphql_cmd,
    health,
    integrations,
    jobs,
    lineage,
    lineage_subscriptions,
    marketplace,
    mesh,
    ml,
    notifications,
    observability,
    openlineage,
    orchestration,
    platform,
    processor_agreements,
    retention,
    ropa,
    scheduled_export,
    scheduled_ingestion,
    search,
    security,
    social,
    semantic,
    tenants,
    transformation,
    users,
    versioning,
    virtualization,
    warehouses,
    webhooks,
)
from .commands import config as config_cmd
from .api_client import api_client
from .config import config


@click.group()
@click.version_option(version="1.0.0", prog_name="datahub")
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Preview write operations without executing them. GET requests still run; POST/PATCH/DELETE are skipped.",
)
@click.pass_context
def cli(ctx, dry_run):
    """
    DataHub CLI - Command-line tool for managing DataHub resources.

    Use 'datahub login' to authenticate, or set an API key with 'datahub config set api_key <key>'.
    """
    # Ensure context object exists
    ctx.ensure_object(dict)
    ctx.obj["dry_run"] = dry_run
    # Propagate to the global API client so every command benefits
    api_client.dry_run = dry_run


@cli.command("login")
@click.option("--email", prompt=True, help="Email address")
@click.option("--password", prompt=True, hide_input=True, help="Password")
def login(email: str, password: str):
    """Login with email and password"""
    auth_manager.login(email, password)


@cli.command("logout")
def logout():
    """Logout and clear authentication tokens"""
    auth_manager.logout()


# Add command groups
cli.add_command(auth_cmd.auth, name="auth")
cli.add_command(assets.assets, name="assets")
cli.add_command(contracts.contracts, name="contracts")
cli.add_command(lineage.lineage, name="lineage")
cli.add_command(files.files, name="files")
cli.add_command(jobs.jobs, name="jobs")
cli.add_command(config_cmd.config_cmd, name="config")
cli.add_command(dq.dq, name="dq")
cli.add_command(compliance.compliance, name="compliance")
cli.add_command(governance.governance, name="governance")
cli.add_command(mesh.mesh, name="mesh")
cli.add_command(virtualization.virtualization, name="virtualization")
cli.add_command(marketplace.marketplace, name="marketplace")
cli.add_command(baas.baas, name="baas")
cli.add_command(ml.ml, name="ml")
cli.add_command(scheduled_ingestion.scheduled_ingestion, name="scheduled-ingestion")
cli.add_command(scheduled_export.scheduled_export, name="scheduled-export")
cli.add_command(webhooks.webhooks, name="webhooks")
cli.add_command(warehouses.warehouses, name="warehouses")
cli.add_command(audit.audit, name="audit")
cli.add_command(health.health, name="health")
cli.add_command(billing.billing, name="billing")
cli.add_command(tenants.tenants, name="tenants")
cli.add_command(gdpr.gdpr, name="gdpr")
cli.add_command(social.social, name="social")
cli.add_command(search.search, name="search")
cli.add_command(transformation.transformation, name="transformation")
cli.add_command(semantic.semantic, name="semantic")
cli.add_command(graphql_cmd.graphql, name="graphql")
cli.add_command(developer.developer, name="developer")
cli.add_command(platform.platform, name="platform")
cli.add_command(security.security, name="security")
# Register versioning command group.  The rollback subcommand gracefully
# handles missing backend endpoints with clear error messages until the
# Phase 286 backend endpoint is available.
cli.add_command(versioning.versioning, name="versioning")
# Phase 0: Register 16 previously-unregistered CLI modules.
cli.add_command(breach.breach, name="breach")
cli.add_command(capabilities.capabilities, name="capabilities")
cli.add_command(consent.consent, name="consent")
cli.add_command(datasets.datasets, name="datasets")
cli.add_command(dpia.dpia, name="dpia")
cli.add_command(drafts.drafts, name="drafts")
cli.add_command(dsar.dsar, name="dsar")
cli.add_command(events.events, name="events")
cli.add_command(federated_import.federated_import, name="federated-import")
cli.add_command(integrations.integrations, name="integrations")
cli.add_command(lineage_subscriptions.lineage_subscriptions, name="lineage-subscriptions")
cli.add_command(observability.observability, name="observability")
cli.add_command(openlineage.openlineage, name="openlineage")
cli.add_command(notifications.notifications, name="notifications")
cli.add_command(orchestration.orchestration, name="orchestration")
cli.add_command(processor_agreements.processor_agreements, name="processor-agreements")
cli.add_command(retention.retention, name="retention")
cli.add_command(ropa.ropa, name="ropa")
cli.add_command(users.users, name="users")


def main():
    """Main entry point"""
    try:
        cli()
    except click.ClickException as e:
        click.echo(str(e), err=True)
        sys.exit(1)
    except KeyboardInterrupt:
        click.echo("\nOperation cancelled.", err=True)
        sys.exit(130)
    except Exception as e:
        click.echo(f"Unexpected error: {e}", err=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
