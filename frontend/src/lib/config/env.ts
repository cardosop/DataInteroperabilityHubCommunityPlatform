/**
 * Environment Variable Validation and Configuration
 *
 * Validates and exports environment variables with type safety.
 * Throws errors at startup if required variables are missing or invalid.
 *
 * This module provides:
 * - Runtime validation of environment variables
 * - Type-safe configuration object
 * - Helper functions for environment checks
 * - Comprehensive error messages for misconfiguration
 */

interface EnvConfig {
  api: {
    baseUrl: string
    wsUrl: string
    graphqlUrl: string
    version: string
    openapiSchemaUrl: string
    timeout: number
  }
  websocket: {
    reconnectDelay: number
    maxReconnectAttempts: number
  }
  analytics: {
    gaMeasurementId: string | undefined
    sentryDsn: string | undefined
    enabled: boolean
  }
  features: {
    marketplace: boolean
    compliance: boolean
    dataQuality: boolean
    scheduledIngestion: boolean
    search: boolean
    governance: boolean
    aiMl: boolean
    social: boolean
    developer: boolean
  }
  i18n: {
    defaultLanguage: string
    supportedLanguages: string[]
  }
  ui: {
    themeMode: 'light' | 'dark'
    themePersist: boolean
    pageSize: number
    maxPageSize: number
  }
  development: {
    enableProfiler: boolean
    enableApiLogging: boolean
    enableReactQueryDevtools: boolean
    mockApi: boolean
  }
  env: 'development' | 'staging' | 'production'
  debug: boolean
}

/**
 * Validates that a URL is valid
 */
function validateUrl(url: string, key: string): void {
  if (!url || typeof url !== 'string') {
    throw new Error(`Missing or invalid ${key}: ${url}`)
  }
  try {
    const urlObj = new URL(url)
    // Validate protocol
    if (!['http:', 'https:', 'ws:', 'wss:'].includes(urlObj.protocol)) {
      throw new Error(
        `Invalid protocol for ${key}: ${urlObj.protocol}. Must be http, https, ws, or wss`
      )
    }
  } catch (error) {
    if (error instanceof TypeError) {
      throw new Error(`Invalid URL format for ${key}: ${url}`)
    }
    throw error
  }
}

/**
 * Validates that a value is a positive integer
 */
function validatePositiveInteger(
  value: string | undefined,
  key: string,
  defaultValue: number
): number {
  if (!value) {
    return defaultValue
  }
  const num = parseInt(value, 10)
  if (isNaN(num) || num <= 0) {
    throw new Error(`Invalid ${key}: ${value}. Must be a positive integer`)
  }
  return num
}

/**
 * Validates that a value is a boolean string
 */
function parseBoolean(value: string | undefined, defaultValue: boolean): boolean {
  if (!value) {
    return defaultValue
  }
  return value.toLowerCase() === 'true'
}

/**
 * Validates that a value is one of the allowed values
 */
function validateEnum<T extends string>(
  value: string | undefined,
  key: string,
  allowedValues: readonly T[],
  defaultValue: T
): T {
  if (!value) {
    return defaultValue
  }
  if (!allowedValues.includes(value as T)) {
    throw new Error(`Invalid ${key}: ${value}. Must be one of: ${allowedValues.join(', ')}`)
  }
  return value as T
}

/**
 * Validates language code (ISO 639-1)
 */
function validateLanguageCode(
  value: string | undefined,
  key: string,
  defaultValue: string
): string {
  if (!value) {
    return defaultValue
  }
  const validCodes = ['en', 'es', 'fr', 'de', 'it', 'pt', 'ru', 'zh', 'ja', 'ko']
  if (!validCodes.includes(value.toLowerCase())) {
    console.warn(
      `Warning: ${key} has unsupported language code: ${value}. Using default: ${defaultValue}`
    )
    return defaultValue
  }
  return value.toLowerCase()
}

/**
 * Parses comma-separated list of language codes
 */
function parseLanguageList(
  value: string | undefined,
  key: string,
  defaultValue: string[]
): string[] {
  if (!value) {
    return defaultValue
  }
  return value
    .split(',')
    .map(lang => lang.trim().toLowerCase())
    .filter(Boolean)
}

/**
 * Validates environment variables and returns typed configuration
 *
 * This function performs comprehensive validation of all environment variables:
 * - Validates required variables are present
 * - Validates URL formats
 * - Validates numeric values
 * - Validates enum values
 * - Provides sensible defaults where appropriate
 * - Throws descriptive errors for invalid configurations
 */
