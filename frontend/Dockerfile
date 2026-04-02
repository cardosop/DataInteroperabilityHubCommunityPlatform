# Frontend Dockerfile
# Multi-stage build for production
# No external # syntax= image: avoids an extra pull of docker/dockerfile from
# Docker Hub (can TLS-timeout on flaky links). Builtin BuildKit frontend is enough.
# Do not use RUN --network=host: rootless/hardened engines often reject it with
# "network.host is not allowed". Builder is Debian slim; NPM_USE_PUBLIC_DNS is
# opt-in and skipped on read-only /etc/resolv.conf (common in rootless).

# Build stage (Debian glibc: fewer npm/registry stalls vs Alpine+mDNS on some rootless/bridge setups)
FROM node:20-bookworm-slim AS builder

# Optional corporate proxy (pass from host: docker compose build --build-arg HTTPS_PROXY=...)
ARG HTTP_PROXY=
ARG HTTPS_PROXY=
ARG NO_PROXY=
ENV HTTP_PROXY=$HTTP_PROXY \
    HTTPS_PROXY=$HTTPS_PROXY \
    NO_PROXY=$NO_PROXY

# Brand name (Phase 28.7.5 Meshant); baked in at build time
ARG VITE_APP_NAME=Meshant
ENV VITE_APP_NAME=$VITE_APP_NAME

# Optional UX feature flags (Phase 29.66.16); default: enabled
ARG VITE_FEATURE_TOAST_ENABLED=
ARG VITE_FEATURE_BREADCRUMBS_ENABLED=
ARG VITE_FEATURE_RESOURCE_PICKERS_ENABLED=
ENV VITE_FEATURE_TOAST_ENABLED=$VITE_FEATURE_TOAST_ENABLED
ENV VITE_FEATURE_BREADCRUMBS_ENABLED=$VITE_FEATURE_BREADCRUMBS_ENABLED
ENV VITE_FEATURE_RESOURCE_PICKERS_ENABLED=$VITE_FEATURE_RESOURCE_PICKERS_ENABLED

# API base URL baked into the JS bundle.
# Default is empty: the app uses relative /api/v1 paths, proxied by nginx.
# Override at build time for deployments where the frontend is not served by nginx
# (e.g. CDN builds): --build-arg VITE_API_BASE_URL=https://api.example.com/api/v1
ARG VITE_API_BASE_URL=
ARG VITE_WS_BASE_URL=
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL
ENV VITE_WS_BASE_URL=$VITE_WS_BASE_URL

# Sentry DSN baked into the JS bundle at build time.
# Set via --build-arg VITE_SENTRY_DSN=https://... or CI/CD pipeline secret.
# Left empty here so builds without Sentry configured still succeed.
ARG VITE_SENTRY_DSN=
ARG VITE_ENVIRONMENT=production
ENV VITE_SENTRY_DSN=$VITE_SENTRY_DSN
ENV VITE_ENVIRONMENT=$VITE_ENVIRONMENT

ARG VITE_MVP_MODE=
ARG VITE_STRIPE_PUBLISHABLE_KEY=
ENV VITE_MVP_MODE=$VITE_MVP_MODE
ENV VITE_STRIPE_PUBLISHABLE_KEY=$VITE_STRIPE_PUBLISHABLE_KEY

WORKDIR /app

# Registry fetch tuning: slow or flaky networks during `npm ci` often surface as
# ETIMEDOUT; retries + longer timeouts reduce spurious build failures.
# Override at build time, e.g. --build-arg NPM_FETCH_TIMEOUT=900000
ARG NPM_FETCH_RETRIES=5
ARG NPM_FETCH_TIMEOUT=600000
ENV NPM_CONFIG_FETCH_RETRIES=${NPM_FETCH_RETRIES} \
    NPM_CONFIG_FETCH_TIMEOUT=${NPM_FETCH_TIMEOUT} \
    NPM_CONFIG_FETCH_RETRY_MINTIMEOUT=20000 \
    NPM_CONFIG_FETCH_RETRY_MAXTIMEOUT=120000 \
    NPM_CONFIG_MAXSOCKETS=3

# Prefer IPv4 when resolving registry hosts (common fix when IPv6 routes stall).
ENV NODE_OPTIONS=--dns-result-order=ipv4first

# Copy package files
COPY package*.json ./
# --no-audit avoids extra registry round-trips after install.
# Optional: NPM_USE_PUBLIC_DNS=1 tries to write 8.8.8.8 / 1.1.1.1 into /etc/resolv.conf
# before npm ci. Rootless/read-only builds skip silently (|| true); default is off.
ARG NPM_USE_PUBLIC_DNS=0
RUN set -eux; \
  if [ "$NPM_USE_PUBLIC_DNS" = "1" ]; then \
    printf '%s\n' "nameserver 8.8.8.8" "nameserver 1.1.1.1" > /etc/resolv.conf || true; \
  fi; \
  npm ci --no-audit --fund=false

# Copy source files
COPY . .

# Build application (Vite bakes VITE_APP_NAME into bundle)
RUN npm run build

# Production stage
FROM nginx:alpine
# Install wget for Docker healthcheck (busybox wget can have flaky exit codes)
RUN apk add --no-cache wget

# Copy built files
COPY --from=builder /app/dist /usr/share/nginx/html

# Copy nginx configuration as a template.
# The official nginx:alpine image runs envsubst on files in /etc/nginx/templates/
# at container startup (/docker-entrypoint.d/20-envsubst-on-templates.sh),
# outputting the rendered file to /etc/nginx/conf.d/default.conf.
# This allows runtime substitution of ${API_HOST} in the CSP header without
# rebuilding the image.
COPY nginx.conf /etc/nginx/templates/default.conf.template

# API host included in the CSP connect-src directive.
# Default is empty (same-origin only), which is correct when /api is proxied
# through this nginx instance.  Override at docker run / docker-compose level:
#   API_HOST=https://api.example.com
ENV API_HOST=""

# Expose port
EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
