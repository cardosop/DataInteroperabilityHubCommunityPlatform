#!/usr/bin/env bash
#
# Mirror repo-root `shared/` into `frontend/shared/` so the Docker
# build context (which is `./frontend/`) can resolve the
# `@shared/design-tokens/tokens.css` import in `src/index.css`.
#
# Why this exists
# ---------------
# `vite.config.ts` defines:
#
#     '@shared': fs.existsSync(path.resolve(__dirname, 'shared'))
#       ? path.resolve(__dirname, 'shared')           // Docker
#       : path.resolve(__dirname, '../shared'),       // local dev
#
# Local dev (running `npm run build` or `npm run dev` from the host)
# resolves to `../shared` and finds the repo-root `shared/` dir. But
# `docker compose build frontend-test` only copies files from
# `./frontend/` into the build context — `../shared/` is invisible
# inside the container.
#
# CI handles this by running the equivalent `cp` before `docker build`
# (see `.github/workflows/deploy.yml:632-633`). This script gives local
# devs the same automation.
#
# Idempotent: re-running is safe. Files are copied with `-p` so
# timestamps survive (helps Docker layer caching).
#
# Use:
#   ./scripts/sync-shared.sh                 # from frontend/
#   npm run sync-shared                      # via the package script
#
# `frontend/shared/` is `.gitignore`d (frontend/.gitignore:40), so this
# never pollutes git history.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FRONTEND_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
REPO_ROOT="$(cd "${FRONTEND_DIR}/.." && pwd)"

SOURCE_DIR="${REPO_ROOT}/shared"
TARGET_DIR="${FRONTEND_DIR}/shared"

if [[ ! -d "${SOURCE_DIR}" ]]; then
  # Inside the Docker build context the repo-root `shared/` is not
  # mounted (Dockerfile context is `./frontend/`). The Dockerfile's
  # `COPY . .` already brought `frontend/shared/` into the image
  # because the host ran this script before `docker build`. So when
  # we hit this branch INSIDE the container, treat it as a no-op as
  # long as the target already exists. Fail loudly only when neither
  # source nor target is present — that's a genuine misconfiguration.
  if [[ -d "${TARGET_DIR}" ]] && [[ -f "${TARGET_DIR}/design-tokens/tokens.css" ]]; then
    echo "sync-shared: source dir absent (${SOURCE_DIR}) but ${TARGET_DIR} is already populated — assuming Docker post-COPY context; skipping."
    exit 0
  fi
  echo "::error::sync-shared: source dir missing at ${SOURCE_DIR} AND ${TARGET_DIR} is empty — run from a checkout that contains the repo-root shared/ directory before invoking docker compose build." >&2
  exit 1
fi

mkdir -p "${TARGET_DIR}"

# Copy contents of `shared/` into `frontend/shared/`. `-r` for
# directories, `-p` to preserve timestamps for Docker layer caching.
# Trailing slash on source ensures we copy the *contents*, not the
# parent dir.
cp -rp "${SOURCE_DIR}/." "${TARGET_DIR}/"

echo "sync-shared: ${SOURCE_DIR} → ${TARGET_DIR} ($(find "${TARGET_DIR}" -type f | wc -l) file(s))"
