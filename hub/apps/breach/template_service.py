"""Render breach notification copy with tenant overrides (Phase 232.3.8)."""

from __future__ import annotations

from string import Template

from hub.apps.breach.default_templates import DEFAULT_BREACH_REGIME, PLATFORM_BREACH_TEMPLATES
from hub.apps.breach.models import BreachIncident, BreachNotification, BreachTenantTemplateOverride
from hub.apps.regulation_policies.registry import RegulationAuthority, get_authority_by_id


def _platform_row(regime: str) -> dict[str, str | int]:
    key = regime.upper().strip()
    row = PLATFORM_BREACH_TEMPLATES.get(key)
    if row is None:
        row = PLATFORM_BREACH_TEMPLATES[DEFAULT_BREACH_REGIME]
    return row


def merged_template_for_tenant(*, tenant_id, regime: str) -> tuple[int, str, str]:
    key = regime.upper().strip()
    base = _platform_row(key)
    ver = int(base["version"])
    subj = str(base["subject_template"])
    body = str(base["body_template"])
    ov = (
        BreachTenantTemplateOverride.objects.filter(tenant_id=tenant_id, regime=key)
        .only("subject_template", "body_template", "template_version")
        .first()
    )
    if ov:
        ver = int(ov.template_version)
        if ov.subject_template.strip():
            subj = ov.subject_template
        if ov.body_template.strip():
            body = ov.body_template
    return ver, subj, body


def render_notification_copy(
    *,
    notification: BreachNotification,
    incident: BreachIncident,
    authority: RegulationAuthority | None,
) -> tuple[int, str, str]:
    ver, subj_tpl, body_tpl = merged_template_for_tenant(
        tenant_id=incident.tenant_id,
        regime=notification.regime,
    )
    deadline = notification.statutory_due_at_utc.isoformat()
    mapping = {
        "incident_title": incident.title,
        "incident_summary": incident.summary or "",
        "authority_name": authority.name if authority else "",
        "regime": notification.regime,
        "deadline_utc": deadline,
    }
    subject = Template(subj_tpl).safe_substitute(mapping)
    body = Template(body_tpl).safe_substitute(mapping)
    return ver, subject, body


def render_for_authority_id(
    notification: BreachNotification,
    incident: BreachIncident,
) -> tuple[int, str, str]:
    auth = None
    if notification.supervisory_authority_id:
        auth = get_authority_by_id(notification.supervisory_authority_id)
    return render_notification_copy(notification=notification, incident=incident, authority=auth)
