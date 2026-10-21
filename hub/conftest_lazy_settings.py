"""Lazy-settings importability guard (Phase Q.4 W4.1).

Django resolves class-path settings LAZILY — ``MIDDLEWARE``
(``BaseHandler.load_middleware()`` on first request), ``AUTHENTICATION_BACKENDS``
(``django.contrib.auth``'s ``load_backend()``), DRF's class paths
(``api_settings.import_from_string()``), ``STORAGES``/``DEFAULT_FILE_STORAGE``,
``TEMPLATES`` backends and loaders, and ``LOGGING`` handler classes
(``logging.config.dictConfig``) are all imported on FIRST USE, not at
``django.setup()``. An environment missing one of those packages therefore
sails through setup, collection AND fixture setup, then dies mid-test with
an unrelated-looking ``ModuleNotFoundError`` a dozen frames deep — every
affected test reads as a product failure rather than an incomplete venv.

This guard imports every such entry up front during ``pytest_configure`` and
raises ``pytest.UsageError`` naming the missing module, the settings surface
that needs it, and the exact interpreter — making the failure an environment
diagnosis, not a test result.

History: this began as ``_verify_middleware_importable()`` covering
``MIDDLEWARE`` only (Phase 1.1 fix, previously inline in hub/conftest.py).
Q.4 W4.1 generalised it to every lazily-resolved surface and extracted it
here so the guard is importable and testable without conftest side effects.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Iterator

# DRF setting keys whose values are dotted class paths (string or list of
# strings). Deliberately enumerated — NOT every REST_FRAMEWORK key — so
# dict-of-rates keys like DEFAULT_THROTTLE_RATES are never mistaken for paths.
REST_FRAMEWORK_CLASS_PATH_KEYS = (
    "DEFAULT_AUTHENTICATION_CLASSES",
    "DEFAULT_PERMISSION_CLASSES",
    "DEFAULT_THROTTLE_CLASSES",
    "DEFAULT_RENDERER_CLASSES",
    "DEFAULT_PARSER_CLASSES",
    "DEFAULT_FILTER_BACKENDS",
    "DEFAULT_PAGINATION_CLASS",
    "DEFAULT_VERSIONING_CLASS",
    "DEFAULT_CONTENT_NEGOTIATION_CLASS",
    "DEFAULT_SCHEMA_CLASS",
    "EXCEPTION_HANDLER",
    "TEST_REQUEST_RENDERER_CLASSES",
)


def iter_lazy_settings_entries(settings) -> Iterator[tuple[str, str]]:
    """Yield ``(surface, dotted_path)`` for every lazily-resolved entry.

    ``settings`` is any object with attribute-style access
    (``django.conf.settings`` or a plain namespace in tests). Non-string
    entries (already-imported class objects) are skipped — nothing to import.
    """
    for entry in getattr(settings, "MIDDLEWARE", []) or []:
        yield "MIDDLEWARE", entry

    for entry in getattr(settings, "AUTHENTICATION_BACKENDS", []) or []:
        yield "AUTHENTICATION_BACKENDS", entry

    rest_framework = getattr(settings, "REST_FRAMEWORK", {}) or {}
    for key in REST_FRAMEWORK_CLASS_PATH_KEYS:
        value = rest_framework.get(key)
        if isinstance(value, str):
            yield f"REST_FRAMEWORK[{key}]", value
        elif isinstance(value, (list, tuple)):
            for entry in value:
                if isinstance(entry, str):
                    yield f"REST_FRAMEWORK[{key}]", entry

    for name, config in (getattr(settings, "STORAGES", {}) or {}).items():
        backend = config.get("BACKEND") if isinstance(config, dict) else None
        if isinstance(backend, str):
            yield f"STORAGES[{name}]", backend

    default_storage = getattr(settings, "DEFAULT_FILE_STORAGE", None)
    if isinstance(default_storage, str):
        yield "DEFAULT_FILE_STORAGE", default_storage

    for index, engine in enumerate(getattr(settings, "TEMPLATES", []) or []):
        if not isinstance(engine, dict):
            continue
        backend = engine.get("BACKEND")
        if isinstance(backend, str):
            yield f"TEMPLATES[{index}].BACKEND", backend
        loaders = (engine.get("OPTIONS") or {}).get("loaders", [])
        for loader_index, loader in enumerate(loaders or []):
            # Django's loader entries are either a dotted string or a
            # (dotted_string, [template_dirs]) tuple — the dirs are NOT paths.
            loader_path = loader[0] if isinstance(loader, (tuple, list)) and loader else loader
            if isinstance(loader_path, str):
                yield f"TEMPLATES[{index}].OPTIONS.loaders[{loader_index}]", loader_path

    logging_config = getattr(settings, "LOGGING", {}) or {}
    for name, handler in (logging_config.get("handlers") or {}).items():
        klass = handler.get("class") if isinstance(handler, dict) else None
        if isinstance(klass, str):
            yield f"LOGGING.handlers[{name}].class", klass


def verify_lazy_settings_importable(settings=None) -> None:
    """Import every lazily-resolved settings entry; raise UsageError on gaps.

    ``settings`` defaults to ``django.conf.settings``; tests inject a plain
    namespace so RED drills never mutate the live settings.
    """
    import importlib
    import sys

    if settings is None:
        import django
        from django.conf import settings

        # Mirror the runtime: these entries are resolved on FIRST USE, which
        # always happens AFTER django.setup() — some (e.g.
        # django.contrib.auth.middleware) import model definitions whose
        # metaclass requires the app registry. Importing them pre-setup
        # raises AppRegistryNotReady instead of the environment gap this
        # guard exists to report. setup() is idempotent.
        django.setup()

    missing: dict[str, tuple[str, str]] = {}
    for surface, entry in iter_lazy_settings_entries(settings):
        module_path = entry.rsplit(".", 1)[0]
        try:
            importlib.import_module(module_path)
        except ModuleNotFoundError as exc:
            # exc.name is the top-level missing module — this also catches a
            # missing DEPENDENCY of a module that did import, which is the
            # same environment gap from the caller's perspective.
            missing[surface] = (entry, exc.name or module_path)

    if not missing:
        return

    packages = ", ".join(sorted({needed for _, needed in missing.values()}))
    detail = "\n".join(
        f"  - {surface}: {entry} (needs {needed!r})"
        for surface, (entry, needed) in sorted(missing.items())
    )
    raise pytest.UsageError(
        "This Python environment is missing packages required by hub/settings.py: "
        f"{packages}\n\n"
        f"{detail}\n\n"
        "Django loads these settings LAZILY (first request / first use), so "
        "without this check the failure would surface as an unrelated-looking "
        "error inside the first affected test.\n\n"
        f"Interpreter: {sys.executable}\n"
        "Fix: install the project requirements into THIS interpreter —\n"
        f"  {sys.executable} -m pip install -r requirements.txt\n"
        "or use the canonical host-side interpreter (venv/bin/python); see "
        "docs/test-infrastructure/host-env-matrix.md"
    )
