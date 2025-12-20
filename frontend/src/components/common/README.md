# Common Components

This directory contains common, reusable UI components that are used throughout the application.

## Purpose

Common components are generic, reusable UI elements that don't have specific business logic. They are the building blocks for more complex components and features.

## Guidelines

- **Reusability**: Components should be generic and reusable across different contexts
- **Composition**: Build complex components from simple common components
- **Props**: Use clear, well-typed props with sensible defaults
- **Documentation**: Each component should have JSDoc comments and Storybook stories
- **Accessibility**: All components must be accessible (ARIA attributes, keyboard navigation)

## Structure

Each component should follow this structure:

```
ComponentName/
  ├── ComponentName.tsx      # Component implementation
  ├── ComponentName.stories.tsx  # Storybook stories
  ├── ComponentName.test.tsx      # Component tests
  ├── index.ts               # Public exports
  └── README.md              # Component-specific documentation (optional)
```

## Examples

Common components include:
- Buttons
- Inputs
- Cards
- Badges
- Avatars
- Icons
- Loading indicators
- Tooltips
- Modals

## Usage

```tsx
import { Button } from '@/components/common'

function MyComponent() {
  return <Button variant="primary">Click me</Button>
}
```

