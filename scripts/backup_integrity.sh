#!/usr/bin/env bash
# =============================================================================
# backup_integrity.sh — single-source backup hash-verification library (W8.2).
#
# One implementation of the integrity contract every backup surface uses:
#   * create_backup.sh   — manifests for the db dump + config tarballs
#   * backup-postgres.sh — manifest for the S3 upload
#   * restore-drill.sh   — verify before pg_restore
#   * minio-restore-drill.sh — verify every restored object
#
# Manifest format (sha256sum-compatible):
#     <64-hex-sha256>  <filename>
#
# Functions (source this file; nothing runs at source time):
#   integrity_manifest_for FILE          — prints "digest  basename" (exit 1 on error)
#   integrity_write_manifest FILE OUT    — writes the manifest next to OUT path
#   integrity_verify FILE MANIFEST       — exit 0 when FILE matches MANIFEST,
#                                          exit 1 with a diagnostic otherwise
#
# Hashing: sha256sum (GNU coreutils) preferred; falls back to openssl
# dgst -sha256 on Alpine/macOS.  Integrity failures MUST abort the
# caller — a backup that cannot be verified is not a backup.
# =============================================================================

_integrity_hash_file() {
    # Echo the lowercase hex sha256 of $1; exit 1 when no hasher exists.
    local file="$1"
    if command -v sha256sum >/dev/null 2>&1; then
        sha256sum "$file" | awk '{print $1}'
    elif command -v openssl >/dev/null 2>&1; then
        openssl dgst -sha256 "$file" | awk '{print $NF}'
    else
        echo "backup_integrity: neither sha256sum nor openssl found" >&2
        return 1
    fi
}

integrity_manifest_for() {
    # Print the manifest line for FILE (digest + basename, sha256sum shape).
    local file="$1"
    if [ ! -f "$file" ]; then
        echo "backup_integrity: no such file: $file" >&2
        return 1
    fi
    local digest
    digest="$(_integrity_hash_file "$file")" || return 1
    printf '%s  %s\n' "$digest" "$(basename "$file")"
}

integrity_write_manifest() {
    # Write the manifest for FILE to the OUT path (atomically).
    local file="$1" out="$2"
    integrity_manifest_for "$file" > "$out" || return 1
}

integrity_verify() {
    # Verify FILE against its MANIFEST (digest + basename line).
    local file="$1" manifest="$2"
    if [ ! -f "$file" ]; then
        echo "backup_integrity: VERIFY FAILED — file missing: $file" >&2
        return 1
    fi
    if [ ! -f "$manifest" ]; then
        echo "backup_integrity: VERIFY FAILED — manifest missing: $manifest" >&2
        return 1
    fi
    local expected actual
    expected="$(awk '{print $1}' "$manifest" | head -1)"
    actual="$(_integrity_hash_file "$file")" || return 1
    if [ -z "$expected" ] || [ "$expected" != "$actual" ]; then
        echo "backup_integrity: VERIFY FAILED — SHA-256 mismatch for $(basename "$file")" >&2
        echo "  expected: ${expected:-<empty manifest>}" >&2
        echo "  actual:   $actual" >&2
        return 1
    fi
    return 0
}
