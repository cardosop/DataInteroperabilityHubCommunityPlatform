"""Notification management commands."""

import json
import click
from ..api_client import api_client


@click.group()
def notifications():
    """Notification management."""
    pass


@notifications.command("list")
@click.option("--unread-only", is_flag=True, help="Show only unread")
def notifications_list(unread_only):
    """List notifications."""
    url = "notifications/user-notifications/"
    if unread_only:
        url += "?unread=true"
    data = api_client.get(url)
    click.echo(json.dumps(data, indent=2))


@notifications.command("get")
@click.argument("notification_id")
def notifications_get(notification_id):
    """Get a notification by ID."""
    data = api_client.get(f"notifications/user-notifications/{notification_id}/")
    click.echo(json.dumps(data, indent=2))


@notifications.command("unread-count")
def notifications_unread_count():
    """Get unread notification count."""
    data = api_client.get("notifications/user-notifications/unread-count/")
    click.echo(json.dumps(data, indent=2))


@notifications.command("read")
@click.argument("notification_id")
def notifications_read(notification_id):
    """Mark a notification as read."""
    resp = api_client.post(f"notifications/user-notifications/{notification_id}/read/", json={})
    click.echo(json.dumps(resp, indent=2))


@notifications.command("read-all")
def notifications_read_all():
    """Mark all notifications as read."""
    resp = api_client.post("notifications/user-notifications/read-all/", json={})
    click.echo(json.dumps(resp, indent=2))
