# Directory Structure

This document describes the directory structure of the Data Interoperability Hub frontend application.

## Overview

The project follows a feature-based architecture with clear separation of concerns:

```
frontend/
├── src/                    # Source code
│   ├── components/         # Reusable UI components
│   ├── features/           # Feature modules
│   ├── hooks/              # Custom React hooks
│   ├── lib/                # Utility libraries
│   ├── pages/              # Page components
│   ├── routes/             # Route configuration
│   ├── store/              # State management
│   ├── styles/             # Global styles and themes
│   ├── types/              # TypeScript type definitions
│   └── test-utils/         # Testing utilities
├── tests/                  # Test files
│   ├── unit/               # Unit tests
│   ├── component/          # Component tests
│   └── e2e/                # End-to-end tests
└── playwright/             # Playwright E2E tests
```

## Source Directory (`src/`)

### Components (`src/components/`)

Reusable UI components organized by category:

- **`common/`** - Generic, reusable UI components (buttons, inputs, cards, etc.)
- **`layout/`** - Layout components (containers, grids, stacks, etc.)
- **`navigation/`** - Navigation components (headers, sidebars, breadcrumbs, etc.)
- **`forms/`** - Form components (inputs, selects, checkboxes, etc.)

Each component should have:
- Component file (`.tsx`)
- Storybook stories (`.stories.tsx`)
- Tests (`.test.tsx`)
- Index file (`index.ts`)

### Features (`src/features/`)

Self-contained feature modules that encapsulate complete functionality. Each feature includes:
- Components specific to the feature
- Hooks for feature logic
- API calls and data fetching
- Types and interfaces
- Utilities

### Hooks (`src/hooks/`)

Custom React hooks for reusable logic:
- `useMediaQuery.ts` - Responsive breakpoint detection
- `useTouch.ts` - Touch event handling

### Library (`src/lib/`)

Utility libraries and infrastructure code:

- **`api/`** - API client, WebSocket, GraphQL setup
- **`analytics/`** - Analytics integration (Google Analytics, Sentry)
- **`config/`** - Application configuration
- **`i18n/`** - Internationalization utilities
- **`utils/`** - Utility functions

### Pages (`src/pages/`)

Page-level components that represent full routes. Each page:
- Maps to a route
- Composes features and components
- Handles page-level state and data fetching

### Routes (`src/routes/`)

Route configuration and routing utilities:
- Route definitions
- Route guards (authentication, permissions)
- Lazy-loaded route components
- Navigation utilities

### Store (`src/store/`)

Global state management (Redux, Zustand, or other):
- Store configuration
- Slices/stores for different domains
- Middleware
- Typed hooks

### Styles (`src/styles/`)

Global styles and design tokens:
- **`tokens/`** - Design tokens (colors, spacing, typography, etc.)
- Global CSS files
- Theme configuration

### Types (`src/types/`)

Shared TypeScript type definitions:
- API types
- Domain models
- Shared interfaces
- Utility types

### Test Utils (`src/test-utils/`)

Testing utilities and helpers:
- Custom render function with providers
- Mock factories
- Test helpers
- Fixtures

## Test Directory (`tests/`)

Organized by test type:

- **`unit/`** - Unit tests for functions and utilities
- **`component/`** - Component tests using React Testing Library
- **`e2e/`** - End-to-end tests

## Playwright (`playwright/`)

Playwright E2E test configuration and tests:
- Test files
- Page Object Models
- Test utilities
- Configuration (in `playwright.config.ts` at root)

## Guidelines

### File Organization

1. **Co-location**: Keep related files together
2. **Index files**: Use `index.ts` for clean imports
3. **Naming**: Use PascalCase for components, camelCase for utilities
4. **Exports**: Export only what's needed publicly

### Import Paths

Use path aliases for clean imports:

```tsx
import { Button } from '@/components/common'
import { useMediaQuery } from '@/hooks'
import { apiClient } from '@/lib/api'
import type { User } from '@/types'
```

### Adding New Code

1. **Components**: Add to appropriate category in `src/components/`
2. **Features**: Create new feature directory in `src/features/`
3. **Utilities**: Add to `src/lib/utils/` or feature-specific utils
4. **Types**: Add to `src/types/` if shared, or feature-specific types
5. **Tests**: Mirror source structure in `tests/`

## Documentation

Each major directory has a `README.md` file explaining:
- Purpose and guidelines
- Structure
- Usage examples
- Best practices

## See Also

- [Component Guidelines](.storybook/ComponentGuidelines.mdx)
- [Testing Documentation](tests/README.md)
- [Playwright Documentation](playwright/README.md)

