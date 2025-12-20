# Visual Regression Testing with Chromatic

**Last Updated**: 2025-01-15
**Version**: 1.0.0

---

## Overview

This document describes the visual regression testing setup using Chromatic for the Data Interoperability Hub frontend. Visual regression testing ensures that UI components maintain their visual appearance across changes and updates.

**Visual Regression Testing Principles**:
- **Automated**: Visual tests run automatically on every PR
- **Comprehensive**: Tests all breakpoints and themes
- **Fast Feedback**: Quick detection of visual regressions
- **Easy Review**: Visual diffs make it easy to review changes

---

## What is Visual Regression Testing?

Visual regression testing captures screenshots of UI components and compares them against baseline images. When a visual change is detected, the test flags it for review, allowing developers to:

1. **Catch unintended visual changes** before they reach production
2. **Review intentional changes** visually before merging
3. **Maintain design consistency** across the application
4. **Test responsive layouts** at all breakpoints

---

## Chromatic Setup

### Installation

Chromatic is already installed and configured. The following packages are included:

- `@chromatic-com/storybook` - Chromatic addon for Storybook
- Chromatic CLI (via npx)

### Configuration Files

#### `.chromatic.config.json`

Main Chromatic configuration file:

```json
{
  "projectToken": "",
  "buildScriptName": "build-storybook",
  "exitOnceUploaded": true,
  "exitZeroOnChanges": true,
  "ignoreLastBuildOnBranch": "main",
  "onlyChanged": false,
  "zip": true,
  "skip": false,
  "storybookBaseDir": ".",
  "storybookBuildDir": "storybook-static",
  "storybookConfigDir": ".storybook",
  "storybookLogFile": ".chromatic.log",
  "uploadMetadata": true,
  "tracing": false,
  "diagnostics": true
}
```

#### Storybook Preview Configuration

Chromatic is configured in `.storybook/preview.tsx`:

```typescript
chromatic: {
  // Test all viewports for responsive design
  viewports: [375, 768, 1024, 1440],
  // Delay to ensure animations complete
  delay: 300,
  // Disable animations for consistent screenshots
  disableAnimations: false,
  // Pause animations at the end
  pauseAnimationAtEnd: true,
  // Diff threshold for visual changes (0.0 to 1.0)
  diffThreshold: 0.05,
  // Capture screenshots with different themes
  modes: {
    light: {
      themeMode: 'light',
    },
    dark: {
      themeMode: 'dark',
    },
  },
}
```

---

## Breakpoints Configuration

Visual regression tests run at the following breakpoints to ensure responsive design is maintained:

| Breakpoint | Width | Height | Device Type |
|------------|-------|--------|-------------|
| Mobile | 375px | 667px | Small phones |
| Tablet | 768px | 1024px | Tablets |
| Desktop | 1024px | 768px | Laptops, small desktops |
| Desktop Large | 1440px | 900px | Large monitors |

These breakpoints match the viewport configurations in Storybook and align with the design system breakpoints.

---

## CI/CD Integration

### GitHub Actions Workflow

Visual regression tests run automatically via GitHub Actions workflow (`.github/workflows/visual-regression.yml`):

**Triggers**:
- Pull requests to `main` or `develop` branches
- Pushes to `main` or `develop` branches
- Manual workflow dispatch

**Workflow Steps**:
1. Checkout code
2. Setup Node.js
3. Install dependencies
4. Build Storybook
5. Run Chromatic visual tests
6. Comment PR with Chromatic link (if PR)

### Environment Variables

The workflow requires the following secret:

- `CHROMATIC_PROJECT_TOKEN` - Your Chromatic project token

**Setting up the token**:
1. Get your project token from Chromatic dashboard
2. Add it as a GitHub secret: `Settings > Secrets > Actions > New repository secret`
3. Name: `CHROMATIC_PROJECT_TOKEN`
4. Value: Your Chromatic project token

---

## Running Visual Tests

### Local Development

#### Run Chromatic Locally

```bash
# Set your Chromatic project token
export CHROMATIC_PROJECT_TOKEN=your_token_here

# Run Chromatic
cd frontend
npm run chromatic
```

#### Run Chromatic in CI Mode

```bash
# CI mode (exits after upload)
npm run chromatic:ci
```

### Storybook Commands

```bash
# Start Storybook development server
npm run storybook

# Build Storybook for production
npm run build-storybook
```

