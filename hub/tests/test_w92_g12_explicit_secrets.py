"""W9.2 G12 — settings keys are explicit, never silently fallbacked.

Behavioral pins (real settings import in subprocesses, no mocks):

- an explicitly-EMPTY key fails closed with ``ImproperlyConfigured`` in
  EVERY environment (the pre-fix ``_DEV_SECRET_KEY`` well-known default
  meant any environment that forgot the key silently shared a public
  secret);
- all three keys set → settings imports cleanly;
- the postgres config is explicit: the pytest branch has no
  password-guessing matrix (pinned behaviorally: the resolved config
  equals the env-provided values, and ``passwords_to_try`` no longer
  exists in the source).
"""

from __future__ import annotations

import os
import subprocess
import sys

from django.test import SimpleTestCase

_REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_SETTINGS_IMPORT = (
    "import os; os.environ['DJANGO_SETTINGS_MODULE']='hub.settings';import django; django.setup()"
)

REQUIRED_KEYS = ("SECRET_KEY", "JWT_SECRET_KEY", "ENCRYPTION_KEY")


def _import_settings(env: dict[str, str]) -> subprocess.CompletedProcess:
    """Import hub.settings in a subprocess with the given env overlay."""
    full_env = dict(os.environ)
    full_env["DJANGO_SETTINGS_MODULE"] = "hub.settings"
    for key, value in env.items():
        full_env[key] = value
    return subprocess.run(
        [sys.executable, "-c", _SETTINGS_IMPORT],
        cwd=_REPO,
        env=full_env,
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )


class G12ExplicitSecretsTests(SimpleTestCase):
    """Empty keys fail closed in every environment; set keys import."""

    def test_empty_secret_key_fails_closed(self):
        result = _import_settings({**dict.fromkeys(REQUIRED_KEYS, "x"), "SECRET_KEY": ""})
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("SECRET_KEY", result.stderr)

    def test_empty_jwt_secret_key_fails_closed(self):
        result = _import_settings({**dict.fromkeys(REQUIRED_KEYS, "x"), "JWT_SECRET_KEY": ""})
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("JWT_SECRET_KEY", result.stderr)

    def test_empty_encryption_key_fails_closed(self):
        result = _import_settings({**dict.fromkeys(REQUIRED_KEYS, "x"), "ENCRYPTION_KEY": ""})
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("ENCRYPTION_KEY", result.stderr)

    def test_fail_closed_message_names_the_bootstrap_command(self):
        result = _import_settings({**dict.fromkeys(REQUIRED_KEYS, "x"), "SECRET_KEY": ""})
        self.assertIn("make dev-env", result.stderr)

    def test_explicit_keys_import_cleanly(self):
        result = _import_settings(dict.fromkeys(REQUIRED_KEYS, "explicit-test-value"))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_settings_source_has_no_dev_secret_constants(self):
        from hub import settings as settings_module

        source = (settings_module.__file__ or "").replace(".pyc", ".py")
        with open(source, encoding="utf-8") as fh:
            text = fh.read()
        for needle in (
            "_DEV_SECRET_KEY",
            "dev-secret-key-not-for-production",
            "passwords_to_try",
        ):
            self.assertNotIn(needle, text)

    def test_pytest_branch_uses_explicit_postgres_config_verbatim(self):
        """The pytest branch resolves POSTGRES_* from env verbatim — no
        probe matrix, no guessed passwords. Runs with pytest injected into
        sys.modules (so the TEST branch activates) against the REAL local
        postgres the current test run is using."""
        env = dict(os.environ)
        env.update(dict.fromkeys(REQUIRED_KEYS, "explicit-test-value"))
        probe = (
            "import os, sys;"
            "sys.modules['pytest'] = object();"
            "os.environ['DJANGO_SETTINGS_MODULE']='hub.settings';"
            "import django; django.setup();"
            "from django.conf import settings;"
            "db = settings.DATABASES['default'];"
            "print(db.get('HOST'), db.get('PORT'), db.get('NAME'),"
            " db.get('USER'), db.get('PASSWORD'))"
        )
        result = subprocess.run(
            [sys.executable, "-c", probe],
            cwd=_REPO,
            env=env,
            capture_output=True,
            text=True,
            timeout=300,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        expected = " ".join(
            str(os.environ.get(key))
            for key in (
                "POSTGRES_HOST",
                "POSTGRES_PORT",
                "POSTGRES_DB",
                "POSTGRES_USER",
                "POSTGRES_PASSWORD",
            )
        )
        self.assertIn(expected, result.stdout)
