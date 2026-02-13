"""
Test settings for Phase 11 workflow tests.
Uses a fixed test database to avoid migration timeouts.
"""

from hub.settings import *

# Override database name for tests
DATABASES["default"]["NAME"] = "hub_test_phase11"
if "TEST" not in DATABASES["default"]:
    DATABASES["default"]["TEST"] = {}
DATABASES["default"]["TEST"]["NAME"] = "hub_test_phase11"
