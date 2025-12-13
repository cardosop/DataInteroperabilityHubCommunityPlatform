# UX Patterns and Interactions

**Last Updated**: 2025-01-15  
**Version**: 1.0.0

---

## Table of Contents

1. [Overview](#overview)
2. [Navigation Patterns](#navigation-patterns)
3. [Form Patterns](#form-patterns)
4. [Data Display Patterns](#data-display-patterns)
5. [Feedback Patterns](#feedback-patterns)
6. [Error Handling Patterns](#error-handling-patterns)
7. [Loading Patterns](#loading-patterns)
8. [Empty State Patterns](#empty-state-patterns)
9. [Onboarding Patterns](#onboarding-patterns)
10. [Search and Discovery Patterns](#search-and-discovery-patterns)

---

## Overview

This document describes common UX patterns and interaction design guidelines for the Interoperable Data Hub platform. These patterns ensure consistency, usability, and a cohesive user experience across all interfaces.

**Pattern Principles**:
- **Consistency**: Use patterns consistently across the platform
- **Familiarity**: Follow platform conventions and user expectations
- **Efficiency**: Patterns should reduce cognitive load and time to complete tasks
- **Accessibility**: All patterns must be accessible to all users

---

## Navigation Patterns

### Pattern: Primary Navigation

**Purpose**: Main navigation for authenticated users

**Structure**:
- **Header**: Logo, primary navigation, user menu
- **Sidebar**: Secondary navigation (collapsible)
- **Breadcrumbs**: Current location trail

**Behavior**:
- Sticky header (stays at top on scroll)
- Sidebar collapses on mobile (hamburger menu)
- Active navigation item highlighted
- Breadcrumbs show full path

**Example**:
```
Header: [Logo] [Assets] [Marketplace] [Admin] ... [User Menu]
Sidebar: [Assets] [Onboarding] [DQ & Compliance] [Marketplace]
Breadcrumbs: Assets > Customer Orders > Edit
```

---

### Pattern: Tab Navigation

**Purpose**: Organize related content within a page

**Structure**:
- Horizontal tabs at top of content area
- Active tab highlighted with underline
- Tab content below tabs

**Behavior**:
- Click tab to switch content
- Keyboard navigation (arrow keys)
- URL updates with tab ID (for bookmarking)
- Smooth transition between tabs

**Example**:
```
[Overview] [Schema] [Quality] [Compliance] [Audit]
────────────────────────────────────────────────────
Content for selected tab appears here
```

---

### Pattern: Breadcrumb Navigation

**Purpose**: Show current location and enable quick navigation

**Structure**:
- Horizontal list of links
- Separator between items (/, >, or •)
- Last item is current page (not clickable)

**Behavior**:
- Click any breadcrumb to navigate
- Truncate long paths (show ... for middle items)
- Show full path on hover (tooltip)

**Example**:
```
Assets > Customer Orders > Edit Contract
```

---

## Form Patterns

### Pattern: Progressive Disclosure

**Purpose**: Show essential fields first, advanced options on demand

**Structure**:
- Basic fields visible by default
- "Advanced" or "More Options" expandable section
- Advanced fields hidden until expanded

**Behavior**:
- Click to expand/collapse
- Remember expanded state (localStorage)
- Smooth animation on expand/collapse

**Example**:
```
Basic Information:
[Asset Name*]
[Description]
[Domain]

[▼ Advanced Options]
  [Tags]
  [Custom Metadata]
  [Retention Policy]
```

---

### Pattern: Inline Validation

**Purpose**: Validate form fields as user types

**Structure**:
- Validation runs on blur (or after delay on type)
- Error message appears below field
- Success indicator (checkmark) for valid fields
- Field border changes color (red for error, green for success)

**Behavior**:
- Don't show errors until user interacts
- Clear errors when field becomes valid
- Show validation rules before user starts typing (helper text)

**Example**:
```
[Asset Name*]
✓ Valid name

[Email]
✗ Invalid email format
  Please enter a valid email address
```

---

### Pattern: Multi-Step Form

**Purpose**: Break complex forms into manageable steps

**Structure**:
- Stepper showing current step and progress
- One step visible at a time
- Navigation buttons (Back, Next, Skip)
- Summary step before submission

**Behavior**:
- Validate current step before proceeding
- Save progress automatically
- Allow navigation between completed steps
- Show progress indicator

**Example**:
```
Step 1: Basic Info        [Current]
Step 2: Upload Data       [Next]
Step 3: Review & Submit   [Future]

[← Back]              [Continue →]
```

---

## Data Display Patterns

### Pattern: Data Table

**Purpose**: Display tabular data with sorting, filtering, pagination

**Structure**:
- Table with sortable column headers
- Search bar above table
- Filters (dropdowns or chips)
- Pagination below table
- Row actions (menu or buttons)

**Behavior**:
- Click column header to sort (ascending/descending)
- Apply filters immediately
- Show loading state during data fetch
- Empty state when no data
- Row selection (checkbox) for bulk actions

**Example**:
```
[Search] [Status: All ▼] [Domain: All ▼]

┌─────────┬─────────┬─────────┬─────────┐
│ Name ▲  │ Domain  │ Status  │ Actions │
├─────────┼─────────┼─────────┼─────────┤
│ Asset 1 │ Sales   │ Active  │ [⋮]     │
│ Asset 2 │ Mktg    │ Draft   │ [⋮]     │
└─────────┴─────────┴─────────┴─────────┘

[← Previous]  Page 1 of 5  [Next →]
```

---

### Pattern: Card Grid

**Purpose**: Display items in a grid layout

**Structure**:
- Responsive grid (1-4 columns based on screen size)
- Cards with consistent structure
- Image/icon, title, description, actions
- Hover effects (elevation, scale)

**Behavior**:
- Click card to navigate to detail
- Hover shows additional actions
- Consistent card heights
- Loading skeleton while fetching

**Example**:
```
┌─────────┐ ┌─────────┐ ┌─────────┐
│ Asset 1 │ │ Asset 2 │ │ Asset 3 │
│ Title   │ │ Title   │ │ Title   │
│ Desc... │ │ Desc... │ │ Desc... │
│ [View]  │ │ [View]  │ │ [View]  │
└─────────┘ └─────────┘ └─────────┘
```

---

### Pattern: Detail View

**Purpose**: Show detailed information about a single item

**Structure**:
- Header with title and actions
- Summary cards (key metrics)
- Tabs for different sections
- Related items section

**Behavior**:
- Sticky header on scroll
- Tabs switch content smoothly
- Actions always accessible
- Breadcrumb navigation

**Example**:
```
┌─────────────────────────────────────┐
│ Asset Name              [Edit] [⋮] │
├─────────────────────────────────────┤
│ ┌──────┐ ┌──────┐ ┌──────┐ ┌────┐ │
│ │Contract│ │Quality│ │Comply│ │Mkt │ │
│ │ Valid  │ │ Pass  │ │ Pass │ │ ...│ │
│ └──────┘ └──────┘ └──────┘ └────┘ │
├─────────────────────────────────────┤
│ [Overview] [Schema] [Quality] ...  │
├─────────────────────────────────────┤
│ Content for selected tab            │
└─────────────────────────────────────┘
```

---

## Feedback Patterns

### Pattern: Toast Notifications

**Purpose**: Provide non-intrusive feedback for user actions

**Structure**:
- Small notification card
- Icon, message, optional action
- Auto-dismiss after duration
- Stack vertically when multiple

**Behavior**:
- Appear from top-right (or configurable)
- Slide in animation
- Auto-dismiss after 5 seconds (configurable)
- Manual dismiss (X button)
- Click to navigate (if applicable)

**Example**:
```
┌────────────────────────┐
│ ✓ Asset created        │
│   successfully         │
└────────────────────────┘
```

---

### Pattern: Inline Messages

**Purpose**: Provide contextual feedback within forms or content

**Structure**:
- Message box above or below related content
- Icon, title, message, optional action
- Color-coded by severity

**Behavior**:
- Dismissible (X button)
- Persistent until dismissed or condition changes
- Link to related content or actions

**Example**:
```
┌─────────────────────────────────────┐
│ ⚠ Warning                           │
│ Data quality issues detected.        │
│ [View Details]              [×]     │
└─────────────────────────────────────┘
```

---

### Pattern: Progress Indicators

**Purpose**: Show progress of long-running operations

**Structure**:
- Progress bar with percentage
- Step indicator (for multi-step processes)
- Estimated time remaining
- Cancel button (if applicable)

**Behavior**:
- Update in real-time
- Show current step and next steps
- Allow cancellation (with confirmation)
- Show completion message

**Example**:
```
Uploading file...
[████████░░] 80%
Estimated time: 30 seconds remaining
[Cancel]
```

---

## Error Handling Patterns

### Pattern: Form Validation Errors

**Purpose**: Show validation errors clearly and helpfully

**Structure**:
- Error message below field
- Field border turns red
- Error icon next to field
- Summary of all errors at top (optional)

**Behavior**:
- Show errors on blur or submit
- Clear errors when field becomes valid
- Focus first error field on submit
- Provide specific, actionable error messages

**Example**:
```
┌─────────────────────────────┐
│ ✗ Please fix the following: │
│   • Asset name is required  │
│   • Invalid email format    │
└─────────────────────────────┘

[Asset Name*]
✗ This field is required

[Email]
✗ Invalid email format
  Please enter a valid email address
```

---

### Pattern: Error Boundaries

**Purpose**: Handle unexpected errors gracefully

**Structure**:
- Error message with explanation
- Retry button
- Support link
- Error ID for reporting

**Behavior**:
- Catch and display errors
- Don't crash entire application
- Provide recovery options
- Log errors for debugging

**Example**:
```
┌─────────────────────────────────────┐
│ ⚠ Something went wrong              │
│                                     │
│ We encountered an unexpected error. │
│ Error ID: ERR-12345                 │
│                                     │
│ [Retry]  [Contact Support]          │
└─────────────────────────────────────┘
```

---

## Loading Patterns

### Pattern: Skeleton Loaders

**Purpose**: Show content structure while loading

**Structure**:
- Placeholder shapes matching content layout
- Animated shimmer effect
- Same dimensions as actual content

**Behavior**:
- Show immediately on load
- Replace with actual content when ready
- Smooth transition

**Example**:
```
┌─────────────────────────┐
│ ░░░░░░░░░░░░░░░░░░░░░░ │  (Title skeleton)
│ ░░░░░░░░░░░░░░░░░░░░░░ │  (Description)
│ ░░░░░░░░░░░░░░░░░░░░░░ │
└─────────────────────────┘
```

---

### Pattern: Loading Spinners

**Purpose**: Indicate operation in progress

**Structure**:
- Circular spinner
- Optional message
- Centered or inline

**Behavior**:
- Show immediately
- Smooth rotation animation
- Replace with content or error when done

**Example**:
```
    [Spinner]
  Loading...
```

---

## Empty State Patterns

### Pattern: Empty State with CTA

**Purpose**: Guide users when no data exists

**Structure**:
- Illustration or icon
- Title and description
- Primary action button
- Optional secondary actions

**Behavior**:
- Show when list/table is empty
- Provide clear next steps
- Link to relevant documentation

**Example**:
```
┌─────────────────────────────┐
│        [Illustration]        │
│                             │
│    No Assets Yet            │
│                             │
│    Create your first asset  │
│    to get started           │
│                             │
│    [+ Create Asset]         │
└─────────────────────────────┘
```

---

### Pattern: Empty Search Results

**Purpose**: Handle empty search results

**Structure**:
- Search icon or illustration
- Message about no results
- Suggestions or tips
- Clear search button

**Behavior**:
- Show when search returns no results
- Suggest alternative search terms
- Provide filters to refine search

**Example**:
```
┌─────────────────────────────┐
│        [Search Icon]         │
│                             │
│    No results found         │
│                             │
│    Try different keywords   │
│    or adjust your filters   │
│                             │
│    [Clear Search]           │
└─────────────────────────────┘
```

---

## Onboarding Patterns

### Pattern: Guided Tour

**Purpose**: Introduce new users to key features

**Structure**:
- Step-by-step tooltips
- Highlight relevant UI elements
- Progress indicator
- Skip option

**Behavior**:
- Show on first visit (or opt-in)
- Allow skipping
- Remember completion (don't show again)
- Smooth transitions between steps

**Example**:
```
┌─────────────────────────────┐
│ Welcome to Data Hub!         │
│                             │
│ This is the Assets page.    │
│ Create your first asset to  │
│ get started.                │
│                             │
│ [Skip Tour]  [Next →]       │
└─────────────────────────────┘
```

---

### Pattern: Contextual Help

**Purpose**: Provide help when and where needed

**Structure**:
- Help icon (?) next to complex fields
- Tooltip or popover with explanation
- Link to detailed documentation

**Behavior**:
- Show on hover or click
- Context-specific content
- Don't obstruct workflow

**Example**:
```
[Asset Name*]  [?]
               ┌─────────────────────┐
               │ Asset Name          │
               │                     │
               │ A unique identifier │
               │ for your asset      │
               │                     │
               │ [Learn More →]      │
               └─────────────────────┘
```

---

## Search and Discovery Patterns

### Pattern: Global Search

**Purpose**: Quick access to search across platform

**Structure**:
- Search bar in header
- Autocomplete suggestions
- Recent searches
- Quick filters

**Behavior**:
- Focus with keyboard shortcut (Cmd/Ctrl+K)
- Show suggestions as user types
- Highlight search terms in results
- Navigate to result on selection

**Example**:
```
[Search: "customer orders"        ]
┌─────────────────────────────────┐
│ Recent Searches:                │
│ • customer data                 │
│ • order history                 │
│                                 │
│ Suggestions:                    │
│ • customer_orders (Asset)       │
│ • customer_data (Asset)         │
└─────────────────────────────────┘
```

---

### Pattern: Advanced Filters

**Purpose**: Refine search and filter results

**Structure**:
- Filter panel or dropdowns
- Multiple filter types (text, select, date range)
- Active filters shown as chips
- Clear all option

**Behavior**:
- Apply filters immediately
- Show active filter count
- Allow removing individual filters
- Save filter presets (future)

**Example**:
```
Filters:
[Status: Active ▼] [Domain: Sales ▼]
[Date Range: Last 30 days ▼]

Active Filters:
[Status: Active ×] [Domain: Sales ×]
[Clear All]
```

---

**Last Updated**: 2025-01-15  
**Version**: 1.0.0

