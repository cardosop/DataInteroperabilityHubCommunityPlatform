#!/bin/sh
# Idempotent Fuseki admin-password sync (Phase P.1 root fix).
#
# The upstream stain/jena-fuseki entrypoint writes shiro.ini ONLY when the
# persisted file does not exist:
#
#     if [ ! -f "$FUSEKI_BASE/shiro.ini" ] ; then
#         cp "$FUSEKI_HOME/shiro.ini" "$FUSEKI_BASE/shiro.ini"
#         ... envsubst '${ADMIN_PASSWORD}' ...
#     fi
#
# On a named volume the file persists across container recreations, so the
# FIRST password (or the base-image literal `admin=admin` when the initial
# boot raced/skipped the substitution) wins FOREVER. Rotating
# FUSEKI_ADMIN_PASSWORD, or re-creating the container with a different env
# value, changes nothing — the semantic-service then authenticates with the
# current env password against a Fuseki still serving the stale one, every
# write to /hub/update returns 401, RDF ingestion marks resources DEGRADED,
# and semantic tests fail en masse while healthchecks (unauthenticated GET)
# stay green. Measured on the P.1 full-mode run 2026-08-23: 40 semantic
# failures, root-caused to `insert_triples failed: status=401`.
#
# This wrapper re-runs the SAME envsubst the upstream entrypoint performs on
# first boot, on every start. It is idempotent: with a fresh volume it is a
# no-op (the upstream entrypoint has just written the file), and with an
# existing volume it converges shiro.ini to the current ADMIN_PASSWORD.
#
# Wired as an entrypoint prefix in the compose files that run this image:
#   entrypoint: ["sh", "-c", "/scripts/fuseki_password_sync.sh && exec /docker-entrypoint.sh"]
# with the script bind-mounted read-only.

set -eu

: "${FUSEKI_BASE:?FUSEKI_BASE must be set}"
: "${FUSEKI_HOME:?FUSEKI_HOME must be set}"

template="$FUSEKI_HOME/shiro.ini"
target="$FUSEKI_BASE/shiro.ini"

if [ ! -f "$template" ]; then
    echo "fuseki_password_sync: template $template not found; skipping" >&2
    exit 0
fi

if [ -z "${ADMIN_PASSWORD:-}" ]; then
    # Matches upstream: no env password means the existing file (whatever it
    # holds, including the upstream-generated random one) is authoritative.
    exit 0
fi

export ADMIN_PASSWORD
tmp="${target}.sync.$$"
trap 'rm -f "$tmp"' EXIT
envsubst '${ADMIN_PASSWORD}' < "$template" > "$tmp"
mv "$tmp" "$target"
trap - EXIT

echo "fuseki_password_sync: shiro.ini synced to current ADMIN_PASSWORD"
