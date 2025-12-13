# Performance Optimization Guide

**Last Updated**: 2025-12-13  
**Version**: 1.0.0

---

## Table of Contents

1. [Overview](#overview)
2. [Performance Targets](#performance-targets)
3. [Code Splitting](#code-splitting)
4. [Lazy Loading](#lazy-loading)
5. [Image Optimization](#image-optimization)
6. [Bundle Optimization](#bundle-optimization)
7. [Caching Strategies](#caching-strategies)
8. [Virtual Scrolling](#virtual-scrolling)
9. [Memoization](#memoization)
10. [Performance Monitoring](#performance-monitoring)

---

## Overview

This document outlines performance optimization strategies for the frontend application. The goal is to achieve fast load times, smooth interactions, and efficient resource usage.

**Performance Principles**:
- **Fast Initial Load**: First Contentful Paint < 1.5s
- **Interactive Quickly**: Time to Interactive < 3s
- **Smooth Interactions**: 60fps animations
- **Efficient Updates**: Minimal re-renders
- **Optimized Assets**: Compressed images, minified code

**Key Metrics**:
- **Lighthouse Score**: 90+ (Performance)
- **First Contentful Paint (FCP)**: < 1.5s
- **Largest Contentful Paint (LCP)**: < 2.5s
- **Time to Interactive (TTI)**: < 3s
- **Cumulative Layout Shift (CLS)**: < 0.1
- **First Input Delay (FID)**: < 100ms

---

## Performance Targets

### Load Time Targets

- **Initial Load**: < 2s
- **Route Navigation**: < 500ms
- **API Response**: < 300ms (P95)
- **Image Load**: < 1s

### Runtime Performance Targets

- **Frame Rate**: 60fps
- **Component Render**: < 16ms
- **List Scroll**: Smooth, no jank
- **Form Input**: < 50ms response time

### Bundle Size Targets

- **Initial Bundle**: < 200KB (gzipped)
- **Total Bundle**: < 500KB (gzipped)
- **Route Chunks**: < 50KB each (gzipped)
- **Vendor Bundle**: < 150KB (gzipped)

---

## Code Splitting

### Route-Based Code Splitting

**Implementation**: `src/routes/index.tsx`

```typescript
import { lazy } from 'react';
import { Route, Routes } from 'react-router-dom';

// Lazy load routes
const AssetsPage = lazy(() => import('@/pages/AssetsPage'));
const ContractsPage = lazy(() => import('@/pages/ContractsPage'));
const MarketplacePage = lazy(() => import('@/pages/MarketplacePage'));
const CompliancePage = lazy(() => import('@/pages/CompliancePage'));

export function AppRoutes() {
  return (
    <Suspense fallback={<PageLoader />}>
      <Routes>
        <Route path="/assets" element={<AssetsPage />} />
        <Route path="/contracts" element={<ContractsPage />} />
        <Route path="/marketplace" element={<MarketplacePage />} />
        <Route path="/compliance" element={<CompliancePage />} />
      </Routes>
    </Suspense>
  );
}
```

### Component-Based Code Splitting

**Implementation**: `src/components/LazyComponents.tsx`

```typescript
import { lazy } from 'react';

// Heavy components loaded on demand
export const ContractEditor = lazy(() => import('./ContractEditor'));
export const DataQualityDashboard = lazy(() => import('./DataQualityDashboard'));
export const ComplianceReport = lazy(() => import('./ComplianceReport'));

// Usage with Suspense
<Suspense fallback={<ComponentLoader />}>
  <ContractEditor contractId={id} />
</Suspense>
```

### Library Splitting

**Implementation**: `vite.config.ts`

```typescript
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  build: {
    rollupOptions: {
      output: {
        manualChunks: {
          'react-vendor': ['react', 'react-dom', 'react-router-dom'],
          'mui-vendor': ['@mui/material', '@mui/icons-material'],
          'query-vendor': ['@tanstack/react-query'],
          'graphql-vendor': ['graphql', 'graphql-request'],
        },
      },
    },
  },
});
```

---

## Lazy Loading

### Image Lazy Loading

**Component**: `LazyImage`

```typescript
interface LazyImageProps {
  src: string;
  alt: string;
  width?: number;
  height?: number;
  placeholder?: string;
}

export function LazyImage({
  src,
  alt,
  width,
  height,
  placeholder,
}: LazyImageProps) {
  const [loaded, setLoaded] = useState(false);
  const [error, setError] = useState(false);

  return (
    <Box
      sx={{
        width,
        height,
        position: 'relative',
        backgroundColor: 'grey.200',
      }}
    >
      {!loaded && placeholder && (
        <img
          src={placeholder}
          alt=""
          style={{
            position: 'absolute',
            width: '100%',
            height: '100%',
            objectFit: 'cover',
          }}
        />
      )}
      <img
        src={src}
        alt={alt}
        loading="lazy"
        onLoad={() => setLoaded(true)}
        onError={() => setError(true)}
        style={{
          width: '100%',
          height: '100%',
          objectFit: 'cover',
          opacity: loaded ? 1 : 0,
          transition: 'opacity 0.3s',
        }}
      />
      {error && (
        <Box
          sx={{
            position: 'absolute',
            inset: 0,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}
        >
          <Typography variant="body2" color="error">
            Failed to load image
          </Typography>
        </Box>
      )}
    </Box>
  );
}
```

### Component Lazy Loading with Intersection Observer

**Hook**: `useIntersectionObserver`

```typescript
export function useIntersectionObserver(
  ref: RefObject<HTMLElement>,
  options?: IntersectionObserverInit
) {
  const [isIntersecting, setIsIntersecting] = useState(false);

  useEffect(() => {
    const element = ref.current;
    if (!element) return;

    const observer = new IntersectionObserver(([entry]) => {
      setIsIntersecting(entry.isIntersecting);
    }, options);

    observer.observe(element);

    return () => {
      observer.unobserve(element);
    };
  }, [ref, options]);

  return isIntersecting;
}
```

**Usage**:
```typescript
function AssetList() {
  const loadMoreRef = useRef<HTMLDivElement>(null);
  const isIntersecting = useIntersectionObserver(loadMoreRef);

  useEffect(() => {
    if (isIntersecting && hasNextPage) {
      fetchNextPage();
    }
  }, [isIntersecting, hasNextPage, fetchNextPage]);

  return (
    <>
      {assets.map(asset => <AssetCard key={asset.id} asset={asset} />)}
      <div ref={loadMoreRef} />
    </>
  );
}
```

---

## Image Optimization

### Image Optimization Strategy

1. **Format Selection**:
   - Use WebP with fallback to JPEG/PNG
   - Use SVG for icons and simple graphics
   - Use responsive images with `srcset`

2. **Compression**:
   - Compress images before upload
   - Use CDN for image delivery
   - Serve different sizes for different viewports

3. **Lazy Loading**:
   - Load images only when visible
   - Use placeholder images
   - Progressive image loading

**Component**: `OptimizedImage`

```typescript
interface OptimizedImageProps {
  src: string;
  alt: string;
  width: number;
  height: number;
  sizes?: string;
  srcSet?: string;
}

export function OptimizedImage({
  src,
  alt,
  width,
  height,
  sizes,
  srcSet,
}: OptimizedImageProps) {
  return (
    <picture>
      <source srcSet={srcSet} type="image/webp" />
      <img
        src={src}
        alt={alt}
        width={width}
        height={height}
        sizes={sizes}
        loading="lazy"
        decoding="async"
      />
    </picture>
  );
}
```

---

## Bundle Optimization

### Tree Shaking

**Configuration**: `vite.config.ts`

```typescript
export default defineConfig({
  build: {
    rollupOptions: {
      treeshake: {
        moduleSideEffects: false,
      },
    },
  },
});
```

### Import Optimization

**Bad**:
```typescript
import * as MUI from '@mui/material';
```

**Good**:
```typescript
import { Button, TextField } from '@mui/material';
```

### Dynamic Imports

**Implementation**:
```typescript
// Load heavy library only when needed
const loadChartLibrary = async () => {
  const { Chart } = await import('chart.js');
  return Chart;
};

// Usage
const Chart = await loadChartLibrary();
```

---

## Caching Strategies

### React Query Caching

**Configuration**:
```typescript
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 5 * 60 * 1000, // 5 minutes
      cacheTime: 10 * 60 * 1000, // 10 minutes
    },
  },
});
```

### Browser Caching

**Service Worker**: `public/sw.js`

```javascript
const CACHE_NAME = 'datahub-v1';
const urlsToCache = [
  '/',
  '/static/css/main.css',
  '/static/js/main.js',
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll(urlsToCache);
    })
  );
});

self.addEventListener('fetch', (event) => {
  event.respondWith(
    caches.match(event.request).then((response) => {
      return response || fetch(event.request);
    })
  );
});
```

---

## Virtual Scrolling

### Virtual List Component

**Component**: `VirtualList`

```typescript
import { useVirtualizer } from '@tanstack/react-virtual';

interface VirtualListProps<T> {
  items: T[];
  itemHeight: number;
  renderItem: (item: T, index: number) => React.ReactNode;
}

export function VirtualList<T>({
  items,
  itemHeight,
  renderItem,
}: VirtualListProps<T>) {
  const parentRef = useRef<HTMLDivElement>(null);

  const virtualizer = useVirtualizer({
    count: items.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => itemHeight,
    overscan: 5,
  });

  return (
    <div
      ref={parentRef}
      style={{
        height: '600px',
        overflow: 'auto',
      }}
    >
      <div
        style={{
          height: `${virtualizer.getTotalSize()}px`,
          width: '100%',
          position: 'relative',
        }}
      >
        {virtualizer.getVirtualItems().map((virtualItem) => (
          <div
            key={virtualItem.key}
            style={{
              position: 'absolute',
              top: 0,
              left: 0,
              width: '100%',
              height: `${virtualItem.size}px`,
              transform: `translateY(${virtualItem.start}px)`,
            }}
          >
            {renderItem(items[virtualItem.index], virtualItem.index)}
          </div>
        ))}
      </div>
    </div>
  );
}
```

**Usage**:
```typescript
<VirtualList
  items={assets}
  itemHeight={100}
  renderItem={(asset, index) => (
    <AssetCard key={asset.id} asset={asset} />
  )}
/>
```

---

## Memoization

### React.memo

**Usage**:
```typescript
export const AssetCard = React.memo(function AssetCard({
  asset,
  onEdit,
}: AssetCardProps) {
  return (
    <Card>
      <CardContent>
        <Typography>{asset.name}</Typography>
        <Button onClick={() => onEdit(asset.id)}>Edit</Button>
      </CardContent>
    </Card>
  );
}, (prevProps, nextProps) => {
  // Custom comparison
  return (
    prevProps.asset.id === nextProps.asset.id &&
    prevProps.asset.name === nextProps.asset.name
  );
});
```

### useMemo

**Usage**:
```typescript
function AssetList({ assets, filters }: AssetListProps) {
  const filteredAssets = useMemo(() => {
    return assets.filter(asset => {
      if (filters.status && asset.status !== filters.status) {
        return false;
      }
      if (filters.search && !asset.name.includes(filters.search)) {
        return false;
      }
      return true;
    });
  }, [assets, filters]);

  return (
    <div>
      {filteredAssets.map(asset => (
        <AssetCard key={asset.id} asset={asset} />
      ))}
    </div>
  );
}
```

### useCallback

**Usage**:
```typescript
function AssetCard({ asset, onEdit }: AssetCardProps) {
  const handleEdit = useCallback(() => {
    onEdit(asset.id);
  }, [asset.id, onEdit]);

  return (
    <Card>
      <Button onClick={handleEdit}>Edit</Button>
    </Card>
  );
}
```

---

## Performance Monitoring

### Web Vitals Monitoring

**Implementation**: `src/lib/performance/vitals.ts`

```typescript
import { onCLS, onFID, onFCP, onLCP, onTTFB } from 'web-vitals';

function sendToAnalytics(metric: any) {
  // Send to analytics service
  console.log(metric);
}

export function trackWebVitals() {
  onCLS(sendToAnalytics);
  onFID(sendToAnalytics);
  onFCP(sendToAnalytics);
  onLCP(sendToAnalytics);
  onTTFB(sendToAnalytics);
}
```

### Performance Monitoring Hook

**Hook**: `usePerformanceMonitoring`

```typescript
export function usePerformanceMonitoring() {
  useEffect(() => {
    // Monitor component render time
    const observer = new PerformanceObserver((list) => {
      for (const entry of list.getEntries()) {
        if (entry.entryType === 'measure') {
          console.log(`${entry.name}: ${entry.duration}ms`);
        }
      }
    });

    observer.observe({ entryTypes: ['measure'] });

    return () => {
      observer.disconnect();
    };
  }, []);
}
```

### Bundle Analysis

**Tool**: `vite-bundle-visualizer`

**Configuration**:
```typescript
import { visualizer } from 'rollup-plugin-visualizer';

export default defineConfig({
  plugins: [
    react(),
    visualizer({
      open: true,
      gzipSize: true,
      brotliSize: true,
    }),
  ],
});
```

---

## Best Practices

1. **Code Split by Route**: Split code at route level
2. **Lazy Load Heavy Components**: Load on demand
3. **Optimize Images**: Use WebP, compress, lazy load
4. **Minimize Bundle Size**: Tree shake, optimize imports
5. **Use Memoization**: Memoize expensive computations
6. **Virtual Scrolling**: For long lists
7. **Cache Aggressively**: Cache API responses
8. **Monitor Performance**: Track Web Vitals
9. **Optimize Fonts**: Use font-display: swap
10. **Preload Critical Resources**: Preload key assets

---

**Last Updated**: 2025-12-13  
**Version**: 1.0.0

