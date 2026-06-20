"""
Data Quality management commands.
"""

import json
import time

import click

from ..api_client import api_client


@click.group()
def dq():
    """Data Quality management commands"""


@dq.command("run")
@click.option("--asset-id", help="Asset ID to run DQ check on")
@click.option("--dataset-id", help="Dataset ID to run DQ check on")
@click.option("--file-id", help="File ID for external/scan-only DQ check")
@click.option(
    "--profile-key", default="intake_basic_gx", help="DQ profile key (default: intake_basic_gx)"
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["json", "table"]),
    default="table",
    help="Output format",
)
def run_dq(
    asset_id: str | None,
    dataset_id: str | None,
    file_id: str | None,
    profile_key: str,
    output_format: str,
):
    """Run a Data Quality check"""
    if not asset_id and not dataset_id and not file_id:
        raise click.ClickException(
            "At least one of --asset-id, --dataset-id, or --file-id must be provided"
        )

    data = {"profile_key": profile_key}
    if asset_id:
        data["asset_id"] = asset_id
    if dataset_id:
        data["dataset_id"] = dataset_id
    if file_id:
        data["file_id"] = file_id
        data["run_scope"] = "EXTERNAL"

    try:
        result = api_client.post("dq/runs/", json_data=data)

        if output_format == "json":
            click.echo(json.dumps(result, indent=2))
        else:
            # The API returns the DQ run object directly — handle both
            # flat response {"id": ..., "status": ...} and legacy nested
            # response {"dq_run": {...}, "job": {...}}.
            if isinstance(result, dict) and "dq_run" in result:
                dq_run = result["dq_run"]
                job_id = (result.get("job") or {}).get("id")
            else:
                dq_run = result if isinstance(result, dict) else {}
                # job field may be a UUID string or a dict
                job_val = dq_run.get("job")
                job_id = job_val.get("id") if isinstance(job_val, dict) else job_val

            run_id = dq_run.get("id") or "N/A"
            status = dq_run.get("status", "PENDING")
            pkey = dq_run.get("profile_key", profile_key)

            click.echo("DQ check started successfully!")
            click.echo(f"DQ Run ID: {run_id}")
            click.echo(f"Job ID: {job_id or 'N/A'}")
            click.echo(f"Status: {status}")
            click.echo(f"Profile: {pkey}")
            if job_id:
                click.echo(f"\nMonitor progress with: datahub jobs watch {job_id}")
    except click.ClickException:
        raise
    except Exception as e:
        raise click.ClickException(f"Failed to run DQ check: {e}")


@dq.command("get")
@click.argument("dq_run_id")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["json", "table"]),
    default="table",
    help="Output format",
)
def get_dq_run(dq_run_id: str, output_format: str):
    """Get DQ run details and results"""
    try:
        data = api_client.get(f"dq/runs/{dq_run_id}/")

        if output_format == "json":
            click.echo(json.dumps(data, indent=2))
        else:
            click.echo(f"DQ Run ID: {data.get('id')}")
            click.echo(f"Status: {data.get('status')}")
            click.echo(f"Overall Status: {data.get('overall_status', 'UNKNOWN')}")
            click.echo(f"Quality Score: {data.get('quality_score', 'N/A')}")
            click.echo(f"Profile: {data.get('profile_key', 'N/A')}")
            if data.get("asset"):
                click.echo(f"Asset ID: {data['asset']}")
            elif data.get("asset_id"):
                click.echo(f"Asset ID: {data['asset_id']}")
            if data.get("dataset"):
                click.echo(f"Dataset ID: {data['dataset']}")
            elif data.get("dataset_id"):
                click.echo(f"Dataset ID: {data['dataset_id']}")

            job_val = data.get("job") or data.get("job_id")
            if job_val:
                click.echo(f"Job ID: {job_val}")

            click.echo(f"Started: {data.get('started_at', 'N/A')}")
            click.echo(f"Completed: {data.get('completed_at', 'N/A')}")

            checks = data.get("checks_json") or []
            if checks:
                click.echo(f"\nChecks ({len(checks)}):")
                passed = sum(1 for c in checks if c.get("status") == "PASS")
                failed = sum(1 for c in checks if c.get("status") == "FAIL")
                warnings = sum(1 for c in checks if c.get("status") == "WARN")
                click.echo(f"  Passed: {passed}")
                click.echo(f"  Failed: {failed}")
                click.echo(f"  Warnings: {warnings}")

                failed_checks = [c for c in checks if c.get("status") == "FAIL"]
                if failed_checks:
                    click.echo("\nFailed Checks:")
                    for check in failed_checks[:10]:
                        name = check.get("name", "Unknown")
                        cat = check.get("category", "UNKNOWN")
                        click.echo(f"  - {name} ({cat})")
                    if len(failed_checks) > 10:
                        click.echo(f"  ... and {len(failed_checks) - 10} more")
    except click.ClickException:
        raise
    except Exception as e:
        raise click.ClickException(f"Failed to get DQ run: {e}")


