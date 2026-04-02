"""
Unit tests for WORKER_TYPE queue selection (Phase 16.8).

Verifies that ``services/worker/main.py`` selects the correct RQ
queues for each WORKER_TYPE value without starting a real worker
or touching Django.

Isolation strategy
------------------
``main.py`` has module-level side-effects that require Django::

    django.setup()
    from django.core.management import call_command
    from services.worker.health import healthz, ready

All Django sub-packages and ``services.worker.health`` are stubbed
in ``sys.modules`` before the module is loaded so no DB/Redis is
touched.
"""
import importlib.util
import logging
import os
import sys
import types
from unittest.mock import MagicMock, patch

import pytest


# -------------------------------------------------------------------
# Module loader helper
# -------------------------------------------------------------------

def _make_django_mock() -> MagicMock:
    """MagicMock satisfying ``import django; django.setup()``."""
    mock = MagicMock()
    mock.core = MagicMock()
    mock.core.management = MagicMock()
    mock.core.management.call_command = MagicMock()
    return mock


def _make_health_mock() -> MagicMock:
    """Stub for ``services.worker.health``."""
    mock = MagicMock()
    mock.healthz = MagicMock(
        return_value=(200, {"status": "ok"}),
    )
    mock.ready = MagicMock(
        return_value=(200, {"status": "ready"}),
    )
    return mock


def _load_main_module(
    env_overrides: "dict | None" = None,
) -> types.ModuleType:
    """
    Load ``services/worker/main.py`` with Django deps stubbed.
    """
    django_mock = _make_django_mock()
    health_mock = _make_health_mock()

    module_stubs = {
        "django": django_mock,
        "django.core": django_mock.core,
        "django.core.management": django_mock.core.management,
        "services": MagicMock(),
        "services.worker": MagicMock(),
        "services.worker.health": health_mock,
    }

    spec_path = os.path.join(
        os.path.dirname(__file__), "..", "main.py",
    )
    spec = importlib.util.spec_from_file_location(
        "_worker_main_under_test", spec_path,
    )
    assert spec is not None
    assert spec.loader is not None

    mod = importlib.util.module_from_spec(spec)

    with patch.dict(sys.modules, module_stubs):
        sys.modules.pop("_worker_main_under_test", None)

        env = dict(os.environ)
        if env_overrides is not None:
            env.update(env_overrides)
        if (
            env_overrides is None
            or "WORKER_TYPE" not in env_overrides
        ):
            env.pop("WORKER_TYPE", None)

        with patch.dict(os.environ, env, clear=True):
            spec.loader.exec_module(mod)

    return mod


def _run_main(env_overrides):
    """Load main.py and call main(), capturing call_command args.

    Returns (cmd, queues_list, kwargs_dict).
    """
    mod = _load_main_module(env_overrides=env_overrides)
    captured = {}

    def fake_call_command(cmd, *queues, **kwargs):
        captured["cmd"] = cmd
        captured["queues"] = list(queues)
        captured["kwargs"] = kwargs

    runtime_env = dict(os.environ)
    if env_overrides is not None:
        runtime_env.update(env_overrides)
    if (
        env_overrides is None
        or "WORKER_TYPE" not in env_overrides
    ):
        runtime_env.pop("WORKER_TYPE", None)

    with (
        patch.object(mod, "call_command", fake_call_command),
        patch.object(mod, "start_health_check_server"),
        patch("sys.argv", ["services/worker/main.py"]),
        patch.dict(os.environ, runtime_env, clear=True),
    ):
        mod.main()

    return (
        captured["cmd"],
        captured["queues"],
        captured["kwargs"],
    )


# -------------------------------------------------------------------
# Tests: static queue mapping contract
# -------------------------------------------------------------------

class TestWorkerTypeQueueMapping:
    """_WORKER_TYPE_QUEUES dict — static contract (no I/O)."""

    def test_heavy_maps_to_job_critical_only(self):
        mod = _load_main_module()
        assert mod._WORKER_TYPE_QUEUES["heavy"] == [
            "job_critical",
        ]

    def test_light_maps_to_job_default_and_job_low(self):
        mod = _load_main_module()
        assert mod._WORKER_TYPE_QUEUES["light"] == [
            "job_default", "job_low",
        ]

    def test_all_maps_to_all_three_queues(self):
        mod = _load_main_module()
        assert mod._WORKER_TYPE_QUEUES["all"] == [
            "job_critical", "job_default", "job_low",
        ]


# -------------------------------------------------------------------
# Tests: WORKER_TYPE=heavy
# -------------------------------------------------------------------

