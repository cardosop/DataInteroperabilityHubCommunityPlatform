"""Tests for the lazy-settings importability guard (Phase Q.4 W4.1).

Django resolves class-path settings LAZILY — MIDDLEWARE,
AUTHENTICATION_BACKENDS, REST_FRAMEWORK class paths, STORAGES backends,
TEMPLATES backends/loaders and LOGGING handler classes are imported on FIRST
USE, not at ``django.setup()``. An environment missing one of those packages
sails through setup and collection, then dies mid-test with an
unrelated-looking ``ModuleNotFoundError`` — every affected test reads as a
product failure instead of an incomplete venv.

The guard imports every entry up front and raises ``pytest.UsageError``
naming the missing module, the settings surface that needs it, and the
exact interpreter.

These tests drive the REAL import machinery — no mocks:
* every GREEN case uses genuinely installed modules (Django itself, the
  stdlib, or modules present in this repository);
* every RED case points one entry at a genuinely nonexistent module and
  asserts the UsageError names it;
* the settings container is a plain injected namespace, because the guard's
  contract is ``(settings) -> raise-or-pass`` and the RED drills must not
  mutate the live ``django.conf.settings``.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from hub.conftest_lazy_settings import iter_lazy_settings_entries, verify_lazy_settings_importable

# A module that genuinely does not exist anywhere in this interpreter.
MISSING_MODULE = "hub_conftest_guard_nonexistent_pkg_xyz"

# Real, installed entries used to prove the GREEN path exercises real imports.
REAL_MIDDLEWARE = "django.middleware.security.SecurityMiddleware"
REAL_BACKEND = "django.contrib.auth.backends.ModelBackend"
REAL_RENDERER = "rest_framework.renderers.JSONRenderer"
REAL_HANDLER = "django.core.exceptions.ImproperlyConfigured"  # any real class path


def _settings(**overrides):
    base = {
        "MIDDLEWARE": [REAL_MIDDLEWARE],
        "AUTHENTICATION_BACKENDS": [REAL_BACKEND],
        "REST_FRAMEWORK": {
            "DEFAULT_RENDERER_CLASSES": [REAL_RENDERER],
            "DEFAULT_AUTHENTICATION_CLASSES": [REAL_BACKEND],
        },
        "STORAGES": {"default": {"BACKEND": "django.core.files.storage.FileSystemStorage"}},
        "TEMPLATES": [{"BACKEND": "django.template.backends.django.DjangoTemplates"}],
        "LOGGING": {"handlers": {"console": {"class": "logging.StreamHandler"}}},
    }
    base.update(overrides)
    return SimpleNamespace(**base)


class TestGreenPaths:
    def test_real_installed_entries_pass(self):
        verify_lazy_settings_importable(_settings())

    def test_empty_container_passes(self):
        verify_lazy_settings_importable(SimpleNamespace())

    def test_non_string_entries_are_skipped(self):
        """An already-imported class object needs no import — and must not
        crash the guard."""
        settings = _settings()
        settings.REST_FRAMEWORK["DEFAULT_RENDERER_CLASSES"] = [
            json_renderer := type("Renderer", (), {})
        ]
        assert isinstance(json_renderer, type)
        verify_lazy_settings_importable(settings)

    def test_tuple_form_template_loader_real(self):
        settings = _settings()
        settings.TEMPLATES[0]["OPTIONS"] = {
            "loaders": [("django.template.loaders.filesystem.Loader", [])]
        }
        verify_lazy_settings_importable(settings)

    def test_real_django_settings_pass(self):
        """Integration: the LIVE settings must be importable in THIS env —
        this doubles as the venv-parity test (W4.3)."""
        from django.conf import settings as live_settings

        verify_lazy_settings_importable(live_settings)


class TestRedDrills:
    """One RED drill per surface: point an entry at a nonexistent module."""

    def _assert_raises_naming(self, settings, surface_fragment):
        with pytest.raises(pytest.UsageError) as excinfo:
            verify_lazy_settings_importable(settings)
        message = str(excinfo.value)
        assert MISSING_MODULE in message, message
        assert surface_fragment in message, message
        assert "Interpreter:" in message, message

    def test_middleware_missing_module(self):
        self._assert_raises_naming(
            _settings(MIDDLEWARE=[f"{MISSING_MODULE}.middleware.M"]), "MIDDLEWARE"
        )

    def test_auth_backends_missing_module(self):
        self._assert_raises_naming(
            _settings(AUTHENTICATION_BACKENDS=[f"{MISSING_MODULE}.backends.B"]),
            "AUTHENTICATION_BACKENDS",
        )

    def test_rest_framework_list_entry_missing_module(self):
        settings = _settings()
        settings.REST_FRAMEWORK["DEFAULT_RENDERER_CLASSES"] = [f"{MISSING_MODULE}.renderers.R"]
        self._assert_raises_naming(settings, "DEFAULT_RENDERER_CLASSES")

    def test_rest_framework_string_entry_missing_module(self):
        settings = _settings()
        settings.REST_FRAMEWORK["EXCEPTION_HANDLER"] = f"{MISSING_MODULE}.handlers.h"
        self._assert_raises_naming(settings, "EXCEPTION_HANDLER")

    def test_storages_backend_missing_module(self):
        settings = _settings()
        settings.STORAGES["default"]["BACKEND"] = f"{MISSING_MODULE}.storage.S3Storage"
        self._assert_raises_naming(settings, "STORAGES")

    def test_default_file_storage_missing_module(self):
        settings = _settings()
        settings.DEFAULT_FILE_STORAGE = f"{MISSING_MODULE}.storage.LegacyStorage"
        self._assert_raises_naming(settings, "DEFAULT_FILE_STORAGE")

    def test_template_backend_missing_module(self):
        settings = _settings()
        settings.TEMPLATES[0]["BACKEND"] = f"{MISSING_MODULE}.backends.T"
        self._assert_raises_naming(settings, "TEMPLATES[0].BACKEND")

    def test_template_loader_missing_module(self):
        settings = _settings()
        settings.TEMPLATES[0]["OPTIONS"] = {"loaders": [(f"{MISSING_MODULE}.loaders.L", [])]}
        self._assert_raises_naming(settings, "loaders[0]")

    def test_logging_handler_missing_module(self):
        settings = _settings()
        settings.LOGGING["handlers"]["console"]["class"] = f"{MISSING_MODULE}.handlers.H"
        self._assert_raises_naming(settings, "LOGGING.handlers")

    def test_multiple_missing_surfaces_all_reported(self):
        settings = _settings()
        settings.MIDDLEWARE = [f"{MISSING_MODULE}.middleware.M"]
        settings.LOGGING["handlers"]["console"]["class"] = f"{MISSING_MODULE}.handlers.H"
        with pytest.raises(pytest.UsageError) as excinfo:
            verify_lazy_settings_importable(settings)
        message = str(excinfo.value)
        assert "MIDDLEWARE" in message, message
        assert "LOGGING.handlers" in message, message


class TestEntryIteration:
    def test_yields_every_surface(self):
        settings = _settings(
            DEFAULT_FILE_STORAGE="django.core.files.storage.FileSystemStorage",
        )
        settings.TEMPLATES[0]["OPTIONS"] = {
            "loaders": [("django.template.loaders.filesystem.Loader", [])]
        }
        entries = list(iter_lazy_settings_entries(settings))
        surfaces = {surface for surface, _ in entries}
        assert {
            "MIDDLEWARE",
            "AUTHENTICATION_BACKENDS",
            "REST_FRAMEWORK[DEFAULT_RENDERER_CLASSES]",
            "REST_FRAMEWORK[DEFAULT_AUTHENTICATION_CLASSES]",
            "STORAGES[default]",
            "DEFAULT_FILE_STORAGE",
            "TEMPLATES[0].BACKEND",
            "TEMPLATES[0].OPTIONS.loaders[0]",
            "LOGGING.handlers[console].class",
        } <= surfaces

    def test_tuple_loader_yields_loader_path_not_dirs(self):
        settings = _settings()
        settings.TEMPLATES[0]["OPTIONS"] = {
            "loaders": [("django.template.loaders.cached.Loader", ["/some/dir"])]
        }
        entries = dict(iter_lazy_settings_entries(settings))
        assert entries["TEMPLATES[0].OPTIONS.loaders[0]"] == "django.template.loaders.cached.Loader"
