"""Tests for DataMovementConfig model."""

import pytest

from hub.data_movement.models import DataMovementConfig

pytestmark = pytest.mark.django_db(transaction=True)


class TestDataMovementConfig:
    def test_create_config_for_tenant(self, tenant):
        """Config can be created with defaults."""
        config = DataMovementConfig.objects.create(tenant=tenant)
        assert config.dlt_dev_mode is False
        assert config.max_parallel_pipelines == 5
        assert config.tenant == tenant

    def test_tenant_cascade_delete(self, tenant):
        """Config is deleted when tenant is deleted."""
        config = DataMovementConfig.objects.create(tenant=tenant)
        assert DataMovementConfig.objects.filter(tenant=tenant).exists()
        tenant.delete()
        # After cascade delete, the config row should be gone.
        assert not DataMovementConfig.objects.filter(pk=config.pk).exists()

    def test_one_config_per_tenant(self, tenant):
        """Only one config per tenant (OneToOneField)."""
        DataMovementConfig.objects.create(tenant=tenant)
        with pytest.raises(Exception):
            DataMovementConfig.objects.create(tenant=tenant)

    def test_dev_mode_default_false(self, tenant):
        """dlt_dev_mode defaults to False."""
        config = DataMovementConfig.objects.create(tenant=tenant)
        config.refresh_from_db()
        assert config.dlt_dev_mode is False

    def test_max_parallel_pipelines_default(self, tenant):
        """max_parallel_pipelines defaults to 5."""
        config = DataMovementConfig.objects.create(tenant=tenant)
        assert config.max_parallel_pipelines == 5
        config.max_parallel_pipelines = 10
        config.save()
        config.refresh_from_db()
        assert config.max_parallel_pipelines == 10
