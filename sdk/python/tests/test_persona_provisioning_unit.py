"""
Phase 216.1.10 — unit tests for _persona_provisioning.py internals.

Tests validate the caching, cache-key generation, and credential
dataclass WITHOUT hitting any backend.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from unittest.mock import patch

from tests._persona_provisioning import (
    PersonaCredentials,
    _cache_key,
    _cache_path,
    _read_cache,
    _write_cache,
    _xdist_worker_id,
    _CACHE_DIR,
)


def test_xdist_worker_id_default():
    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop("PYTEST_XDIST_WORKER", None)
        assert _xdist_worker_id() == "master"


def test_xdist_worker_id_from_env():
    with patch.dict(os.environ, {"PYTEST_XDIST_WORKER": "gw3"}):
        assert _xdist_worker_id() == "gw3"


def test_cache_key_deterministic():
    with patch("tests._persona_provisioning._xdist_worker_id", return_value="master"):
        k1 = _cache_key("data_engineer", None)
        k2 = _cache_key("data_engineer", None)
        assert k1 == k2


def test_cache_key_differs_by_role():
    with patch("tests._persona_provisioning._xdist_worker_id", return_value="master"):
        k1 = _cache_key("data_engineer", None)
        k2 = _cache_key("tenant_admin", None)  # noqa: PHASE216-STATIC-ID
        assert k1 != k2


def test_cache_key_differs_by_tenant():
    with patch("tests._persona_provisioning._xdist_worker_id", return_value="master"):
        k1 = _cache_key("data_engineer", None)
        k2 = _cache_key("data_engineer", "acme")
        assert k1 != k2


def test_write_and_read_cache(tmp_path):
    with patch("tests._persona_provisioning._CACHE_DIR", tmp_path):
        key = "test-key-abc"
        creds = PersonaCredentials(
            api_key="ak", user_id="u1", tenant_id="t1",
            refresh_token="rt", role="visitor",
        )
        _write_cache(key, creds)
        loaded = _read_cache(key)
        assert loaded is not None
        assert loaded.api_key == "ak"
        assert loaded.role == "visitor"


def test_read_cache_returns_none_for_missing(tmp_path):
    with patch("tests._persona_provisioning._CACHE_DIR", tmp_path):
        assert _read_cache("nonexistent") is None


def test_read_cache_expired(tmp_path):
    with patch("tests._persona_provisioning._CACHE_DIR", tmp_path):
        key = "expired"
        creds = PersonaCredentials(
            api_key="ak", user_id="u1", tenant_id="t1",
            refresh_token="rt", role="visitor",
        )
        _write_cache(key, creds)
        # Backdate the timestamp by 2 hours
        path = tmp_path / f"{key}.json"
        data = json.loads(path.read_text())
        data["_ts"] = time.time() - 7200
        path.write_text(json.dumps(data))
        assert _read_cache(key) is None


def test_read_cache_malformed_json(tmp_path):
    with patch("tests._persona_provisioning._CACHE_DIR", tmp_path):
        key = "bad"
        path = tmp_path / f"{key}.json"
        path.write_text("{not valid json")
        assert _read_cache(key) is None