function validateEnv(): EnvConfig {
  // API Configuration
  const apiBaseUrl = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'
  const wsUrl = import.meta.env.VITE_WS_URL || 'ws://localhost:8000'
  const graphqlUrl = import.meta.env.VITE_GRAPHQL_URL || `${apiBaseUrl}/graphql`
  const openapiSchemaUrl =
    import.meta.env.VITE_OPENAPI_SCHEMA_URL || `${apiBaseUrl}/api/v1/openapi.json`

  // Validate URLs
  validateUrl(apiBaseUrl, 'VITE_API_BASE_URL')
  validateUrl(wsUrl, 'VITE_WS_URL')
  validateUrl(graphqlUrl, 'VITE_GRAPHQL_URL')
  validateUrl(openapiSchemaUrl, 'VITE_OPENAPI_SCHEMA_URL')

  // Validate environment
  const env = validateEnum(
    import.meta.env.VITE_ENV,
    'VITE_ENV',
    ['development', 'staging', 'production'] as const,
    'development'
  )

  // Parse boolean values
  const debug = parseBoolean(import.meta.env.VITE_DEBUG, env === 'development')

  // API timeout
  const apiTimeout = validatePositiveInteger(
    import.meta.env.VITE_API_TIMEOUT,
    'VITE_API_TIMEOUT',
    30000
  )

  // WebSocket configuration
  const wsReconnectDelay = validatePositiveInteger(
    import.meta.env.VITE_WS_RECONNECT_DELAY,
    'VITE_WS_RECONNECT_DELAY',
    3000
  )
  const wsMaxReconnectAttempts = validatePositiveInteger(
    import.meta.env.VITE_WS_MAX_RECONNECT_ATTEMPTS,
    'VITE_WS_MAX_RECONNECT_ATTEMPTS',
    5
  )

  // Analytics
  const analyticsEnabled = parseBoolean(import.meta.env.VITE_ENABLE_ANALYTICS, env === 'production')

  // Feature flags
  const features = {
    marketplace: parseBoolean(import.meta.env.VITE_ENABLE_MARKETPLACE, true),
    compliance: parseBoolean(import.meta.env.VITE_ENABLE_COMPLIANCE, true),
    dataQuality: parseBoolean(import.meta.env.VITE_ENABLE_DATA_QUALITY, true),
    scheduledIngestion: parseBoolean(import.meta.env.VITE_ENABLE_SCHEDULED_INGESTION, true),
    search: parseBoolean(import.meta.env.VITE_ENABLE_SEARCH, true),
    governance: parseBoolean(import.meta.env.VITE_ENABLE_GOVERNANCE, true),
    aiMl: parseBoolean(import.meta.env.VITE_ENABLE_AI_ML, false),
    social: parseBoolean(import.meta.env.VITE_ENABLE_SOCIAL, false),
    developer: parseBoolean(import.meta.env.VITE_ENABLE_DEVELOPER, true),
  }

  // Internationalization
  const defaultLanguage = validateLanguageCode(
    import.meta.env.VITE_DEFAULT_LANGUAGE,
    'VITE_DEFAULT_LANGUAGE',
    'en'
  )
  const supportedLanguages = parseLanguageList(
    import.meta.env.VITE_SUPPORTED_LANGUAGES,
    'VITE_SUPPORTED_LANGUAGES',
    ['en', 'es', 'fr']
  )

  // UI Configuration
  const themeMode = validateEnum(
    import.meta.env.VITE_THEME_MODE,
    'VITE_THEME_MODE',
    ['light', 'dark'] as const,
    'light'
  )
  const themePersist = parseBoolean(import.meta.env.VITE_THEME_PERSIST, true)
  const pageSize = validatePositiveInteger(import.meta.env.VITE_PAGE_SIZE, 'VITE_PAGE_SIZE', 20)
  const maxPageSize = validatePositiveInteger(
    import.meta.env.VITE_MAX_PAGE_SIZE,
    'VITE_MAX_PAGE_SIZE',
    100
  )

  // Development settings
  const development = {
    enableProfiler: parseBoolean(import.meta.env.VITE_ENABLE_PROFILER, env === 'development'),
    enableApiLogging: parseBoolean(import.meta.env.VITE_ENABLE_API_LOGGING, env === 'development'),
    enableReactQueryDevtools: parseBoolean(
      import.meta.env.VITE_ENABLE_REACT_QUERY_DEVTOOLS,
      env === 'development'
    ),
    mockApi: parseBoolean(import.meta.env.VITE_MOCK_API, false),
  }

  return {
    api: {
      baseUrl: apiBaseUrl,
      wsUrl,
      graphqlUrl,
      version: import.meta.env.VITE_API_VERSION || 'v1',
      openapiSchemaUrl,
      timeout: apiTimeout,
    },
    websocket: {
      reconnectDelay: wsReconnectDelay,
      maxReconnectAttempts: wsMaxReconnectAttempts,
    },
    analytics: {
      gaMeasurementId: import.meta.env.VITE_GA_MEASUREMENT_ID,
      sentryDsn: import.meta.env.VITE_SENTRY_DSN,
      enabled: analyticsEnabled,
    },
    features,
    i18n: {
      defaultLanguage,
      supportedLanguages,
    },
    ui: {
      themeMode,
      themePersist,
      pageSize,
      maxPageSize,
    },
    development,
    env,
    debug,
  }
}

/**
 * Validated environment configuration
 * Throws error at import time if validation fails
 */
export const env = validateEnv()

