"""
283.3.2.2 — DSAR CLI commands.

Data Subject Access Request (GDPR Art. 15-22) public ingress commands.
"""
from __future__ import annotations

import json
from typing import Optional

import click

from ..api_client import api_client


@click.group()
def dsar():
    """DSAR (Data Subject Access Request) commands"""
    pass


@dsar.command("create")
@click.option("--email", required=True, help="Subject email address")
@click.option(
    "--type", "request_type", required=True,
    type=click.Choice(["access", "erasure", "rectification", "portability",
                       "restriction", "objection"]),
    help="Type of request",
)
@click.option("--tenant-id", default=None, help="Organisation UUID (optional)")
@click.option("--regimes", default=None, help="Comma-separated regimes (e.g. GDPR,CCPA)")
@click.option("--hcaptcha-token", default=None, help="hCaptcha verification token")
@click.option("--subject-tz", default=None, help="Subject IANA timezone")
@click.option("--regulator-tz", default=None, help="Regulator IANA timezone")
@click.option("--format", "output_format", type=click.Choice(["json", "table"]),
              default="table", help="Output format")
def create(
    email: str, request_type: str, tenant_id: Optional[str],
    regimes: Optional[str], hcaptcha_token: Optional[str],
    subject_tz: Optional[str], regulator_tz: Optional[str],
    output_format: str,
):
    """Submit a new data subject rights request"""
    payload = {"email": email, "type": request_type}
    if tenant_id:
        payload["tenant_id"] = tenant_id
    if regimes:
        payload["regimes"] = [r.strip() for r in regimes.split(",")]
    if hcaptcha_token:
        payload["hcaptcha_token"] = hcaptcha_token
    if subject_tz:
        payload["subject_tz"] = subject_tz
    if regulator_tz:
        payload["regulator_tz"] = regulator_tz

    try:
        data = api_client.post("public/dsar/submit/", data=payload)
        if output_format == "json":
            click.echo(json.dumps(data, indent=2))
        else:
            click.echo(f"Request submitted: {data.get('request_id') or data.get('id')}")
            click.echo(f"Status: {data.get('status')}")
            click.echo(f"Reference: {data.get('reference', 'N/A')}")
            click.echo("Check your email for the OTP verification code.")
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)


@dsar.command("verify-otp")
@click.option("--request-id", required=True, help="Request ID from create")
@click.option("--otp", required=True, help="OTP code from email")
@click.option("--format", "output_format", type=click.Choice(["json", "table"]),
              default="table", help="Output format")
def verify_otp(request_id: str, otp: str, output_format: str):
    """Verify the OTP code sent by email"""
    try:
        data = api_client.post("public/dsar/verify-otp/", data={
            "request_id": request_id, "otp": otp,
        })
        if output_format == "json":
            click.echo(json.dumps(data, indent=2))
        else:
            click.echo(f"Verification: {data.get('status')}")
            if data.get("access_token"):
                click.echo("Access token received — use it to check status.")
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)


@dsar.command("get")
@click.option("--request-id", required=True, help="Request ID")
@click.option("--format", "output_format", type=click.Choice(["json", "table"]),
              default="table", help="Output format")
def get(request_id: str, output_format: str):
    """Get DSAR request status"""
    try:
        data = api_client.get(f"public/dsar/{request_id}/status/")
        if output_format == "json":
            click.echo(json.dumps(data, indent=2))
        else:
            click.echo(f"Request ID:    {data.get('request_id', request_id)}")
            click.echo(f"Status:        {data.get('status')}")
            click.echo(f"Type:          {data.get('type', 'N/A')}")
            click.echo(f"Ack deadline:  {data.get('ack_deadline', 'N/A')}")
            click.echo(f"Fulfil by:     {data.get('fulfil_deadline', 'N/A')}")
            click.echo(f"Subject-local: {data.get('subject_local', 'N/A')}")
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)


@dsar.command("list")
@click.option("--status", "filter_status", default=None,
              help="Filter by status (PENDING, VERIFIED, IN_PROGRESS, FULFILLED, REJECTED)")
@click.option("--type", "filter_type", default=None,
              help="Filter by type (access, erasure, rectification, portability, restriction, objection)")
@click.option("--page", type=int, default=1, help="Page number")
@click.option("--page-size", type=int, default=20, help="Items per page")
@click.option("--format", "output_format", type=click.Choice(["json", "table"]),
              default="table", help="Output format")
def list_requests(filter_status: Optional[str], filter_type: Optional[str],
                  page: int, page_size: int, output_format: str):
    """List DSAR requests (authenticated/admin only)"""
    params = {"page": page, "page_size": page_size}
    if filter_status:
        params["status"] = filter_status
    if filter_type:
        params["type"] = filter_type

    try:
        data = api_client.get("public/dsar/", params=params)
        if output_format == "json":
            click.echo(json.dumps(data, indent=2))
        else:
            results = data.get("results", [])
            click.echo(f"DSAR requests: {len(results)} (page {page}, total {data.get('count', '?')})")
            for r in results:
                click.echo(f"  {r.get('id','?')[:8]}… {r.get('status'):12s} "
                           f"{r.get('type','?'):15s} {r.get('subject_email','?')}")
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)


@dsar.command("cancel")
@click.option("--request-id", required=True, help="Request ID to cancel")
@click.option("--format", "output_format", type=click.Choice(["json", "table"]),
              default="table", help="Output format")
def cancel(request_id: str, output_format: str):
    """Cancel a pending DSAR request"""
    try:
        data = api_client.post(f"public/dsar/{request_id}/cancel/", data={})
        if output_format == "json":
            click.echo(json.dumps(data, indent=2))
        else:
            click.echo(f"Request {request_id}: {data.get('status', 'CANCELLED')}")
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)
