# Frontend Dockerfile
# Multi-stage build for production

# Build stage
FROM node:20-alpine AS builder

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

WORKDIR /app

# Copy package files
COPY package*.json ./
RUN npm ci

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

# Copy nginx configuration
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Expose port
EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
