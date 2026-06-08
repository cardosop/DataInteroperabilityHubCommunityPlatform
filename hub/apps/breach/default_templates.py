"""Default breach notification templates (Phase 232.3.8 / .9).

Placeholders use ``string.Template`` syntax: ``$incident_title``,
``$incident_summary``, ``$authority_name``, ``$regime``, ``$deadline_utc``.
"""

from __future__ import annotations
# regime -> {version, subject_template, body_template}
PLATFORM_BREACH_TEMPLATES: dict[str, dict[str, str | int]] = {
    "GDPR": {
        "version": 1,
        "subject_template": "Personal data breach — $incident_title ($regime)",
        "body_template": (
            "Incident: $incident_title\n"
            "Summary: $incident_summary\n"
            "Supervisory authority: $authority_name\n"
            "Regime: $regime\n"
            "Statutory supervisory notification deadline (UTC): $deadline_utc\n"
        ),
    },
    "UK_GDPR": {
        "version": 1,
        "subject_template": "Personal data breach notification — $incident_title (UK GDPR)",
        "body_template": (
            "Incident: $incident_title\n"
            "Summary: $incident_summary\n"
            "Supervisory authority: $authority_name\n"
            "Regime: $regime\n"
            "Deadline (UTC): $deadline_utc\n"
        ),
    },
    "LGPD": {
        "version": 1,
        "subject_template": "Incidente de dados pessoais — $incident_title (LGPD)",
        "body_template": (
            "Incidente: $incident_title\n"
            "Resumo: $incident_summary\n"
            "Autoridade: $authority_name\n"
            "Regime: $regime\n"
            "Prazo (UTC): $deadline_utc\n"
        ),
    },
    "CCPA": {
        "version": 1,
        "subject_template": "Security incident — $incident_title (CCPA / CPRA context)",
        "body_template": (
            "Incident: $incident_title\n"
            "Summary: $incident_summary\n"
            "Regime: $regime\n"
            "Planning deadline (UTC): $deadline_utc\n"
            "(California AG notification requirements depend on facts; this is a draft scaffold.)\n"
        ),
    },
}
DEFAULT_BREACH_REGIME = "GDPR"
