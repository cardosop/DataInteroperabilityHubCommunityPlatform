"""W7.4 (oss-release-remediation) — alert-file loading pins.

19 real alert-rule files sat unloaded in monitoring/prometheus/alerts/
(the design's "19 unloaded alert files") — rules that never fired
anywhere.  Contract now pinned:

  * every alert file whose name does NOT end in ``-synthetic-firing``
    is listed in ``monitoring/prometheus/prometheus.yml`` rule_files
    (the synthetic-firing files are promtool TEST fixtures — they stay
    unloaded by design and are referenced from the suites that run
    them);
  * every loaded file passes ``promtool check rules`` (a parse-broken
    rule file breaks prometheus boot) — two pre-existing broken files
    were fixed on the way (breach-sla's template arithmetic, rq-queue's
    invalid range/`by` expressions).
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent.parent
ALERTS = REPO / "monitoring" / "prometheus" / "alerts"
PROMETHEUS_YML = REPO / "monitoring" / "prometheus" / "prometheus.yml"

PROMTOOL = shutil.which("promtool")
requires_promtool = pytest.mark.skipif(PROMTOOL is None, reason="promtool not installed")


def _rule_files() -> set[str]:
    text = PROMETHEUS_YML.read_text()
    out: set[str] = set()
    in_rf = False
    for line in text.splitlines():
        if line.strip() == "rule_files:":
            in_rf = True
            continue
        if in_rf:
            if line.strip() and not line.startswith((" ", "-", "#")):
                in_rf = False
                continue
            for part in line.split():
                if part.startswith("'alerts/") and part.endswith(".yml'"):
                    out.add(part.strip("'"))
    return out


def _alert_files() -> dict[str, Path]:
    return {f.name: f for f in ALERTS.glob("*.yml")}


def test_every_real_alert_file_is_loaded():
    """The only unloaded alert files are the synthetic-firing fixtures."""
    loaded = {Path(r).name for r in _rule_files()}
    unloaded = []
    for name, _path in sorted(_alert_files().items()):
        if name.endswith("-firing.yml"):
            continue
        if name not in loaded:
            unloaded.append(name)
    assert not unloaded, f"unloaded alert files: {unloaded}"


def test_synthetic_firing_files_are_not_loaded():
    """Synthetic-firing files are promtool test fixtures — loading them
    would fire synthetic alerts in production prometheus."""
    loaded = {Path(r).name for r in _rule_files()}
    for name in sorted(_alert_files()):
        if name.endswith("-firing.yml"):
            assert name not in loaded, f"fixture {name} must not be loaded"


def test_rule_files_entries_exist_on_disk():
    for rel in _rule_files():
        assert (REPO / "monitoring" / "prometheus" / rel).exists(), rel


@requires_promtool
def test_every_loaded_file_passes_promtool():
    broken = []
    for rel in sorted(_rule_files()):
        result = subprocess.run(
            [PROMTOOL, "check", "rules", str(REPO / "monitoring" / "prometheus" / rel)],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            broken.append((rel, result.stderr.strip().splitlines()[-1]))
    assert not broken, f"parse-broken rule files: {broken}"
