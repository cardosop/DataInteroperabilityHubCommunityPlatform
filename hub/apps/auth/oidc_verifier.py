"""
D4 (oss-release-remediation W1.5) — OIDC ID-token verification via JWKS.

The round-1 P0: the SSO callback decoded ID tokens WITHOUT signature /
audience / expiry verification and minted platform JWTs from the
attacker-chosen claims — forged-token account takeover. This module is
the fix: every ID token is verified against the tenant's IdP JWKS
(signature), the pinned issuer, the tenant's OIDC client_id (audience),
and expiry, before ANY user lookup happens.

Stack note: decisions.md D4 names authlib/pyoidc as the example stacks —
neither is installed, and PyJWT (the repo's JWT stack) + PyJWKSet over
the JWKS fetched through ``idp_metadata`` is the same substance (JWKS
signature verification). W1.0's capability check validated exactly this
consumer path (PyJWK loadability) against the pilot IdP.

Failure modes are CLASSIFIED into ``OIDCTokenVerificationError`` reason
codes — never token material, never the IdP response body. The callback
maps every code to a 400 envelope.
"""

from __future__ import annotations

import base64
import binascii
import hashlib

import httpx
import jwt
from django.core.cache import cache

from .idp_metadata import IdPMetadataError, fetch_idp_metadata

# RS256/ES256 ONLY — HS256/alg-none confusion is closed by construction
# (no symmetric keys are ever accepted; `algorithms` rejects everything
# else, including "none").
_ALGORITHMS = ("RS256", "ES256")
_JWKS_CACHE_SECONDS = 60
_EC_CURVES = {
    "P-256": "SECP256R1",
    "P-384": "SECP384R1",
    "P-521": "SECP521R1",
}


def _b64decode(data: str) -> bytes:
    return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))


def _jwk_to_public_key(jwk: dict):
    """Convert a JWK to a cryptography public-key OBJECT.

    ``jwt.decode`` accepts cryptography key objects on every PyJWT build
    this repo runs (2.12 in-container, 2.15 host-side) — passing a
    ``PyJWKSet`` only works on newer builds (the in-container 2.12
    ``prepare_key`` raises "Expecting a PEM-formatted key" on it). The
    object form is the version-agnostic single path.
    """
    from cryptography.hazmat.primitives.asymmetric import ec, rsa

    def _invalid(cause: Exception) -> None:
        # TRY301: the raise is abstracted so the classification stays a
        # single exit — every malformed JWK yields OIDC_JWKS_INVALID.
        raise OIDCTokenVerificationError("OIDC_JWKS_INVALID") from cause

    kty = jwk.get("kty")
    try:
        if kty == "RSA":
            n = int.from_bytes(_b64decode(jwk["n"]), "big")
            e = int.from_bytes(_b64decode(jwk["e"]), "big")
            return rsa.RSAPublicNumbers(e, n).public_key(), "RS256"
        if kty == "EC":
            curve_name = _EC_CURVES.get(jwk.get("crv", ""))
            if curve_name:
                curve = getattr(ec, curve_name)()
                x = int.from_bytes(_b64decode(jwk["x"]), "big")
                y = int.from_bytes(_b64decode(jwk["y"]), "big")
                return ec.EllipticCurvePublicNumbers(x, y, curve).public_key(), "ES256"
    except (KeyError, ValueError, binascii.Error) as exc:
        _invalid(exc)
    _invalid(ValueError(f"unsupported JWK kty {kty!r}"))


