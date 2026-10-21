"""
Tests for hub.db_router.PrimaryReplicaRouter (Phase 17.3 / 17.10)

Covers:
  17.3  test_read_router_returns_replica  — db_for_read routes read-replica
        apps to "replica" when the alias is present in DATABASES
  17.3  test_write_router_returns_primary — db_for_write always returns
        "default" for read-replica apps
  17.10 test_read_queries_hit_replica    — router returns "replica" alias for
        Asset list query
  17.10 test_write_queries_hit_primary   — router returns "default" for writes
        regardless of app label
  Additional: no-op when replica not configured; allow_migrate blocks replica;
              allow_relation permits cross-database pairs.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_model(app_label: str) -> MagicMock:
    """Return a minimal Django model mock with the given app_label."""
    model = MagicMock()
    model._meta.app_label = app_label
    return model


def _make_obj(db: str) -> MagicMock:
    """Return a model instance mock whose _state.db is *db*."""
    obj = MagicMock()
    obj._state.db = db
    return obj


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def router():
    """Fresh PrimaryReplicaRouter instance for each test."""
    from hub.db_router import PrimaryReplicaRouter

    return PrimaryReplicaRouter()


@pytest.fixture
def with_replica(settings):
    """Extend settings.DATABASES to include a 'replica' alias."""
    import warnings

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        settings.DATABASES = dict(
            settings.DATABASES,
            replica={"ENGINE": "django.db.backends.postgresql"},
        )


@pytest.fixture
def without_replica(settings):
    """Ensure 'replica' is absent from settings.DATABASES."""
    import warnings

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        dbs = {k: v for k, v in settings.DATABASES.items() if k != "replica"}
        settings.DATABASES = dbs


# ---------------------------------------------------------------------------
# 17.3  db_for_read — returns "replica" for read-replica apps
# ---------------------------------------------------------------------------


class TestReadRouterReturnsReplica:
    """db_for_read must return 'replica' for all read-replica app labels."""

    @pytest.mark.parametrize("app_label", ["assets", "contracts", "marketplace", "search"])
    def test_read_router_returns_replica(self, router, with_replica, app_label):
        model = _make_model(app_label)
        result = router.db_for_read(model)
        assert result == "replica", (
            f"Expected 'replica' for app_label={app_label!r}, got {result!r}"
        )

    def test_non_replica_app_returns_none(self, router, with_replica):
        """Apps not in read-replica list should return None (use default routing)."""
        model = _make_model("users")
        assert router.db_for_read(model) is None

    def test_read_returns_none_when_replica_not_configured(self, router, without_replica):
        """When replica alias is absent, router must be a transparent no-op."""
        model = _make_model("assets")
        assert router.db_for_read(model) is None

    # 17.10 alias
    def test_read_queries_hit_replica(self, router, with_replica):
        """Asset list query routing: db_for_read → 'replica'."""
        asset_model = _make_model("assets")
        assert router.db_for_read(asset_model) == "replica"


# ---------------------------------------------------------------------------
# 17.3  db_for_write — always returns "default" for write ops
# ---------------------------------------------------------------------------


class TestWriteRouterReturnsPrimary:
    """db_for_write must return 'default' for read-replica app models ONLY
    when a replica is configured — otherwise a transparent no-op (R2-D8)."""

    @pytest.mark.parametrize("app_label", ["assets", "contracts", "marketplace", "search"])
    def test_write_router_returns_primary(self, router, with_replica, app_label):
        model = _make_model(app_label)
        result = router.db_for_write(model)
        assert result == "default", (
            f"Expected 'default' for app_label={app_label!r}, got {result!r}"
        )

    @pytest.mark.parametrize("app_label", ["assets", "contracts", "marketplace", "search"])
    def test_write_returns_none_when_replica_not_configured(
        self, router, without_replica, app_label
    ):
        """R2-D8 — with no replica the router MUST be a transparent no-op:
        returning 'default' here would OVERRIDE the ``using("admin")`` alias
        of management-command instances (save() consults db_for_write
        regardless of ``_state.db``), self-deadlocking admin-DB sweeps
        against their own FOR UPDATE row locks."""
        model = _make_model(app_label)
        assert router.db_for_write(model) is None

    def test_non_replica_app_write_returns_none(self, router):
        """Non-replica apps return None (defer to next router / default)."""
        model = _make_model("users")
        assert router.db_for_write(model) is None

    # 17.10 alias
    def test_write_queries_hit_primary(self, router, with_replica):
        """Write routing for replica-app model must return 'default' regardless."""
        asset_model = _make_model("assets")
        assert router.db_for_write(asset_model) == "default"


# ---------------------------------------------------------------------------
# allow_migrate — replica must never be migrated
# ---------------------------------------------------------------------------


class TestAllowMigrate:
    def test_replica_db_always_blocked(self, router):
        """allow_migrate must return False for the replica alias."""
        assert router.allow_migrate("replica", "assets") is False

    def test_default_db_returns_none(self, router):
        """allow_migrate defers to other routers for 'default'."""
        assert router.allow_migrate("default", "assets") is None

    def test_other_db_returns_none(self, router):
        assert router.allow_migrate("baas", "baas") is None


# ---------------------------------------------------------------------------
# allow_relation — cross-database relations
# ---------------------------------------------------------------------------


class TestAllowRelation:
    def test_same_default_db(self, router):
        obj1 = _make_obj("default")
        obj2 = _make_obj("default")
        assert router.allow_relation(obj1, obj2) is True

    def test_default_and_replica(self, router):
        """Relation between default and replica objects must be permitted."""
        obj1 = _make_obj("default")
        obj2 = _make_obj("replica")
        assert router.allow_relation(obj1, obj2) is True

    def test_default_and_admin(self, router):
        """Relation between default and admin objects must be permitted.

        The admin alias (B-RLS-0.5) is the SAME physical database as
        default — a role swap, not a different database — so FK
        assignments across the pair (e.g. DatabricksAccount signoff →
        users.User, account-plane task 8.2) must not fall through to
        Django's db-equality fallback and raise "the current database
        router prevents this relation"."""
        obj1 = _make_obj("default")
        obj2 = _make_obj("admin")
        assert router.allow_relation(obj1, obj2) is True

    def test_unrelated_db_returns_none(self, router):
        """Relations involving a third DB defer to the next router."""
        obj1 = _make_obj("default")
        obj2 = _make_obj("baas")
        assert router.allow_relation(obj1, obj2) is None
