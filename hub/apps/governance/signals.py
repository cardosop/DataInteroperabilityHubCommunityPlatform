"""
Governance Signals

Signals for ABAC policy cache invalidation.
"""
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from .models import AccessPolicy, FieldAccessPolicy
from .abac import ABACEngine


@receiver(post_save, sender=AccessPolicy)
def invalidate_policy_cache_on_save(sender, instance, **kwargs):
    """Invalidate policy cache when policy is saved"""
    if instance.tenant_id:
        # Invalidate all caches for this tenant
        ABACEngine.invalidate_policy_cache(str(instance.tenant_id))
        
        # Also invalidate specific resource caches if applicable
        if instance.asset_id:
            ABACEngine.invalidate_policy_cache(
                str(instance.tenant_id),
                "ASSET",
                str(instance.asset_id)
            )
        if instance.dataset_id:
            ABACEngine.invalidate_policy_cache(
                str(instance.tenant_id),
                "DATASET",
                str(instance.dataset_id)
            )


@receiver(post_delete, sender=AccessPolicy)
def invalidate_policy_cache_on_delete(sender, instance, **kwargs):
    """Invalidate policy cache when policy is deleted"""
    if instance.tenant_id:
        ABACEngine.invalidate_policy_cache(str(instance.tenant_id))
        
        if instance.asset_id:
            ABACEngine.invalidate_policy_cache(
                str(instance.tenant_id),
                "ASSET",
                str(instance.asset_id)
            )
        if instance.dataset_id:
            ABACEngine.invalidate_policy_cache(
                str(instance.tenant_id),
                "DATASET",
                str(instance.dataset_id)
            )


@receiver(post_save, sender=FieldAccessPolicy)
@receiver(post_delete, sender=FieldAccessPolicy)
def invalidate_field_policy_cache(sender, instance, **kwargs):
    """Invalidate policy cache when field policy changes"""
    if instance.tenant_id and instance.dataset_id:
        ABACEngine.invalidate_policy_cache(
            str(instance.tenant_id),
            "DATASET",
            str(instance.dataset_id)
        )

