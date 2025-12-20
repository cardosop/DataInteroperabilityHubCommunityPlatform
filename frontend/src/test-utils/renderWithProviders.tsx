/**
 * renderWithProviders Utility
 *
 * Enhanced render utility that wraps components with all necessary providers:
 * - React Query (QueryClientProvider)
 * - Material-UI Theme (ThemeProvider)
 * - i18next (I18nextProvider)
 * - React Router (MemoryRouter)
 * - Toast Provider (ToastProvider)
 *
 * This ensures components are tested in an environment that matches production.
 */

import React, { ReactElement } from 'react'
import { render, RenderOptions } from '@testing-library/react'
import { ThemeProvider, CssBaseline } from '@mui/material'
import { I18nextProvider } from 'react-i18next'
import { MemoryRouter, BrowserRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { createAppTheme } from '@/lib/config/mui'
import i18n from '@/lib/config/i18n'
import { ToastProvider } from '@/components/feedback/Toast'
import { createTestQueryClient } from './createTestQueryClient'

/**
 * Options for renderWithProviders
 */
export interface RenderWithProvidersOptions extends Omit<RenderOptions, 'wrapper'> {
  /**
   * Custom QueryClient instance (optional, uses test client by default)
   */
  queryClient?: QueryClient
  /**
   * Initial route path for MemoryRouter
   * @default '/'
   */
  initialEntries?: string[]
  /**
   * Use BrowserRouter instead of MemoryRouter
   * @default false
   */
  useBrowserRouter?: boolean
  /**
   * Theme mode
   * @default 'light'
   */
  themeMode?: 'light' | 'dark'
  /**
   * Custom theme (optional, uses default if not provided)
   */
  theme?: ReturnType<typeof createAppTheme>
  /**
   * Custom i18n instance (optional, uses default if not provided)
   */
  i18nInstance?: typeof i18n
  /**
   * Toast provider options
   */
  toastOptions?: {
    position?: 'top-left' | 'top-right' | 'bottom-left' | 'bottom-right'
    maxToasts?: number
  }
}

/**
 * Render component with all necessary providers
 *
 * @param ui - Component to render
 * @param options - Render options
 * @returns Render result with all providers
 *
 * @example
 * ```tsx
 * import { renderWithProviders } from '@/test-utils'
 *
 * test('renders component', () => {
 *   const { getByText } = renderWithProviders(<MyComponent />)
 *   expect(getByText('Hello')).toBeInTheDocument()
 * })
 * ```
 *
 * @example
 * ```tsx
 * // With custom route
 * renderWithProviders(<MyComponent />, {
 *   initialEntries: ['/custom-path'],
 * })
 * ```
 *
 * @example
 * ```tsx
 * // With custom QueryClient
 * const queryClient = createTestQueryClient()
 * renderWithProviders(<MyComponent />, {
 *   queryClient,
 * })
 * ```
 */
export function renderWithProviders(
  ui: ReactElement,
  options: RenderWithProvidersOptions = {}
): ReturnType<typeof render> {
  const {
    queryClient = createTestQueryClient(),
    initialEntries = ['/'],
    useBrowserRouter = false,
    themeMode = 'light',
    theme,
    i18nInstance = i18n,
    toastOptions,
    ...renderOptions
  } = options

  const appTheme = theme || createAppTheme(themeMode)

  const Router = useBrowserRouter ? BrowserRouter : MemoryRouter

  function AllProviders({ children }: { children: React.ReactNode }) {
    return (
      <QueryClientProvider client={queryClient}>
        <I18nextProvider i18n={i18nInstance}>
          <ThemeProvider theme={appTheme}>
            <CssBaseline />
            <ToastProvider
              position={toastOptions?.position}
              maxToasts={toastOptions?.maxToasts}
            >
              <Router initialEntries={initialEntries}>
                {children}
              </Router>
            </ToastProvider>
          </ThemeProvider>
        </I18nextProvider>
      </QueryClientProvider>
    )
  }

  return render(ui, { wrapper: AllProviders, ...renderOptions })
}

/**
 * Re-export render from @testing-library/react for convenience
 */
export { render } from '@testing-library/react'

