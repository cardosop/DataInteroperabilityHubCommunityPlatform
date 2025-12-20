# Loading Patterns

Comprehensive loading patterns for the Data Interoperability Hub platform.

## Overview

This module provides:
- **Skeleton Screens**: Text, Image, Table, and Card skeletons
- **Progressive Loading**: Load critical content first, then non-critical
- **Lazy Loading**: Images, components, and routes
- **Loading States**: Spinners, progress bars with percentage

## Skeleton Screens

### TextSkeleton

```tsx
import { TextSkeleton } from '@/components/loading'

<TextSkeleton lines={3} width="100%" />
<TextSkeleton lines={4} width={['100%', '80%', '90%', '60%']} />
```

### ImageSkeleton

```tsx
import { ImageSkeleton } from '@/components/loading'

<ImageSkeleton width="100%" height="200px" aspectRatio="16/9" />
<ImageSkeleton width={100} height={100} circular />
```

### TableSkeleton

```tsx
import { TableSkeleton } from '@/components/loading'

<TableSkeleton rows={5} columns={4} showHeader />
```

### CardSkeleton

```tsx
import { CardSkeleton } from '@/components/loading'

<CardSkeleton
  showHeader
  showImage
  contentLines={3}
  showActions
/>
```

## Progressive Loading

Load critical content first, then non-critical content:

```tsx
import { useProgressiveLoading } from '@/components/loading'

const { critical, nonCritical, loadingCritical, loadingNonCritical } =
  useProgressiveLoading({
    loadCritical: async () => {
      // Load essential data first
      return await fetchCriticalData()
    },
    loadNonCritical: async () => {
      // Load secondary data after delay
      return await fetchNonCriticalData()
    },
    nonCriticalDelay: 500, // Wait 500ms before loading non-critical
  })

if (loadingCritical) return <LoadingSpinner />
if (!critical) return <ErrorState />

return (
  <div>
    <CriticalContent data={critical} />
    {loadingNonCritical ? (
      <LoadingSpinner />
    ) : (
      <NonCriticalContent data={nonCritical} />
    )}
  </div>
)
```

## Lazy Loading

### Lazy Images

```tsx
import { LazyImage } from '@/components/loading'

<LazyImage
  src="/large-image.jpg"
  alt="Description"
  placeholder="/placeholder.jpg"
  rootMargin="100px"
  showSkeleton
  skeletonWidth="100%"
  skeletonHeight="400px"
/>
```

### Lazy Components

```tsx
import { LazyComponent, createLazyComponent } from '@/components/loading'

// Option 1: Using LazyComponent wrapper
const HeavyComponent = createLazyComponent(() => import('./HeavyComponent'))

<LazyComponent
  component={HeavyComponent}
  fallback={<LoadingSpinner />}
/>

// Option 2: Direct usage with Suspense
const HeavyComponent = React.lazy(() => import('./HeavyComponent'))

<Suspense fallback={<LoadingSpinner />}>
  <HeavyComponent />
</Suspense>
```

### Lazy Routes

```tsx
import { createLazyRoute } from '@/components/loading'

const HomePage = createLazyRoute(() => import('@/pages/Home'))
const AssetsPage = createLazyRoute(() => import('@/pages/Assets'))
```

## Loading States

### With Percentage

```tsx
import { LoadingState } from '@/components/loading'

<LoadingState
  variant="progress"
  progress={75}
  message="Uploading file..."
  showPercentage
/>

<LoadingState
  variant="circular"
  progress={50}
  message="Processing..."
  showPercentage
/>
```

### Spinner Variants

```tsx
<LoadingState variant="spinner" message="Loading..." />
<LoadingState variant="spinner" fullPage message="Loading page..." />
```

## Best Practices

1. **Use skeletons for perceived performance** - Show skeleton screens immediately
2. **Progressive loading** - Load critical content first, defer non-critical
3. **Lazy load images** - Use Intersection Observer for images below the fold
4. **Code splitting** - Lazy load routes and heavy components
5. **Show progress** - Use progress bars with percentage for long operations
6. **Error handling** - Always handle loading errors gracefully

## Examples

### Complete Page with Progressive Loading

```tsx
import { useProgressiveLoading } from '@/components/loading'
import { TextSkeleton, CardSkeleton } from '@/components/loading'

function AssetPage() {
  const { critical, loadingCritical, loadingNonCritical } =
    useProgressiveLoading({
      loadCritical: () => fetchAssetDetails(),
      loadNonCritical: () => fetchRelatedAssets(),
    })

  if (loadingCritical) {
    return <CardSkeleton showHeader showImage contentLines={5} />
  }

  return (
    <div>
      <AssetDetails data={critical} />
      {loadingNonCritical ? (
        <TextSkeleton lines={3} />
      ) : (
        <RelatedAssets data={nonCritical} />
      )}
    </div>
  )
}
```

### Image Gallery with Lazy Loading

```tsx
import { LazyImage } from '@/components/loading'

function ImageGallery({ images }) {
  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)' }}>
      {images.map((img) => (
        <LazyImage
          key={img.id}
          src={img.url}
          alt={img.alt}
          skeletonAspectRatio="1/1"
          showSkeleton
        />
      ))}
    </div>
  )
}
```

