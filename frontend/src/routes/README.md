# Routes

This directory contains route configuration and routing utilities.

## Purpose

Centralized route configuration for:
- Route definitions
- Route guards
- Lazy loading
- Route metadata
- Navigation utilities

## Structure

```
routes/
├── index.tsx          # Main route configuration
├── guards.tsx         # Route guards (auth, permissions)
├── lazy.tsx           # Lazy-loaded route components
├── types.ts           # Route types
└── utils.ts           # Routing utilities
```

## Guidelines

- **Centralized**: All routes defined in one place
- **Type safety**: Use typed routes
- **Lazy loading**: Lazy load routes for code splitting
- **Guards**: Use route guards for authentication and permissions
- **Documentation**: Document route structure and requirements

## Usage

```tsx
import { routes } from '@/routes'
import { useNavigate, useParams } from '@/routes/utils'

// In App.tsx or router setup
<Router>
  {routes}
</Router>
```

## Best Practices

1. **Code splitting**: Lazy load routes for better performance
2. **Route guards**: Protect routes with authentication/permission guards
3. **Type safety**: Use typed route parameters
4. **404 handling**: Provide proper 404 handling
5. **Redirects**: Handle redirects appropriately

