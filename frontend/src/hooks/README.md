# Custom React Hooks

This directory contains reusable custom React hooks.

## Purpose

Custom hooks encapsulate reusable logic and state management that can be shared across components.

## Guidelines

- **Single Responsibility**: Each hook should have a clear, single purpose
- **Reusability**: Hooks should be generic enough to be used in multiple contexts
- **Type Safety**: All hooks must have TypeScript types
- **Documentation**: Each hook should have JSDoc comments
- **Testing**: All hooks should have unit tests

## Structure

Each hook should follow this structure:

```
useHookName.ts
```

Or for complex hooks with utilities:

```
useHookName/
  ├── useHookName.ts       # Hook implementation
  ├── useHookName.test.ts  # Hook tests
  ├── utils.ts             # Hook-specific utilities (if needed)
  └── index.ts             # Public exports
```

## Existing Hooks

- **useMediaQuery**: Responsive breakpoint detection
- **useTouch**: Touch event handling

## Usage

```tsx
import { useMediaQuery } from '@/hooks'

function MyComponent() {
  const isMobile = useMediaQuery('(max-width: 768px)')

  return isMobile ? <MobileView /> : <DesktopView />
}
```

## Best Practices

1. **Naming**: Always prefix hooks with `use`
2. **Return values**: Return objects for multiple values, arrays for pairs
3. **Dependencies**: Properly handle dependency arrays
4. **Cleanup**: Clean up side effects in useEffect return functions
5. **Error handling**: Handle errors appropriately

## Testing

Test hooks using `@testing-library/react-hooks`:

```tsx
import { renderHook } from '@testing-library/react'
import { useMyHook } from './useMyHook'

test('hook works correctly', () => {
  const { result } = renderHook(() => useMyHook())
  expect(result.current).toBeDefined()
})
```

