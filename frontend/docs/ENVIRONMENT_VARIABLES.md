# Environment Variables Documentation

**Last Updated**: 2025-01-15
**Version**: 1.0.0

## Overview

This document describes all environment variables used by the frontend application. All variables prefixed with `VITE_` are exposed to client-side code and should never contain sensitive secrets.

## Quick Start

1. Copy the example file:
   ```bash
   cp .env.example .env
   ```

2. Edit `.env` with your configuration values

3. For environment-specific configs, see:
   - `.env.development` - Development environment
   - `.env.staging` - Staging environment
   - `.env.production` - Production environment

## Variable Categories

### API Configuration (Required)

#### `VITE_API_BASE_URL`
- **Type**: `string`
- **Required**: Yes
- **Default**: `http://localhost:8000`
- **Description**: Backend API base URL (without trailing slash)
- **Example**: `https://api.datahub.example.com`
- **Validation**: Must be a valid HTTP/HTTPS URL

#### `VITE_WS_URL`
- **Type**: `string`
- **Required**: Yes
- **Default**: `ws://localhost:8000`
- **Description**: WebSocket URL for real-time features
- **Example**: `wss://api.datahub.example.com`
- **Validation**: Must be a valid WS/WSS URL
- **Note**: Protocol should match API protocol (https → wss, http → ws)

#### `VITE_GRAPHQL_URL`
- **Type**: `string`
- **Required**: No (defaults to `${VITE_API_BASE_URL}/graphql`)
- **Default**: `${VITE_API_BASE_URL}/graphql`
- **Description**: GraphQL endpoint URL
- **Example**: `https://api.datahub.example.com/graphql`
- **Validation**: Must be a valid HTTP/HTTPS URL

#### `VITE_API_VERSION`
- **Type**: `string`
- **Required**: No
- **Default**: `v1`
- **Description**: API version used in API requests
- **Example**: `v1`, `v2`

#### `VITE_OPENAPI_SCHEMA_URL`
- **Type**: `string`
- **Required**: No (defaults to `${VITE_API_BASE_URL}/api/v1/openapi.json`)
- **Default**: `${VITE_API_BASE_URL}/api/v1/openapi.json`
- **Description**: OpenAPI schema URL for API documentation and type generation
- **Example**: `https://api.datahub.example.com/api/v1/openapi.json`
- **Validation**: Must be a valid HTTP/HTTPS URL

### Environment Settings (Required)

#### `VITE_ENV`
- **Type**: `'development' | 'staging' | 'production'`
- **Required**: Yes
- **Default**: `development`
- **Description**: Environment name
- **Validation**: Must be one of: `development`, `staging`, `production`

#### `VITE_DEBUG`
- **Type**: `boolean` (string: `'true'` or `'false'`)
- **Required**: No
- **Default**: `true` in development, `false` in staging/production
- **Description**: Enable debug mode (shows additional logging and error details)
- **Warning**: Should be `false` in production

### Analytics Configuration (Optional)

#### `VITE_GA_MEASUREMENT_ID`
- **Type**: `string | undefined`
- **Required**: No
- **Default**: `undefined`
- **Description**: Google Analytics 4 Measurement ID
- **Format**: `G-XXXXXXXXXX`
- **Example**: `G-ABC123XYZ`
- **Note**: Leave empty to disable Google Analytics

#### `VITE_SENTRY_DSN`
- **Type**: `string | undefined`
- **Required**: No
- **Default**: `undefined`
- **Description**: Sentry DSN for error tracking
- **Format**: `https://xxxxx@xxxxx.ingest.sentry.io/xxxxx`
- **Example**: `https://abc123@o123456.ingest.sentry.io/123456`
- **Note**: Leave empty to disable Sentry

#### `VITE_ENABLE_ANALYTICS`
- **Type**: `boolean` (string: `'true'` or `'false'`)
- **Required**: No
- **Default**: `false` in development, `true` in staging/production
- **Description**: Enable analytics (Sentry and Google Analytics)
- **Note**: Analytics will only work if corresponding IDs are configured

### Feature Flags (Optional)

All feature flags default to `true` except `VITE_ENABLE_AI_ML` and `VITE_ENABLE_SOCIAL` which default to `false` (opt-in features).

