from __future__ import annotations

from typing import Any

from django.db.models import Prefetch

from hub.apps.assets.models import Asset
from hub.apps.governance.models import RetentionPolicy
from hub.apps.ropa.cache import current_cache_version


def _asset_row_dict(asset: Asset) -> dict[str, Any]:
    pref = getattr(asset, "_prefetched_processing_purposes", None)
    purpose_iter = pref if pref is not None else asset.processing_purposes.all()
    purposes = [{"id": str(p.id), "key": p.key, "name": p.name} for p in purpose_iter]
    return {
        "id": str(asset.id),
        "key": asset.key,
        "name": asset.name,
        "domain": asset.domain,
        "status": asset.status,
        "processing_purposes": purposes,
        "categories_of_subjects": asset.categories_of_subjects or [],
        "recipient_categories": asset.recipient_categories or [],
    }


def _retention_for_assets(tenant_id: str, asset_ids: list[str]) -> dict[str, list[dict[str, Any]]]:
    if not asset_ids:
        return {}
    qs = RetentionPolicy.objects.filter(tenant_id=tenant_id, asset_id__in=asset_ids)
    out: dict[str, list[dict[str, Any]]] = {}
    for rp in qs:
        aid = str(rp.asset_id)
        out.setdefault(aid, []).append(
            {
                "policy_id": str(rp.id),
                "name": rp.name,
                "policy_type": rp.policy_type,
                "retention_period_days": rp.retention_period_days,
                "action": rp.action,
                "legal_hold": rp.legal_hold,
            }
        )
    return out


def build_ropa_payload(*, tenant_id: str, regulation: str) -> dict[str, Any]:
    """Walk tenant assets + linked metadata; return structured RoPA document + gaps."""
    reg = (regulation or "GDPR").upper()
    cv = current_cache_version(str(tenant_id))

    qs = (
        Asset.objects.filter(tenant_id=tenant_id)
        .prefetch_related(
            Prefetch(
                "processing_purposes",
                to_attr="_prefetched_processing_purposes",
            )
        )
        .order_by("key")
    )
    assets = list(qs)
    asset_ids = [str(a.id) for a in assets]
    ret_map = _retention_for_assets(str(tenant_id), asset_ids)
    max_updated = None
    for a in assets:
        if max_updated is None or a.updated_at > max_updated:
            max_updated = a.updated_at

    rows: list[dict[str, Any]] = []
    gaps: list[dict[str, Any]] = []
    for a in assets:
        row = _asset_row_dict(a)
        row["retention_policies"] = ret_map.get(str(a.id), [])
        rows.append(row)
        asset_detail_path = f"/assets/{a.id}"
        if not row["processing_purposes"]:
            gaps.append(
                {
                    "asset_id": str(a.id),
                    "asset_key": a.key,
                    "code": "MISSING_PROCESSING_PURPOSES",
                    "fix_path": "/governance/consent/purposes",
                    "message": "Link at least one processing purpose (consent purpose) for RoPA completeness.",
                }
            )
        if not row["categories_of_subjects"]:
            gaps.append(
                {
                    "asset_id": str(a.id),
                    "asset_key": a.key,
                    "code": "MISSING_SUBJECT_CATEGORIES",
                    "fix_path": asset_detail_path,
                    "message": "Populate categories_of_subjects (JSON) on the asset.",
                }
            )
        if not row["recipient_categories"]:
            gaps.append(
                {
                    "asset_id": str(a.id),
                    "asset_key": a.key,
                    "code": "MISSING_RECIPIENT_CATEGORIES",
                    "fix_path": asset_detail_path,
                    "message": "Populate recipient_categories (JSON) on the asset.",
                }
            )
        if reg == "GDPR" and not row["retention_policies"]:
            gaps.append(
                {
                    "asset_id": str(a.id),
                    "asset_key": a.key,
                    "code": "MISSING_RETENTION_POLICY",
                    "fix_path": "/governance/retention",
                    "message": "Attach a retention policy to this asset for Article 30 completeness.",
                }
            )

    meta = {
        "regulation": reg,
        "tenant_id": str(tenant_id),
        "cache_version": cv,
        "asset_count": len(rows),
        "aggregates": {
            "assets_max_updated_at": max_updated.isoformat() if max_updated else None,
        },
    }
    return {
        "meta": meta,
        "activities": rows,
        "gaps": gaps,
    }


def estimate_json_bytes(payload: dict[str, Any]) -> int:
    import json

    return len(json.dumps(payload, separators=(",", ":"), default=str).encode("utf-8"))
