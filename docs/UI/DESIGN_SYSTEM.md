# Design System

**Last Updated**: 2025-01-15  
**Version**: 1.0.0

---

## Table of Contents

1. [Overview](#overview)
2. [Colors](#colors)
3. [Typography](#typography)
4. [Spacing](#spacing)
5. [Icons](#icons)
6. [Shadows and Elevation](#shadows-and-elevation)
7. [Borders and Dividers](#borders-and-dividers)
8. [Animation and Motion](#animation-and-motion)
9. [Design Tokens](#design-tokens)
10. [Theme Support](#theme-support)

---

## Overview

The Design System provides a comprehensive set of design tokens, components, and guidelines that ensure visual consistency across the Interoperable Data Hub platform. All UI components and interfaces should use these design tokens.

**Design System Principles**:
- **Consistency**: Unified visual language across all interfaces
- **Scalability**: Tokens support growth and customization
- **Accessibility**: All tokens meet WCAG 2.1 AA standards
- **Maintainability**: Centralized tokens for easy updates

---

## Colors

### Color Palette

The color palette is designed for accessibility, clarity, and brand consistency.

#### Primary Colors

**Primary Blue**
- `primary-50`: #E3F2FD (Lightest)
- `primary-100`: #BBDEFB
- `primary-200`: #90CAF9
- `primary-300`: #64B5F6
- `primary-400`: #42A5F5
- `primary-500`: #2196F3 (Base)
- `primary-600`: #1E88E5
- `primary-700`: #1976D2
- `primary-800`: #1565C0
- `primary-900`: #0D47A1 (Darkest)

**Usage**: Primary actions, links, brand elements

#### Secondary Colors

**Secondary Teal**
- `secondary-50`: #E0F2F1
- `secondary-100`: #B2DFDB
- `secondary-200`: #80CBC4
- `secondary-300`: #4DB6AC
- `secondary-400`: #26A69A
- `secondary-500`: #009688 (Base)
- `secondary-600`: #00897B
- `secondary-700`: #00796B
- `secondary-800`: #00695C
- `secondary-900`: #004D40

**Usage**: Secondary actions, accents, highlights

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

**Info (Blue)**
- `info-50`: #E3F2FD
- `info-100`: #BBDEFB
- `info-500`: #2196F3 (Base)
- `info-700`: #1976D2
- `info-900`: #0D47A1

**Usage**: Informational messages, help text, neutral status

#### Neutral Colors

**Gray Scale**
- `gray-50`: #FAFAFA (Lightest)
- `gray-100`: #F5F5F5
- `gray-200`: #EEEEEE
- `gray-300`: #E0E0E0
- `gray-400`: #BDBDBD
- `gray-500`: #9E9E9E (Base)
- `gray-600`: #757575
- `gray-700`: #616161
- `gray-800`: #424242
- `gray-900`: #212121 (Darkest)

**Usage**: Text, backgrounds, borders, dividers

#### Text Colors

- `text-primary`: `gray-900` (#212121) - Primary text
- `text-secondary`: `gray-700` (#616161) - Secondary text
- `text-disabled`: `gray-400` (#BDBDBD) - Disabled text
- `text-inverse`: `white` (#FFFFFF) - Text on dark backgrounds
- `text-link`: `primary-600` (#1E88E5) - Links
- `text-error`: `error-700` (#D32F2F) - Error text

#### Background Colors

- `background-default`: `white` (#FFFFFF) - Default background
- `background-paper`: `white` (#FFFFFF) - Card/paper background
- `background-elevated`: `gray-50` (#FAFAFA) - Elevated surfaces
- `background-hover`: `gray-100` (#F5F5F5) - Hover states
- `background-selected`: `primary-50` (#E3F2FD) - Selected states
- `background-disabled`: `gray-200` (#EEEEEE) - Disabled states

#### Border Colors

- `border-default`: `gray-300` (#E0E0E0) - Default borders
- `border-focus`: `primary-500` (#2196F3) - Focus borders
- `border-error`: `error-500` (#F44336) - Error borders
- `border-divider`: `gray-200` (#EEEEEE) - Dividers

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

### Font Families

**Primary Font**: Inter (or system font stack)
- Sans-serif, modern, highly readable
- Supports multiple languages
- Excellent screen rendering

**Font Stack**:
```css
font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', 
  'Roboto', 'Oxygen', 'Ubuntu', 'Cantarell', 'Fira Sans', 'Droid Sans', 
  'Helvetica Neue', sans-serif;
```

**Monospace Font**: 'Fira Code' or 'JetBrains Mono'
- Used for code, technical content, data values
- Font stack: `'Fira Code', 'Courier New', monospace`

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

The spacing system uses an 8px base unit for consistency.

| Token | Value | Usage |
|-------|-------|-------|
| `space-0` | 0px | No spacing |
| `space-1` | 4px (0.25rem) | Tight spacing |
| `space-2` | 8px (0.5rem) | Base unit |
| `space-3` | 12px (0.75rem) | Small spacing |
| `space-4` | 16px (1rem) | Default spacing |
| `space-5` | 20px (1.25rem) | Medium spacing |
| `space-6` | 24px (1.5rem) | Large spacing |
| `space-8` | 32px (2rem) | Extra large spacing |
| `space-10` | 40px (2.5rem) | Section spacing |
| `space-12` | 48px (3rem) | Page spacing |
| `space-16` | 64px (4rem) | Major section spacing |

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

| Token | Value | Usage |
|-------|-------|-------|
| `radius-none` | 0px | Sharp corners |
| `radius-sm` | 2px | Small elements |
| `radius-md` | 4px | Default radius |
| `radius-lg` | 8px | Cards, buttons |
| `radius-xl` | 12px | Large cards |
| `radius-full` | 9999px | Pills, avatars |

### Border Width

| Token | Value | Usage |
|-------|-------|-------|
| `border-none` | 0px | No border |
| `border-thin` | 1px | Default borders |
| `border-medium` | 2px | Focus states |
| `border-thick` | 3px | Emphasis |

### Dividers

- **Horizontal**: 1px solid `border-divider`
- **Vertical**: 1px solid `border-divider`
- **Spacing**: 16px margin on both sides

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

Design tokens are stored in JSON format for use across platforms.

```json
{
  "color": {
    "primary": {
      "50": "#E3F2FD",
      "500": "#2196F3",
      "900": "#0D47A1"
    }
  },
  "typography": {
    "fontFamily": {
      "primary": "Inter, sans-serif",
      "monospace": "Fira Code, monospace"
    },
    "fontSize": {
      "h1": "32px",
      "body1": "16px"
    }
  },
  "spacing": {
    "1": "4px",
    "2": "8px",
    "4": "16px"
  }
}
```

### Token Usage

- **CSS Variables**: Use CSS custom properties for runtime theming
- **JavaScript**: Import tokens in JavaScript/TypeScript
- **Documentation**: Keep tokens documented and versioned

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

**Last Updated**: 2025-01-15  
**Version**: 1.0.0

