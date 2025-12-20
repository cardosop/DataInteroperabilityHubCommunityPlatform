# Layout Components

This directory contains layout components used for structuring page layouts and organizing content.

## Purpose

Layout components provide structure and spacing for pages and sections. They handle responsive design, grid systems, and content organization.

## Guidelines

- **Responsive**: All layout components must be responsive
- **Semantic HTML**: Use semantic HTML elements where appropriate
- **Flexibility**: Support various content types and sizes
- **Spacing**: Follow design system spacing tokens
- **Documentation**: Each component should have Storybook stories with viewport variants

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

## Existing Components

- **Container**: Wraps content with max-width and padding
- **Grid**: Responsive grid system
- **Stack**: Vertical/horizontal stacking with spacing
- **Divider**: Visual separators
- **Spacer**: Flexible spacing component
- **ResponsiveGrid**: Grid with responsive breakpoints
- **ResponsiveImage**: Image with responsive sizing
- **ResponsiveTypography**: Typography with responsive sizing

## Usage

```tsx
import { Container, Stack, Grid } from '@/components/layout'

function MyPage() {
  return (
    <Container>
      <Stack spacing={2}>
        <Grid columns={12} gap={2}>
          {/* Content */}
        </Grid>
      </Stack>
    </Container>
  )
}
```

