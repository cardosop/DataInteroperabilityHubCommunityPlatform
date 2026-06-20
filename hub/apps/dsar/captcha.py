"""hCaptcha verification for public DSAR ingress (Phase 232.2.10)."""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request

from django.conf import settings


def verify_hcaptcha(*, response_token: str, remote_ip: str | None) -> bool:
    """
    POST to hCaptcha siteverify. Returns False on network/parse errors or
    unsuccessful verification.
    """
    # Dev/test: skip captcha when DSAR_SKIP_HCAPTCHA_VERIFICATION is set,
    # regardless of whether a secret key is configured.
    if getattr(settings, "DSAR_SKIP_HCAPTCHA_VERIFICATION", False):
        return True

    secret = getattr(settings, "HCAPTCHA_SECRET_KEY", "") or ""
    if not secret.strip():
        return False

    data = urllib.parse.urlencode(
        {
            "secret": secret,
            "response": response_token,
            **({"remoteip": remote_ip} if remote_ip else {}),
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        "https://hcaptcha.com/siteverify",
        data=data,
        method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, json.JSONDecodeError, OSError):
        return False
    return body.get("success") is True
