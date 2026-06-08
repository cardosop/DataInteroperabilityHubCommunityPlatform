
import pytest
from hub.apps.core.management.admin_db import (
    MANAGEMENT_DB_ALIAS_ENV,
    MANAGEMENT_DB_MODE_ENV,
    prepare_manage_argv,
)  # type: ignore[import-not-found]  # test: edge-case type exercise


@pytest.mark.unit
def test_prepare_manage_argv_sets_admin_mode_for_migrate():
    argv, enable_admin = prepare_manage_argv(["manage.py", "migrate"])
    assert enable_admin is True
    assert argv[-2:] == ["--database", "admin"]


@pytest.mark.unit
def test_prepare_manage_argv_keeps_explicit_database():
    argv, enable_admin = prepare_manage_argv(
        ["manage.py", "migrate", "--database=default"]
    )
    assert enable_admin is True
    assert argv.count("--database") == 0
    assert "--database=default" in argv


@pytest.mark.parametrize("cmd", ["runserver", "test", "shell"])
@pytest.mark.unit
def test_prepare_manage_argv_disables_admin_mode_for_runtime_commands(cmd):
    argv, enable_admin = prepare_manage_argv(["manage.py", cmd])
    assert enable_admin is False
    assert "--database" not in argv


@pytest.mark.unit
def test_management_db_env_constants_are_stable():
    assert MANAGEMENT_DB_MODE_ENV == "HUB_USE_ADMIN_DB_FOR_COMMANDS"
    assert MANAGEMENT_DB_ALIAS_ENV == "HUB_COMMAND_DB_ALIAS"
