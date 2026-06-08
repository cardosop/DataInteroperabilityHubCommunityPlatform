"""
280.B.2.4 — Management command: run synthetic probes against the API.

Usage:
  # One-shot run of all 4 critical probes
  python manage.py run_synthetic_probes

  # Continuous loop with configurable interval (for cron / daemon)
  python manage.py run_synthetic_probes --interval 60 --iterations 0

  # Run only specific probes
  python manage.py run_synthetic_probes --probes login,health

Metrics are emitted via structlog → Prometheus (OpenTelemetry bridge).
Alert rules in monitoring/prometheus/alerts/synthetic-probes.yml fire
when failure rate exceeds 1% for 5 minutes.
"""
from __future__ import annotations
import os
import sys
import time
import argparse
from typing import Optional

from django.core.management.base import BaseCommand

from hub.apps.health.synthetic_probes import (
    create_probes,
    run_all_probes,
    CRITICAL_PROBE_NAMES,
)


class Command(BaseCommand):
    help = "Run synthetic probes against the API (280.B.2.4)"

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            "--base-url",
            default=os.environ.get("MESHANT_API_URL", "http://localhost:8000"),
            help="API base URL (default: $MESHANT_API_URL or http://localhost:8000)",
        )
        parser.add_argument(
            "--interval",
            type=int,
            default=0,
            help="Seconds between probe cycles (0 = run once and exit)",
        )
        parser.add_argument(
            "--iterations",
            type=int,
            default=1,
            help="Number of cycles (0 = run forever). Only meaningful with --interval.",
        )
        parser.add_argument(
            "--probes",
            default="",
            help="Comma-separated probe names to run (default: all 4 critical)",
        )
        parser.add_argument(
            "--auth-email",
            default=os.environ.get("SYNTHETIC_PROBE_EMAIL", ""),
            help="Email for login probe (default: $SYNTHETIC_PROBE_EMAIL)",
        )
        parser.add_argument(
            "--auth-password",
            default=os.environ.get("SYNTHETIC_PROBE_PASSWORD", ""),
            help="Password for login probe (default: $SYNTHETIC_PROBE_PASSWORD)",
        )

    def handle(self, **options) -> None:
        base_url = options["base_url"]
        interval = options["interval"]
        iterations = options["iterations"]
        probe_filter = (
            set(p.strip() for p in options["probes"].split(",") if p.strip())
            if options["probes"]
            else None
        )

        auth_email = options["auth_email"]
        auth_password = options["auth_password"]

        if not auth_email or not auth_password:
            self.stdout.write(
                self.style.WARNING(
                    "Auth credentials not provided — login and authenticated "
                    "probes will fail. Set SYNTHETIC_PROBE_EMAIL and "
                    "SYNTHETIC_PROBE_PASSWORD env vars."
                )
            )

        # Create all probes
        all_probes = create_probes(
            base_url=base_url,
            auth_email=auth_email,
            auth_password=auth_password,
        )

        # Filter probes if requested
        if probe_filter:
            probes = {
                name: p for name, p in all_probes.items() if name in probe_filter
            }
            invalid = probe_filter - set(probes.keys())
            if invalid:
                self.stderr.write(
                    f"Unknown probe names: {sorted(invalid)}. "
                    f"Valid: {sorted(all_probes.keys())}"
                )
                sys.exit(1)
        else:
            probes = all_probes

        self.stdout.write(
            f"Running {len(probes)} probes against {base_url}"
            + (f" every {interval}s" if interval else "")
        )

        # ── Probe loop ────────────────────────────────────────────────
        cycle = 0
        max_cycles = iterations if iterations > 0 else (1 if interval == 0 else None)

        while max_cycles is None or cycle < max_cycles:
            cycle += 1

            # Obtain auth token via login probe (or reuse from env)
            auth_token = self._obtain_token(
                all_probes.get("login"), auth_email, auth_password
            )

            summary = run_all_probes(probes, auth_token=auth_token)

            self.stdout.write(
                f"[{summary.timestamp.isoformat()}] "
                f"cycle={cycle} "
                f"passed={summary.passed}/{summary.total_probes} "
                f"failed={summary.failed} "
                f"failure_rate={summary.failure_rate:.1%}"
            )

            # Log structured metrics for Prometheus alerting
            for result in summary.results:
                self.stdout.write(
                    f"  {result.probe_name:15s} "
                    f"{'PASS' if result.success else 'FAIL':5s} "
                    f"{result.latency_ms:8.1f}ms"
                    + (f"  status={result.status_code}" if result.status_code else "")
                    + (
                        f"  error={result.error_message}"
                        if result.error_message
                        else ""
                    )
                )

            if summary.failure_rate > 0.01:
                self.stdout.write(
                    self.style.WARNING(
                        f"⚠  Failure rate {summary.failure_rate:.1%} exceeds 1% "
                        f"threshold — alert may fire if sustained for 5 min."
                    )
                )

            if interval > 0 and (max_cycles is None or cycle < max_cycles):
                time.sleep(interval)

        # ── Final summary ─────────────────────────────────────────────
        self.stdout.write(
            self.style.SUCCESS(f"Probe run complete. {cycle} cycle(s).")
        )

    def _obtain_token(
        self,
        login_probe,
        auth_email: Optional[str],
        auth_password: Optional[str],
    ) -> Optional[str]:
        """Run the login probe to get a JWT for authenticated probes.

        Extracts the token from the ProbeResult.response_body — no second
        HTTP request is made (the probe already captured the JSON body).
        """
        if login_probe is None:
            return None
        if not auth_email or not auth_password:
            return None

        result = login_probe.run()
        if not result.success:
            return None

        response_body = result.response_body
        if isinstance(response_body, dict):
            token = response_body.get("access_token")
            if token:
                return token

        return None
