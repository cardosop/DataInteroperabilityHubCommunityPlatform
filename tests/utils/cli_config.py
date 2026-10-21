"""Test support for pointing the in-process CLI config at a writable dir.

The API test image runs with a hardened read-only rootfs (only /tmp tmpfs
and the bind-mounted /app are writable — see the api-service-test service
in docker-compose.test.yml).  The CLI's default config location is
``$HOME/.datahub`` (``/home/appuser/.datahub`` in the image), so any
``config.set_*`` call raises ``OSError: [Errno 30] Read-only file system``
unless the config dir is redirected.

``datahub_cli.config`` resolves ``CONFIG_DIR`` at import time, but
``Config._get_config_dir()`` re-reads the module attribute on every call,
so patching the attributes at test setup works regardless of when the
module was first imported in the process.
"""

import tempfile
from pathlib import Path


def point_cli_config_at_tmpdir() -> str:
    """Redirect the CLI config to a fresh temp dir and reset its state.

    Returns the temp dir path (caller may clean it up).
    """
    import datahub_cli.config as cli_config_module

    tmp_dir = tempfile.mkdtemp(prefix="datahub-cli-test-")
    cli_config_module.CONFIG_DIR = Path(tmp_dir)
    cli_config_module.CONFIG_FILE = Path(tmp_dir) / "config.yaml"
    # The module-level singleton is shared across the whole pytest process —
    # reset it so each test starts from a clean config instead of inheriting
    # another test's api_key / base URL.
    cli_config_module.config._config = {}
    return tmp_dir
