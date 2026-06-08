"""
281.B.7.6–281.B.7.8 — Customer Health Score Model.

Composite 0-100 health score from:
  - login_frequency:   How often tenant users log in (30d window)
  - error_rate:        API error rate (7d window)
  - support_tickets:   Open/support ticket count
  - feature_adoption:  % of available features actively used
  - recency:           Days since last login (any user)

At-risk detection:
  - Health <50 → CS alert (warning)
  - Health <30 → escalation (critical)
  - Weekly automated health report

Formula (weighted sum, normalised 0-100):
  health = (login_freq * 25) + (feature_adoption * 30) + (recency * 20)
           - (error_rate * 15) - (support_tickets * 10)
"""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Optional

from django.utils import timezone as dj_timezone

# ── Weights ─────────────────────────────────────────────────────────────────

WEIGHTS = {
    "login_frequency": 25,
    "feature_adoption": 30,
    "recency": 20,
    "error_rate": -15,
    "support_tickets": -10,
}

RISK_THRESHOLD_CS_ALERT = 50   # Health <50 → customer success alert
RISK_THRESHOLD_ESCALATION = 30  # Health <30 → escalation to account manager


@dataclass
class TenantHealthSnapshot:
    """Health score for a single tenant at a point in time."""

    tenant_id: str
    tenant_name: str
    plan_name: str
    persona_slug: str

    # Raw metrics
    login_frequency: float = 0.0      # logins/user/week normalised 0-1
    error_rate: float = 0.0            # error rate 0-1 (0=no errors)
    support_tickets: int = 0           # open tickets
    feature_adoption: float = 0.0      # % of features used 0-1
    recency: float = 0.0               # 1.0=today, decays to 0 at 30 days
    days_since_last_login: int = 30

    # Composite
    health_score: float = 0.0
    risk_level: str = "healthy"  # healthy, at_risk, critical

    # Metadata
    calculated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self):
        if self.health_score == 0.0:
            self.health_score = self._calculate()
        self.risk_level = self._risk_level()

    def _calculate(self) -> float:
        raw = (
            self.login_frequency * WEIGHTS["login_frequency"]
            + self.feature_adoption * WEIGHTS["feature_adoption"]
            + self.recency * WEIGHTS["recency"]
            + self.error_rate * WEIGHTS["error_rate"]
            + min(self.support_tickets, 5) * WEIGHTS["support_tickets"]
        )
        return max(0.0, min(100.0, raw))

    def _risk_level(self) -> str:
        if self.health_score < RISK_THRESHOLD_ESCALATION:
            return "critical"
        if self.health_score < RISK_THRESHOLD_CS_ALERT:
            return "at_risk"
        return "healthy"


# ── Metric collectors ───────────────────────────────────────────────────────

def _normalise_login_frequency(logins_per_user_per_week: float) -> float:
    """Normalise: 5+ = 1.0, 0 = 0.0"""
    return min(1.0, logins_per_user_per_week / 5.0)


def _normalise_recency(days_since_last_login: int) -> float:
    """1.0 = today, 0.0 = 30+ days"""
    return max(0.0, 1.0 - days_since_last_login / 30.0)


def _normalise_feature_adoption(adoption_pct: float) -> float:
    """Already 0-1, just clamp."""
    return max(0.0, min(1.0, adoption_pct))


def compute_health_score(
    tenant_id: str,
    tenant_name: str,
    plan_name: str,
    persona_slug: str,
    logins_per_user_per_week: float = 0,
    error_rate: float = 0,
    support_tickets: int = 0,
    feature_adoption: float = 0,
    days_since_last_login: int = 30,
) -> TenantHealthSnapshot:
    """Compute a tenant health score from raw metrics."""
    return TenantHealthSnapshot(
        tenant_id=tenant_id,
        tenant_name=tenant_name,
        plan_name=plan_name,
        persona_slug=persona_slug,
        login_frequency=_normalise_login_frequency(logins_per_user_per_week),
        error_rate=error_rate,
        support_tickets=support_tickets,
        feature_adoption=_normalise_feature_adoption(feature_adoption),
        recency=_normalise_recency(days_since_last_login),
        days_since_last_login=days_since_last_login,
    )


# ── Batch health report ─────────────────────────────────────────────────────

@dataclass
class HealthReport:
    """Weekly aggregated health report for all tenants."""

    generated_at: datetime
    total_tenants: int
    healthy_count: int
    at_risk_count: int
    critical_count: int
    average_score: float
    tenants: list[TenantHealthSnapshot] = field(default_factory=list)

    @property
    def at_risk_pct(self) -> float:
        if self.total_tenants == 0:
            return 0.0
        return (self.at_risk_count + self.critical_count) / self.total_tenants * 100

    def to_summary(self) -> str:
        return (
            f"Tenant Health Report — {self.generated_at.date()}\n"
            f"  Total: {self.total_tenants}\n"
            f"  Healthy: {self.healthy_count}\n"
            f"  At-risk: {self.at_risk_count} ({self.at_risk_pct:.1f}%)\n"
            f"  Critical: {self.critical_count}\n"
            f"  Average score: {self.average_score:.1f}/100"
        )
