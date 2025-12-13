# Frontend Deployment Guide

**Last Updated**: 2025-12-13  
**Version**: 1.0.0

---

## Table of Contents

1. [Overview](#overview)
2. [Build Configuration](#build-configuration)
3. [Environment Configuration](#environment-configuration)
4. [CDN Strategy](#cdn-strategy)
5. [Docker Deployment](#docker-deployment)
6. [Kubernetes Deployment](#kubernetes-deployment)
7. [CI/CD Pipeline](#cicd-pipeline)
8. [Version Management](#version-management)
9. [Feature Flags](#feature-flags)
10. [Rollback Strategy](#rollback-strategy)

---

## Overview

This document describes the deployment strategy for the frontend application. The application is deployed to multiple environments (development, staging, production) using containerization and orchestration.

**Deployment Environments**:
- **Development**: Local development server
- **Staging**: Staging environment for testing
- **Production**: Production environment for end users

**Deployment Methods**:
- Docker containers
- Kubernetes orchestration
- CDN for static assets
- CI/CD pipelines

---

## Build Configuration

### Vite Build Configuration

**File**: `vite.config.ts`

```typescript
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { visualizer } from 'rollup-plugin-visualizer';

export default defineConfig(({ mode }) => {
  const isProduction = mode === 'production';

  return {
    plugins: [
      react(),
      visualizer({
        open: false,
        filename: 'dist/stats.html',
      }),
    ],
    build: {
      outDir: 'dist',
      sourcemap: isProduction ? false : true,
      minify: isProduction ? 'terser' : false,
      terserOptions: {
        compress: {
          drop_console: isProduction,
          drop_debugger: isProduction,
        },
      },
      rollupOptions: {
        output: {
          manualChunks: {
            'react-vendor': ['react', 'react-dom', 'react-router-dom'],
            'mui-vendor': ['@mui/material', '@mui/icons-material'],
            'query-vendor': ['@tanstack/react-query'],
          },
        },
      },
      chunkSizeWarningLimit: 1000,
    },
    server: {
      port: 3000,
      proxy: {
        '/api': {
          target: 'http://localhost:8000',
          changeOrigin: true,
        },
        '/ws': {
          target: 'ws://localhost:8000',
          ws: true,
        },
      },
    },
  };
});
```

### Build Scripts

**File**: `package.json`

```json
{
  "scripts": {
    "build": "vite build",
    "build:staging": "vite build --mode staging",
    "build:production": "vite build --mode production",
    "preview": "vite preview",
    "analyze": "vite build --mode production && open dist/stats.html"
  }
}
```

---

## Environment Configuration

### Environment Variables

**File**: `.env.example`

```bash
# API Configuration
VITE_API_BASE_URL=http://localhost:8000
VITE_WS_URL=ws://localhost:8000
VITE_GRAPHQL_URL=http://localhost:8000/graphql

# Analytics
VITE_GA_ID=G-XXXXXXXXXX
VITE_SENTRY_DSN=https://xxx@sentry.io/xxx
VITE_ENABLE_ANALYTICS=false

# Feature Flags
VITE_ENABLE_MARKETPLACE=true
VITE_ENABLE_COMPLIANCE=true

# Environment
VITE_ENV=development
```

### Environment-Specific Files

- `.env.development` - Development environment
- `.env.staging` - Staging environment
- `.env.production` - Production environment

### Environment Variable Loading

**File**: `src/lib/config.ts`

```typescript
export const config = {
  api: {
    baseUrl: import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000',
    wsUrl: import.meta.env.VITE_WS_URL || 'ws://localhost:8000',
    graphqlUrl: import.meta.env.VITE_GRAPHQL_URL || 'http://localhost:8000/graphql',
  },
  analytics: {
    gaId: import.meta.env.VITE_GA_ID,
    sentryDsn: import.meta.env.VITE_SENTRY_DSN,
    enabled: import.meta.env.VITE_ENABLE_ANALYTICS === 'true',
  },
  features: {
    marketplace: import.meta.env.VITE_ENABLE_MARKETPLACE === 'true',
    compliance: import.meta.env.VITE_ENABLE_COMPLIANCE === 'true',
  },
  env: import.meta.env.VITE_ENV || 'development',
} as const;
```

---

## CDN Strategy

### Static Asset CDN

**Configuration**: Use CDN for static assets (JS, CSS, images)

**Benefits**:
- Faster load times
- Reduced server load
- Global distribution
- Caching

**Implementation**:
1. Build application
2. Upload to CDN (AWS CloudFront, Cloudflare, etc.)
3. Configure CDN caching rules
4. Update HTML to reference CDN URLs

### CDN Configuration Example

**CloudFront Distribution**:
- Origin: S3 bucket or application server
- Cache behaviors: Different rules for different file types
- Headers: Cache-Control, ETag
- Compression: Gzip/Brotli

---

## Docker Deployment

### Dockerfile

**File**: `Dockerfile`

```dockerfile
# Build stage
FROM node:18-alpine AS builder

WORKDIR /app

# Copy package files
COPY package*.json ./
RUN npm ci

# Copy source code
COPY . .

# Build application
RUN npm run build:production

# Production stage
FROM nginx:alpine

# Copy built files
COPY --from=builder /app/dist /usr/share/nginx/html

# Copy nginx configuration
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Expose port
EXPOSE 80

# Start nginx
CMD ["nginx", "-g", "daemon off;"]
```

### Nginx Configuration

**File**: `nginx.conf`

```nginx
server {
    listen 80;
    server_name _;
    root /usr/share/nginx/html;
    index index.html;

    # Gzip compression
    gzip on;
    gzip_vary on;
    gzip_min_length 1024;
    gzip_types text/plain text/css text/xml text/javascript application/json application/javascript application/xml+rss;

    # Cache static assets
    location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff|woff2|ttf|eot)$ {
        expires 1y;
        add_header Cache-Control "public, immutable";
    }

    # SPA routing
    location / {
        try_files $uri $uri/ /index.html;
    }

    # API proxy (if needed)
    location /api {
        proxy_pass http://backend:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    # WebSocket proxy
    location /ws {
        proxy_pass http://backend:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

### Docker Compose

**File**: `docker-compose.yml`

```yaml
version: '3.8'

services:
  frontend:
    build:
      context: .
      dockerfile: Dockerfile
    ports:
      - "3000:80"
    environment:
      - VITE_API_BASE_URL=http://backend:8000
    depends_on:
      - backend
    networks:
      - app-network

  backend:
    # Backend service configuration
    # ...

networks:
  app-network:
    driver: bridge
```

---

## Kubernetes Deployment

### Deployment Manifest

**File**: `k8s/deployment.yaml`

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: frontend
  namespace: production
spec:
  replicas: 3
  selector:
    matchLabels:
      app: frontend
  template:
    metadata:
      labels:
        app: frontend
    spec:
      containers:
      - name: frontend
        image: datahub/frontend:latest
        ports:
        - containerPort: 80
        env:
        - name: VITE_API_BASE_URL
          valueFrom:
            configMapKeyRef:
              name: frontend-config
              key: api-base-url
        resources:
          requests:
            memory: "128Mi"
            cpu: "100m"
          limits:
            memory: "256Mi"
            cpu: "200m"
        livenessProbe:
          httpGet:
            path: /
            port: 80
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /
            port: 80
          initialDelaySeconds: 5
          periodSeconds: 5
```

### Service Manifest

**File**: `k8s/service.yaml`

```yaml
apiVersion: v1
kind: Service
metadata:
  name: frontend-service
  namespace: production
spec:
  selector:
    app: frontend
  ports:
  - protocol: TCP
    port: 80
    targetPort: 80
  type: LoadBalancer
```

### ConfigMap

**File**: `k8s/configmap.yaml`

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: frontend-config
  namespace: production
data:
  api-base-url: "https://api.datahub.example.com"
  ws-url: "wss://api.datahub.example.com"
```

---

## CI/CD Pipeline

### GitHub Actions Workflow

**File**: `.github/workflows/deploy.yml`

```yaml
name: Deploy Frontend

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

jobs:
  build:
    runs-on: ubuntu-latest
    
    steps:
      - uses: actions/checkout@v3
      
      - name: Setup Node.js
        uses: actions/setup-node@v3
        with:
          node-version: '18'
          cache: 'npm'
      
      - name: Install dependencies
        run: npm ci
      
      - name: Run tests
        run: npm run test:ci
      
      - name: Build application
        run: npm run build:production
        env:
          VITE_API_BASE_URL: ${{ secrets.API_BASE_URL }}
      
      - name: Build Docker image
        run: |
          docker build -t datahub/frontend:${{ github.sha }} .
          docker tag datahub/frontend:${{ github.sha }} datahub/frontend:latest
      
      - name: Push to registry
        run: |
          echo "${{ secrets.DOCKER_PASSWORD }}" | docker login -u "${{ secrets.DOCKER_USERNAME }}" --password-stdin
          docker push datahub/frontend:${{ github.sha }}
          docker push datahub/frontend:latest

  deploy-staging:
    needs: build
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/develop'
    
    steps:
      - name: Deploy to staging
        run: |
          kubectl set image deployment/frontend \
            frontend=datahub/frontend:${{ github.sha }} \
            -n staging

  deploy-production:
    needs: build
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main'
    
    steps:
      - name: Deploy to production
        run: |
          kubectl set image deployment/frontend \
            frontend=datahub/frontend:${{ github.sha }} \
            -n production
```

---

## Version Management

### Version Tagging

**Strategy**: Semantic versioning (MAJOR.MINOR.PATCH)

**Implementation**:
```bash
# Tag release
git tag -a v1.2.3 -m "Release version 1.2.3"
git push origin v1.2.3

# Build with version
docker build -t datahub/frontend:1.2.3 .
docker push datahub/frontend:1.2.3
```

### Version Display

**Component**: `VersionDisplay`

```typescript
export function VersionDisplay() {
  const version = import.meta.env.VITE_APP_VERSION || 'dev';

  return (
    <Typography variant="caption" color="text.secondary">
      Version {version}
    </Typography>
  );
}
```

---

## Feature Flags

### Feature Flag Service

**Service**: `src/lib/features/flags.ts`

```typescript
export interface FeatureFlags {
  marketplace: boolean;
  compliance: boolean;
  advancedSearch: boolean;
}

export function getFeatureFlags(): FeatureFlags {
  return {
    marketplace: import.meta.env.VITE_ENABLE_MARKETPLACE === 'true',
    compliance: import.meta.env.VITE_ENABLE_COMPLIANCE === 'true',
    advancedSearch: import.meta.env.VITE_ENABLE_ADVANCED_SEARCH === 'true',
  };
}

export function isFeatureEnabled(feature: keyof FeatureFlags): boolean {
  const flags = getFeatureFlags();
  return flags[feature] || false;
}
```

### Usage

```typescript
import { isFeatureEnabled } from '@/lib/features/flags';

function App() {
  const showMarketplace = isFeatureEnabled('marketplace');

  return (
    <Routes>
      <Route path="/assets" element={<AssetsPage />} />
      {showMarketplace && (
        <Route path="/marketplace" element={<MarketplacePage />} />
      )}
    </Routes>
  );
}
```

---

## Rollback Strategy

### Automated Rollback

**Kubernetes Rollback**:
```bash
# Rollback to previous deployment
kubectl rollout undo deployment/frontend -n production

# Rollback to specific revision
kubectl rollout undo deployment/frontend --to-revision=2 -n production
```

### Manual Rollback

1. **Identify Issue**: Monitor error rates, user reports
2. **Revert Code**: Revert to previous working version
3. **Rebuild**: Build previous version
4. **Deploy**: Deploy previous version
5. **Verify**: Verify application is working

### Health Checks

**Implementation**: Health check endpoint

```typescript
// Health check route
app.get('/health', (req, res) => {
  res.json({
    status: 'healthy',
    version: process.env.VITE_APP_VERSION,
    timestamp: new Date().toISOString(),
  });
});
```

---

## Best Practices

1. **Version Everything**: Tag all releases
2. **Test Before Deploy**: Run tests in CI/CD
3. **Gradual Rollout**: Use canary deployments
4. **Monitor Deployments**: Monitor after deployment
5. **Rollback Plan**: Always have a rollback plan
6. **Environment Parity**: Keep environments similar
7. **Secure Secrets**: Use secrets management
8. **CDN Caching**: Use CDN for static assets
9. **Health Checks**: Implement health checks
10. **Documentation**: Document deployment process

---

**Last Updated**: 2025-12-13  
**Version**: 1.0.0

