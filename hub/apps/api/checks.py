"""
Django system checks (registered with ``deploy=True``) that surface
misconfigurations during the post-deploy smoke step
``python manage.py check --deploy --fail-level WARNING``.

These are NOT run on every `manage.py migrate` / `collectstatic` — those
happen at image-build time, when env vars like `MVP_MODE` and
`E2E_TEST_SECRET` may be absent. ``deploy=True`` scopes the checks to
explicit `--deploy` invocations (post-deploy health probe).
"""
from __future__ import annotations

from typing import Any

from django.core.checks import Error, Tags, register


@register(Tags.security, deploy=True)
def check_mvp_mode_on_staging(app_configs: Any, **kwargs: Any) -> list[Error]:
    """hub.E001 — staging must run with MVP_MODE=True.

    Without MVP_MODE=True on staging, every non-MVP API prefix (mesh/,
    virtualization/, ai/, baas/, ml/, ...) becomes reachable on the public
    staging URL, defeating the gate. The MvpModeApiGateMiddleware reads
    settings.MVP_MODE per request, so an incorrectly-false value is a
    silent unit-un-gating.
    """
    from django.conf import settings

    env = getattr(settings, "ENVIRONMENT", "")
    mvp = getattr(settings, "MVP_MODE", None)
    if env == "staging" and mvp is not True:
        return [
            Error(
                "MVP_MODE must be True on staging.",
                hint=(
                    "Set MVP_MODE=true via Helm values (api.env.MVP_MODE) or the "
                    "container env var. Deploy pipeline forces this via "
                    "MVP_HELM_SETS in .github/workflows/deploy.yml."
                ),
                id="hub.E001",
            )
        ]
    return []


@register(Tags.security, deploy=True)
def check_e2e_secret_when_endpoints_mounted(
    app_configs: Any, **kwargs: Any
) -> list[Error]:
    """hub.E002 — E2E_TEST_SECRET must be set where ensure_e2e_* endpoints exist.

    The ``@require_e2e_token`` decorator returns 404 when the secret is
    empty (failsafe). This check surfaces the misconfiguration during
    deploy so operators don't discover it via silent E2E failures.

    Development intentionally skips this check: local developers should
    be able to run the stack without provisioning a secret.
    """
    from django.conf import settings

    env = getattr(settings, "ENVIRONMENT", "")
    secret = getattr(settings, "E2E_TEST_SECRET", "")
    if env in ("staging", "test", "production") and not secret:
        return [
            Error(
                "E2E_TEST_SECRET is empty but ensure_e2e_* endpoints are mounted.",
                hint=(
                    "Set E2E_TEST_SECRET from AWS Secrets Manager via "
                    "ExternalSecrets (staging/hub/e2e). See docs/e2e-setup.md."
                ),
                id="hub.E002",
            )
        ]
    return []
