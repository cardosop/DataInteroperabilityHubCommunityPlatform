import type { Preview } from '@storybook/react-vite'
import { ThemeProvider, CssBaseline } from '@mui/material'
import { createAppTheme } from '../src/lib/config/mui'
import { I18nextProvider } from 'react-i18next'
import i18n from '../src/lib/config/i18n'
import '../src/index.css'

/**
 * Storybook Preview Configuration
 *
 * This configuration provides:
 * - Material-UI theme provider with light/dark mode support
 * - i18n internationalization support
 * - Global CSS styles
 * - Accessibility testing
 * - Responsive viewport testing
 * - Interactive controls for all props
 * - Comprehensive documentation
 */

const preview: Preview = {
  parameters: {
    // Controls configuration for interactive prop editing
    controls: {
      matchers: {
        color: /(background|color)$/i,
        date: /Date$/i,
      },
      expanded: true,
      sort: 'requiredFirst',
    },
    // Actions configuration for event handlers
    actions: {
      argTypesRegex: '^on[A-Z].*',
    },
    // Accessibility testing
    a11y: {
      config: {
        rules: [
          {
            id: 'color-contrast',
            enabled: true,
          },
          {
            id: 'keyboard-navigation',
            enabled: true,
          },
          {
            id: 'aria-required-attr',
            enabled: true,
          },
        ],
      },
      options: {
        checks: { 'color-contrast': { options: { noScroll: true } } },
        restoreScroll: true,
      },
    },
    // Viewport configuration for responsive testing
    viewport: {
      viewports: {
        mobile: {
          name: 'Mobile',
          styles: {
            width: '375px',
            height: '667px',
          },
        },
        tablet: {
          name: 'Tablet',
          styles: {
            width: '768px',
            height: '1024px',
          },
        },
        desktop: {
          name: 'Desktop',
          styles: {
            width: '1024px',
            height: '768px',
          },
        },
        desktopLarge: {
          name: 'Desktop Large',
          styles: {
            width: '1440px',
            height: '900px',
          },
        },
      },
      defaultViewport: 'desktop',
    },
    // Backgrounds for testing components on different backgrounds
    backgrounds: {
      default: 'light',
      values: [
        {
          name: 'light',
          value: '#ffffff',
        },
        {
          name: 'dark',
          value: '#121212',
        },
        {
          name: 'gray',
          value: '#f5f5f5',
        },
      ],
    },
    // Documentation configuration
    docs: {
      toc: true,
      source: {
        type: 'code',
        state: 'open',
      },
    },
    // Layout configuration
    layout: 'padded',
  },
  // Global decorators to wrap all stories
  decorators: [
    (Story, context) => {
      // Get theme mode from story args or default to light
      const themeMode = context.globals.themeMode || 'light'
      const locale = context.globals.locale || 'en'

      // Change i18n language when locale changes
      if (i18n.language !== locale) {
        i18n.changeLanguage(locale)
      }

      const theme = createAppTheme(themeMode)

      return (
        <I18nextProvider i18n={i18n}>
          <ThemeProvider theme={theme}>
            <CssBaseline />
            <Story />
          </ThemeProvider>
        </I18nextProvider>
      )
    },
  ],
  // Global types for story controls
  globalTypes: {
    themeMode: {
      description: 'Theme mode for Material-UI',
      defaultValue: 'light',
      toolbar: {
        title: 'Theme Mode',
        icon: 'circlehollow',
        items: [
          { value: 'light', icon: 'circlehollow', title: 'Light' },
          { value: 'dark', icon: 'circle', title: 'Dark' },
        ],
        dynamicTitle: true,
      },
    },
    locale: {
      description: 'Internationalization locale',
      defaultValue: 'en',
      toolbar: {
        icon: 'globe',
        items: [
          { value: 'en', title: 'English' },
          { value: 'es', title: 'Español' },
          { value: 'fr', title: 'Français' },
        ],
        showName: true,
        dynamicTitle: true,
      },
    },
  },
}

export default preview
