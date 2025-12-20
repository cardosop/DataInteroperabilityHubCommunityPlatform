# Pages

This directory contains page-level components that represent full routes.

## Purpose

Pages are top-level components that:
- Represent complete routes
- Compose features and components
- Handle page-level state and data fetching
- Define page-specific layouts

## Guidelines

- **Route mapping**: Each page should map to a route
- **Composition**: Pages should compose features and components
- **Data fetching**: Handle page-level data fetching
- **Layout**: Define page-specific layouts
- **Documentation**: Each page should have clear purpose documentation

## Structure

Each page should follow this structure:

```
PageName/
  ├── PageName.tsx         # Page component
  ├── PageName.stories.tsx # Storybook stories (if applicable)
  ├── PageName.test.tsx    # Page tests
  ├── components/          # Page-specific components (if any)
  └── index.ts             # Public exports
```

## Examples

Pages might include:
- Home
- Login
- Dashboard
- User Profile
- Data Catalog
- Settings

## Usage

```tsx
import { HomePage } from '@/pages/home'
import { DashboardPage } from '@/pages/dashboard'

// In routes configuration
<Route path="/" element={<HomePage />} />
<Route path="/dashboard" element={<DashboardPage />} />
```

## Best Practices

1. **Keep pages thin**: Move logic to features and hooks
2. **Composition**: Compose features rather than duplicating code
3. **Error boundaries**: Use error boundaries for page-level error handling
4. **Loading states**: Provide loading states for async operations
5. **SEO**: Consider SEO for public pages