/**
 * Type-safe environment configuration export
 *
 * This object provides type-safe access to all validated environment variables.
 * All values are validated and have proper types.
 */
export const config = {
  api: {
    baseUrl: env.api.baseUrl,
    wsUrl: env.api.wsUrl,
    graphqlUrl: env.api.graphqlUrl,
    version: env.api.version,
    openapiSchemaUrl: env.api.openapiSchemaUrl,
    timeout: env.api.timeout,
  },
  websocket: {
    reconnectDelay: env.websocket.reconnectDelay,
    maxReconnectAttempts: env.websocket.maxReconnectAttempts,
  },
  analytics: {
    gaMeasurementId: env.analytics.gaMeasurementId,
    sentryDsn: env.analytics.sentryDsn,
    enabled: env.analytics.enabled,
  },
  features: {
    marketplace: env.features.marketplace,
    compliance: env.features.compliance,
    dataQuality: env.features.dataQuality,
    scheduledIngestion: env.features.scheduledIngestion,
    search: env.features.search,
    governance: env.features.governance,
    aiMl: env.features.aiMl,
    social: env.features.social,
    developer: env.features.developer,
  },
  i18n: {
    defaultLanguage: env.i18n.defaultLanguage,
    supportedLanguages: env.i18n.supportedLanguages,
  },
  ui: {
    themeMode: env.ui.themeMode,
    themePersist: env.ui.themePersist,
    pageSize: env.ui.pageSize,
    maxPageSize: env.ui.maxPageSize,
  },
  development: {
    enableProfiler: env.development.enableProfiler,
    enableApiLogging: env.development.enableApiLogging,
    enableReactQueryDevtools: env.development.enableReactQueryDevtools,
    mockApi: env.development.mockApi,
  },
  env: env.env,
  debug: env.debug,
} as const

/**
 * Helper to check if running in development
 */
export const isDevelopment = config.env === 'development'

/**
 * Helper to check if running in production
 */
export const isProduction = config.env === 'production'

/**
 * Helper to check if running in staging
 */
export const isStaging = config.env === 'staging'

/**
 * Validates configuration at startup
 *
 * Performs additional runtime checks and logs warnings for potential issues.
 */
function validateConfiguration(): void {
  // Warn if analytics is enabled but DSNs are missing
  if (config.analytics.enabled) {
    if (!config.analytics.gaMeasurementId && !config.analytics.sentryDsn) {
      console.warn(
        'Warning: Analytics is enabled but neither Google Analytics ID nor Sentry DSN is configured.'
      )
    }
  }

  // Warn if production environment but debug is enabled
  if (isProduction && config.debug) {
    console.warn('Warning: Debug mode is enabled in production. This should be disabled.')
  }

  // Warn if WebSocket URL doesn't match API URL protocol
  const apiProtocol = new URL(config.api.baseUrl).protocol
  const wsProtocol = new URL(config.api.wsUrl).protocol
  const expectedWsProtocol = apiProtocol === 'https:' ? 'wss:' : 'ws:'
  if (wsProtocol !== expectedWsProtocol) {
    console.warn(
      `Warning: WebSocket protocol (${wsProtocol}) doesn't match API protocol (${apiProtocol}). Expected ${expectedWsProtocol}`
    )
  }

  // Validate page size constraints
  if (config.ui.pageSize > config.ui.maxPageSize) {
    throw new Error(
      `Invalid configuration: VITE_PAGE_SIZE (${config.ui.pageSize}) cannot be greater than VITE_MAX_PAGE_SIZE (${config.ui.maxPageSize})`
    )
  }

  // Validate supported languages includes default language
  if (!config.i18n.supportedLanguages.includes(config.i18n.defaultLanguage)) {
    throw new Error(
      `Invalid configuration: Default language (${config.i18n.defaultLanguage}) must be in supported languages (${config.i18n.supportedLanguages.join(', ')})`
    )
  }
}

// Run validation at module load time
try {
  validateConfiguration()
} catch (error) {
  // In development, show full error details
  if (isDevelopment) {
    console.error('Environment Configuration Error:', error)
  }
  throw error
}

/**
 * Log environment configuration (only in development with debug enabled)
 */
if (isDevelopment && config.debug) {
  // eslint-disable-next-line no-console
  console.log('Environment Configuration:', {
    env: config.env,
    api: {
      baseUrl: config.api.baseUrl,
      version: config.api.version,
      timeout: config.api.timeout,
    },
    websocket: {
      reconnectDelay: config.websocket.reconnectDelay,
      maxReconnectAttempts: config.websocket.maxReconnectAttempts,
    },
    features: config.features,
    analytics: {
      enabled: config.analytics.enabled,
      hasGaId: !!config.analytics.gaMeasurementId,
      hasSentryDsn: !!config.analytics.sentryDsn,
    },
    i18n: {
      defaultLanguage: config.i18n.defaultLanguage,
      supportedLanguages: config.i18n.supportedLanguages,
    },
    ui: {
      themeMode: config.ui.themeMode,
      pageSize: config.ui.pageSize,
    },
    development: config.development,
  })
}
