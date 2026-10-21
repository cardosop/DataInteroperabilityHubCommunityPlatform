"""
Phase 83.5 — validate_config management command tests.
"""

from io import StringIO
from unittest.mock import patch

from django.core.exceptions import ImproperlyConfigured
from django.core.management import call_command
from django.test import TestCase

# The command imports validate_all at call time, so we patch where it's used
_VALIDATE_ALL = "hub.apps.core.management.commands.validate_config.validate_all"


class ValidateConfigCommandTest(TestCase):
    @patch(_VALIDATE_ALL)
    def test_valid_config_exits_zero(self, mock_validate):
        out = StringIO()
        call_command("validate_config", stdout=out)
        mock_validate.assert_called_once()
        assert "valid" in out.getvalue().lower()

    @patch(_VALIDATE_ALL, side_effect=ImproperlyConfigured("DATABASE_URL is required"))
    def test_missing_db_exits_one(self, mock_validate):
        err = StringIO()
        with self.assertRaises(SystemExit) as ctx:
            call_command("validate_config", stderr=err)
        assert ctx.exception.code == 1

    @patch(_VALIDATE_ALL, side_effect=ImproperlyConfigured("ALLOWED_HOSTS=* in production"))
    def test_wildcard_allowed_hosts_exits_one(self, mock_validate):
        with self.assertRaises(SystemExit):
            call_command("validate_config", stderr=StringIO())

    @patch(_VALIDATE_ALL, side_effect=ImproperlyConfigured("SECRET_KEY is required"))
    def test_missing_secret_key_exits_one(self, mock_validate):
        with self.assertRaises(SystemExit):
            call_command("validate_config", stderr=StringIO())
