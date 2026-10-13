"""
Contract tests for the internal-operations ExternalSecret manifest
(oss-release-remediation W0.7).

The staging Redis instance passwords (requirepass x4) and the worker API
key are referenced from the cluster secret store — the manifest is the
contract (installed once the staging cluster runs external-secrets; the
compose path consumes the same values as ${VAR:?} env vars per the
secrets registry). These pins parse the REAL manifest and fail on:

- a missing/moved manifest;
- anything that is not the ExternalSecret kind on the v1beta1 api;
- a secretKey set that diverges from the canonical 5 keys;
- a remoteRef that does not point at the declared store keys
  (pilot/redis for the 4 passwords, pilot/staging-internal for the
  worker key);
- any INLINE secret value (the sso-manifest convention: referenced,
  never inlined).
"""

from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
MANIFEST = (
    REPO_ROOT
    / "infrastructure"
    / "staging"
    / "secrets"
    / "internal-operations-externalsecret.yaml"
)

REDIS_KEYS = (
    "REDIS_CACHE_PASSWORD",
    "REDIS_QUEUE_PASSWORD",
    "REDIS_EVENTS_PASSWORD",
    "REDIS_CHANNELS_PASSWORD",
)
CANONICAL_KEYS = (*REDIS_KEYS, "HUB_WORKER_API_KEY")


def _load():
    with MANIFEST.open() as handle:
        return yaml.safe_load(handle)


def test_manifest_exists_at_the_pinned_path():
    assert MANIFEST.is_file(), "the internal-operations manifest moved or was deleted"


def test_kind_and_api_version():
    doc = _load()
    assert doc["apiVersion"] == "external-secrets.io/v1beta1"
    assert doc["kind"] == "ExternalSecret"
    assert doc["metadata"]["namespace"] == "datahub-staging"


def test_canonical_secret_keys():
    doc = _load()
    secret_keys = tuple(entry["secretKey"] for entry in doc["spec"]["data"])
    assert secret_keys == CANONICAL_KEYS


def test_remote_refs_point_at_the_declared_store_keys():
    doc = _load()
    refs = {
        entry["secretKey"]: entry["remoteRef"]
        for entry in doc["spec"]["data"]
    }
    for key in REDIS_KEYS:
        assert refs[key] == {"key": "pilot/redis", "property": key}
    assert refs["HUB_WORKER_API_KEY"] == {
        "key": "pilot/staging-internal",
        "property": "HUB_WORKER_API_KEY",
    }


def test_no_inline_secret_values():
    text = MANIFEST.read_text()
    for entry in _load()["spec"]["data"]:
        assert "value" not in entry, "an inline secret value in the manifest"
    lowered = text.lower()
    assert "password:" not in lowered, "inline password-shaped material"
    assert "secret:" not in lowered, "inline secret-shaped material"


def test_secret_store_ref():
    doc = _load()
    assert doc["spec"]["secretStoreRef"] == {
        "kind": "SecretStore",
        "name": "pilot-secret-store",
    }
