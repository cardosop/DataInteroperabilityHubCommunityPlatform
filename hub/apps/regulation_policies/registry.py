"""
Loaders and derived policy windows (Phase 232.0).

Retention and identity-verification knobs are **defaults**; tenant-specific
overrides remain in ``TenantConfig`` / future policy apps.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Any, cast

import yaml
from django.conf import settings


@dataclass(frozen=True, slots=True)
class RegulationAuthority:
    """Public metadata for a supervisory authority."""

    id: str
    name: str
    jurisdiction: str
    website: str | None


_STATUTORY_DEADLINE_DEFAULTS: dict[str, dict[str, Any]] = {
    # GDPR / UK GDPR style windows (calendar days unless noted).
    "GDPR": {
        "dsar_acknowledgement_hours": 72,
        "dsar_extension_calendar_days": 90,
        "breach_notification_hours_where_feasible": 72,
        "breach_supervisory_authority_hours": 72,
    },
    # LGPD baseline (hours surrogate for statutory business-day windows).
    "LGPD": {
        "dsar_confirmation_business_days_equivalent_hours": 120,
        "simple_dsar_response_calendar_days": 15,
    },
}


_RETENTION_RULE_DEFAULTS: dict[str, dict[str, Any]] = {
    "PLATFORM_DEFAULT": {
        "audit_event_retention_years_min": 3,
        "job_metadata_retention_years_min": 3,
    },
}


_IDV_POLICY_DEFAULTS: dict[str, Any] = {
    "kyb_required_for_marketplace_publish": True,
    "minimum_evidence_tier": "ORG_VERIFIED",
}

# Phase 232.2 — DSAR statutory-clock matrix (UTC computation; business-day
# refinements land in a later sub-phase). Values are **defaults** only.
_DSAR_STATUTORY_CLOCK_MATRIX: dict[str, dict[str, Any]] = {
    "GDPR": {
        "acknowledgement_hours": 72,
        "fulfilment_calendar_days": 30,
        "fulfilment_extension_calendar_days": 60,
        "sla_warn_days_before_deadline": 7,
        "sla_alert_days_before_deadline": 1,
        "sla_escalate_on_deadline_breach": True,
    },
    "UK_GDPR": {
        "acknowledgement_hours": 72,
        "fulfilment_calendar_days": 30,
        "fulfilment_extension_calendar_days": 60,
        "sla_warn_days_before_deadline": 7,
        "sla_alert_days_before_deadline": 1,
        "sla_escalate_on_deadline_breach": True,
    },
    "LGPD": {
        "acknowledgement_hours": 168,
        "fulfilment_calendar_days": 15,
        "fulfilment_extension_calendar_days": None,
        "sla_warn_days_before_deadline": 7,
        "sla_alert_days_before_deadline": 2,
        "sla_escalate_on_deadline_breach": True,
    },
    "CCPA": {
        "acknowledgement_hours": 72,
        "fulfilment_calendar_days": 45,
        "fulfilment_extension_calendar_days": 90,
        "sla_warn_days_before_deadline": 7,
        "sla_alert_days_before_deadline": 1,
        "sla_escalate_on_deadline_breach": True,
    },
    "CPA_COLORADO": {
        "acknowledgement_hours": 72,
        "fulfilment_calendar_days": 45,
        "fulfilment_extension_calendar_days": None,
        "sla_warn_days_before_deadline": 7,
        "sla_alert_days_before_deadline": 1,
        "sla_escalate_on_deadline_breach": True,
    },
}
_DEFAULT_DSAR_CLOCK_KEY = "GDPR"

# Phase 232.7 — default calendar-day retention horizons for regulated **datasets/assets**
# when a tenant attaches ``regulation_keys`` to a TIME_BASED ``RetentionPolicy``.
# Product/counsel may tune deployments; unknown keys inherit the PLATFORM_DEFAULT
# floor from ``_RETENTION_RULE_DEFAULTS``.
_DATA_RESOURCE_RETENTION_DAYS_BY_REGIME: dict[str, int] = {
    "GDPR": 2555,
    "UK_GDPR": 2555,
    "LGPD": 1825,
    "CCPA": 730,
    "CPA_COLORADO": 730,
}

# Phase 232.3 — breach supervisory notification SLA matrix (UTC hours).
_DEFAULT_BREACH_CLOCK_KEY = "GDPR"
_BREACH_STATUTORY_CLOCK_MATRIX: dict[str, dict[str, Any]] = {
    "GDPR": {
        "supervisory_notification_hours": 72,
        "sla_warn_hours_before_deadline": 24,
        "sla_alert_hours_before_deadline": 6,
        "sla_escalate_on_deadline_breach": True,
    },
    "UK_GDPR": {
        "supervisory_notification_hours": 72,
        "sla_warn_hours_before_deadline": 24,
        "sla_alert_hours_before_deadline": 6,
        "sla_escalate_on_deadline_breach": True,
    },
    "LGPD": {
        "supervisory_notification_hours": 72,
        "sla_warn_hours_before_deadline": 48,
        "sla_alert_hours_before_deadline": 12,
        "sla_escalate_on_deadline_breach": True,
    },
    "CCPA": {
        "supervisory_notification_hours": 96,
        "sla_warn_hours_before_deadline": 24,
        "sla_alert_hours_before_deadline": 8,
        "sla_escalate_on_deadline_breach": True,
    },
}


def _data_path() -> Path:
    base = Path(settings.BASE_DIR)
    return base / "data" / "regulation_authorities.yaml"


@lru_cache(maxsize=1)
def _regulation_yaml_document() -> dict[str, Any]:
    """Cached YAML root document (authorities + breach routing)."""
    path = _data_path()
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    return cast("dict[str, Any]", raw if isinstance(raw, dict) else {})


@lru_cache(maxsize=1)
def load_regulation_authorities() -> tuple[RegulationAuthority, ...]:
    """Parse ``data/regulation_authorities.yaml`` into immutable tuples."""
    raw = _regulation_yaml_document()
    rows = raw.get("authorities") or []
    out: list[RegulationAuthority] = []
    for row in rows:
        out.append(
            RegulationAuthority(
                id=str(row["id"]),
                name=str(row["name"]),
                jurisdiction=str(row["jurisdiction"]),
                website=row.get("website"),
            )
        )
    return tuple(out)


@lru_cache(maxsize=1)
def breach_notification_routing_map() -> dict[str, tuple[str, ...]]:
    """Regime → supervisory authority ids from ``breach_notification_routing``."""
    raw = _regulation_yaml_document()
    out: dict[str, tuple[str, ...]] = {}
    for row in raw.get("breach_notification_routing") or []:
        if not isinstance(row, dict):
            continue
        regime = str(row.get("regime", "")).upper().strip()
        if not regime:
            continue
        ids_raw = row.get("supervisory_authority_ids") or []
        if not isinstance(ids_raw, list):
            ids_raw = []
        out[regime] = tuple(str(x) for x in ids_raw)
    return out


def resolve_breach_supervisory_authority_ids(regime: str) -> tuple[str, ...]:
    """Resolve YAML ids for ``regime``; unknown regimes inherit GDPR routing."""
    m = breach_notification_routing_map()
    key = regime.upper().strip()
    if key in m:
        return m[key]
    return m.get(_DEFAULT_BREACH_CLOCK_KEY, ())


def breach_statutory_clock_matrix(regime: str) -> dict[str, Any]:
    """Breach SLA parameters for ``regime`` (hours-based)."""
    key = regime.upper().strip()
    row = _BREACH_STATUTORY_CLOCK_MATRIX.get(key)
    if row is None:
        row = _BREACH_STATUTORY_CLOCK_MATRIX[_DEFAULT_BREACH_CLOCK_KEY]
    out = dict(row)
    sd = statutory_deadlines_for(key) or statutory_deadlines_for(_DEFAULT_BREACH_CLOCK_KEY)
    h = sd.get("breach_supervisory_authority_hours")
    if h is not None:
        out["supervisory_notification_hours"] = int(h)
    return out


def compute_breach_supervisory_deadline_utc(
    discovered_at_utc: datetime,
    regimes: tuple[str, ...],
) -> datetime:
    """Soonest supervisory-notification deadline across ``regimes``."""
    if not regimes:
        regimes = (_DEFAULT_BREACH_CLOCK_KEY,)
    deltas: list[timedelta] = []
    for r in regimes:
        m = breach_statutory_clock_matrix(r)
        hours = int(m["supervisory_notification_hours"])
        deltas.append(timedelta(hours=hours))
    return discovered_at_utc + min(deltas)


def merge_breach_incident_sla_windows(regimes: Iterable[str]) -> dict[str, Any]:
    """
    Merge per-regime breach SLA parameters for scanner escalation.

    Warn/alert windows use the **strictest** (minimum hours-before-deadline).
    Escalate-after-deadline is True if **any** regime requests it.
    """
    keys = tuple(sorted({str(r).upper().strip() for r in regimes if str(r).strip()}))
    if not keys:
        keys = (_DEFAULT_BREACH_CLOCK_KEY,)
    base = breach_statutory_clock_matrix(keys[0])
    out: dict[str, Any] = dict(base)
    for r in keys[1:]:
        m = breach_statutory_clock_matrix(r)
        out["sla_warn_hours_before_deadline"] = min(
            float(out["sla_warn_hours_before_deadline"]),
            float(m["sla_warn_hours_before_deadline"]),
        )
        out["sla_alert_hours_before_deadline"] = min(
            float(out["sla_alert_hours_before_deadline"]),
            float(m["sla_alert_hours_before_deadline"]),
        )
        out["sla_escalate_on_deadline_breach"] = bool(
            out.get("sla_escalate_on_deadline_breach") or m.get("sla_escalate_on_deadline_breach")
        )
    return out


def get_authority_by_id(authority_id: str) -> RegulationAuthority | None:
    for auth in load_regulation_authorities():
        if auth.id == authority_id:
            return auth
    return None


def statutory_deadlines_for(regime: str) -> dict[str, Any]:
    """Return a copy of default statutory windows for ``regime`` (e.g. GDPR)."""
    key = regime.upper()
    return dict(_STATUTORY_DEADLINE_DEFAULTS.get(key, {}))


def retention_defaults() -> dict[str, Any]:
    return dict(_RETENTION_RULE_DEFAULTS["PLATFORM_DEFAULT"])


def data_retention_period_days_for_regime_keys(keys: Iterable[str]) -> int:
    """
    Return the strictest horizon (maximum days across regimes) implied by ``keys``.

    Unknown regime tokens fall back to the platform statutory minimum expressed
    via ``audit_event_retention_years_min`` (calendar-day approximation).

    Phase 232.7 — used by governance ``RetentionPolicy`` when ``regulation_keys``
    is non-empty for TIME_BASED policies.
    """
    yrs = retention_defaults().get("audit_event_retention_years_min")
    fallback_days = int(yrs * 365) if yrs else 1095

    ks = tuple(sorted({str(x).upper().strip() for x in keys if str(x).strip()}))
    if not ks:
        return 0

    resolved: list[int] = []
    for k in ks:
        d = _DATA_RESOURCE_RETENTION_DAYS_BY_REGIME.get(k)
        if d is not None:
            resolved.append(int(d))
        else:
            resolved.append(fallback_days)

    return max(resolved)


def idv_defaults() -> dict[str, Any]:
    return dict(_IDV_POLICY_DEFAULTS)


def dsar_statutory_clock_matrix(regime: str) -> dict[str, Any]:
    """Return a copy of default DSAR SLA parameters for ``regime`` (e.g. ``GDPR``)."""
    key = regime.upper().strip()
    row = _DSAR_STATUTORY_CLOCK_MATRIX.get(key)
    if row is None:
        row = _DSAR_STATUTORY_CLOCK_MATRIX[_DEFAULT_DSAR_CLOCK_KEY]
    return dict(row)


def compute_dsar_ack_deadline_utc(
    submitted_at_utc: datetime,
    regimes: tuple[str, ...],
) -> datetime:
    """Earliest acknowledgement deadline across regimes (strictest for the controller)."""
    if not regimes:
        regimes = (_DEFAULT_DSAR_CLOCK_KEY,)
    deltas: list[timedelta] = []
    for r in regimes:
        m = dsar_statutory_clock_matrix(r)
        hours = int(m["acknowledgement_hours"])
        deltas.append(timedelta(hours=hours))
    # min timedelta == soonest deadline
    step = min(deltas)
    return submitted_at_utc + step


def compute_dsar_fulfilment_deadline_utc(
    submitted_at_utc: datetime,
    regimes: tuple[str, ...],
    *,
    use_extension_path: bool = False,
) -> datetime:
    """
    Earliest primary (or extended) fulfilment deadline across regimes.

    ``use_extension_path`` selects the longer statutory window when defined
    (e.g. GDPR +2 months extension path).
    """
    if not regimes:
        regimes = (_DEFAULT_DSAR_CLOCK_KEY,)
    deltas: list[timedelta] = []
    for r in regimes:
        m = dsar_statutory_clock_matrix(r)
        if use_extension_path and m.get("fulfilment_extension_calendar_days"):
            days = int(m["fulfilment_extension_calendar_days"])
        else:
            days = int(m["fulfilment_calendar_days"])
        deltas.append(timedelta(days=days))
    step = min(deltas)
    return submitted_at_utc + step
