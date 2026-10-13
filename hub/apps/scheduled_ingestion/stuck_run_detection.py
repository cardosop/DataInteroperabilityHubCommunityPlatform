"""W3.5 (R2-P4) — shared stuck-run detection helpers.

The canonical liveness + Prefect-status seams used by BOTH the ingestion
detector (``detect_and_remediate_stuck_runs``) and the export detector
(``detect_and_remediate_stuck_export_runs``) — one implementation, no
sibling copies (the P1 pattern inventory).

The lease contract: a run is stuck when it is old AND its last
heartbeat is old or missing. A fresh heartbeat means the worker is
alive — the detector never touches a leased run, no matter how old the
``started_at``.
"""

from __future__ import annotations

import os
from datetime import timedelta

import requests
from django.db.models import Q
from django.utils import timezone


def stuck_run_predicate(threshold_hours: int) -> Q:
    """The shared stuck predicate.

    RUNNING runs: old AND the heartbeat lease expired (stale or
    missing); a NULL ``started_at`` never hides a run (the age then
    falls back to the heartbeat or ``created_at``).

    PENDING runs (ingestion only — the export run has no PENDING
    state): the worker never picked them up, so age is measured from
    ``created_at`` and no heartbeat is expected.
    """
    threshold_time = timezone.now() - timedelta(hours=threshold_hours)
    old_heartbeat = Q(heartbeat_at__isnull=True) | Q(heartbeat_at__lt=threshold_time)
    # A started run ages by started_at; a NULL-started run falls back to
    # created_at (a freshly created NULL-started run is not stuck yet).
    running_age = Q(started_at__lt=threshold_time) | (
        Q(started_at__isnull=True) & Q(created_at__lt=threshold_time)
    )
    return (
        Q(status="RUNNING") & running_age & old_heartbeat
        | Q(status="PENDING") & Q(created_at__lt=threshold_time)
    )


def fetch_prefect_flow_run_status(prefect_flow_run_id: str, on_warning=None) -> dict | None:
    """Check a Prefect flow run's status via the Prefect API.

    Returns the flow-run JSON, or None when the flow run is not found /
    the API is unreachable (the detector's fail-closed remediation
    path). ``on_warning`` is the command's stderr-safe note hook.
    """
    prefect_api_url = os.getenv("PREFECT_API_URL", "http://prefect-server:4200/api")
    prefect_api_key = os.getenv("PREFECT_API_KEY", "")

    headers = {}
    if prefect_api_key:
        headers["Authorization"] = f"Bearer {prefect_api_key}"

    try:
        url = f"{prefect_api_url}/flow_runs/{prefect_flow_run_id}"
        resp = requests.get(url, headers=headers, timeout=5)
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.RequestException as e:
        if on_warning:
            on_warning(f"Failed to check Prefect flow run status: {e}")
        return None
    except Exception as e:  # noqa: BLE001 — the detector never crashes on the API check
        if on_warning:
            on_warning(f"Error checking Prefect flow run status: {e}")
        return None