class TestWorkerTypeHeavy:
    """WORKER_TYPE=heavy → rqworker with job_critical only."""

    def test_heavy_passes_rqworker_command(self):
        """call_command receives 'rqworker' as first arg."""
        cmd, queues, _ = _run_main({"WORKER_TYPE": "heavy"})
        assert cmd == "rqworker"

    def test_heavy_only_joins_critical_queue(self):
        _, queues, _ = _run_main({"WORKER_TYPE": "heavy"})
        assert queues == ["job_critical"]

    def test_heavy_enables_scheduler(self):
        """with_scheduler=True must be passed for delayed
        job retries."""
        _, _, kwargs = _run_main({"WORKER_TYPE": "heavy"})
        assert kwargs.get("with_scheduler") is True

    def test_heavy_sets_verbosity(self):
        _, _, kwargs = _run_main({"WORKER_TYPE": "heavy"})
        assert kwargs.get("verbosity") == 1

    @pytest.mark.xfail(
        strict=True,
        reason=(
            "WORKER_CONCURRENCY env var not yet "
            "forwarded to call_command "
            "(arch-improvements-01 Phase 4)."
        ),
    )
    def test_concurrency_env_forwarded(self):
        """WORKER_CONCURRENCY=8 must be forwarded."""
        _, _, kwargs = _run_main({
            "WORKER_TYPE": "heavy",
            "WORKER_CONCURRENCY": "8",
        })
        concurrency_keys = {
            k for k in kwargs
            if "concur" in k or "worker" in k or "num" in k
        }
        assert concurrency_keys
        for key in concurrency_keys:
            assert str(kwargs[key]) == "8"


# -------------------------------------------------------------------
# Tests: WORKER_TYPE=light
# -------------------------------------------------------------------

class TestWorkerTypeLight:
    """WORKER_TYPE=light → rqworker with default+low queues."""

    def test_light_skips_critical_queue(self):
        _, queues, _ = _run_main({"WORKER_TYPE": "light"})
        assert "job_critical" not in queues
        assert set(queues) == {"job_default", "job_low"}

    def test_light_passes_rqworker_command(self):
        cmd, _, _ = _run_main({"WORKER_TYPE": "light"})
        assert cmd == "rqworker"

    def test_light_enables_scheduler(self):
        _, _, kwargs = _run_main({"WORKER_TYPE": "light"})
        assert kwargs.get("with_scheduler") is True


# -------------------------------------------------------------------
# Tests: WORKER_TYPE=all / default / unknown
# -------------------------------------------------------------------

class TestWorkerTypeAllAndDefaults:
    """WORKER_TYPE=all → all queues; absent/unknown fall back."""

    _ALL = {"job_critical", "job_default", "job_low"}

    def test_all_joins_all_queues(self):
        _, queues, _ = _run_main({"WORKER_TYPE": "all"})
        assert set(queues) == self._ALL

    def test_default_worker_type_joins_all_queues(self):
        """Absent WORKER_TYPE defaults to all-queues."""
        _, queues, _ = _run_main(env_overrides=None)
        assert set(queues) == self._ALL

    def test_unknown_type_falls_back_to_all(self):
        """Unrecognised WORKER_TYPE falls back to all."""
        _, queues, _ = _run_main(
            {"WORKER_TYPE": "bogus_unknown_value"},
        )
        assert set(queues) == self._ALL

    def test_unknown_type_logs_warning(self, caplog):
        """Unrecognised WORKER_TYPE emits WARNING."""
        with caplog.at_level(logging.WARNING):
            _run_main(
                {"WORKER_TYPE": "bogus_unknown_value"},
            )

        warnings = [
            r.message for r in caplog.records
            if r.levelno >= logging.WARNING
        ]
        assert any(
            "bogus_unknown_value" in msg
            for msg in warnings
        ), (
            "Unknown WORKER_TYPE must be logged. "
            f"Got: {warnings}"
        )

    def test_all_passes_rqworker_and_scheduler(self):
        cmd, _, kwargs = _run_main(
            {"WORKER_TYPE": "all"},
        )
        assert cmd == "rqworker"
        assert kwargs.get("with_scheduler") is True


# -------------------------------------------------------------------
# Tests: sys.argv explicit queue override
# -------------------------------------------------------------------

class TestExplicitQueueArgs:
    """sys.argv queue args override WORKER_TYPE."""

    def test_argv_overrides_worker_type(self):
        """Explicit CLI args take precedence over env var."""
        mod = _load_main_module(
            env_overrides={"WORKER_TYPE": "heavy"},
        )
        captured = {}

        def fake_call_command(cmd, *queues, **kwargs):
            captured["cmd"] = cmd
            captured["queues"] = list(queues)

        with (
            patch.object(
                mod, "call_command", fake_call_command,
            ),
            patch.object(mod, "start_health_check_server"),
            patch(
                "sys.argv",
                [
                    "services/worker/main.py",
                    "my_queue_a",
                    "my_queue_b",
                ],
            ),
            patch.dict(
                os.environ, {"WORKER_TYPE": "heavy"},
            ),
        ):
            mod.main()

        assert captured["queues"] == [
            "my_queue_a", "my_queue_b",
        ]

    def test_health_server_started_with_env_port(self):
        """start_health_check_server uses
        WORKER_HEALTH_PORT."""
        mod = _load_main_module(
            env_overrides={"WORKER_HEALTH_PORT": "9090"},
        )

        with (
            patch.object(mod, "call_command"),
            patch.object(
                mod, "start_health_check_server",
            ) as mock_health,
            patch("sys.argv", ["services/worker/main.py"]),
            patch.dict(
                os.environ,
                {"WORKER_HEALTH_PORT": "9090"},
            ),
        ):
            mod.main()

        mock_health.assert_called_once_with(port=9090)
