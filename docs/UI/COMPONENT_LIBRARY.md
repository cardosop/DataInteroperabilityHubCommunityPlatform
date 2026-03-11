# Component Library

**Last Updated**: 2025-01-15  
**Version**: 1.0.0

---

## Table of Contents

1. [Overview](#overview)
2. [Component Categories](#component-categories)
3. [Layout Components](#layout-components)
4. [Navigation Components](#navigation-components)
5. [Form Components](#form-components)
6. [Data Display Components](#data-display-components)
7. [Feedback Components](#feedback-components)
8. [Overlay Components](#overlay-components)
9. [Utility Components](#utility-components)
10. [Component Specifications](#component-specifications)

---

## Overview

The Component Library provides a comprehensive catalog of reusable UI components for the Interoperable Data Hub platform. All components follow the design system guidelines and are built for accessibility, consistency, and maintainability.

**Component Principles**:
- **Reusability**: Components are composable and reusable
- **Accessibility**: All components meet WCAG 2.1 AA standards
- **Consistency**: Components follow design system tokens
- **Documentation**: Each component is fully documented
- **Testing**: Components are tested in isolation (Storybook)

---

## Component Categories

### 1. Layout Components
Components for page structure and layout

### 2. Navigation Components
Components for navigation and wayfinding

### 3. Form Components
Components for user input and data entry

### 4. Data Display Components
Components for displaying data and content

### 5. Feedback Components
Components for user feedback and status

### 6. Overlay Components
Components that overlay content (modals, tooltips, etc.)

### 7. Utility Components
Helper components and utilities

---

## Layout Components

### Container

**Purpose**: Wrapper for page content with max-width and padding

**Props**:
- `maxWidth`: 'sm' | 'md' | 'lg' | 'xl' | 'full'
- `padding`: boolean (default: true)
- `children`: ReactNode

**Usage**:
```tsx
<Container maxWidth="lg">
  <PageContent />
</Container>
```

**Specifications**:
- Max widths: sm (600px), md (900px), lg (1200px), xl (1536px)
- Padding: 16px on mobile, 24px on desktop
- Responsive: Adapts to screen size

---

### Grid

**Purpose**: Responsive grid layout system

**Props**:
- `columns`: number (default: 12)
- `spacing`: number (default: 2)
- `children`: ReactNode

**Usage**:
```tsx
<Grid columns={12} spacing={2}>
  <GridItem span={6}>Left Column</GridItem>
  <GridItem span={6}>Right Column</GridItem>
</Grid>
```

**Specifications**:
- 12-column grid system
- Responsive breakpoints
- Consistent spacing

---

### Stack

**Purpose**: Vertical or horizontal stack layout

**Props**:
- `direction`: 'row' | 'column' (default: 'column')
- `spacing`: number (default: 2)
- `alignItems`: 'start' | 'center' | 'end' | 'stretch'
- `justifyContent`: 'start' | 'center' | 'end' | 'space-between'
- `children`: ReactNode

**Usage**:
```tsx
<Stack direction="row" spacing={2}>
  <Button>Action 1</Button>
  <Button>Action 2</Button>
</Stack>
```

---

### Card

**Purpose**: Container for related content

**Props**:
- `elevation`: number (default: 1)
- `padding`: number (default: 4)
- `children`: ReactNode

**Usage**:
```tsx
<Card elevation={2}>
  <CardHeader title="Asset Details" />
  <CardContent>
    <AssetInfo />
  </CardContent>
</Card>
```

**Specifications**:
- Elevation: 1 (default), 2 (hover), 4 (selected)
- Padding: 16px default
- Border radius: 8px

---

## Navigation Components

### Header

**Purpose**: Top navigation bar

**Props**:
- `logo`: ReactNode
- `navigation`: NavigationItem[]
- `userMenu`: ReactNode
- `tenantName`: string

**Usage**:
```tsx
<Header
  logo={<Logo />}
  navigation={navItems}
  userMenu={<UserMenu />}
  tenantName="Acme Corp"
/>
```

**Specifications**:
- Height: 64px
- Sticky: Yes (stays at top on scroll)
- Background: White with shadow
- Responsive: Collapses to hamburger menu on mobile

---

### Sidebar

**Purpose**: Left navigation sidebar

**Props**:
- `items`: NavigationItem[]
- `collapsed`: boolean
- `onToggle`: () => void

**Usage**:
```tsx
<Sidebar
  items={sidebarItems}
  collapsed={false}
  onToggle={handleToggle}
/>
```

**Specifications**:
- Width: 240px (expanded), 64px (collapsed)
- Sticky: Yes
- Icons: Material Icons
- Active state: Highlighted with primary color

---

### Breadcrumbs

**Purpose**: Navigation breadcrumb trail

**Props**:
- `items`: BreadcrumbItem[]
- `separator`: string (default: '/')

**Usage**:
```tsx
<Breadcrumbs
  items={[
    { label: 'Assets', href: '/assets' },
    { label: 'Customer Orders', href: '/assets/123' }
  ]}
/>
```

**Specifications**:
- Font size: 14px
- Color: Gray-700
- Active: Gray-900
- Separator: '/' or custom

---

### Tabs

**Purpose**: Tab navigation

**Props**:
- `tabs`: TabItem[]
- `activeTab`: string
- `onChange`: (tabId: string) => void

**Usage**:
```tsx
<Tabs
  tabs={[
    { id: 'overview', label: 'Overview' },
    { id: 'schema', label: 'Schema' }
  ]}
  activeTab="overview"
  onChange={handleTabChange}
/>
```

**Specifications**:
- Height: 48px
- Active indicator: Primary color underline
- Font: 14px, medium weight

---

## Form Components

### Resource Pickers

Searchable dropdowns for selecting assets, contracts, datasets, and files. See [RESOURCE_PICKERS.md](RESOURCE_PICKERS.md) for full documentation, props, and examples.

- **AssetPicker**, **ContractPicker**, **DatasetPicker**, **FilePicker** — single-select
- **AssetMultiPicker**, **DatasetMultiPicker**, **FileMultiPicker** — multi-select

---

### Text Input

**Purpose**: Single-line text input

**Props**:
- `label`: string
- `value`: string
- `onChange`: (value: string) => void
- `error`: string | null
- `helperText`: string
- `required`: boolean
- `disabled`: boolean
- `placeholder`: string

**Usage**:
```tsx
<TextInput
  label="Asset Name"
  value={name}
  onChange={setName}
  error={errors.name}
  required
/>
```

**Specifications**:
- Height: 56px
- Border: 1px solid gray-300
- Focus: Primary color border
- Error: Red border and text
- Font: 16px (prevents zoom on iOS)

---

### Textarea

**Purpose**: Multi-line text input

**Props**:
- `label`: string
- `value`: string
- `onChange`: (value: string) => void
- `rows`: number (default: 4)
- `error`: string | null
- `helperText`: string

**Usage**:
```tsx
<Textarea
  label="Description"
  value={description}
  onChange={setDescription}
  rows={4}
/>
```

---

### Select

**Purpose**: Dropdown selection

**Props**:
- `label`: string
- `options`: Option[]
- `value`: string | null
- `onChange`: (value: string) => void
- `error`: string | null
- `multiple`: boolean

**Usage**:
```tsx
<Select
  label="Domain"
  options={domains}
  value={selectedDomain}
  onChange={setDomain}
/>
```

**Specifications**:
- Height: 56px
- Dropdown: Max height 300px, scrollable
- Search: Optional search for long lists

---

### Checkbox

**Purpose**: Checkbox input

**Props**:
- `label`: string
- `checked`: boolean
- `onChange`: (checked: boolean) => void
- `disabled`: boolean

**Usage**:
```tsx
<Checkbox
  label="Publish to Marketplace"
  checked={isPublished}
  onChange={setIsPublished}
/>
```

**Specifications**:
- Size: 20px × 20px
- Check color: Primary color
- Border: 2px solid gray-400

---

### Radio Group

**Purpose**: Radio button group

**Props**:
- `label`: string
- `options`: Option[]
- `value`: string | null
- `onChange`: (value: string) => void

**Usage**:
```tsx
<RadioGroup
  label="Onboarding Flow"
  options={flows}
  value={selectedFlow}
  onChange={setFlow}
/>
```

---

### File Upload

**Purpose**: File upload with drag-and-drop

**Props**:
- `accept`: string (file types)
- `maxSize`: number (bytes)
- `onUpload`: (file: File) => void
- `multiple`: boolean

**Usage**:
```tsx
<FileUpload
  accept=".csv,.json,.parquet"
  maxSize={100 * 1024 * 1024}
  onUpload={handleUpload}
/>
```

**Specifications**:
- Dropzone: 200px height, dashed border
- Drag state: Highlighted border
- Progress: Progress bar during upload
- Error: Clear error messages

---

### Button

**Purpose**: Action button

**Props**:
- `variant`: 'primary' | 'secondary' | 'outline' | 'text'
- `size`: 'sm' | 'md' | 'lg'
- `disabled`: boolean
- `loading`: boolean
- `onClick`: () => void
- `children`: ReactNode

**Usage**:
```tsx
<Button
  variant="primary"
  size="md"
  onClick={handleSubmit}
  loading={isSubmitting}
>
  Create Asset
</Button>
```

**Specifications**:
- Heights: sm (32px), md (40px), lg (48px)
- Padding: 12px 24px (md)
- Border radius: 4px
- Focus: Visible focus ring

---

## Data Display Components

### Table

**Purpose**: Data table with sorting and filtering

**Props**:
- `columns`: Column[]
- `data`: Row[]
- `sortable`: boolean
- `filterable`: boolean
- `pagination`: boolean

**Usage**:
```tsx
<Table
  columns={assetColumns}
  data={assets}
  sortable
  filterable
  pagination
/>
```

**Specifications**:
- Row height: 48px
- Header: Sticky, gray background
- Hover: Light gray background
- Selected: Primary color background
- Responsive: Horizontal scroll on mobile

---

### Badge

**Purpose**: Status badge or label

**Props**:
- `variant`: 'success' | 'warning' | 'error' | 'info' | 'neutral'
- `size`: 'sm' | 'md'
- `children`: ReactNode

**Usage**:
```tsx
<Badge variant="success">Active</Badge>
<Badge variant="error">Failed</Badge>
```

**Specifications**:
- Height: 20px (sm), 24px (md)
- Border radius: 12px (pill shape)
- Font: 12px, medium weight
- Colors: Semantic colors

---

### Status Indicator

**Purpose**: Visual status indicator

**Props**:
- `status`: 'success' | 'warning' | 'error' | 'pending' | 'running'
- `label`: string
- `size`: 'sm' | 'md' | 'lg'

**Usage**:
```tsx
<StatusIndicator
  status="running"
  label="Processing"
  size="md"
/>
```

**Specifications**:
- Dot: 8px (sm), 12px (md), 16px (lg)
- Animation: Pulse for running/pending
- Colors: Semantic colors

---

### Progress Bar

**Purpose**: Progress indicator

**Props**:
- `value`: number (0-100)
- `label`: string
- `showValue`: boolean

**Usage**:
```tsx
<ProgressBar
  value={75}
  label="Upload Progress"
  showValue
/>
```

**Specifications**:
- Height: 4px (default), 8px (thick)
- Color: Primary color
- Animation: Smooth transition

---

### Empty State

**Purpose**: Empty state message

**Props**:
- `icon`: ReactNode
- `title`: string
- `description`: string
- `action`: ReactNode

**Usage**:
```tsx
<EmptyState
  icon={<EmptyIcon />}
  title="No Assets Yet"
  description="Create your first asset to get started"
  action={<Button>Create Asset</Button>}
/>
```

---

## Feedback Components

### Alert

**Purpose**: Alert message

**Props**:
- `severity`: 'success' | 'warning' | 'error' | 'info'
- `title`: string
- `message`: string
- `dismissible`: boolean
- `onClose`: () => void

**Usage**:
```tsx
<Alert
  severity="error"
  title="Upload Failed"
  message="File size exceeds maximum limit"
  dismissible
  onClose={handleClose}
/>
```

**Specifications**:
- Padding: 16px
- Border: Left border (4px) in severity color
- Icon: Severity-specific icon
- Animation: Slide in from top

---

### Toast

**Purpose**: Toast notification

**Props**:
- `message`: string
- `severity`: 'success' | 'warning' | 'error' | 'info'
- `duration`: number (ms, default: 5000)

**Usage**:
```tsx
toast.success('Asset created successfully');
toast.error('Upload failed');
```

**Specifications**:
- Position: Top-right (default)
- Duration: 5 seconds (default)
- Animation: Slide in/out
- Stack: Multiple toasts stack vertically

---

### Loading Spinner

**Purpose**: Loading indicator

**Props**:
- `size`: 'sm' | 'md' | 'lg'
- `color`: 'primary' | 'white'

**Usage**:
```tsx
<LoadingSpinner size="md" color="primary" />
```

**Specifications**:
- Size: 20px (sm), 32px (md), 48px (lg)
- Animation: Rotate 360deg
- Color: Primary or white

---

## Overlay Components

### Modal

**Purpose**: Modal dialog

**Props**:
- `open`: boolean
- `onClose`: () => void
- `title`: string
- `children`: ReactNode
- `actions`: ReactNode
- `size`: 'sm' | 'md' | 'lg' | 'xl'

**Usage**:
```tsx
<Modal
  open={isOpen}
  onClose={handleClose}
  title="Confirm Delete"
  size="md"
  actions={
    <>
      <Button onClick={handleClose}>Cancel</Button>
      <Button variant="primary" onClick={handleDelete}>Delete</Button>
    </>
  }
>
  <p>Are you sure you want to delete this asset?</p>
</Modal>
```

**Specifications**:
- Backdrop: Dark overlay (rgba(0,0,0,0.5))
- Max width: sm (400px), md (600px), lg (900px), xl (1200px)
- Animation: Fade in + scale up
- Focus trap: Yes
- ESC to close: Yes

---

### Tooltip

**Purpose**: Tooltip on hover

**Props**:
- `content`: string | ReactNode
- `placement`: 'top' | 'bottom' | 'left' | 'right'
- `children`: ReactNode

**Usage**:
```tsx
<Tooltip content="This field is required" placement="top">
  <IconButton icon={<HelpIcon />} />
</Tooltip>
```

**Specifications**:
- Background: Gray-900
- Text: White
- Font: 12px
- Arrow: Points to trigger element
- Delay: 200ms before showing

---

### Dropdown Menu

**Purpose**: Dropdown menu

**Props**:
- `trigger`: ReactNode
- `items`: MenuItem[]
- `placement`: 'bottom-start' | 'bottom-end' | 'top-start' | 'top-end'

**Usage**:
```tsx
<DropdownMenu
  trigger={<Button>Actions</Button>}
  items={[
    { label: 'Edit', onClick: handleEdit },
    { label: 'Delete', onClick: handleDelete }
  ]}
/>
```

**Specifications**:
- Min width: 200px
- Max height: 300px (scrollable)
- Elevation: 8
- Animation: Fade in + slide

---

## Utility Components

### Avatar

**Purpose**: User avatar

**Props**:
- `src`: string (image URL)
- `alt`: string
- `size`: 'sm' | 'md' | 'lg'
- `initials`: string

**Usage**:
```tsx
<Avatar
  src={user.avatar}
  alt={user.name}
  size="md"
  initials="JD"
/>
```

**Specifications**:
- Size: 32px (sm), 40px (md), 48px (lg)
- Border radius: 50% (circle)
- Fallback: Initials or default icon

---

### Divider

**Purpose**: Visual divider

**Props**:
- `orientation`: 'horizontal' | 'vertical'
- `spacing`: number

**Usage**:
```tsx
<Divider orientation="horizontal" spacing={2} />
```

**Specifications**:
- Height/Width: 1px
- Color: Gray-200
- Spacing: 16px default

---

### Skeleton

**Purpose**: Loading skeleton

**Props**:
- `variant`: 'text' | 'circular' | 'rectangular'
- `width`: number | string
- `height`: number | string

**Usage**:
```tsx
<Skeleton variant="text" width="100%" height={20} />
<Skeleton variant="rectangular" width={200} height={100} />
```

**Specifications**:
- Animation: Pulse
- Color: Gray-200 background, gray-100 shimmer

---

## Component Specifications

### Component Structure

All components follow this structure:

```
ComponentName/
  ├── ComponentName.tsx       # Main component
  ├── ComponentName.test.tsx  # Tests
  ├── ComponentName.stories.tsx # Storybook stories
  └── index.ts                # Exports
```

### Component Props

- All props are typed with TypeScript
- Required props are clearly marked
- Default values are provided where appropriate
- Props are documented with JSDoc comments

### Component States

Components support these states:
- **Default**: Normal state
- **Hover**: Mouse hover
- **Focus**: Keyboard focus
- **Active**: Being pressed/clicked
- **Disabled**: Disabled state
- **Loading**: Loading state
- **Error**: Error state

### Accessibility

All components include:
- ARIA labels and roles
- Keyboard navigation
- Focus management
- Screen reader support
- Color contrast compliance

---

**Last Updated**: 2025-01-15  
**Version**: 1.0.0

