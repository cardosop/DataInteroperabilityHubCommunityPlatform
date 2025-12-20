# Library Modules

This directory contains utility libraries and shared infrastructure code.

## Structure

```
lib/
├── api/           # API client, WebSocket, GraphQL
├── analytics/     # Analytics integration
├── config/        # Configuration modules
├── i18n/          # Internationalization
└── utils/         # Utility functions
```

## Purpose

The `lib` directory contains:
- **Infrastructure code**: Code that supports the application but isn't UI-specific
- **Third-party integrations**: Wrappers around external libraries
- **Shared utilities**: Functions used across the application
- **Configuration**: App-wide configuration and setup

## Guidelines

- **No UI**: This directory should not contain React components
- **Pure functions**: Prefer pure functions where possible
- **Type safety**: All code must be fully typed
- **Documentation**: Each module should have clear documentation
- **Testing**: All utilities should have unit tests

## Usage

```tsx
import { apiClient } from '@/lib/api'
import { trackEvent } from '@/lib/analytics'
import { formatDate } from '@/lib/utils'
```

