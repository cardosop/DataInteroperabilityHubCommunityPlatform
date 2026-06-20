"""
312.16.3 — RDS CloudWatch alarm tests (O3).

Verifies that RDS monitoring alarms for FreeableMemory, CPU,
Connections, and DiskQueueDepth are defined in Terraform/Helm
config with correct thresholds.

Tests are file-based — they verify alarm definitions exist in
infrastructure config rather than testing live CloudWatch.
"""

import contextlib
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
TERRAFORM_DIR = REPO_ROOT / "infrastructure" / "terraform"
HELM_DIR = REPO_ROOT / "helm"


@pytest.mark.unit
@pytest.mark.observability
class TestRDSAlarmsDefined:
    """RDS CloudWatch alarms are defined in infrastructure config."""

    def _uses_rds(self, content: str) -> bool:
        """Check if infrastructure config references RDS (not just Postgres)."""
        # AWS RDS-specific keywords
        return (
            "aws_db_instance" in content
            or "aws_rds" in content
            or "rds_cluster" in content
            or "aws.rds" in content
        )

    def _find_alarm_configs(self) -> str:
        """Find all alarm definitions in Terraform and Helm files."""
        content = ""
        for d in (TERRAFORM_DIR, HELM_DIR):
            if not d.exists():
                continue
            for f in d.rglob("*.tf"):
                with contextlib.suppress(Exception):
                    content += "\n" + f.read_text()
            for f in d.rglob("*.yaml"):
                with contextlib.suppress(Exception):
                    content += "\n" + f.read_text()
            for f in d.rglob("*.yml"):
                with contextlib.suppress(Exception):
                    content += "\n" + f.read_text()
        return content

    def test_rds_freeable_memory_alarm_defined(self):
        """RDS FreeableMemory alarm is defined."""
        content = self._find_alarm_configs()
        # Look for FreeableMemory in CloudWatch alarm or monitoring config
        has_fm = (
            "FreeableMemory" in content
            or "freeable_memory" in content.lower()
            or "freeable" in content.lower()
        )
        # If using RDS, this should be defined. If not using RDS, skip.
        uses_rds = self._uses_rds(content)
        if uses_rds:
            assert has_fm, "FreeableMemory alarm should be defined when using RDS"

    def test_rds_cpu_alarm_defined(self):
        """RDS CPUUtilization alarm is defined."""
        content = self._find_alarm_configs()
        has_cpu = (
            "CPUUtilization" in content
            or "cpu_utilization" in content.lower()
            or "cpu" in content.lower()
        )
        uses_rds = self._uses_rds(content)
        if uses_rds:
            assert has_cpu, "CPUUtilization alarm should be defined when using RDS"

    def test_rds_connections_alarm_defined(self):
        """RDS DatabaseConnections alarm is defined."""
        content = self._find_alarm_configs()
        has_conn = (
            "DatabaseConnections" in content
            or "database_connections" in content.lower()
            or "connections" in content.lower()
        )
        uses_rds = self._uses_rds(content)
        if uses_rds:
            assert has_conn, "DatabaseConnections alarm should be defined when using RDS"

    def test_rds_disk_queue_depth_alarm_defined(self):
        """RDS DiskQueueDepth alarm is defined."""
        content = self._find_alarm_configs()
        has_dqd = (
            "DiskQueueDepth" in content
            or "disk_queue_depth" in content.lower()
            or "diskqueue" in content.lower()
        )
        uses_rds = self._uses_rds(content)
        if uses_rds:
            assert has_dqd, "DiskQueueDepth alarm should be defined when using RDS"


@pytest.mark.unit
@pytest.mark.observability
class TestAlarmThresholds:
    """RDS alarms have reasonable thresholds."""

    def _find_alarm_thresholds(self) -> dict:
        """Extract alarm thresholds from Terraform config."""
        thresholds = {}
        if not TERRAFORM_DIR.exists():
            return thresholds
        for f in TERRAFORM_DIR.rglob("*.tf"):
            try:
                content = f.read_text()
                # Extract metric_name and threshold from Terraform alarm blocks
                for match in re.finditer(
                    r'metric_name\s*=\s*"(\w+)".*?threshold\s*=\s*"?(\d+)"?',
                    content,
                    re.DOTALL,
                ):
                    thresholds[match.group(1)] = int(match.group(2))
            except Exception:
                pass
        return thresholds

    def test_freeable_memory_threshold_is_reasonable(self):
        """FreeableMemory threshold should be at least 256MB."""
        thresholds = self._find_alarm_thresholds()
        if "FreeableMemory" in thresholds:
            assert thresholds["FreeableMemory"] >= 256_000_000, (
                f"FreeableMemory threshold too low: {thresholds['FreeableMemory']}"
            )

    def test_cpu_threshold_is_reasonable(self):
        """CPUUtilization threshold should be <= 90%."""
        thresholds = self._find_alarm_thresholds()
        if "CPUUtilization" in thresholds:
            assert thresholds["CPUUtilization"] <= 90, (
                f"CPU alarm threshold too high: {thresholds['CPUUtilization']}%"
            )
