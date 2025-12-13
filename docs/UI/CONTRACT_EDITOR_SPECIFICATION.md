# Contract Editor Specification

**Last Updated**: 2025-01-15  
**Version**: 1.0.0

---

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Component Specifications](#component-specifications)
4. [HubContract Structure](#hubcontract-structure)
5. [Editor Modes](#editor-modes)
6. [Integration Points](#integration-points)
7. [Implementation Plan](#implementation-plan)
8. [Technical Specifications](#technical-specifications)
9. [User Flows](#user-flows)
10. [Accessibility](#accessibility)

---

## Overview

The Contract Editor is a comprehensive, custom-built editor for creating and managing data contracts in the Interoperable Data Hub platform. It supports multiple editing modes, real-time validation, and HubContract-specific features that go beyond standard ODCS/DataContract.com specifications.

**Key Principles**:
- **HubContract-First**: Designed specifically for HubContract format with all sections
- **Multi-Mode Editing**: Form, YAML, and Visual editing modes
- **Real-Time Validation**: Instant feedback on contract validity
- **Normalization Integration**: Seamless integration with normalization pipeline
- **Schema-Aware**: Intelligent editing with schema inference and comparison

**Target Personas**: Data Product Owner, Data Engineer

---

## Architecture

### High-Level Architecture

```
ContractEditor (Main Container)
├── EditorHeader
│   ├── ContractMetadata
│   ├── StatusBadges (Normalization, Validation)
│   └── ActionButtons (Save, Validate, Activate)
├── EditorTabs
│   ├── OverviewTab
│   ├── SchemaTab
│   ├── QualityTab
│   ├── ComplianceTab
│   ├── LifecycleTab
│   ├── MarketplaceTab
│   └── RawEditorTab
├── ValidationPanel
│   ├── ValidationStatus
│   ├── ErrorList
│   └── WarningList
└── SchemaComparison (Contract-First Flow)
    ├── InferredSchema
    ├── ContractSchema
    └── DiffView
```

### Component Hierarchy

```
ContractEditor
  ├── EditorLayout (Grid/Stack)
  │   ├── EditorHeader
  │   ├── EditorContent
  │   │   ├── TabNavigation
  │   │   └── TabContent
  │   │       ├── OverviewSection
  │   │       ├── SchemaSection
  │   │       ├── QualitySection
  │   │       ├── ComplianceSection
  │   │       ├── LifecycleSection
  │   │       ├── MarketplaceSection
  │   │       └── RawEditorSection
  │   └── EditorFooter
  │       ├── ValidationPanel
  │       └── ActionBar
  └── SchemaComparison (Conditional - Contract-First)
```

---

## Component Specifications

### ContractEditor (Main Component)

**Purpose**: Main container for contract editing

**Props**:
```typescript
interface ContractEditorProps {
  contractId?: string;              // Existing contract ID (for edit mode)
  assetId?: string;                  // Asset ID (for new contract)
  initialContract?: HubContract;    // Initial contract data
  mode?: 'create' | 'edit';         // Editor mode
  onboardingFlow?: 'data-first' | 'contract-first' | 'contract-only';
  inferredSchema?: SchemaField[];    // Inferred schema (data-first flow)
  onSave: (contract: HubContract) => Promise<void>;
  onValidate: (contract: HubContract) => Promise<ValidationResult>;
  onCancel: () => void;
}
```

**State**:
```typescript
interface ContractEditorState {
  contract: HubContract;              // Current contract data
  activeTab: string;                 // Active tab ID
  validationStatus: ValidationStatus;
  normalizationStatus: NormalizationStatus;
  isDirty: boolean;                  // Has unsaved changes
  isSaving: boolean;
  isValidating: boolean;
  errors: ValidationError[];
  warnings: ValidationWarning[];
  schemaComparison?: SchemaComparison; // For contract-first flow
}
```

**Behavior**:
- Auto-save draft every 30 seconds
- Real-time validation on field changes
- Show normalization status
- Handle tab navigation
- Manage editor state

---

### EditorHeader

**Purpose**: Display contract metadata and status

**Components**:
- Contract name and description
- Normalization status badge
- Validation status badge
- Action buttons (Save, Validate, Activate)

**Specifications**:
- Height: 80px
- Sticky on scroll
- Background: White with shadow
- Status badges: Color-coded (green/yellow/red)

---

### OverviewSection

**Purpose**: Edit contract overview information

**Fields**:
- **Name** (required): TextInput
- **Description**: Textarea
- **Version**: TextInput (auto-incremented)
- **Owners**: Array of Owner objects
  - Name: TextInput
  - Email: EmailInput
  - Add/Remove buttons
- **Tags**: TagInput (multi-select with autocomplete)
- **Domain**: Select (dropdown with common domains)

**Layout**:
- Single column on mobile
- Two columns on desktop
- Form validation on blur

---

### SchemaSection

**Purpose**: Edit contract schema fields

**Features**:
- **Field Table**: Editable table with all field properties
- **Field Editor**: Modal/drawer for detailed field editing
- **Schema Inference Integration**: Show inferred fields (data-first flow)
- **Field Comparison**: Highlight differences (contract-first flow)

**Field Properties**:
- Name (required)
- Data Type (required)
- Nullable (checkbox)
- Description
- Semantic Type (select)
- Format (text input)
- Pattern (regex input)
- Enum (array input)
- Default Value
- Min/Max Length
- Min/Max Numeric
- Metadata (JSON editor)

**Schema Constraints**:
- Primary Key (single field)
- Unique Constraints (array of field arrays)
- Indexes (array of field arrays)

**Layout**:
- Table view with inline editing
- Expandable rows for field details
- Bulk operations (add/remove fields)
- Import/Export schema

---

### QualitySection

**Purpose**: Edit data quality rules (HubContract-specific)

**Features**:
- **Default Profile**: Select (intake_basic, custom)
- **Quality Rules Table**: List of quality rules
- **Rule Editor**: Modal for creating/editing rules

**Rule Properties**:
- Rule ID (required)
- Name (required)
- Dimension (select: completeness, validity, uniqueness, consistency, accuracy, timeliness)
- Expression (SQL/expression)
- Severity (select: ERROR, WARNING, INFO)
- Target Level (select: COLUMN, TABLE, DATASET)
- Target Column (text, if column-level)
- Target Pattern (regex, if pattern-based)
- Parameters (JSON editor)

**Layout**:
- Rules table with inline editing
- Rule editor modal
- Rule templates (pre-defined rules)
- Rule validation

---

### ComplianceSection

**Purpose**: Edit compliance policy (HubContract-specific)

**Features**:
- **Contains Personal Data**: Checkbox
- **Personal Data Categories**: Multi-select (EMAIL, PHONE, NAME, ADDRESS, etc.)
- **Jurisdictions**: Multi-select (GDPR, LGPD, CCPA, HIPAA, SOX)
- **Legal Bases**: Multi-select (CONSENT, CONTRACT, LEGAL_OBLIGATION, etc.)
- **Retention Policy**:
  - Period (duration input: P5Y, P1Y, etc.)
  - Notes (textarea)

**Layout**:
- Form with sections
- Checkbox groups for multi-selects
- Duration picker for retention
- Compliance risk indicator

---

### LifecycleSection

**Purpose**: Edit lifecycle policy (HubContract-specific)

**Features**:
- **Data Source**: TextInput (e.g., "OLTP.orders")
- **Refresh Cadence**: Select (REAL_TIME, HOURLY, DAILY, WEEKLY, MONTHLY, ON_DEMAND)
- **SLAs**:
  - Availability (percentage input: 99.0)
  - Latency P95 (milliseconds input: 5000)

**Layout**:
- Simple form layout
- SLA visualization (charts/graphs)

---

### MarketplaceSection

**Purpose**: Edit marketplace policy (HubContract-specific)

**Features**:
- **License Summary**: TextInput
- **Intended Use**: Multi-select (analytics, machine_learning, reporting, etc.)
- **Restricted Use**: Multi-select (resale, competitive_analysis, etc.)

**Layout**:
- Form with multi-select inputs
- Use case templates

---

### RawEditorSection

**Purpose**: Edit contract in raw YAML/JSON format

**Features**:
- **Editor Mode Toggle**: YAML / JSON
- **Syntax Highlighting**: Monaco Editor or CodeMirror
- **Code Completion**: HubContract schema-aware
- **Error Highlighting**: Real-time error markers
- **Format Toggle**: Switch between YAML and JSON
- **Validation Feedback**: Inline error messages

**Layout**:
- Full-width editor
- Line numbers
- Minimap (optional)
- Format toolbar

**Editor Library Options**:
1. **Monaco Editor** (VS Code editor)
   - Pros: Excellent syntax highlighting, IntelliSense, familiar UX
   - Cons: Larger bundle size
2. **CodeMirror 6**
   - Pros: Lightweight, modular, good performance
   - Cons: Less feature-rich than Monaco

**Recommendation**: Monaco Editor for better UX and code completion

---

### ValidationPanel

**Purpose**: Display validation and normalization status

**Components**:
- **Normalization Status Badge**:
  - NORMALIZED_OK (green)
  - NORMALIZED_WITH_WARNINGS (yellow)
  - NORMALIZATION_FAILED (red)
- **Validation Status Badge**:
  - VALID (green)
  - INVALID (red)
  - WARNING_ONLY (yellow)
  - PENDING (gray)
- **Error List**: Grouped by category
  - Syntax errors
  - Required field errors
  - Spec compatibility errors
- **Warning List**: Grouped by severity
- **Validation Actions**:
  - Run Validation button
  - Last validated timestamp
  - CLI version

**Layout**:
- Fixed bottom panel or sidebar
- Expandable error/warning lists
- Clickable errors (jump to field)

---

### SchemaComparison (Contract-First Flow)

**Purpose**: Compare inferred schema with contract schema

**Features**:
- **Side-by-Side Comparison**:
  - Left: Inferred Schema (from data)
  - Right: Contract Schema
- **Diff Highlighting**:
  - Green: Matching fields
  - Yellow: Type mismatches
  - Red: Missing/extra fields
- **Field Details**:
  - Show differences in properties
  - Type mismatches
  - Missing fields
- **Actions**:
  - Accept inferred schema
  - Keep contract schema
  - Merge schemas
  - Resolve conflicts manually

**Layout**:
- Two-column layout
- Diff view with highlighting
- Action buttons for resolution

---

## HubContract Structure

### Complete HubContract v1.0 Structure

```typescript
interface HubContract {
  hub_contract_version: number;      // 1
  id: string;                         // Contract identifier
  info: {
    name: string;                     // Required
    description?: string;
    version?: string;
    owners?: Owner[];                 // Array of {name, email}
    tags?: string[];                  // Array of tags
    domain?: string;
    status?: string;
    dataProduct?: string;
    links?: Link[];                   // Array of {rel, href}
    authoritativeDefinitions?: string[];
  };
  schema: {
    fields: SchemaField[];            // Required
    primary_key?: string[];
    unique_constraints?: string[][];
    indexes?: string[][];
  };
  quality: {
    default_profile_key?: string;     // e.g., "intake_basic"
    rules?: QualityRule[];             // Array of quality rules
  };
  privacy_compliance: {
    contains_personal_data?: boolean;
    personal_data_categories?: string[];
    jurisdictions?: string[];
    legal_bases?: string[];
    retention_policy?: {
      period?: string;                // ISO 8601 duration
      notes?: string;
    };
  };
  lifecycle: {
    data_source?: string;
    refresh_cadence?: string;
    slas?: {
      availability?: number;          // Percentage
      latency_ms_p95?: number;        // Milliseconds
    };
  };
  marketplace: {
    license_summary?: string;
    intended_use?: string[];
    restricted_use?: string[];
  };
  extensions?: {
    odcs?: Record<string, any>;
    datacontract_com?: Record<string, any>;
    [key: string]: any;
  };
}
```

### SchemaField Structure

```typescript
interface SchemaField {
  name: string;                       // Required
  data_type: string;                  // Required (string, integer, float, boolean, date, timestamp, array, object)
  nullable?: boolean;
  description?: string;
  semantic_type?: string;             // e.g., EMAIL, PHONE, ORDER_ID
  format?: string;                    // e.g., email, uri, date-time
  pattern?: string;                   // Regex pattern
  enum?: any[];                       // Array of allowed values
  default?: any;                      // Default value
  min_length?: number;
  max_length?: number;
  minimum?: number;
  maximum?: number;
  metadata?: Record<string, any>;     // Custom metadata
  is_primary_key?: boolean;
  is_unique?: boolean;
  is_indexed?: boolean;
}
```

### QualityRule Structure

```typescript
interface QualityRule {
  rule_id: string;                    // Required
  name: string;                       // Required
  dimension: string;                  // completeness, validity, uniqueness, consistency, accuracy, timeliness
  expression?: string;                // SQL expression or rule definition
  severity: string;                   // ERROR, WARNING, INFO
  target_level?: string;              // COLUMN, TABLE, DATASET
  target_column?: string;
  target_pattern?: string;
  params?: Record<string, any>;       // Rule-specific parameters
}
```

---

## Editor Modes

### Mode 1: Form Editor (Default)

**Purpose**: Guided editing with forms for each section

**Features**:
- Tab-based navigation
- Form inputs for each field
- Inline validation
- Help text and tooltips
- Progressive disclosure

**Use Case**: Primary editing mode for most users

---

### Mode 2: YAML/JSON Editor

**Purpose**: Direct editing of contract in YAML or JSON format

**Features**:
- Syntax highlighting
- Code completion (HubContract schema-aware)
- Error highlighting
- Format conversion (YAML ↔ JSON)
- Validation feedback

**Use Case**: Advanced users, quick edits, bulk changes

---

### Mode 3: Visual Editor (Future)

**Purpose**: Visual representation of contract structure

**Features**:
- Drag-and-drop field organization
- Visual schema representation
- Relationship visualization
- Flow-based editing

**Use Case**: Non-technical users, visual learners

---

## Integration Points

### API Integration

**Endpoints**:
```typescript
// Get contract
GET /api/v1/contracts/{id}/

// Update contract
PATCH /api/v1/contracts/{id}/

// Validate contract
POST /api/v1/contracts/{id}/validate/

// Normalize contract (automatic on save)
// Triggered by PATCH with original_raw

// Get inferred schema (data-first flow)
GET /api/v1/datasets/{id}/schema/
```

### Real-Time Validation

**Flow**:
1. User edits contract
2. Debounce (500ms)
3. Call validation API
4. Update validation panel
5. Highlight errors in editor

**Implementation**:
```typescript
const useContractValidation = (contractId: string) => {
  const [validationResult, setValidationResult] = useState<ValidationResult | null>(null);
  
  const validate = useCallback(
    debounce(async (contract: HubContract) => {
      const result = await api.post(`/contracts/${contractId}/validate/`, {
        contract
      });
      setValidationResult(result);
    }, 500),
    [contractId]
  );
  
  return { validate, validationResult };
};
```

### Normalization Integration

**Flow**:
1. User saves contract (original_raw)
2. Backend normalizes to HubContract
3. Frontend receives normalized contract
4. Update editor with normalized data
5. Show normalization status

**Status Display**:
- NORMALIZED_OK: Green badge, allow activation
- NORMALIZED_WITH_WARNINGS: Yellow badge, show warnings, allow activation
- NORMALIZATION_FAILED: Red badge, show errors, block activation

---

## Implementation Plan

### Phase 1: Core Editor (Weeks 1-2)

**Deliverables**:
- ContractEditor main component
- EditorHeader with status badges
- Basic tab navigation
- OverviewSection (form)
- RawEditorSection (Monaco Editor)
- ValidationPanel (basic)

**Dependencies**:
- Monaco Editor setup
- API client setup
- Design system components

---

### Phase 2: Schema Editor (Weeks 3-4)

**Deliverables**:
- SchemaSection with field table
- Field editor modal
- Schema constraints editor
- Schema import/export

**Dependencies**:
- Table component
- Modal component
- Form components

---

### Phase 3: HubContract-Specific Sections (Weeks 5-6)

**Deliverables**:
- QualitySection (rules editor)
- ComplianceSection (policy editor)
- LifecycleSection (policy editor)
- MarketplaceSection (policy editor)

**Dependencies**:
- All form components
- Multi-select components
- JSON editor for complex fields

---

### Phase 4: Advanced Features (Weeks 7-8)

**Deliverables**:
- Schema comparison (contract-first flow)
- Real-time validation
- Auto-save draft
- Code completion for HubContract
- Advanced error handling

**Dependencies**:
- Validation API integration
- Monaco Editor IntelliSense setup
- Local storage for drafts

---

### Phase 5: Polish & Testing (Weeks 9-10)

**Deliverables**:
- Accessibility improvements
- Performance optimization
- Error handling
- User testing
- Documentation

**Dependencies**:
- Accessibility audit
- Performance profiling
- User feedback

---

## Technical Specifications

### Technology Stack

**Editor Core**:
- React 18+ with TypeScript
- Monaco Editor (VS Code editor)
- React Hook Form (form management)
- Zod (schema validation)

**State Management**:
- React Query (server state)
- Zustand or Context API (client state)

**Styling**:
- Material-UI or custom design system
- CSS-in-JS (Emotion) or Tailwind CSS

**Validation**:
- HubContract JSON Schema (for validation)
- Real-time API validation

### Performance Considerations

**Optimization Strategies**:
- Lazy load editor tabs
- Debounce validation calls
- Virtual scrolling for large field lists
- Memoize expensive computations
- Code splitting for editor modes

**Bundle Size**:
- Monaco Editor: ~2MB (can be loaded on demand)
- Total editor bundle: Target <500KB (excluding Monaco)

### Accessibility

**Requirements**:
- Keyboard navigation for all interactions
- Screen reader support
- ARIA labels for all components
- Focus management
- Error announcements

**Implementation**:
- Use semantic HTML
- Proper ARIA roles and labels
- Keyboard shortcuts
- Focus traps in modals

---

## User Flows

### Flow 1: Create Contract (Contract-First)

1. User navigates to "Create Contract"
2. Upload contract file or paste YAML/JSON
3. Editor loads with contract data
4. User reviews/edits in Form Editor
5. User clicks "Validate"
6. Validation runs, shows results
7. If valid, user clicks "Save & Activate"
8. Contract saved and activated

---

### Flow 2: Edit Contract (Data-First)

1. User completes data upload and analysis
2. Editor opens with pre-filled contract (from inferred schema)
3. User edits schema fields
4. User adds quality rules, compliance policy
5. User clicks "Validate"
6. If valid, user clicks "Save & Activate"
7. Contract saved and asset activated

---

### Flow 3: Schema Comparison (Contract-First)

1. User uploads contract
2. User uploads data file
3. Schema comparison view appears
4. User reviews differences
5. User accepts inferred schema or keeps contract schema
6. User resolves conflicts
7. Editor updates with merged schema
8. User continues editing

---

## Accessibility

### Keyboard Navigation

**Shortcuts**:
- `Ctrl/Cmd + S`: Save contract
- `Ctrl/Cmd + Enter`: Validate contract
- `Tab`: Navigate between fields
- `Esc`: Close modals/drawers
- `Ctrl/Cmd + /`: Show keyboard shortcuts

### Screen Reader Support

**Announcements**:
- Validation status changes
- Normalization status changes
- Field errors
- Save success/failure
- Tab changes

**ARIA Labels**:
- All form fields have labels
- Status badges have descriptions
- Error messages are announced
- Tab panels are properly labeled

---

## Testing Strategy

### Unit Tests

- Component rendering
- Form validation
- State management
- API integration mocks

### Integration Tests

- Editor workflows
- Validation flow
- Save flow
- Schema comparison

### E2E Tests

- Complete contract creation flow
- Contract editing flow
- Validation workflow
- Schema comparison workflow

---

## Future Enhancements

### Phase 6+ (Post-MVP)

1. **Visual Editor Mode**
   - Drag-and-drop schema builder
   - Visual relationship mapping

2. **Template System**
   - Contract templates
   - Field templates
   - Rule templates

3. **Collaboration Features**
   - Real-time collaborative editing
   - Comments and annotations
   - Change tracking

4. **Advanced Validation**
   - Custom validation rules
   - Validation rule builder
   - Validation history

5. **Import/Export**
   - Export to ODCS/DataContract.com
   - Import from external sources
   - Bulk import/export

---

**Last Updated**: 2025-01-15  
**Version**: 1.0.0


