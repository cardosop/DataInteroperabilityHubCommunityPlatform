# User Interface Specifications

**Last Updated**: 2025-01-15  
**Version**: 1.0.0

---

## Table of Contents

1. [Overview](#overview)
2. [Data Product Owner Interfaces](#data-product-owner-interfaces)
3. [Data Engineer Interfaces](#data-engineer-interfaces)
4. [Compliance Officer Interfaces](#compliance-officer-interfaces)
5. [Data Consumer Interfaces](#data-consumer-interfaces)
6. [Tenant Admin Interfaces](#tenant-admin-interfaces)
7. [Platform Admin Interfaces](#platform-admin-interfaces)
8. [Common Interface Patterns](#common-interface-patterns)
9. [Screen Specifications](#screen-specifications)

---

## Overview

This document provides detailed UI specifications for all personas and use cases in the Interoperable Data Hub platform. Each interface specification includes layout, components, interactions, and state management.

**Specification Format**:
- **Screen ID**: Unique identifier
- **Screen Name**: Descriptive name
- **Persona**: Primary persona(s)
- **Purpose**: What the screen accomplishes
- **Layout**: Screen structure and components
- **Components**: Specific components used
- **Interactions**: User interactions and behaviors
- **States**: Different states of the screen
- **Responsive Behavior**: How it adapts to different screen sizes

---

## Data Product Owner Interfaces

### UI-DPO-001: Asset Creation (Data-First Flow)

**Screen ID**: UI-DPO-001  
**Screen Name**: Create Asset - Data-First  
**Persona**: Data Product Owner  
**Purpose**: Onboard new asset via data-first flow

**Layout**:
```
┌─────────────────────────────────────────┐
│ Header (Logo, Navigation, User Menu)     │
├─────────────────────────────────────────┤
│ Breadcrumbs: Assets > Create Asset      │
├─────────────────────────────────────────┤
│                                         │
│  Title: Create New Asset                │
│                                         │
│  ┌─────────────────┬─────────────────┐ │
│  │ Basic Metadata  │ Onboarding Mode │ │
│  │                 │                 │ │
│  │ [Asset Name*]   │ ○ Data First    │ │
│  │ [Description]   │ ● Contract First│ │
│  │ [Domain]        │ ○ Contract Only │ │
│  │ [Tags]          │                 │ │
│  └─────────────────┴─────────────────┘ │
│                                         │
│  [Cancel]              [Continue →]     │
└─────────────────────────────────────────┘
```

**Components**:
- Header (with navigation)
- Breadcrumbs
- Container (max-width: lg)
- Grid (2 columns)
- TextInput (Asset Name, Description)
- Select (Domain)
- TagInput (Tags)
- RadioGroup (Onboarding Mode)
- Button (Cancel, Continue)

**Interactions**:
- Asset Name: Required, auto-generates slug on blur
- Domain: Dropdown with common domains
- Tags: Multi-select with autocomplete
- Continue: Validates required fields, navigates to file upload

**States**:
- **Default**: Empty form
- **Validating**: Show validation errors
- **Loading**: Disable form during submission

**Responsive Behavior**:
- Desktop: 2-column layout
- Tablet: 2-column layout (stacked)
- Mobile: Single column, full width

---

### UI-DPO-002: File Upload

**Screen ID**: UI-DPO-002  
**Screen Name**: Upload Data File  
**Persona**: Data Product Owner  
**Purpose**: Upload data file for analysis

**Layout**:
```
┌─────────────────────────────────────────┐
│ Breadcrumbs: Assets > Create > Upload   │
├─────────────────────────────────────────┤
│                                         │
│  Title: Upload Data File                │
│                                         │
│  ┌───────────────────────────────────┐ │
│  │                                     │ │
│  │     Drag & Drop File Here          │ │
│  │     or click to browse              │ │
│  │                                     │ │
│  │     Supported: CSV, JSON, Parquet  │ │
│  │                                     │ │
│  └───────────────────────────────────┘ │
│                                         │
│  ┌───────────────────────────────────┐ │
│  │ What happens next?                 │ │
│  │ 1. File is uploaded                │ │
│  │ 2. Schema is inferred               │ │
│  │ 3. DQ & Compliance checks run       │ │
│  │ 4. You review and edit contract    │ │
│  └───────────────────────────────────┘ │
│                                         │
│  [← Back]              [Upload & Analyze]│
└─────────────────────────────────────────┘
```

**Components**:
- FileUpload (drag-and-drop zone)
- Card (info card)
- Button (Back, Upload & Analyze)
- ProgressBar (during upload)

**Interactions**:
- Drag & Drop: Highlight zone, accept file
- Click to Browse: Open file picker
- Upload: Show progress, validate file
- File Selected: Show file name, size, type

**States**:
- **Empty**: Dropzone visible
- **Dragging**: Highlighted border
- **File Selected**: Show file info
- **Uploading**: Progress bar, disable actions
- **Error**: Show error message

---

### UI-DPO-003: Analyzing Data

**Screen ID**: UI-DPO-003  
**Screen Name**: Analyzing Data  
**Persona**: Data Product Owner  
**Purpose**: Show progress of data analysis

**Layout**:
```
┌─────────────────────────────────────────┐
│ Title: Analyzing Data for "Asset Name"  │
├─────────────────────────────────────────┤
│                                         │
│  Progress Steps:                        │
│  ✓ 1. Upload file                       │
│  → 2. Infer schema          [In Progress]│
│  ○ 3. Run data quality checks           │
│  ○ 4. Run compliance checks             │
│  ○ 5. Prepare contract draft            │
│                                         │
│  ┌───────────────────────────────────┐ │
│  │                                     │ │
│  │         [Loading Spinner]           │ │
│  │                                     │ │
│  │    "Inferring schema..."            │ │
│  │                                     │ │
│  └───────────────────────────────────┘ │
│                                         │
│  Note: You can navigate away; analysis  │
│  will continue in the background        │
└─────────────────────────────────────────┘
```

**Components**:
- Stepper (progress steps)
- LoadingSpinner
- StatusIndicator
- Alert (if errors)

**Interactions**:
- Auto-updates as jobs complete
- Shows current step and status
- Updates progress indicators
- Navigates to next screen when complete

**States**:
- **In Progress**: Show spinner, current step
- **Error**: Show error alert, allow retry
- **Complete**: Navigate to contract editor

---

### UI-DPO-004: Contract Editor

**Screen ID**: UI-DPO-004  
**Screen Name**: Contract Editor  
**Persona**: Data Product Owner  
**Purpose**: Edit and validate contract

> **📋 Detailed Specification**: See [Contract Editor Specification](./CONTRACT_EDITOR_SPECIFICATION.md) for comprehensive component specifications, architecture, and implementation details.

**Layout**:
```
┌─────────────────────────────────────────┐
│ Title: Edit Contract                    │
├─────────────────────────────────────────┤
│                                         │
│  ┌─────────────────┬─────────────────┐ │
│  │ Contract Form    │ Raw Contract    │ │
│  │                 │ & Validation    │ │
│  │ [Tabs]          │                 │ │
│  │ Overview        │ [View: Form]    │ │
│  │ Schema          │ [Raw YAML]      │ │
│  │ Quality         │                 │ │
│  │ Compliance      │ ┌─────────────┐ │ │
│  │ Lifecycle       │ │ Validation  │ │ │
│  │ Marketplace     │ │ Status: ✓   │ │ │
│  │                 │ │ Valid       │ │ │
│  │ [Form Fields]  │ └─────────────┘ │ │
│  └─────────────────┴─────────────────┘ │
│                                         │
│  [Run Validation]  [Save Draft] [Activate]│
└─────────────────────────────────────────┘
```

**Components**:
- EditorHeader (contract metadata, status badges)
- EditorTabs (Overview, Schema, Quality, Compliance, Lifecycle, Marketplace, Raw)
- Form components (TextInput, Select, TagInput, etc.)
- CodeEditor (Monaco Editor for raw YAML/JSON)
- ValidationPanel (real-time validation feedback)
- SchemaComparison (contract-first flow: inferred vs contract schema)
- Button (Run Validation, Save Draft, Activate)

**Interactions**:
- Form editing: Auto-save draft (every 30 seconds)
- Real-time validation: Debounced validation on field changes
- Schema tab: Edit field properties with field editor modal
- Raw view: Edit YAML/JSON directly with syntax highlighting
- Schema comparison: Resolve differences between inferred and contract schema
- Activate: Only enabled when validation status is VALID or WARNING_ONLY

**States**:
- **Editing**: Form editable, show unsaved changes indicator
- **Validating**: Show loading spinner, disable actions
- **Valid**: Green badge, activate button enabled
- **Invalid**: Red badge, show errors in validation panel, activate disabled
- **Warning**: Yellow badge, show warnings, activate enabled (per tenant policy)
- **Normalizing**: Show normalization status (NORMALIZED_OK, WITH_WARNINGS, FAILED)

**HubContract-Specific Features**:
- Quality rules editor (custom DQ rules with dimensions, severity, expressions)
- Compliance policy editor (PII categories, jurisdictions, legal bases, retention)
- Lifecycle policy editor (data source, refresh cadence, SLAs)
- Marketplace policy editor (license, intended use, restricted use)
- Schema comparison view (for contract-first onboarding flow)
- Normalization status display

---

### UI-DPO-005: Asset List

**Screen ID**: UI-DPO-005  
**Screen Name**: Assets List  
**Persona**: Data Product Owner  
**Purpose**: Browse and manage assets

**Layout**:
```
┌─────────────────────────────────────────┐
│ Title: Assets                            │
├─────────────────────────────────────────┤
│                                         │
│  [Search]  [Status Filter] [Domain Filter]│
│                                         │
│  ┌───────────────────────────────────┐ │
│  │ Name    │ Domain │ Status │ Quality│ │
│  ├─────────┼────────┼────────┼────────┤ │
│  │ Asset 1 │ Sales  │ Active │ ✓ Pass │ │
│  │ Asset 2 │ Mktg   │ Draft  │ ⚠ Warn │ │
│  │ Asset 3 │ Sales  │ Active │ ✗ Fail │ │
│  └───────────────────────────────────┘ │
│                                         │
│  [← Previous]  Page 1 of 5  [Next →]   │
│                                         │
│  [+ New Asset] (floating button)       │
└─────────────────────────────────────────┘
```

**Components**:
- SearchInput
- FilterDropdown (Status, Domain)
- Table (sortable, filterable)
- Pagination
- FloatingActionButton (New Asset)
- Badge (Status, Quality, Compliance)

**Interactions**:
- Search: Real-time filtering
- Filters: Multi-select, apply immediately
- Sort: Click column headers
- Row click: Navigate to asset detail
- Actions: Edit, Delete, More menu

**States**:
- **Loading**: Skeleton loaders
- **Empty**: Empty state with CTA
- **Error**: Error message with retry

---

## Data Engineer Interfaces

### UI-DE-001: API Documentation

**Screen ID**: UI-DE-001  
**Screen Name**: API Documentation  
**Persona**: Data Engineer  
**Purpose**: Browse API documentation

**Layout**:
```
┌─────────────────────────────────────────┐
│ Title: API Documentation                 │
├─────────────────────────────────────────┤
│                                         │
│  ┌───────────┬─────────────────────────┐ │
│  │ Endpoints │ Endpoint Details        │ │
│  │           │                         │ │
│  │ Assets    │ POST /api/v1/assets     │ │
│  │ Contracts │                         │ │
│  │ Files     │ Description:            │ │
│  │ DQ Runs   │ Create a new asset      │ │
│  │ ...       │                         │ │
│  │           │ Request:                │ │
│  │           │ { ... }                 │ │
│  │           │                         │ │
│  │           │ Response:               │ │
│  │           │ { ... }                 │ │
│  └───────────┴─────────────────────────┘ │
│                                         │
│  [Try It] [Copy cURL] [Copy Python]    │
└─────────────────────────────────────────┘
```

**Components**:
- Sidebar (endpoint list)
- CodeBlock (request/response examples)
- Tabs (Description, Request, Response, Examples)
- Button (Try It, Copy)

**Interactions**:
- Endpoint selection: Show details
- Code blocks: Syntax highlighting, copy
- Try It: Interactive API tester
- Examples: Language-specific examples

---

## Compliance Officer Interfaces

### UI-CPO-001: Compliance Dashboard

**Screen ID**: UI-CPO-001  
**Screen Name**: Compliance Dashboard  
**Persona**: Compliance Officer  
**Purpose**: Overview of compliance status

**Layout**:
```
┌─────────────────────────────────────────┐
│ Title: Compliance Dashboard             │
├─────────────────────────────────────────┤
│                                         │
│  ┌─────────┬─────────┬─────────┬──────┐ │
│  │ Total   │ Pass    │ Warn    │ Fail │ │
│  │ Assets  │         │         │      │ │
│  │ 150     │ 120     │ 20      │ 10   │ │
│  └─────────┴─────────┴─────────┴──────┘ │
│                                         │
│  ┌───────────────────────────────────┐ │
│  │ Compliance Status by Regulation    │ │
│  │ [Chart: GDPR, HIPAA, SOX, etc.]   │ │
│  └───────────────────────────────────┘ │
│                                         │
│  ┌───────────────────────────────────┐ │
│  │ Recent Compliance Runs            │ │
│  │ [Table: Asset, Status, Date]     │ │
│  └───────────────────────────────────┘ │
└─────────────────────────────────────────┘
```

**Components**:
- StatCard (metrics)
- Chart (compliance by regulation)
- Table (recent runs)
- FilterDropdown (regulation, date range)

**Interactions**:
- Click metrics: Filter to that status
- Click chart: Drill down to details
- Click table row: Navigate to compliance report

---

### UI-CPO-002: Compliance Report

**Screen ID**: UI-CPO-002  
**Screen Name**: Compliance Report  
**Persona**: Compliance Officer  
**Purpose**: Detailed compliance report

**Layout**:
```
┌─────────────────────────────────────────┐
│ Title: Compliance Report - Asset Name   │
├─────────────────────────────────────────┤
│                                         │
│  Summary Card:                          │
│  ┌───────────────────────────────────┐ │
│  │ Status: ⚠ Warning                 │ │
│  │ Risk Level: Medium                │ │
│  │ Allowed to Store: Yes              │ │
│  │ Regulations: GDPR, LGPD           │ │
│  └───────────────────────────────────┘ │
│                                         │
│  Detected Categories:                   │
│  [PII_EMAIL] [PII_NAME] [FINANCIAL]    │
│                                         │
│  Column Findings:                       │
│  ┌───────────────────────────────────┐ │
│  │ Column │ Categories │ Risk │ Notes│ │
│  ├────────┼────────────┼──────┼──────┤ │
│  │ email  │ PII_EMAIL  │ High │ ...  │ │
│  │ name   │ PII_NAME   │ Med  │ ...  │ │
│  └───────────────────────────────────┘ │
│                                         │
│  [Export PDF] [Export CSV] [Add Note] │
└─────────────────────────────────────────┘
```

**Components**:
- SummaryCard
- Badge (categories)
- Table (column findings)
- Button (Export, Add Note)

**Interactions**:
- Export: Generate PDF/CSV report
- Add Note: Add compliance annotation
- Column click: Show detailed findings

---

## Data Consumer Interfaces

### UI-DC-001: Marketplace

**Screen ID**: UI-DC-001  
**Screen Name**: Marketplace  
**Persona**: Data Consumer  
**Purpose**: Browse and discover marketplace assets

**Layout**:
```
┌─────────────────────────────────────────┐
│ Title: Marketplace                      │
├─────────────────────────────────────────┤
│                                         │
│  [Search: "customer data"]               │
│                                         │
│  Filters:                               │
│  [Domain ▼] [Price ▼] [Quality ▼]      │
│                                         │
│  ┌───────────┬───────────┬───────────┐ │
│  │ Asset 1   │ Asset 2   │ Asset 3   │ │
│  │           │           │           │ │
│  │ Title     │ Title     │ Title     │ │
│  │ Provider  │ Provider  │ Provider  │ │
│  │ ✓ Quality │ ⚠ Quality │ ✓ Quality │ │
│  │ $99       │ Free      │ $199      │ │
│  │ [View]    │ [View]    │ [View]    │ │
│  └───────────┴───────────┴───────────┘ │
│                                         │
│  [← Previous]  Page 1 of 10  [Next →] │
└─────────────────────────────────────────┘
```

**Components**:
- SearchInput
- FilterDropdown (Domain, Price, Quality)
- CardGrid (asset cards)
- Pagination
- Badge (Quality, Compliance)

**Interactions**:
- Search: Real-time filtering
- Filters: Apply immediately
- Card click: Navigate to asset detail
- View button: Navigate to asset detail

---

### UI-DC-002: Marketplace Asset Detail

**Screen ID**: UI-DC-002  
**Screen Name**: Marketplace Asset Detail  
**Persona**: Data Consumer  
**Purpose**: View asset details and purchase

**Layout**:
```
┌─────────────────────────────────────────┐
│ Title: Customer Orders Dataset          │
│ Provider: Acme Corp                     │
├─────────────────────────────────────────┤
│                                         │
│  ┌─────────────────┬─────────────────┐ │
│  │ Asset Details   │ Purchase Info   │ │
│  │                 │                 │ │
│  │ Description:    │ Price: $99     │ │
│  │ Customer order  │ License: ...    │ │
│  │ data with...    │                 │ │
│  │                 │ [Request Access]│ │
│  │ Schema Preview: │                 │ │
│  │ - order_id      │ Quality: ✓ Pass │ │
│  │ - customer_id   │ Compliance: ✓   │ │
│  │ - total         │                 │ │
│  │                 │                 │ │
│  │ Sample Data:    │                 │ │
│  │ [Table preview] │                 │ │
│  └─────────────────┴─────────────────┘ │
└─────────────────────────────────────────┘
```

**Components**:
- Card (asset details, purchase info)
- Table (schema preview, sample data)
- Badge (Quality, Compliance)
- Button (Request Access, Buy Now)

**Interactions**:
- Request Access: Create order, show confirmation
- Buy Now: Process payment (if applicable)
- Schema preview: Expandable table
- Sample data: Limited preview

---

## Tenant Admin Interfaces

### UI-TA-001: User Management

**Screen ID**: UI-TA-001  
**Screen Name**: User Management  
**Persona**: Tenant Admin  
**Purpose**: Manage tenant users

**Layout**:
```
┌─────────────────────────────────────────┐
│ Title: User Management                  │
├─────────────────────────────────────────┤
│                                         │
│  [Search]  [Status Filter] [Role Filter]│
│                                         │
│  ┌───────────────────────────────────┐ │
│  │ Name      │ Email    │ Role │ Status│ │
│  ├───────────┼──────────┼──────┼───────┤ │
│  │ John Doe  │ j@...    │ Admin│ Active│ │
│  │ Jane Smith│ jane@... │ Prov │ Active│ │
│  └───────────────────────────────────┘ │
│                                         │
│  [+ Invite User]                        │
└─────────────────────────────────────────┘
```

**Components**:
- SearchInput
- FilterDropdown (Status, Role)
- Table (users)
- Button (Invite User)
- Avatar (user avatars)

**Interactions**:
- Invite User: Open invite modal
- Row click: Navigate to user detail
- Actions: Edit, Deactivate, Delete

---

## Platform Admin Interfaces

### UI-PA-001: Tenant Management

**Screen ID**: UI-PA-001  
**Screen Name**: Tenant Management  
**Persona**: Platform Admin  
**Purpose**: Manage all tenants

**Layout**:
```
┌─────────────────────────────────────────┐
│ Title: Tenant Management                │
├─────────────────────────────────────────┤
│                                         │
│  ┌─────────┬─────────┬─────────┬──────┐ │
│  │ Total   │ Active  │ Susp.   │ KYC  │ │
│  │ Tenants │         │         │      │ │
│  │ 50      │ 45      │ 3       │ 40   │ │
│  └─────────┴─────────┴─────────┴──────┘ │
│                                         │
│  [Search]  [Status Filter] [KYC Filter]│
│                                         │
│  ┌───────────────────────────────────┐ │
│  │ Name    │ Status │ KYC │ Users │ ...│ │
│  ├─────────┼────────┼─────┼───────┼────┤ │
│  │ Acme    │ Active │ ✓   │ 25    │ ...│ │
│  │ Beta    │ Susp.  │ ✗   │ 10    │ ...│ │
│  └───────────────────────────────────┘ │
│                                         │
│  [+ Create Tenant]                      │
└─────────────────────────────────────────┘
```

**Components**:
- StatCard (tenant metrics)
- SearchInput
- FilterDropdown (Status, KYC)
- Table (tenants)
- Button (Create Tenant)

**Interactions**:
- Create Tenant: Open creation modal
- Row click: Navigate to tenant detail
- Actions: Suspend, Reactivate, Delete

---

## Common Interface Patterns

### Pattern-001: Data Table

**Purpose**: Display tabular data with sorting, filtering, pagination

**Components**:
- Table
- SearchInput
- FilterDropdown
- Pagination
- Action buttons

**Specifications**:
- Sortable columns
- Filterable columns
- Pagination (10, 25, 50, 100 per page)
- Row selection (checkbox)
- Bulk actions
- Export (CSV, JSON)

---

### Pattern-002: Form Layout

**Purpose**: Consistent form layout and validation

**Components**:
- Container
- Grid (2 columns on desktop)
- Form fields (TextInput, Select, etc.)
- Button group (Cancel, Submit)

**Specifications**:
- Required field indicators (*)
- Inline validation
- Error messages below fields
- Help text for complex fields
- Auto-save draft (where applicable)

---

### Pattern-003: Status Dashboard

**Purpose**: Display metrics and status overview

**Components**:
- StatCard (metrics)
- Chart (visualizations)
- Table (recent items)
- FilterDropdown

**Specifications**:
- Real-time updates (polling or WebSocket)
- Click to drill down
- Export capabilities
- Date range filters

---

## Screen Specifications

### Responsive Breakpoints

- **Mobile**: < 600px
- **Tablet**: 600px - 960px
- **Desktop**: 960px - 1280px
- **Large Desktop**: > 1280px

### Screen States

All screens support:
- **Loading**: Skeleton loaders or spinners
- **Empty**: Empty state with CTA
- **Error**: Error message with retry
- **Success**: Success message (toast)

### Navigation Patterns

- **Breadcrumbs**: Show current location
- **Back Button**: Return to previous screen
- **Cancel**: Close/discard changes
- **Save**: Save changes (with validation)

---

**Last Updated**: 2025-01-15  
**Version**: 1.0.0

