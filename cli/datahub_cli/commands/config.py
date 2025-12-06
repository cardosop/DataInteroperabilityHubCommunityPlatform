"""
Configuration management commands.
"""
import click
import json
# Import config here to get the global instance
# Note: In tests, this will use the patched CONFIG_FILE after monkeypatch
from ..config import config


@click.group()
def config_cmd():
    """Configuration management commands"""
    pass


@config_cmd.command('get')
@click.argument('key', required=False)
@click.option('--format', 'output_format', type=click.Choice(['json', 'table']), default='table', help='Output format')
def get_config(key: str, output_format: str):
    """Get configuration value(s)"""
    if key:
        value = config.get(key)
        if output_format == 'json':
            click.echo(json.dumps({key: value}, indent=2))
        else:
            click.echo(f"{key}: {value}")
    else:
        # Show all config
        all_config = {
            'api_base_url': config.get_api_base_url(),
            'api_key': '***' if config.get_api_key() else None,
            'default_tenant': config.get_default_tenant(),
            'access_token': '***' if config.get_access_token() else None,
            'refresh_token': '***' if config.get_refresh_token() else None,
        }
        
        if output_format == 'json':
            click.echo(json.dumps(all_config, indent=2))
        else:
            click.echo("Configuration:")
            for k, v in all_config.items():
                click.echo(f"  {k}: {v}")


@config_cmd.command('set')
@click.argument('key')
@click.argument('value')
def set_config(key: str, value: str):
    """Set configuration value"""
    # Reload config to ensure we're using the correct file path (important for tests with monkeypatch)
    config._load()
    
    if key == 'api_base_url':
        config.set_api_base_url(value)
    elif key == 'api_key':
        config.set_api_key(value)
    elif key == 'default_tenant':
        config.set_default_tenant(value)
    else:
        config.set(key, value)
    
    click.echo(f"Set {key} = {value}")


@config_cmd.command('unset')
@click.argument('key')
def unset_config(key: str):
    """Unset configuration value"""
    if key in ['api_key', 'access_token', 'refresh_token']:
        click.echo("Warning: Use 'datahub logout' to clear authentication tokens", err=True)
        return
    
    config_dict = config._config
    if key in config_dict:
        del config_dict[key]
        config._save()
        click.echo(f"Unset {key}")
    else:
        click.echo(f"Key {key} not found in configuration")

