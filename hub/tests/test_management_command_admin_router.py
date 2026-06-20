import pytest

from hub.db_router import (
    ManagementCommandAdminRouter,  # type: ignore[attr-defined]  # test: edge-case type exercise
)


class _Meta:
    app_label = "users"


class _Model:
    _meta = _Meta()


@pytest.fixture()
def router():
    return ManagementCommandAdminRouter()


def test_router_noop_when_admin_mode_env_disabled(settings, monkeypatch, router):
    settings.DATABASES = dict(
        settings.DATABASES,
        admin={"ENGINE": "django.db.backends.postgresql"},
    )
    monkeypatch.delenv("HUB_USE_ADMIN_DB_FOR_COMMANDS", raising=False)
    monkeypatch.delenv("HUB_COMMAND_DB_ALIAS", raising=False)
    assert router.db_for_read(_Model) is None
    assert router.db_for_write(_Model) is None


def test_router_routes_reads_and_writes_to_admin_in_command_mode(
    settings,
    monkeypatch,
    router,
):
    settings.DATABASES = dict(
        settings.DATABASES,
        admin={"ENGINE": "django.db.backends.postgresql"},
    )
    monkeypatch.setenv("HUB_USE_ADMIN_DB_FOR_COMMANDS", "1")
    monkeypatch.setenv("HUB_COMMAND_DB_ALIAS", "admin")
    assert router.db_for_read(_Model) == "admin"
    assert router.db_for_write(_Model) == "admin"


def test_router_noop_when_alias_missing(settings, monkeypatch, router):
    settings.DATABASES = {k: v for k, v in settings.DATABASES.items() if k != "admin"}
    monkeypatch.setenv("HUB_USE_ADMIN_DB_FOR_COMMANDS", "1")
    monkeypatch.setenv("HUB_COMMAND_DB_ALIAS", "admin")
    assert router.db_for_read(_Model) is None
    assert router.db_for_write(_Model) is None