#### `VITE_ENABLE_MARKETPLACE`
- **Type**: `boolean` (string: `'true'` or `'false'`)
- **Default**: `true`
- **Description**: Enable marketplace feature

#### `VITE_ENABLE_COMPLIANCE`
- **Type**: `boolean` (string: `'true'` or `'false'`)
- **Default**: `true`
- **Description**: Enable compliance feature

#### `VITE_ENABLE_DATA_QUALITY`
- **Type**: `boolean` (string: `'true'` or `'false'`)
- **Default**: `true`
- **Description**: Enable data quality feature

#### `VITE_ENABLE_SCHEDULED_INGESTION`
- **Type**: `boolean` (string: `'true'` or `'false'`)
- **Default**: `true`
- **Description**: Enable scheduled ingestion feature

#### `VITE_ENABLE_SEARCH`
- **Type**: `boolean` (string: `'true'` or `'false'`)
- **Default**: `true`
- **Description**: Enable search feature

#### `VITE_ENABLE_GOVERNANCE`
- **Type**: `boolean` (string: `'true'` or `'false'`)
- **Default**: `true`
- **Description**: Enable governance feature

#### `VITE_ENABLE_AI_ML`
- **Type**: `boolean` (string: `'true'` or `'false'`)
- **Default**: `false`
- **Description**: Enable AI/ML features (natural language search, schema matching)

#### `VITE_ENABLE_SOCIAL`
- **Type**: `boolean` (string: `'true'` or `'false'`)
- **Default**: `false`
- **Description**: Enable social features (ratings, reviews, comments, communities)

#### `VITE_ENABLE_DEVELOPER`
- **Type**: `boolean` (string: `'true'` or `'false'`)
- **Default**: `true`
- **Description**: Enable developer features (plugins, SDK documentation)

### Performance & Optimization (Optional)

#### `VITE_ENABLE_REACT_QUERY_DEVTOOLS`
- **Type**: `boolean` (string: `'true'` or `'false'`)
- **Default**: `true` in development, `false` in staging/production
- **Description**: Enable React Query DevTools in development

#### `VITE_API_TIMEOUT`
- **Type**: `number` (string)
- **Default**: `30000`
- **Description**: API request timeout in milliseconds
- **Example**: `30000` (30 seconds)
- **Validation**: Must be a positive integer

#### `VITE_WS_RECONNECT_DELAY`
- **Type**: `number` (string)
- **Default**: `3000`
- **Description**: WebSocket reconnection delay in milliseconds
- **Example**: `3000` (3 seconds)
- **Validation**: Must be a positive integer

#### `VITE_WS_MAX_RECONNECT_ATTEMPTS`
- **Type**: `number` (string)
- **Default**: `5`
- **Description**: Maximum WebSocket reconnection attempts
- **Example**: `5`
- **Validation**: Must be a positive integer

### Internationalization (Optional)

#### `VITE_DEFAULT_LANGUAGE`
- **Type**: `string`
- **Default**: `en`
- **Description**: Default language code (ISO 639-1)
- **Supported**: `en`, `es`, `fr`, `de`, `it`, `pt`, `ru`, `zh`, `ja`, `ko`
- **Example**: `en`

#### `VITE_SUPPORTED_LANGUAGES`
- **Type**: `string` (comma-separated list)
- **Default**: `en,es,fr`
- **Description**: Supported language codes (comma-separated)
- **Example**: `en,es,fr,de`
- **Validation**: Must include `VITE_DEFAULT_LANGUAGE`

### UI Configuration (Optional)

#### `VITE_THEME_MODE`
- **Type**: `'light' | 'dark'`
- **Default**: `light`
- **Description**: Default theme mode
- **Validation**: Must be `light` or `dark`

#### `VITE_THEME_PERSIST`
- **Type**: `boolean` (string: `'true'` or `'false'`)
- **Default**: `true`
- **Description**: Enable theme persistence in localStorage

#### `VITE_PAGE_SIZE`
- **Type**: `number` (string)
- **Default**: `20`
- **Description**: Default items per page for pagination
- **Validation**: Must be a positive integer, must be ≤ `VITE_MAX_PAGE_SIZE`

