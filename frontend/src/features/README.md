# Features

This directory contains feature modules that encapsulate complete functionality.

## Purpose

Features are self-contained modules that include all components, hooks, types, and logic related to a specific feature or domain area.

## Guidelines

- **Self-contained**: Each feature should be independent and reusable
- **Co-location**: Keep related code together (components, hooks, types, utils)
- **Public API**: Export only what's needed by other features
- **Testing**: Each feature should have comprehensive tests
- **Documentation**: Each feature should have a README explaining its purpose and usage

## Structure

Each feature should follow this structure:

```
FeatureName/
  ├── components/          # Feature-specific components
  │   ├── FeatureComponent.tsx
  │   └── index.ts
  ├── hooks/              # Feature-specific hooks
  │   ├── useFeature.ts
  │   └── index.ts
  ├── api/                # Feature-specific API calls
  │   ├── queries.ts
  │   ├── mutations.ts
  │   └── index.ts
  ├── types/              # Feature-specific types
  │   └── index.ts
  ├── utils/              # Feature-specific utilities
  │   └── index.ts
  ├── FeatureName.tsx     # Main feature component (if applicable)
  ├── index.ts            # Public API exports
  └── README.md           # Feature documentation
```

## Examples

Feature modules might include:
- Authentication
- User Profile
- Data Catalog
- Marketplace
- Compliance
- Data Quality
- Search
- Governance

## Usage

```tsx
import { UserProfile, useUserProfile } from '@/features/user-profile'

function MyPage() {
  const { user, isLoading } = useUserProfile()

  return <UserProfile user={user} />
}
```

## Best Practices

1. **Keep features independent**: Avoid circular dependencies between features
2. **Use shared components**: Use common components from `@/components/common`
3. **Type safety**: Export types for use by other features
4. **Error handling**: Handle errors within the feature
5. **Loading states**: Provide loading and error states

