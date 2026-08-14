"""Phase 313.1.5 — job handler registry unit tests (pure, no Django).

The registry is the core-owned dispatch seam: paid apps register handlers
from AppConfig.ready(); core-only mode has no paid handlers and the jobs
dispatcher falls through to its unknown-type error.
"""

from hub.apps.core import job_handlers


def _dummy(_job_obj):
    return {"handled": True}


def test_register_and_get_handler():
    job_handlers.register_job_handler("TEST_JOB")(_dummy)
    try:
        assert job_handlers.get_job_handler("TEST_JOB") is _dummy
    finally:
        job_handlers._JOB_HANDLERS.pop("TEST_JOB", None)


def test_unknown_job_type_returns_none():
    assert job_handlers.get_job_handler("DOES_NOT_EXIST_ANYWHERE") is None


def test_registration_is_idempotent_on_reload():
    def first(_job_obj):
        return "first"

    def second(_job_obj):
        return "second"

    # Simulates ready() running twice (test reloads / re-imports): the last
    # registration wins and no duplicate entries accumulate.
    job_handlers.register_job_handler("RELOAD_JOB")(first)
    job_handlers.register_job_handler("RELOAD_JOB")(second)
    try:
        assert job_handlers.get_job_handler("RELOAD_JOB") is second
        assert job_handlers.get_job_handler("RELOAD_JOB")(None) == "second"
    finally:
        job_handlers._JOB_HANDLERS.pop("RELOAD_JOB", None)


def test_decorator_returns_original_function():
    assert job_handlers.register_job_handler("KEEP_FN")(_dummy) is _dummy
    job_handlers._JOB_HANDLERS.pop("KEEP_FN", None)
