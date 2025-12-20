# Type Definitions

This directory contains shared TypeScript type definitions.

## Purpose

Centralized type definitions for:
- API types
- Domain models
- Shared interfaces
- Utility types
- Type guards

## Guidelines

- **Organization**: Group related types together
- **Reusability**: Types should be reusable across features
- **Documentation**: Document complex types
- **Naming**: Use clear, descriptive names
- **Exports**: Export types for use across the application

## Structure

```
types/
├── api.ts            # API request/response types
├── domain.ts         # Domain model types
├── common.ts         # Common shared types
├── utils.ts          # Utility types
└── index.ts          # Public exports
```

## Usage

```tsx
import type { User, ApiResponse } from '@/types'

function MyComponent({ user }: { user: User }) {
  // Component implementation
}
```

## Best Practices

1. **Co-location**: Keep feature-specific types in features
2. **Shared types**: Only put truly shared types here
3. **Type guards**: Include type guard functions
4. **Documentation**: Document complex types with JSDoc
5. **Naming**: Use PascalCase for types, interfaces, and enums

