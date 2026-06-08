"""Helpers for defaulting Django management commands to admin DB alias."""

from __future__ import annotations
from typing import Sequence

MANAGEMENT_DB_MODE_ENV = "HUB_USE_ADMIN_DB_FOR_COMMANDS"
MANAGEMENT_DB_ALIAS_ENV = "HUB_COMMAND_DB_ALIAS"

_ADMIN_DB_ALIAS = "admin"
_RUNTIME_COMMANDS = frozenset(
    {"runserver", "runserver_plus", "shell", "shell_plus", "test"}
)
_DATABASE_OPTION_COMMANDS = frozenset(
    {
        "migrate",
        "showmigrations",
        "sqlmigrate",
        "flush",
        "loaddata",
        "dumpdata",
        "sqlflush",
        "dbshell",
        "inspectdb",
    }
)


def _has_database_option(argv: Sequence[str]) -> bool:
    return any(
        arg == "--database" or arg.startswith("--database=")
        for arg in argv
    )


def prepare_manage_argv(argv: Sequence[str]) -> tuple[list[str], bool]:
    """
    Return normalized argv and whether admin-command DB mode is enabled.

    - Enable admin DB mode for management commands by default.
    - Do not enable it for runtime/test commands.
    - Add ``--database=admin`` for commands that support explicit DB aliasing.
    """
    normalized = list(argv)
    if len(normalized) < 2:
        return normalized, False

    command = (normalized[1] or "").strip()
    enable_admin_mode = bool(command) and command not in _RUNTIME_COMMANDS
    if (
        enable_admin_mode
        and command in _DATABASE_OPTION_COMMANDS
        and not _has_database_option(normalized)
    ):
        normalized.extend(["--database", _ADMIN_DB_ALIAS])
    return normalized, enable_admin_mode
