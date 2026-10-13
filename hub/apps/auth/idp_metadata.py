"""
pilot-readiness 3.1 — IdP OIDC discovery-metadata fetching.
oss-release-remediation W1.0 (S3) — IdP JWKS capability verification.

Fetches and validates an IdP's OIDC discovery document (the
``.well-known/oauth-authorization-server`` surface) so SSO wiring can
be verified BEFORE the login flow is enabled: the issuer, the
authorization/token endpoints, and the JWKS URI must all exist for a
login to have any chance of succeeding.

W1.0 adds the second leg — the D4 precondition: the JWKS document at
the discovery's ``jwks_uri`` must itself be fetchable AND carry at
least one signing key the OIDC verification stack can actually use
(RSA/EC, ``use=sig``, loadable by PyJWK — the same consumer path the
W1.5 callback verification uses). A discovery document whose
``jwks_uri`` 404s or serves no usable signing key is a NOT_CAPABLE
IdP regardless of how complete the discovery document looks.

The fetch is a plain real HTTPS GET (httpx) — no mocks, no SDK; the
same shape the live integration test uses against the real IdP.
"""

from __future__ import annotations

import binascii

import httpx
from jwt import PyJWK
from jwt.exceptions import PyJWTError

_REQUIRED_KEYS = ("issuer", "authorization_endpoint", "token_endpoint", "jwks_uri")

# OIDC signature verification consumes RSA/EC keys; anything else (oct,
# OKP) cannot verify an RS/ES-signed ID token with authlib/pyoidc.
_SIGNING_KTYS = frozenset({"RSA", "EC"})
_SIGNING_ALG_PREFIXES = ("RS", "ES", "PS")


class IdPMetadataError(RuntimeError):
    """The discovery fetch failed (transport or contract)."""


class IdPJwksError(IdPMetadataError):
    """The JWKS fetch failed (transport or capability contract)."""


def fetch_idp_metadata(discovery_url: str, *, timeout: float = 20.0) -> dict:
    """Fetch + validate the IdP's OIDC discovery document.

    Raises ``IdPMetadataError`` with the failure class (transport class
    name, HTTP status, or the missing key name) — never the response
    body. Returns the parsed document on success.
    """
    try:
        response = httpx.get(discovery_url, timeout=timeout)
    except Exception as exc:
        raise IdPMetadataError(f"discovery fetch failed: {type(exc).__name__}") from exc
    if response.status_code != 200:
        raise IdPMetadataError(f"discovery fetch failed: HTTP {response.status_code}")
    try:
        document = response.json()
    except ValueError as exc:
        raise IdPMetadataError("discovery document is not valid JSON") from exc
    if not isinstance(document, dict):
        raise IdPMetadataError("discovery document is not a JSON object")
    missing = [key for key in _REQUIRED_KEYS if not document.get(key)]
    if missing:
        raise IdPMetadataError(f"discovery document missing: {', '.join(missing)}")
    return document


def _key_usability(key) -> tuple[bool, str | None]:
    """A JWKS member's usability for OIDC signature verification.

    Returns (usable, reason). The check mirrors the W1.5 consumption
    path: PyJWK must load the key, the kty must be a signature-verifying
    family, and the declared use/alg must not exclude signing.
    """
    if not isinstance(key, dict):
        return False, "not a JSON object"
    kty = key.get("kty")
    use = key.get("use")
    alg = key.get("alg")
    reason = None
    if not kty:
        reason = "missing kty"
    elif kty not in _SIGNING_KTYS:
        reason = f"kty {kty} cannot verify OIDC signatures"
    elif use not in (None, "", "sig"):
        reason = f"use={use} (not a signing key)"
    elif alg and not alg.startswith(_SIGNING_ALG_PREFIXES):
        reason = f"alg {alg} is not a signature algorithm"
    if reason is not None:
        return False, reason
    try:
        PyJWK.from_dict(key)
    except (PyJWTError, ValueError, binascii.Error) as exc:
        # The exception CLASS only — PyJWT messages can quote key material.
        # ValueError/binascii.Error: older PyJWT builds let malformed
        # base64/int decoding errors escape unwrapped (the in-container
        # suite found the class — a malformed IdP key must be classified
        # unusable, never crash the capability check).
        return False, f"unloadable by PyJWK: {type(exc).__name__}"
    return True, None


def fetch_idp_jwks(discovery_url: str, *, timeout: float = 20.0) -> dict:
    """The W1.0 capability check: fetch + validate the IdP's JWKS.

    Fetches the discovery document (see ``fetch_idp_metadata``), then
    GETs the JWKS document at its ``jwks_uri`` and validates it is a
    real JWKS with at least one usable signing key. Raises
    ``IdPJwksError`` with the failure class (transport class name, HTTP
    status, or the capability gap) — never the response body. Returns
    the capability report on success:

        {"issuer", "jwks_uri", "key_count", "usable_signing_keys",
         "kty_counts", "keys": [{"kid", "kty", "alg", "use", "usable",
         "unusable_reason"}]}

    Key material is never echoed; only the metadata verdicts are.
    """
    # fetch_idp_metadata already rejects a document without jwks_uri
    # (IdPMetadataError, which IdPJwksError subclasses — one catch
    # family covers every not-capable outcome).
    document = fetch_idp_metadata(discovery_url, timeout=timeout)
    jwks_uri = document["jwks_uri"]
    try:
        response = httpx.get(jwks_uri, timeout=timeout)
    except Exception as exc:
        raise IdPJwksError(f"jwks fetch failed: {type(exc).__name__}") from exc
    if response.status_code != 200:
        raise IdPJwksError(f"jwks fetch failed: HTTP {response.status_code}")
    try:
        raw = response.json()
    except ValueError as exc:
        raise IdPJwksError("jwks document is not valid JSON") from exc
    if not isinstance(raw, dict):
        raise IdPJwksError("jwks document is not a JSON object")
    keys = raw.get("keys")
    if not isinstance(keys, list) or not keys:
        raise IdPJwksError("jwks document has no keys")

    details = []
    kty_counts: dict[str, int] = {}
    usable = 0
    for key in keys:
        verdict, reason = _key_usability(key)
        kty = key.get("kty") if isinstance(key, dict) else None
        if kty:
            kty_counts[kty] = kty_counts.get(kty, 0) + 1
        if verdict:
            usable += 1
        details.append(
            {
                "kid": key.get("kid") if isinstance(key, dict) else None,
                "kty": kty,
                "alg": key.get("alg") if isinstance(key, dict) else None,
                "use": key.get("use") if isinstance(key, dict) else None,
                "usable": verdict,
                "unusable_reason": reason,
            }
        )
    if usable == 0:
        raise IdPJwksError(
            f"no usable signing key in the JWKS ({len(keys)} key(s), none usable)"
        )
    return {
        "issuer": document.get("issuer"),
        "jwks_uri": jwks_uri,
        "key_count": len(keys),
        "usable_signing_keys": usable,
        "kty_counts": kty_counts,
        "keys": details,
    }
