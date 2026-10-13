"""W1.18 (oss-release-remediation) — .env.production.template contract pins.

The template is the deployment source of truth. Three W1.18 findings are
pinned here (host-side, real file reads — no Django/DB required):

  1. ``SECURE_SSL_REDIRECT`` — the template shipped ``False`` with a
     "keep False here" comment while the production settings guard REQUIRES
     True (boot crash for any deployer following the template).
  2. ``TRUST_X_FORWARDED_PROTO`` — absent from the template, so the
     Traefik edge's ``X-Forwarded-Proto: https`` was never honoured:
     ``is_secure()`` stays False behind TLS, HSTS/secure-cookie emission
     breaks, and SECURE_SSL_REDIRECT loops.
  3. Cookie domains — no hardcoded vendor domain (``.meshant.com``) may
     reappear; the domain knobs are env-driven with guidance in the
     template.

Run host-side:
    venv/bin/python -m pytest scripts/tests/test_production_env_template.py -q
"""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
ENV_PRODUCTION_TEMPLATE = PROJECT_ROOT / ".env.production.template"


def _read_template() -> str:
    assert ENV_PRODUCTION_TEMPLATE.exists(), (
        ".env.production.template not found"
    )
    return ENV_PRODUCTION_TEMPLATE.read_text()


def _key_value(template: str, key: str) -> str | None:
    """Return the raw value of ``KEY=value`` (comments stripped), or None."""
    for line in template.splitlines():
        stripped = line.strip()
        if stripped.startswith("#") or "=" not in stripped:
            continue
        k, _, v = stripped.partition("=")
        if k.strip() == key:
            return v.strip()
    return None


class TestSecureSslRedirectTemplate:
    """The template must agree with the production settings guard (W1.18)."""

    def test_template_sets_secure_ssl_redirect_true(self):
        template = _read_template()
        assert _key_value(template, "SECURE_SSL_REDIRECT") == "True", (
            "SECURE_SSL_REDIRECT must be True in the template — the production "
            "settings guard raises ImproperlyConfigured otherwise."
        )

    def test_template_trusts_forwarded_proto(self):
        template = _read_template()
        assert _key_value(template, "TRUST_X_FORWARDED_PROTO") == "True", (
            "TRUST_X_FORWARDED_PROTO must be True — the Traefik edge terminates "
            "TLS and sets X-Forwarded-Proto; without it is_secure() is False "
            "behind TLS and SECURE_SSL_REDIRECT would loop."
        )

    def test_no_stale_keep_false_comment(self):
        template = _read_template()
        assert "keep false here" not in template.lower(), (
            "The stale 'Traefik handles TLS termination; keep False here' "
            "comment contradicts the production guard."
        )


class TestCookieDomainTemplate:
    """Cookie-domain knobs are documented, env-driven, vendor-neutral (W1.18)."""

    def test_no_hardcoded_meshant_domain(self):
        template = _read_template()
        assert ".meshant.com" not in template, (
            "No vendor-specific cookie domain may be baked into the template."
        )

    def test_cookie_domain_entries_present_with_guidance(self):
        template = _read_template()
        for key in ("SESSION_COOKIE_DOMAIN", "CSRF_COOKIE_DOMAIN"):
            assert _key_value(template, key) is not None, (
                f"{key} must be documented in the template (blank default = "
                "host-only cookies)."
            )
        assert "host-only" in template.lower(), (
            "The template must explain the blank default (host-only cookies) "
            "and when to set an explicit domain."
        )

