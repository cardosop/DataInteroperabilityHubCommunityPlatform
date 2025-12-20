# Analytics Integration

This directory contains analytics and tracking code.

## Purpose

Centralized analytics integration for:
- Google Analytics
- Sentry error tracking
- Custom event tracking
- User behavior analytics
- Performance monitoring

## Structure

```
analytics/
├── google-analytics.ts  # Google Analytics integration
├── sentry.ts            # Sentry error tracking
├── events.ts            # Event tracking utilities
├── types.ts             # Analytics types
└── index.ts             # Public exports
```

## Guidelines

- **Privacy**: Respect user privacy and consent
- **Error handling**: Analytics failures should not break the app
- **Type safety**: All events should be typed
- **Consistency**: Use consistent event naming conventions
- **Performance**: Analytics should not impact app performance

## Usage

```tsx
import { trackEvent, trackError } from '@/lib/analytics'

// Track custom event
trackEvent('button_click', { buttonId: 'submit' })

// Track error
trackError(error, { context: 'checkout' })
```