class OIDCTokenVerificationError(ValueError):
    """The ID token failed verification — ``code`` carries the reason."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _fetch_jwks_document(jwks_uri: str, *, timeout: float) -> dict:
    """Fetch the IdP JWKS document (short cache — key material rotates)."""
    cache_key = f"oidc_jwks:{hashlib.sha1(jwks_uri.encode()).hexdigest()}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached
    try:
        response = httpx.get(jwks_uri, timeout=timeout)
    except Exception as exc:
        raise OIDCTokenVerificationError("OIDC_JWKS_FETCH_FAILED") from exc
    if response.status_code != 200:
        raise OIDCTokenVerificationError("OIDC_JWKS_FETCH_FAILED")
    try:
        document = response.json()
    except ValueError as exc:
        raise OIDCTokenVerificationError("OIDC_JWKS_INVALID") from exc
    if not isinstance(document, dict) or not document.get("keys"):
        raise OIDCTokenVerificationError("OIDC_JWKS_INVALID")
    cache.set(cache_key, document, _JWKS_CACHE_SECONDS)
    return document


def verify_oidc_id_token(
    id_token: str,
    *,
    issuer: str,
    audience: str,
    jwks_uri: str | None = None,
    discovery_url: str | None = None,
    timeout: float = 20.0,
) -> dict:
    """Verify an OIDC ID token and return its claims.

    Checks, in order: the JWKS is fetchable (``jwks_uri`` or the
    discovery document's — the ``idp_metadata`` module), the signature
    under an RS/ES key from the JWKS, then iss / aud / exp (+ sub must
    be present). Raises ``OIDCTokenVerificationError`` with a reason
    code on every failure; returns the verified claims on success.
    """
    if not issuer or not audience:
        raise OIDCTokenVerificationError("OIDC_CONFIG_INCOMPLETE")
    if not jwks_uri:
        if not discovery_url:
            raise OIDCTokenVerificationError("OIDC_CONFIG_INCOMPLETE")
        try:
            document = fetch_idp_metadata(discovery_url, timeout=timeout)
        except IdPMetadataError as exc:
            raise OIDCTokenVerificationError("OIDC_DISCOVERY_FAILED") from exc
        jwks_uri = document.get("jwks_uri")
        if not jwks_uri:
            raise OIDCTokenVerificationError("OIDC_JWKS_URI_MISSING")
        if document.get("issuer") and document["issuer"] != issuer:
            raise OIDCTokenVerificationError("OIDC_ISSUER_MISMATCH")

    jwks_document = _fetch_jwks_document(jwks_uri, timeout=timeout)

    # Resolve the token's signing key: the header kid picks the JWK
    # (single-key JWKS accepts a missing kid), then the JWK converts to
    # a cryptography public-key OBJECT — the version-agnostic decode key
    # (PyJWKSet-as-key only works on newer PyJWT builds than the
    # in-container 2.12).
    try:
        token_kid = jwt.get_unverified_header(id_token).get("kid")
    except (jwt.PyJWTError, ValueError, binascii.Error) as exc:
        raise OIDCTokenVerificationError("OIDC_TOKEN_SIGNATURE_INVALID") from exc

    keys = jwks_document.get("keys", [])
    matching = [k for k in keys if isinstance(k, dict) and k.get("kid") == token_kid]
    if len(matching) == 1:
        signing_jwk = matching[0]
    elif not token_kid and len(keys) == 1 and isinstance(keys[0], dict):
        signing_jwk = keys[0]
    else:
        # Unknown kid or ambiguous selection — the token cannot be bound
        # to an IdP key.
        raise OIDCTokenVerificationError("OIDC_TOKEN_SIGNATURE_INVALID")
    public_key, algorithm = _jwk_to_public_key(signing_jwk)

    try:
        claims = jwt.decode(
            id_token,
            key=public_key,
            algorithms=[algorithm],
            audience=audience,
            issuer=issuer,
            options={"require": ["exp", "iss", "aud", "sub"]},
        )
    except jwt.ExpiredSignatureError as exc:
        raise OIDCTokenVerificationError("OIDC_TOKEN_EXPIRED") from exc
    except jwt.InvalidAudienceError as exc:
        raise OIDCTokenVerificationError("OIDC_TOKEN_AUDIENCE_MISMATCH") from exc
    except jwt.InvalidIssuerError as exc:
        raise OIDCTokenVerificationError("OIDC_TOKEN_ISSUER_MISMATCH") from exc
    except (jwt.PyJWTError, ValueError, binascii.Error) as exc:
        # Signature failure, malformed token, or an old-PyJWT raw decode
        # error — one classification, never the message.
        raise OIDCTokenVerificationError("OIDC_TOKEN_SIGNATURE_INVALID") from exc
    if not isinstance(claims, dict) or not claims.get("sub"):
        raise OIDCTokenVerificationError("OIDC_TOKEN_SUB_MISSING")
    return claims
