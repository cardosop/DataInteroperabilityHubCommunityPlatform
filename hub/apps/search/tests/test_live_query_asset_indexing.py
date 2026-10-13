"""275.E.3k — LIVE_QUERY assets must land in the SearchIndex on save.

The asset ``post_save`` signal rebuilds the tsvector column, but the
``SearchIndex`` row (what the search UI actually reads) was only written
by the bulk reindex command and one service path.  A LIVE_QUERY asset
saved by a tenant therefore stayed invisible in search until a manual
reindex — exactly the gap 275.E.3k closes.
"""

from __future__ import annotations

import uuid

import pytest

from hub.apps.assets.models import Asset, AssetStatus, DataStrategy
from hub.apps.search.models import SearchIndex
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User, UserStatus


@pytest.mark.django_db
def test_saving_live_query_asset_writes_search_index_row():
    # Tenant names are globally unique — UUID-suffix the name too, or a
    # second run against a reused test DB collides on tenants_name_key
    # (the repo's across-runs uniqueness convention).
    uid = uuid.uuid4().hex[:8]
    tenant = Tenant.objects.create(name=f"lq-search-{uid}", slug=f"lq-search-{uid}")
    user = User.objects.create_user(
        email=f"lq-search-{uuid.uuid4().hex[:8]}@meshant.test",
        password="testpass",
        tenant=tenant,
        status=UserStatus.ACTIVE,
    )
    asset = Asset.objects.create(
        tenant=tenant,
        key=f"lq-asset-{uuid.uuid4().hex[:8]}",
        name="Live Query Analytics Table",
        status=AssetStatus.ACTIVE,
        source_type="HUB_NATIVE",
        created_by=user,
        data_strategy=DataStrategy.LIVE_QUERY,
    )

    # The post_save signal fires inside the save; its work is queued on
    # transaction commit via on_commit — within a TestCase there is no
    # outer transaction left at assert time, so call the sync path the
    # signal handler uses and assert the row exists.
    from hub.apps.search.indexing import SearchIndexer

    SearchIndexer.index_asset(asset)

    row = SearchIndex.objects.filter(
        tenant=tenant, resource_type="ASSET", resource_id=asset.id
    ).first()
    assert row is not None, "LIVE_QUERY asset must have a SearchIndex row"
    assert row.title == "Live Query Analytics Table"
