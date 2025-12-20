# Storybook Configuration

This directory contains the Storybook configuration for the Data Interoperability Hub frontend.

## Files

- `main.ts` - Main Storybook configuration (addons, framework, stories)
- `preview.ts` - Preview configuration (decorators, parameters, global types)
- `manager.ts` - Manager configuration (UI theme, toolbar settings)
- `ComponentGuidelines.mdx` - Component usage guidelines and best practices

## Configuration Overview

### Addons

The following addons are configured:

- **@chromatic-com/storybook** - Visual regression testing with Chromatic
- **@storybook/addon-vitest** - Run Vitest tests in Storybook
- **@storybook/addon-a11y** - Accessibility testing
- **@storybook/addon-docs** - Automatic documentation generation
- **@storybook/addon-onboarding** - Interactive onboarding for new users

### Features

- **Material-UI Integration**: Full MUI theme support with light/dark mode
- **i18n Support**: Internationalization with language switching
- **Accessibility Testing**: Automated a11y checks on all stories
- **Responsive Testing**: Multiple viewport configurations
- **Interactive Controls**: Dynamic prop editing
- **Comprehensive Documentation**: Auto-generated docs with examples

### Global Types

- **themeMode**: Switch between light and dark themes
- **locale**: Switch between supported languages (en, es, fr)

## Usage

### Running Storybook

```bash
npm run storybook
```

Starts Storybook development server on `http://localhost:6006`

### Building Storybook

```bash
npm run build-storybook
```

Builds static Storybook for deployment.

### Chromatic Visual Testing

```bash
# Set your Chromatic project token
export CHROMATIC_PROJECT_TOKEN=your_token_here

# Run Chromatic
npm run chromatic
```

## Story Structure

Stories should be placed alongside components:

```
src/
  components/
    Button/
      Button.tsx
      Button.stories.tsx
```

## Best Practices

See `ComponentGuidelines.mdx` for comprehensive guidelines on:

- Component development standards
- Story creation guidelines
- Accessibility requirements
- Responsive design
- Testing practices

## Troubleshooting

### Environment Variables

Storybook mocks environment variables in `main.ts`. If you need to test with different values, update the `viteFinal` configuration.

### Theme Issues

If MUI theme isn't applying correctly, check:
1. Theme provider is in preview decorators
2. CssBaseline is included
3. Theme mode global type is configured

### i18n Issues

If translations aren't working:
1. Check locale files are imported correctly
2. Verify i18n is initialized in preview
3. Check locale global type is configured

## Resources

- [Storybook Documentation](https://storybook.js.org/docs)
- [Chromatic Documentation](https://www.chromatic.com/docs)
- [Material-UI Storybook Integration](https://mui.com/material-ui/integrations/storybook/)