---

## Visual Test Baselines

### Creating Baselines

Baselines are created automatically when:
1. First run of Chromatic for a story
2. Visual changes are accepted in Chromatic dashboard
3. Baselines are updated on the `main` branch

### Updating Baselines

To update baselines:

1. **Via Chromatic Dashboard**:
   - Review visual changes in Chromatic
   - Accept changes to update baselines
   - Baselines are updated for all breakpoints and themes

2. **Via Command Line**:
   ```bash
   # Accept all changes (use with caution)
   npx chromatic --auto-accept-changes
   ```

### Baseline Management

- Baselines are stored in Chromatic cloud
- Each story has baselines for all configured viewports
- Baselines are versioned and can be rolled back
- Baselines are branch-specific (main branch is authoritative)

---

## Best Practices

### Story Creation

1. **Comprehensive Coverage**: Create stories for all component states
2. **Responsive Testing**: Ensure stories work at all breakpoints
3. **Theme Testing**: Test both light and dark themes
4. **Interaction States**: Include hover, focus, active states

### Visual Testing

1. **Review Changes Carefully**: Always review visual diffs before accepting
2. **Test Responsive**: Verify changes at all breakpoints
3. **Test Themes**: Check both light and dark mode
4. **Avoid Flaky Tests**: Use consistent data and avoid timestamps

### CI/CD

1. **Don't Skip Tests**: Always run visual tests on PRs
2. **Review PR Comments**: Check Chromatic links in PR comments
3. **Accept Intended Changes**: Accept intentional visual changes promptly
4. **Fix Regressions**: Address unintended visual changes immediately

---

## Troubleshooting

### Common Issues

#### Tests Fail Due to Flaky Animations

**Solution**: Increase delay in Chromatic configuration:
```typescript
chromatic: {
  delay: 500, // Increase delay
}
```

#### Tests Fail Due to Dynamic Content

**Solution**: Use consistent mock data in stories:
```typescript
export const Default: Story = {
  args: {
    date: '2025-01-15', // Use fixed date instead of new Date()
  },
}
```

#### Tests Fail Due to Font Rendering

**Solution**: Ensure fonts are loaded before screenshots:
```typescript
parameters: {
  chromatic: {
    delay: 1000, // Wait for fonts to load
  },
}
```

#### Build Fails in CI

**Solution**: Check Chromatic logs:
1. View workflow logs in GitHub Actions
2. Check `.chromatic.log` file
3. Verify `CHROMATIC_PROJECT_TOKEN` is set correctly

### Getting Help

1. **Chromatic Documentation**: https://www.chromatic.com/docs
2. **Storybook Documentation**: https://storybook.js.org/docs
3. **Check Logs**: Review `.chromatic.log` for detailed error messages
4. **Contact Team**: Reach out to the frontend team for assistance

---

## Workflow Examples

### Adding Visual Tests to a New Component

1. **Create Story File**:
   ```typescript
   // Button.stories.tsx
   import type { Meta, StoryObj } from '@storybook/react'
   import { Button } from './Button'

   const meta: Meta<typeof Button> = {
     title: 'Components/Button',
     component: Button,
   }

   export default meta
   type Story = StoryObj<typeof Button>

   export const Primary: Story = {
     args: {
       children: 'Click me',
       variant: 'contained',
     },
   }
   ```

2. **Run Chromatic**:
   ```bash
   npm run chromatic
   ```

3. **Review Baselines**: Check Chromatic dashboard for new baselines

### Updating Visual Baselines

1. **Make Visual Changes**: Update component styling
2. **Run Chromatic**: Visual tests will detect changes
3. **Review Diffs**: Check Chromatic dashboard for visual diffs
4. **Accept Changes**: Accept intentional changes in Chromatic dashboard

### Fixing Visual Regressions

1. **Identify Regression**: Check Chromatic dashboard or PR comments
2. **Review Diff**: Understand what changed visually
3. **Fix Issue**: Update component to match expected appearance
4. **Re-run Tests**: Verify fix with Chromatic

---

## Resources

- **Chromatic Documentation**: https://www.chromatic.com/docs
- **Storybook Documentation**: https://storybook.js.org/docs
- **Visual Testing Best Practices**: https://www.chromatic.com/docs/test
- **Chromatic Dashboard**: https://www.chromatic.com/builds

---

**Last Updated**: 2025-01-15
**Version**: 1.0.0

