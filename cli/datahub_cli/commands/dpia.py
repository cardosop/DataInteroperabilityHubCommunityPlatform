"""
283.3.5.2 — DPIA CLI commands with wizard flow.

Data Protection Impact Assessment (GDPR Art. 35) commands.
"""

from __future__ import annotations

import json

import click

from ..api_client import api_client

DPIA_PREFIX = "dpia/records"


@click.group()
def dpia():
    """DPIA (Data Protection Impact Assessment) commands"""


@dpia.command("create")
@click.option("--title", required=True, help="Assessment title")
@click.option("--description", required=True, help="Processing activity description")
@click.option("--data-categories", default=None, help="Comma-separated data categories")
@click.option(
    "--risk-level",
    type=click.Choice(["LOW", "MEDIUM", "HIGH"]),
    default="MEDIUM",
    help="Initial risk level",
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["json", "table"]),
    default="table",
    help="Output format",
)
def create(
    title: str, description: str, data_categories: str | None, risk_level: str, output_format: str
):
    """Create a new DPIA assessment"""
    payload = {"title": title, "description": description, "risk_level": risk_level}
    if data_categories:
        payload["data_categories"] = [c.strip() for c in data_categories.split(",")]
    try:
        data = api_client.post(f"{DPIA_PREFIX}/", data=payload)
        if output_format == "json":
            click.echo(json.dumps(data, indent=2))
        else:
            click.echo(f"DPIA created: {data.get('id')}")
            click.echo(f"Status: {data.get('status')}")
            click.echo(f"Risk Level: {data.get('risk_level')}")
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)


@dpia.command("list")
@click.option(
    "--status",
    "filter_status",
    default=None,
    help="Filter by status (DRAFT, SUBMITTED, IN_REVIEW, APPROVED, REJECTED)",
)
@click.option("--page", type=int, default=1)
@click.option("--page-size", type=int, default=25)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["json", "table"]),
    default="table",
    help="Output format",
)
def list_assessments(filter_status: str | None, page: int, page_size: int, output_format: str):
    """List DPIA assessments"""
    params = {"page": page, "page_size": page_size}
    if filter_status:
        params["status"] = filter_status
    try:
        data = api_client.get(f"{DPIA_PREFIX}/", params=params)
        if output_format == "json":
            click.echo(json.dumps(data, indent=2))
        else:
            results = data.get("results", [])
            click.echo(f"DPIAs: {len(results)} (page {page}, total {data.get('count', '?')})")
            for r in results:
                click.echo(
                    f"  {r.get('id', '?')[:8]}… {r.get('status', '?'):15s} "
                    f"{r.get('risk_level', '?'):8s} {r.get('title', '?')[:60]}"
                )
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)


@dpia.command("get")
@click.option("--dpia-id", required=True, help="DPIA UUID")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["json", "table"]),
    default="table",
    help="Output format",
)
def get(dpia_id: str, output_format: str):
    """Get DPIA assessment details"""
    try:
        data = api_client.get(f"{DPIA_PREFIX}/{dpia_id}/")
        if output_format == "json":
            click.echo(json.dumps(data, indent=2))
        else:
            click.echo(f"ID:          {data.get('id')}")
            click.echo(f"Title:       {data.get('title')}")
            click.echo(f"Status:      {data.get('status')}")
            click.echo(f"Risk Level:  {data.get('risk_level')}")
            click.echo(f"Description: {data.get('description', '')[:200]}")
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)


@dpia.command("submit")
@click.option("--dpia-id", required=True, help="DPIA UUID")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["json", "table"]),
    default="table",
    help="Output format",
)
def submit(dpia_id: str, output_format: str):
    """Submit a DPIA for DPO review"""
    try:
        data = api_client.post(f"{DPIA_PREFIX}/{dpia_id}/submit/")
        if output_format == "json":
            click.echo(json.dumps(data, indent=2))
        else:
            click.echo(f"DPIA submitted: {data.get('status')}")
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)


@dpia.command("review-queue")
@click.option("--page", type=int, default=1)
@click.option("--page-size", type=int, default=25)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["json", "table"]),
    default="table",
    help="Output format",
)
def review_queue(page: int, page_size: int, output_format: str):
    """View periodic review queue (DPIAs due for review)"""
    try:
        data = api_client.get(
            f"{DPIA_PREFIX}/", params={"page": page, "page_size": page_size, "status": "APPROVED"}
        )
        if output_format == "json":
            click.echo(json.dumps(data, indent=2))
        else:
            results = data.get("results", [])
            click.echo(f"Review queue (APPROVED DPIAs): {len(results)}")
            for r in results:
                click.echo(f"  {r.get('id', '?')[:8]}… {r.get('title', '?')[:50]}")
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)


@dpia.command("trigger-review")
@click.option("--dpia-id", required=True, help="DPIA UUID")
@click.option("--notes", default="", help="Reviewer notes")
@click.option("--assigned-to", default=None, help="Reviewer user ID")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["json", "table"]),
    default="table",
    help="Output format",
)
def trigger_review(dpia_id: str, notes: str, assigned_to: str | None, output_format: str):
    """Trigger a periodic review for a completed DPIA"""
    try:
        data = api_client.post(f"{DPIA_PREFIX}/{dpia_id}/submit/")
        if output_format == "json":
            click.echo(json.dumps(data, indent=2))
        else:
            click.echo(f"Review triggered: {data.get('review_status', 'PENDING')}")
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)


@dpia.command("wizard")
@click.option("--title", prompt=True, help="Assessment title")
@click.option("--description", prompt=True, help="Processing activity description")
@click.option("--data-categories", prompt=True, default="", help="Comma-separated data categories")
@click.option(
    "--risk-level",
    type=click.Choice(["LOW", "MEDIUM", "HIGH"]),
    prompt="Risk level",
    default="MEDIUM",
)
def wizard(title: str, description: str, data_categories: str, risk_level: str):
    """Interactive DPIA creation wizard (step-by-step)"""
    click.echo("\n═══ DPIA Creation Wizard ═══\n")

    cats = [c.strip() for c in data_categories.split(",") if c.strip()] if data_categories else []
    payload = {
        "title": title,
        "description": description,
        "risk_level": risk_level,
        "data_categories": cats,
    }

    click.echo("Summary:")
    click.echo(f"  Title:          {title}")
    click.echo(f"  Risk Level:     {risk_level}")
    click.echo(f"  Categories:     {', '.join(cats) if cats else 'none'}")
    click.echo(f"  Description:    {description[:100]}...")

    if not click.confirm("\nCreate this DPIA assessment?"):
        click.echo("Cancelled.")
        return

    try:
        data = api_client.post(f"{DPIA_PREFIX}/", data=payload)
        click.echo(f"\n✅ DPIA created: {data.get('id')}")
        click.echo(f"   Status: {data.get('status')}")
        click.echo(f"   Submit when ready: datahub dpia submit --dpia-id {data.get('id')}")
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)
