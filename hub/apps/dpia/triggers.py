"""High-risk processing indicators that trigger DPIA obligations (GDPR Art 35 style)."""

from __future__ import annotations
from hub.apps.assets.models import Asset

# Normalised substring hints — not a legal determination; drives workflow flags only.
_SUBJECT_CATEGORY_MARKERS = (
    "health",
    "biometric",
    "genetic",
    "criminal",
    "children",
    "child",
    "minor",
    "racial",
    "ethnic",
    "political",
    "religious",
    "sexual orientation",
    "trade union",
)

_PURPOSE_MARKERS = (
    "profiling",
    "automated decision",
    "systematic monitoring",
    "large scale",
    "vulnerable",
)


def _text_haystack(asset: Asset) -> str:
    parts = [
        str(asset.name or ""),
        str(asset.description or ""),
        str(asset.domain or ""),
    ]
    cats = asset.categories_of_subjects or []
    parts.extend(str(c) for c in cats)
    return " ".join(parts).lower()


def asset_requires_dpia(asset: Asset) -> bool:
    """
    Return True when inventory metadata suggests a DPIA should exist for this asset.

    Uses coarse keyword / list heuristics on subject categories, free text, and
    linked processing-purpose keys/names.
    """
    hay = _text_haystack(asset)
    for m in _SUBJECT_CATEGORY_MARKERS:
        if m in hay:
            return True

    pref = getattr(asset, "processing_purposes", None)
    if pref is None:
        return False
    for p in pref.all():
        blob = f"{p.key or ''} {p.name or ''}".lower()
        for m in _PURPOSE_MARKERS:
            if m in blob:
                return True
    return False
