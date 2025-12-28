"""
DataHub CLI main entry point.
"""
import click
import sys
from .commands import assets, contracts, files, jobs, config as config_cmd, lineage, dq, compliance, governance, mesh, transformation, virtualization
from .auth import auth_manager
from .config import config


@click.group()
@click.version_option(version='1.0.0', prog_name='datahub')
@click.pass_context
def cli(ctx):
    """
    DataHub CLI - Command-line tool for managing DataHub resources.

    Use 'datahub login' to authenticate, or set an API key with 'datahub config set api_key <key>'.
    """
    # Ensure context object exists
    ctx.ensure_object(dict)


@cli.command('login')
@click.option('--email', prompt=True, help='Email address')
@click.option('--password', prompt=True, hide_input=True, help='Password')
def login(email: str, password: str):
    """Login with email and password"""
    auth_manager.login(email, password)


@cli.command('logout')
def logout():
    """Logout and clear authentication tokens"""
    auth_manager.logout()


# Add command groups
cli.add_command(assets.assets, name='assets')
cli.add_command(contracts.contracts, name='contracts')
cli.add_command(lineage.lineage, name='lineage')
cli.add_command(files.files, name='files')
cli.add_command(jobs.jobs, name='jobs')
cli.add_command(config_cmd.config_cmd, name='config')
cli.add_command(dq.dq, name='dq')
cli.add_command(compliance.compliance, name='compliance')
cli.add_command(governance.governance, name='governance')
cli.add_command(mesh.mesh, name='mesh')
cli.add_command(transformation.transformation, name='transformation')
cli.add_command(virtualization.virtualization, name='virtualization')


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


if __name__ == '__main__':
    main()

