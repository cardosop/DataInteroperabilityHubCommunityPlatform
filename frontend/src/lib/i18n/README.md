# Internationalization (i18n)

This directory contains internationalization configuration and utilities.

## Purpose

Centralized i18n setup for:
- Language detection
- Translation management
- Locale switching
- Pluralization
- Date/number formatting

## Structure

```
i18n/
├── config.ts          # i18next configuration
├── locales/           # Translation files (if co-located)
├── utils.ts           # i18n utility functions
└── index.ts           # Public exports
```

## Guidelines

- **Centralized config**: All i18n configuration in one place
- **Type safety**: Use typed translation keys
- **Fallbacks**: Provide fallback translations
- **Performance**: Lazy load translations when possible
- **Formatting**: Use proper date/number formatting for locales

## Usage

```tsx
import { useTranslation } from 'react-i18next'
import { formatDate, formatNumber } from '@/lib/i18n'

function MyComponent() {
  const { t, i18n } = useTranslation()

  return (
    <div>
      <h1>{t('common.welcome')}</h1>
      <p>{formatDate(new Date(), i18n.language)}</p>
    </div>
  )
}
```

## Note

The main i18n configuration is currently in `@/lib/config/i18n.ts`. This directory can be used for additional i18n utilities and helpers.

