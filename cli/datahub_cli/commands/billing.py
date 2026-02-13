"""
Billing management commands (Phase 25).

Provides CLI commands for managing subscriptions and invoices.
Uses real hub API - no mocks/stubs.
"""

import json
from typing import Optional

import click

from ..api_client import api_client


@click.group()
def billing():
    """Billing management commands"""
    pass


@billing.command("subscription")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["json", "table"]),
    default="table",
    help="Output format",
)
def get_subscription(output_format: str):
    """Get current subscription for tenant"""
    try:
        data = api_client.get("billing/subscription/current/")

        if output_format == "json":
            click.echo(json.dumps(data, indent=2))
        else:
            click.echo(f"Subscription ID: {data.get('id')}")
            click.echo(f"Plan: {data.get('plan_name')} ({data.get('plan_slug')})")
            click.echo(f"Tier: {data.get('plan_tier')}")
            click.echo(f"Status: {data.get('status')}")
            click.echo(f"Current Period Start: {data.get('current_period_start')}")
            click.echo(f"Current Period End: {data.get('current_period_end')}")
            if data.get("trial_end"):
                click.echo(f"Trial End: {data.get('trial_end')}")
            if data.get("canceled_at"):
                click.echo(f"Canceled At: {data.get('canceled_at')}")
    except click.ClickException:
        raise
    except Exception as e:
        raise click.ClickException(f"Failed to get subscription: {e}")


@billing.command("invoices")
@click.option("--limit", type=int, default=20, help="Limit number of results")
@click.option("--offset", type=int, default=0, help="Offset for pagination")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["json", "table"]),
    default="table",
    help="Output format",
)
def list_invoices(limit: int, offset: int, output_format: str):
    """List invoices for tenant"""
    params = {"limit": limit, "offset": offset}

    try:
        data = api_client.get("billing/invoices/", params=params)
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
                click.echo("No invoices found.")
                return

            # Table format
            click.echo(f"{'ID':<40} {'Amount':<15} {'Status':<15} {'Due Date':<25} {'Paid At':<25}")
            click.echo("-" * 120)
            for invoice in results:
                if not isinstance(invoice, dict):
                    continue
                invoice_id = str(invoice.get("id", ""))[:36] if invoice.get("id") else ""
                amount = f"{invoice.get('amount_due', 0):.2f} {invoice.get('currency', 'USD')}"
                status_val = str(invoice.get("status", ""))[:13] if invoice.get("status") else ""
                due_date = (
                    str(invoice.get("due_date", ""))[:23] if invoice.get("due_date") else "N/A"
                )
                paid_at = str(invoice.get("paid_at", ""))[:23] if invoice.get("paid_at") else "N/A"
                click.echo(
                    f"{invoice_id:<40} "
                    f"{amount:<15} "
                    f"{status_val:<15} "
                    f"{due_date:<25} "
                    f"{paid_at:<25}"
                )
    except click.ClickException:
        raise
    except Exception as e:
        raise click.ClickException(f"Failed to list invoices: {e}")


@billing.command("invoice")
@click.argument("invoice_id")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["json", "table"]),
    default="table",
    help="Output format",
)
def get_invoice(invoice_id: str, output_format: str):
    """Get invoice details"""
    try:
        data = api_client.get(f"billing/invoices/{invoice_id}/")

        if output_format == "json":
            click.echo(json.dumps(data, indent=2))
        else:
            click.echo(f"Invoice ID: {data.get('id')}")
            click.echo(f"Amount Due: {data.get('amount_due', 0):.2f} {data.get('currency', 'USD')}")
            click.echo(
                f"Amount Paid: {data.get('amount_paid', 0):.2f} {data.get('currency', 'USD')}"
            )
            click.echo(f"Status: {data.get('status')}")
            if data.get("due_date"):
                click.echo(f"Due Date: {data.get('due_date')}")
            if data.get("paid_at"):
                click.echo(f"Paid At: {data.get('paid_at')}")
            if data.get("invoice_pdf_url"):
                click.echo(f"PDF URL: {data.get('invoice_pdf_url')}")
    except click.ClickException:
        raise
    except Exception as e:
        raise click.ClickException(f"Failed to get invoice: {e}")