def _safe_str(value, max_len=None):
    """Safely convert a value to string for display, handling None."""
    s = str(value) if value is not None else ""
    if max_len is not None:
        s = s[:max_len]
    return s


@dq.command("list")
@click.option("--asset-id", help="Filter by asset ID")
@click.option("--dataset-id", help="Filter by dataset ID")
@click.option("--status", help="Filter by status (PENDING, RUNNING, SUCCEEDED, FAILED)")
@click.option("--limit", type=int, default=20, help="Limit number of results")
@click.option("--offset", type=int, default=0, help="Offset for pagination")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["json", "table"]),
    default="table",
    help="Output format",
)
def list_dq_runs(
    asset_id: str | None,
    dataset_id: str | None,
    status: str | None,
    limit: int,
    offset: int,
    output_format: str,
):
    """List DQ runs"""
    params = {"limit": limit, "offset": offset}
    if asset_id:
        params["asset_id"] = asset_id
    if dataset_id:
        params["dataset_id"] = dataset_id
    if status:
        params["status"] = status

    try:
        data = api_client.get("dq/runs/", params=params)
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
                click.echo("No DQ runs found.")
                return

            header = (
                f"{'ID':<40} {'Status':<15} {'Overall Status':<15} {'Score':<10} {'Profile':<20}"
            )
            click.echo(header)
            click.echo("-" * 100)
            for dq_run in results:
                click.echo(
                    f"{_safe_str(dq_run.get('id'), 36):<40} "
                    f"{_safe_str(dq_run.get('status'), 13):<15} "
                    f"{_safe_str(dq_run.get('overall_status', 'UNKNOWN'), 13):<15} "
                    f"{_safe_str(dq_run.get('quality_score', 'N/A')):<10} "
                    f"{_safe_str(dq_run.get('profile_key'), 18):<20}"
                )
    except click.ClickException:
        raise
    except Exception as e:
        raise click.ClickException(f"Failed to list DQ runs: {e}")


@dq.command("watch")
@click.argument("dq_run_id")
@click.option("--interval", type=int, default=2, help="Polling interval in seconds")
@click.option("--timeout", type=int, default=300, help="Timeout in seconds")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["json", "table"]),
    default="table",
    help="Output format",
)
def watch_dq_run(dq_run_id: str, interval: int, timeout: int, output_format: str):
    """Watch a DQ run until completion"""
    start_time = time.time()

    try:
        while True:
            if time.time() - start_time > timeout:
                click.echo(f"\nPoll timeout for DQ run {dq_run_id}.")
                click.echo("Overall Status: UNKNOWN")
                click.echo("Error Code: POLL_TIMEOUT")
                click.echo(
                    "The DQ run may still be in progress. Check with: datahub dq get " + dq_run_id
                )
                raise click.ClickException(f"Timeout waiting for DQ run {dq_run_id} to complete")

            data = api_client.get(f"dq/runs/{dq_run_id}/")
            run_status = data.get("status")

            if output_format == "table":
                overall = data.get("overall_status", "UNKNOWN")
                score = data.get("quality_score", "N/A")
                click.echo(
                    f"DQ Run {dq_run_id}: {run_status} | Overall: {overall} | Score: {score}"
                )

            if run_status in ["SUCCEEDED", "FAILED"]:
                if output_format == "json":
                    click.echo(json.dumps(data, indent=2))
                else:
                    click.echo(f"\nDQ run {run_status.lower()}!")
                    if run_status == "SUCCEEDED":
                        click.echo(f"Overall Status: {data.get('overall_status', 'UNKNOWN')}")
                        click.echo(f"Quality Score: {data.get('quality_score', 'N/A')}")
                        checks = data.get("checks_json") or []
                        if checks:
                            passed = sum(1 for c in checks if c.get("status") == "PASS")
                            failed = sum(1 for c in checks if c.get("status") == "FAIL")
                            click.echo(f"Checks: {passed} passed, {failed} failed")
                    elif run_status == "FAILED":
                        if data.get("error_message"):
                            click.echo(f"Error: {data['error_message']}")
                return

            time.sleep(interval)
    except click.ClickException:
        raise
    except KeyboardInterrupt:
        click.echo("\nWatching cancelled by user.")
        raise
    except Exception as e:
        raise click.ClickException(f"Failed to watch DQ run: {e}")


