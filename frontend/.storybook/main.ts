import type { StorybookConfig } from '@storybook/react-vite'
import { mergeConfig } from 'vite'
import path from 'path'
import { fileURLToPath } from 'url'

// Get __dirname equivalent for ES modules
const __filename = fileURLToPath(import.meta.url)
const __dirname = path.dirname(__filename)

const config: StorybookConfig = {
  stories: [
    '../src/**/*.mdx',
    '../src/**/*.stories.@(js|jsx|mjs|ts|tsx)',
  ],
  addons: [
    '@chromatic-com/storybook',
    '@storybook/addon-vitest',
    '@storybook/addon-a11y',
    '@storybook/addon-docs',
    '@storybook/addon-onboarding',
  ],
  framework: {
    name: '@storybook/react-vite',
    options: {},
  },
  docs: {
    autodocs: 'tag',
    defaultName: 'Documentation',
  },
  typescript: {
    check: false,
    reactDocgen: 'react-docgen-typescript',
    reactDocgenTypescriptOptions: {
      shouldExtractLiteralValuesFromEnum: true,
      propFilter: (prop) => (prop.parent ? !/node_modules/.test(prop.parent.fileName) : true),
    },
  },
  async viteFinal(config) {
    return mergeConfig(config, {
      resolve: {
        alias: {
          '@': path.resolve(__dirname, '../src'),
        },
      },
      define: {
        // Mock environment variables for Storybook
        'import.meta.env.VITE_API_BASE_URL': JSON.stringify('http://localhost:8000'),
        'import.meta.env.VITE_WS_URL': JSON.stringify('ws://localhost:8000'),
        'import.meta.env.VITE_GRAPHQL_URL': JSON.stringify('http://localhost:8000/graphql'),
        'import.meta.env.VITE_ENV': JSON.stringify('development'),
        'import.meta.env.VITE_DEBUG': JSON.stringify('true'),
        'import.meta.env.DEV': JSON.stringify('true'),
      },
    })
  },
}

export default config
