"""
Management command: report workflow post-deployment metrics (Task 5.3).

Collects validation metrics, workflow execution metrics, and produces
optimization recommendations from the database. No mocks.

Usage:
  python manage.py report_workflow_post_deployment_metrics
  python manage.py report_workflow_post_deployment_metrics --window 120
  python manage.py report_workflow_post_deployment_metrics --json
"""

import json

from django.core.management.base import BaseCommand

from hub.apps.orchestration.post_deployment import (
    PostDeploymentMetricsCollector,
    PostDeploymentReport,
)


class Command(BaseCommand):
    help = (
        "Report workflow post-deployment metrics (Task 5.3): "
        "validation rates, workflow success/failure rates, duration, "
        "and optimization recommendations."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--window",
            type=int,
            default=60,
            metavar="MINUTES",
            help="Time window in minutes (default: 60).",
        )
        parser.add_argument(
            "--json",
            action="store_true",
            help="Output report as JSON.",
        )

    def handle(self, *args, **options):
        window = options["window"]
        as_json = options["json"]

        collector = PostDeploymentMetricsCollector(time_window_minutes=window)
        report = collector.collect()

        if as_json:
            self._output_json(report)
        else:
            self._output_text(report)

    def _output_text(self, report: PostDeploymentReport) -> None:
        self.stdout.write("=== Workflow Post-Deployment Metrics (Task 5.3) ===\n")
        self.stdout.write(
            f"Window: {report.window_start} to {report.window_end} ({report.window_minutes} min)\n"
        )

        # 5.3.1 Validation metrics (from DB: validation-related failures)
        self.stdout.write("\n--- Validation metrics (5.3.1) ---\n")
        if not report.workflow_stats:
            self.stdout.write("  No workflow activity in window.\n")
        else:
            for ws in report.workflow_stats:
                if ws.started_count == 0:
                    continue
                vf = ws.validation_failure_rate
                vf_str = f"{vf:.1%}" if vf is not None else "N/A"
                self.stdout.write(
                    f"  {ws.workflow_name}: validation failures "
                    f"{ws.validation_failure_count} of {ws.started_count} ({vf_str})\n"
                )
            self.stdout.write("  Live validation/cache rates: Grafana 'Workflow Orchestration'.\n")

        # 5.3.2 Workflow execution
        self.stdout.write("\n--- Workflow execution (5.3.2) ---\n")
        if not report.workflow_stats:
            self.stdout.write("  No workflow activity in window.\n")
        else:
            for ws in report.workflow_stats:
                sr = ws.success_rate
                fr = ws.failure_rate
                sr_str = f"{sr:.1%}" if sr is not None else "N/A"
                fr_str = f"{fr:.1%}" if fr is not None else "N/A"
                dur = ws.avg_duration_seconds
                dur_str = f"{dur:.2f}s" if dur is not None else "N/A"
                self.stdout.write(
                    f"  {ws.workflow_name}: started={ws.started_count} "
                    f"completed={ws.completed_count} failed={ws.failed_count} "
                    f"success={sr_str} failure={fr_str} avg_dur={dur_str}\n"
                )

        # Step-level summary (optional)
        if report.step_stats:
            self.stdout.write("\n--- Step execution (sample) ---\n")
            for ss in report.step_stats[:10]:
                if ss.started_count == 0:
                    continue
                fr = ss.failure_rate
                fr_str = f"{fr:.1%}" if fr is not None else "N/A"
                self.stdout.write(
                    f"  {ss.workflow_name}.{ss.step_name}: started={ss.started_count} "
                    f"failed={ss.failed_count} failure={fr_str}\n"
                )
            if len(report.step_stats) > 10:
                n = len(report.step_stats) - 10
                self.stdout.write(f"  ... and {n} more step groups.\n")

        # 5.3.3 Optimize based on metrics
        self.stdout.write("\n--- Recommendations (5.3.3) ---\n")
        for rec in report.recommendations:
            self.stdout.write(f"  - {rec}\n")

        self.stdout.write("\nDone.\n")

    def _output_json(self, report: PostDeploymentReport) -> None:
        def stat_dict(ws):
            return {
                "workflow_name": ws.workflow_name,
                "started_count": ws.started_count,
                "completed_count": ws.completed_count,
                "failed_count": ws.failed_count,
                "cancelled_count": ws.cancelled_count,
                "rolled_back_count": ws.rolled_back_count,
                "avg_duration_seconds": ws.avg_duration_seconds,
                "validation_failure_count": ws.validation_failure_count,
                "success_rate": (float(ws.success_rate) if ws.success_rate is not None else None),
                "failure_rate": (float(ws.failure_rate) if ws.failure_rate is not None else None),
                "validation_failure_rate": (
                    float(ws.validation_failure_rate)
                    if ws.validation_failure_rate is not None
                    else None
                ),
            }

        def step_dict(ss):
            return {
                "workflow_name": ss.workflow_name,
                "step_name": ss.step_name,
                "started_count": ss.started_count,
                "completed_count": ss.completed_count,
                "failed_count": ss.failed_count,
                "avg_duration_seconds": ss.avg_duration_seconds,
                "validation_failure_count": ss.validation_failure_count,
                "success_rate": (float(ss.success_rate) if ss.success_rate is not None else None),
                "failure_rate": (float(ss.failure_rate) if ss.failure_rate is not None else None),
            }

        payload = {
            "window_minutes": report.window_minutes,
            "window_start": report.window_start.isoformat(),
            "window_end": report.window_end.isoformat(),
            "workflow_stats": [stat_dict(ws) for ws in report.workflow_stats],
            "step_stats": [step_dict(ss) for ss in report.step_stats],
            "recommendations": report.recommendations,
        }
        self.stdout.write(json.dumps(payload, indent=2))
