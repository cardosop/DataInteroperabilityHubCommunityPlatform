"""ClamAV startup gate smoke tests (Phase 260.0.17)."""

import pytest
from django.test import SimpleTestCase
from django.test.utils import override_settings

from hub.apps.core.clamav_startup_check import run_clamav_version_compat_check


class ClamavStartupCheckTests(SimpleTestCase):
    @override_settings(
        CLAMAV_ENABLED=False,
        CLAMAV_STARTUP_VERSION_CHECK_ENABLED=True,
    )
    @pytest.mark.unit
    def test_skips_when_clamav_disabled(self) -> None:
        run_clamav_version_compat_check()  # should not raise
