"""
Billing management commands (Phase 25).

Provides CLI commands for managing subscriptions and invoices.
Uses real hub API - no mocks/stubs.
"""

import json

import click

from ..api_client import api_client


@click.group()
def billing():
    """Billing management commands"""


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
                    f"{invoice_id:<40} {amount:<15} {status_val:<15} {due_date:<25} {paid_at:<25}"
                )
    except click.ClickException:
        raise
    except Exception as e:
        raise click.ClickException(f"Failed to list invoices: {e}")


@billing.command("plan-limits")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["json", "table"]),
    default="table",
    help="Output format",
)
def plan_limits(output_format: str):
    """Show current plan limits and usage"""
    try:
        data = api_client.get("billing/subscription/current/")
        limits = data.get("limits", {})

        if output_format == "json":
            click.echo(json.dumps(limits, indent=2))
        else:
            if not limits:
                click.echo("No limits on current plan.")
                return
            click.echo(f"{'Limit Key':<45} {'Value':<15}")
            click.echo("-" * 60)
            for k, v in sorted(limits.items()):
                val = "Unlimited" if v is None else str(v)
                click.echo(f"{k:<45} {val:<15}")
    except click.ClickException:
        raise
    except Exception as e:
        raise click.ClickException(f"Failed to get plan limits: {e}")


@billing.command("usage")
@click.option(
    "--resource-type",
    help="Filter by resource type (e.g. api_calls, storage_gb)",
)
@click.option("--limit", type=int, default=20)
@click.option("--offset", type=int, default=0)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["json", "table"]),
    default="table",
    help="Output format",
)
def get_usage(
    resource_type: str | None,
    limit: int,
    offset: int,
    output_format: str,
):
    """List usage records for current billing period"""
    params = {"limit": limit, "offset": offset}
    if resource_type:
        params["metric_key"] = resource_type

    try:
        data = api_client.get(
            "billing/usage/",
            params=params,
        )
        results = (
            data.get("results", [])
            if isinstance(data, dict)
            else data
            if isinstance(data, list)
            else []
        )

        if output_format == "json":
            click.echo(json.dumps(results, indent=2))
        else:
            if not results:
                click.echo("No usage records found.")
                return
            click.echo(f"{'Metric':<30} {'Quantity':<15} {'Period Start':<25}")
            click.echo("-" * 70)
            for r in results:
                if not isinstance(r, dict):
                    continue
                click.echo(
                    f"{r.get('metric_key', '')!s:<30} "
                    f"{r.get('quantity', '')!s:<15} "
                    f"{str(r.get('period_start', ''))[:23]:<25}"
                )
    except click.ClickException:
        raise
    except Exception as e:
        raise click.ClickException(f"Failed to get usage: {e}")


@billing.command("refund")
@click.argument("payment_intent_id")
@click.option(
    "--amount",
    "amount_cents",
    type=int,
    required=True,
    help="Refund amount in cents",
)
@click.option(
    "--reason",
    type=click.Choice(
        [
            "duplicate",
            "fraudulent",
            "requested_by_customer",
        ]
    ),
    required=True,
    help="Refund reason",
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["json", "table"]),
    default="table",
    help="Output format",
)
def process_refund(
    payment_intent_id: str,
    amount_cents: int,
    reason: str,
    output_format: str,
):
    """Issue a Stripe refund (admin only)"""
    try:
        data = api_client.post(
            "billing/refunds/",
            json_data={
                "payment_intent_id": payment_intent_id,
                "amount_cents": amount_cents,
                "reason": reason,
            },
        )
        if output_format == "json":
            click.echo(json.dumps(data, indent=2))
        else:
            click.echo("Refund issued successfully!")
            click.echo(f"Refund ID: {data.get('refund_id')}")
            click.echo(f"Status: {data.get('status')}")
            click.echo(f"Amount: {data.get('amount_cents')} cents")
    except click.ClickException:
        raise
    except Exception as e:
        raise click.ClickException(f"Failed to process refund: {e}")


@billing.command("reconcile")
@click.option("--dry-run", is_flag=True, default=False)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["json", "table"]),
    default="table",
    help="Output format",
)
def reconcile(dry_run: bool, output_format: str):
    """Reconcile subscription status with Stripe (admin)"""
    try:
        data = api_client.post(
            "billing/admin/reconcile/",
            json_data={"dry_run": dry_run},
            timeout=120,
        )
        if output_format == "json":
            click.echo(json.dumps(data, indent=2))
        else:
            click.echo(f"Checked: {data.get('checked', 0)}")
            click.echo(f"Drifted: {data.get('drifted', 0)}")
            click.echo(f"Errors: {data.get('errors', 0)}")
            if dry_run:
                click.echo("(dry-run — no changes made)")
    except click.ClickException:
        raise
    except Exception as e:
        raise click.ClickException(f"Failed to reconcile: {e}")


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
