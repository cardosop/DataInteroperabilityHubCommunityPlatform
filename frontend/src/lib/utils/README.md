# Utility Functions

This directory contains reusable utility functions.

## Purpose

Shared utility functions used across the application:
- Data manipulation
- Formatting functions
- Validation utilities
- Type guards
- Helper functions

## Guidelines

- **Pure functions**: Prefer pure, side-effect-free functions
- **Type safety**: All functions must be fully typed
- **Documentation**: Each function should have JSDoc comments
- **Testing**: All utilities should have unit tests
- **Performance**: Optimize for performance when needed

## Structure

Organize utilities by category:

```
utils/
├── date.ts           # Date formatting and manipulation
├── string.ts         # String utilities
├── array.ts          # Array utilities
├── object.ts         # Object utilities
├── validation.ts     # Validation functions
├── format.ts         # Formatting functions
└── index.ts          # Public exports
```

## Usage

```tsx
import { formatDate, debounce, cn } from '@/lib/utils'

const formatted = formatDate(new Date())
const debouncedFn = debounce(() => {}, 300)
const className = cn('base-class', condition && 'conditional-class')
```

## Best Practices

1. **Single responsibility**: Each function should do one thing
2. **Immutability**: Don't mutate input parameters
3. **Error handling**: Handle edge cases gracefully
4. **Performance**: Consider performance for frequently used functions
5. **Tree-shaking**: Export individual functions for better tree-shaking

