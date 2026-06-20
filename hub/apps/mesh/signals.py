"""
Mesh Signals — Phase 91.13

post_save / post_delete handlers that invalidate mesh-related caches.

Best-effort: failures logged at WARNING, never propagate.
"""

import logging

from django.core.cache import cache
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

logger = logging.getLogger(__name__)

# Cache key patterns used by mesh services
MESH_DOMAIN_CACHE_PREFIX = "mesh:domain"
MESH_TOPOLOGY_CACHE_PREFIX = "mesh:topology"


@receiver(post_save, sender="mesh.DataMeshDomain")
def invalidate_mesh_cache_on_save(sender, instance, **kwargs):
    """Invalidate mesh domain and topology caches on save."""
    try:
        domain_id = str(instance.pk)
        tenant_id = str(instance.tenant_id) if instance.tenant_id else None

        # Invalidate domain detail cache
        cache.delete(f"{MESH_DOMAIN_CACHE_PREFIX}:{domain_id}")

        # Invalidate topology cache for the tenant
        if tenant_id:
            cache.delete(f"{MESH_TOPOLOGY_CACHE_PREFIX}:{tenant_id}")

        logger.debug(
            "mesh_cache_invalidated_on_save domain_id=%s",
            domain_id,
        )
    except Exception as exc:
        logger.warning(
            "mesh_cache_invalidation_failed domain_id=%s error=%s",
            instance.pk,
            exc,
        )


@receiver(post_delete, sender="mesh.DataMeshDomain")
def invalidate_mesh_cache_on_delete(sender, instance, **kwargs):
    """Invalidate mesh domain and topology caches on delete."""
    try:
        domain_id = str(instance.pk)
        tenant_id = str(instance.tenant_id) if instance.tenant_id else None

        cache.delete(f"{MESH_DOMAIN_CACHE_PREFIX}:{domain_id}")
        if tenant_id:
            cache.delete(f"{MESH_TOPOLOGY_CACHE_PREFIX}:{tenant_id}")

        logger.debug(
            "mesh_cache_invalidated_on_delete domain_id=%s",
            domain_id,
        )
    except Exception as exc:
        logger.warning(
            "mesh_cache_invalidation_failed domain_id=%s error=%s",
            instance.pk,
            exc,
        )
