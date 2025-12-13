# Responsive Design Guidelines

**Last Updated**: 2025-01-15  
**Version**: 1.0.0

---

## Table of Contents

1. [Overview](#overview)
2. [Breakpoints](#breakpoints)
3. [Mobile-First Approach](#mobile-first-approach)
4. [Layout Patterns](#layout-patterns)
5. [Component Responsiveness](#component-responsiveness)
6. [Typography Scaling](#typography-scaling)
7. [Touch Targets](#touch-targets)
8. [Navigation Patterns](#navigation-patterns)
9. [Image and Media](#image-and-media)
10. [Testing Responsive Design](#testing-responsive-design)

---

## Overview

This document provides comprehensive guidelines for responsive design across the Interoperable Data Hub platform. All interfaces must work seamlessly across devices, from mobile phones to large desktop screens.

**Responsive Design Principles**:
- **Mobile-First**: Design for mobile, enhance for larger screens
- **Fluid Layouts**: Use flexible layouts that adapt to screen size
- **Touch-Friendly**: Ensure touch targets are appropriately sized
- **Performance**: Optimize for mobile network conditions
- **Accessibility**: Maintain accessibility across all screen sizes

---

## Breakpoints

### Standard Breakpoints

The design system uses the following breakpoints:

| Breakpoint | Min Width | Device Type | Usage |
|------------|-----------|-------------|-------|
| `xs` | 0px | Mobile (portrait) | Small phones |
| `sm` | 600px | Mobile (landscape), Tablet (portrait) | Large phones, small tablets |
| `md` | 960px | Tablet (landscape) | Tablets |
| `lg` | 1280px | Desktop | Laptops, small desktops |
| `xl` | 1920px | Large Desktop | Large monitors |

### Breakpoint Usage

```tsx
// Material-UI breakpoints
const theme = {
  breakpoints: {
    values: {
      xs: 0,
      sm: 600,
      md: 960,
      lg: 1280,
      xl: 1920
    }
  }
};

// Usage in components
<Box
  sx={{
    width: { xs: '100%', sm: '50%', md: '33%', lg: '25%' }
  }}
>
  Content
</Box>
```

---

## Mobile-First Approach

### Design Strategy

1. **Start with Mobile**: Design for smallest screen first
2. **Progressive Enhancement**: Add features and complexity for larger screens
3. **Content Priority**: Show most important content first
4. **Performance**: Optimize for mobile network speeds

### Implementation

```css
/* Mobile-first CSS */
.container {
  padding: 16px; /* Mobile default */
}

@media (min-width: 600px) {
  .container {
    padding: 24px; /* Tablet and up */
  }
}

@media (min-width: 1280px) {
  .container {
    padding: 32px; /* Desktop */
    max-width: 1200px;
    margin: 0 auto;
  }
}
```

---

## Layout Patterns

### Pattern: Single Column to Multi-Column

**Mobile**: Single column, full width
**Tablet**: 2 columns
**Desktop**: 3-4 columns

```tsx
<Grid container spacing={2}>
  <Grid item xs={12} sm={6} md={4} lg={3}>
    <Card>Item 1</Card>
  </Grid>
  <Grid item xs={12} sm={6} md={4} lg={3}>
    <Card>Item 2</Card>
  </Grid>
</Grid>
```

### Pattern: Stack to Side-by-Side

**Mobile**: Stacked vertically
**Desktop**: Side-by-side

```tsx
<Stack
  direction={{ xs: 'column', md: 'row' }}
  spacing={2}
>
  <Box flex={1}>Left Content</Box>
  <Box flex={1}>Right Content</Box>
</Stack>
```

### Pattern: Hidden on Small Screens

**Mobile**: Hide less important content
**Desktop**: Show all content

```tsx
<Box
  sx={{
    display: { xs: 'none', md: 'block' }
  }}
>
  Additional Content
</Box>
```

---

## Component Responsiveness

### Header

**Mobile**:
- Collapsed navigation (hamburger menu)
- Simplified logo
- Essential actions only

**Desktop**:
- Full navigation visible
- Complete logo
- All actions visible

### Sidebar

**Mobile**:
- Hidden by default (drawer)
- Overlay when open
- Full width when open

**Desktop**:
- Always visible
- Collapsible (240px → 64px)
- No overlay

### Tables

**Mobile**:
- Horizontal scroll
- Simplified columns
- Card view option

**Desktop**:
- All columns visible
- Full functionality
- Inline actions

### Forms

**Mobile**:
- Single column
- Full-width inputs
- Stacked buttons

**Desktop**:
- Multi-column where appropriate
- Optimal input widths
- Side-by-side buttons

---

## Typography Scaling

### Responsive Typography

```tsx
const theme = {
  typography: {
    h1: {
      fontSize: '2rem',      // 32px on mobile
      '@media (min-width:600px)': {
        fontSize: '2.5rem'  // 40px on tablet+
      }
    },
    body1: {
      fontSize: '1rem',      // 16px (consistent)
      lineHeight: 1.5
    }
  }
};
```

### Readable Line Length

- **Mobile**: Full width (with padding)
- **Desktop**: Max 75 characters per line
- **Large Text**: Slightly wider (80-90 characters)

---

## Touch Targets

### Minimum Sizes

- **Touch Target**: 44px × 44px minimum (iOS), 48px × 48px (Material Design)
- **Button Height**: 40px minimum (mobile), 48px preferred
- **Input Height**: 48px minimum
- **Icon Button**: 48px × 48px

### Spacing

- **Between Touch Targets**: 8px minimum
- **Padding**: 12px minimum inside touch targets
- **Safe Areas**: Account for device notches and home indicators

### Examples

```tsx
// Good: Large touch target
<IconButton size="large" sx={{ minWidth: 48, minHeight: 48 }}>
  <Icon />
</IconButton>

// Good: Adequate spacing
<Stack direction="row" spacing={2}>
  <Button>Action 1</Button>
  <Button>Action 2</Button>
</Stack>
```

---

## Navigation Patterns

### Mobile Navigation

**Pattern**: Bottom Navigation or Hamburger Menu

```tsx
// Bottom Navigation (for primary actions)
<BottomNavigation>
  <BottomNavigationAction icon={<HomeIcon />} label="Home" />
  <BottomNavigationAction icon={<AssetsIcon />} label="Assets" />
  <BottomNavigationAction icon={<MarketplaceIcon />} label="Marketplace" />
</BottomNavigation>

// Hamburger Menu (for secondary navigation)
<Drawer anchor="left" open={open} onClose={handleClose}>
  <List>
    <ListItem>Assets</ListItem>
    <ListItem>Marketplace</ListItem>
  </List>
</Drawer>
```

### Desktop Navigation

**Pattern**: Horizontal Navigation Bar

```tsx
<AppBar>
  <Toolbar>
    <Logo />
    <Tabs>
      <Tab label="Assets" />
      <Tab label="Marketplace" />
    </Tabs>
    <UserMenu />
  </Toolbar>
</AppBar>
```

---

## Image and Media

### Responsive Images

```tsx
<img
  src="image.jpg"
  srcSet="image-small.jpg 600w, image-large.jpg 1200w"
  sizes="(max-width: 600px) 100vw, 50vw"
  alt="Description"
/>
```

### Aspect Ratios

Maintain aspect ratios across screen sizes:

```css
.image-container {
  aspect-ratio: 16 / 9;
  width: 100%;
  object-fit: cover;
}
```

### Video

- **Mobile**: Full width, autoplay disabled
- **Desktop**: Optimal size, autoplay optional
- **Controls**: Always visible and accessible

---

## Testing Responsive Design

### Device Testing

Test on real devices:
- **Mobile**: iPhone, Android phones
- **Tablet**: iPad, Android tablets
- **Desktop**: Various screen sizes

### Browser Testing

Test in:
- Chrome (desktop and mobile)
- Safari (desktop and iOS)
- Firefox
- Edge

### Tools

- **Browser DevTools**: Responsive design mode
- **Chrome DevTools**: Device toolbar
- **BrowserStack**: Cross-browser testing
- **Lighthouse**: Performance and accessibility

### Checklist

- [ ] Layout works on all breakpoints
- [ ] Text is readable on all screen sizes
- [ ] Touch targets are appropriately sized
- [ ] Navigation is accessible on mobile
- [ ] Forms are usable on mobile
- [ ] Images scale appropriately
- [ ] No horizontal scrolling (unless intentional)
- [ ] Performance is acceptable on mobile networks

---

## Common Responsive Patterns

### Pattern: Responsive Grid

```tsx
<Grid container spacing={2}>
  <Grid item xs={12} sm={6} md={4}>
    {/* 1 column mobile, 2 tablet, 3 desktop */}
  </Grid>
</Grid>
```

### Pattern: Responsive Typography

```tsx
<Typography
  variant="h1"
  sx={{
    fontSize: { xs: '1.5rem', sm: '2rem', md: '2.5rem' }
  }}
>
  Title
</Typography>
```

### Pattern: Responsive Spacing

```tsx
<Box
  sx={{
    padding: { xs: 2, sm: 3, md: 4 }
  }}
>
  Content
</Box>
```

### Pattern: Show/Hide Based on Screen Size

```tsx
<Box
  sx={{
    display: { xs: 'none', md: 'block' }
  }}
>
  Desktop Only Content
</Box>

<Box
  sx={{
    display: { xs: 'block', md: 'none' }
  }}
>
  Mobile Only Content
</Box>
```

---

**Last Updated**: 2025-01-15  
**Version**: 1.0.0

