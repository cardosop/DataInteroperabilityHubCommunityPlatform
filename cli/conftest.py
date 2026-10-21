"""
Root-level conftest for the CLI test suite.

Two requirements collide on the top-level name ``tests``:

1. ``cli/tests/`` is a package and CLI test modules import
   ``tests.fixtures...`` / ``tests._persona_provisioning`` meaning *this*
   directory.
2. The project root must stay importable, because the Django-backed CLI
   tests (``cli/tests/e2e/``, ``cli/tests/use_cases/``) — and
   ``django.setup()`` in ``cli/tests/conftest.py`` — import ``hub``.

``cli/__init__.py`` exists, so pytest's ``prepend`` import mode walks the
basedir up past ``cli/`` to the project root and inserts *that* on
``sys.path``.  The project root also contains its own ``tests/`` package,
which then wins ``import tests`` over ``cli/tests/``.

The previous fix purged the project root from ``sys.path`` before every
module import.  That resolved the shadowing but made ``hub`` unimportable,
so ``django.setup()`` raised ``ModuleNotFoundError: No module named 'hub'``
and *no* Django-backed CLI test could run on a host interpreter at all —
trading a collection error for a total outage of the same tests.

Instead, bind the name ``tests`` to ``cli/tests`` in ``sys.modules`` up
front.  Python resolves ``tests.<sub>`` through the already-bound parent
package's ``__path__``, so ``cli/tests`` wins the name regardless of
``sys.path`` order, and every other project-root package (``hub``,
``services``, ...) stays importable.

Safe because this conftest is only loaded for CLI-scoped collection: the
project-root ``pytest.ini`` pins ``testpaths = hub/apps tests``, so a
bare root-level ``pytest`` never descends into ``cli/``.
"""

import importlib.util
import os
import sys

_CLI_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_CLI_DIR)
_CLI_TESTS_DIR = os.path.join(_CLI_DIR, "tests")


def _ensure_sys_path() -> None:
    """Put ``cli/`` ahead of the project root without dropping either.

    ``cli/`` first so CLI-local modules win; the project root retained so
    ``hub`` (and therefore ``DJANGO_SETTINGS_MODULE=hub.settings``) is
    importable.
    """
    if _CLI_DIR not in sys.path:
        sys.path.insert(0, _CLI_DIR)
    if _PROJECT_ROOT not in sys.path:
        sys.path.append(_PROJECT_ROOT)


def _bind_cli_tests_package() -> None:
    """Bind top-level ``tests`` to ``cli/tests`` in ``sys.modules``.

    Idempotent: a no-op once ``sys.modules["tests"]`` already points into
    ``cli/tests``.  If the project-root ``tests`` package got imported
    first it is replaced, since within a CLI run that binding is always
    the wrong one.
    """
    existing = sys.modules.get("tests")
    if existing is not None:
        existing_file = os.path.abspath(getattr(existing, "__file__", "") or "")
        if existing_file.startswith(_CLI_TESTS_DIR + os.sep):
            return

    init_path = os.path.join(_CLI_TESTS_DIR, "__init__.py")
    spec = importlib.util.spec_from_file_location(
        "tests",
        init_path,
        submodule_search_locations=[_CLI_TESTS_DIR],
    )
    if spec is None or spec.loader is None:  # pragma: no cover - defensive
        raise ImportError(f"cannot build a module spec for {init_path}")

    module = importlib.util.module_from_spec(spec)
    sys.modules["tests"] = module
    try:
        spec.loader.exec_module(module)
    except BaseException:
        # Never leave a half-initialised package bound under the name.
        sys.modules.pop("tests", None)
        raise


_ensure_sys_path()
_bind_cli_tests_package()
