# Accessibility Guidelines

**Last Updated**: 2025-01-15  
**Version**: 1.0.0

---

## Table of Contents

1. [Overview](#overview)
2. [WCAG Compliance](#wcag-compliance)
3. [Keyboard Navigation](#keyboard-navigation)
4. [Screen Readers](#screen-readers)
5. [Color and Contrast](#color-and-contrast)
6. [Focus Management](#focus-management)
7. [ARIA Labels and Roles](#aria-labels-and-roles)
8. [Forms and Inputs](#forms-and-inputs)
9. [Images and Media](#images-and-media)
10. [Testing Accessibility](#testing-accessibility)

---

## Overview

This document provides comprehensive accessibility guidelines for the Interoperable Data Hub platform. All interfaces must be accessible to users with disabilities, including those using assistive technologies.

**Accessibility Principles**:
- **Perceivable**: Information must be presentable to users in ways they can perceive
- **Operable**: Interface components must be operable by all users
- **Understandable**: Information and UI operation must be understandable
- **Robust**: Content must be robust enough for assistive technologies

**Compliance Target**: WCAG 2.1 Level AA (minimum)

---

## WCAG Compliance

### WCAG 2.1 Level AA Requirements

#### Perceivable

1. **Text Alternatives**
   - All images have alt text
   - Decorative images have empty alt text
   - Icons have text labels or ARIA labels

2. **Time-based Media**
   - Videos have captions
   - Audio has transcripts
   - Auto-playing media can be paused

3. **Adaptable**
   - Content can be presented without losing information
   - Information is not conveyed by color alone
   - Text can be resized up to 200% without loss of functionality

4. **Distinguishable**
   - Color contrast ratio of at least 4.5:1 for normal text
   - Color contrast ratio of at least 3:1 for large text
   - Text spacing can be adjusted

#### Operable

1. **Keyboard Accessible**
   - All functionality available via keyboard
   - No keyboard traps
   - Keyboard shortcuts don't conflict with browser shortcuts

2. **Enough Time**
   - Users can extend time limits
   - Moving, blinking, or auto-updating content can be paused

3. **Seizures and Physical Reactions**
   - No content flashes more than 3 times per second

4. **Navigable**
   - Clear page titles
   - Focus order is logical
   - Multiple ways to find content
   - Headings and labels are descriptive

#### Understandable

1. **Readable**
   - Language of page is identified
   - Unusual words are explained
   - Abbreviations are explained

2. **Predictable**
   - Navigation is consistent
   - Components with same functionality are identified consistently
   - Changes of context are initiated by user

3. **Input Assistance**
   - Errors are identified and described
   - Labels and instructions are provided
   - Error suggestions are provided

#### Robust

1. **Compatible**
   - Valid HTML
   - Proper use of ARIA attributes
   - Assistive technologies can parse content

---

## Keyboard Navigation

### Tab Order

- **Logical Order**: Tab order follows visual order
- **Skip Links**: Provide skip links for main content
- **Focus Indicators**: Visible focus indicators on all interactive elements

### Keyboard Shortcuts

**Global Shortcuts**:
- `Tab`: Move forward through interactive elements
- `Shift + Tab`: Move backward
- `Enter` / `Space`: Activate buttons and links
- `Esc`: Close modals, dismiss notifications
- `Arrow Keys`: Navigate within components (tabs, menus)

**Component-Specific**:
- **Dropdowns**: Arrow keys to navigate, Enter to select
- **Tabs**: Arrow keys to switch tabs
- **Tables**: Arrow keys to navigate cells
- **Modals**: Tab cycles within modal, Esc closes

### Implementation

```tsx
// Focusable element
<Button
  onKeyDown={(e) => {
    if (e.key === 'Enter' || e.key === ' ') {
      handleClick();
    }
  }}
>
  Click me
</Button>

// Skip link
<a href="#main-content" className="skip-link">
  Skip to main content
</a>
```

---

## Screen Readers

### Semantic HTML

Use semantic HTML elements:

```tsx
// Good: Semantic HTML
<header>
  <nav>
    <ul>
      <li><a href="/assets">Assets</a></li>
    </ul>
  </nav>
</header>

<main>
  <article>
    <h1>Asset Details</h1>
    <p>Content</p>
  </article>
</main>

// Bad: Div soup
<div>
  <div>
    <div>Assets</div>
  </div>
</div>
```

### ARIA Labels

Provide descriptive labels:

```tsx
// Icon button with label
<IconButton aria-label="Close dialog">
  <CloseIcon />
</IconButton>

// Form field with label
<TextField
  label="Asset Name"
  aria-describedby="asset-name-help"
/>
<FormHelperText id="asset-name-help">
  Enter a unique name for your asset
</FormHelperText>
```

### Live Regions

Announce dynamic content changes:

```tsx
// Status updates
<div role="status" aria-live="polite" aria-atomic="true">
  Asset created successfully
</div>

// Error messages
<div role="alert" aria-live="assertive">
  Error: Invalid input
</div>
```

---

## Color and Contrast

### Contrast Requirements

- **Normal Text** (≤18px): 4.5:1 contrast ratio
- **Large Text** (>18px or bold ≥14px): 3:1 contrast ratio
- **UI Components**: 3:1 contrast ratio
- **Graphical Objects**: 3:1 contrast ratio

### Color Usage

**Don't rely on color alone**:

```tsx
// Bad: Color only
<span style={{ color: 'red' }}>Error</span>

// Good: Color + icon + text
<span style={{ color: 'red' }}>
  <ErrorIcon aria-hidden="true" />
  Error: Invalid input
</span>
```

### Testing Contrast

Use tools to verify contrast:
- **WebAIM Contrast Checker**: https://webaim.org/resources/contrastchecker/
- **Chrome DevTools**: Accessibility panel
- **axe DevTools**: Automated testing

---

## Focus Management

### Visible Focus Indicators

All interactive elements must have visible focus indicators:

```css
/* Focus styles */
button:focus,
a:focus,
input:focus {
  outline: 2px solid #2196F3;
  outline-offset: 2px;
}

/* Custom focus for components */
.custom-button:focus-visible {
  box-shadow: 0 0 0 3px rgba(33, 150, 243, 0.3);
}
```

### Focus Trapping

Trap focus within modals:

```tsx
// Modal with focus trap
<Modal
  open={open}
  onClose={handleClose}
  aria-labelledby="modal-title"
>
  <FocusTrap>
    <DialogTitle id="modal-title">Confirm Delete</DialogTitle>
    <DialogContent>
      {/* Content */}
    </DialogContent>
    <DialogActions>
      <Button onClick={handleClose}>Cancel</Button>
      <Button onClick={handleConfirm}>Delete</Button>
    </DialogActions>
  </FocusTrap>
</Modal>
```

### Focus Restoration

Restore focus after closing modals:

```tsx
const handleClose = () => {
  // Save reference to element that opened modal
  const previousActiveElement = document.activeElement;
  
  setOpen(false);
  
  // Restore focus
  setTimeout(() => {
    previousActiveElement?.focus();
  }, 0);
};
```

---

## ARIA Labels and Roles

### Common ARIA Patterns

**Buttons**:
```tsx
<button aria-label="Close dialog">
  <CloseIcon aria-hidden="true" />
</button>
```

**Navigation**:
```tsx
<nav aria-label="Main navigation">
  <ul role="menubar">
    <li role="none">
      <a role="menuitem" href="/assets">Assets</a>
    </li>
  </ul>
</nav>
```

**Forms**:
```tsx
<form aria-label="Create asset">
  <label htmlFor="asset-name">Asset Name</label>
  <input
    id="asset-name"
    aria-required="true"
    aria-describedby="asset-name-error"
  />
  <div id="asset-name-error" role="alert">
    This field is required
  </div>
</form>
```

**Status**:
```tsx
<div role="status" aria-live="polite" aria-atomic="true">
  Loading assets...
</div>
```

---

## Forms and Inputs

### Label Association

All form fields must have associated labels:

```tsx
// Good: Explicit label
<label htmlFor="email">Email</label>
<input id="email" type="email" />

// Good: Implicit label
<label>
  Email
  <input type="email" />
</label>

// Good: aria-label
<input
  type="email"
  aria-label="Email address"
/>
```

### Error Messages

Provide clear, accessible error messages:

```tsx
<TextField
  label="Email"
  error={!!errors.email}
  helperText={errors.email}
  aria-describedby="email-error"
  aria-invalid={!!errors.email}
/>
<div id="email-error" role="alert">
  {errors.email}
</div>
```

### Required Fields

Indicate required fields:

```tsx
<TextField
  label="Asset Name"
  required
  aria-required="true"
  InputLabelProps={{
    required: true
  }}
/>
```

---

## Images and Media

### Alt Text

Provide descriptive alt text:

```tsx
// Informative image
<img
  src="chart.png"
  alt="Sales revenue increased 25% from Q1 to Q2"
/>

// Decorative image
<img
  src="decoration.png"
  alt=""
  aria-hidden="true"
/>

// Complex image (chart, diagram)
<img
  src="complex-chart.png"
  alt="Sales by region chart"
  aria-describedby="chart-description"
/>
<div id="chart-description">
  Detailed description of chart data
</div>
```

### Video and Audio

Provide captions and transcripts:

```tsx
<video controls>
  <source src="video.mp4" type="video/mp4" />
  <track
    kind="captions"
    src="captions.vtt"
    srcLang="en"
    label="English"
    default
  />
</video>
```

---

## Testing Accessibility

### Automated Testing

**Tools**:
- **axe DevTools**: Browser extension for automated testing
- **WAVE**: Web accessibility evaluation tool
- **Lighthouse**: Accessibility audit
- **Pa11y**: Command-line accessibility testing

**Example**:
```bash
# Run axe tests
npm run test:a11y

# Lighthouse audit
lighthouse http://localhost:3000 --view
```

### Manual Testing

**Keyboard Testing**:
- [ ] All interactive elements are keyboard accessible
- [ ] Tab order is logical
- [ ] Focus indicators are visible
- [ ] No keyboard traps
- [ ] Keyboard shortcuts work

**Screen Reader Testing**:
- [ ] Test with NVDA (Windows) or VoiceOver (Mac/iOS)
- [ ] All content is announced correctly
- [ ] Form labels are associated
- [ ] Error messages are announced
- [ ] Dynamic content changes are announced

**Visual Testing**:
- [ ] Color contrast meets requirements
- [ ] Information is not conveyed by color alone
- [ ] Text can be resized up to 200%
- [ ] Content is readable at all zoom levels

### Testing Checklist

**Per Component**:
- [ ] Keyboard accessible
- [ ] Screen reader friendly
- [ ] Proper ARIA labels
- [ ] Focus management
- [ ] Color contrast
- [ ] Error handling

**Per Page**:
- [ ] Page title is descriptive
- [ ] Heading hierarchy is logical
- [ ] Skip links provided
- [ ] Language is identified
- [ ] All images have alt text
- [ ] Forms are accessible

---

## Accessibility Resources

### Tools

- **axe DevTools**: https://www.deque.com/axe/devtools/
- **WAVE**: https://wave.webaim.org/
- **WebAIM Contrast Checker**: https://webaim.org/resources/contrastchecker/
- **Screen Reader Testing**: NVDA, JAWS, VoiceOver

### Documentation

- **WCAG 2.1**: https://www.w3.org/WAI/WCAG21/quickref/
- **ARIA Authoring Practices**: https://www.w3.org/WAI/ARIA/apg/
- **WebAIM**: https://webaim.org/

---

**Last Updated**: 2025-01-15  
**Version**: 1.0.0

