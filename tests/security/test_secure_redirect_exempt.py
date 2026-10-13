"""W1.18 (oss-release-remediation) — SECURE_SSL_REDIRECT health-path exempt.

The production compose healthcheck is ``curl -f http://localhost:8000/health``
— an internal HTTP request that bypasses the Traefik edge, so it carries no
``X-Forwarded-Proto: https`` header. Under SECURE_SSL_REDIRECT=True (required
by the production settings guard) Django's SecurityMiddleware would 301 every
healthcheck and the replicas would never report healthy.

These pins run the REAL SecurityMiddleware end-to-end: the health paths are
never redirected (the contract is redirect-freedom — the /health/ payload
itself legitimately reports non-200 when a dependency is degraded, e.g.
in-container), while non-exempt paths under the same settings redirect to
https (control — proves the redirect itself is live, not globally disabled).
"""

from django.test import Client, override_settings


class TestSecureRedirectExempt:
    """Health paths must stay reachable over plain internal HTTP."""

    def test_health_paths_exempt_from_ssl_redirect(self):
        client = Client()
        with override_settings(
            SECURE_SSL_REDIRECT=True,
            SECURE_REDIRECT_EXEMPT=[r"^health"],
        ):
            for path in ("/health/", "/health/live/"):
                resp = client.get(path)
                assert resp.status_code not in (301, 302), (
                    f"{path} must not be redirected under SECURE_SSL_REDIRECT: "
                    f"got {resp.status_code}"
                )
                assert (
                    "Location" not in resp
                ), f"{path} must not carry a redirect Location"

    def test_liveness_stays_200_under_redirect_on(self):
        client = Client()
        with override_settings(
            SECURE_SSL_REDIRECT=True,
            SECURE_REDIRECT_EXEMPT=[r"^health"],
        ):
            resp = client.get("/health/live/")
            assert resp.status_code == 200

    def test_non_exempt_path_still_redirects_to_https(self):
        client = Client()
        with override_settings(
            SECURE_SSL_REDIRECT=True,
            SECURE_REDIRECT_EXEMPT=[r"^health"],
        ):
            resp = client.get("/not-a-health-path/")
            assert resp.status_code in (301, 302), (
                f"Non-exempt path must redirect under SECURE_SSL_REDIRECT, "
                f"got {resp.status_code}"
            )
            assert resp["Location"].startswith(
                "https://"
            ), "Redirect Location must be https"

    def test_redirect_inert_when_disabled(self):
        client = Client()
        with override_settings(
            SECURE_SSL_REDIRECT=False, SECURE_REDIRECT_EXEMPT=[]
        ):
            resp = client.get("/health/live/")
            assert resp.status_code == 200