@dq.command("scorecard")
@click.argument("asset_id")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["json", "table"]),
    default="table",
    help="Output format",
)
def get_scorecard(asset_id: str, output_format: str):
    """Get DQ scorecard for an asset.

    Retrieves recent DQ runs for the given asset and computes an
    aggregate quality summary.
    """
    try:
        # Fetch the most recent DQ runs for this asset
        data = api_client.get(
            "dq/runs/",
            params={"asset_id": asset_id, "limit": 5},
        )
        if isinstance(data, dict):
            runs = data.get("results", [])
        elif isinstance(data, list):
            runs = data
        else:
            runs = []

        if output_format == "json":
            click.echo(
                json.dumps(
                    {
                        "asset_id": asset_id,
                        "recent_runs": runs,
                    },
                    indent=2,
                )
            )
        else:
            click.echo(f"Asset ID: {asset_id}")
            if not runs:
                click.echo("No DQ runs found for this asset.")
                return

            # Show the latest run's score as the "overall" score
            latest = runs[0]
            click.echo(f"Overall Quality Score: {latest.get('quality_score', 'N/A')}")
            click.echo(f"Latest Status: {latest.get('overall_status', 'UNKNOWN')}")

            click.echo(f"\nRecent DQ Runs ({len(runs)}):")
            for run in runs:
                run_id = _safe_str(run.get("id"), 36)
                overall = run.get("overall_status", "UNKNOWN")
                score = run.get("quality_score", "N/A")
                click.echo(f"  - {run_id}: {overall} (Score: {score})")
    except click.ClickException:
        raise
    except Exception as e:
        raise click.ClickException(f"Failed to get DQ scorecard: {e}")


@dq.command("alerts")
@click.option("--list", "list_alerts", is_flag=True, help="List alerting rules")
@click.option("--create", is_flag=True, help="Create alerting rule (interactive)")
@click.option("--asset-id", help="Asset ID for alerting rule")
@click.option("--threshold", type=float, help="Quality score threshold")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["json", "table"]),
    default="table",
    help="Output format",
)
def manage_alerts(
    list_alerts: bool,
    create: bool,
    asset_id: str | None,
    threshold: float | None,
    output_format: str,
):
    """Manage DQ alerting rules"""
    if list_alerts:
        try:
            data = api_client.get("dq/alerting-rules/")
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
                    click.echo("No alerting rules found.")
                    return

                header = f"{'ID':<40} {'Asset ID':<40} {'Threshold':<15} {'Status':<15}"
                click.echo(header)
                click.echo("-" * 110)
                for rule in results:
                    click.echo(
                        f"{_safe_str(rule.get('id'), 36):<40} "
                        f"{_safe_str(rule.get('asset_id', 'N/A'), 36):<40} "
                        f"{_safe_str(rule.get('threshold', 'N/A')):<15} "
                        f"{_safe_str(rule.get('status', 'ACTIVE'), 13):<15}"
                    )
        except click.ClickException:
            raise
        except Exception as e:
            raise click.ClickException(f"Failed to list alerting rules: {e}")
    elif create:
        if not asset_id or threshold is None:
            raise click.ClickException(
                "--asset-id and --threshold are required for creating alerting rules"
            )

        payload = {"asset_id": asset_id, "threshold": threshold}

        try:
            result = api_client.post(
                "dq/alerting-rules/",
                json_data=payload,
            )

            if output_format == "json":
                click.echo(json.dumps(result, indent=2))
            else:
                click.echo("Alerting rule created successfully!")
                click.echo(f"ID: {result.get('id')}")
                click.echo(f"Asset ID: {result.get('asset_id')}")
                click.echo(f"Threshold: {result.get('threshold')}")
        except click.ClickException:
            raise
        except Exception as e:
            raise click.ClickException(f"Failed to create alerting rule: {e}")
    else:
        click.echo("Use --list to list alerting rules or --create to create one")
        click.echo("Example: datahub dq alerts --list")
        click.echo("Example: datahub dq alerts --create --asset-id <id> --threshold 80.0")
