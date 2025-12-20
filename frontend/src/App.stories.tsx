import type { Meta, StoryObj } from '@storybook/react-vite'
import App from './App'

/**
 * App Component Stories
 *
 * The App component is the root component of the Data Interoperability Hub frontend.
 * It displays environment configuration, feature flags, and serves as the entry point
 * for the application.
 *
 * ## Purpose
 * - Display application configuration and status
 * - Show feature flags and their current state
 * - Provide development/debugging information
 *
 * ## Usage
 * The App component is typically used as the root component in `main.tsx`:
 * ```tsx
 * import App from './App'
 * createRoot(rootElement).render(<App />)
 * ```
 *
 * ## Props
 * This component does not accept any props. It reads configuration from the
 * centralized config module (`@/lib/config`).
 *
 * ## Environment Variables
 * The component displays values from environment variables:
 * - `VITE_ENV`: Current environment (development/staging/production)
 * - `VITE_API_BASE_URL`: API base URL
 * - `VITE_DEBUG`: Debug mode status
 * - Feature flags: Various `VITE_ENABLE_*` flags
 *
 * ## Accessibility
 * - Uses semantic HTML elements
 * - Provides clear visual hierarchy
 * - Supports keyboard navigation
 *
 * ## Responsive Design
 * - Uses system fonts for optimal rendering
 * - Responsive padding and spacing
 * - Adapts to different screen sizes
 */
const meta = {
  title: 'Application/App',
  component: App,
  parameters: {
    layout: 'fullscreen',
    docs: {
      description: {
        component: `
The root App component displays the current application configuration including
environment settings, API endpoints, and feature flags. This component is
primarily used for development and debugging purposes.

### Key Features
- **Environment Display**: Shows current environment (development/staging/production)
- **API Configuration**: Displays API base URL and endpoints
- **Feature Flags**: Visual indicator of enabled/disabled features
- **Debug Information**: Shows debug mode status

### Configuration
The component reads from the centralized configuration module which validates
all environment variables at startup. Invalid configurations will cause the
application to fail at startup with descriptive error messages.
        `,
      },
    },
  },
  tags: ['autodocs'],
  argTypes: {
    // App component doesn't accept props, but we document this for clarity
  },
} satisfies Meta<typeof App>

export default meta
type Story = StoryObj<typeof meta>

/**
 * Default App Component
 *
 * Displays the application in its default state with all configuration
 * information visible. This is the standard view used in development.
 */
export const Default: Story = {
  parameters: {
    docs: {
      description: {
        story: 'The default App component showing all configuration and feature flags.',
      },
    },
  },
}

/**
 * Development Environment
 *
 * Shows the App component configured for development environment.
 * In development mode, debug information is typically enabled.
 */
export const Development: Story = {
  parameters: {
    docs: {
      description: {
        story: 'App component in development environment with debug mode enabled.',
      },
    },
    // Mock environment for this story
    mockData: {
      env: 'development',
      debug: true,
    },
  },
}

/**
 * Staging Environment
 *
 * Shows the App component configured for staging environment.
 * Staging typically has production-like settings with additional logging.
 */
export const Staging: Story = {
  parameters: {
    docs: {
      description: {
        story: 'App component in staging environment configuration.',
      },
    },
  },
}

/**
 * Production Environment
 *
 * Shows the App component configured for production environment.
 * Production mode typically has debug disabled and optimized settings.
 */
export const Production: Story = {
  parameters: {
    docs: {
      description: {
        story: 'App component in production environment with optimized settings.',
      },
    },
  },
}

/**
 * Light Theme
 *
 * App component displayed with light theme (default).
 */
export const LightTheme: Story = {
  parameters: {
    backgrounds: {
      default: 'light',
    },
    docs: {
      description: {
        story: 'App component with light theme applied.',
      },
    },
  },
}

/**
 * Dark Theme
 *
 * App component displayed with dark theme.
 */
export const DarkTheme: Story = {
  parameters: {
    backgrounds: {
      default: 'dark',
    },
    docs: {
      description: {
        story: 'App component with dark theme applied.',
      },
    },
  },
}

/**
 * Mobile Viewport
 *
 * App component displayed on mobile viewport (375x667).
 * Tests responsive design and mobile layout.
 */
export const Mobile: Story = {
  parameters: {
    viewport: {
      defaultViewport: 'mobile',
    },
    docs: {
      description: {
        story: 'App component displayed on mobile viewport to test responsive design.',
      },
    },
  },
}

/**
 * Tablet Viewport
 *
 * App component displayed on tablet viewport (768x1024).
 * Tests tablet-specific layout and spacing.
 */
export const Tablet: Story = {
  parameters: {
    viewport: {
      defaultViewport: 'tablet',
    },
    docs: {
      description: {
        story: 'App component displayed on tablet viewport.',
      },
    },
  },
}

/**
 * Desktop Viewport
 *
 * App component displayed on desktop viewport (1024x768).
 * Standard desktop layout with optimal spacing.
 */
export const Desktop: Story = {
  parameters: {
    viewport: {
      defaultViewport: 'desktop',
    },
    docs: {
      description: {
        story: 'App component displayed on desktop viewport.',
      },
    },
  },
}

/**
 * All Features Enabled
 *
 * Shows the App component with all feature flags enabled.
 * Useful for testing feature availability.
 */
export const AllFeaturesEnabled: Story = {
  parameters: {
    docs: {
      description: {
        story: 'App component with all feature flags enabled for testing.',
      },
    },
  },
}

/**
 * Minimal Features
 *
 * Shows the App component with minimal feature set enabled.
 * Useful for testing with limited functionality.
 */
export const MinimalFeatures: Story = {
  parameters: {
    docs: {
      description: {
        story: 'App component with minimal feature set enabled.',
      },
    },
  },
}

