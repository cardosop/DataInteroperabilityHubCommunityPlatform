"""
Phase 277.B.065 — Password complexity, common-password deny-list, and
Have I Been Pwned k-anonymity validators.

Custom Django password validators that extend the built-in set with:

* ``PasswordComplexityValidator`` — minimum 10 characters, at least one
  uppercase letter, one lowercase letter, one digit, and one special
  character.
* ``CommonPasswordDenyListValidator`` — block a curated deny-list of
  100,000+ common passwords (extends Django's built-in ~1,000 list).
* ``HaveIBeenPwnedValidator`` — queries the Have I Been Pwned
  k-anonymity API (range-search, only first 5 chars of the SHA-1 hash
  are sent to the remote service).

All three follow the Django ``AUTH_PASSWORD_VALIDATORS`` interface so
they are automatically invoked by ``django.contrib.auth.authenticate``
and any code path that calls ``validate_password()``.
"""
from __future__ import annotations

import hashlib
import re
from pathlib import Path

from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _


# ---------------------------------------------------------------------------
# Common-password deny-list loader
# ---------------------------------------------------------------------------

_COMMON_PASSWORDS: set[str] | None = None

_COMMON_PASSWORDS_FILE = (
    Path(__file__).resolve().parent / "common_passwords.txt"
)


def _load_common_passwords() -> set[str]:
    """Load common-password deny-list from the bundled text file.

    Falls back to Django's built-in list if the file is missing.
    """
    global _COMMON_PASSWORDS
    if _COMMON_PASSWORDS is not None:
        return _COMMON_PASSWORDS

    passwords: set[str] = set()
    if _COMMON_PASSWORDS_FILE.exists():
        with open(_COMMON_PASSWORDS_FILE, encoding="utf-8") as f:
            for line in f:
                stripped = line.strip().lower()
                if stripped and not stripped.startswith("#"):
                    passwords.add(stripped)
    # Minimum baseline: Django 6.0's built-in common passwords (bundled gzip file).
    # Django 6.0 removed the ``common_passwords`` module; CommonPasswordValidator
    # now reads directly from a gzipped file shipped alongside the module.
    import gzip
    from django.contrib.auth.password_validation import CommonPasswordValidator

    _validator = CommonPasswordValidator()
    try:
        with gzip.open(
            str(_validator.DEFAULT_PASSWORD_LIST_PATH), "rt", encoding="utf-8"
        ) as _f:
            passwords.update({x.strip() for x in _f})
    except (OSError, gzip.BadGzipFile):
        pass  # File missing or corrupt; use only the custom deny-list

    _COMMON_PASSWORDS = passwords
    return _COMMON_PASSWORDS


# ---------------------------------------------------------------------------
# Validators
# ---------------------------------------------------------------------------


class PasswordComplexityValidator:
    """Require passwords to meet complexity rules.

    Rules:
    * Minimum 10 characters
    * At least one uppercase letter (A-Z)
    * At least one lowercase letter (a-z)
    * At least one digit (0-9)
    * At least one special character (punctuation / symbol)
    """

    def __init__(self, min_length: int = 10):
        self.min_length = min_length

    def validate(self, password: str, user=None):
        errors: list[str] = []

        if len(password) < self.min_length:
            errors.append(
                _(f"This password is too short. It must contain at least "
                  f"{self.min_length} characters.")
            )

        if not re.search(r"[A-Z]", password):
            errors.append(_("This password must contain at least one uppercase letter."))

        if not re.search(r"[a-z]", password):
            errors.append(_("This password must contain at least one lowercase letter."))

        if not re.search(r"[0-9]", password):
            errors.append(_("This password must contain at least one digit."))

        if not re.search(r"[^A-Za-z0-9]", password):
            errors.append(_("This password must contain at least one special character."))

        if errors:
            raise ValidationError(errors, code="password_complexity")

    def get_help_text(self):
        return _(
            f"Your password must contain at least {self.min_length} characters "
            "and include at least one uppercase letter, one lowercase letter, "
            "one digit, and one special character."
        )


class CommonPasswordDenyListValidator:
    """Reject passwords that appear in a bundled common-password list.

    The deny-list is loaded from ``hub/apps/auth/common_passwords.txt``
    (one lowercased password per line).  If the file is missing the
    validator falls back to Django's built-in 1,000-entry list.
    """

    def validate(self, password: str, user=None):
        deny_list = _load_common_passwords()
        if password.lower() in deny_list:
            raise ValidationError(
                _("This password is too common."),
                code="password_too_common",
            )

    def get_help_text(self):
        return _(
            "Your password must not be a commonly used password."
        )


class HaveIBeenPwnedValidator:
    """Check the password against the Have I Been Pwned k-anonymity range API.

    Only the **first 5 hex characters** of the SHA-1 hash are sent to
    ``api.pwnedpasswords.com``.  The service returns a list of matching
    hash suffixes; if the full hash appears in the response the password
    is rejected.

    The validator is best-effort: a network error or timeout (5 s) is
    logged but does NOT block the password.  In CI / offline
    environments the check is skipped entirely (no network = pass).
    """

    API_URL = "https://api.pwnedpasswords.com/range/{prefix}"

    def __init__(self, timeout: float = 5.0):
        self.timeout = timeout

    def validate(self, password: str, user=None):
        import logging

        logger = logging.getLogger(__name__)

        # Honour the feature flag so CI/test environments can disable the
        # external HIBP API call without mocking.  Tests that specifically
        # exercise this validator can override via @override_settings.
        from django.conf import settings as _django_settings
        if not getattr(_django_settings, "HIBP_VALIDATOR_ENABLED", True):
            return

        sha1 = hashlib.sha1(password.encode("utf-8")).hexdigest().upper()
        prefix, suffix = sha1[:5], sha1[5:]

        try:
            import urllib.request
            import urllib.error

            req = urllib.request.Request(
                self.API_URL.format(prefix=prefix),
                headers={"User-Agent": "meshant-hub-password-validator"},
            )
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                body = resp.read().decode("utf-8")
        except (urllib.error.URLError, urllib.error.HTTPError, OSError, ValueError) as exc:
            logger.warning(
                "hibp_api_unreachable",
                extra={"error": str(exc)},
            )
            return  # Best-effort — don't block on network failure
        except Exception:
            logger.exception("hibp_check_unexpected_error")
            return

        for line in body.splitlines():
            if line.strip().upper().startswith(suffix):
                count = line.split(":")[-1].strip() if ":" in line else "?"
                raise ValidationError(
                    _(
                        f"This password has appeared in {count} known data breaches "
                        f"and cannot be used."
                    ),
                    code="password_pwned",
                )

        # Password not found in breach corpus

    def get_help_text(self):
        return _(
            "Your password must not have appeared in any known data breach. "
            "We check against the Have I Been Pwned breach corpus using a "
            "privacy-preserving range API."
        )
