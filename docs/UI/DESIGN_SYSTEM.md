# Design System

**Last Updated**: 2026-03-06  
**Version**: 2.0.0 (Meshant)

---

## Table of Contents

1. [Overview](#overview)
2. [Meshant Palette](#meschant-palette)
3. [Token Mapping (CSS ↔ tokens.ts)](#token-mapping-css--tokensts)
4. [Colors](#colors)
5. [Typography](#typography)
6. [Spacing](#spacing)
7. [Icons](#icons)
8. [Shadows and Elevation](#shadows-and-elevation)
9. [Borders and Dividers](#borders-and-dividers)
10. [Layout](#layout)
11. [Animation and Motion](#animation-and-motion)
12. [Design Tokens](#design-tokens)
13. [Theme Support](#theme-support)

---

## Overview

The Design System provides a comprehensive set of design tokens, components, and guidelines that ensure visual consistency across the Meshant platform. All UI components and interfaces should use these design tokens.

**Design System Principles**:
- **Consistency**: Unified visual language across all interfaces
- **Scalability**: Tokens support growth and customization
- **Accessibility**: All tokens meet WCAG 2.1 AA standards
- **Maintainability**: Centralized tokens for easy updates

**Reference**: [MESHANT_DESIGN_SYSTEM_PLAN.md](../../openspec/changes/useronboardfix/MESHANT_DESIGN_SYSTEM_PLAN.md)

---

## Meshant Palette

The Meshant design system uses a navy, blue, and cyan palette:

| Role | Base (#500) | Hex | Usage |
|------|-------------|-----|-------|
| **Primary** | Meshant Navy | `#0A1F44` | Headers, primary text on light, brand elements |
| **Secondary** | Meshant Blue | `#2F6BFF` | Primary actions, links, CTAs |
| **Accent** | Meshant Cyan | `#17C6E6` | Highlights, secondary accents, hover states |

**Full scales** (50–900) are defined in `frontend/src/index.css` and `frontend/src/shared/design-system/tokens.ts`.

---

## Token Mapping (CSS ↔ tokens.ts)

Single source of truth: `frontend/src/index.css` (CSS variables) and `frontend/src/shared/design-system/tokens.ts` (TypeScript). Both must stay in sync.

### Colors

| CSS Variable | tokens.ts | Value |
|--------------|-----------|-------|
| `--color-primary-500` | `colors.primary[500]` | #0A1F44 |
| `--color-primary-800` | `colors.primary[800]` | #0A1F44 |
| `--color-secondary-500` | `colors.secondary[500]` | #2F6BFF |
| `--color-accent-500` | `colors.accent[500]` | #17C6E6 |
| `--color-primary` | — | `var(--color-primary-500)` |
| `--color-secondary` | — | `var(--color-secondary-500)` |
| `--color-accent` | — | `var(--color-accent-500)` |

### Typography

| CSS Variable | tokens.ts | Value |
|--------------|-----------|-------|
| `--font-family-sans` | `typography.fontFamily.sans` | 'Inter', -apple-system, BlinkMacSystemFont, sans-serif |
| `--font-family-mono` | `typography.fontFamily.mono` | Monaco, Menlo, Consolas, monospace |
| `--font-size-base` | `typography.fontSize.base` | 16px |
| `--font-size-xs` | `typography.fontSize.xs` | 12px |
| `--font-size-sm` | `typography.fontSize.sm` | 14px |
| `--font-size-lg` | `typography.fontSize.lg` | 18px |
| `--font-size-xl` | `typography.fontSize.xl` | 20px |
| `--font-size-2xl` | `typography.fontSize['2xl']` | 24px |
| `--font-size-3xl` | `typography.fontSize['3xl']` | 30px |
| `--font-size-4xl` | `typography.fontSize['4xl']` | 36px |

### Spacing

| CSS Variable | tokens.ts | Value |
|--------------|-----------|-------|
| `--spacing-xs` | `spacing.xs` | 4px |
| `--spacing-sm` | `spacing.sm` | 8px |
| `--spacing-md` | `spacing.md` | 16px |
| `--spacing-lg` | `spacing.lg` | 24px |
| `--spacing-xl` | `spacing.xl` | 32px |
| `--spacing-2xl` | `spacing['2xl']` | 48px |
| `--spacing-3xl` | `spacing['3xl']` | 64px |

### Layout

| CSS Variable | tokens.ts | Value |
|--------------|-----------|-------|
| `--layout-sidebar-width` | `layout.sidebarWidth` | 240px |
| `--layout-content-max-width` | `layout.contentMaxWidth` | 1200px |

### Breakpoints (tokens.ts only)

| Token | Value |
|-------|-------|
| `breakpoints.sm` | 600px |
| `breakpoints.md` | 900px |
| `breakpoints.lg` | 1200px |
| `breakpoints.xl` | 1536px |

### Shadows

| CSS Variable | tokens.ts | Value |
|--------------|-----------|-------|
| `--shadow-sm` | `shadows.sm` | 0 1px 2px 0 rgba(0,0,0,0.05) |
| `--shadow-md` | `shadows.md` | 0 4px 6px -1px rgba(0,0,0,0.1) |
| `--shadow-lg` | `shadows.lg` | 0 10px 15px -3px rgba(0,0,0,0.1) |
| `--shadow-xl` | `shadows.xl` | 0 20px 25px -5px rgba(0,0,0,0.1) |

### Border Radius

| CSS Variable | tokens.ts | Value |
|--------------|-----------|-------|
| `--border-radius-sm` | `borderRadius.sm` | 4px |
| `--border-radius-md` | `borderRadius.md` | 8px |
| `--border-radius-lg` | `borderRadius.lg` | 12px |
| `--border-radius-xl` | `borderRadius.xl` | 16px |
| `--border-radius-full` | `borderRadius.full` | 9999px |

### Token Usage in Code

- **CSS**: Use `var(--color-primary)`, `var(--spacing-md)`, etc.
- **TypeScript**: Import from `shared/design-system/tokens` for computed values (e.g. breakpoints in media queries).
- **Extension**: Add new tokens in both `index.css` and `tokens.ts`; run `npm run test:run -- src/shared/design-system/` to verify.

---

## Colors

### Color Palette (Meshant)

#### Primary Colors (Meshant Navy)

- `primary-50`: #E8ECF4 (Lightest)
- `primary-100`: #CFD8E8
- `primary-200`: #9BA8C4
- `primary-300`: #6778A0
- `primary-400`: #33497C
- `primary-500`: #0A1F44 (Base)
- `primary-600`: #081A3A
- `primary-700`: #061530
- `primary-800`: #0A1F44
- `primary-900`: #030D22 (Darkest)

**Usage**: Headers, primary text on light backgrounds, brand elements, sidebar

#### Secondary Colors (Meshant Blue)

- `secondary-50`: #EBF0FF
- `secondary-100`: #D6E0FF
- `secondary-200`: #ADBFFF
- `secondary-300`: #849EFF
- `secondary-400`: #5B7DFF
- `secondary-500`: #2F6BFF (Base)
- `secondary-600`: #2756E6
- `secondary-700`: #1F41CC
- `secondary-800`: #172DB3
- `secondary-900`: #0F1999

**Usage**: Primary actions, links, CTAs, interactive elements

#### Accent Colors (Meshant Cyan)

- `accent-50`: #E6FAFC
- `accent-100`: #CCF5F9
- `accent-200`: #99EBF3
- `accent-300`: #66E0ED
- `accent-400`: #33D6E7
- `accent-500`: #17C6E6 (Base)
- `accent-600`: #12A0C0
- `accent-700`: #0E7A9A
- `accent-800`: #095474
- `accent-900`: #052E3D

**Usage**: Highlights, secondary accents, hover states, badges

#### Semantic Colors

**Success (Green)**
- `success-50`: #E8F5E9
- `success-100`: #C8E6C9
- `success-500`: #4CAF50 (Base)
- `success-700`: #388E3C
- `success-900`: #1B5E20

**Usage**: Success messages, positive status indicators, completed states

**Warning (Amber)**
- `warning-50`: #FFF8E1
- `warning-100`: #FFECB3
- `warning-500`: #FFC107 (Base)
- `warning-700`: #F57C00
- `warning-900`: #E65100

**Usage**: Warning messages, caution indicators, pending states

**Error (Red)**
- `error-50`: #FFEBEE
- `error-100`: #FFCDD2
- `error-500`: #F44336 (Base)
- `error-700`: #D32F2F
- `error-900`: #B71C1C

**Usage**: Error messages, failure states, destructive actions

**Info (Blue)** — Maps to Meshant primary
- `info-50`: `primary-50` (#E8ECF4)
- `info-100`: `primary-100` (#CFD8E8)
- `info-500`: `primary-500` (#0A1F44) (Base)
- `info-700`: `primary-700` (#061530)
- `info-900`: `primary-900` (#030D22)

**Usage**: Informational messages, help text, neutral status

#### Neutral Colors

**Gray Scale** (`neutral-*` in tokens.ts)
- `neutral-50`: #FAFAFA (Lightest)
- `neutral-100`: #F5F5F5
- `neutral-200`: #EEEEEE
- `neutral-300`: #E0E0E0
- `neutral-400`: #BDBDBD
- `neutral-500`: #9E9E9E (Base)
- `neutral-600`: #757575
- `neutral-700`: #616161
- `neutral-800`: #424242
- `neutral-900`: #212121 (Darkest)

**Usage**: Text, backgrounds, borders, dividers

#### Text Colors

- `--color-text-primary`: `neutral-900` (#212121) - Primary text
- `--color-text-secondary`: `neutral-700` (#616161) - Secondary text
- `--color-text-tertiary`: `neutral-600` (#757575) - Tertiary text
- `text-inverse`: `white` (#FFFFFF) - Text on dark backgrounds
- `text-link`: `--color-secondary` (#2F6BFF) - Links
- `text-error`: `error-700` (#D32F2F) - Error text

#### Background Colors

- `--color-background-primary`: `white` (#FFFFFF) - Default background
- `--color-background-secondary`: `neutral-50` (#FAFAFA) - Elevated surfaces
- `--color-background-tertiary`: `neutral-100` (#F5F5F5) - Hover states
- `background-selected`: `primary-100` (#CFD8E8) - Selected states
- `background-disabled`: `neutral-200` (#EEEEEE) - Disabled states

#### Border Colors

- `--color-border`: `neutral-300` (#E0E0E0) - Default borders
- `border-focus`: `primary-500` (#0A1F44) - Focus borders
- `border-error`: `error-500` (#F44336) - Error borders
- `--color-border-light`: `neutral-200` (#EEEEEE) - Dividers

### Color Usage Guidelines

1. **Contrast Requirements**:
   - Text on background: Minimum 4.5:1 for normal text, 3:1 for large text
   - UI components: Minimum 3:1 contrast
   - Use contrast checker tools to verify

2. **Color and Meaning**:
   - Use semantic colors consistently (green = success, red = error)
   - Don't rely on color alone; use icons and text
   - Test with colorblind simulators

3. **Accessibility**:
   - All color combinations meet WCAG 2.1 AA standards
   - Provide alternative indicators (icons, patterns) for color-only information

---

## Typography

### Font Families (Meshant)

**Primary Font**: Inter (Google Fonts: 400, 500, 600, 700)
- Loaded via `frontend/index.html` preconnect + stylesheet
- Sans-serif, modern, highly readable
- Supports multiple languages
- Excellent screen rendering

**Font Stack**:
```css
font-family: var(--font-family-sans);
/* Resolves to: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif */
```

**Monospace Font**: Monaco, Menlo, Consolas
- Used for code, technical content, data values
- Font stack: `var(--font-family-mono)` → `'Monaco', 'Menlo', 'Consolas', monospace`

**Air-gapped deployments**: Inter loads from Google Fonts. In offline environments, the fallback stack (`-apple-system`, `BlinkMacSystemFont`, `sans-serif`) is used. For self-hosted font, bundle Inter woff2 files and use `@font-face` locally.

### Type Scale

The typography system uses a modular scale based on 1.25 (Major Third).

| Scale | Size | Line Height | Weight | Usage |
|-------|------|-------------|--------|-------|
| `h1` | 32px (2rem) | 1.2 | 700 | Page titles |
| `h2` | 24px (1.5rem) | 1.3 | 600 | Section titles |
| `h3` | 20px (1.25rem) | 1.4 | 600 | Subsection titles |
| `h4` | 18px (1.125rem) | 1.4 | 600 | Card titles |
| `h5` | 16px (1rem) | 1.5 | 600 | Small headings |
| `h6` | 14px (0.875rem) | 1.5 | 600 | Labels |
| `body1` | 16px (1rem) | 1.5 | 400 | Body text |
| `body2` | 14px (0.875rem) | 1.5 | 400 | Secondary text |
| `caption` | 12px (0.75rem) | 1.4 | 400 | Captions, metadata |
| `overline` | 10px (0.625rem) | 1.6 | 600 | Overlines, tags |
| `code` | 14px (0.875rem) | 1.5 | 400 | Code snippets |

### Font Weights

- `300`: Light
- `400`: Regular (default)
- `500`: Medium
- `600`: Semi-bold
- `700`: Bold

### Typography Usage Guidelines

1. **Hierarchy**: Use type scale to establish clear visual hierarchy
2. **Readability**: Minimum 16px for body text
3. **Line Length**: Optimal 45-75 characters per line
4. **Line Height**: 1.5 for body text, 1.2-1.4 for headings
5. **Spacing**: Use consistent spacing between text elements

---

## Spacing

### Spacing Scale

The spacing system uses a 4px base unit. Align to 8px grid for consistency.

| Token | Value | Usage |
|-------|-------|-------|
| `--spacing-xs` | 4px | Tight spacing |
| `--spacing-sm` | 8px | Base unit |
| `--spacing-md` | 16px | Default spacing |
| `--spacing-lg` | 24px | Large spacing |
| `--spacing-xl` | 32px | Extra large spacing |
| `--spacing-2xl` | 48px | Section spacing |
| `--spacing-3xl` | 64px | Major section spacing |

### Spacing Usage Guidelines

1. **Consistency**: Use spacing tokens, not arbitrary values
2. **Alignment**: Align to 8px grid
3. **Relationships**: Related elements use smaller spacing, unrelated use larger
4. **Responsive**: Adjust spacing for smaller screens

---

## Icons

### Icon Library

**Primary**: Material Icons (Material Design Icons)
- Comprehensive icon set
- Consistent style
- Good accessibility support

**Alternative**: Custom icons for brand-specific elements

### Icon Sizes

| Size | Value | Usage |
|------|-------|-------|
| `icon-xs` | 12px | Inline with small text |
| `icon-sm` | 16px | Default inline icons |
| `icon-md` | 20px | Standard icons |
| `icon-lg` | 24px | Prominent icons |
| `icon-xl` | 32px | Hero icons |
| `icon-2xl` | 48px | Large display icons |

### Icon Usage Guidelines

1. **Consistency**: Use icons from the same library
2. **Meaning**: Icons should be universally understood
3. **Accessibility**: Provide text labels or ARIA labels
4. **Size**: Match icon size to text size
5. **Color**: Use semantic colors for status icons

### Common Icons

- **Actions**: Add, Edit, Delete, Save, Cancel, Search, Filter
- **Status**: Success (check), Error (X), Warning (alert), Info (info)
- **Navigation**: Home, Back, Forward, Menu, Close
- **Data**: Table, Chart, File, Folder, Download, Upload
- **System**: Settings, User, Notifications, Help

---

## Shadows and Elevation

### Elevation Levels

Material Design elevation system with 5 levels.

| Level | Shadow | Usage |
|-------|--------|-------|
| `elevation-0` | None | Flat surfaces |
| `elevation-1` | 0px 1px 3px rgba(0,0,0,0.12) | Cards, buttons |
| `elevation-2` | 0px 2px 6px rgba(0,0,0,0.12) | Hover states |
| `elevation-4` | 0px 4px 12px rgba(0,0,0,0.15) | Modals, dropdowns |
| `elevation-8` | 0px 8px 24px rgba(0,0,0,0.15) | Popovers, tooltips |
| `elevation-16` | 0px 16px 48px rgba(0,0,0,0.2) | Dialogs |

### Shadow Usage Guidelines

1. **Purpose**: Use elevation to show hierarchy and depth
2. **Consistency**: Use standard elevation levels
3. **Performance**: Avoid excessive shadows
4. **Accessibility**: Ensure sufficient contrast with shadows

---

## Borders and Dividers

### Border Radius

Aligns with `--border-radius-*` and `tokens.ts` `borderRadius`:

| Token | Value | Usage |
|-------|-------|-------|
| `--border-radius-none` | 0 | Sharp corners |
| `--border-radius-sm` | 4px | Small elements |
| `--border-radius-md` | 8px | Default radius |
| `--border-radius-lg` | 12px | Cards, buttons |
| `--border-radius-xl` | 16px | Large cards |
| `--border-radius-full` | 9999px | Pills, avatars |

### Border Width

| Token | Value | Usage |
|-------|-------|-------|
| `border-none` | 0px | No border |
| `border-thin` | 1px | Default borders |
| `border-medium` | 2px | Focus states |
| `border-thick` | 3px | Emphasis |

### Dividers

- **Horizontal**: 1px solid `var(--color-border-light)`
- **Vertical**: 1px solid `var(--color-border-light)`
- **Spacing**: 16px margin on both sides

---

## Layout

Meshant layout constants (Phase 28.7.4):

| Token | Value | Usage |
|-------|-------|-------|
| `--layout-sidebar-width` | 240px | App sidebar width |
| `--layout-content-max-width` | 1200px | Main content max-width, centered |

**Usage in CSS**:
```css
.app-sidebar { width: var(--layout-sidebar-width); }
.app-main { max-width: var(--layout-content-max-width); margin: 0 auto; }
```

**Breakpoints** (tokens.ts): `sm` 600px, `md` 900px, `lg` 1200px, `xl` 1536px.

---

## Animation and Motion

### Animation Principles

1. **Purpose**: Animations should enhance understanding, not distract
2. **Duration**: Keep animations short (150-300ms)
3. **Easing**: Use natural easing curves
4. **Performance**: Use CSS transforms and opacity for smooth animations

### Animation Durations

| Duration | Value | Usage |
|----------|-------|-------|
| `duration-fast` | 150ms | Micro-interactions |
| `duration-normal` | 250ms | Standard transitions |
| `duration-slow` | 350ms | Complex animations |

### Easing Functions

- **Ease In**: `cubic-bezier(0.4, 0, 1, 1)` - Entering elements
- **Ease Out**: `cubic-bezier(0, 0, 0.2, 1)` - Exiting elements
- **Ease In Out**: `cubic-bezier(0.4, 0, 0.2, 1)` - Standard transitions

### Common Animations

- **Fade**: Opacity 0 → 1 (150ms)
- **Slide**: Transform translate (250ms)
- **Scale**: Transform scale (200ms)
- **Rotate**: Transform rotate (300ms)

---

## Design Tokens

### Token Format

Design tokens live in two places (must stay in sync):

1. **CSS**: `frontend/src/index.css` — `:root` CSS custom properties
2. **TypeScript**: `frontend/src/shared/design-system/tokens.ts` — exported constants

**Meshant palette example** (tokens.ts):
```typescript
export const colors = {
  primary: { 500: '#0A1F44', ... },
  secondary: { 500: '#2F6BFF', ... },
  accent: { 500: '#17C6E6', ... },
  // ...
};
```

### Token Usage

- **CSS**: Use `var(--color-primary)`, `var(--spacing-md)`, etc.
- **TypeScript**: Import from `shared/design-system/tokens` for breakpoints, computed values
- **Extension**: Add tokens in both `index.css` and `tokens.ts`; run `npm run test:run -- src/shared/design-system/` to verify
- **Runbook**: See [Brand Name Change](../runbooks/BRAND_NAME_CHANGE.md) for changing brand/app name

---

## Theme Support

### Light Theme (Default)

- Primary background: White
- Text: Dark gray
- Accents: Primary blue

### Dark Theme (Future)

- Primary background: Dark gray
- Text: Light gray
- Accents: Light blue

### Theme Implementation

- Use CSS variables for theme values
- Support system preference (prefers-color-scheme)
- Provide theme toggle in settings
- Ensure all components support both themes

---

**Last Updated**: 2026-03-06  
**Version**: 2.0.0 (Meshant)

