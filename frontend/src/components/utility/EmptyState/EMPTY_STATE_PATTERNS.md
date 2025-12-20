# Empty State Patterns

This document describes the empty state patterns implemented for the Data Interoperability Hub frontend.

## Table of Contents

1. [Overview](#overview)
2. [Contextual Empty States](#contextual-empty-states)
3. [Empty State with CTA](#empty-state-with-cta)
4. [Empty State Illustrations](#empty-state-illustrations)
5. [Empty State with Help Text](#empty-state-with-help-text)
6. [Usage Examples](#usage-examples)
7. [Best Practices](#best-practices)

## Overview

Empty states are crucial for guiding users when there's no data to display. They provide:
- Clear messaging about why the state is empty
- Visual illustrations to make the state more engaging
- Call-to-action buttons to guide next steps
- Help text and links for additional guidance

## Contextual Empty States

Predefined empty states for common scenarios with appropriate illustrations and messaging.

### Available Contexts

- **`no-data`** - No data available (e.g., empty table)
- **`no-results`** - Search/filter returned no results
- **`no-items`** - Empty list
- **`no-files`** - No files or documents
- **`no-connections`** - No connections or integrations
- **`error`** - Error state
- **`custom`** - Fully customizable

### Usage

#### Using Predefined Contextual Components

```tsx
import {
  NoDataEmptyState,
  NoResultsEmptyState,
  NoItemsEmptyState,
} from '@/components/utility/EmptyState'

// No data
<NoDataEmptyState
  primaryAction={{
    label: 'Create Asset',
    onClick: () => navigate('/assets/create'),
    primary: true,
  }}
/>

// No search results
<NoResultsEmptyState
  secondaryActions={[
    {
      label: 'Clear Filters',
      onClick: () => clearFilters(),
    },
    {
      label: 'View All',
      onClick: () => showAll(),
    },
  ]}
/>

// No items
<NoItemsEmptyState
  primaryAction={{
    label: 'Add Item',
    onClick: () => openAddDialog(),
  }}
  helpLinks={[
    { text: 'Learn more', href: '/docs/items' },
    { text: 'View examples', href: '/examples', external: true },
  ]}
/>
```

#### Using EnhancedEmptyState with Context

```tsx
import { EnhancedEmptyState } from '@/components/utility/EmptyState'

<EnhancedEmptyState
  context="no-data"
  title="No assets yet"
  description="Create your first asset to get started"
  primaryAction={{
    label: 'Create Asset',
    onClick: () => navigate('/assets/create'),
  }}
/>
```

## Empty State with CTA

Primary and secondary action buttons guide users to the next step.

### Primary Action

The primary action is the main call-to-action, styled as a primary button.

```tsx
<EnhancedEmptyState
  title="No data available"
  primaryAction={{
    label: 'Create First Item',
    onClick: () => handleCreate(),
    primary: true, // Default
    variant: 'contained', // Default
  }}
/>
```

### Secondary Actions

Secondary actions provide alternative options, styled as outlined buttons.

```tsx
<EnhancedEmptyState
  title="No results found"
  secondaryActions={[
    {
      label: 'Clear Filters',
      onClick: () => clearFilters(),
      variant: 'outlined',
    },
    {
      label: 'View All',
      onClick: () => showAll(),
      variant: 'text',
    },
  ]}
/>
```

### Multiple Actions

You can combine primary and secondary actions:

```tsx
<EnhancedEmptyState
  title="No connections"
  description="Connect your first service to get started"
  primaryAction={{
    label: 'Add Connection',
    onClick: () => openConnectionDialog(),
  }}
  secondaryActions={[
    {
      label: 'Browse Integrations',
      onClick: () => navigate('/integrations'),
    },
    {
      label: 'View Documentation',
      onClick: () => openDocs(),
    },
  ]}
/>
```

## Empty State Illustrations

SVG illustrations make empty states more engaging and help users understand the context.

### Built-in Illustrations

The component includes several built-in illustrations:

- **EmptyBoxIllustration** - Generic empty state
- **EmptyFolderIllustration** - No files
- **EmptySearchIllustration** - No search results
- **EmptyListIllustration** - Empty list
- **EmptyDataIllustration** - No data
- **EmptyNetworkIllustration** - No connections

### Using Built-in Illustrations

Illustrations are automatically selected based on context:

```tsx
<EnhancedEmptyState
  context="no-files" // Automatically uses EmptyFolderIllustration
  title="No files yet"
/>
```

### Custom Illustrations

You can provide your own illustration:

```tsx
<EnhancedEmptyState
  illustration={<CustomIllustration />}
  illustrationSize={150}
  title="Custom empty state"
/>
```

### Using Illustration Components Directly

```tsx
import { EmptySearchIllustration } from '@/components/utility/EmptyState'

<EnhancedEmptyState
  illustration={<EmptySearchIllustration size={120} color="#666" />}
  title="No results found"
/>
```

## Empty State with Help Text

Help text and links provide additional guidance and resources.

### Help Text

Simple help text below the actions:

```tsx
<EnhancedEmptyState
  title="No data available"
  helpText="Need help getting started? Check out our documentation."
/>
```

### Help Links

Links to documentation, examples, or support:

```tsx
<EnhancedEmptyState
  title="No connections"
  helpLinks={[
    {
      text: 'View Documentation',
      href: '/docs/connections',
    },
    {
      text: 'Browse Integrations',
      href: '/integrations',
      external: true,
    },
    {
      text: 'Contact Support',
      href: '/support',
    },
  ]}
/>
```

### Custom Help Content

Provide custom help content:

```tsx
<EnhancedEmptyState
  title="No data"
  helpContent={
    <div>
      <p>For more information, visit our help center.</p>
      <Button href="/help">Help Center</Button>
    </div>
  }
/>
```

### Combined Help Text and Links

```tsx
<EnhancedEmptyState
  title="No results found"
  helpText="Try adjusting your search criteria or browse our help resources:"
  helpLinks={[
    { text: 'Search Tips', href: '/help/search' },
    { text: 'Contact Support', href: '/support' },
  ]}
/>
```

## Usage Examples

### Complete Example

```tsx
import {
  EnhancedEmptyState,
  NoDataEmptyState,
} from '@/components/utility/EmptyState'

function AssetList({ assets }) {
  if (assets.length === 0) {
    return (
      <NoDataEmptyState
        primaryAction={{
          label: 'Create Asset',
          onClick: () => navigate('/assets/create'),
        }}
        secondaryActions={[
          {
            label: 'Import Assets',
            onClick: () => openImportDialog(),
          },
        ]}
        helpText="Learn how to create and manage assets in our documentation."
        helpLinks={[
          { text: 'Asset Guide', href: '/docs/assets' },
          { text: 'Video Tutorial', href: '/tutorials/assets', external: true },
        ]}
      />
    )
  }

  return <AssetTable assets={assets} />
}
```

### Search Results Empty State

```tsx
function SearchResults({ query, results }) {
  if (results.length === 0 && query) {
    return (
      <EnhancedEmptyState
        context="no-results"
        title={`No results for "${query}"`}
        description="Try different keywords or adjust your filters"
        primaryAction={{
          label: 'Clear Search',
          onClick: () => setQuery(''),
        }}
        secondaryActions={[
          {
            label: 'View All Items',
            onClick: () => showAll(),
          },
        ]}
        helpText="Search tips:"
        helpLinks={[
          { text: 'Search Guide', href: '/help/search' },
        ]}
      />
    )
  }

  return <ResultsList results={results} />
}
```

### Table Empty State

```tsx
function DataTable({ data }) {
  if (data.length === 0) {
    return (
      <EnhancedEmptyState
        context="no-data"
        title="No data to display"
        description="Create your first record to get started"
        primaryAction={{
          label: 'Add Record',
          onClick: () => openAddDialog(),
        }}
        minHeight={400}
      />
    )
  }

  return <Table data={data} />
}
```

### Error Empty State

```tsx
function DataView({ data, error }) {
  if (error) {
    return (
      <EnhancedEmptyState
        context="error"
        title="Unable to load data"
        description="We encountered an error. Please try again."
        primaryAction={{
          label: 'Retry',
          onClick: () => refetch(),
        }}
        helpLinks={[
          { text: 'Report Issue', href: '/support' },
        ]}
      />
    )
  }

  if (data.length === 0) {
    return <NoDataEmptyState />
  }

  return <DataList data={data} />
}
```

## Best Practices

### 1. Use Appropriate Context

Choose the right contextual empty state for the situation:

- **No Data** - When a table or list is empty
- **No Results** - When search/filter returns nothing
- **No Items** - When a collection is empty
- **No Files** - When there are no files
- **No Connections** - When there are no integrations
- **Error** - When an error occurs

### 2. Provide Clear Actions

Always provide at least one action button:

- **Primary Action** - The main next step (e.g., "Create Asset")
- **Secondary Actions** - Alternative options (e.g., "Import", "Browse Examples")

### 3. Include Helpful Guidance

Add help text and links to guide users:

- Link to relevant documentation
- Provide search tips for no-results states
- Link to examples or tutorials
- Offer support contact options

### 4. Use Appropriate Illustrations

- Use context-appropriate illustrations
- Keep illustrations simple and recognizable
- Ensure illustrations are accessible (proper alt text)

### 5. Customize Messages

Override default messages when needed:

```tsx
<NoDataEmptyState
  title="No assets in this workspace"
  description="Assets you create will appear here. Get started by creating your first asset."
/>
```

### 6. Consider User Journey

Think about where the user is in their journey:

- **First-time users** - More guidance, links to tutorials
- **Returning users** - Quick actions, less explanation
- **Error states** - Clear error messages, retry options

### 7. Accessibility

- Use semantic HTML
- Provide proper ARIA labels
- Ensure sufficient color contrast
- Support keyboard navigation

## Type Safety

All components are fully typed:

```tsx
import type {
  EmptyStateContext,
  EmptyStateAction,
  HelpLink,
} from '@/components/utility/EmptyState'
```

## See Also

- [Component Library Documentation](../../../docs/UI/COMPONENT_LIBRARY.md)
- [UX Patterns Documentation](../../../docs/UI/UX_PATTERNS.md)

