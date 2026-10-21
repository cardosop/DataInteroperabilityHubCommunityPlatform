"""
Contract tests for the SSO secrets boundary (pilot-readiness 3.1).

"Secrets in ExternalSecrets only": the SSO IdP credentials must be
referenced from an ExternalSecret manifest — never inlined in staging
env files, compose files, or the manifest itself. Pins:

- the ExternalSecret manifest references the canonical SSO keys via
  remoteRef ONLY (no inline data values);
- no staging env/compose file carries SSO secret keys or values;
- the manifest lives where the 1.6 ExternalSecrets wiring expects it.
"""

import re
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).parent.parent.parent
MANIFEST = REPO / "infrastructure/staging/secrets/sso-externalsecret.yaml"
STAGING_FILES = [
    REPO / ".env.staging",
    REPO / "infrastructure/staging",
    REPO / "infrastructure/traefik/traefik-staging.yml",
]

CANONICAL_SSO_KEYS = (
    "SSO_IDP_DISCOVERY_URL",
    "SSO_IDP_CLIENT_ID",
    "SSO_IDP_CLIENT_SECRET",
)
_SSO_SECRET_KEY_RE = re.compile(
    r"^[A-Z_]*(SSO|OIDC|AUTH0|OKTA|ENTRA)[A-Z_]*(SECRET|PASSWORD|TOKEN|CLIENT)", re.I
)


@pytest.fixture(scope="module")
def manifest():
    return yaml.safe_load(MANIFEST.read_text())


def test_manifest_exists_at_the_canonical_path():
    assert MANIFEST.exists(), "infrastructure/staging/secrets/sso-externalsecret.yaml missing"


def test_manifest_is_an_external_secret(manifest):
    assert manifest["kind"] == "ExternalSecret"
    assert "external-secrets.io" in manifest.get("apiVersion", "")


def test_manifest_references_the_canonical_sso_keys(manifest):
    # The canonical SSO keys are the secretKey/materialized names; the
    # store-side remoteRef points at the shared pilot/sso entry.
    keys = {entry["secretKey"] for entry in manifest.get("spec", {}).get("data", [])}
    for key in CANONICAL_SSO_KEYS:
        assert key in keys, f"{key} not referenced by the ExternalSecret"
    refs = {
        entry.get("remoteRef", {}).get("key") for entry in manifest.get("spec", {}).get("data", [])
    }
    assert refs == {"pilot/sso"}, "all three keys must come from the one store entry"


def test_manifest_has_no_inline_secret_values(manifest):
    # remoteRef-only: no entry may carry an inline `value` — the secret
    # store is the single source.
    for entry in manifest.get("spec", {}).get("data", []):
        assert "value" not in entry or entry.get("value") in (None, ""), (
            f"inline value found on {entry.get('remoteRef', {}).get('key')!r} — "
            "secrets live in ExternalSecrets only"
        )


def test_no_staging_env_or_compose_file_carries_sso_secrets():
    for path in STAGING_FILES:
        files = [p for p in path.rglob("*") if p.is_file()] if path.is_dir() else [path]
        for file in files:
            if not file.exists() or file.suffix not in (
                "",
                ".yml",
                ".yaml",
                ".ini",
                ".env",
                ".staging",
            ):
                continue
            for line in file.read_text(errors="ignore").splitlines():
                if _SSO_SECRET_KEY_RE.search(line.split("=", 1)[0] if "=" in line else line):
                    pytest.fail(
                        f"SSO secret key material found in {file.relative_to(REPO)}: "
                        "secrets belong in the ExternalSecret manifest only"
                    )