#### `VITE_MAX_PAGE_SIZE`
- **Type**: `number` (string)
- **Default**: `100`
- **Description**: Maximum items per page
- **Validation**: Must be a positive integer, must be ≥ `VITE_PAGE_SIZE`

### Development Only (Optional)

These variables are only used in development and should be `false` or disabled in production.

#### `VITE_ENABLE_PROFILER`
- **Type**: `boolean` (string: `'true'` or `'false'`)
- **Default**: `true` in development, `false` in staging/production
- **Description**: Enable React DevTools Profiler

#### `VITE_ENABLE_API_LOGGING`
- **Type**: `boolean` (string: `'true'` or `'false'`)
- **Default**: `true` in development, `false` in staging/production
- **Description**: Enable API request/response logging

#### `VITE_MOCK_API`
- **Type**: `boolean` (string: `'true'` or `'false'`)
- **Default**: `false`
- **Description**: Mock API responses (for development/testing)
- **Warning**: Should always be `false` in production

## Environment-Specific Files

Vite automatically loads environment-specific files based on the mode:

- **Development**: `.env.development` (loaded when running `npm run dev`)
- **Staging**: `.env.staging` (loaded when building with `--mode staging`)
- **Production**: `.env.production` (loaded when building with `--mode production`)

Variables in `.env` are always loaded, and environment-specific files override them.

## Validation

All environment variables are validated at application startup:

1. **Required variables** must be present
2. **URLs** must be valid HTTP/HTTPS/WS/WSS URLs
3. **Numeric values** must be positive integers
4. **Enum values** must be one of the allowed values
5. **Boolean values** must be `'true'` or `'false'`
6. **Constraints** are validated (e.g., page size ≤ max page size)

If validation fails, the application will throw an error with a descriptive message.

## Type Safety

All environment variables have TypeScript type definitions in `src/vite-env.d.ts`. This provides:

- IntelliSense autocomplete
- Type checking at compile time
- Documentation in IDE tooltips

## Usage in Code

Access environment variables through the validated configuration object:

```typescript
import { config } from '@/lib/config';

// API configuration
const apiUrl = config.api.baseUrl;
const wsUrl = config.api.wsUrl;

// Feature flags
if (config.features.aiMl) {
  // AI/ML features enabled
}

// Environment checks
import { isDevelopment, isProduction } from '@/lib/config';
if (isDevelopment) {
  // Development-only code
}
```

## Security Notes

⚠️ **Important**: All `VITE_` prefixed variables are exposed to client-side code. Never put:

- API keys
- Secrets
- Passwords
- Private tokens
- Database credentials

Use server-side environment variables for sensitive data.

## Troubleshooting

### Variable not working?

1. **Check variable name**: Must start with `VITE_`
2. **Restart dev server**: Vite only reads env vars at startup
3. **Check file location**: Must be in project root
4. **Check syntax**: No spaces around `=`, no quotes needed for strings

### Validation errors?

Check the error message for:
- Missing required variables
- Invalid URL formats
- Invalid enum values
- Constraint violations

### Type errors?

Ensure `src/vite-env.d.ts` includes the variable type definition.

## Examples

### Development Setup

```bash
# .env.development
VITE_API_BASE_URL=http://localhost:8000
VITE_WS_URL=ws://localhost:8000
VITE_ENV=development
VITE_DEBUG=true
VITE_ENABLE_AI_ML=true
VITE_ENABLE_SOCIAL=true
```

### Production Setup

```bash
# .env.production
VITE_API_BASE_URL=https://api.datahub.example.com
VITE_WS_URL=wss://api.datahub.example.com
VITE_ENV=production
VITE_DEBUG=false
VITE_GA_MEASUREMENT_ID=G-ABC123XYZ
VITE_SENTRY_DSN=https://abc123@o123456.ingest.sentry.io/123456
VITE_ENABLE_ANALYTICS=true
```

## Related Documentation

- [Configuration Module](../src/lib/config/env.ts) - Environment validation implementation
- [Type Definitions](../src/vite-env.d.ts) - TypeScript type definitions
- [Vite Environment Variables](https://vitejs.dev/guide/env-and-mode.html) - Vite documentation

