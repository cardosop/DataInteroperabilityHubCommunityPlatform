#!/usr/bin/env bash
# =============================================================================
# ensure-stripe-cli.sh — repo-owned Stripe CLI provisioning (W2.10, pilot 4.3)
#
# Downloads a PINNED release of the Stripe CLI into .tools/bin/stripe with
# checksum verification, so the Stripe E2E specs drive a known CLI version
# instead of whatever happens to be on the operator's PATH.
#
# Pipeline:
#   1. If the binary already exists and matches the pinned BINARY sha256,
#      exit 0 (idempotent — no network).
#   2. Download the release tarball.
#   3. Verify the tarball sha256 against the pinned value (tamper-proof).
#   4. Extract, verify the EXTRACTED binary sha256 against the pinned value.
#   5. Install into the tools dir; clean up the temp dir.
#
# Usage:
#   ./scripts/ensure-stripe-cli.sh
#
# Env overrides (TEST SEAMS — pinned by scripts/tests/test_ensure_stripe_cli.py;
# production runs use the baked-in defaults):
#   STRIPE_CLI_BASE_URL     — download base (default: GitHub releases)
#   STRIPE_CLI_TOOLS_DIR    — install directory (default: <repo>/.tools/bin)
#   STRIPE_CLI_SHA256       — expected TARBALL sha256
#   STRIPE_CLI_BINARY_SHA256 — expected EXTRACTED BINARY sha256
#
# Exit codes:
#   0 — binary present and verified (installed or already current)
#   1 — download/verification/extraction failed
# =============================================================================
set -euo pipefail

STRIPE_CLI_VERSION="1.53.1"
# Env-first assignment: STRIPE_CLI_SHA256=... on the CLI overrides the pin.
# NOTE: this must be a single assignment — `VAR=const; VAR="${VAR:-}"`
# reads back the just-assigned constant (a literal assignment overwrites
# the inherited env value), silently ignoring the override.
STRIPE_CLI_SHA256="${STRIPE_CLI_SHA256:-032fe0b849a9d6a222488bc846445bafeae993af1026b78a8121d02321ca1fd1}"
STRIPE_CLI_BINARY_SHA256="${STRIPE_CLI_BINARY_SHA256:-79414e039e75062df696f3fb4a062321fa9642a1a6c0e4769c9723b47b1281c7}"
STRIPE_CLI_TARBALL="stripe_${STRIPE_CLI_VERSION}_linux_x86_64.tar.gz"

STRIPE_CLI_BASE_URL="${STRIPE_CLI_BASE_URL:-https://github.com/stripe/stripe-cli/releases/download/v${STRIPE_CLI_VERSION}}"

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TOOLS_DIR="${STRIPE_CLI_TOOLS_DIR:-$REPO_ROOT/.tools/bin}"
BIN_PATH="$TOOLS_DIR/stripe"

# Idempotence fast path: an existing binary whose sha matches the pin is
# already current — no network round-trip.
if [[ -f "$BIN_PATH" ]] && [[ -x "$BIN_PATH" ]]; then
    _bin_sha="$(sha256sum "$BIN_PATH" | awk '{print $1}')"
    if [[ "$_bin_sha" == "$STRIPE_CLI_BINARY_SHA256" ]]; then
        echo "stripe CLI ${STRIPE_CLI_VERSION} already installed and verified at ${BIN_PATH}"
        exit 0
    fi
    echo "stripe CLI at ${BIN_PATH} does not match the pinned sha256 — re-installing" >&2
fi

TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

echo "Downloading stripe CLI ${STRIPE_CLI_VERSION}..."
if ! curl -fsSL "${STRIPE_CLI_BASE_URL}/${STRIPE_CLI_TARBALL}" -o "${TMP_DIR}/${STRIPE_CLI_TARBALL}"; then
    echo "ERROR: download failed: ${STRIPE_CLI_BASE_URL}/${STRIPE_CLI_TARBALL}" >&2
    exit 1
fi

_downloaded_sha="$(sha256sum "${TMP_DIR}/${STRIPE_CLI_TARBALL}" | awk '{print $1}')"
if [[ "$_downloaded_sha" != "$STRIPE_CLI_SHA256" ]]; then
    echo "ERROR: tarball sha256 mismatch" >&2
    echo "  expected: ${STRIPE_CLI_SHA256}" >&2
    echo "  actual:   ${_downloaded_sha}" >&2
    exit 1
fi

tar xzf "${TMP_DIR}/${STRIPE_CLI_TARBALL}" -C "$TMP_DIR"

_extracted_sha="$(sha256sum "${TMP_DIR}/stripe" | awk '{print $1}')"
if [[ "$_extracted_sha" != "$STRIPE_CLI_BINARY_SHA256" ]]; then
    echo "ERROR: extracted binary sha256 mismatch" >&2
    echo "  expected: ${STRIPE_CLI_BINARY_SHA256}" >&2
    echo "  actual:   ${_extracted_sha}" >&2
    exit 1
fi

mkdir -p "$TOOLS_DIR"
install -m 0755 "${TMP_DIR}/stripe" "$BIN_PATH"

echo "stripe CLI ${STRIPE_CLI_VERSION} installed to ${BIN_PATH}"
