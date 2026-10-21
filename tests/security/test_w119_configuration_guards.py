"""W11.9 (oss-release-remediation) — default-secure configuration
assertions (ASVS V14, register row 13) + CORS/ALLOWED_HOSTS (V13.5).

REAL subprocess boots of the production settings (the W1.18 harness —
no replica logic, no mocks): the guards under test must fail closed
when the secure value is violated and boot when it holds.  Plus the
request-level Host-header validation (Django's DisallowedHost path —
previously untested anywhere) and the production CORS checker.

The base env is imported from ``test_production_secrets.py`` (the
canonical production-shaped env that satisfies every guard except the
one under test).
"""

import subprocess
import sys
from pathlib import Path

import pytest
from django.core.exceptions import DisallowedHost

from tests.security.test_production_secrets import _run_django_with_env

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

pytestmark = pytest.mark.security


def _base_env(**overrides):
    from tests.security.test_production_secrets import _production_base_env

    return _production_base_env(**overrides)


class TestProductionCookieSslRedirectGuard:
    """The secure-cookie + SSL-redirect production guard — REAL boots."""

    def test_production_boot_has_secure_cookies_and_redirect(self):
        code = (
            "import django; django.setup(); from django.conf import settings; "
            "assert settings.SESSION_COOKIE_SECURE is True; "
            "assert settings.CSRF_COOKIE_SECURE is True; "
            "assert settings.SECURE_SSL_REDIRECT is True; "
            "assert settings.SECURE_HSTS_SECONDS == 63072000; "
            "assert settings.SECURE_HSTS_INCLUDE_SUBDOMAINS is True"
        )
        returncode, err = _run_django_with_env(
            _base_env(), assert_code=code
        )
        assert returncode == 0, err

    def test_insecure_cookie_in_production_fails_closed(self):
        returncode, err = _run_django_with_env(
            _base_env(SESSION_COOKIE_SECURE="false")
        )
        assert returncode != 0, (
            "production must refuse SESSION_COOKIE_SECURE=false: " + err
        )
        assert "ImproperlyConfigured" in err or "cookie" in err.lower()


class TestProductionCORSGuard:
    """The production CORS guard: no localhost defaults, no empty list."""

    def test_production_without_cors_origins_fails_closed(self):
        env = _base_env()
        env.pop("CORS_ALLOWED_ORIGINS", None)
        returncode, err = _run_django_with_env(env)
        assert returncode != 0, (
            "production must refuse an empty CORS_ALLOWED_ORIGINS: " + err
        )
        assert "CORS" in err or "cors" in err.lower() or "ImproperlyConfigured" in err

    def test_production_cors_origins_are_exact(self):
        code = (
            "import django; django.setup(); from django.conf import settings; "
            "assert settings.CORS_ALLOWED_ORIGINS == ['https://example.com']; "
            "assert 'localhost' not in settings.CORS_ALLOWED_ORIGINS"
        )
        returncode, err = _run_django_with_env(_base_env(), assert_code=code)
        assert returncode == 0, err


class TestAllowedHostsValidation:
    """The Host-header validation (Django DisallowedHost).

    Django enforces ALLOWED_HOSTS inside ``HttpRequest.get_host()`` —
    the call every host-consuming path (redirects, absolute URIs,
    signature generation) makes.  The pin drives the REAL validation:
    an unknown Host header raises; a known host passes.
    """

    def test_unknown_host_header_is_rejected(self):
        from django.test import RequestFactory

        request = RequestFactory().get("/", HTTP_HOST="evil.example.com")
        with pytest.raises(DisallowedHost):
            request.get_host()

    def test_known_host_is_accepted(self):
        from django.test import RequestFactory

        request = RequestFactory().get("/", HTTP_HOST="testserver")
        assert request.get_host() == "testserver"


class TestProductionCorsChecker:
    """The production CORS wildcard checker runs clean on the tree."""

    def test_check_production_cors_exits_zero(self):
        result = subprocess.run(
            [sys.executable, "scripts/check_production_cors.py"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
        assert result.returncode == 0, result.stdout + result.stderr
