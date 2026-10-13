"""Compose test-stack command sanity pin (Phase T.4 / W16 infra prerequisite).

Root cause pinned here: the W16 edit removed ``--appendonly yes`` from
``redis-queue-test`` and put the rationale as ``#`` comment lines INSIDE the
folded block scalar of the service's ``command``. PyYAML happily folds those
``#`` lines into the scalar, but the compose engine rejects the result
(``'services[redis-queue-test].command' invalid command line string``) — so
every boot of the test stack broke while every PyYAML-based repo test stayed
green. A ``#`` token inside a folded ``command`` scalar is the failure
mechanism; this suite makes it unbuildable again.

Two pins, plus RED drills:
  1. No service ``command`` in ``docker-compose.test.yml`` may contain a
     ``#`` comment token (block or flow scalar — comments belong OUTSIDE
     the scalar, as proper YAML comments).
  2. The W16 contract itself: ``redis-queue-test`` must not carry
     ``appendonly`` (the flag removal is the deliverable; drift back to
     AOF-on must fail here, not as a corrupted dump mid-suite).

No mocks: real YAML parsing of the real file; synthetic documents for the
RED drills (a broken document must be reported, a clean one must not).
"""

from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
BASE_COMPOSE = REPO_ROOT / "docker-compose.test.yml"


class _ResetLoader(yaml.SafeLoader):
    pass


def _reset_constructor(_loader, _node):
    return None


_ResetLoader.add_constructor("!reset", _reset_constructor)


def _load(path: Path) -> dict:
    return yaml.load(path.read_text(), Loader=_ResetLoader) or {}


def command_comment_violations(compose_doc: dict) -> list[str]:
    """Service names whose string-form ``command`` contains a ``#`` comment token.

    A ``#`` embedded in a string-form command scalar (folded or flow) becomes
    part of the shell command line: the compose engine may reject the whole
    document, and where it does not, the shell treats everything after the
    ``#`` as a comment — silently DROPPING the remaining flags. Comments must
    live outside the scalar as proper YAML comments.

    List-form commands are exempt: their entries are either literal argv or
    bash scripts (the ckan-test entrypoint pattern) where ``#`` lines are
    legitimate shell comments and no argument is silently dropped.
    """
    violations: list[str] = []
    for name, spec in (compose_doc.get("services") or {}).items():
        if not isinstance(spec, dict):
            continue
        command = spec.get("command")
        if isinstance(command, str) and "#" in command:
            violations.append(name)
    return sorted(violations)


def redis_queue_command(compose_doc: dict) -> list[str] | str | None:
    """The redis-queue-test command, or None when absent."""
    services = compose_doc.get("services") or {}
    spec = services.get("redis-queue-test") or {}
    return spec.get("command")


class TestRealComposeFile:
    def test_no_command_scalar_contains_a_comment_token(self):
        violations = command_comment_violations(_load(BASE_COMPOSE))
        assert violations == [], (
            "compose engine rejects `#` tokens inside command scalars — move the "
            f"comment outside the scalar: {violations}"
        )

    def test_redis_queue_test_has_no_appendonly_flag(self):
        """W16 infra contract: AOF stays off on redis-queue-test (the AOF file
        corrupted once under I/O load; the two flag-less Redis services were
        unaffected)."""
        command = redis_queue_command(_load(BASE_COMPOSE))
        assert command is not None, "redis-queue-test service missing"
        text = command if isinstance(command, str) else " ".join(command)
        assert "appendonly" not in text, (
            "redis-queue-test carries an appendonly flag — W16 removed it "
            "because the AOF file corrupted under I/O load"
        )


class TestSyntheticFixtures:
    """RED drills — the failure modes the real-file pins are supposed to catch."""

    def test_folded_command_with_comment_token_is_reported(self):
        doc = {
            "services": {
                "redis-queue-test": {
                    "image": "redis:7-alpine",
                    # The exact failure mode of the W16 edit: the rationale
                    # comment placed INSIDE the folded command scalar.
                    "command": "redis-server\n# rationale\n--maxmemory 512mb\n",
                }
            }
        }
        assert command_comment_violations(doc) == ["redis-queue-test"]

    def test_clean_folded_command_is_not_reported(self):
        doc = {
            "services": {
                "redis-queue-test": {
                    "image": "redis:7-alpine",
                    "command": "redis-server\n--maxmemory 512mb\n--maxmemory-policy noeviction\n",
                }
            }
        }
        assert command_comment_violations(doc) == []

    def test_list_command_with_comment_lines_is_exempt(self):
        """List-form commands carry literal argv / bash scripts (the
        ckan-test pattern) where ``#`` lines are legitimate shell comments."""
        doc = {
            "services": {
                "svc": {
                    "image": "x",
                    "command": ["run", "# a shell comment inside a script", "--flag"],
                }
            }
        }
        assert command_comment_violations(doc) == []
