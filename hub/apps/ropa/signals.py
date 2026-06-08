"""Invalidate RoPA preview cache when inventory inputs change."""

from django.db.models.signals import m2m_changed, post_delete, post_save
from django.dispatch import receiver

from hub.apps.assets.models import Asset
from hub.apps.consent.models import ConsentPurpose
from hub.apps.governance.models import RetentionPolicy
from hub.apps.ropa.cache import bump_cache_version


@receiver(post_save, sender=Asset)
def _invalidate_ro_cache_asset(sender, instance: Asset, **kwargs):
    bump_cache_version(str(instance.tenant_id))


@receiver(m2m_changed, sender=Asset.processing_purposes.through)
def _invalidate_ro_cache_asset_purposes(sender, instance, **kwargs):
    if isinstance(instance, Asset):
        bump_cache_version(str(instance.tenant_id))


@receiver(post_save, sender=ConsentPurpose)
def _invalidate_ro_cache_purpose(sender, instance: ConsentPurpose, **kwargs):
    bump_cache_version(str(instance.tenant_id))


@receiver([post_save, post_delete], sender=RetentionPolicy)
def _invalidate_ro_cache_retention(sender, instance: RetentionPolicy, **kwargs):
    bump_cache_version(str(instance.tenant_id))
