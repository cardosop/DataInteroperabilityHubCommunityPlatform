"""
Tests for init_tenant_configs management command.

GAP-1.2.5: Tests for management command to initialize tenant configs.
"""

import pytest
from django.test import TestCase

pytestmark = pytest.mark.django_db(transaction=True)


class InitTenantConfigsCommandTest(TestCase):
    """Test init_tenant_configs management command"""
