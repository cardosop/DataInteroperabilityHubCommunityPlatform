# Internationalization (i18n) Guide

**Last Updated**: 2025-12-13  
**Version**: 1.0.0

---

## Table of Contents

1. [Overview](#overview)
2. [i18n Setup](#i18n-setup)
3. [Translation Management](#translation-management)
4. [Locale-Specific Formatting](#locale-specific-formatting)
5. [RTL Language Support](#rtl-language-support)
6. [Language Selection UI](#language-selection-ui)
7. [Best Practices](#best-practices)

---

## Overview

This document describes the internationalization (i18n) strategy for the frontend application. The application supports multiple languages and locales, with proper formatting for dates, numbers, and currencies.

**Supported Languages** (Initial):
- English (en) - Default
- Spanish (es)
- French (fr)
- German (de)
- Japanese (ja)
- Chinese (zh)

**Key Features**:
- Multi-language support
- Locale-specific date/time formatting
- Locale-specific number formatting
- RTL (Right-to-Left) language support
- Dynamic language switching
- Translation key management

---

## i18n Setup

### React i18next Configuration

**Installation**:
```bash
npm install react-i18next i18next i18next-browser-languagedetector
```

**Configuration**: `src/lib/i18n/config.ts`

```typescript
import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';
import LanguageDetector from 'i18next-browser-languagedetector';
import enTranslations from './locales/en.json';
import esTranslations from './locales/es.json';
import frTranslations from './locales/fr.json';
import deTranslations from './locales/de.json';
import jaTranslations from './locales/ja.json';
import zhTranslations from './locales/zh.json';

i18n
  .use(LanguageDetector)
  .use(initReactI18next)
  .init({
    resources: {
      en: { translation: enTranslations },
      es: { translation: esTranslations },
      fr: { translation: frTranslations },
      de: { translation: deTranslations },
      ja: { translation: jaTranslations },
      zh: { translation: zhTranslations },
    },
    fallbackLng: 'en',
    defaultNS: 'translation',
    interpolation: {
      escapeValue: false,
    },
    detection: {
      order: ['localStorage', 'navigator'],
      caches: ['localStorage'],
    },
  });

export default i18n;
```

### Translation File Structure

**File**: `src/lib/i18n/locales/en.json`

```json
{
  "common": {
    "save": "Save",
    "cancel": "Cancel",
    "delete": "Delete",
    "edit": "Edit",
    "create": "Create",
    "search": "Search",
    "loading": "Loading...",
    "error": "Error",
    "success": "Success"
  },
  "assets": {
    "title": "Assets",
    "create": "Create Asset",
    "name": "Asset Name",
    "description": "Description",
    "status": "Status",
    "created": "Created",
    "updated": "Updated"
  },
  "contracts": {
    "title": "Contracts",
    "create": "Create Contract",
    "version": "Version",
    "status": "Status",
    "valid": "Valid",
    "invalid": "Invalid"
  },
  "errors": {
    "notFound": "Resource not found",
    "unauthorized": "You are not authorized to perform this action",
    "serverError": "A server error occurred. Please try again."
  }
}
```

---

## Translation Management

### Using Translations in Components

**Hook**: `useTranslation`

```typescript
import { useTranslation } from 'react-i18next';

export function AssetCard({ asset }: AssetCardProps) {
  const { t } = useTranslation();

  return (
    <Card>
      <CardContent>
        <Typography variant="h6">{asset.name}</Typography>
        <Typography variant="body2">
          {t('assets.status')}: {asset.status}
        </Typography>
        <Button>{t('common.edit')}</Button>
      </CardContent>
    </Card>
  );
}
```

### Translation with Variables

**Translation File**:
```json
{
  "assets": {
    "createdAt": "Created on {{date}}",
    "itemCount": "{{count}} asset",
    "itemCount_plural": "{{count}} assets"
  }
}
```

**Usage**:
```typescript
const { t } = useTranslation();

// Simple variable
t('assets.createdAt', { date: formatDate(asset.created_at) });

// Pluralization
t('assets.itemCount', { count: assets.length });
```

### Namespace Support

**Configuration**:
```typescript
// Load namespace
const { t } = useTranslation('errors');

// Use namespace
t('serverError'); // Looks in errors namespace
```

---

## Locale-Specific Formatting

### Date Formatting

**Utility**: `src/lib/i18n/date.ts`

```typescript
import { format, formatDistance, formatRelative } from 'date-fns';
import { enUS, es, fr, de, ja, zhCN } from 'date-fns/locale';

const localeMap = {
  en: enUS,
  es: es,
  fr: fr,
  de: de,
  ja: ja,
  zh: zhCN,
};

export function formatDate(
  date: Date | string,
  formatStr: string = 'PP',
  locale?: string
): string {
  const currentLocale = locale || i18n.language;
  const dateFnsLocale = localeMap[currentLocale] || enUS;
  return format(new Date(date), formatStr, { locale: dateFnsLocale });
}

export function formatDateDistance(
  date: Date | string,
  locale?: string
): string {
  const currentLocale = locale || i18n.language;
  const dateFnsLocale = localeMap[currentLocale] || enUS;
  return formatDistance(new Date(date), new Date(), {
    locale: dateFnsLocale,
    addSuffix: true,
  });
}
```

**Usage**:
```typescript
import { formatDate, formatDateDistance } from '@/lib/i18n/date';

// Format date
formatDate(asset.created_at, 'PP'); // "Jan 15, 2025"
formatDate(asset.created_at, 'PP', 'es'); // "15 ene 2025"

// Relative time
formatDateDistance(asset.created_at); // "2 hours ago"
```

### Number Formatting

**Utility**: `src/lib/i18n/number.ts`

```typescript
export function formatNumber(
  value: number,
  options?: Intl.NumberFormatOptions,
  locale?: string
): string {
  const currentLocale = locale || i18n.language;
  return new Intl.NumberFormat(currentLocale, options).format(value);
}

export function formatCurrency(
  value: number,
  currency: string = 'USD',
  locale?: string
): string {
  const currentLocale = locale || i18n.language;
  return new Intl.NumberFormat(currentLocale, {
    style: 'currency',
    currency,
  }).format(value);
}

export function formatPercentage(
  value: number,
  locale?: string
): string {
  const currentLocale = locale || i18n.language;
  return new Intl.NumberFormat(currentLocale, {
    style: 'percent',
    minimumFractionDigits: 1,
    maximumFractionDigits: 1,
  }).format(value / 100);
}
```

**Usage**:
```typescript
import { formatNumber, formatCurrency, formatPercentage } from '@/lib/i18n/number';

// Format number
formatNumber(1234.56); // "1,234.56" (en) or "1.234,56" (de)

// Format currency
formatCurrency(1234.56, 'USD'); // "$1,234.56" (en) or "1.234,56 $" (de)

// Format percentage
formatPercentage(85.5); // "85.5%" (en) or "85,5 %" (de)
```

---

## RTL Language Support

### RTL Detection Hook

**Hook**: `useRTL`

```typescript
import { useTranslation } from 'react-i18next';

const RTL_LANGUAGES = ['ar', 'he', 'fa', 'ur'];

export function useRTL() {
  const { i18n } = useTranslation();
  const isRTL = RTL_LANGUAGES.includes(i18n.language);

  useEffect(() => {
    document.documentElement.dir = isRTL ? 'rtl' : 'ltr';
    document.documentElement.lang = i18n.language;
  }, [isRTL, i18n.language]);

  return { isRTL };
}
```

### MUI RTL Support

**Configuration**: `src/theme/index.ts`

```typescript
import { createTheme, ThemeProvider } from '@mui/material/styles';
import { prefixer } from 'stylis';
import rtlPlugin from 'stylis-plugin-rtl';
import { CacheProvider } from '@emotion/react';
import createCache from '@emotion/cache';

const rtlCache = createCache({
  key: 'muirtl',
  stylisPlugins: [prefixer, rtlPlugin],
});

export function RTLProvider({ children }: { children: React.ReactNode }) {
  const { isRTL } = useRTL();

  return (
    <CacheProvider value={isRTL ? rtlCache : undefined}>
      <ThemeProvider theme={createTheme({ direction: isRTL ? 'rtl' : 'ltr' })}>
        {children}
      </ThemeProvider>
    </CacheProvider>
  );
}
```

---

## Language Selection UI

### Language Selector Component

**Component**: `LanguageSelector`

```typescript
import { useTranslation } from 'react-i18next';
import {
  Menu,
  MenuItem,
  IconButton,
  ListItemIcon,
  ListItemText,
} from '@mui/material';
import LanguageIcon from '@mui/icons-material/Language';

const LANGUAGES = [
  { code: 'en', name: 'English', flag: '🇺🇸' },
  { code: 'es', name: 'Español', flag: '🇪🇸' },
  { code: 'fr', name: 'Français', flag: '🇫🇷' },
  { code: 'de', name: 'Deutsch', flag: '🇩🇪' },
  { code: 'ja', name: '日本語', flag: '🇯🇵' },
  { code: 'zh', name: '中文', flag: '🇨🇳' },
];

export function LanguageSelector() {
  const { i18n } = useTranslation();
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);

  const handleClick = (event: React.MouseEvent<HTMLElement>) => {
    setAnchorEl(event.currentTarget);
  };

  const handleClose = () => {
    setAnchorEl(null);
  };

  const handleLanguageChange = (languageCode: string) => {
    i18n.changeLanguage(languageCode);
    handleClose();
  };

  const currentLanguage = LANGUAGES.find((lang) => lang.code === i18n.language);

  return (
    <>
      <IconButton onClick={handleClick} aria-label="Select language">
        <LanguageIcon />
      </IconButton>
      <Menu
        anchorEl={anchorEl}
        open={Boolean(anchorEl)}
        onClose={handleClose}
      >
        {LANGUAGES.map((language) => (
          <MenuItem
            key={language.code}
            selected={language.code === i18n.language}
            onClick={() => handleLanguageChange(language.code)}
          >
            <ListItemIcon>{language.flag}</ListItemIcon>
            <ListItemText>{language.name}</ListItemText>
          </MenuItem>
        ))}
      </Menu>
    </>
  );
}
```

### Language Selection in Settings

**Component**: `LanguageSettings`

```typescript
export function LanguageSettings() {
  const { i18n, t } = useTranslation();

  return (
    <Card>
      <CardHeader title={t('settings.language')} />
      <CardContent>
        <FormControl fullWidth>
          <InputLabel>{t('settings.selectLanguage')}</InputLabel>
          <Select
            value={i18n.language}
            onChange={(e) => i18n.changeLanguage(e.target.value)}
          >
            {LANGUAGES.map((language) => (
              <MenuItem key={language.code} value={language.code}>
                {language.flag} {language.name}
              </MenuItem>
            ))}
          </Select>
        </FormControl>
      </CardContent>
    </Card>
  );
}
```

---

## Translation Key Organization

### Key Naming Convention

**Structure**:
```
{namespace}.{section}.{item}
```

**Examples**:
- `common.save` - Common save button
- `assets.title` - Assets page title
- `assets.form.name` - Asset form name field
- `errors.notFound` - Error message for not found
- `validation.required` - Validation message for required field

### Translation File Organization

**Structure**:
```
src/lib/i18n/locales/
  en/
    common.json
    assets.json
    contracts.json
    errors.json
    validation.json
  es/
    common.json
    assets.json
    ...
```

**Loading Multiple Files**:
```typescript
import enCommon from './locales/en/common.json';
import enAssets from './locales/en/assets.json';
import enContracts from './locales/en/contracts.json';

i18n.addResourceBundle('en', 'common', enCommon);
i18n.addResourceBundle('en', 'assets', enAssets);
i18n.addResourceBundle('en', 'contracts', enContracts);
```

---

## Best Practices

1. **Use Translation Keys**: Never hardcode strings
2. **Organize Keys**: Use namespaces and logical grouping
3. **Provide Context**: Include context in translation keys when needed
4. **Test Translations**: Test all languages during development
5. **Handle Missing Translations**: Provide fallback to English
6. **Format Locale-Specific**: Use locale-aware formatting for dates/numbers
7. **Support RTL**: Test and support RTL languages
8. **Cache Translations**: Load translations efficiently
9. **Update Translations**: Keep translations in sync with code changes
10. **Accessibility**: Ensure translations are accessible

---

## Translation Workflow

1. **Extract Keys**: Use tools to extract translation keys from code
2. **Translate**: Send keys to translation service/team
3. **Review**: Review translations for accuracy
4. **Test**: Test translations in application
5. **Deploy**: Deploy updated translations

---

**Last Updated**: 2025-12-13  
**Version**: 1.0.0

