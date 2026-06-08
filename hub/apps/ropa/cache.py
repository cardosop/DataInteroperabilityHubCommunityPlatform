from __future__ import annotations
from django.core.cache import cache

PREVIEW_CACHE_TTL_SECONDS = 86400  # 24 hours

_VER = "ropa:cv:{tenant_id}"


def current_cache_version(tenant_id: str) -> int:
    return int(cache.get(_VER.format(tenant_id=tenant_id)) or 0)


def bump_cache_version(tenant_id: str) -> None:
    key = _VER.format(tenant_id=tenant_id)
    n = int(cache.get(key) or 0) + 1
    cache.set(key, n, timeout=None)


def preview_cache_key(tenant_id: str, regulation: str, cache_version: int) -> str:
    reg = (regulation or "GDPR").upper()
    return f"ropa:pv:{tenant_id}:{reg}:{cache_version}"


def get_cached_preview(tenant_id: str, regulation: str, cache_version: int):
    return cache.get(preview_cache_key(tenant_id, regulation, cache_version))


def set_cached_preview(tenant_id: str, regulation: str, cache_version: int, payload) -> None:
    cache.set(
        preview_cache_key(tenant_id, regulation, cache_version),
        payload,
        timeout=PREVIEW_CACHE_TTL_SECONDS,
    )
