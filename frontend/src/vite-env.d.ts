/// <reference types="vite/client" />

/**
 * Environment Variable Type Definitions
 *
 * All environment variables prefixed with VITE_ are exposed to client-side code.
 * These types provide IntelliSense and type safety for environment variables.
 */
interface ImportMetaEnv {
  // API Configuration (Required)
  readonly VITE_API_BASE_URL: string
  readonly VITE_WS_URL: string
  readonly VITE_GRAPHQL_URL: string
  readonly VITE_API_VERSION: string
  readonly VITE_OPENAPI_SCHEMA_URL: string

  // Environment Settings (Required)
  readonly VITE_ENV: 'development' | 'staging' | 'production'
  readonly VITE_DEBUG: string

  // Analytics Configuration (Optional)
  readonly VITE_GA_MEASUREMENT_ID?: string
  readonly VITE_SENTRY_DSN?: string
  readonly VITE_ENABLE_ANALYTICS?: string

  // Feature Flags (Optional)
  readonly VITE_ENABLE_MARKETPLACE?: string
  readonly VITE_ENABLE_COMPLIANCE?: string
  readonly VITE_ENABLE_DATA_QUALITY?: string
  readonly VITE_ENABLE_SCHEDULED_INGESTION?: string
  readonly VITE_ENABLE_SEARCH?: string
  readonly VITE_ENABLE_GOVERNANCE?: string
  readonly VITE_ENABLE_AI_ML?: string
  readonly VITE_ENABLE_SOCIAL?: string
  readonly VITE_ENABLE_DEVELOPER?: string

  // Performance & Optimization (Optional)
  readonly VITE_ENABLE_REACT_QUERY_DEVTOOLS?: string
  readonly VITE_API_TIMEOUT?: string
  readonly VITE_WS_RECONNECT_DELAY?: string
  readonly VITE_WS_MAX_RECONNECT_ATTEMPTS?: string

  // Internationalization (Optional)
  readonly VITE_DEFAULT_LANGUAGE?: string
  readonly VITE_SUPPORTED_LANGUAGES?: string

  // UI Configuration (Optional)
  readonly VITE_THEME_MODE?: 'light' | 'dark'
  readonly VITE_THEME_PERSIST?: string
  readonly VITE_PAGE_SIZE?: string
  readonly VITE_MAX_PAGE_SIZE?: string

  // Development Only (Optional)
  readonly VITE_ENABLE_PROFILER?: string
  readonly VITE_ENABLE_API_LOGGING?: string
  readonly VITE_MOCK_API?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
