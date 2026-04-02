# Frontend Guide

> UI components, pages, and frontend-API integration
>
> **Source**: Merged during Phase 120F documentation consolidation.

---


---

# Accessibility Guidelines

**Last Updated**: 2026-03-22  
**Version**: 1.0.0

---

## Table of Contents

1. [Overview](#overview)
2. [WCAG Compliance](#wcag-compliance)
3. [Keyboard Navigation](#keyboard-navigation)
4. [Screen Readers](#screen-readers)
5. [Color and Contrast](#color-and-contrast)
6. [Focus Management](#focus-management)
7. [ARIA Labels and Roles](#aria-labels-and-roles)
8. [Forms and Inputs](#forms-and-inputs)
9. [Images and Media](#images-and-media)
10. [Testing Accessibility](#testing-accessibility)

---

## Overview

This document provides comprehensive accessibility guidelines for the Interoperable Data Hub platform. All interfaces must be accessible to users with disabilities, including those using assistive technologies.

**Accessibility Principles**:
- **Perceivable**: Information must be presentable to users in ways they can perceive
- **Operable**: Interface components must be operable by all users
- **Understandable**: Information and UI operation must be understandable
- **Robust**: Content must be robust enough for assistive technologies

**Compliance Target**: WCAG 2.1 Level AA (minimum)

---

## WCAG Compliance

### WCAG 2.1 Level AA Requirements

#### Perceivable

1. **Text Alternatives**
   - All images have alt text
   - Decorative images have empty alt text
   - Icons have text labels or ARIA labels

2. **Time-based Media**
   - Videos have captions
   - Audio has transcripts
   - Auto-playing media can be paused

3. **Adaptable**
   - Content can be presented without losing information
   - Information is not conveyed by color alone
   - Text can be resized up to 200% without loss of functionality

4. **Distinguishable**
   - Color contrast ratio of at least 4.5:1 for normal text
   - Color contrast ratio of at least 3:1 for large text
   - Text spacing can be adjusted

#### Operable

1. **Keyboard Accessible**
   - All functionality available via keyboard
   - No keyboard traps
   - Keyboard shortcuts don't conflict with browser shortcuts

2. **Enough Time**
   - Users can extend time limits
   - Moving, blinking, or auto-updating content can be paused

3. **Seizures and Physical Reactions**
   - No content flashes more than 3 times per second

4. **Navigable**
   - Clear page titles
   - Focus order is logical
   - Multiple ways to find content
   - Headings and labels are descriptive

#### Understandable

1. **Readable**
   - Language of page is identified
   - Unusual words are explained
   - Abbreviations are explained

2. **Predictable**
   - Navigation is consistent
   - Components with same functionality are identified consistently
   - Changes of context are initiated by user

3. **Input Assistance**
   - Errors are identified and described
   - Labels and instructions are provided
   - Error suggestions are provided

#### Robust

1. **Compatible**
   - Valid HTML
   - Proper use of ARIA attributes
   - Assistive technologies can parse content

---

## Keyboard Navigation

### Tab Order

- **Logical Order**: Tab order follows visual order
- **Skip Links**: Provide skip links for main content
- **Focus Indicators**: Visible focus indicators on all interactive elements

### Keyboard Shortcuts

**Global Shortcuts**:
- `Tab`: Move forward through interactive elements
- `Shift + Tab`: Move backward
- `Enter` / `Space`: Activate buttons and links
- `Esc`: Close modals, dismiss notifications
- `Arrow Keys`: Navigate within components (tabs, menus)

**Component-Specific**:
- **Dropdowns**: Arrow keys to navigate, Enter to select
- **Tabs**: Arrow keys to switch tabs
- **Tables**: Arrow keys to navigate cells
- **Modals**: Tab cycles within modal, Esc closes

### Implementation

```tsx
// Focusable element
<Button
  onKeyDown={(e) => {
    if (e.key === 'Enter' || e.key === ' ') {
      handleClick();
    }
  }}
>
  Click me
</Button>

// Skip link
<a href="#main-content" className="skip-link">
  Skip to main content
</a>
```

---

## Screen Readers

### Semantic HTML

Use semantic HTML elements:

```tsx
// Good: Semantic HTML
<header>
  <nav>
    <ul>
      <li><a href="/assets">Assets</a></li>
    </ul>
  </nav>
</header>

<main>
  <article>
    <h1>Asset Details</h1>
    <p>Content</p>
  </article>
</main>

// Bad: Div soup
<div>
  <div>
    <div>Assets</div>
  </div>
</div>
```

### ARIA Labels

Provide descriptive labels:

```tsx
// Icon button with label
<IconButton aria-label="Close dialog">
  <CloseIcon />
</IconButton>

// Form field with label
<TextField
  label="Asset Name"
  aria-describedby="asset-name-help"
/>
<FormHelperText id="asset-name-help">
  Enter a unique name for your asset
</FormHelperText>
```

### Live Regions

Announce dynamic content changes:

```tsx
// Status updates
<div role="status" aria-live="polite" aria-atomic="true">
  Asset created successfully
</div>

// Error messages
<div role="alert" aria-live="assertive">
  Error: Invalid input
</div>
```

---

## Color and Contrast

### Contrast Requirements

- **Normal Text** (≤18px): 4.5:1 contrast ratio
- **Large Text** (>18px or bold ≥14px): 3:1 contrast ratio
- **UI Components**: 3:1 contrast ratio
- **Graphical Objects**: 3:1 contrast ratio

### Color Usage

**Don't rely on color alone**:

```tsx
// Bad: Color only
<span style={{ color: 'red' }}>Error</span>

// Good: Color + icon + text
<span style={{ color: 'red' }}>
  <ErrorIcon aria-hidden="true" />
  Error: Invalid input
</span>
```

### Testing Contrast

Use tools to verify contrast:
- **WebAIM Contrast Checker**: https://webaim.org/resources/contrastchecker/
- **Chrome DevTools**: Accessibility panel
- **axe DevTools**: Automated testing

---

## Focus Management

### Visible Focus Indicators

All interactive elements must have visible focus indicators:

```css
/* Focus styles */
button:focus,
a:focus,
input:focus {
  outline: 2px solid #2196F3;
  outline-offset: 2px;
}

/* Custom focus for components */
.custom-button:focus-visible {
  box-shadow: 0 0 0 3px rgba(33, 150, 243, 0.3);
}
```

### Focus Trapping

Trap focus within modals:

```tsx
// Modal with focus trap
<Modal
  open={open}
  onClose={handleClose}
  aria-labelledby="modal-title"
>
  <FocusTrap>
    <DialogTitle id="modal-title">Confirm Delete</DialogTitle>
    <DialogContent>
      {/* Content */}
    </DialogContent>
    <DialogActions>
      <Button onClick={handleClose}>Cancel</Button>
      <Button onClick={handleConfirm}>Delete</Button>
    </DialogActions>
  </FocusTrap>
</Modal>
```

### Focus Restoration

Restore focus after closing modals:

```tsx
const handleClose = () => {
  // Save reference to element that opened modal
  const previousActiveElement = document.activeElement;
  
  setOpen(false);
  
  // Restore focus
  setTimeout(() => {
    previousActiveElement?.focus();
  }, 0);
};
```

---

## ARIA Labels and Roles

### Common ARIA Patterns

**Buttons**:
```tsx
<button aria-label="Close dialog">
  <CloseIcon aria-hidden="true" />
</button>
```

**Navigation**:
```tsx
<nav aria-label="Main navigation">
  <ul role="menubar">
    <li role="none">
      <a role="menuitem" href="/assets">Assets</a>
    </li>
  </ul>
</nav>
```

**Forms**:
```tsx
<form aria-label="Create asset">
  <label htmlFor="asset-name">Asset Name</label>
  <input
    id="asset-name"
    aria-required="true"
    aria-describedby="asset-name-error"
  />
  <div id="asset-name-error" role="alert">
    This field is required
  </div>
</form>
```

**Status**:
```tsx
<div role="status" aria-live="polite" aria-atomic="true">
  Loading assets...
</div>
```

---

## Forms and Inputs

### Label Association

All form fields must have associated labels:

```tsx
// Good: Explicit label
<label htmlFor="email">Email</label>
<input id="email" type="email" />

// Good: Implicit label
<label>
  Email
  <input type="email" />
</label>

// Good: aria-label
<input
  type="email"
  aria-label="Email address"
/>
```

### Error Messages

Provide clear, accessible error messages:

```tsx
<TextField
  label="Email"
  error={!!errors.email}
  helperText={errors.email}
  aria-describedby="email-error"
  aria-invalid={!!errors.email}
/>
<div id="email-error" role="alert">
  {errors.email}
</div>
```

### Required Fields

Indicate required fields:

```tsx
<TextField
  label="Asset Name"
  required
  aria-required="true"
  InputLabelProps={{
    required: true
  }}
/>
```

---

## Images and Media

### Alt Text

Provide descriptive alt text:

```tsx
// Informative image
<img
  src="chart.png"
  alt="Sales revenue increased 25% from Q1 to Q2"
/>

// Decorative image
<img
  src="decoration.png"
  alt=""
  aria-hidden="true"
/>

// Complex image (chart, diagram)
<img
  src="complex-chart.png"
  alt="Sales by region chart"
  aria-describedby="chart-description"
/>
<div id="chart-description">
  Detailed description of chart data
</div>
```

### Video and Audio

Provide captions and transcripts:

```tsx
<video controls>
  <source src="video.mp4" type="video/mp4" />
  <track
    kind="captions"
    src="captions.vtt"
    srcLang="en"
    label="English"
    default
  />
</video>
```

---

## Testing Accessibility

### Automated Testing

**Tools**:
- **axe DevTools**: Browser extension for automated testing
- **WAVE**: Web accessibility evaluation tool
- **Lighthouse**: Accessibility audit
- **Pa11y**: Command-line accessibility testing

**Example**:
```bash
# Run axe tests
npm run test:a11y

# Lighthouse audit
lighthouse http://localhost:3000 --view
```

### Manual Testing

**Keyboard Testing**:
- [ ] All interactive elements are keyboard accessible
- [ ] Tab order is logical
- [ ] Focus indicators are visible
- [ ] No keyboard traps
- [ ] Keyboard shortcuts work

**Screen Reader Testing**:
- [ ] Test with NVDA (Windows) or VoiceOver (Mac/iOS)
- [ ] All content is announced correctly
- [ ] Form labels are associated
- [ ] Error messages are announced
- [ ] Dynamic content changes are announced

**Visual Testing**:
- [ ] Color contrast meets requirements
- [ ] Information is not conveyed by color alone
- [ ] Text can be resized up to 200%
- [ ] Content is readable at all zoom levels

### Testing Checklist

**Per Component**:
- [ ] Keyboard accessible
- [ ] Screen reader friendly
- [ ] Proper ARIA labels
- [ ] Focus management
- [ ] Color contrast
- [ ] Error handling

**Per Page**:
- [ ] Page title is descriptive
- [ ] Heading hierarchy is logical
- [ ] Skip links provided
- [ ] Language is identified
- [ ] All images have alt text
- [ ] Forms are accessible

---

## Accessibility Resources

### Tools

- **axe DevTools**: https://www.deque.com/axe/devtools/
- **WAVE**: https://wave.webaim.org/
- **WebAIM Contrast Checker**: https://webaim.org/resources/contrastchecker/
- **Screen Reader Testing**: NVDA, JAWS, VoiceOver

### Documentation

- **WCAG 2.1**: https://www.w3.org/WAI/WCAG21/quickref/
- **ARIA Authoring Practices**: https://www.w3.org/WAI/ARIA/apg/
- **WebAIM**: https://webaim.org/

---

**Last Updated**: 2026-03-22  
**Version**: 1.0.0


---

# Analytics Integration Guide

**Last Updated**: 2026-03-22  
**Version**: 1.0.0

---

## Table of Contents

1. [Overview](#overview)
2. [Analytics Tools](#analytics-tools)
3. [Event Tracking](#event-tracking)
4. [User Analytics](#user-analytics)
5. [Error Tracking](#error-tracking)
6. [Performance Monitoring](#performance-monitoring)
7. [Privacy Compliance](#privacy-compliance)
8. [Best Practices](#best-practices)

---

## Overview

This document describes the analytics and tracking strategy for the frontend application. Analytics help understand user behavior, track errors, monitor performance, and improve the application.

**Analytics Goals**:
- Track user interactions and feature usage
- Monitor application performance
- Track errors and exceptions
- Understand user journeys
- Measure business metrics

**Privacy Principles**:
- User consent for tracking
- Anonymize user data
- Comply with GDPR/CCPA
- Opt-out capabilities

---

## Analytics Tools

### Primary Tools

1. **Google Analytics 4 (GA4)**: User behavior tracking
2. **Sentry**: Error tracking and monitoring
3. **Web Vitals**: Performance monitoring
4. **Custom Analytics**: Business-specific metrics

### Tool Configuration

**File**: `src/lib/analytics/config.ts`

```typescript
export interface AnalyticsConfig {
  googleAnalyticsId?: string;
  sentryDsn?: string;
  environment: 'development' | 'staging' | 'production';
  enableTracking: boolean;
}

export const analyticsConfig: AnalyticsConfig = {
  googleAnalyticsId: import.meta.env.VITE_GA_ID,
  sentryDsn: import.meta.env.VITE_SENTRY_DSN,
  environment: import.meta.env.MODE as any,
  enableTracking: import.meta.env.VITE_ENABLE_ANALYTICS === 'true',
};
```

---

## Event Tracking

### Analytics Service

**Service**: `src/lib/analytics/analytics.ts`

```typescript
import { analyticsConfig } from './config';

export interface AnalyticsEvent {
  name: string;
  category: string;
  action?: string;
  label?: string;
  value?: number;
  properties?: Record<string, any>;
}

class AnalyticsService {
  private enabled: boolean;

  constructor() {
    this.enabled = analyticsConfig.enableTracking && this.hasConsent();
  }

  private hasConsent(): boolean {
    return localStorage.getItem('analytics_consent') === 'true';
  }

  track(event: AnalyticsEvent): void {
    if (!this.enabled) {
      return;
    }

    // Google Analytics
    if (window.gtag) {
      window.gtag('event', event.name, {
        event_category: event.category,
        event_action: event.action,
        event_label: event.label,
        value: event.value,
        ...event.properties,
      });
    }

    // Custom analytics endpoint
    this.sendToCustomAnalytics(event);
  }

  private async sendToCustomAnalytics(event: AnalyticsEvent): Promise<void> {
    try {
      await fetch('/api/v1/analytics/events/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          ...event,
          timestamp: new Date().toISOString(),
          user_id: this.getUserId(),
          session_id: this.getSessionId(),
        }),
      });
    } catch (error) {
      console.error('Failed to send analytics event:', error);
    }
  }

  private getUserId(): string | null {
    // Get user ID from auth context
    return localStorage.getItem('user_id');
  }

  private getSessionId(): string {
    let sessionId = sessionStorage.getItem('session_id');
    if (!sessionId) {
      sessionId = crypto.randomUUID();
      sessionStorage.setItem('session_id', sessionId);
    }
    return sessionId;
  }
}

export const analytics = new AnalyticsService();
```

### Event Tracking Hook

**Hook**: `useAnalytics`

```typescript
import { useCallback } from 'react';
import { analytics } from '@/lib/analytics/analytics';

export function useAnalytics() {
  const trackEvent = useCallback(
    (
      name: string,
      category: string,
      properties?: Record<string, any>
    ) => {
      analytics.track({
        name,
        category,
        properties,
      });
    },
    []
  );

  const trackPageView = useCallback((path: string) => {
    analytics.track({
      name: 'page_view',
      category: 'navigation',
      properties: {
        path,
      },
    });
  }, []);

  return { trackEvent, trackPageView };
}
```

### Common Events

**File**: `src/lib/analytics/events.ts`

```typescript
export const AnalyticsEvents = {
  // Navigation
  PAGE_VIEW: 'page_view',
  NAVIGATION: 'navigation',

  // Assets
  ASSET_CREATED: 'asset_created',
  ASSET_UPDATED: 'asset_updated',
  ASSET_DELETED: 'asset_deleted',
  ASSET_VIEWED: 'asset_viewed',

  // Contracts
  CONTRACT_CREATED: 'contract_created',
  CONTRACT_VALIDATED: 'contract_validated',
  CONTRACT_PUBLISHED: 'contract_published',

  // Marketplace
  CONTRACT_DISCOVERED: 'contract_discovered',
  CONTRACT_DOWNLOADED: 'contract_downloaded',

  // Data Quality
  DQ_RUN_STARTED: 'dq_run_started',
  DQ_RUN_COMPLETED: 'dq_run_completed',

  // Compliance
  COMPLIANCE_SCAN_STARTED: 'compliance_scan_started',
  COMPLIANCE_SCAN_COMPLETED: 'compliance_scan_completed',

  // User Actions
  USER_LOGIN: 'user_login',
  USER_LOGOUT: 'user_logout',
  USER_REGISTERED: 'user_registered',

  // Errors
  ERROR_OCCURRED: 'error_occurred',
  API_ERROR: 'api_error',
} as const;
```

### Usage Examples

**Component Tracking**:
```typescript
function AssetCard({ asset }: AssetCardProps) {
  const { trackEvent } = useAnalytics();

  const handleView = () => {
    trackEvent(AnalyticsEvents.ASSET_VIEWED, 'assets', {
      asset_id: asset.id,
      asset_name: asset.name,
    });
    // Navigate to asset detail
  };

  return (
    <Card onClick={handleView}>
      <CardContent>
        <Typography>{asset.name}</Typography>
      </CardContent>
    </Card>
  );
}
```

**Form Submission Tracking**:
```typescript
function AssetForm({ onSubmit }: AssetFormProps) {
  const { trackEvent } = useAnalytics();

  const handleSubmit = async (data: AssetFormData) => {
    try {
      await onSubmit(data);
      trackEvent(AnalyticsEvents.ASSET_CREATED, 'assets', {
        asset_name: data.name,
        onboarding_mode: data.onboarding_mode,
      });
    } catch (error) {
      trackEvent(AnalyticsEvents.ERROR_OCCURRED, 'errors', {
        error_type: 'asset_creation_failed',
        error_message: error.message,
      });
    }
  };

  return <Form onSubmit={handleSubmit} />;
}
```

---

## User Analytics

### User Identification

**Service**: `src/lib/analytics/user.ts`

```typescript
export function identifyUser(userId: string, traits?: Record<string, any>): void {
  if (window.gtag) {
    window.gtag('set', {
      user_id: userId,
      ...traits,
    });
  }

  // Send to custom analytics
  fetch('/api/v1/analytics/identify/', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      user_id: userId,
      traits,
    }),
  });
}

export function setUserProperties(properties: Record<string, any>): void {
  if (window.gtag) {
    window.gtag('set', 'user_properties', properties);
  }
}
```

### User Journey Tracking

**Hook**: `useUserJourney`

```typescript
export function useUserJourney() {
  const { trackEvent } = useAnalytics();

  const trackJourneyStep = useCallback(
    (step: string, properties?: Record<string, any>) => {
      trackEvent('journey_step', 'user_journey', {
        step,
        ...properties,
      });
    },
    [trackEvent]
  );

  return { trackJourneyStep };
}
```

**Usage**:
```typescript
function OnboardingFlow() {
  const { trackJourneyStep } = useUserJourney();

  useEffect(() => {
    trackJourneyStep('onboarding_started');
  }, []);

  const handleStepComplete = (step: string) => {
    trackJourneyStep('onboarding_step_completed', { step });
  };

  return <OnboardingSteps onStepComplete={handleStepComplete} />;
}
```

---

## Error Tracking

### Sentry Integration

**Configuration**: `src/lib/analytics/sentry.ts`

```typescript
import * as Sentry from '@sentry/react';
import { BrowserTracing } from '@sentry/tracing';

export function initSentry() {
  if (!analyticsConfig.sentryDsn) {
    return;
  }

  Sentry.init({
    dsn: analyticsConfig.sentryDsn,
    environment: analyticsConfig.environment,
    integrations: [
      new BrowserTracing({
        tracingOrigins: ['localhost', /^\//],
      }),
    ],
    tracesSampleRate: analyticsConfig.environment === 'production' ? 0.1 : 1.0,
    beforeSend(event, hint) {
      // Filter out sensitive data
      if (event.request) {
        delete event.request.cookies;
        delete event.request.headers?.Authorization;
      }
      return event;
    },
  });
}

export function captureException(error: Error, context?: Record<string, any>): void {
  Sentry.captureException(error, {
    extra: context,
  });
}

export function captureMessage(message: string, level: Sentry.SeverityLevel = 'info'): void {
  Sentry.captureMessage(message, level);
}
```

### Error Boundary Integration

**Component**: `ErrorBoundary`

```typescript
import * as Sentry from '@sentry/react';
import { captureException } from '@/lib/analytics/sentry';

export class ErrorBoundary extends Component {
  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    captureException(error, {
      componentStack: errorInfo.componentStack,
      errorBoundary: this.constructor.name,
    });
  }

  render() {
    // Error UI
  }
}
```

### API Error Tracking

**Interceptor**: `src/lib/api/interceptors.ts`

```typescript
import { captureException } from '@/lib/analytics/sentry';
import { analytics } from '@/lib/analytics/analytics';

export function errorInterceptor(error: AxiosError) {
  // Track API errors
  if (error.response?.status >= 500) {
    captureException(error as Error, {
      type: 'api_error',
      status: error.response.status,
      url: error.config?.url,
    });

    analytics.track({
      name: AnalyticsEvents.API_ERROR,
      category: 'errors',
      properties: {
        status: error.response.status,
        url: error.config?.url,
      },
    });
  }

  return Promise.reject(error);
}
```

---

## Performance Monitoring

### Web Vitals Tracking

**Implementation**: `src/lib/analytics/web-vitals.ts`

```typescript
import { onCLS, onFID, onFCP, onLCP, onTTFB } from 'web-vitals';

export function trackWebVitals() {
  function sendToAnalytics(metric: any) {
    // Send to Google Analytics
    if (window.gtag) {
      window.gtag('event', metric.name, {
        value: Math.round(metric.value),
        event_category: 'Web Vitals',
        event_label: metric.id,
        non_interaction: true,
      });
    }

    // Send to custom analytics
    fetch('/api/v1/analytics/web-vitals/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(metric),
    });
  }

  onCLS(sendToAnalytics);
  onFID(sendToAnalytics);
  onFCP(sendToAnalytics);
  onLCP(sendToAnalytics);
  onTTFB(sendToAnalytics);
}
```

### Performance Monitoring Hook

**Hook**: `usePerformanceMonitoring`

```typescript
export function usePerformanceMonitoring() {
  useEffect(() => {
    const observer = new PerformanceObserver((list) => {
      for (const entry of list.getEntries()) {
        if (entry.entryType === 'measure') {
          analytics.track({
            name: 'performance_measure',
            category: 'performance',
            properties: {
              measure_name: entry.name,
              duration: entry.duration,
            },
          });
        }
      }
    });

    observer.observe({ entryTypes: ['measure'] });

    return () => {
      observer.disconnect();
    };
  }, []);
}
```

---

## Privacy Compliance

### Consent Management

**Component**: `ConsentBanner`

```typescript
export function ConsentBanner() {
  const [showBanner, setShowBanner] = useState(
    !localStorage.getItem('analytics_consent')
  );

  const handleAccept = () => {
    localStorage.setItem('analytics_consent', 'true');
    setShowBanner(false);
    // Initialize analytics
    initAnalytics();
  };

  const handleReject = () => {
    localStorage.setItem('analytics_consent', 'false');
    setShowBanner(false);
  };

  if (!showBanner) {
    return null;
  }

  return (
    <Banner>
      <BannerContent>
        <Typography>
          We use cookies and analytics to improve your experience.
        </Typography>
        <Button onClick={handleAccept}>Accept</Button>
        <Button onClick={handleReject}>Reject</Button>
      </BannerContent>
    </Banner>
  );
}
```

### Data Anonymization

**Service**: `src/lib/analytics/anonymize.ts`

```typescript
export function anonymizeUserData(data: Record<string, any>): Record<string, any> {
  const anonymized = { ...data };

  // Remove PII
  delete anonymized.email;
  delete anonymized.phone;
  delete anonymized.address;

  // Hash user ID
  if (anonymized.user_id) {
    anonymized.user_id = hashUserId(anonymized.user_id);
  }

  return anonymized;
}

function hashUserId(userId: string): string {
  // Simple hash function (use crypto in production)
  return btoa(userId).substring(0, 16);
}
```

---

## Best Practices

1. **Get User Consent**: Always get consent before tracking
2. **Anonymize Data**: Remove PII from analytics data
3. **Track Meaningful Events**: Track events that provide value
4. **Error Handling**: Handle analytics failures gracefully
5. **Performance**: Don't block UI for analytics
6. **Privacy**: Comply with GDPR/CCPA
7. **Test Analytics**: Test analytics in development
8. **Monitor Costs**: Monitor analytics service costs
9. **Document Events**: Document all tracked events
10. **Review Regularly**: Review analytics data regularly

---

**Last Updated**: 2026-03-22  
**Version**: 1.0.0


---

# API Integration Guide

**Last Updated**: 2026-03-22  
**Version**: 1.0.0

---

## Table of Contents

1. [Overview](#overview)
2. [API Client Setup](#api-client-setup)
3. [Authentication](#authentication)
4. [REST API Integration](#rest-api-integration)
5. [GraphQL API Integration](#graphql-api-integration)
6. [WebSocket Integration](#websocket-integration)
7. [Error Handling](#error-handling)
8. [Request/Response Interceptors](#requestresponse-interceptors)
9. [Caching Strategy](#caching-strategy)
10. [Rate Limiting Handling](#rate-limiting-handling)
11. [Retry Logic](#retry-logic)
12. [TypeScript Types](#typescript-types)
13. [Testing API Integration](#testing-api-integration)

---

## Overview

This guide provides comprehensive instructions for integrating the frontend application with the Data Interoperability Hub backend APIs. It covers REST API, GraphQL API, and WebSocket integration patterns, error handling, caching, and best practices.

**API Endpoints**:
- **REST API**: `/api/v1/`
- **GraphQL API**: `/graphql`
- **WebSocket API**: `/ws/events/`

**Base URLs**:
- **Development**: `http://localhost:8000`
- **Staging**: `https://staging-api.datahub.example.com`
- **Production**: `https://api.datahub.example.com`

---

## API Client Setup

### React Query Configuration

**Recommended**: Use React Query (TanStack Query) for server state management.

```typescript
// src/lib/api/react-query.ts
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ReactQueryDevtools } from '@tanstack/react-query-devtools';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 5 * 60 * 1000, // 5 minutes
      cacheTime: 10 * 60 * 1000, // 10 minutes
      retry: (failureCount, error) => {
        // Don't retry on 4xx errors
        if (error?.status >= 400 && error?.status < 500) {
          return false;
        }
        return failureCount < 3;
      },
      retryDelay: (attemptIndex) => Math.min(1000 * 2 ** attemptIndex, 30000),
      refetchOnWindowFocus: false,
      refetchOnReconnect: true,
    },
    mutations: {
      retry: false,
    },
  },
});

export { queryClient, QueryClientProvider, ReactQueryDevtools };
```

### Axios Configuration

```typescript
// src/lib/api/axios.ts
import axios, { AxiosInstance, AxiosError, InternalAxiosRequestConfig } from 'axios';
import { getAuthToken, refreshAuthToken } from './auth';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

const apiClient: AxiosInstance = axios.create({
  baseURL: `${API_BASE_URL}/api/v1`,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor for authentication
apiClient.interceptors.request.use(
  async (config: InternalAxiosRequestConfig) => {
    const token = getAuthToken();
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    
    // Add tenant ID if available
    const tenantId = getTenantId();
    if (tenantId) {
      config.headers['X-Tenant-ID'] = tenantId;
    }
    
    // Add request ID for tracing
    config.headers['X-Request-ID'] = crypto.randomUUID();
    
    return config;
  },
  (error: AxiosError) => {
    return Promise.reject(error);
  }
);

// Response interceptor for error handling and token refresh
apiClient.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const originalRequest = error.config as InternalAxiosRequestConfig & { _retry?: boolean };
    
    // Handle 401 Unauthorized - try to refresh token
    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true;
      
      try {
        const newToken = await refreshAuthToken();
        if (newToken) {
          originalRequest.headers.Authorization = `Bearer ${newToken}`;
          return apiClient(originalRequest);
        }
      } catch (refreshError) {
        // Refresh failed, redirect to login
        window.location.href = '/login';
        return Promise.reject(refreshError);
      }
    }
    
    // Handle rate limiting (429)
    if (error.response?.status === 429) {
      const retryAfter = error.response.headers['retry-after'];
      if (retryAfter) {
        await new Promise(resolve => setTimeout(resolve, parseInt(retryAfter) * 1000));
        return apiClient(originalRequest);
      }
    }
    
    return Promise.reject(error);
  }
);

export default apiClient;
```

### API Client Factory

```typescript
// src/lib/api/client.ts
import apiClient from './axios';
import { QueryClient } from '@tanstack/react-query';

export interface ApiResponse<T> {
  data: T;
  status: number;
  headers: Record<string, string>;
}

export interface PaginatedResponse<T> {
  count: number;
  page: number;
  page_size: number;
  total_pages: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

export interface CursorPaginatedResponse<T> {
  count: number;
  next_cursor: string | null;
  previous_cursor: string | null;
  page_size: number;
  results: T[];
}

export class ApiClient {
  constructor(
    private client = apiClient,
    private queryClient?: QueryClient
  ) {}

  async get<T>(url: string, config?: any): Promise<ApiResponse<T>> {
    const response = await this.client.get<T>(url, config);
    return {
      data: response.data,
      status: response.status,
      headers: response.headers,
    };
  }

  async post<T>(url: string, data?: any, config?: any): Promise<ApiResponse<T>> {
    const response = await this.client.post<T>(url, data, config);
    return {
      data: response.data,
      status: response.status,
      headers: response.headers,
    };
  }

  async put<T>(url: string, data?: any, config?: any): Promise<ApiResponse<T>> {
    const response = await this.client.put<T>(url, data, config);
    return {
      data: response.data,
      status: response.status,
      headers: response.headers,
    };
  }

  async patch<T>(url: string, data?: any, config?: any): Promise<ApiResponse<T>> {
    const response = await this.client.patch<T>(url, data, config);
    return {
      data: response.data,
      status: response.status,
      headers: response.headers,
    };
  }

  async delete<T>(url: string, config?: any): Promise<ApiResponse<T>> {
    const response = await this.client.delete<T>(url, config);
    return {
      data: response.data as T,
      status: response.status,
      headers: response.headers,
    };
  }
}

export const api = new ApiClient();
```

---

## Authentication

### Token Management

```typescript
// src/lib/api/auth.ts
const TOKEN_KEY = 'auth_token';
const REFRESH_TOKEN_KEY = 'refresh_token';
const TOKEN_EXPIRY_KEY = 'token_expiry';

export interface AuthTokens {
  access: string;
  refresh: string;
  expiresIn: number;
}

export function setAuthTokens(tokens: AuthTokens): void {
  localStorage.setItem(TOKEN_KEY, tokens.access);
  localStorage.setItem(REFRESH_TOKEN_KEY, tokens.refresh);
  
  const expiry = Date.now() + tokens.expiresIn * 1000;
  localStorage.setItem(TOKEN_EXPIRY_KEY, expiry.toString());
}

export function getAuthToken(): string | null {
  const token = localStorage.getItem(TOKEN_KEY);
  const expiry = localStorage.getItem(TOKEN_EXPIRY_KEY);
  
  if (!token || !expiry) {
    return null;
  }
  
  // Check if token is expired
  if (Date.now() > parseInt(expiry)) {
    // Token expired, try to refresh
    refreshAuthToken();
    return null;
  }
  
  return token;
}

export async function refreshAuthToken(): Promise<string | null> {
  const refreshToken = localStorage.getItem(REFRESH_TOKEN_KEY);
  if (!refreshToken) {
    return null;
  }
  
  try {
    const response = await apiClient.post<AuthTokens>('/auth/refresh/', {
      refresh: refreshToken,
    });
    
    setAuthTokens(response.data);
    return response.data.access;
  } catch (error) {
    // Refresh failed, clear tokens
    clearAuthTokens();
    return null;
  }
}

export function clearAuthTokens(): void {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(REFRESH_TOKEN_KEY);
  localStorage.removeItem(TOKEN_EXPIRY_KEY);
}

export function getTenantId(): string | null {
  return localStorage.getItem('tenant_id');
}

export function setTenantId(tenantId: string): void {
  localStorage.setItem('tenant_id', tenantId);
}
```

### Login Flow

```typescript
// src/lib/api/auth.ts (continued)
export interface LoginCredentials {
  email: string;
  password: string;
}

export interface LoginResponse {
  access: string;
  refresh: string;
  user: {
    id: string;
    email: string;
    tenant_id: string;
  };
}

export async function login(credentials: LoginCredentials): Promise<LoginResponse> {
  const response = await apiClient.post<LoginResponse>('/auth/login/', credentials);
  
  setAuthTokens({
    access: response.data.access,
    refresh: response.data.refresh,
    expiresIn: 3600, // 1 hour default
  });
  
  if (response.data.user.tenant_id) {
    setTenantId(response.data.user.tenant_id);
  }
  
  return response.data;
}

export async function logout(): Promise<void> {
  try {
    await apiClient.post('/auth/logout/');
  } catch (error) {
    // Ignore errors on logout
  } finally {
    clearAuthTokens();
  }
}
```

---

## REST API Integration

### React Query Hooks

```typescript
// src/hooks/api/useAssets.ts
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api/client';
import type { Asset, PaginatedResponse } from '@/types';

// Query keys
export const assetKeys = {
  all: ['assets'] as const,
  lists: () => [...assetKeys.all, 'list'] as const,
  list: (filters?: Record<string, any>) => [...assetKeys.lists(), filters] as const,
  details: () => [...assetKeys.all, 'detail'] as const,
  detail: (id: string) => [...assetKeys.details(), id] as const,
};

// List assets
export function useAssets(filters?: {
  page?: number;
  page_size?: number;
  ordering?: string;
  search?: string;
}) {
  return useQuery({
    queryKey: assetKeys.list(filters),
    queryFn: async () => {
      const params = new URLSearchParams();
      if (filters?.page) params.append('page', filters.page.toString());
      if (filters?.page_size) params.append('page_size', filters.page_size.toString());
      if (filters?.ordering) params.append('ordering', filters.ordering);
      if (filters?.search) params.append('search', filters.search);
      
      const response = await api.get<PaginatedResponse<Asset>>(
        `/assets/assets/?${params.toString()}`
      );
      return response.data;
    },
  });
}

// Get single asset
export function useAsset(id: string) {
  return useQuery({
    queryKey: assetKeys.detail(id),
    queryFn: async () => {
      const response = await api.get<Asset>(`/assets/assets/${id}/`);
      return response.data;
    },
    enabled: !!id,
  });
}

// Create asset
export function useCreateAsset() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: async (data: Partial<Asset>) => {
      const response = await api.post<Asset>('/assets/assets/', data);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: assetKeys.lists() });
    },
  });
}

// Update asset
export function useUpdateAsset() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: async ({ id, data }: { id: string; data: Partial<Asset> }) => {
      const response = await api.patch<Asset>(`/assets/assets/${id}/`, data);
      return response.data;
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: assetKeys.detail(data.id) });
      queryClient.invalidateQueries({ queryKey: assetKeys.lists() });
    },
  });
}

// Delete asset
export function useDeleteAsset() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: async (id: string) => {
      await api.delete(`/assets/assets/${id}/`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: assetKeys.lists() });
    },
  });
}
```

### Pagination Handling

```typescript
// src/hooks/api/usePagination.ts
import { useState, useMemo } from 'react';
import type { PaginatedResponse } from '@/lib/api/client';

export function usePagination<T>(
  query: { data?: PaginatedResponse<T>; isLoading: boolean; error: any }
) {
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  
  const pagination = useMemo(() => {
    if (!query.data) {
      return {
        page: 1,
        pageSize: 20,
        totalPages: 0,
        totalCount: 0,
        hasNext: false,
        hasPrevious: false,
      };
    }
    
    return {
      page: query.data.page,
      pageSize: query.data.page_size,
      totalPages: query.data.total_pages,
      totalCount: query.data.count,
      hasNext: !!query.data.next,
      hasPrevious: !!query.data.previous,
    };
  }, [query.data]);
  
  const goToPage = (newPage: number) => {
    setPage(newPage);
  };
  
  const goToNext = () => {
    if (pagination.hasNext) {
      setPage(page + 1);
    }
  };
  
  const goToPrevious = () => {
    if (pagination.hasPrevious) {
      setPage(page - 1);
    }
  };
  
  return {
    ...pagination,
    goToPage,
    goToNext,
    goToPrevious,
    setPageSize,
  };
}
```

---

## GraphQL API Integration

### GraphQL Client Setup

```typescript
// src/lib/api/graphql.ts
import { GraphQLClient } from 'graphql-request';
import { getAuthToken } from './auth';

const GRAPHQL_ENDPOINT = `${import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'}/graphql`;

export const graphqlClient = new GraphQLClient(GRAPHQL_ENDPOINT, {
  headers: () => {
    const token = getAuthToken();
    return {
      Authorization: token ? `Bearer ${token}` : '',
    };
  },
});

// GraphQL query example
export const GET_ASSET_QUERY = `
  query GetAsset($id: ID!) {
    asset(id: $id) {
      id
      name
      key
      description
      status
      createdAt
      contract {
        id
        version
        status
      }
      dataset {
        id
        name
        version
      }
    }
  }
`;

export const LIST_ASSETS_QUERY = `
  query ListAssets($first: Int, $after: String, $filter: AssetFilter) {
    assets(first: $first, after: $after, filter: $filter) {
      edges {
        node {
          id
          name
          key
          status
        }
        cursor
      }
      pageInfo {
        hasNextPage
        hasPreviousPage
        startCursor
        endCursor
      }
    }
  }
`;
```

### React Query with GraphQL

```typescript
// src/hooks/api/useGraphQL.ts
import { useQuery } from '@tanstack/react-query';
import { graphqlClient, GET_ASSET_QUERY } from '@/lib/api/graphql';
import type { Asset } from '@/types';

export function useGraphQLAsset(id: string) {
  return useQuery({
    queryKey: ['graphql', 'asset', id],
    queryFn: async () => {
      const data = await graphqlClient.request<{ asset: Asset }>(GET_ASSET_QUERY, { id });
      return data.asset;
    },
    enabled: !!id,
  });
}
```

---

## WebSocket Integration

### WebSocket Client

```typescript
// src/lib/api/websocket.ts
import { getAuthToken } from './auth';

export type WebSocketEventType =
  | 'contract.created'
  | 'contract.updated'
  | 'contract.validated'
  | 'asset.created'
  | 'asset.updated'
  | 'job.started'
  | 'job.completed'
  | 'job.failed'
  | 'dq.run.completed'
  | 'compliance.scan.completed';

export interface WebSocketEvent {
  type: string;
  data: any;
  timestamp: string;
  request_id?: string;
}

export interface WebSocketMessage {
  type: 'subscribe' | 'unsubscribe' | 'ping';
  data?: {
    event_types?: WebSocketEventType[];
    filters?: Record<string, any>;
  };
}

export class WebSocketClient {
  private ws: WebSocket | null = null;
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 5;
  private reconnectDelay = 1000;
  private listeners: Map<string, Set<(event: WebSocketEvent) => void>> = new Map();
  private pingInterval: number | null = null;

  constructor(private url: string) {}

  connect(): Promise<void> {
    return new Promise((resolve, reject) => {
      const token = getAuthToken();
      if (!token) {
        reject(new Error('No authentication token'));
        return;
      }

      const wsUrl = `${this.url}?token=${token}`;
      this.ws = new WebSocket(wsUrl);

      this.ws.onopen = () => {
        console.log('WebSocket connected');
        this.reconnectAttempts = 0;
        this.startPingInterval();
        resolve();
      };

      this.ws.onmessage = (event) => {
        try {
          const message: WebSocketEvent = JSON.parse(event.data);
          this.handleMessage(message);
        } catch (error) {
          console.error('Failed to parse WebSocket message:', error);
        }
      };

      this.ws.onerror = (error) => {
        console.error('WebSocket error:', error);
        reject(error);
      };

      this.ws.onclose = () => {
        console.log('WebSocket disconnected');
        this.stopPingInterval();
        this.attemptReconnect();
      };
    });
  }

  private handleMessage(message: WebSocketEvent): void {
    // Handle different message types
    if (message.type === 'event') {
      const eventType = message.data?.event_type;
      if (eventType) {
        this.notifyListeners(eventType, message);
      }
    } else if (message.type === 'subscription_confirmed') {
      console.log('Subscription confirmed:', message.data);
    } else if (message.type === 'error') {
      console.error('WebSocket error:', message.data);
    } else if (message.type === 'pong') {
      // Ping response received
    }
  }

  subscribe(eventTypes: WebSocketEventType[], filters?: Record<string, any>): void {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
      console.warn('WebSocket not connected');
      return;
    }

    const message: WebSocketMessage = {
      type: 'subscribe',
      data: {
        event_types: eventTypes,
        filters,
      },
    };

    this.ws.send(JSON.stringify(message));
  }

  unsubscribe(eventTypes: WebSocketEventType[]): void {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
      return;
    }

    const message: WebSocketMessage = {
      type: 'unsubscribe',
      data: {
        event_types: eventTypes,
      },
    };

    this.ws.send(JSON.stringify(message));
  }

  on(eventType: WebSocketEventType, callback: (event: WebSocketEvent) => void): () => void {
    if (!this.listeners.has(eventType)) {
      this.listeners.set(eventType, new Set());
    }
    this.listeners.get(eventType)!.add(callback);

    // Return unsubscribe function
    return () => {
      this.listeners.get(eventType)?.delete(callback);
    };
  }

  private notifyListeners(eventType: string, event: WebSocketEvent): void {
    const listeners = this.listeners.get(eventType as WebSocketEventType);
    if (listeners) {
      listeners.forEach((callback) => callback(event));
    }
  }

  private startPingInterval(): void {
    this.pingInterval = window.setInterval(() => {
      if (this.ws && this.ws.readyState === WebSocket.OPEN) {
        this.ws.send(JSON.stringify({ type: 'ping' }));
      }
    }, 30000); // Ping every 30 seconds
  }

  private stopPingInterval(): void {
    if (this.pingInterval) {
      clearInterval(this.pingInterval);
      this.pingInterval = null;
    }
  }

  private attemptReconnect(): void {
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      console.error('Max reconnection attempts reached');
      return;
    }

    this.reconnectAttempts++;
    const delay = this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1);

    setTimeout(() => {
      console.log(`Attempting to reconnect (${this.reconnectAttempts}/${this.maxReconnectAttempts})...`);
      this.connect().catch((error) => {
        console.error('Reconnection failed:', error);
      });
    }, delay);
  }

  disconnect(): void {
    this.stopPingInterval();
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
  }
}

// Singleton instance
const WS_URL = `${import.meta.env.VITE_WS_URL || 'ws://localhost:8000'}/ws/events/`;
export const wsClient = new WebSocketClient(WS_URL);
```

### React Hook for WebSocket

```typescript
// src/hooks/useWebSocket.ts
import { useEffect, useRef } from 'react';
import { wsClient, type WebSocketEventType, type WebSocketEvent } from '@/lib/api/websocket';
import { useQueryClient } from '@tanstack/react-query';

export function useWebSocket(
  eventTypes: WebSocketEventType[],
  onEvent?: (event: WebSocketEvent) => void
) {
  const queryClient = useQueryClient();
  const onEventRef = useRef(onEvent);

  useEffect(() => {
    onEventRef.current = onEvent;
  }, [onEvent]);

  useEffect(() => {
    let unsubscribeFunctions: (() => void)[] = [];

    const connectAndSubscribe = async () => {
      try {
        await wsClient.connect();
        wsClient.subscribe(eventTypes);

        // Set up listeners
        eventTypes.forEach((eventType) => {
          const unsubscribe = wsClient.on(eventType, (event) => {
            // Invalidate relevant queries
            if (eventType.startsWith('asset.')) {
              queryClient.invalidateQueries({ queryKey: ['assets'] });
            } else if (eventType.startsWith('contract.')) {
              queryClient.invalidateQueries({ queryKey: ['contracts'] });
            } else if (eventType.startsWith('job.')) {
              queryClient.invalidateQueries({ queryKey: ['jobs'] });
            }

            // Call custom handler
            onEventRef.current?.(event);
          });
          unsubscribeFunctions.push(unsubscribe);
        });
      } catch (error) {
        console.error('WebSocket connection failed:', error);
      }
    };

    connectAndSubscribe();

    return () => {
      unsubscribeFunctions.forEach((unsubscribe) => unsubscribe());
      wsClient.unsubscribe(eventTypes);
    };
  }, [eventTypes, queryClient]);
}
```

---

## Error Handling

### Error Types

```typescript
// src/lib/api/errors.ts
export interface ApiError {
  error: {
    code: string;
    message: string;
    http_status: number;
    request_id?: string;
    timestamp?: string;
    details?: Record<string, any>;
  };
}

export class ApiException extends Error {
  constructor(
    public code: string,
    public message: string,
    public status: number,
    public requestId?: string,
    public details?: Record<string, any>
  ) {
    super(message);
    this.name = 'ApiException';
  }

  static fromAxiosError(error: any): ApiException {
    if (error.response?.data?.error) {
      const apiError = error.response.data.error;
      return new ApiException(
        apiError.code || 'UNKNOWN_ERROR',
        apiError.message || 'An error occurred',
        apiError.http_status || error.response.status,
        apiError.request_id,
        apiError.details
      );
    }

    return new ApiException(
      'NETWORK_ERROR',
      error.message || 'Network error occurred',
      error.response?.status || 0
    );
  }
}
```

### Error Boundary Component

```typescript
// src/components/ErrorBoundary.tsx
import React, { Component, ErrorInfo, ReactNode } from 'react';
import { Alert, Button, Container } from '@mui/material';

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo): void {
    console.error('ErrorBoundary caught an error:', error, errorInfo);
    // Log to error tracking service (e.g., Sentry)
  }

  handleReset = (): void => {
    this.setState({ hasError: false, error: null });
  };

  render(): ReactNode {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback;
      }

      return (
        <Container maxWidth="md" sx={{ mt: 4 }}>
          <Alert severity="error" sx={{ mb: 2 }}>
            <strong>Something went wrong</strong>
            <p>{this.state.error?.message}</p>
          </Alert>
          <Button variant="contained" onClick={this.handleReset}>
            Try Again
          </Button>
        </Container>
      );
    }

    return this.props.children;
  }
}
```

### Error Handling Hook

```typescript
// src/hooks/useErrorHandler.ts
import { useCallback } from 'react';
import { useSnackbar } from 'notistack';
import { ApiException } from '@/lib/api/errors';

export function useErrorHandler() {
  const { enqueueSnackbar } = useSnackbar();

  const handleError = useCallback(
    (error: unknown) => {
      if (error instanceof ApiException) {
        // Handle API errors
        const message = error.details?.field_errors
          ? Object.values(error.details.field_errors).flat().join(', ')
          : error.message;

        enqueueSnackbar(message, {
          variant: 'error',
          autoHideDuration: 5000,
        });

        // Handle specific error codes
        if (error.code === 'UNAUTHORIZED') {
          // Redirect to login
          window.location.href = '/login';
        } else if (error.code === 'RATE_LIMIT_EXCEEDED') {
          // Show rate limit message
          enqueueSnackbar('Rate limit exceeded. Please try again later.', {
            variant: 'warning',
          });
        }
      } else if (error instanceof Error) {
        // Handle generic errors
        enqueueSnackbar(error.message, { variant: 'error' });
      } else {
        // Handle unknown errors
        enqueueSnackbar('An unexpected error occurred', { variant: 'error' });
      }
    },
    [enqueueSnackbar]
  );

  return { handleError };
}
```

---

## Request/Response Interceptors

### Request Interceptor

```typescript
// src/lib/api/interceptors.ts
import { InternalAxiosRequestConfig } from 'axios';
import { getAuthToken, getTenantId } from './auth';

export function requestInterceptor(config: InternalAxiosRequestConfig): InternalAxiosRequestConfig {
  // Add authentication token
  const token = getAuthToken();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }

  // Add tenant ID
  const tenantId = getTenantId();
  if (tenantId) {
    config.headers['X-Tenant-ID'] = tenantId;
  }

  // Add request ID for tracing
  config.headers['X-Request-ID'] = crypto.randomUUID();

  // Add API version
  config.headers['X-API-Version'] = 'v1';

  return config;
}
```

### Response Interceptor

```typescript
// src/lib/api/interceptors.ts (continued)
import { AxiosResponse, AxiosError } from 'axios';
import { refreshAuthToken } from './auth';

export function responseInterceptor(response: AxiosResponse): AxiosResponse {
  // Log response for debugging (development only)
  if (import.meta.env.DEV) {
    console.log('API Response:', {
      url: response.config.url,
      status: response.status,
      data: response.data,
    });
  }

  // Extract rate limit headers
  const rateLimitHeaders = {
    limit: response.headers['x-ratelimit-limit'],
    remaining: response.headers['x-ratelimit-remaining'],
    reset: response.headers['x-ratelimit-reset'],
  };

  // Store rate limit info (can be used for UI indicators)
  if (rateLimitHeaders.limit) {
    localStorage.setItem('rate_limit_info', JSON.stringify(rateLimitHeaders));
  }

  return response;
}

export async function errorInterceptor(
  error: AxiosError
): Promise<AxiosError | any> {
  const originalRequest = error.config as InternalAxiosRequestConfig & { _retry?: boolean };

  // Handle 401 - Unauthorized
  if (error.response?.status === 401 && !originalRequest._retry) {
    originalRequest._retry = true;

    try {
      const newToken = await refreshAuthToken();
      if (newToken) {
        originalRequest.headers.Authorization = `Bearer ${newToken}`;
        return apiClient(originalRequest);
      }
    } catch (refreshError) {
      // Refresh failed, redirect to login
      window.location.href = '/login';
      return Promise.reject(refreshError);
    }
  }

  // Handle 429 - Rate Limited
  if (error.response?.status === 429) {
    const retryAfter = error.response.headers['retry-after'];
    if (retryAfter) {
      await new Promise((resolve) => setTimeout(resolve, parseInt(retryAfter) * 1000));
      return apiClient(originalRequest);
    }
  }

  // Handle 500 - Server Error
  if (error.response?.status === 500) {
    // Log to error tracking service
    console.error('Server error:', error);
  }

  return Promise.reject(error);
}
```

---

## Caching Strategy

### React Query Caching

```typescript
// src/lib/api/cache.ts
import { QueryClient } from '@tanstack/react-query';

export const cacheConfig = {
  // Short-lived cache (1 minute) - frequently changing data
  short: {
    staleTime: 1 * 60 * 1000,
    cacheTime: 5 * 60 * 1000,
  },

  // Medium cache (5 minutes) - moderately changing data
  medium: {
    staleTime: 5 * 60 * 1000,
    cacheTime: 10 * 60 * 1000,
  },

  // Long cache (30 minutes) - rarely changing data
  long: {
    staleTime: 30 * 60 * 1000,
    cacheTime: 60 * 60 * 1000,
  },

  // Infinite cache - static reference data
  infinite: {
    staleTime: Infinity,
    cacheTime: Infinity,
  },
};

// Cache invalidation helpers
export function invalidateAssetCache(queryClient: QueryClient, assetId?: string): void {
  if (assetId) {
    queryClient.invalidateQueries({ queryKey: ['assets', 'detail', assetId] });
  }
  queryClient.invalidateQueries({ queryKey: ['assets', 'list'] });
}

export function invalidateContractCache(queryClient: QueryClient, contractId?: string): void {
  if (contractId) {
    queryClient.invalidateQueries({ queryKey: ['contracts', 'detail', contractId] });
  }
  queryClient.invalidateQueries({ queryKey: ['contracts', 'list'] });
}
```

---

## Rate Limiting Handling

### Rate Limit Hook

```typescript
// src/hooks/useRateLimit.ts
import { useState, useEffect } from 'react';

export interface RateLimitInfo {
  limit: number;
  remaining: number;
  reset: number;
}

export function useRateLimit(): RateLimitInfo | null {
  const [rateLimit, setRateLimit] = useState<RateLimitInfo | null>(null);

  useEffect(() => {
    const stored = localStorage.getItem('rate_limit_info');
    if (stored) {
      try {
        setRateLimit(JSON.parse(stored));
      } catch (error) {
        console.error('Failed to parse rate limit info:', error);
      }
    }
  }, []);

  return rateLimit;
}
```

### Rate Limit Indicator Component

```typescript
// src/components/RateLimitIndicator.tsx
import { LinearProgress, Tooltip, Box } from '@mui/material';
import { useRateLimit } from '@/hooks/useRateLimit';

export function RateLimitIndicator() {
  const rateLimit = useRateLimit();

  if (!rateLimit) {
    return null;
  }

  const percentage = (rateLimit.remaining / rateLimit.limit) * 100;
  const isLow = percentage < 20;

  return (
    <Tooltip title={`${rateLimit.remaining} of ${rateLimit.limit} requests remaining`}>
      <Box sx={{ width: 100, mr: 2 }}>
        <LinearProgress
          variant="determinate"
          value={percentage}
          color={isLow ? 'error' : 'primary'}
          sx={{ height: 4, borderRadius: 2 }}
        />
      </Box>
    </Tooltip>
  );
}
```

---

## Retry Logic

### Retry Configuration

```typescript
// src/lib/api/retry.ts
export interface RetryConfig {
  maxRetries: number;
  retryDelay: number;
  retryableStatuses: number[];
  retryableErrors: string[];
}

export const defaultRetryConfig: RetryConfig = {
  maxRetries: 3,
  retryDelay: 1000,
  retryableStatuses: [500, 502, 503, 504],
  retryableErrors: ['NETWORK_ERROR', 'TIMEOUT'],
};

export async function retryRequest<T>(
  request: () => Promise<T>,
  config: Partial<RetryConfig> = {}
): Promise<T> {
  const finalConfig = { ...defaultRetryConfig, ...config };
  let lastError: Error | null = null;

  for (let attempt = 0; attempt <= finalConfig.maxRetries; attempt++) {
    try {
      return await request();
    } catch (error: any) {
      lastError = error;

      // Don't retry on last attempt
      if (attempt === finalConfig.maxRetries) {
        break;
      }

      // Check if error is retryable
      const isRetryable =
        finalConfig.retryableStatuses.includes(error?.response?.status) ||
        finalConfig.retryableErrors.includes(error?.code);

      if (!isRetryable) {
        break;
      }

      // Wait before retry with exponential backoff
      const delay = finalConfig.retryDelay * Math.pow(2, attempt);
      await new Promise((resolve) => setTimeout(resolve, delay));
    }
  }

  throw lastError || new Error('Request failed');
}
```

---

## TypeScript Types

### API Types

```typescript
// src/types/api.ts
export interface ApiResponse<T> {
  data: T;
  status: number;
  headers: Record<string, string>;
}

export interface PaginatedResponse<T> {
  count: number;
  page: number;
  page_size: number;
  total_pages: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

export interface CursorPaginatedResponse<T> {
  count: number;
  next_cursor: string | null;
  previous_cursor: string | null;
  page_size: number;
  results: T[];
}

export interface ApiError {
  error: {
    code: string;
    message: string;
    http_status: number;
    request_id?: string;
    timestamp?: string;
    details?: {
      field_errors?: Record<string, string[]>;
      [key: string]: any;
    };
  };
}
```

---

## Testing API Integration

### Mock API Client

```typescript
// src/lib/api/mock.ts
import { ApiClient } from './client';

export class MockApiClient extends ApiClient {
  private mockData: Map<string, any> = new Map();

  setMockData(endpoint: string, data: any): void {
    this.mockData.set(endpoint, data);
  }

  async get<T>(url: string): Promise<ApiResponse<T>> {
    const mockData = this.mockData.get(url);
    if (mockData) {
      return {
        data: mockData,
        status: 200,
        headers: {},
      };
    }
    throw new Error(`No mock data for ${url}`);
  }
}

// Usage in tests
export const mockApi = new MockApiClient();
```

### Test Utilities

```typescript
// src/test-utils/api.ts
import { QueryClient } from '@tanstack/react-query';
import { render, RenderOptions } from '@testing-library/react';
import { QueryClientProvider } from '@tanstack/react-query';

export function createTestQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
        cacheTime: 0,
      },
      mutations: {
        retry: false,
      },
    },
  });
}

export function renderWithProviders(
  ui: React.ReactElement,
  options?: RenderOptions
) {
  const queryClient = createTestQueryClient();

  function Wrapper({ children }: { children: React.ReactNode }) {
    return (
      <QueryClientProvider client={queryClient}>
        {children}
      </QueryClientProvider>
    );
  }

  return render(ui, { wrapper: Wrapper, ...options });
}
```

---

## Workflow State Management

### Overview

The frontend tracks multi-step workflow execution through React Query and WebSocket integration.

### Workflow Progress Components

#### TransformationPipelineProgress

Tracks transformation pipeline execution progress:

```typescript
import { useWorkflowProgress } from '@/hooks/useWorkflowProgress';

function TransformationPipelineProgress({ pipelineId }: { pipelineId: string }) {
  const { workflow, progress, currentStep, error } = useWorkflowProgress(
    'transformation_pipeline',
    pipelineId
  );

  return (
    <WorkflowProgress
      workflow={workflow}
      progress={progress}
      currentStep={currentStep}
      error={error}
    />
  );
}
```

#### AIMLOperationProgress

Tracks AI/ML operation progress:

```typescript
function AIMLOperationProgress({ operationId }: { operationId: string }) {
  const { workflow, progress, currentStep, error } = useWorkflowProgress(
    'ai_ml_operation',
    operationId
  );

  return (
    <WorkflowProgress
      workflow={workflow}
      progress={progress}
      currentStep={currentStep}
      error={error}
    />
  );
}
```

### React Query Integration

Workflow state is cached in React Query:

```typescript
import { useQuery } from '@tanstack/react-query';

function useWorkflowProgress(workflowName: string, instanceId: string) {
  return useQuery({
    queryKey: ['workflow', workflowName, instanceId],
    queryFn: () => api.getWorkflowInstance(workflowName, instanceId),
    refetchInterval: 2000, // Poll every 2 seconds
  });
}
```

### WebSocket Integration

Real-time workflow updates via WebSocket:

```typescript
import { useWebSocket } from '@/hooks/useWebSocket';

function useWorkflowUpdates(workflowName: string, instanceId: string) {
  const { data, queryClient } = useWebSocket(`workflow.${workflowName}.${instanceId}`);

  useEffect(() => {
    if (data) {
      // Update React Query cache
      queryClient.setQueryData(
        ['workflow', workflowName, instanceId],
        data
      );
    }
  }, [data, workflowName, instanceId, queryClient]);
}
```

### State Reconciliation

Handle conflicts between optimistic updates and server state:

```typescript
function useWorkflowMutation(workflowName: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (input: WorkflowInput) => 
      api.startWorkflow(workflowName, input),
    onMutate: async (input) => {
      // Optimistic update
      await queryClient.cancelQueries(['workflow', workflowName]);
      const previous = queryClient.getQueryData(['workflow', workflowName]);
      queryClient.setQueryData(['workflow', workflowName], {
        ...previous,
        status: 'running',
      });
      return { previous };
    },
    onError: (err, input, context) => {
      // Rollback on error
      queryClient.setQueryData(['workflow', workflowName], context.previous);
    },
    onSettled: () => {
      // Refetch to reconcile
      queryClient.invalidateQueries(['workflow', workflowName]);
    },
  });
}
```

### Workflow Error Handling

Handle workflow failures gracefully:

```typescript
function WorkflowError({ error, workflow }: { error: Error; workflow: Workflow }) {
  if (error.type === 'COMPENSATION_FAILED') {
    return <CompensationError workflow={workflow} />;
  }
  if (error.type === 'STEP_FAILED') {
    return <StepError workflow={workflow} failedStep={error.step} />;
  }
  return <GenericError error={error} />;
}
```

---

## Best Practices

1. **Always use React Query for server state** - Don't use useState for API data
2. **Handle loading and error states** - Always show appropriate UI states
3. **Use TypeScript types** - Define types for all API responses
4. **Implement optimistic updates** - Update UI immediately, rollback on error
5. **Cache invalidation** - Invalidate related queries after mutations
6. **Error boundaries** - Wrap components in error boundaries
7. **Request deduplication** - React Query handles this automatically
8. **Pagination** - Use cursor-based pagination for large datasets
9. **WebSocket reconnection** - Always implement reconnection logic
10. **Rate limit awareness** - Show rate limit status to users

---

**Last Updated**: 2026-03-22  
**Version**: 1.0.0


---

# Authentication UI Specifications

**Last Updated**: 2026-03-22  
**Version**: 1.0.0

---

## Table of Contents

1. [Overview](#overview)
2. [Login Screen](#login-screen)
3. [Registration Screen](#registration-screen)
4. [Tenant Selection Screen](#tenant-selection-screen)
5. [API Key Management Screen](#api-key-management-screen)
6. [Permission Denied Screens](#permission-denied-screens)
7. [Password Reset Flow](#password-reset-flow)
8. [Multi-Factor Authentication](#multi-factor-authentication)
9. [SSO Integration](#sso-integration)
10. [Session Management](#session-management)

---

## Overview

This document specifies the authentication UI components and flows for the Interoperable Data Hub platform. All authentication screens follow the design system guidelines and accessibility standards.

**Authentication Methods**:
- Email/Password authentication
- API Key authentication
- SSO (Single Sign-On) - OAuth 2.0, SAML 2.0
- Multi-Factor Authentication (MFA)

**Key Principles**:
- Secure by default
- Clear error messages
- Accessible to all users
- Consistent with design system
- Mobile-responsive

---

## Login Screen

### UI-AUTH-001: Login Screen

**Screen ID**: UI-AUTH-001  
**Screen Name**: Login  
**Purpose**: Authenticate users and establish session

**Layout**:
```
┌─────────────────────────────────────────┐
│                                         │
│              [Logo]                     │
│         Data Interoperability Hub       │
│                                         │
│  ┌───────────────────────────────────┐ │
│  │ Sign In                            │ │
│  ├───────────────────────────────────┤ │
│  │                                   │ │
│  │ Email Address *                   │ │
│  │ [_____________________________]   │ │
│  │                                   │ │
│  │ Password *                         │ │
│  │ [_____________________________] 🔒 │ │
│  │                                   │ │
│  │ ☐ Remember me                     │ │
│  │                                   │ │
│  │ [Forgot Password?]                 │ │
│  │                                   │ │
│  │ [Sign In]                         │ │
│  │                                   │ │
│  │ ─────────── or ───────────        │ │
│  │                                   │ │
│  │ [Sign in with SSO]                │ │
│  │                                   │ │
│  └───────────────────────────────────┘ │
│                                         │
│  Don't have an account? [Sign Up]      │
│                                         │
└─────────────────────────────────────────┘
```

**Components**:
- Logo component
- Container (centered, max-width: 400px)
- TextInput (Email, Password)
- Checkbox (Remember me)
- Button (Sign In, primary)
- Link (Forgot Password, Sign Up)
- Divider (or separator)
- Button (Sign in with SSO, secondary)

**Interactions**:
- Email: Required, email validation on blur
- Password: Required, show/hide toggle
- Remember me: Persist session (optional)
- Sign In: Validate form, submit, show loading state
- Forgot Password: Navigate to password reset
- Sign Up: Navigate to registration
- SSO: Redirect to SSO provider

**States**:
- **Default**: Empty form
- **Validating**: Show validation errors inline
- **Submitting**: Disable form, show spinner on button
- **Error**: Show error message above form
- **Success**: Redirect to tenant selection or dashboard

**Validation**:
- Email: Valid email format required
- Password: Minimum 8 characters
- Show validation errors inline below fields

**Error Messages**:
- Invalid credentials: "Invalid email or password"
- Account locked: "Account temporarily locked. Please try again in {minutes} minutes"
- Network error: "Unable to connect. Please check your connection"
- Server error: "An error occurred. Please try again"

**Accessibility**:
- All form fields have labels
- Error messages associated with fields (aria-describedby)
- Keyboard navigation support
- Focus management
- Screen reader announcements

**Responsive Behavior**:
- Desktop: Centered card, max-width 400px
- Tablet: Centered card, full width with padding
- Mobile: Full width, padding 16px

---

## Registration Screen

### UI-AUTH-002: Registration Screen

**Screen ID**: UI-AUTH-002  
**Screen Name**: Register  
**Purpose**: Create new user account

**Layout**:
```
┌─────────────────────────────────────────┐
│              [Logo]                     │
│         Data Interoperability Hub       │
│                                         │
│  ┌───────────────────────────────────┐ │
│  │ Create Account                    │ │
│  ├───────────────────────────────────┤ │
│  │                                   │ │
│  │ Full Name *                       │ │
│  │ [_____________________________]   │ │
│  │                                   │ │
│  │ Email Address *                   │ │
│  │ [_____________________________]   │ │
│  │                                   │ │
│  │ Password *                         │ │
│  │ [_____________________________] 🔒 │ │
│  │ • 8+ characters                   │ │
│  │ • 1 uppercase letter               │ │
│  │ • 1 number                         │ │
│  │                                   │ │
│  │ Confirm Password *                 │ │
│  │ [_____________________________] 🔒 │ │
│  │                                   │ │
│  │ ☐ I agree to Terms of Service     │ │
│  │    and Privacy Policy *            │ │
│  │                                   │ │
│  │ [Create Account]                  │ │
│  │                                   │ │
│  │ ─────────── or ───────────        │ │
│  │                                   │ │
│  │ [Sign up with SSO]                │ │
│  │                                   │ │
│  └───────────────────────────────────┘ │
│                                         │
│  Already have an account? [Sign In]    │
│                                         │
└─────────────────────────────────────────┘
```

**Components**:
- Logo component
- Container (centered, max-width: 400px)
- TextInput (Full Name, Email, Password, Confirm Password)
- PasswordStrengthIndicator
- Checkbox (Terms agreement)
- Button (Create Account, primary)
- Link (Sign In)
- Divider
- Button (Sign up with SSO, secondary)

**Interactions**:
- Full Name: Required, 2-100 characters
- Email: Required, email validation, check availability
- Password: Required, show strength indicator
- Confirm Password: Must match password
- Terms: Required checkbox
- Create Account: Validate, submit, show loading
- Real-time password strength feedback

**Password Strength Indicator**:
- Weak: Red, < 8 chars or missing requirements
- Medium: Yellow, 8+ chars, missing 1 requirement
- Strong: Green, all requirements met

**States**:
- **Default**: Empty form
- **Validating**: Show validation errors
- **Checking Email**: Show "Checking availability..."
- **Submitting**: Disable form, show spinner
- **Error**: Show error message
- **Success**: Navigate to email verification screen

---

## Tenant Selection Screen

### UI-AUTH-003: Tenant Selection Screen

**Screen ID**: UI-AUTH-003  
**Screen Name**: Select Tenant  
**Purpose**: Select tenant after authentication (if user belongs to multiple tenants)

**Layout**:
```
┌─────────────────────────────────────────┐
│              [Logo]                     │
│                                         │
│  ┌───────────────────────────────────┐ │
│  │ Select Tenant                      │ │
│  ├───────────────────────────────────┤ │
│  │                                   │ │
│  │ Welcome, {user.name}              │ │
│  │                                   │ │
│  │ You have access to multiple       │ │
│  │ tenants. Please select one:        │ │
│  │                                   │ │
│  │ ┌─────────────────────────────┐   │ │
│  │ │ ○ Acme Corporation          │   │ │
│  │ │   acme.example.com          │   │ │
│  │ │   Role: Tenant Admin        │   │ │
│  │ └─────────────────────────────┘   │ │
│  │                                   │ │
│  │ ┌─────────────────────────────┐   │ │
│  │ │ ● Data Solutions Inc.        │   │ │
│  │ │   datasolutions.example.com  │   │ │
│  │ │   Role: Data Engineer       │   │ │
│  │ └─────────────────────────────┘   │ │
│  │                                   │ │
│  │ [Continue]                        │ │
│  │                                   │ │
│  └───────────────────────────────────┘ │
│                                         │
└─────────────────────────────────────────┘
```

**Components**:
- Logo component
- Container (centered, max-width: 500px)
- RadioGroup (Tenant selection)
- RadioCard (Tenant option with details)
- Button (Continue, primary)

**Interactions**:
- Tenant selection: Radio button selection
- Continue: Set selected tenant, navigate to dashboard
- Auto-select: If only one tenant, auto-select and redirect

**States**:
- **Loading**: Show skeleton loaders
- **Single Tenant**: Auto-redirect to dashboard
- **Multiple Tenants**: Show selection screen
- **Error**: Show error message, allow retry

**Responsive Behavior**:
- Desktop: 2-column grid for tenant cards
- Mobile: Single column, stacked cards

---

## API Key Management Screen

### UI-AUTH-004: API Key Management Screen

**Screen ID**: UI-AUTH-004  
**Screen Name**: API Keys  
**Purpose**: Create, view, and manage API keys

**Layout**:
```
┌─────────────────────────────────────────┐
│ API Keys                                │
├─────────────────────────────────────────┤
│                                         │
│  [Create New API Key]                   │
│                                         │
│  ┌───────────────────────────────────┐ │
│  │ Active API Keys                   │ │
│  ├───────────────────────────────────┤ │
│  │                                   │ │
│  │ ┌───────────────────────────────┐ │ │
│  │ │ Production Key                │ │ │
│  │ │ •••••••••••••••••••••••••••• │ │ │
│  │ │ Created: Jan 1, 2025          │ │ │
│  │ │ Last used: 2 hours ago        │ │ │
│  │ │ [Show] [Copy] [Revoke]        │ │ │
│  │ └───────────────────────────────┘ │ │
│  │                                   │ │
│  │ ┌───────────────────────────────┐ │ │
│  │ │ Development Key               │ │ │
│  │ │ •••••••••••••••••••••••••••• │ │ │
│  │ │ Created: Dec 15, 2024        │ │ │
│  │ │ Last used: Never             │ │ │
│  │ │ [Show] [Copy] [Revoke]        │ │ │
│  │ └───────────────────────────────┘ │ │
│  │                                   │ │
│  └───────────────────────────────────┘ │
│                                         │
│  ┌───────────────────────────────────┐ │
│  │ Revoked API Keys                  │ │
│  ├───────────────────────────────────┤ │
│  │ [Show revoked keys]               │ │
│  └───────────────────────────────────┘ │
│                                         │
└─────────────────────────────────────────┘
```

**Components**:
- PageHeader (Title, Create button)
- Card (API Key list)
- APIKeyCard (Key details, actions)
- Button (Create New API Key, Show, Copy, Revoke)
- Modal (Create API Key dialog)
- Modal (Revoke confirmation)

**Interactions**:
- Create New API Key: Open modal, enter name, create, show key (one-time)
- Show: Reveal full key (with confirmation)
- Copy: Copy key to clipboard, show success toast
- Revoke: Confirm dialog, revoke key, remove from list
- Key display: Masked by default, show last 4 characters

**Create API Key Modal**:
```
┌─────────────────────────────────────────┐
│ Create API Key                          │
├─────────────────────────────────────────┤
│                                         │
│  Key Name *                             │
│  [_____________________________]        │
│  e.g., "Production Key", "CI/CD Key"    │
│                                         │
│  Expiration (optional)                   │
│  [Never expires ▼]                      │
│  or                                     │
│  [Expires on: [Date Picker]]            │
│                                         │
│  Permissions                            │
│  ☑ Read                                 │
│  ☑ Write                                │
│  ☐ Admin                                │
│                                         │
│  ⚠️ Important: Copy this key now.      │
│  You won't be able to see it again.    │
│                                         │
│  ┌───────────────────────────────────┐ │
│  │ api_key_abc123xyz789...          │ │
│  │ [Copy]                            │ │
│  └───────────────────────────────────┘ │
│                                         │
│  [Done]                                 │
│                                         │
└─────────────────────────────────────────┘
```

**States**:
- **Loading**: Show skeleton loaders
- **Empty**: Show empty state with CTA
- **Creating**: Show loading in modal
- **Created**: Show key (one-time), copy button
- **Revoking**: Show confirmation dialog
- **Revoked**: Remove from active list

**Security Considerations**:
- Keys masked by default
- Show requires confirmation
- Copy shows success feedback
- Revoke requires confirmation
- One-time key display on creation
- Expiration date support

---

## Permission Denied Screens

### UI-AUTH-005: Permission Denied Screen

**Screen ID**: UI-AUTH-005  
**Screen Name**: Access Denied  
**Purpose**: Inform user they don't have permission to access resource

**Layout**:
```
┌─────────────────────────────────────────┐
│                                         │
│              🔒                          │
│                                         │
│         Access Denied                  │
│                                         │
│  You don't have permission to access    │
│  this resource.                         │
│                                         │
│  Required Permission:                   │
│  • {permission_name}                    │
│                                         │
│  Your Role: {user_role}                 │
│                                         │
│  [Request Access]  [Go Back]            │
│                                         │
└─────────────────────────────────────────┘
```

**Components**:
- Icon (Lock icon)
- Heading (Access Denied)
- Text (Permission message)
- PermissionList (Required permissions)
- UserRoleBadge (Current role)
- Button (Request Access, Go Back)

**Interactions**:
- Request Access: Open access request form
- Go Back: Navigate to previous page or dashboard

**Variations**:
- **403 Forbidden**: User authenticated but lacks permission
- **401 Unauthorized**: User not authenticated (redirect to login)
- **Tenant Mismatch**: User from different tenant

---

## Password Reset Flow

### UI-AUTH-006: Password Reset Request

**Screen ID**: UI-AUTH-006  
**Screen Name**: Forgot Password  
**Purpose**: Request password reset email

**Layout**:
```
┌─────────────────────────────────────────┐
│              [Logo]                     │
│                                         │
│  ┌───────────────────────────────────┐ │
│  │ Reset Password                    │ │
│  ├───────────────────────────────────┤ │
│  │                                   │ │
│  │ Enter your email address and we'll│ │
│  │ send you a link to reset your     │ │
│  │ password.                         │ │
│  │                                   │ │
│  │ Email Address *                   │ │
│  │ [_____________________________]   │ │
│  │                                   │ │
│  │ [Send Reset Link]                 │ │
│  │                                   │ │
│  │ [Back to Sign In]                 │ │
│  │                                   │ │
│  └───────────────────────────────────┘ │
│                                         │
└─────────────────────────────────────────┘
```

### UI-AUTH-007: Password Reset Confirmation

**Screen ID**: UI-AUTH-007  
**Screen Name**: Reset Password  
**Purpose**: Set new password using reset token

**Layout**:
```
┌─────────────────────────────────────────┐
│              [Logo]                     │
│                                         │
│  ┌───────────────────────────────────┐ │
│  │ Set New Password                  │ │
│  ├───────────────────────────────────┤ │
│  │                                   │ │
│  │ New Password *                     │ │
│  │ [_____________________________] 🔒 │ │
│  │ • 8+ characters                   │ │
│  │ • 1 uppercase letter               │ │
│  │ • 1 number                         │ │
│  │                                   │ │
│  │ Confirm New Password *             │ │
│  │ [_____________________________] 🔒 │ │
│  │                                   │ │
│  │ [Reset Password]                  │ │
│  │                                   │ │
│  └───────────────────────────────────┘ │
│                                         │
└─────────────────────────────────────────┘
```

**Interactions**:
- Email input: Validate email format
- Send Reset Link: Submit, show success message
- Reset Password: Validate passwords match, submit
- Success: Redirect to login with success message

**States**:
- **Email Sent**: Show confirmation message
- **Token Invalid**: Show error, allow resend
- **Password Reset**: Show success, redirect to login

---

## Multi-Factor Authentication

### UI-AUTH-008: MFA Setup Screen

**Screen ID**: UI-AUTH-008  
**Screen Name**: Enable Two-Factor Authentication  
**Purpose**: Set up MFA for account

**Layout**:
```
┌─────────────────────────────────────────┐
│ Enable Two-Factor Authentication        │
├─────────────────────────────────────────┤
│                                         │
│  Step 1: Scan QR Code                   │
│                                         │
│  ┌───────────────────────────────────┐ │
│  │                                   │ │
│  │        [QR Code Image]            │ │
│  │                                   │ │
│  └───────────────────────────────────┘ │
│                                         │
│  Scan this QR code with your           │
│  authenticator app (Google Authenticator│
│  Authy, Microsoft Authenticator, etc.)  │
│                                         │
│  Step 2: Enter Verification Code       │
│                                         │
│  [______]                               │
│                                         │
│  [Enable 2FA]                           │
│                                         │
│  [Skip for now]                        │
│                                         │
└─────────────────────────────────────────┘
```

### UI-AUTH-009: MFA Verification Screen

**Screen ID**: UI-AUTH-009  
**Screen Name**: Two-Factor Authentication  
**Purpose**: Verify MFA code during login

**Layout**:
```
┌─────────────────────────────────────────┐
│              [Logo]                     │
│                                         │
│  ┌───────────────────────────────────┐ │
│  │ Two-Factor Authentication         │ │
│  ├───────────────────────────────────┤ │
│  │                                   │ │
│  │ Enter the 6-digit code from your  │ │
│  │ authenticator app.                │ │
│  │                                   │ │
│  │ [______]                          │ │
│  │                                   │ │
│  │ [Verify]                          │ │
│  │                                   │ │
│  │ [Use backup code]                 │ │
│  │                                   │ │
│  │ [Resend code]                     │ │
│  │                                   │ │
│  └───────────────────────────────────┘ │
│                                         │
└─────────────────────────────────────────┘
```

**Interactions**:
- QR Code: Display QR code for authenticator app
- Verification Code: 6-digit code input
- Verify: Validate code, complete setup/login
- Backup Code: Show backup codes, allow use
- Resend: Resend code (if SMS-based)

---

## SSO Integration

### UI-AUTH-010: SSO Login Screen

**Screen ID**: UI-AUTH-010  
**Screen Name**: Sign in with SSO  
**Purpose**: Authenticate via SSO provider

**Layout**:
```
┌─────────────────────────────────────────┐
│              [Logo]                     │
│                                         │
│  ┌───────────────────────────────────┐ │
│  │ Sign in with SSO                  │ │
│  ├───────────────────────────────────┤ │
│  │                                   │ │
│  │ Select your organization:         │ │
│  │                                   │ │
│  │ ┌─────────────────────────────┐  │ │
│  │ │ [Logo] Acme Corporation     │  │ │
│  │ │ Sign in with Acme SSO        │  │ │
│  │ └─────────────────────────────┘  │ │
│  │                                   │ │
│  │ ┌─────────────────────────────┐  │ │
│  │ │ [Logo] Data Solutions Inc.   │  │ │
│  │ │ Sign in with Data Solutions │  │ │
│  │ └─────────────────────────────┘  │ │
│  │                                   │ │
│  │ [Back to Email Login]             │ │
│  │                                   │ │
│  └───────────────────────────────────┘ │
│                                         │
└─────────────────────────────────────────┘
```

**Interactions**:
- SSO Provider Selection: Show available SSO providers
- Sign in with SSO: Redirect to SSO provider
- Back: Return to email/password login
- SSO Callback: Handle OAuth callback, create session

**Supported SSO Providers**:
- OAuth 2.0 (Google, Microsoft, GitHub)
- SAML 2.0 (Enterprise SSO)
- OpenID Connect

---

## Session Management

### Session Timeout Handling

**Components**:
- SessionTimeoutDialog: Warn user before session expires
- SessionExpiredScreen: Inform user session expired

**Session Timeout Dialog**:
```
┌─────────────────────────────────────────┐
│ Session Expiring Soon                    │
├─────────────────────────────────────────┤
│                                         │
│  Your session will expire in 2 minutes. │
│                                         │
│  [Extend Session]  [Sign Out]           │
│                                         │
└─────────────────────────────────────────┘
```

**Interactions**:
- Auto-show: 2 minutes before expiration
- Extend Session: Refresh token, extend session
- Sign Out: Logout user immediately
- Auto-logout: After timeout, redirect to login

### Session Management UI

**Components**:
- ActiveSessionsList: Show active sessions
- SessionCard: Session details (device, location, last active)
- Button (Revoke Session)

**Layout**:
```
┌─────────────────────────────────────────┐
│ Active Sessions                         │
├─────────────────────────────────────────┤
│                                         │
│  ┌───────────────────────────────────┐ │
│  │ Current Session                    │ │
│  │ • Chrome on Windows                │ │
│  │ • IP: 192.168.1.1                  │ │
│  │ • Last active: Now                 │ │
│  │ [This Device]                     │ │
│  └───────────────────────────────────┘ │
│                                         │
│  ┌───────────────────────────────────┐ │
│  │ Mobile Device                      │ │
│  │ • Safari on iOS                    │ │
│  │ • IP: 192.168.1.2                  │ │
│  │ • Last active: 2 hours ago         │ │
│  │ [Revoke]                           │ │
│  └───────────────────────────────────┘ │
│                                         │
└─────────────────────────────────────────┘
```

---

## Accessibility Requirements

All authentication screens must:

1. **Keyboard Navigation**: Full keyboard support
2. **Screen Readers**: All elements properly labeled
3. **Focus Management**: Logical focus order
4. **Error Announcements**: Errors announced to screen readers
5. **Color Contrast**: WCAG AA compliant
6. **Form Labels**: All inputs have associated labels
7. **Error Messages**: Clear, actionable error messages

---

## Security Considerations

1. **Password Requirements**: Enforced client and server-side
2. **Rate Limiting**: Login attempts rate-limited
3. **CSRF Protection**: CSRF tokens for all forms
4. **Secure Storage**: Tokens stored securely (httpOnly cookies preferred)
5. **HTTPS Only**: All authentication over HTTPS
6. **Session Security**: Secure session management
7. **Password Visibility**: Toggle for password visibility
8. **Account Lockout**: Temporary lockout after failed attempts

---

**Last Updated**: 2026-03-22  
**Version**: 1.0.0


---

# Component Library

**Last Updated**: 2026-03-22  
**Version**: 1.0.0

---

## Table of Contents

1. [Overview](#overview)
2. [Component Categories](#component-categories)
3. [Layout Components](#layout-components)
4. [Navigation Components](#navigation-components)
5. [Form Components](#form-components)
6. [Data Display Components](#data-display-components)
7. [Feedback Components](#feedback-components)
8. [Overlay Components](#overlay-components)
9. [Utility Components](#utility-components)
10. [Component Specifications](#component-specifications)

---

## Overview

The Component Library provides a comprehensive catalog of reusable UI components for the Interoperable Data Hub platform. All components follow the design system guidelines and are built for accessibility, consistency, and maintainability.

**Component Principles**:
- **Reusability**: Components are composable and reusable
- **Accessibility**: All components meet WCAG 2.1 AA standards
- **Consistency**: Components follow design system tokens
- **Documentation**: Each component is fully documented
- **Testing**: Components are tested in isolation (Storybook)

---

## Component Categories

### 1. Layout Components
Components for page structure and layout

### 2. Navigation Components
Components for navigation and wayfinding

### 3. Form Components
Components for user input and data entry

### 4. Data Display Components
Components for displaying data and content

### 5. Feedback Components
Components for user feedback and status

### 6. Overlay Components
Components that overlay content (modals, tooltips, etc.)

### 7. Utility Components
Helper components and utilities

---

## Layout Components

### Container

**Purpose**: Wrapper for page content with max-width and padding

**Props**:
- `maxWidth`: 'sm' | 'md' | 'lg' | 'xl' | 'full'
- `padding`: boolean (default: true)
- `children`: ReactNode

**Usage**:
```tsx
<Container maxWidth="lg">
  <PageContent />
</Container>
```

**Specifications**:
- Max widths: sm (600px), md (900px), lg (1200px), xl (1536px)
- Padding: 16px on mobile, 24px on desktop
- Responsive: Adapts to screen size

---

### Grid

**Purpose**: Responsive grid layout system

**Props**:
- `columns`: number (default: 12)
- `spacing`: number (default: 2)
- `children`: ReactNode

**Usage**:
```tsx
<Grid columns={12} spacing={2}>
  <GridItem span={6}>Left Column</GridItem>
  <GridItem span={6}>Right Column</GridItem>
</Grid>
```

**Specifications**:
- 12-column grid system
- Responsive breakpoints
- Consistent spacing

---

### Stack

**Purpose**: Vertical or horizontal stack layout

**Props**:
- `direction`: 'row' | 'column' (default: 'column')
- `spacing`: number (default: 2)
- `alignItems`: 'start' | 'center' | 'end' | 'stretch'
- `justifyContent`: 'start' | 'center' | 'end' | 'space-between'
- `children`: ReactNode

**Usage**:
```tsx
<Stack direction="row" spacing={2}>
  <Button>Action 1</Button>
  <Button>Action 2</Button>
</Stack>
```

---

### Card

**Purpose**: Container for related content

**Props**:
- `elevation`: number (default: 1)
- `padding`: number (default: 4)
- `children`: ReactNode

**Usage**:
```tsx
<Card elevation={2}>
  <CardHeader title="Asset Details" />
  <CardContent>
    <AssetInfo />
  </CardContent>
</Card>
```

**Specifications**:
- Elevation: 1 (default), 2 (hover), 4 (selected)
- Padding: 16px default
- Border radius: 8px

---

## Navigation Components

### Header

**Purpose**: Top navigation bar

**Props**:
- `logo`: ReactNode
- `navigation`: NavigationItem[]
- `userMenu`: ReactNode
- `tenantName`: string

**Usage**:
```tsx
<Header
  logo={<Logo />}
  navigation={navItems}
  userMenu={<UserMenu />}
  tenantName="Acme Corp"
/>
```

**Specifications**:
- Height: 64px
- Sticky: Yes (stays at top on scroll)
- Background: White with shadow
- Responsive: Collapses to hamburger menu on mobile

---

### Sidebar

**Purpose**: Left navigation sidebar

**Props**:
- `items`: NavigationItem[]
- `collapsed`: boolean
- `onToggle`: () => void

**Usage**:
```tsx
<Sidebar
  items={sidebarItems}
  collapsed={false}
  onToggle={handleToggle}
/>
```

**Specifications**:
- Width: 240px (expanded), 64px (collapsed)
- Sticky: Yes
- Icons: Material Icons
- Active state: Highlighted with primary color

---

### Breadcrumbs

**Purpose**: Navigation breadcrumb trail

**Props**:
- `items`: BreadcrumbItem[]
- `separator`: string (default: '/')

**Usage**:
```tsx
<Breadcrumbs
  items={[
    { label: 'Assets', href: '/assets' },
    { label: 'Customer Orders', href: '/assets/123' }
  ]}
/>
```

**Specifications**:
- Font size: 14px
- Color: Gray-700
- Active: Gray-900
- Separator: '/' or custom

---

### Tabs

**Purpose**: Tab navigation

**Props**:
- `tabs`: TabItem[]
- `activeTab`: string
- `onChange`: (tabId: string) => void

**Usage**:
```tsx
<Tabs
  tabs={[
    { id: 'overview', label: 'Overview' },
    { id: 'schema', label: 'Schema' }
  ]}
  activeTab="overview"
  onChange={handleTabChange}
/>
```

**Specifications**:
- Height: 48px
- Active indicator: Primary color underline
- Font: 14px, medium weight

---

## Form Components

### Resource Pickers

Searchable dropdowns for selecting assets, contracts, datasets, and files. See [RESOURCE_PICKERS.md](RESOURCE_PICKERS.md) for full documentation, props, and examples.

- **AssetPicker**, **ContractPicker**, **DatasetPicker**, **FilePicker** — single-select
- **AssetMultiPicker**, **DatasetMultiPicker**, **FileMultiPicker** — multi-select

---

### Text Input

**Purpose**: Single-line text input

**Props**:
- `label`: string
- `value`: string
- `onChange`: (value: string) => void
- `error`: string | null
- `helperText`: string
- `required`: boolean
- `disabled`: boolean
- `placeholder`: string

**Usage**:
```tsx
<TextInput
  label="Asset Name"
  value={name}
  onChange={setName}
  error={errors.name}
  required
/>
```

**Specifications**:
- Height: 56px
- Border: 1px solid gray-300
- Focus: Primary color border
- Error: Red border and text
- Font: 16px (prevents zoom on iOS)

---

### Textarea

**Purpose**: Multi-line text input

**Props**:
- `label`: string
- `value`: string
- `onChange`: (value: string) => void
- `rows`: number (default: 4)
- `error`: string | null
- `helperText`: string

**Usage**:
```tsx
<Textarea
  label="Description"
  value={description}
  onChange={setDescription}
  rows={4}
/>
```

---

### Select

**Purpose**: Dropdown selection

**Props**:
- `label`: string
- `options`: Option[]
- `value`: string | null
- `onChange`: (value: string) => void
- `error`: string | null
- `multiple`: boolean

**Usage**:
```tsx
<Select
  label="Domain"
  options={domains}
  value={selectedDomain}
  onChange={setDomain}
/>
```

**Specifications**:
- Height: 56px
- Dropdown: Max height 300px, scrollable
- Search: Optional search for long lists

---

### Checkbox

**Purpose**: Checkbox input

**Props**:
- `label`: string
- `checked`: boolean
- `onChange`: (checked: boolean) => void
- `disabled`: boolean

**Usage**:
```tsx
<Checkbox
  label="Publish to Marketplace"
  checked={isPublished}
  onChange={setIsPublished}
/>
```

**Specifications**:
- Size: 20px × 20px
- Check color: Primary color
- Border: 2px solid gray-400

---

### Radio Group

**Purpose**: Radio button group

**Props**:
- `label`: string
- `options`: Option[]
- `value`: string | null
- `onChange`: (value: string) => void

**Usage**:
```tsx
<RadioGroup
  label="Onboarding Flow"
  options={flows}
  value={selectedFlow}
  onChange={setFlow}
/>
```

---

### File Upload

**Purpose**: File upload with drag-and-drop

**Props**:
- `accept`: string (file types)
- `maxSize`: number (bytes)
- `onUpload`: (file: File) => void
- `multiple`: boolean

**Usage**:
```tsx
<FileUpload
  accept=".csv,.json,.parquet"
  maxSize={100 * 1024 * 1024}
  onUpload={handleUpload}
/>
```

**Specifications**:
- Dropzone: 200px height, dashed border
- Drag state: Highlighted border
- Progress: Progress bar during upload
- Error: Clear error messages

---

### Button

**Purpose**: Action button

**Props**:
- `variant`: 'primary' | 'secondary' | 'outline' | 'text'
- `size`: 'sm' | 'md' | 'lg'
- `disabled`: boolean
- `loading`: boolean
- `onClick`: () => void
- `children`: ReactNode

**Usage**:
```tsx
<Button
  variant="primary"
  size="md"
  onClick={handleSubmit}
  loading={isSubmitting}
>
  Create Asset
</Button>
```

**Specifications**:
- Heights: sm (32px), md (40px), lg (48px)
- Padding: 12px 24px (md)
- Border radius: 4px
- Focus: Visible focus ring

---

## Data Display Components

### Table

**Purpose**: Data table with sorting and filtering

**Props**:
- `columns`: Column[]
- `data`: Row[]
- `sortable`: boolean
- `filterable`: boolean
- `pagination`: boolean

**Usage**:
```tsx
<Table
  columns={assetColumns}
  data={assets}
  sortable
  filterable
  pagination
/>
```

**Specifications**:
- Row height: 48px
- Header: Sticky, gray background
- Hover: Light gray background
- Selected: Primary color background
- Responsive: Horizontal scroll on mobile

---

### Badge

**Purpose**: Status badge or label

**Props**:
- `variant`: 'success' | 'warning' | 'error' | 'info' | 'neutral'
- `size`: 'sm' | 'md'
- `children`: ReactNode

**Usage**:
```tsx
<Badge variant="success">Active</Badge>
<Badge variant="error">Failed</Badge>
```

**Specifications**:
- Height: 20px (sm), 24px (md)
- Border radius: 12px (pill shape)
- Font: 12px, medium weight
- Colors: Semantic colors

---

### Status Indicator

**Purpose**: Visual status indicator

**Props**:
- `status`: 'success' | 'warning' | 'error' | 'pending' | 'running'
- `label`: string
- `size`: 'sm' | 'md' | 'lg'

**Usage**:
```tsx
<StatusIndicator
  status="running"
  label="Processing"
  size="md"
/>
```

**Specifications**:
- Dot: 8px (sm), 12px (md), 16px (lg)
- Animation: Pulse for running/pending
- Colors: Semantic colors

---

### Progress Bar

**Purpose**: Progress indicator

**Props**:
- `value`: number (0-100)
- `label`: string
- `showValue`: boolean

**Usage**:
```tsx
<ProgressBar
  value={75}
  label="Upload Progress"
  showValue
/>
```

**Specifications**:
- Height: 4px (default), 8px (thick)
- Color: Primary color
- Animation: Smooth transition

---

### Empty State

**Purpose**: Empty state message

**Props**:
- `icon`: ReactNode
- `title`: string
- `description`: string
- `action`: ReactNode

**Usage**:
```tsx
<EmptyState
  icon={<EmptyIcon />}
  title="No Assets Yet"
  description="Create your first asset to get started"
  action={<Button>Create Asset</Button>}
/>
```

---

## Feedback Components

### Alert

**Purpose**: Alert message

**Props**:
- `severity`: 'success' | 'warning' | 'error' | 'info'
- `title`: string
- `message`: string
- `dismissible`: boolean
- `onClose`: () => void

**Usage**:
```tsx
<Alert
  severity="error"
  title="Upload Failed"
  message="File size exceeds maximum limit"
  dismissible
  onClose={handleClose}
/>
```

**Specifications**:
- Padding: 16px
- Border: Left border (4px) in severity color
- Icon: Severity-specific icon
- Animation: Slide in from top

---

### Toast

**Purpose**: Toast notification

**Props**:
- `message`: string
- `severity`: 'success' | 'warning' | 'error' | 'info'
- `duration`: number (ms, default: 5000)

**Usage**:
```tsx
toast.success('Asset created successfully');
toast.error('Upload failed');
```

**Specifications**:
- Position: Top-right (default)
- Duration: 5 seconds (default)
- Animation: Slide in/out
- Stack: Multiple toasts stack vertically

---

### Loading Spinner

**Purpose**: Loading indicator

**Props**:
- `size`: 'sm' | 'md' | 'lg'
- `color`: 'primary' | 'white'

**Usage**:
```tsx
<LoadingSpinner size="md" color="primary" />
```

**Specifications**:
- Size: 20px (sm), 32px (md), 48px (lg)
- Animation: Rotate 360deg
- Color: Primary or white

---

## Overlay Components

### Modal

**Purpose**: Modal dialog

**Props**:
- `open`: boolean
- `onClose`: () => void
- `title`: string
- `children`: ReactNode
- `actions`: ReactNode
- `size`: 'sm' | 'md' | 'lg' | 'xl'

**Usage**:
```tsx
<Modal
  open={isOpen}
  onClose={handleClose}
  title="Confirm Delete"
  size="md"
  actions={
    <>
      <Button onClick={handleClose}>Cancel</Button>
      <Button variant="primary" onClick={handleDelete}>Delete</Button>
    </>
  }
>
  <p>Are you sure you want to delete this asset?</p>
</Modal>
```

**Specifications**:
- Backdrop: Dark overlay (rgba(0,0,0,0.5))
- Max width: sm (400px), md (600px), lg (900px), xl (1200px)
- Animation: Fade in + scale up
- Focus trap: Yes
- ESC to close: Yes

---

### Tooltip

**Purpose**: Tooltip on hover

**Props**:
- `content`: string | ReactNode
- `placement`: 'top' | 'bottom' | 'left' | 'right'
- `children`: ReactNode

**Usage**:
```tsx
<Tooltip content="This field is required" placement="top">
  <IconButton icon={<HelpIcon />} />
</Tooltip>
```

**Specifications**:
- Background: Gray-900
- Text: White
- Font: 12px
- Arrow: Points to trigger element
- Delay: 200ms before showing

---

### Dropdown Menu

**Purpose**: Dropdown menu

**Props**:
- `trigger`: ReactNode
- `items`: MenuItem[]
- `placement`: 'bottom-start' | 'bottom-end' | 'top-start' | 'top-end'

**Usage**:
```tsx
<DropdownMenu
  trigger={<Button>Actions</Button>}
  items={[
    { label: 'Edit', onClick: handleEdit },
    { label: 'Delete', onClick: handleDelete }
  ]}
/>
```

**Specifications**:
- Min width: 200px
- Max height: 300px (scrollable)
- Elevation: 8
- Animation: Fade in + slide

---

## Utility Components

### Avatar

**Purpose**: User avatar

**Props**:
- `src`: string (image URL)
- `alt`: string
- `size`: 'sm' | 'md' | 'lg'
- `initials`: string

**Usage**:
```tsx
<Avatar
  src={user.avatar}
  alt={user.name}
  size="md"
  initials="JD"
/>
```

**Specifications**:
- Size: 32px (sm), 40px (md), 48px (lg)
- Border radius: 50% (circle)
- Fallback: Initials or default icon

---

### Divider

**Purpose**: Visual divider

**Props**:
- `orientation`: 'horizontal' | 'vertical'
- `spacing`: number

**Usage**:
```tsx
<Divider orientation="horizontal" spacing={2} />
```

**Specifications**:
- Height/Width: 1px
- Color: Gray-200
- Spacing: 16px default

---

### Skeleton

**Purpose**: Loading skeleton

**Props**:
- `variant`: 'text' | 'circular' | 'rectangular'
- `width`: number | string
- `height`: number | string

**Usage**:
```tsx
<Skeleton variant="text" width="100%" height={20} />
<Skeleton variant="rectangular" width={200} height={100} />
```

**Specifications**:
- Animation: Pulse
- Color: Gray-200 background, gray-100 shimmer

---

## Component Specifications

### Component Structure

All components follow this structure:

```
ComponentName/
  ├── ComponentName.tsx       # Main component
  ├── ComponentName.test.tsx  # Tests
  ├── ComponentName.stories.tsx # Storybook stories
  └── index.ts                # Exports
```

### Component Props

- All props are typed with TypeScript
- Required props are clearly marked
- Default values are provided where appropriate
- Props are documented with JSDoc comments

### Component States

Components support these states:
- **Default**: Normal state
- **Hover**: Mouse hover
- **Focus**: Keyboard focus
- **Active**: Being pressed/clicked
- **Disabled**: Disabled state
- **Loading**: Loading state
- **Error**: Error state

### Accessibility

All components include:
- ARIA labels and roles
- Keyboard navigation
- Focus management
- Screen reader support
- Color contrast compliance

---

**Last Updated**: 2026-03-22  
**Version**: 1.0.0


---

# Contract Editor Specification

**Last Updated**: 2026-03-22  
**Version**: 1.0.0

---

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Component Specifications](#component-specifications)
4. [HubContract Structure](#hubcontract-structure)
5. [Editor Modes](#editor-modes)
6. [Integration Points](#integration-points)
7. [Implementation Plan](#implementation-plan)
8. [Technical Specifications](#technical-specifications)
9. [User Flows](#user-flows)
10. [Accessibility](#accessibility)

---

## Overview

The Contract Editor is a comprehensive, custom-built editor for creating and managing data contracts in the Interoperable Data Hub platform. It supports multiple editing modes, real-time validation, and HubContract-specific features that go beyond standard ODCS/DataContract.com specifications.

**Key Principles**:
- **HubContract-First**: Designed specifically for HubContract format with all sections
- **Multi-Mode Editing**: Form, YAML, and Visual editing modes
- **Real-Time Validation**: Instant feedback on contract validity
- **Normalization Integration**: Seamless integration with normalization pipeline
- **Schema-Aware**: Intelligent editing with schema inference and comparison

**Target Personas**: Data Product Owner, Data Engineer

---

## Architecture

### High-Level Architecture

```
ContractEditor (Main Container)
├── EditorHeader
│   ├── ContractMetadata
│   ├── StatusBadges (Normalization, Validation)
│   └── ActionButtons (Save, Validate, Activate)
├── EditorTabs
│   ├── OverviewTab
│   ├── SchemaTab
│   ├── QualityTab
│   ├── ComplianceTab
│   ├── LifecycleTab
│   ├── MarketplaceTab
│   └── RawEditorTab
├── ValidationPanel
│   ├── ValidationStatus
│   ├── ErrorList
│   └── WarningList
└── SchemaComparison (Contract-First Flow)
    ├── InferredSchema
    ├── ContractSchema
    └── DiffView
```

### Component Hierarchy

```
ContractEditor
  ├── EditorLayout (Grid/Stack)
  │   ├── EditorHeader
  │   ├── EditorContent
  │   │   ├── TabNavigation
  │   │   └── TabContent
  │   │       ├── OverviewSection
  │   │       ├── SchemaSection
  │   │       ├── QualitySection
  │   │       ├── ComplianceSection
  │   │       ├── LifecycleSection
  │   │       ├── MarketplaceSection
  │   │       └── RawEditorSection
  │   └── EditorFooter
  │       ├── ValidationPanel
  │       └── ActionBar
  └── SchemaComparison (Conditional - Contract-First)
```

---

## Component Specifications

### ContractEditor (Main Component)

**Purpose**: Main container for contract editing

**Props**:
```typescript
interface ContractEditorProps {
  contractId?: string;              // Existing contract ID (for edit mode)
  assetId?: string;                  // Asset ID (for new contract)
  initialContract?: HubContract;    // Initial contract data
  mode?: 'create' | 'edit';         // Editor mode
  onboardingFlow?: 'data-first' | 'contract-first' | 'contract-only';
  inferredSchema?: SchemaField[];    // Inferred schema (data-first flow)
  onSave: (contract: HubContract) => Promise<void>;
  onValidate: (contract: HubContract) => Promise<ValidationResult>;
  onCancel: () => void;
}
```

**State**:
```typescript
interface ContractEditorState {
  contract: HubContract;              // Current contract data
  activeTab: string;                 // Active tab ID
  validationStatus: ValidationStatus;
  normalizationStatus: NormalizationStatus;
  isDirty: boolean;                  // Has unsaved changes
  isSaving: boolean;
  isValidating: boolean;
  errors: ValidationError[];
  warnings: ValidationWarning[];
  schemaComparison?: SchemaComparison; // For contract-first flow
}
```

**Behavior**:
- Auto-save draft every 30 seconds
- Real-time validation on field changes
- Show normalization status
- Handle tab navigation
- Manage editor state

---

### EditorHeader

**Purpose**: Display contract metadata and status

**Components**:
- Contract name and description
- Normalization status badge
- Validation status badge
- Action buttons (Save, Validate, Activate)

**Specifications**:
- Height: 80px
- Sticky on scroll
- Background: White with shadow
- Status badges: Color-coded (green/yellow/red)

---

### OverviewSection

**Purpose**: Edit contract overview information

**Fields**:
- **Name** (required): TextInput
- **Description**: Textarea
- **Version**: TextInput (auto-incremented)
- **Owners**: Array of Owner objects
  - Name: TextInput
  - Email: EmailInput
  - Add/Remove buttons
- **Tags**: TagInput (multi-select with autocomplete)
- **Domain**: Select (dropdown with common domains)

**Layout**:
- Single column on mobile
- Two columns on desktop
- Form validation on blur

---

### SchemaSection

**Purpose**: Edit contract schema fields

**Features**:
- **Field Table**: Editable table with all field properties
- **Field Editor**: Modal/drawer for detailed field editing
- **Schema Inference Integration**: Show inferred fields (data-first flow)
- **Field Comparison**: Highlight differences (contract-first flow)

**Field Properties**:
- Name (required)
- Data Type (required)
- Nullable (checkbox)
- Description
- Semantic Type (select)
- Format (text input)
- Pattern (regex input)
- Enum (array input)
- Default Value
- Min/Max Length
- Min/Max Numeric
- Metadata (JSON editor)

**Schema Constraints**:
- Primary Key (single field)
- Unique Constraints (array of field arrays)
- Indexes (array of field arrays)

**Layout**:
- Table view with inline editing
- Expandable rows for field details
- Bulk operations (add/remove fields)
- Import/Export schema

---

### QualitySection

**Purpose**: Edit data quality rules (HubContract-specific)

**Features**:
- **Default Profile**: Select (intake_basic, custom)
- **Quality Rules Table**: List of quality rules
- **Rule Editor**: Modal for creating/editing rules

**Rule Properties**:
- Rule ID (required)
- Name (required)
- Dimension (select: completeness, validity, uniqueness, consistency, accuracy, timeliness)
- Expression (SQL/expression)
- Severity (select: ERROR, WARNING, INFO)
- Target Level (select: COLUMN, TABLE, DATASET)
- Target Column (text, if column-level)
- Target Pattern (regex, if pattern-based)
- Parameters (JSON editor)

**Layout**:
- Rules table with inline editing
- Rule editor modal
- Rule templates (pre-defined rules)
- Rule validation

---

### ComplianceSection

**Purpose**: Edit compliance policy (HubContract-specific)

**Features**:
- **Contains Personal Data**: Checkbox
- **Personal Data Categories**: Multi-select (EMAIL, PHONE, NAME, ADDRESS, etc.)
- **Jurisdictions**: Multi-select (GDPR, LGPD, CCPA, HIPAA, SOX)
- **Legal Bases**: Multi-select (CONSENT, CONTRACT, LEGAL_OBLIGATION, etc.)
- **Retention Policy**:
  - Period (duration input: P5Y, P1Y, etc.)
  - Notes (textarea)

**Layout**:
- Form with sections
- Checkbox groups for multi-selects
- Duration picker for retention
- Compliance risk indicator

---

### LifecycleSection

**Purpose**: Edit lifecycle policy (HubContract-specific)

**Features**:
- **Data Source**: TextInput (e.g., "OLTP.orders")
- **Refresh Cadence**: Select (REAL_TIME, HOURLY, DAILY, WEEKLY, MONTHLY, ON_DEMAND)
- **SLAs**:
  - Availability (percentage input: 99.0)
  - Latency P95 (milliseconds input: 5000)

**Layout**:
- Simple form layout
- SLA visualization (charts/graphs)

---

### MarketplaceSection

**Purpose**: Edit marketplace policy (HubContract-specific)

**Features**:
- **License Summary**: TextInput
- **Intended Use**: Multi-select (analytics, machine_learning, reporting, etc.)
- **Restricted Use**: Multi-select (resale, competitive_analysis, etc.)

**Layout**:
- Form with multi-select inputs
- Use case templates

---

### RawEditorSection

**Purpose**: Edit contract in raw YAML/JSON format

**Features**:
- **Editor Mode Toggle**: YAML / JSON
- **Syntax Highlighting**: Monaco Editor or CodeMirror
- **Code Completion**: HubContract schema-aware
- **Error Highlighting**: Real-time error markers
- **Format Toggle**: Switch between YAML and JSON
- **Validation Feedback**: Inline error messages

**Layout**:
- Full-width editor
- Line numbers
- Minimap (optional)
- Format toolbar

**Editor Library Options**:
1. **Monaco Editor** (VS Code editor)
   - Pros: Excellent syntax highlighting, IntelliSense, familiar UX
   - Cons: Larger bundle size
2. **CodeMirror 6**
   - Pros: Lightweight, modular, good performance
   - Cons: Less feature-rich than Monaco

**Recommendation**: Monaco Editor for better UX and code completion

---

### ValidationPanel

**Purpose**: Display validation and normalization status

**Components**:
- **Normalization Status Badge**:
  - NORMALIZED_OK (green)
  - NORMALIZED_WITH_WARNINGS (yellow)
  - NORMALIZATION_FAILED (red)
- **Validation Status Badge**:
  - VALID (green)
  - INVALID (red)
  - WARNING_ONLY (yellow)
  - PENDING (gray)
- **Error List**: Grouped by category
  - Syntax errors
  - Required field errors
  - Spec compatibility errors
- **Warning List**: Grouped by severity
- **Validation Actions**:
  - Run Validation button
  - Last validated timestamp
  - CLI version

**Layout**:
- Fixed bottom panel or sidebar
- Expandable error/warning lists
- Clickable errors (jump to field)

---

### SchemaComparison (Contract-First Flow)

**Purpose**: Compare inferred schema with contract schema

**Features**:
- **Side-by-Side Comparison**:
  - Left: Inferred Schema (from data)
  - Right: Contract Schema
- **Diff Highlighting**:
  - Green: Matching fields
  - Yellow: Type mismatches
  - Red: Missing/extra fields
- **Field Details**:
  - Show differences in properties
  - Type mismatches
  - Missing fields
- **Actions**:
  - Accept inferred schema
  - Keep contract schema
  - Merge schemas
  - Resolve conflicts manually

**Layout**:
- Two-column layout
- Diff view with highlighting
- Action buttons for resolution

---

## HubContract Structure

### Complete HubContract v1.0 Structure

```typescript
interface HubContract {
  hub_contract_version: number;      // 1
  id: string;                         // Contract identifier
  info: {
    name: string;                     // Required
    description?: string;
    version?: string;
    owners?: Owner[];                 // Array of {name, email}
    tags?: string[];                  // Array of tags
    domain?: string;
    status?: string;
    dataProduct?: string;
    links?: Link[];                   // Array of {rel, href}
    authoritativeDefinitions?: string[];
  };
  schema: {
    fields: SchemaField[];            // Required
    primary_key?: string[];
    unique_constraints?: string[][];
    indexes?: string[][];
  };
  quality: {
    default_profile_key?: string;     // e.g., "intake_basic"
    rules?: QualityRule[];             // Array of quality rules
  };
  privacy_compliance: {
    contains_personal_data?: boolean;
    personal_data_categories?: string[];
    jurisdictions?: string[];
    legal_bases?: string[];
    retention_policy?: {
      period?: string;                // ISO 8601 duration
      notes?: string;
    };
  };
  lifecycle: {
    data_source?: string;
    refresh_cadence?: string;
    slas?: {
      availability?: number;          // Percentage
      latency_ms_p95?: number;        // Milliseconds
    };
  };
  marketplace: {
    license_summary?: string;
    intended_use?: string[];
    restricted_use?: string[];
  };
  extensions?: {
    odcs?: Record<string, any>;
    datacontract_com?: Record<string, any>;
    [key: string]: any;
  };
}
```

### SchemaField Structure

```typescript
interface SchemaField {
  name: string;                       // Required
  data_type: string;                  // Required (string, integer, float, boolean, date, timestamp, array, object)
  nullable?: boolean;
  description?: string;
  semantic_type?: string;             // e.g., EMAIL, PHONE, ORDER_ID
  format?: string;                    // e.g., email, uri, date-time
  pattern?: string;                   // Regex pattern
  enum?: any[];                       // Array of allowed values
  default?: any;                      // Default value
  min_length?: number;
  max_length?: number;
  minimum?: number;
  maximum?: number;
  metadata?: Record<string, any>;     // Custom metadata
  is_primary_key?: boolean;
  is_unique?: boolean;
  is_indexed?: boolean;
}
```

### QualityRule Structure

```typescript
interface QualityRule {
  rule_id: string;                    // Required
  name: string;                       // Required
  dimension: string;                  // completeness, validity, uniqueness, consistency, accuracy, timeliness
  expression?: string;                // SQL expression or rule definition
  severity: string;                   // ERROR, WARNING, INFO
  target_level?: string;              // COLUMN, TABLE, DATASET
  target_column?: string;
  target_pattern?: string;
  params?: Record<string, any>;       // Rule-specific parameters
}
```

---

## Editor Modes

### Mode 1: Form Editor (Default)

**Purpose**: Guided editing with forms for each section

**Features**:
- Tab-based navigation
- Form inputs for each field
- Inline validation
- Help text and tooltips
- Progressive disclosure

**Use Case**: Primary editing mode for most users

---

### Mode 2: YAML/JSON Editor

**Purpose**: Direct editing of contract in YAML or JSON format

**Features**:
- Syntax highlighting
- Code completion (HubContract schema-aware)
- Error highlighting
- Format conversion (YAML ↔ JSON)
- Validation feedback

**Use Case**: Advanced users, quick edits, bulk changes

---

### Mode 3: Visual Editor (Future)

**Purpose**: Visual representation of contract structure

**Features**:
- Drag-and-drop field organization
- Visual schema representation
- Relationship visualization
- Flow-based editing

**Use Case**: Non-technical users, visual learners

---

## Integration Points

### API Integration

**Endpoints**:
```typescript
// Get contract
GET /api/v1/contracts/{id}/

// Update contract
PATCH /api/v1/contracts/{id}/

// Validate contract
POST /api/v1/contracts/{id}/validate/

// Normalize contract (automatic on save)
// Triggered by PATCH with original_raw

// Get inferred schema (data-first flow)
GET /api/v1/datasets/{id}/schema/
```

### Real-Time Validation

**Flow**:
1. User edits contract
2. Debounce (500ms)
3. Call validation API
4. Update validation panel
5. Highlight errors in editor

**Implementation**:
```typescript
const useContractValidation = (contractId: string) => {
  const [validationResult, setValidationResult] = useState<ValidationResult | null>(null);
  
  const validate = useCallback(
    debounce(async (contract: HubContract) => {
      const result = await api.post(`/contracts/${contractId}/validate/`, {
        contract
      });
      setValidationResult(result);
    }, 500),
    [contractId]
  );
  
  return { validate, validationResult };
};
```

### Normalization Integration

**Flow**:
1. User saves contract (original_raw)
2. Backend normalizes to HubContract
3. Frontend receives normalized contract
4. Update editor with normalized data
5. Show normalization status

**Status Display**:
- NORMALIZED_OK: Green badge, allow activation
- NORMALIZED_WITH_WARNINGS: Yellow badge, show warnings, allow activation
- NORMALIZATION_FAILED: Red badge, show errors, block activation

---

## Implementation Plan

### Phase 1: Core Editor (Weeks 1-2)

**Deliverables**:
- ContractEditor main component
- EditorHeader with status badges
- Basic tab navigation
- OverviewSection (form)
- RawEditorSection (Monaco Editor)
- ValidationPanel (basic)

**Dependencies**:
- Monaco Editor setup
- API client setup
- Design system components

---

### Phase 2: Schema Editor (Weeks 3-4)

**Deliverables**:
- SchemaSection with field table
- Field editor modal
- Schema constraints editor
- Schema import/export

**Dependencies**:
- Table component
- Modal component
- Form components

---

### Phase 3: HubContract-Specific Sections (Weeks 5-6)

**Deliverables**:
- QualitySection (rules editor)
- ComplianceSection (policy editor)
- LifecycleSection (policy editor)
- MarketplaceSection (policy editor)

**Dependencies**:
- All form components
- Multi-select components
- JSON editor for complex fields

---

### Phase 4: Advanced Features (Weeks 7-8)

**Deliverables**:
- Schema comparison (contract-first flow)
- Real-time validation
- Auto-save draft
- Code completion for HubContract
- Advanced error handling

**Dependencies**:
- Validation API integration
- Monaco Editor IntelliSense setup
- Local storage for drafts

---

### Phase 5: Polish & Testing (Weeks 9-10)

**Deliverables**:
- Accessibility improvements
- Performance optimization
- Error handling
- User testing
- Documentation

**Dependencies**:
- Accessibility audit
- Performance profiling
- User feedback

---

## Technical Specifications

### Technology Stack

**Editor Core**:
- React 18+ with TypeScript
- Monaco Editor (VS Code editor)
- React Hook Form (form management)
- Zod (schema validation)

**State Management**:
- React Query (server state)
- Zustand or Context API (client state)

**Styling**:
- Material-UI or custom design system
- CSS-in-JS (Emotion) or Tailwind CSS

**Validation**:
- HubContract JSON Schema (for validation)
- Real-time API validation

### Performance Considerations

**Optimization Strategies**:
- Lazy load editor tabs
- Debounce validation calls
- Virtual scrolling for large field lists
- Memoize expensive computations
- Code splitting for editor modes

**Bundle Size**:
- Monaco Editor: ~2MB (can be loaded on demand)
- Total editor bundle: Target <500KB (excluding Monaco)

### Accessibility

**Requirements**:
- Keyboard navigation for all interactions
- Screen reader support
- ARIA labels for all components
- Focus management
- Error announcements

**Implementation**:
- Use semantic HTML
- Proper ARIA roles and labels
- Keyboard shortcuts
- Focus traps in modals

---

## User Flows

### Flow 1: Create Contract (Contract-First)

1. User navigates to "Create Contract"
2. Upload contract file or paste YAML/JSON
3. Editor loads with contract data
4. User reviews/edits in Form Editor
5. User clicks "Validate"
6. Validation runs, shows results
7. If valid, user clicks "Save & Activate"
8. Contract saved and activated

---

### Flow 2: Edit Contract (Data-First)

1. User completes data upload and analysis
2. Editor opens with pre-filled contract (from inferred schema)
3. User edits schema fields
4. User adds quality rules, compliance policy
5. User clicks "Validate"
6. If valid, user clicks "Save & Activate"
7. Contract saved and asset activated

---

### Flow 3: Schema Comparison (Contract-First)

1. User uploads contract
2. User uploads data file
3. Schema comparison view appears
4. User reviews differences
5. User accepts inferred schema or keeps contract schema
6. User resolves conflicts
7. Editor updates with merged schema
8. User continues editing

---

## Accessibility

### Keyboard Navigation

**Shortcuts**:
- `Ctrl/Cmd + S`: Save contract
- `Ctrl/Cmd + Enter`: Validate contract
- `Tab`: Navigate between fields
- `Esc`: Close modals/drawers
- `Ctrl/Cmd + /`: Show keyboard shortcuts

### Screen Reader Support

**Announcements**:
- Validation status changes
- Normalization status changes
- Field errors
- Save success/failure
- Tab changes

**ARIA Labels**:
- All form fields have labels
- Status badges have descriptions
- Error messages are announced
- Tab panels are properly labeled

---

## Testing Strategy

### Unit Tests

- Component rendering
- Form validation
- State management
- API integration mocks

### Integration Tests

- Editor workflows
- Validation flow
- Save flow
- Schema comparison

### E2E Tests

- Complete contract creation flow
- Contract editing flow
- Validation workflow
- Schema comparison workflow

---

## Future Enhancements

### Phase 6+ (Post-MVP)

1. **Visual Editor Mode**
   - Drag-and-drop schema builder
   - Visual relationship mapping

2. **Template System**
   - Contract templates
   - Field templates
   - Rule templates

3. **Collaboration Features**
   - Real-time collaborative editing
   - Comments and annotations
   - Change tracking

4. **Advanced Validation**
   - Custom validation rules
   - Validation rule builder
   - Validation history

5. **Import/Export**
   - Export to ODCS/DataContract.com
   - Import from external sources
   - Bulk import/export

---

**Last Updated**: 2026-03-22  
**Version**: 1.0.0



---

# Frontend Deployment Guide

**Last Updated**: 2026-03-22  
**Version**: 1.0.0

---

## Table of Contents

1. [Overview](#overview)
2. [Build Configuration](#build-configuration)
3. [Environment Configuration](#environment-configuration)
4. [CDN Strategy](#cdn-strategy)
5. [Docker Deployment](#docker-deployment)
6. [Kubernetes Deployment](#kubernetes-deployment)
7. [CI/CD Pipeline](#cicd-pipeline)
8. [Version Management](#version-management)
9. [Feature Flags](#feature-flags)
10. [Rollback Strategy](#rollback-strategy)

---

## Overview

This document describes the deployment strategy for the frontend application. The application is deployed to multiple environments (development, staging, production) using containerization and orchestration.

**Deployment Environments**:
- **Development**: Local development server
- **Staging**: Staging environment for testing
- **Production**: Production environment for end users

**Deployment Methods**:
- Docker containers
- Kubernetes orchestration
- CDN for static assets
- CI/CD pipelines

---

## Build Configuration

### Vite Build Configuration

**File**: `vite.config.ts`

```typescript
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { visualizer } from 'rollup-plugin-visualizer';

export default defineConfig(({ mode }) => {
  const isProduction = mode === 'production';

  return {
    plugins: [
      react(),
      visualizer({
        open: false,
        filename: 'dist/stats.html',
      }),
    ],
    build: {
      outDir: 'dist',
      sourcemap: isProduction ? false : true,
      minify: isProduction ? 'terser' : false,
      terserOptions: {
        compress: {
          drop_console: isProduction,
          drop_debugger: isProduction,
        },
      },
      rollupOptions: {
        output: {
          manualChunks: {
            'react-vendor': ['react', 'react-dom', 'react-router-dom'],
            'mui-vendor': ['@mui/material', '@mui/icons-material'],
            'query-vendor': ['@tanstack/react-query'],
          },
        },
      },
      chunkSizeWarningLimit: 1000,
    },
    server: {
      port: 3000,
      proxy: {
        '/api': {
          target: 'http://localhost:8000',
          changeOrigin: true,
        },
        '/ws': {
          target: 'ws://localhost:8000',
          ws: true,
        },
      },
    },
  };
});
```

### Build Scripts

**File**: `package.json`

```json
{
  "scripts": {
    "build": "vite build",
    "build:staging": "vite build --mode staging",
    "build:production": "vite build --mode production",
    "preview": "vite preview",
    "analyze": "vite build --mode production && open dist/stats.html"
  }
}
```

---

## Environment Configuration

### Environment Variables

**File**: `.env.example`

```bash
# API Configuration
VITE_API_BASE_URL=http://localhost:8000
VITE_WS_URL=ws://localhost:8000
VITE_GRAPHQL_URL=http://localhost:8000/graphql

# Analytics
VITE_GA_ID=G-XXXXXXXXXX
VITE_SENTRY_DSN=https://xxx@sentry.io/xxx
VITE_ENABLE_ANALYTICS=false

# Feature Flags
VITE_ENABLE_MARKETPLACE=true
VITE_ENABLE_COMPLIANCE=true

# Environment
VITE_ENV=development
```

### Environment-Specific Files

- `.env.development` - Development environment
- `.env.staging` - Staging environment
- `.env.production` - Production environment

### Environment Variable Loading

**File**: `src/lib/config.ts`

```typescript
export const config = {
  api: {
    baseUrl: import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000',
    wsUrl: import.meta.env.VITE_WS_URL || 'ws://localhost:8000',
    graphqlUrl: import.meta.env.VITE_GRAPHQL_URL || 'http://localhost:8000/graphql',
  },
  analytics: {
    gaId: import.meta.env.VITE_GA_ID,
    sentryDsn: import.meta.env.VITE_SENTRY_DSN,
    enabled: import.meta.env.VITE_ENABLE_ANALYTICS === 'true',
  },
  features: {
    marketplace: import.meta.env.VITE_ENABLE_MARKETPLACE === 'true',
    compliance: import.meta.env.VITE_ENABLE_COMPLIANCE === 'true',
  },
  env: import.meta.env.VITE_ENV || 'development',
} as const;
```

---

## CDN Strategy

### Static Asset CDN

**Configuration**: Use CDN for static assets (JS, CSS, images)

**Benefits**:
- Faster load times
- Reduced server load
- Global distribution
- Caching

**Implementation**:
1. Build application
2. Upload to CDN (AWS CloudFront, Cloudflare, etc.)
3. Configure CDN caching rules
4. Update HTML to reference CDN URLs

### CDN Configuration Example

**CloudFront Distribution**:
- Origin: S3 bucket or application server
- Cache behaviors: Different rules for different file types
- Headers: Cache-Control, ETag
- Compression: Gzip/Brotli

---

## Docker Deployment

### Dockerfile

**File**: `Dockerfile`

```dockerfile
# Build stage
FROM node:18-alpine AS builder

WORKDIR /app

# Copy package files
COPY package*.json ./
RUN npm ci

# Copy source code
COPY . .

# Build application
RUN npm run build:production

# Production stage
FROM nginx:alpine

# Copy built files
COPY --from=builder /app/dist /usr/share/nginx/html

# Copy nginx configuration
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Expose port
EXPOSE 80

# Start nginx
CMD ["nginx", "-g", "daemon off;"]
```

### Nginx Configuration

**File**: `nginx.conf`

```nginx
server {
    listen 80;
    server_name _;
    root /usr/share/nginx/html;
    index index.html;

    # Gzip compression
    gzip on;
    gzip_vary on;
    gzip_min_length 1024;
    gzip_types text/plain text/css text/xml text/javascript application/json application/javascript application/xml+rss;

    # Cache static assets
    location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff|woff2|ttf|eot)$ {
        expires 1y;
        add_header Cache-Control "public, immutable";
    }

    # SPA routing
    location / {
        try_files $uri $uri/ /index.html;
    }

    # API proxy (if needed)
    location /api {
        proxy_pass http://backend:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    # WebSocket proxy
    location /ws {
        proxy_pass http://backend:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

### Docker Compose

**File**: `docker-compose.yml`

```yaml
version: '3.8'

services:
  frontend:
    build:
      context: .
      dockerfile: Dockerfile
    ports:
      - "3000:80"
    environment:
      - VITE_API_BASE_URL=http://backend:8000
    depends_on:
      - backend
    networks:
      - app-network

  backend:
    # Backend service configuration
    # ...

networks:
  app-network:
    driver: bridge
```

---

## Kubernetes Deployment

### Deployment Manifest

**File**: `k8s/deployment.yaml`

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: frontend
  namespace: production
spec:
  replicas: 3
  selector:
    matchLabels:
      app: frontend
  template:
    metadata:
      labels:
        app: frontend
    spec:
      containers:
      - name: frontend
        image: datahub/frontend:latest
        ports:
        - containerPort: 80
        env:
        - name: VITE_API_BASE_URL
          valueFrom:
            configMapKeyRef:
              name: frontend-config
              key: api-base-url
        resources:
          requests:
            memory: "128Mi"
            cpu: "100m"
          limits:
            memory: "256Mi"
            cpu: "200m"
        livenessProbe:
          httpGet:
            path: /
            port: 80
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /
            port: 80
          initialDelaySeconds: 5
          periodSeconds: 5
```

### Service Manifest

**File**: `k8s/service.yaml`

```yaml
apiVersion: v1
kind: Service
metadata:
  name: frontend-service
  namespace: production
spec:
  selector:
    app: frontend
  ports:
  - protocol: TCP
    port: 80
    targetPort: 80
  type: LoadBalancer
```

### ConfigMap

**File**: `k8s/configmap.yaml`

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: frontend-config
  namespace: production
data:
  api-base-url: "https://api.datahub.example.com"
  ws-url: "wss://api.datahub.example.com"
```

---

## CI/CD Pipeline

### GitHub Actions Workflow

**File**: `.github/workflows/deploy.yml`

```yaml
name: Deploy Frontend

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

jobs:
  build:
    runs-on: ubuntu-latest
    
    steps:
      - uses: actions/checkout@v3
      
      - name: Setup Node.js
        uses: actions/setup-node@v3
        with:
          node-version: '18'
          cache: 'npm'
      
      - name: Install dependencies
        run: npm ci
      
      - name: Run tests
        run: npm run test:ci
      
      - name: Build application
        run: npm run build:production
        env:
          VITE_API_BASE_URL: ${{ secrets.API_BASE_URL }}
      
      - name: Build Docker image
        run: |
          docker build -t datahub/frontend:${{ github.sha }} .
          docker tag datahub/frontend:${{ github.sha }} datahub/frontend:latest
      
      - name: Push to registry
        run: |
          echo "${{ secrets.DOCKER_PASSWORD }}" | docker login -u "${{ secrets.DOCKER_USERNAME }}" --password-stdin
          docker push datahub/frontend:${{ github.sha }}
          docker push datahub/frontend:latest

  deploy-staging:
    needs: build
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/develop'
    
    steps:
      - name: Deploy to staging
        run: |
          kubectl set image deployment/frontend \
            frontend=datahub/frontend:${{ github.sha }} \
            -n staging

  deploy-production:
    needs: build
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main'
    
    steps:
      - name: Deploy to production
        run: |
          kubectl set image deployment/frontend \
            frontend=datahub/frontend:${{ github.sha }} \
            -n production
```

---

## Version Management

### Version Tagging

**Strategy**: Semantic versioning (MAJOR.MINOR.PATCH)

**Implementation**:
```bash
# Tag release
git tag -a v1.2.3 -m "Release version 1.2.3"
git push origin v1.2.3

# Build with version
docker build -t datahub/frontend:1.2.3 .
docker push datahub/frontend:1.2.3
```

### Version Display

**Component**: `VersionDisplay`

```typescript
export function VersionDisplay() {
  const version = import.meta.env.VITE_APP_VERSION || 'dev';

  return (
    <Typography variant="caption" color="text.secondary">
      Version {version}
    </Typography>
  );
}
```

---

## Feature Flags

### Feature Flag Service

**Service**: `src/lib/features/flags.ts`

```typescript
export interface FeatureFlags {
  marketplace: boolean;
  compliance: boolean;
  advancedSearch: boolean;
}

export function getFeatureFlags(): FeatureFlags {
  return {
    marketplace: import.meta.env.VITE_ENABLE_MARKETPLACE === 'true',
    compliance: import.meta.env.VITE_ENABLE_COMPLIANCE === 'true',
    advancedSearch: import.meta.env.VITE_ENABLE_ADVANCED_SEARCH === 'true',
  };
}

export function isFeatureEnabled(feature: keyof FeatureFlags): boolean {
  const flags = getFeatureFlags();
  return flags[feature] || false;
}
```

### Usage

```typescript
import { isFeatureEnabled } from '@/lib/features/flags';

function App() {
  const showMarketplace = isFeatureEnabled('marketplace');

  return (
    <Routes>
      <Route path="/assets" element={<AssetsPage />} />
      {showMarketplace && (
        <Route path="/marketplace" element={<MarketplacePage />} />
      )}
    </Routes>
  );
}
```

---

## Rollback Strategy

### Automated Rollback

**Kubernetes Rollback**:
```bash
# Rollback to previous deployment
kubectl rollout undo deployment/frontend -n production

# Rollback to specific revision
kubectl rollout undo deployment/frontend --to-revision=2 -n production
```

### Manual Rollback

1. **Identify Issue**: Monitor error rates, user reports
2. **Revert Code**: Revert to previous working version
3. **Rebuild**: Build previous version
4. **Deploy**: Deploy previous version
5. **Verify**: Verify application is working

### Health Checks

**Implementation**: Health check endpoint

```typescript
// Health check route
app.get('/health', (req, res) => {
  res.json({
    status: 'healthy',
    version: process.env.VITE_APP_VERSION,
    timestamp: new Date().toISOString(),
  });
});
```

---

## Best Practices

1. **Version Everything**: Tag all releases
2. **Test Before Deploy**: Run tests in CI/CD
3. **Gradual Rollout**: Use canary deployments
4. **Monitor Deployments**: Monitor after deployment
5. **Rollback Plan**: Always have a rollback plan
6. **Environment Parity**: Keep environments similar
7. **Secure Secrets**: Use secrets management
8. **CDN Caching**: Use CDN for static assets
9. **Health Checks**: Implement health checks
10. **Documentation**: Document deployment process

---

**Last Updated**: 2026-03-22  
**Version**: 1.0.0


---

# Design Principles and Guidelines

**Last Updated**: 2026-03-22  
**Version**: 1.0.0

---

## Table of Contents

1. [Overview](#overview)
2. [Core Design Principles](#core-design-principles)
3. [User Experience Principles](#user-experience-principles)
4. [Visual Design Principles](#visual-design-principles)
5. [Interaction Design Principles](#interaction-design-principles)
6. [Content Design Principles](#content-design-principles)
7. [Design Decision Framework](#design-decision-framework)
8. [Design Review Process](#design-review-process)

---

## Overview

This document defines the core design principles and guidelines that guide all UI/UX decisions for the Interoperable Data Hub platform. These principles ensure consistency, usability, and a cohesive user experience across all interfaces.

**Purpose**:  
To establish a shared understanding of design values and provide a framework for making design decisions that align with user needs and business goals.

---

## Core Design Principles

### 1. User-Centered Design

**Principle**: Every design decision prioritizes user needs, goals, and context.

**Guidelines**:
- Understand user personas and their goals before designing
- Design for real user workflows, not theoretical scenarios
- Test designs with actual users whenever possible
- Prioritize user value over feature completeness
- Reduce cognitive load by showing only what's needed

**Examples**:
- Data Product Owner onboarding flow prioritizes simplicity over feature richness
- Compliance Officer dashboards focus on actionable insights, not raw data
- Data Consumer marketplace emphasizes discovery and evaluation

---

### 2. Accessibility First

**Principle**: Design for all users, including those with disabilities.

**Guidelines**:
- Meet WCAG 2.1 AA standards as minimum
- Ensure keyboard navigation for all interactions
- Provide sufficient color contrast (4.5:1 for text, 3:1 for UI components)
- Support screen readers with proper ARIA labels
- Design for various input methods (mouse, keyboard, touch, voice)
- Test with assistive technologies

**Examples**:
- All buttons and links are keyboard accessible
- Form fields have clear labels and error messages
- Color is never the only indicator of status
- Focus indicators are visible and clear

---

### 3. Consistency

**Principle**: Maintain a unified design language across all interfaces.

**Guidelines**:
- Use consistent terminology and patterns
- Follow design system components and patterns
- Maintain consistent spacing, typography, and colors
- Use consistent iconography and imagery
- Follow established interaction patterns
- Document patterns for reuse

**Examples**:
- All forms use the same input styles and validation patterns
- All data tables use consistent column headers and actions
- All modals follow the same structure and behavior
- All error messages use consistent language and styling

---

### 4. Efficiency

**Principle**: Streamline workflows to reduce time and effort.

**Guidelines**:
- Minimize steps to complete tasks
- Provide shortcuts for power users
- Use progressive disclosure to reduce complexity
- Automate repetitive tasks
- Provide bulk operations where appropriate
- Show progress for long-running operations
- Pre-fill forms with known information

**Examples**:
- Asset creation flow pre-fills metadata from previous assets
- Contract validation shows progress and estimated time
- Bulk operations for asset management
- Keyboard shortcuts for common actions

---

### 5. Clarity

**Principle**: Make information and actions clear and understandable.

**Guidelines**:
- Use plain language, avoid jargon
- Provide clear labels and descriptions
- Show context and relationships
- Use visual hierarchy to guide attention
- Provide helpful error messages
- Explain why actions are needed
- Show system status and feedback

**Examples**:
- Error messages explain what went wrong and how to fix it
- Form fields have helpful placeholder text and descriptions
- Status indicators clearly show current state
- Tooltips explain technical terms

---

### 6. Trustworthiness

**Principle**: Build user confidence through transparency and reliability.

**Guidelines**:
- Show what the system is doing
- Provide clear feedback for all actions
- Explain data usage and privacy
- Show data lineage and provenance
- Display compliance and quality status
- Handle errors gracefully
- Provide audit trails

**Examples**:
- Job status shows progress and estimated completion time
- Compliance reports show detailed findings and recommendations
- Data lineage visualization shows data sources and transformations
- Audit logs are accessible and searchable

---

### 7. Scalability

**Principle**: Design for growth and change.

**Guidelines**:
- Design system supports expansion
- Components are reusable and composable
- Patterns work across different contexts
- Performance remains good at scale
- Design for internationalization
- Support multiple languages and regions

**Examples**:
- Component library supports custom themes
- Data tables handle large datasets efficiently
- Search works across millions of assets
- UI supports RTL languages

---

## User Experience Principles

### 1. Progressive Disclosure

**Principle**: Show information and options progressively, revealing complexity as needed.

**Guidelines**:
- Start with essential information
- Provide "show more" options for details
- Use tabs or accordions for related content
- Hide advanced options by default
- Show contextual help when needed

**Examples**:
- Asset creation form shows basic fields first, advanced options in expandable sections
- Contract editor shows common fields, with "Advanced" section for less common options
- Compliance report shows summary first, detailed findings on demand

---

### 2. Immediate Feedback

**Principle**: Provide immediate feedback for all user actions.

**Guidelines**:
- Show loading states for async operations
- Provide success/error feedback
- Update UI immediately for optimistic updates
- Show progress for long operations
- Use animations to indicate state changes
- Provide undo for destructive actions

**Examples**:
- File upload shows progress bar and percentage
- Form validation shows errors as user types
- Asset activation shows success message and status update
- Delete actions show confirmation dialog with undo option

---

### 3. Error Prevention

**Principle**: Prevent errors before they occur.

**Guidelines**:
- Validate input before submission
- Provide clear constraints and requirements
- Use confirmation dialogs for destructive actions
- Disable invalid actions
- Show warnings before risky operations
- Provide helpful suggestions

**Examples**:
- Contract validation runs automatically as user edits
- File upload validates format and size before upload
- Delete actions require confirmation
- Form fields show required indicators and validation rules

---

### 4. Error Recovery

**Principle**: Help users recover from errors gracefully.

**Guidelines**:
- Provide clear error messages
- Explain what went wrong and why
- Suggest solutions or next steps
- Allow users to retry failed operations
- Preserve user input when possible
- Provide support links for complex issues

**Examples**:
- Validation errors show specific field issues and how to fix
- Failed uploads show reason and allow retry
- API errors show user-friendly messages with support links
- Network errors allow retry with exponential backoff

---

### 5. Contextual Help

**Principle**: Provide help when and where users need it.

**Guidelines**:
- Use tooltips for brief explanations
- Provide inline help for complex fields
- Link to detailed documentation
- Show examples and templates
- Provide guided tours for new users
- Context-sensitive help based on user role

**Examples**:
- Contract fields have tooltips explaining purpose
- Asset creation provides example contracts
- Compliance dashboard links to regulatory documentation
- New user onboarding shows guided tour

---

## Visual Design Principles

### 1. Visual Hierarchy

**Principle**: Use visual hierarchy to guide user attention.

**Guidelines**:
- Use size, color, and contrast to establish hierarchy
- Place important information prominently
- Group related information visually
- Use whitespace to separate sections
- Follow reading patterns (F-pattern, Z-pattern)

**Examples**:
- Page titles are larger and bolder
- Primary actions use prominent buttons
- Related form fields are grouped visually
- Important alerts use high contrast colors

---

### 2. Balance and Alignment

**Principle**: Create visual balance through alignment and spacing.

**Guidelines**:
- Use consistent spacing system
- Align elements to grid
- Balance visual weight
- Use symmetry or asymmetry intentionally
- Maintain consistent margins and padding

**Examples**:
- All components align to 8px grid
- Form fields align to consistent baseline
- Cards use consistent padding and spacing
- Navigation items are evenly spaced

---

### 3. Color and Contrast

**Principle**: Use color purposefully and ensure sufficient contrast.

**Guidelines**:
- Use color to convey meaning, not just decoration
- Maintain sufficient contrast for readability
- Support colorblind users (don't rely on color alone)
- Use consistent color meanings (red = error, green = success)
- Provide dark mode support

**Examples**:
- Status indicators use color + icon + text
- Error messages use red color with warning icon
- Success messages use green color with checkmark icon
- Links are blue and underlined for accessibility

---

### 4. Typography

**Principle**: Use typography to enhance readability and hierarchy.

**Guidelines**:
- Use clear, readable fonts
- Establish typographic scale
- Use appropriate font weights
- Maintain consistent line height
- Limit font families (2-3 max)
- Support multiple languages

**Examples**:
- Headings use larger, bolder fonts
- Body text uses readable size (16px minimum)
- Code uses monospace font
- Long-form content uses comfortable line height (1.5-1.6)

---

## Interaction Design Principles

### 1. Affordances

**Principle**: Make interactive elements clearly identifiable.

**Guidelines**:
- Buttons look clickable
- Links are distinguishable from text
- Form fields are clearly editable
- Disabled states are visually distinct
- Hover states provide feedback
- Use familiar UI patterns

**Examples**:
- Buttons have clear borders and backgrounds
- Links are blue and underlined
- Input fields have visible borders
- Disabled buttons are grayed out
- Hover states show cursor change

---

### 2. Feedback

**Principle**: Provide clear feedback for all interactions.

**Guidelines**:
- Show hover states for interactive elements
- Provide active/pressed states
- Use loading indicators for async operations
- Show success/error states
- Use animations to indicate state changes
- Provide haptic feedback on mobile (where applicable)

**Examples**:
- Buttons show hover and active states
- Form submission shows loading spinner
- File upload shows progress bar
- Success messages appear with animation
- Error states are clearly indicated

---

### 3. Consistency in Interactions

**Principle**: Use consistent interaction patterns.

**Guidelines**:
- Similar actions behave similarly
- Use standard interaction patterns
- Maintain consistent navigation
- Follow platform conventions
- Document interaction patterns

**Examples**:
- All modals close the same way (X button, ESC key, outside click)
- All forms submit the same way (Submit button, Enter key)
- All tables sort and filter consistently
- Navigation follows consistent patterns

---

## Content Design Principles

### 1. Plain Language

**Principle**: Use clear, simple language.

**Guidelines**:
- Avoid jargon and technical terms when possible
- Explain technical terms when needed
- Use active voice
- Write concisely
- Use consistent terminology
- Provide examples

**Examples**:
- "Create Asset" instead of "Initialize Data Product Entity"
- "Run Quality Check" instead of "Execute DQ Profile"
- Tooltips explain technical terms
- Error messages use plain language

---

### 2. Scannable Content

**Principle**: Make content easy to scan and understand.

**Guidelines**:
- Use headings and subheadings
- Break up long paragraphs
- Use bullet points and lists
- Highlight key information
- Use whitespace effectively
- Structure content logically

**Examples**:
- Long forms use sections with headings
- Lists use bullet points for readability
- Important information is highlighted
- Tables use clear headers and spacing

---

### 3. Action-Oriented

**Principle**: Use action-oriented language for buttons and links.

**Guidelines**:
- Use verbs for button labels
- Be specific about actions
- Use consistent action language
- Avoid vague terms like "OK" or "Submit"

**Examples**:
- "Create Asset" instead of "Submit"
- "Save Changes" instead of "OK"
- "Delete Asset" instead of "Remove"
- "Publish to Marketplace" instead of "Publish"

---

## Design Decision Framework

When making design decisions, consider:

1. **User Impact**: How does this affect users?
2. **Consistency**: Does this align with existing patterns?
3. **Accessibility**: Is this accessible to all users?
4. **Performance**: Does this impact performance?
5. **Maintainability**: Is this easy to maintain?
6. **Scalability**: Will this work as the platform grows?

**Decision Process**:
1. Understand the problem and user needs
2. Research existing patterns and solutions
3. Consider design principles and guidelines
4. Create design options
5. Evaluate options against framework
6. Test with users (when possible)
7. Document decision and rationale

---

## Design Review Process

### Review Checklist

Before finalizing a design, ensure:

- [ ] Aligns with design principles
- [ ] Follows design system guidelines
- [ ] Meets accessibility standards (WCAG 2.1 AA)
- [ ] Works across breakpoints (responsive)
- [ ] Uses consistent patterns and components
- [ ] Provides clear feedback and error handling
- [ ] Uses plain language
- [ ] Has been tested with users (when possible)
- [ ] Is documented in design system

### Review Participants

- **Designer**: Creates and presents design
- **Product Manager**: Ensures alignment with requirements
- **Developer**: Ensures technical feasibility
- **Accessibility Specialist**: Reviews accessibility
- **User Researcher**: Provides user insights (when available)

---

**Last Updated**: 2026-03-22  
**Version**: 1.0.0


---

# Design System

**Last Updated**: 2026-03-22  
**Version**: 2.0.0 (Meshant)

---

## Table of Contents

1. [Overview](#overview)
2. [Meshant Palette](#meschant-palette)
3. [Token Mapping (CSS ↔ tokens.ts)](#token-mapping-css--tokensts)
4. [Colors](#colors)
5. [Typography](#typography)
6. [Spacing](#spacing)
7. [Icons](#icons)
8. [Shadows and Elevation](#shadows-and-elevation)
9. [Borders and Dividers](#borders-and-dividers)
10. [Layout](#layout)
11. [Animation and Motion](#animation-and-motion)
12. [Design Tokens](#design-tokens)
13. [Theme Support](#theme-support)

---

## Overview

The Design System provides a comprehensive set of design tokens, components, and guidelines that ensure visual consistency across the Meshant platform. All UI components and interfaces should use these design tokens.

**Design System Principles**:
- **Consistency**: Unified visual language across all interfaces
- **Scalability**: Tokens support growth and customization
- **Accessibility**: All tokens meet WCAG 2.1 AA standards
- **Maintainability**: Centralized tokens for easy updates

**Reference**: [MESHANT_DESIGN_SYSTEM_PLAN.md](../../openspec/changes/useronboardfix/MESHANT_DESIGN_SYSTEM_PLAN.md)

---

## Meshant Palette

The Meshant design system uses a navy, blue, and cyan palette:

| Role | Base (#500) | Hex | Usage |
|------|-------------|-----|-------|
| **Primary** | Meshant Navy | `#0A1F44` | Headers, primary text on light, brand elements |
| **Secondary** | Meshant Blue | `#2F6BFF` | Primary actions, links, CTAs |
| **Accent** | Meshant Cyan | `#17C6E6` | Highlights, secondary accents, hover states |

**Full scales** (50–900) are defined in `frontend/src/index.css` and `frontend/src/shared/design-system/tokens.ts`.

---

## Token Mapping (CSS ↔ tokens.ts)

Single source of truth: `frontend/src/index.css` (CSS variables) and `frontend/src/shared/design-system/tokens.ts` (TypeScript). Both must stay in sync.

### Colors

| CSS Variable | tokens.ts | Value |
|--------------|-----------|-------|
| `--color-primary-500` | `colors.primary[500]` | #0A1F44 |
| `--color-primary-800` | `colors.primary[800]` | #0A1F44 |
| `--color-secondary-500` | `colors.secondary[500]` | #2F6BFF |
| `--color-accent-500` | `colors.accent[500]` | #17C6E6 |
| `--color-primary` | — | `var(--color-primary-500)` |
| `--color-secondary` | — | `var(--color-secondary-500)` |
| `--color-accent` | — | `var(--color-accent-500)` |

### Typography

| CSS Variable | tokens.ts | Value |
|--------------|-----------|-------|
| `--font-family-sans` | `typography.fontFamily.sans` | 'Inter', -apple-system, BlinkMacSystemFont, sans-serif |
| `--font-family-mono` | `typography.fontFamily.mono` | Monaco, Menlo, Consolas, monospace |
| `--font-size-base` | `typography.fontSize.base` | 16px |
| `--font-size-xs` | `typography.fontSize.xs` | 12px |
| `--font-size-sm` | `typography.fontSize.sm` | 14px |
| `--font-size-lg` | `typography.fontSize.lg` | 18px |
| `--font-size-xl` | `typography.fontSize.xl` | 20px |
| `--font-size-2xl` | `typography.fontSize['2xl']` | 24px |
| `--font-size-3xl` | `typography.fontSize['3xl']` | 30px |
| `--font-size-4xl` | `typography.fontSize['4xl']` | 36px |

### Spacing

| CSS Variable | tokens.ts | Value |
|--------------|-----------|-------|
| `--spacing-xs` | `spacing.xs` | 4px |
| `--spacing-sm` | `spacing.sm` | 8px |
| `--spacing-md` | `spacing.md` | 16px |
| `--spacing-lg` | `spacing.lg` | 24px |
| `--spacing-xl` | `spacing.xl` | 32px |
| `--spacing-2xl` | `spacing['2xl']` | 48px |
| `--spacing-3xl` | `spacing['3xl']` | 64px |

### Layout

| CSS Variable | tokens.ts | Value |
|--------------|-----------|-------|
| `--layout-sidebar-width` | `layout.sidebarWidth` | 240px |
| `--layout-content-max-width` | `layout.contentMaxWidth` | 1200px |

### Breakpoints (tokens.ts only)

| Token | Value |
|-------|-------|
| `breakpoints.sm` | 600px |
| `breakpoints.md` | 900px |
| `breakpoints.lg` | 1200px |
| `breakpoints.xl` | 1536px |

### Shadows

| CSS Variable | tokens.ts | Value |
|--------------|-----------|-------|
| `--shadow-sm` | `shadows.sm` | 0 1px 2px 0 rgba(0,0,0,0.05) |
| `--shadow-md` | `shadows.md` | 0 4px 6px -1px rgba(0,0,0,0.1) |
| `--shadow-lg` | `shadows.lg` | 0 10px 15px -3px rgba(0,0,0,0.1) |
| `--shadow-xl` | `shadows.xl` | 0 20px 25px -5px rgba(0,0,0,0.1) |

### Border Radius

| CSS Variable | tokens.ts | Value |
|--------------|-----------|-------|
| `--border-radius-sm` | `borderRadius.sm` | 4px |
| `--border-radius-md` | `borderRadius.md` | 8px |
| `--border-radius-lg` | `borderRadius.lg` | 12px |
| `--border-radius-xl` | `borderRadius.xl` | 16px |
| `--border-radius-full` | `borderRadius.full` | 9999px |

### Token Usage in Code

- **CSS**: Use `var(--color-primary)`, `var(--spacing-md)`, etc.
- **TypeScript**: Import from `shared/design-system/tokens` for computed values (e.g. breakpoints in media queries).
- **Extension**: Add new tokens in both `index.css` and `tokens.ts`; run `npm run test:run -- src/shared/design-system/` to verify.

---

## Colors

### Color Palette (Meshant)

#### Primary Colors (Meshant Navy)

- `primary-50`: #E8ECF4 (Lightest)
- `primary-100`: #CFD8E8
- `primary-200`: #9BA8C4
- `primary-300`: #6778A0
- `primary-400`: #33497C
- `primary-500`: #0A1F44 (Base)
- `primary-600`: #081A3A
- `primary-700`: #061530
- `primary-800`: #0A1F44
- `primary-900`: #030D22 (Darkest)

**Usage**: Headers, primary text on light backgrounds, brand elements, sidebar

#### Secondary Colors (Meshant Blue)

- `secondary-50`: #EBF0FF
- `secondary-100`: #D6E0FF
- `secondary-200`: #ADBFFF
- `secondary-300`: #849EFF
- `secondary-400`: #5B7DFF
- `secondary-500`: #2F6BFF (Base)
- `secondary-600`: #2756E6
- `secondary-700`: #1F41CC
- `secondary-800`: #172DB3
- `secondary-900`: #0F1999

**Usage**: Primary actions, links, CTAs, interactive elements

#### Accent Colors (Meshant Cyan)

- `accent-50`: #E6FAFC
- `accent-100`: #CCF5F9
- `accent-200`: #99EBF3
- `accent-300`: #66E0ED
- `accent-400`: #33D6E7
- `accent-500`: #17C6E6 (Base)
- `accent-600`: #12A0C0
- `accent-700`: #0E7A9A
- `accent-800`: #095474
- `accent-900`: #052E3D

**Usage**: Highlights, secondary accents, hover states, badges

#### Semantic Colors

**Success (Green)**
- `success-50`: #E8F5E9
- `success-100`: #C8E6C9
- `success-500`: #4CAF50 (Base)
- `success-700`: #388E3C
- `success-900`: #1B5E20

**Usage**: Success messages, positive status indicators, completed states

**Warning (Amber)**
- `warning-50`: #FFF8E1
- `warning-100`: #FFECB3
- `warning-500`: #FFC107 (Base)
- `warning-700`: #F57C00
- `warning-900`: #E65100

**Usage**: Warning messages, caution indicators, pending states

**Error (Red)**
- `error-50`: #FFEBEE
- `error-100`: #FFCDD2
- `error-500`: #F44336 (Base)
- `error-700`: #D32F2F
- `error-900`: #B71C1C

**Usage**: Error messages, failure states, destructive actions

**Info (Blue)** — Maps to Meshant primary
- `info-50`: `primary-50` (#E8ECF4)
- `info-100`: `primary-100` (#CFD8E8)
- `info-500`: `primary-500` (#0A1F44) (Base)
- `info-700`: `primary-700` (#061530)
- `info-900`: `primary-900` (#030D22)

**Usage**: Informational messages, help text, neutral status

#### Neutral Colors

**Gray Scale** (`neutral-*` in tokens.ts)
- `neutral-50`: #FAFAFA (Lightest)
- `neutral-100`: #F5F5F5
- `neutral-200`: #EEEEEE
- `neutral-300`: #E0E0E0
- `neutral-400`: #BDBDBD
- `neutral-500`: #9E9E9E (Base)
- `neutral-600`: #757575
- `neutral-700`: #616161
- `neutral-800`: #424242
- `neutral-900`: #212121 (Darkest)

**Usage**: Text, backgrounds, borders, dividers

#### Text Colors

- `--color-text-primary`: `neutral-900` (#212121) - Primary text
- `--color-text-secondary`: `neutral-700` (#616161) - Secondary text
- `--color-text-tertiary`: `neutral-600` (#757575) - Tertiary text
- `text-inverse`: `white` (#FFFFFF) - Text on dark backgrounds
- `text-link`: `--color-secondary` (#2F6BFF) - Links
- `text-error`: `error-700` (#D32F2F) - Error text

#### Background Colors

- `--color-background-primary`: `white` (#FFFFFF) - Default background
- `--color-background-secondary`: `neutral-50` (#FAFAFA) - Elevated surfaces
- `--color-background-tertiary`: `neutral-100` (#F5F5F5) - Hover states
- `background-selected`: `primary-100` (#CFD8E8) - Selected states
- `background-disabled`: `neutral-200` (#EEEEEE) - Disabled states

#### Border Colors

- `--color-border`: `neutral-300` (#E0E0E0) - Default borders
- `border-focus`: `primary-500` (#0A1F44) - Focus borders
- `border-error`: `error-500` (#F44336) - Error borders
- `--color-border-light`: `neutral-200` (#EEEEEE) - Dividers

### Color Usage Guidelines

1. **Contrast Requirements**:
   - Text on background: Minimum 4.5:1 for normal text, 3:1 for large text
   - UI components: Minimum 3:1 contrast
   - Use contrast checker tools to verify

2. **Color and Meaning**:
   - Use semantic colors consistently (green = success, red = error)
   - Don't rely on color alone; use icons and text
   - Test with colorblind simulators

3. **Accessibility**:
   - All color combinations meet WCAG 2.1 AA standards
   - Provide alternative indicators (icons, patterns) for color-only information

---

## Typography

### Font Families (Meshant)

**Primary Font**: Inter (Google Fonts: 400, 500, 600, 700)
- Loaded via `frontend/index.html` preconnect + stylesheet
- Sans-serif, modern, highly readable
- Supports multiple languages
- Excellent screen rendering

**Font Stack**:
```css
font-family: var(--font-family-sans);
/* Resolves to: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif */
```

**Monospace Font**: Monaco, Menlo, Consolas
- Used for code, technical content, data values
- Font stack: `var(--font-family-mono)` → `'Monaco', 'Menlo', 'Consolas', monospace`

**Air-gapped deployments**: Inter loads from Google Fonts. In offline environments, the fallback stack (`-apple-system`, `BlinkMacSystemFont`, `sans-serif`) is used. For self-hosted font, bundle Inter woff2 files and use `@font-face` locally.

### Type Scale

The typography system uses a modular scale based on 1.25 (Major Third).

| Scale | Size | Line Height | Weight | Usage |
|-------|------|-------------|--------|-------|
| `h1` | 32px (2rem) | 1.2 | 700 | Page titles |
| `h2` | 24px (1.5rem) | 1.3 | 600 | Section titles |
| `h3` | 20px (1.25rem) | 1.4 | 600 | Subsection titles |
| `h4` | 18px (1.125rem) | 1.4 | 600 | Card titles |
| `h5` | 16px (1rem) | 1.5 | 600 | Small headings |
| `h6` | 14px (0.875rem) | 1.5 | 600 | Labels |
| `body1` | 16px (1rem) | 1.5 | 400 | Body text |
| `body2` | 14px (0.875rem) | 1.5 | 400 | Secondary text |
| `caption` | 12px (0.75rem) | 1.4 | 400 | Captions, metadata |
| `overline` | 10px (0.625rem) | 1.6 | 600 | Overlines, tags |
| `code` | 14px (0.875rem) | 1.5 | 400 | Code snippets |

### Font Weights

- `300`: Light
- `400`: Regular (default)
- `500`: Medium
- `600`: Semi-bold
- `700`: Bold

### Typography Usage Guidelines

1. **Hierarchy**: Use type scale to establish clear visual hierarchy
2. **Readability**: Minimum 16px for body text
3. **Line Length**: Optimal 45-75 characters per line
4. **Line Height**: 1.5 for body text, 1.2-1.4 for headings
5. **Spacing**: Use consistent spacing between text elements

---

## Spacing

### Spacing Scale

The spacing system uses a 4px base unit. Align to 8px grid for consistency.

| Token | Value | Usage |
|-------|-------|-------|
| `--spacing-xs` | 4px | Tight spacing |
| `--spacing-sm` | 8px | Base unit |
| `--spacing-md` | 16px | Default spacing |
| `--spacing-lg` | 24px | Large spacing |
| `--spacing-xl` | 32px | Extra large spacing |
| `--spacing-2xl` | 48px | Section spacing |
| `--spacing-3xl` | 64px | Major section spacing |

### Spacing Usage Guidelines

1. **Consistency**: Use spacing tokens, not arbitrary values
2. **Alignment**: Align to 8px grid
3. **Relationships**: Related elements use smaller spacing, unrelated use larger
4. **Responsive**: Adjust spacing for smaller screens

---

## Icons

### Icon Library

**Primary**: Material Icons (Material Design Icons)
- Comprehensive icon set
- Consistent style
- Good accessibility support

**Alternative**: Custom icons for brand-specific elements

### Icon Sizes

| Size | Value | Usage |
|------|-------|-------|
| `icon-xs` | 12px | Inline with small text |
| `icon-sm` | 16px | Default inline icons |
| `icon-md` | 20px | Standard icons |
| `icon-lg` | 24px | Prominent icons |
| `icon-xl` | 32px | Hero icons |
| `icon-2xl` | 48px | Large display icons |

### Icon Usage Guidelines

1. **Consistency**: Use icons from the same library
2. **Meaning**: Icons should be universally understood
3. **Accessibility**: Provide text labels or ARIA labels
4. **Size**: Match icon size to text size
5. **Color**: Use semantic colors for status icons

### Common Icons

- **Actions**: Add, Edit, Delete, Save, Cancel, Search, Filter
- **Status**: Success (check), Error (X), Warning (alert), Info (info)
- **Navigation**: Home, Back, Forward, Menu, Close
- **Data**: Table, Chart, File, Folder, Download, Upload
- **System**: Settings, User, Notifications, Help

---

## Shadows and Elevation

### Elevation Levels

Material Design elevation system with 5 levels.

| Level | Shadow | Usage |
|-------|--------|-------|
| `elevation-0` | None | Flat surfaces |
| `elevation-1` | 0px 1px 3px rgba(0,0,0,0.12) | Cards, buttons |
| `elevation-2` | 0px 2px 6px rgba(0,0,0,0.12) | Hover states |
| `elevation-4` | 0px 4px 12px rgba(0,0,0,0.15) | Modals, dropdowns |
| `elevation-8` | 0px 8px 24px rgba(0,0,0,0.15) | Popovers, tooltips |
| `elevation-16` | 0px 16px 48px rgba(0,0,0,0.2) | Dialogs |

### Shadow Usage Guidelines

1. **Purpose**: Use elevation to show hierarchy and depth
2. **Consistency**: Use standard elevation levels
3. **Performance**: Avoid excessive shadows
4. **Accessibility**: Ensure sufficient contrast with shadows

---

## Borders and Dividers

### Border Radius

Aligns with `--border-radius-*` and `tokens.ts` `borderRadius`:

| Token | Value | Usage |
|-------|-------|-------|
| `--border-radius-none` | 0 | Sharp corners |
| `--border-radius-sm` | 4px | Small elements |
| `--border-radius-md` | 8px | Default radius |
| `--border-radius-lg` | 12px | Cards, buttons |
| `--border-radius-xl` | 16px | Large cards |
| `--border-radius-full` | 9999px | Pills, avatars |

### Border Width

| Token | Value | Usage |
|-------|-------|-------|
| `border-none` | 0px | No border |
| `border-thin` | 1px | Default borders |
| `border-medium` | 2px | Focus states |
| `border-thick` | 3px | Emphasis |

### Dividers

- **Horizontal**: 1px solid `var(--color-border-light)`
- **Vertical**: 1px solid `var(--color-border-light)`
- **Spacing**: 16px margin on both sides

---

## Layout

Meshant layout constants (Phase 28.7.4):

| Token | Value | Usage |
|-------|-------|-------|
| `--layout-sidebar-width` | 240px | App sidebar width |
| `--layout-content-max-width` | 1200px | Main content max-width, centered |

**Usage in CSS**:
```css
.app-sidebar { width: var(--layout-sidebar-width); }
.app-main { max-width: var(--layout-content-max-width); margin: 0 auto; }
```

**Breakpoints** (tokens.ts): `sm` 600px, `md` 900px, `lg` 1200px, `xl` 1536px.

---

## Animation and Motion

### Animation Principles

1. **Purpose**: Animations should enhance understanding, not distract
2. **Duration**: Keep animations short (150-300ms)
3. **Easing**: Use natural easing curves
4. **Performance**: Use CSS transforms and opacity for smooth animations

### Animation Durations

| Duration | Value | Usage |
|----------|-------|-------|
| `duration-fast` | 150ms | Micro-interactions |
| `duration-normal` | 250ms | Standard transitions |
| `duration-slow` | 350ms | Complex animations |

### Easing Functions

- **Ease In**: `cubic-bezier(0.4, 0, 1, 1)` - Entering elements
- **Ease Out**: `cubic-bezier(0, 0, 0.2, 1)` - Exiting elements
- **Ease In Out**: `cubic-bezier(0.4, 0, 0.2, 1)` - Standard transitions

### Common Animations

- **Fade**: Opacity 0 → 1 (150ms)
- **Slide**: Transform translate (250ms)
- **Scale**: Transform scale (200ms)
- **Rotate**: Transform rotate (300ms)

---

## Design Tokens

### Token Format

Design tokens live in two places (must stay in sync):

1. **CSS**: `frontend/src/index.css` — `:root` CSS custom properties
2. **TypeScript**: `frontend/src/shared/design-system/tokens.ts` — exported constants

**Meshant palette example** (tokens.ts):
```typescript
export const colors = {
  primary: { 500: '#0A1F44', ... },
  secondary: { 500: '#2F6BFF', ... },
  accent: { 500: '#17C6E6', ... },
  // ...
};
```

### Token Usage

- **CSS**: Use `var(--color-primary)`, `var(--spacing-md)`, etc.
- **TypeScript**: Import from `shared/design-system/tokens` for breakpoints, computed values
- **Extension**: Add tokens in both `index.css` and `tokens.ts`; run `npm run test:run -- src/shared/design-system/` to verify
- **Runbook**: See [Brand Name Change](../runbooks/BRAND_NAME_CHANGE.md) for changing brand/app name

---

## Theme Support

### Light Theme (Default)

- Primary background: White
- Text: Dark gray
- Accents: Primary blue

### Dark Theme (Future)

- Primary background: Dark gray
- Text: Light gray
- Accents: Light blue

### Theme Implementation

- Use CSS variables for theme values
- Support system preference (prefers-color-scheme)
- Provide theme toggle in settings
- Ensure all components support both themes

---

**Last Updated**: 2026-03-22  
**Version**: 2.0.0 (Meshant)


---

# Developer Experience Guide

**Last Updated**: 2026-03-22  
**Version**: 1.0.0

---

## Table of Contents

1. [Overview](#overview)
2. [Development Setup](#development-setup)
3. [Project Structure](#project-structure)
4. [Development Workflow](#development-workflow)
5. [Component Development](#component-development)
6. [Storybook Usage](#storybook-usage)
7. [Code Style Guide](#code-style-guide)
8. [Git Workflow](#git-workflow)
9. [Debugging](#debugging)
10. [Common Tasks](#common-tasks)

---

## Overview

This guide provides comprehensive instructions for developers working on the frontend application. It covers setup, workflows, best practices, and common development tasks.

**Developer Experience Goals**:
- Fast setup and onboarding
- Clear project structure
- Efficient development workflow
- Comprehensive tooling
- Good documentation

---

## Development Setup

### Prerequisites

- **Node.js**: 18.x or higher
- **npm**: 9.x or higher
- **Git**: Latest version
- **IDE**: VS Code (recommended) or any modern IDE

### Initial Setup

```bash
# Clone repository
git clone https://github.com/org/datahub-frontend.git
cd datahub-frontend

# Install dependencies
npm install

# Copy environment file
cp .env.example .env

# Start development server
npm run dev
```

### VS Code Setup

**Recommended Extensions**:
- ESLint
- Prettier
- TypeScript
- React snippets
- Tailwind CSS IntelliSense (if using Tailwind)

**Settings**: `.vscode/settings.json`

```json
{
  "editor.formatOnSave": true,
  "editor.defaultFormatter": "esbenp.prettier-vscode",
  "editor.codeActionsOnSave": {
    "source.fixAll.eslint": true
  },
  "typescript.tsdk": "node_modules/typescript/lib",
  "typescript.enablePromptUseWorkspaceTsdk": true
}
```

---

## Project Structure

### Directory Layout

```
src/
├── components/          # Reusable UI components
│   ├── common/         # Common components (Button, Input, etc.)
│   ├── layout/         # Layout components (Header, Sidebar, etc.)
│   └── features/       # Feature-specific components
├── features/           # Feature modules
│   ├── assets/        # Assets feature
│   ├── contracts/     # Contracts feature
│   └── marketplace/   # Marketplace feature
├── hooks/              # Custom React hooks
├── lib/                # Utility libraries
│   ├── api/           # API client, WebSocket
│   ├── analytics/     # Analytics integration
│   ├── i18n/          # Internationalization
│   └── utils/         # Utility functions
├── pages/              # Page components
├── routes/             # Route configuration
├── store/              # State management (Redux/Zustand)
├── styles/             # Global styles, themes
├── types/              # TypeScript type definitions
└── test-utils/        # Testing utilities
```

### File Naming Conventions

- **Components**: PascalCase (e.g., `AssetCard.tsx`)
- **Hooks**: camelCase with `use` prefix (e.g., `useAssets.ts`)
- **Utils**: camelCase (e.g., `formatDate.ts`)
- **Types**: PascalCase (e.g., `Asset.ts`)
- **Constants**: UPPER_SNAKE_CASE (e.g., `API_ENDPOINTS.ts`)

---

## Development Workflow

### Starting Development

```bash
# Start development server
npm run dev

# Start with backend
docker-compose up

# Run tests in watch mode
npm run test:watch
```

### Development Server

- **URL**: http://localhost:3000
- **Hot Reload**: Automatic on file changes
- **API Proxy**: `/api` proxied to backend
- **WebSocket Proxy**: `/ws` proxied to backend

### Common Commands

```bash
# Development
npm run dev              # Start dev server
npm run build           # Build for production
npm run preview         # Preview production build

# Testing
npm run test            # Run tests
npm run test:watch      # Run tests in watch mode
npm run test:coverage   # Run tests with coverage

# Linting
npm run lint            # Run ESLint
npm run lint:fix        # Fix ESLint errors
npm run format          # Format code with Prettier

# Storybook
npm run storybook       # Start Storybook
npm run build-storybook # Build Storybook
```

---

## Component Development

### Component Template

**Template**: `src/components/templates/ComponentTemplate.tsx`

```typescript
import React from 'react';
import { Box, Typography } from '@mui/material';

export interface ComponentTemplateProps {
  title: string;
  children?: React.ReactNode;
}

/**
 * ComponentTemplate - Brief description of component
 *
 * @param props - Component props
 * @returns Component JSX
 */
export function ComponentTemplate({
  title,
  children,
}: ComponentTemplateProps) {
  return (
    <Box>
      <Typography variant="h6">{title}</Typography>
      {children}
    </Box>
  );
}
```

### Component Checklist

- [ ] Component follows naming conventions
- [ ] Props are typed with TypeScript
- [ ] Component is documented
- [ ] Component is accessible (ARIA labels, keyboard navigation)
- [ ] Component is responsive
- [ ] Component has loading and error states
- [ ] Component is tested
- [ ] Component has Storybook story

---

## Storybook Usage

### Story Template

**Template**: `src/components/Component.stories.tsx`

```typescript
import type { Meta, StoryObj } from '@storybook/react';
import { ComponentTemplate } from './ComponentTemplate';

const meta: Meta<typeof ComponentTemplate> = {
  title: 'Components/ComponentTemplate',
  component: ComponentTemplate,
  tags: ['autodocs'],
  parameters: {
    layout: 'centered',
  },
};

export default meta;
type Story = StoryObj<typeof ComponentTemplate>;

export const Default: Story = {
  args: {
    title: 'Default Title',
    children: 'Default content',
  },
};

export const WithContent: Story = {
  args: {
    title: 'With Content',
    children: <div>Custom content here</div>,
  },
};
```

### Viewing Stories

```bash
# Start Storybook
npm run storybook

# Open in browser
# http://localhost:6006
```

### Storybook Best Practices

1. **Document Components**: Use JSDoc comments
2. **Multiple Variants**: Create stories for different states
3. **Controls**: Use controls for interactive props
4. **Accessibility**: Test accessibility in Storybook
5. **Visual Testing**: Use Chromatic for visual regression

---

## Code Style Guide

### TypeScript

**Guidelines**:
- Use TypeScript for all new code
- Avoid `any` type
- Use interfaces for object types
- Use type aliases for unions/intersections
- Prefer `const` over `let`

**Example**:
```typescript
// Good
interface User {
  id: string;
  name: string;
  email: string;
}

function getUser(id: string): Promise<User> {
  // ...
}

// Bad
function getUser(id: any): Promise<any> {
  // ...
}
```

### React

**Guidelines**:
- Use functional components
- Use hooks for state and side effects
- Extract custom hooks for reusable logic
- Use `React.memo` for expensive components
- Avoid inline functions in JSX when possible

**Example**:
```typescript
// Good
const handleClick = useCallback(() => {
  onClick(id);
}, [id, onClick]);

return <Button onClick={handleClick}>Click me</Button>;

// Bad
return <Button onClick={() => onClick(id)}>Click me</Button>;
```

### Naming Conventions

- **Components**: PascalCase (`AssetCard`)
- **Functions**: camelCase (`getAsset`)
- **Constants**: UPPER_SNAKE_CASE (`API_BASE_URL`)
- **Files**: Match export name
- **Props**: camelCase (`assetId`)

---

## Git Workflow

### Branch Strategy

- **main**: Production-ready code
- **develop**: Integration branch
- **feature/**: Feature branches
- **fix/**: Bug fix branches
- **hotfix/**: Critical production fixes

### Commit Messages

**Format**: `type(scope): subject`

**Types**:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation
- `style`: Code style changes
- `refactor`: Code refactoring
- `test`: Test changes
- `chore`: Build/tooling changes

**Examples**:
```
feat(assets): add asset creation form
fix(contracts): fix contract validation error
docs(readme): update setup instructions
```

### Pull Request Process

1. **Create Branch**: `git checkout -b feature/new-feature`
2. **Make Changes**: Implement feature
3. **Write Tests**: Add tests for new code
4. **Update Docs**: Update documentation if needed
5. **Create PR**: Create pull request with description
6. **Review**: Address review comments
7. **Merge**: Merge after approval

---

## Debugging

### React DevTools

- Install React DevTools browser extension
- Inspect component tree
- View component props and state
- Profile component performance

### Redux DevTools

- Install Redux DevTools browser extension
- View action history
- Time-travel debugging
- State inspection

### VS Code Debugging

**Configuration**: `.vscode/launch.json`

```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "type": "chrome",
      "request": "launch",
      "name": "Launch Chrome",
      "url": "http://localhost:3000",
      "webRoot": "${workspaceFolder}/src"
    }
  ]
}
```

### Console Debugging

```typescript
// Use console.log for debugging (remove before commit)
console.log('Debug info:', data);

// Use debugger statement
debugger; // Pauses execution
```

---

## Common Tasks

### Adding a New Component

1. Create component file: `src/components/NewComponent.tsx`
2. Create component styles (if needed)
3. Create Storybook story: `NewComponent.stories.tsx`
4. Create tests: `NewComponent.test.tsx`
5. Export from index: `src/components/index.ts`

### Adding a New Page

1. Create page component: `src/pages/NewPage.tsx`
2. Add route: `src/routes/index.tsx`
3. Add navigation link (if needed)
4. Create tests: `NewPage.test.tsx`

### Adding a New API Endpoint

1. Add API function: `src/lib/api/endpoints.ts`
2. Create React Query hook: `src/hooks/api/useNewEndpoint.ts`
3. Add TypeScript types: `src/types/api.ts`
4. Use in component

### Adding a New Feature

1. Create feature directory: `src/features/new-feature/`
2. Add components, hooks, types
3. Add routes
4. Add navigation
5. Write tests
6. Update documentation

---

## Best Practices

1. **Follow Conventions**: Follow project conventions
2. **Write Tests**: Write tests for new code
3. **Document Code**: Document complex logic
4. **Review Code**: Review code before committing
5. **Keep Dependencies Updated**: Update dependencies regularly
6. **Optimize Performance**: Consider performance implications
7. **Accessibility**: Ensure accessibility
8. **Error Handling**: Handle errors gracefully
9. **Type Safety**: Use TypeScript effectively
10. **Clean Code**: Write clean, maintainable code

---

**Last Updated**: 2026-03-22  
**Version**: 1.0.0


---

# Error Handling UI Patterns

**Last Updated**: 2026-03-22  
**Version**: 1.0.0

---

## Table of Contents

1. [Overview](#overview)
2. [Error Types and Categories](#error-types-and-categories)
3. [Error Display Patterns](#error-display-patterns)
4. [Network Error Handling](#network-error-handling)
5. [Offline Mode Handling](#offline-mode-handling)
6. [API Error Handling](#api-error-handling)
7. [Validation Error Handling](#validation-error-handling)
8. [Error Recovery Patterns](#error-recovery-patterns)
9. [Error Boundary Implementation](#error-boundary-implementation)
10. [User-Friendly Error Messages](#user-friendly-error-messages)

---

## Overview

This document describes comprehensive error handling patterns for the frontend application. All error handling follows user-centric principles, providing clear, actionable feedback while maintaining a good user experience.

**Error Handling Principles**:
- **User-Centric**: Errors should be understandable by end users
- **Actionable**: Provide clear next steps
- **Non-Blocking**: Don't block user workflow unnecessarily
- **Recoverable**: Allow users to recover from errors
- **Accessible**: Errors accessible to all users

---

## Error Types and Categories

### Error Categories

1. **Network Errors**: Connection failures, timeouts
2. **API Errors**: Server errors, validation errors, authentication errors
3. **Client Errors**: Form validation, business logic errors
4. **System Errors**: Unexpected errors, crashes
5. **Permission Errors**: Access denied, insufficient permissions

### Error Severity Levels

- **Critical**: Blocks user workflow, requires immediate attention
- **Warning**: Important but doesn't block workflow
- **Info**: Informational, user should be aware
- **Success**: Positive feedback (not an error, but included for completeness)

---

## Error Display Patterns

### Pattern 1: Inline Field Errors

**Use Case**: Form validation errors

**Component**: `FormFieldError`

**Layout**:
```
┌─────────────────────────────────────────┐
│ Email Address *                         │
│ [invalid-email]                         │
│ ⚠️ Please enter a valid email address  │
└─────────────────────────────────────────┘
```

**Specification**:
```typescript
interface FormFieldErrorProps {
  error?: string;
  touched?: boolean;
}

export function FormFieldError({ error, touched }: FormFieldErrorProps) {
  if (!error || !touched) {
    return null;
  }

  return (
    <FormHelperText error>
      <ErrorIcon fontSize="small" sx={{ mr: 0.5, verticalAlign: 'middle' }} />
      {error}
    </FormHelperText>
  );
}
```

### Pattern 2: Toast Notifications

**Use Case**: Non-blocking errors, success messages

**Component**: `ErrorToast`

**Layout**:
```
┌─────────────────────────────────────────┐
│                                         │
│  ┌───────────────────────────────────┐ │
│  │ ✗ Error: Failed to save contract  │ │
│  │   Please try again                │ │
│  └───────────────────────────────────┘ │
│                                         │
└─────────────────────────────────────────┘
```

**Specification**:
```typescript
import { useSnackbar } from 'notistack';

export function useErrorToast() {
  const { enqueueSnackbar } = useSnackbar();

  const showError = useCallback((message: string, options?: any) => {
    enqueueSnackbar(message, {
      variant: 'error',
      autoHideDuration: 5000,
      ...options,
    });
  }, [enqueueSnackbar]);

  return { showError };
}
```

### Pattern 3: Error Alert Banner

**Use Case**: Page-level errors, critical errors

**Component**: `ErrorAlert`

**Layout**:
```
┌─────────────────────────────────────────┐
│ ⚠️ Error                                │
│                                         │
│  Unable to load assets. Please try     │
│  again or contact support if the       │
│  problem persists.                      │
│                                         │
│  [Retry]  [Contact Support]            │
│                                         │
└─────────────────────────────────────────┘
```

**Specification**:
```typescript
interface ErrorAlertProps {
  title?: string;
  message: string;
  severity?: 'error' | 'warning' | 'info';
  actions?: React.ReactNode;
  onDismiss?: () => void;
}

export function ErrorAlert({
  title,
  message,
  severity = 'error',
  actions,
  onDismiss,
}: ErrorAlertProps) {
  return (
    <Alert
      severity={severity}
      onClose={onDismiss}
      action={actions}
      sx={{ mb: 2 }}
    >
      {title && <AlertTitle>{title}</AlertTitle>}
      {message}
    </Alert>
  );
}
```

### Pattern 4: Error Modal/Dialog

**Use Case**: Critical errors requiring user action

**Component**: `ErrorDialog`

**Layout**:
```
┌─────────────────────────────────────────┐
│ ⚠️ Error                                │
├─────────────────────────────────────────┤
│                                         │
│  An unexpected error occurred.          │
│                                         │
│  Error Code: INTERNAL_ERROR            │
│  Request ID: abc-123-def-456           │
│                                         │
│  [Copy Error Details]                  │
│                                         │
│  [Retry]  [Go Back]  [Report Issue]    │
│                                         │
└─────────────────────────────────────────┘
```

---

## Network Error Handling

### Network Error Detection

**Hook**: `useNetworkStatus`

```typescript
export function useNetworkStatus() {
  const [isOnline, setIsOnline] = useState(navigator.onLine);
  const [wasOffline, setWasOffline] = useState(false);

  useEffect(() => {
    const handleOnline = () => {
      setIsOnline(true);
      if (wasOffline) {
        // Show reconnection success message
        showToast('Connection restored', 'success');
        setWasOffline(false);
      }
    };

    const handleOffline = () => {
      setIsOnline(false);
      setWasOffline(true);
      showToast('Connection lost. Working offline.', 'warning');
    };

    window.addEventListener('online', handleOnline);
    window.addEventListener('offline', handleOffline);

    return () => {
      window.removeEventListener('online', handleOnline);
      window.removeEventListener('offline', handleOffline);
    };
  }, [wasOffline]);

  return { isOnline, wasOffline };
}
```

### Network Error UI

**Component**: `NetworkErrorBanner`

```typescript
export function NetworkErrorBanner() {
  const { isOnline } = useNetworkStatus();

  if (isOnline) {
    return null;
  }

  return (
    <Alert severity="warning" sx={{ position: 'sticky', top: 0, zIndex: 1000 }}>
      <AlertTitle>You're offline</AlertTitle>
      Some features may not be available. Changes will be saved when you're back online.
    </Alert>
  );
}
```

### Retry Logic

**Component**: `RetryButton`

```typescript
interface RetryButtonProps {
  onRetry: () => void;
  maxRetries?: number;
  retryCount?: number;
}

export function RetryButton({
  onRetry,
  maxRetries = 3,
  retryCount = 0,
}: RetryButtonProps) {
  const canRetry = retryCount < maxRetries;

  return (
    <Button
      onClick={onRetry}
      disabled={!canRetry}
      variant="outlined"
      startIcon={<RefreshIcon />}
    >
      {canRetry ? 'Retry' : `Max retries (${maxRetries}) reached`}
    </Button>
  );
}
```

---

## Offline Mode Handling

### Offline Queue

**Pattern**: Queue actions when offline, sync when online

**Implementation**:
```typescript
class OfflineQueue {
  private queue: Array<{ action: string; data: any; timestamp: Date }> = [];

  add(action: string, data: any): void {
    this.queue.push({
      action,
      data,
      timestamp: new Date(),
    });
    this.persist();
  }

  async sync(): Promise<void> {
    if (!navigator.onLine) {
      return;
    }

    const items = [...this.queue];
    this.queue = [];

    for (const item of items) {
      try {
        await this.executeAction(item.action, item.data);
      } catch (error) {
        // Re-queue failed items
        this.queue.push(item);
      }
    }

    this.persist();
  }

  private persist(): void {
    localStorage.setItem('offline_queue', JSON.stringify(this.queue));
  }

  load(): void {
    const stored = localStorage.getItem('offline_queue');
    if (stored) {
      this.queue = JSON.parse(stored);
    }
  }
}

export const offlineQueue = new OfflineQueue();
```

### Offline Indicator

**Component**: `OfflineIndicator`

```typescript
export function OfflineIndicator() {
  const { isOnline } = useNetworkStatus();
  const [queuedActions, setQueuedActions] = useState(0);

  useEffect(() => {
    offlineQueue.load();
    const interval = setInterval(() => {
      setQueuedActions(offlineQueue.getQueueLength());
      if (navigator.onLine) {
        offlineQueue.sync();
      }
    }, 5000);

    return () => clearInterval(interval);
  }, []);

  if (isOnline && queuedActions === 0) {
    return null;
  }

  return (
    <Chip
      icon={isOnline ? <SyncIcon /> : <OfflineIcon />}
      label={
        isOnline
          ? `Syncing ${queuedActions} pending actions...`
          : `${queuedActions} actions queued`
      }
      color={isOnline ? 'primary' : 'warning'}
      size="small"
    />
  );
}
```

---

## API Error Handling

### API Error Handler

**Hook**: `useApiErrorHandler`

```typescript
export function useApiErrorHandler() {
  const { enqueueSnackbar } = useSnackbar();
  const navigate = useNavigate();

  const handleError = useCallback(
    (error: ApiException) => {
      // Handle specific error codes
      switch (error.code) {
        case 'UNAUTHORIZED':
          enqueueSnackbar('Your session has expired. Please sign in again.', {
            variant: 'warning',
          });
          navigate('/login');
          break;

        case 'FORBIDDEN':
          enqueueSnackbar('You don't have permission to perform this action.', {
            variant: 'error',
          });
          break;

        case 'NOT_FOUND':
          enqueueSnackbar('The requested resource was not found.', {
            variant: 'error',
          });
          navigate('/404');
          break;

        case 'VALIDATION_ERROR':
          // Validation errors handled inline in forms
          break;

        case 'RATE_LIMIT_EXCEEDED':
          enqueueSnackbar(
            'Rate limit exceeded. Please try again in a few moments.',
            {
              variant: 'warning',
              autoHideDuration: 10000,
            }
          );
          break;

        case 'SERVER_ERROR':
          enqueueSnackbar(
            'A server error occurred. Please try again or contact support.',
            {
              variant: 'error',
            }
          );
          break;

        case 'NETWORK_ERROR':
          enqueueSnackbar(
            'Network error. Please check your connection and try again.',
            {
              variant: 'error',
            }
          );
          break;

        default:
          enqueueSnackbar(error.message || 'An error occurred', {
            variant: 'error',
          });
      }
    },
    [enqueueSnackbar, navigate]
  );

  return { handleError };
}
```

### Error Code Mapping

**Mapping Table**:
```typescript
const ERROR_MESSAGES: Record<string, string> = {
  UNAUTHORIZED: 'Your session has expired. Please sign in again.',
  FORBIDDEN: "You don't have permission to perform this action.",
  NOT_FOUND: 'The requested resource was not found.',
  VALIDATION_ERROR: 'Please check your input and try again.',
  RATE_LIMIT_EXCEEDED: 'Rate limit exceeded. Please try again later.',
  SERVER_ERROR: 'A server error occurred. Please try again.',
  NETWORK_ERROR: 'Network error. Please check your connection.',
  CONFLICT: 'This resource has been modified. Please refresh and try again.',
  TIMEOUT: 'Request timed out. Please try again.',
};
```

---

## Validation Error Handling

### Form Validation Errors

**Pattern**: Inline validation with field-level errors

**Component**: `ValidatedTextField`

```typescript
interface ValidatedTextFieldProps {
  name: string;
  label: string;
  errors?: Record<string, string[]>;
  touched?: Record<string, boolean>;
}

export function ValidatedTextField({
  name,
  label,
  errors,
  touched,
  ...props
}: ValidatedTextFieldProps) {
  const fieldErrors = errors?.[name] || [];
  const fieldTouched = touched?.[name] || false;
  const hasError = fieldErrors.length > 0 && fieldTouched;

  return (
    <TextField
      {...props}
      name={name}
      label={label}
      error={hasError}
      helperText={hasError ? fieldErrors[0] : props.helperText}
    />
  );
}
```

### Server-Side Validation Errors

**Pattern**: Display server validation errors in forms

```typescript
export function useFormValidation() {
  const [errors, setErrors] = useState<Record<string, string[]>>({});
  const [touched, setTouched] = useState<Record<string, boolean>>({});

  const handleServerErrors = useCallback((apiError: ApiException) => {
    if (apiError.code === 'VALIDATION_ERROR' && apiError.details?.field_errors) {
      setErrors(apiError.details.field_errors);
    }
  }, []);

  const setFieldTouched = useCallback((field: string) => {
    setTouched((prev) => ({ ...prev, [field]: true }));
  }, []);

  return {
    errors,
    touched,
    handleServerErrors,
    setFieldTouched,
  };
}
```

---

## Error Recovery Patterns

### Pattern 1: Automatic Retry

**Use Case**: Transient network errors

**Implementation**:
```typescript
export async function retryRequest<T>(
  request: () => Promise<T>,
  maxRetries = 3
): Promise<T> {
  let lastError: Error | null = null;

  for (let attempt = 0; attempt <= maxRetries; attempt++) {
    try {
      return await request();
    } catch (error) {
      lastError = error as Error;

      // Don't retry on 4xx errors
      if (error instanceof ApiException && error.status >= 400 && error.status < 500) {
        throw error;
      }

      // Wait before retry (exponential backoff)
      if (attempt < maxRetries) {
        await new Promise((resolve) =>
          setTimeout(resolve, Math.pow(2, attempt) * 1000)
        );
      }
    }
  }

  throw lastError || new Error('Request failed after retries');
}
```

### Pattern 2: Manual Retry

**Use Case**: User-initiated retry

**Component**: `ErrorWithRetry`

```typescript
interface ErrorWithRetryProps {
  error: Error;
  onRetry: () => void;
  retryCount?: number;
  maxRetries?: number;
}

export function ErrorWithRetry({
  error,
  onRetry,
  retryCount = 0,
  maxRetries = 3,
}: ErrorWithRetryProps) {
  const canRetry = retryCount < maxRetries;

  return (
    <Alert
      severity="error"
      action={
        canRetry ? (
          <Button onClick={onRetry} size="small">
            Retry
          </Button>
        ) : null
      }
    >
      <AlertTitle>Error</AlertTitle>
      {error.message}
      {!canRetry && (
        <Typography variant="body2" sx={{ mt: 1 }}>
          Maximum retry attempts reached. Please contact support.
        </Typography>
      )}
    </Alert>
  );
}
```

### Pattern 3: Fallback UI

**Use Case**: Show alternative content when error occurs

**Component**: `ErrorBoundaryWithFallback`

```typescript
interface ErrorBoundaryWithFallbackProps {
  children: React.ReactNode;
  fallback: React.ReactNode;
}

export function ErrorBoundaryWithFallback({
  children,
  fallback,
}: ErrorBoundaryWithFallbackProps) {
  return (
    <ErrorBoundary fallback={fallback}>
      {children}
    </ErrorBoundary>
  );
}

// Usage
<ErrorBoundaryWithFallback
  fallback={<EmptyState message="Unable to load content" />}
>
  <AssetList />
</ErrorBoundaryWithFallback>
```

---

## Error Boundary Implementation

### Global Error Boundary

**Component**: `GlobalErrorBoundary`

```typescript
export class GlobalErrorBoundary extends Component<
  { children: React.ReactNode },
  { hasError: boolean; error: Error | null }
> {
  constructor(props: { children: React.ReactNode }) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error) {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    // Log to error tracking service
    console.error('Global error boundary caught error:', error, errorInfo);
    // Send to Sentry, LogRocket, etc.
  }

  handleReset = () => {
    this.setState({ hasError: false, error: null });
  };

  render() {
    if (this.state.hasError) {
      return (
        <Container maxWidth="md" sx={{ mt: 4 }}>
          <Alert severity="error" sx={{ mb: 2 }}>
            <AlertTitle>Something went wrong</AlertTitle>
            {this.state.error?.message || 'An unexpected error occurred'}
          </Alert>
          <Box display="flex" gap={2}>
            <Button variant="contained" onClick={this.handleReset}>
              Try Again
            </Button>
            <Button variant="outlined" onClick={() => window.location.reload()}>
              Reload Page
            </Button>
            <Button
              variant="outlined"
              href="mailto:support@example.com"
            >
              Contact Support
            </Button>
          </Box>
        </Container>
      );
    }

    return this.props.children;
  }
}
```

### Feature-Level Error Boundary

**Component**: `FeatureErrorBoundary`

```typescript
export function FeatureErrorBoundary({
  children,
  feature,
  fallback,
}: {
  children: React.ReactNode;
  feature: string;
  fallback?: React.ReactNode;
}) {
  return (
    <ErrorBoundary
      fallback={
        fallback || (
          <Alert severity="error">
            Unable to load {feature}. Please refresh the page.
          </Alert>
        )
      }
    >
      {children}
    </ErrorBoundary>
  );
}
```

---

## User-Friendly Error Messages

### Error Message Guidelines

1. **Be Specific**: Tell user what went wrong
2. **Be Actionable**: Tell user what they can do
3. **Be Polite**: Use friendly, professional language
4. **Avoid Technical Jargon**: Use plain language
5. **Provide Context**: Explain why error occurred when possible

### Error Message Examples

**Bad**:
- "Error 500"
- "Internal server error"
- "Failed"

**Good**:
- "We couldn't save your changes. Please try again in a moment."
- "This asset is being used by another process. Please try again later."
- "Your session has expired. Please sign in again to continue."

### Error Message Templates

```typescript
const ERROR_MESSAGE_TEMPLATES = {
  NETWORK_ERROR: "We're having trouble connecting. Please check your internet connection and try again.",
  TIMEOUT: "The request took too long. Please try again.",
  NOT_FOUND: "We couldn't find what you're looking for. It may have been moved or deleted.",
  VALIDATION_ERROR: "Please check your input. Some fields need to be corrected.",
  PERMISSION_DENIED: "You don't have permission to perform this action. Contact your administrator if you need access.",
  SERVER_ERROR: "Something went wrong on our end. We've been notified and are working on it. Please try again in a few moments.",
};
```

---

## Error Logging and Monitoring

### Error Tracking Integration

**Implementation**:
```typescript
import * as Sentry from '@sentry/react';

export function logError(error: Error, context?: Record<string, any>) {
  // Log to console in development
  if (import.meta.env.DEV) {
    console.error('Error:', error, context);
  }

  // Send to error tracking service
  Sentry.captureException(error, {
    extra: context,
  });
}

// Usage in error boundaries
componentDidCatch(error: Error, errorInfo: ErrorInfo) {
  logError(error, {
    componentStack: errorInfo.componentStack,
    errorBoundary: this.constructor.name,
  });
}
```

---

## Best Practices

1. **Always show errors**: Don't silently fail
2. **Provide recovery options**: Give users ways to fix errors
3. **Log errors**: Track errors for debugging
4. **Test error states**: Test all error scenarios
5. **Graceful degradation**: App should work even with errors
6. **User feedback**: Always provide user feedback
7. **Error boundaries**: Use error boundaries to prevent crashes
8. **Retry logic**: Implement smart retry logic
9. **Offline support**: Handle offline scenarios gracefully
10. **Accessibility**: Errors must be accessible to all users

---

**Last Updated**: 2026-03-22  
**Version**: 1.0.0


---

# Frontend Architecture

**Last Updated**: 2026-03-22  
**Version**: 1.0.0

---

## Table of Contents

1. [Overview](#overview)
2. [Technology Stack](#technology-stack)
3. [Project Structure](#project-structure)
4. [Architecture Patterns](#architecture-patterns)
5. [State Management](#state-management)
6. [API Integration](#api-integration)
7. [Routing](#routing)
8. [Authentication](#authentication)
9. [Error Handling](#error-handling)
10. [Performance Optimization](#performance-optimization)
11. [Testing Strategy](#testing-strategy)
12. [Build and Deployment](#build-and-deployment)

---

## Overview

This document describes the frontend architecture for the Interoperable Data Hub platform. The frontend is built as a modern single-page application (SPA) with a focus on performance, maintainability, and user experience.

**Architecture Principles**:
- **Component-Based**: Reusable, composable components
- **Type-Safe**: TypeScript for type safety
- **Performance-First**: Optimized for fast load times and smooth interactions
- **Accessible**: WCAG 2.1 AA compliant
- **Maintainable**: Clear structure and documentation

---

## Technology Stack

### Core Framework

**React 18+**
- Modern React with hooks
- Concurrent features (Suspense, Transitions)
- Server Components (future)

**TypeScript 5+**
- Type safety
- Better IDE support
- Refactoring safety

### UI Library

**Material-UI (MUI) v5+** (or similar)
- Comprehensive component library
- Theming support
- Accessibility built-in
- Customizable design system

**Alternative Options**:
- Chakra UI
- Ant Design
- Custom component library

### State Management

**Redux Toolkit** (or Zustand)
- Centralized state management
- DevTools support
- Middleware for async actions
- RTK Query for API state

**Alternative**: Zustand for simpler state needs

### Routing

**React Router v6+**
- Declarative routing
- Code splitting
- Protected routes
- Nested routes

### API Client

**React Query (TanStack Query)**
- Server state management
- Caching and synchronization
- Optimistic updates
- Background refetching

**Axios**
- HTTP client
- Request/response interceptors
- Error handling

### Styling

**Emotion** (CSS-in-JS)
- Component-scoped styles
- Theme integration
- Dynamic styling

**Alternative**: Tailwind CSS

### Build Tools

**Vite**
- Fast development server
- Optimized production builds
- HMR (Hot Module Replacement)

**Alternative**: Create React App, Next.js

### Testing

**Jest**
- Unit testing
- Snapshot testing
- Mocking

**React Testing Library**
- Component testing
- User-centric testing
- Accessibility testing

**Cypress** (or Playwright)
- E2E testing
- Integration testing

### Development Tools

**ESLint**
- Code linting
- TypeScript support

**Prettier**
- Code formatting

**Storybook**
- Component documentation
- Component testing
- Design system showcase

---

## Project Structure

```
frontend/
├── public/                 # Static assets
│   ├── favicon.ico
│   └── assets/
├── src/
│   ├── components/         # Reusable components
│   │   ├── common/        # Common components (Button, Input, etc.)
│   │   ├── layout/        # Layout components (Header, Sidebar, etc.)
│   │   └── features/      # Feature-specific components
│   ├── pages/             # Page components
│   │   ├── assets/
│   │   ├── contracts/
│   │   ├── marketplace/
│   │   └── admin/
│   ├── features/           # Feature modules
│   │   ├── assets/
│   │   │   ├── components/
│   │   │   ├── hooks/
│   │   │   ├── services/
│   │   │   └── types.ts
│   │   ├── contracts/
│   │   └── marketplace/
│   ├── hooks/              # Custom React hooks
│   ├── services/           # API services
│   │   ├── api/
│   │   ├── auth/
│   │   └── storage/
│   ├── store/              # Redux store
│   │   ├── slices/
│   │   ├── middleware/
│   │   └── store.ts
│   ├── utils/              # Utility functions
│   ├── types/              # TypeScript types
│   ├── theme/              # Theme configuration
│   │   ├── colors.ts
│   │   ├── typography.ts
│   │   └── theme.ts
│   ├── App.tsx             # Root component
│   ├── index.tsx           # Entry point
│   └── routes.tsx          # Route configuration
├── .env                    # Environment variables
├── .eslintrc.js           # ESLint config
├── .prettierrc            # Prettier config
├── package.json
├── tsconfig.json          # TypeScript config
├── vite.config.ts         # Vite config
└── README.md
```

---

## Architecture Patterns

### Feature-Based Structure

Organize code by feature rather than by type:

```
features/
  assets/
    components/     # Asset-specific components
    hooks/          # Asset-specific hooks
    services/       # Asset API services
    types.ts        # Asset types
    index.ts        # Public exports
```

**Benefits**:
- Co-located related code
- Easier to find and maintain
- Clear feature boundaries
- Better code splitting

---

### Component Composition

Build complex components from simple ones:

```tsx
// Simple components
<Button />
<Icon />
<Text />

// Composed components
<IconButton icon={<Icon />} label="Save" />
<Card>
  <CardHeader title="Asset" />
  <CardContent>
    <Text>Content</Text>
  </CardContent>
</Card>
```

---

### Container/Presenter Pattern

Separate logic from presentation:

```tsx
// Container (logic)
const AssetListContainer = () => {
  const { data, isLoading } = useAssets();
  const handleDelete = useDeleteAsset();
  
  return <AssetList data={data} loading={isLoading} onDelete={handleDelete} />;
};

// Presenter (UI)
const AssetList = ({ data, loading, onDelete }) => {
  // Pure presentation logic
};
```

---

## State Management

### Server State (React Query)

Use React Query for server state:

```tsx
// Query
const { data, isLoading } = useQuery({
  queryKey: ['assets'],
  queryFn: () => api.getAssets()
});

// Mutation
const mutation = useMutation({
  mutationFn: (asset) => api.createAsset(asset),
  onSuccess: () => {
    queryClient.invalidateQueries(['assets']);
  }
});
```

### Client State (Redux/Zustand)

Use Redux for global client state:

```tsx
// Slice
const authSlice = createSlice({
  name: 'auth',
  initialState: { user: null, token: null },
  reducers: {
    setUser: (state, action) => {
      state.user = action.payload;
    }
  }
});

// Usage
const user = useSelector(state => state.auth.user);
dispatch(setUser(userData));
```

### Local State (useState)

Use useState for component-local state:

```tsx
const [isOpen, setIsOpen] = useState(false);
```

---

## API Integration

### API Client Setup

```tsx
// api/client.ts
import axios from 'axios';

const apiClient = axios.create({
  baseURL: process.env.REACT_APP_API_URL,
  headers: {
    'Content-Type': 'application/json'
  }
});

// Request interceptor (add auth token)
apiClient.interceptors.request.use((config) => {
  const token = getAuthToken();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Response interceptor (handle errors)
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      // Handle unauthorized
      logout();
    }
    return Promise.reject(error);
  }
);
```

### API Services

```tsx
// services/assets.ts
export const assetService = {
  getAssets: () => apiClient.get('/api/v1/assets'),
  getAsset: (id: string) => apiClient.get(`/api/v1/assets/${id}`),
  createAsset: (data: Asset) => apiClient.post('/api/v1/assets', data),
  updateAsset: (id: string, data: Asset) => 
    apiClient.put(`/api/v1/assets/${id}`, data),
  deleteAsset: (id: string) => apiClient.delete(`/api/v1/assets/${id}`)
};
```

### React Query Integration

```tsx
// hooks/useAssets.ts
export const useAssets = () => {
  return useQuery({
    queryKey: ['assets'],
    queryFn: () => assetService.getAssets()
  });
};

export const useCreateAsset = () => {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: assetService.createAsset,
    onSuccess: () => {
      queryClient.invalidateQueries(['assets']);
    }
  });
};
```

---

## Routing

### Route Configuration

```tsx
// routes.tsx
import { Routes, Route } from 'react-router-dom';

export const AppRoutes = () => {
  return (
    <Routes>
      <Route path="/" element={<Dashboard />} />
      <Route path="/assets" element={<AssetList />} />
      <Route path="/assets/:id" element={<AssetDetail />} />
      <Route path="/assets/new" element={<AssetCreate />} />
      <Route path="/marketplace" element={<Marketplace />} />
      <Route path="/admin/*" element={<AdminRoutes />} />
    </Routes>
  );
};
```

### Protected Routes

```tsx
// components/ProtectedRoute.tsx
const ProtectedRoute = ({ children, requiredRole }) => {
  const { user, isAuthenticated } = useAuth();
  
  if (!isAuthenticated) {
    return <Navigate to="/login" />;
  }
  
  if (requiredRole && !hasRole(user, requiredRole)) {
    return <Navigate to="/unauthorized" />;
  }
  
  return children;
};

// Usage
<Route
  path="/admin"
  element={
    <ProtectedRoute requiredRole="TENANT_ADMIN">
      <AdminPanel />
    </ProtectedRoute>
  }
/>
```

---

## Authentication

### Auth Context

```tsx
// contexts/AuthContext.tsx
const AuthContext = createContext();

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [token, setToken] = useState(localStorage.getItem('token'));
  
  const login = async (email, password) => {
    const response = await authService.login(email, password);
    setToken(response.token);
    setUser(response.user);
    localStorage.setItem('token', response.token);
  };
  
  const logout = () => {
    setToken(null);
    setUser(null);
    localStorage.removeItem('token');
  };
  
  return (
    <AuthContext.Provider value={{ user, token, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
};
```

### Auth Hook

```tsx
// hooks/useAuth.ts
export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within AuthProvider');
  }
  return context;
};
```

---

## Error Handling

### Error Boundary

```tsx
// components/ErrorBoundary.tsx
class ErrorBoundary extends React.Component {
  state = { hasError: false, error: null };
  
  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }
  
  componentDidCatch(error, errorInfo) {
    // Log to error reporting service
    console.error('Error caught:', error, errorInfo);
  }
  
  render() {
    if (this.state.hasError) {
      return <ErrorFallback error={this.state.error} />;
    }
    return this.props.children;
  }
}
```

### API Error Handling

```tsx
// utils/errorHandler.ts
export const handleApiError = (error: AxiosError) => {
  if (error.response) {
    // Server responded with error
    const { status, data } = error.response;
    
    switch (status) {
      case 400:
        return 'Invalid request. Please check your input.';
      case 401:
        return 'Unauthorized. Please log in.';
      case 403:
        return 'You do not have permission to perform this action.';
      case 404:
        return 'Resource not found.';
      case 500:
        return 'Server error. Please try again later.';
      default:
        return data?.message || 'An error occurred.';
    }
  }
  
  return 'Network error. Please check your connection.';
};
```

---

## Performance Optimization

### Code Splitting

```tsx
// Lazy load routes
const AssetDetail = lazy(() => import('./pages/AssetDetail'));
const AdminPanel = lazy(() => import('./pages/AdminPanel'));

// Usage with Suspense
<Suspense fallback={<LoadingSpinner />}>
  <AssetDetail />
</Suspense>
```

### Memoization

```tsx
// Memoize expensive components
const ExpensiveComponent = memo(({ data }) => {
  // Expensive rendering
});

// Memoize callbacks
const handleClick = useCallback(() => {
  // Handler logic
}, [dependencies]);

// Memoize computed values
const expensiveValue = useMemo(() => {
  return computeExpensiveValue(data);
}, [data]);
```

### Virtual Scrolling

For long lists:

```tsx
import { FixedSizeList } from 'react-window';

<FixedSizeList
  height={600}
  itemCount={items.length}
  itemSize={50}
>
  {({ index, style }) => (
    <div style={style}>
      {items[index]}
    </div>
  )}
</FixedSizeList>
```

---

## Testing Strategy

### Unit Tests

```tsx
// components/Button.test.tsx
import { render, screen, fireEvent } from '@testing-library/react';
import { Button } from './Button';

test('renders button with text', () => {
  render(<Button>Click me</Button>);
  expect(screen.getByText('Click me')).toBeInTheDocument();
});

test('calls onClick when clicked', () => {
  const handleClick = jest.fn();
  render(<Button onClick={handleClick}>Click me</Button>);
  fireEvent.click(screen.getByText('Click me'));
  expect(handleClick).toHaveBeenCalledTimes(1);
});
```

### Integration Tests

```tsx
// features/assets/AssetList.test.tsx
test('loads and displays assets', async () => {
  render(<AssetList />);
  
  // Wait for data to load
  await waitFor(() => {
    expect(screen.getByText('Asset 1')).toBeInTheDocument();
  });
});
```

### E2E Tests

```tsx
// cypress/integration/assets.spec.ts
describe('Asset Management', () => {
  it('creates a new asset', () => {
    cy.visit('/assets');
    cy.get('[data-testid="new-asset-button"]').click();
    cy.get('[data-testid="asset-name-input"]').type('Test Asset');
    cy.get('[data-testid="submit-button"]').click();
    cy.contains('Asset created successfully').should('be.visible');
  });
});
```

---

## Build and Deployment

### Environment Variables

```bash
# .env.development
REACT_APP_API_URL=http://localhost:8000/api/v1
REACT_APP_ENV=development

# .env.production
REACT_APP_API_URL=https://api.hub.example.com/api/v1
REACT_APP_ENV=production
```

### Build Process

```bash
# Development
npm run dev

# Production build
npm run build

# Preview production build
npm run preview
```

### Deployment

- **Static Hosting**: Deploy to CDN (CloudFront, Cloudflare)
- **Container**: Docker container with Nginx
- **CI/CD**: Automated builds and deployments

---

**Last Updated**: 2026-03-22  
**Version**: 1.0.0


---

# Internationalization (i18n) Guide

**Last Updated**: 2026-03-22  
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

**Last Updated**: 2026-03-22  
**Version**: 1.0.0


---

# Performance Optimization Guide

**Last Updated**: 2026-03-22  
**Version**: 1.0.0

---

## Table of Contents

1. [Overview](#overview)
2. [Performance Targets](#performance-targets)
3. [Code Splitting](#code-splitting)
4. [Lazy Loading](#lazy-loading)
5. [Image Optimization](#image-optimization)
6. [Bundle Optimization](#bundle-optimization)
7. [Caching Strategies](#caching-strategies)
8. [Virtual Scrolling](#virtual-scrolling)
9. [Memoization](#memoization)
10. [Performance Monitoring](#performance-monitoring)

---

## Overview

This document outlines performance optimization strategies for the frontend application. The goal is to achieve fast load times, smooth interactions, and efficient resource usage.

**Performance Principles**:
- **Fast Initial Load**: First Contentful Paint < 1.5s
- **Interactive Quickly**: Time to Interactive < 3s
- **Smooth Interactions**: 60fps animations
- **Efficient Updates**: Minimal re-renders
- **Optimized Assets**: Compressed images, minified code

**Key Metrics**:
- **Lighthouse Score**: 90+ (Performance)
- **First Contentful Paint (FCP)**: < 1.5s
- **Largest Contentful Paint (LCP)**: < 2.5s
- **Time to Interactive (TTI)**: < 3s
- **Cumulative Layout Shift (CLS)**: < 0.1
- **First Input Delay (FID)**: < 100ms

---

## Performance Targets

### Load Time Targets

- **Initial Load**: < 2s
- **Route Navigation**: < 500ms
- **API Response**: < 300ms (P95)
- **Image Load**: < 1s

### Runtime Performance Targets

- **Frame Rate**: 60fps
- **Component Render**: < 16ms
- **List Scroll**: Smooth, no jank
- **Form Input**: < 50ms response time

### Bundle Size Targets

- **Initial Bundle**: < 200KB (gzipped)
- **Total Bundle**: < 500KB (gzipped)
- **Route Chunks**: < 50KB each (gzipped)
- **Vendor Bundle**: < 150KB (gzipped)

---

## Code Splitting

### Route-Based Code Splitting

**Implementation**: `src/routes/index.tsx`

```typescript
import { lazy } from 'react';
import { Route, Routes } from 'react-router-dom';

// Lazy load routes
const AssetsPage = lazy(() => import('@/pages/AssetsPage'));
const ContractsPage = lazy(() => import('@/pages/ContractsPage'));
const MarketplacePage = lazy(() => import('@/pages/MarketplacePage'));
const CompliancePage = lazy(() => import('@/pages/CompliancePage'));

export function AppRoutes() {
  return (
    <Suspense fallback={<PageLoader />}>
      <Routes>
        <Route path="/assets" element={<AssetsPage />} />
        <Route path="/contracts" element={<ContractsPage />} />
        <Route path="/marketplace" element={<MarketplacePage />} />
        <Route path="/compliance" element={<CompliancePage />} />
      </Routes>
    </Suspense>
  );
}
```

### Component-Based Code Splitting

**Implementation**: `src/components/LazyComponents.tsx`

```typescript
import { lazy } from 'react';

// Heavy components loaded on demand
export const ContractEditor = lazy(() => import('./ContractEditor'));
export const DataQualityDashboard = lazy(() => import('./DataQualityDashboard'));
export const ComplianceReport = lazy(() => import('./ComplianceReport'));

// Usage with Suspense
<Suspense fallback={<ComponentLoader />}>
  <ContractEditor contractId={id} />
</Suspense>
```

### Library Splitting

**Implementation**: `vite.config.ts`

```typescript
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  build: {
    rollupOptions: {
      output: {
        manualChunks: {
          'react-vendor': ['react', 'react-dom', 'react-router-dom'],
          'mui-vendor': ['@mui/material', '@mui/icons-material'],
          'query-vendor': ['@tanstack/react-query'],
          'graphql-vendor': ['graphql', 'graphql-request'],
        },
      },
    },
  },
});
```

---

## Lazy Loading

### Image Lazy Loading

**Component**: `LazyImage`

```typescript
interface LazyImageProps {
  src: string;
  alt: string;
  width?: number;
  height?: number;
  placeholder?: string;
}

export function LazyImage({
  src,
  alt,
  width,
  height,
  placeholder,
}: LazyImageProps) {
  const [loaded, setLoaded] = useState(false);
  const [error, setError] = useState(false);

  return (
    <Box
      sx={{
        width,
        height,
        position: 'relative',
        backgroundColor: 'grey.200',
      }}
    >
      {!loaded && placeholder && (
        <img
          src={placeholder}
          alt=""
          style={{
            position: 'absolute',
            width: '100%',
            height: '100%',
            objectFit: 'cover',
          }}
        />
      )}
      <img
        src={src}
        alt={alt}
        loading="lazy"
        onLoad={() => setLoaded(true)}
        onError={() => setError(true)}
        style={{
          width: '100%',
          height: '100%',
          objectFit: 'cover',
          opacity: loaded ? 1 : 0,
          transition: 'opacity 0.3s',
        }}
      />
      {error && (
        <Box
          sx={{
            position: 'absolute',
            inset: 0,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}
        >
          <Typography variant="body2" color="error">
            Failed to load image
          </Typography>
        </Box>
      )}
    </Box>
  );
}
```

### Component Lazy Loading with Intersection Observer

**Hook**: `useIntersectionObserver`

```typescript
export function useIntersectionObserver(
  ref: RefObject<HTMLElement>,
  options?: IntersectionObserverInit
) {
  const [isIntersecting, setIsIntersecting] = useState(false);

  useEffect(() => {
    const element = ref.current;
    if (!element) return;

    const observer = new IntersectionObserver(([entry]) => {
      setIsIntersecting(entry.isIntersecting);
    }, options);

    observer.observe(element);

    return () => {
      observer.unobserve(element);
    };
  }, [ref, options]);

  return isIntersecting;
}
```

**Usage**:
```typescript
function AssetList() {
  const loadMoreRef = useRef<HTMLDivElement>(null);
  const isIntersecting = useIntersectionObserver(loadMoreRef);

  useEffect(() => {
    if (isIntersecting && hasNextPage) {
      fetchNextPage();
    }
  }, [isIntersecting, hasNextPage, fetchNextPage]);

  return (
    <>
      {assets.map(asset => <AssetCard key={asset.id} asset={asset} />)}
      <div ref={loadMoreRef} />
    </>
  );
}
```

---

## Image Optimization

### Image Optimization Strategy

1. **Format Selection**:
   - Use WebP with fallback to JPEG/PNG
   - Use SVG for icons and simple graphics
   - Use responsive images with `srcset`

2. **Compression**:
   - Compress images before upload
   - Use CDN for image delivery
   - Serve different sizes for different viewports

3. **Lazy Loading**:
   - Load images only when visible
   - Use placeholder images
   - Progressive image loading

**Component**: `OptimizedImage`

```typescript
interface OptimizedImageProps {
  src: string;
  alt: string;
  width: number;
  height: number;
  sizes?: string;
  srcSet?: string;
}

export function OptimizedImage({
  src,
  alt,
  width,
  height,
  sizes,
  srcSet,
}: OptimizedImageProps) {
  return (
    <picture>
      <source srcSet={srcSet} type="image/webp" />
      <img
        src={src}
        alt={alt}
        width={width}
        height={height}
        sizes={sizes}
        loading="lazy"
        decoding="async"
      />
    </picture>
  );
}
```

---

## Bundle Optimization

### Tree Shaking

**Configuration**: `vite.config.ts`

```typescript
export default defineConfig({
  build: {
    rollupOptions: {
      treeshake: {
        moduleSideEffects: false,
      },
    },
  },
});
```

### Import Optimization

**Bad**:
```typescript
import * as MUI from '@mui/material';
```

**Good**:
```typescript
import { Button, TextField } from '@mui/material';
```

### Dynamic Imports

**Implementation**:
```typescript
// Load heavy library only when needed
const loadChartLibrary = async () => {
  const { Chart } = await import('chart.js');
  return Chart;
};

// Usage
const Chart = await loadChartLibrary();
```

---

## Caching Strategies

### React Query Caching

**Configuration**:
```typescript
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 5 * 60 * 1000, // 5 minutes
      cacheTime: 10 * 60 * 1000, // 10 minutes
    },
  },
});
```

### Browser Caching

**Service Worker**: `public/sw.js`

```javascript
const CACHE_NAME = 'datahub-v1';
const urlsToCache = [
  '/',
  '/static/css/main.css',
  '/static/js/main.js',
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll(urlsToCache);
    })
  );
});

self.addEventListener('fetch', (event) => {
  event.respondWith(
    caches.match(event.request).then((response) => {
      return response || fetch(event.request);
    })
  );
});
```

---

## Virtual Scrolling

### Virtual List Component

**Component**: `VirtualList`

```typescript
import { useVirtualizer } from '@tanstack/react-virtual';

interface VirtualListProps<T> {
  items: T[];
  itemHeight: number;
  renderItem: (item: T, index: number) => React.ReactNode;
}

export function VirtualList<T>({
  items,
  itemHeight,
  renderItem,
}: VirtualListProps<T>) {
  const parentRef = useRef<HTMLDivElement>(null);

  const virtualizer = useVirtualizer({
    count: items.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => itemHeight,
    overscan: 5,
  });

  return (
    <div
      ref={parentRef}
      style={{
        height: '600px',
        overflow: 'auto',
      }}
    >
      <div
        style={{
          height: `${virtualizer.getTotalSize()}px`,
          width: '100%',
          position: 'relative',
        }}
      >
        {virtualizer.getVirtualItems().map((virtualItem) => (
          <div
            key={virtualItem.key}
            style={{
              position: 'absolute',
              top: 0,
              left: 0,
              width: '100%',
              height: `${virtualItem.size}px`,
              transform: `translateY(${virtualItem.start}px)`,
            }}
          >
            {renderItem(items[virtualItem.index], virtualItem.index)}
          </div>
        ))}
      </div>
    </div>
  );
}
```

**Usage**:
```typescript
<VirtualList
  items={assets}
  itemHeight={100}
  renderItem={(asset, index) => (
    <AssetCard key={asset.id} asset={asset} />
  )}
/>
```

---

## Memoization

### React.memo

**Usage**:
```typescript
export const AssetCard = React.memo(function AssetCard({
  asset,
  onEdit,
}: AssetCardProps) {
  return (
    <Card>
      <CardContent>
        <Typography>{asset.name}</Typography>
        <Button onClick={() => onEdit(asset.id)}>Edit</Button>
      </CardContent>
    </Card>
  );
}, (prevProps, nextProps) => {
  // Custom comparison
  return (
    prevProps.asset.id === nextProps.asset.id &&
    prevProps.asset.name === nextProps.asset.name
  );
});
```

### useMemo

**Usage**:
```typescript
function AssetList({ assets, filters }: AssetListProps) {
  const filteredAssets = useMemo(() => {
    return assets.filter(asset => {
      if (filters.status && asset.status !== filters.status) {
        return false;
      }
      if (filters.search && !asset.name.includes(filters.search)) {
        return false;
      }
      return true;
    });
  }, [assets, filters]);

  return (
    <div>
      {filteredAssets.map(asset => (
        <AssetCard key={asset.id} asset={asset} />
      ))}
    </div>
  );
}
```

### useCallback

**Usage**:
```typescript
function AssetCard({ asset, onEdit }: AssetCardProps) {
  const handleEdit = useCallback(() => {
    onEdit(asset.id);
  }, [asset.id, onEdit]);

  return (
    <Card>
      <Button onClick={handleEdit}>Edit</Button>
    </Card>
  );
}
```

---

## Performance Monitoring

### Web Vitals Monitoring

**Implementation**: `src/lib/performance/vitals.ts`

```typescript
import { onCLS, onFID, onFCP, onLCP, onTTFB } from 'web-vitals';

function sendToAnalytics(metric: any) {
  // Send to analytics service
  console.log(metric);
}

export function trackWebVitals() {
  onCLS(sendToAnalytics);
  onFID(sendToAnalytics);
  onFCP(sendToAnalytics);
  onLCP(sendToAnalytics);
  onTTFB(sendToAnalytics);
}
```

### Performance Monitoring Hook

**Hook**: `usePerformanceMonitoring`

```typescript
export function usePerformanceMonitoring() {
  useEffect(() => {
    // Monitor component render time
    const observer = new PerformanceObserver((list) => {
      for (const entry of list.getEntries()) {
        if (entry.entryType === 'measure') {
          console.log(`${entry.name}: ${entry.duration}ms`);
        }
      }
    });

    observer.observe({ entryTypes: ['measure'] });

    return () => {
      observer.disconnect();
    };
  }, []);
}
```

### Bundle Analysis

**Tool**: `vite-bundle-visualizer`

**Configuration**:
```typescript
import { visualizer } from 'rollup-plugin-visualizer';

export default defineConfig({
  plugins: [
    react(),
    visualizer({
      open: true,
      gzipSize: true,
      brotliSize: true,
    }),
  ],
});
```

---

## Best Practices

1. **Code Split by Route**: Split code at route level
2. **Lazy Load Heavy Components**: Load on demand
3. **Optimize Images**: Use WebP, compress, lazy load
4. **Minimize Bundle Size**: Tree shake, optimize imports
5. **Use Memoization**: Memoize expensive computations
6. **Virtual Scrolling**: For long lists
7. **Cache Aggressively**: Cache API responses
8. **Monitor Performance**: Track Web Vitals
9. **Optimize Fonts**: Use font-display: swap
10. **Preload Critical Resources**: Preload key assets

---

**Last Updated**: 2026-03-22  
**Version**: 1.0.0


---

# UI/UX Documentation

**Last Updated**: 2026-03-22  
**Version**: 2.0.0

---

## Table of Contents

1. [Overview](#overview)
2. [Core Design Documentation](#core-design-documentation)
3. [Implementation Guides](#implementation-guides)
4. [Development Documentation](#development-documentation)
5. [Documentation Status](#documentation-status)
6. [Quick Links](#quick-links)

---

## Overview

This directory contains comprehensive UI/UX and frontend design documentation for the Interoperable Data Hub platform. The documentation covers design principles, design system, component library, user interface specifications, UX patterns, frontend architecture, responsive design, accessibility guidelines, and comprehensive implementation guides.

**Documentation Structure**:

### Core Design Documentation

- **[Design Principles and Guidelines](./DESIGN_PRINCIPLES.md)** - Core design principles, user experience guidelines, and design philosophy
- **[Design System](./DESIGN_SYSTEM.md)** - Colors, typography, spacing, icons, and visual design tokens
- **[Component Library](./COMPONENT_LIBRARY.md)** - Complete catalog of UI components with specifications
- **[User Interface Specifications](./UI_SPECIFICATIONS.md)** - Detailed UI specifications for all personas and use cases
- **[UX Patterns and Interactions](./UX_PATTERNS.md)** - Common UX patterns, interaction design, and best practices
- **[Frontend Architecture](./FRONTEND_ARCHITECTURE.md)** - Frontend technology stack, architecture, and development guidelines
- **[Responsive Design](./RESPONSIVE_DESIGN.md)** - Responsive design guidelines, breakpoints, and mobile-first approach
- **[Accessibility Guidelines](./ACCESSIBILITY.md)** - WCAG compliance, accessibility patterns, and inclusive design
- **[Contract Editor Specification](./CONTRACT_EDITOR_SPECIFICATION.md)** - Comprehensive specification for the custom contract editor component

### Implementation Guides

- **[API Integration Guide](./API_INTEGRATION.md)** - Complete guide for integrating with backend APIs (REST, GraphQL, WebSocket)
- **[Authentication UI Specifications](./AUTHENTICATION_UI.md)** - Authentication flows, login, registration, SSO, MFA
- **[Real-Time Features UI Patterns](./REALTIME_FEATURES.md)** - WebSocket integration, live updates, notifications
- **[Error Handling UI Patterns](./ERROR_HANDLING_UI.md)** - Comprehensive error handling, recovery patterns, offline mode
- **[Testing Strategy](./TESTING_STRATEGY.md)** - Frontend testing strategy, unit, component, E2E, visual regression
- **[Performance Optimization](./PERFORMANCE_OPTIMIZATION.md)** - Code splitting, lazy loading, bundle optimization, caching
- **[Internationalization (i18n)](./INTERNATIONALIZATION.md)** - Multi-language support, locale formatting, RTL support
- **[Analytics Integration](./ANALYTICS_INTEGRATION.md)** - Event tracking, error monitoring, performance metrics
- **[Frontend Deployment](./DEPLOYMENT.md)** - Docker, Kubernetes, CI/CD, CDN strategy, version management
- **[Developer Experience](./DEVELOPER_EXPERIENCE.md)** - Development setup, workflows, component development, debugging

---

## Documentation Status

✅ **Complete**: All UI/UX documentation has been created and is ready for implementation.

**Total Documentation**:
- **20 comprehensive documents**
- **~15,000+ lines of documentation**
- **Covers all aspects of UI/UX, frontend design, and implementation**
- **Includes detailed implementation guides for all critical areas**

---

## Quick Links

### For Designers
- **Design System**: [Design System Documentation](./DESIGN_SYSTEM.md)
- **Components**: [Component Library](./COMPONENT_LIBRARY.md)
- **UI Specs**: [User Interface Specifications](./UI_SPECIFICATIONS.md)
- **UX Patterns**: [UX Patterns and Interactions](./UX_PATTERNS.md)
- **Accessibility**: [Accessibility Guidelines](./ACCESSIBILITY.md)

### For Developers
- **Frontend Architecture**: [Frontend Architecture](./FRONTEND_ARCHITECTURE.md)
- **API Integration**: [API Integration Guide](./API_INTEGRATION.md)
- **Authentication**: [Authentication UI Specifications](./AUTHENTICATION_UI.md)
- **Testing**: [Testing Strategy](./TESTING_STRATEGY.md)
- **Performance**: [Performance Optimization](./PERFORMANCE_OPTIMIZATION.md)
- **Deployment**: [Frontend Deployment](./DEPLOYMENT.md)
- **Developer Guide**: [Developer Experience](./DEVELOPER_EXPERIENCE.md)

### For Implementation
- **Real-Time Features**: [Real-Time Features UI Patterns](./REALTIME_FEATURES.md)
- **Error Handling**: [Error Handling UI Patterns](./ERROR_HANDLING_UI.md)
- **Internationalization**: [Internationalization Guide](./INTERNATIONALIZATION.md)
- **Analytics**: [Analytics Integration](./ANALYTICS_INTEGRATION.md)
- **Contract Editor**: [Contract Editor Specification](./CONTRACT_EDITOR_SPECIFICATION.md)

---

## Design Philosophy

The Interoperable Data Hub UI is designed with the following principles:

1. **User-Centered**: Every design decision prioritizes user needs and goals
2. **Accessible**: Inclusive design that works for all users
3. **Consistent**: Unified design language across all interfaces
4. **Efficient**: Streamlined workflows that reduce cognitive load
5. **Trustworthy**: Clear feedback and transparent processes
6. **Scalable**: Design system that grows with the platform

---

## Target Personas

The UI is designed to serve multiple personas:

- **Data Product Owner**: Web UI for asset management and publishing
- **Data Engineer**: API-first with UI for monitoring and debugging
- **Compliance Officer**: Dashboards and reports for compliance management
- **Data Consumer**: Marketplace UI for discovery and purchase
- **Tenant Admin**: Admin UI for tenant management
- **Platform Admin**: Platform-wide admin UI
- **External Developer**: API documentation and developer tools

---

## Technology Stack (Planned)

- **Framework**: React 18+ with TypeScript
- **UI Library**: Material-UI (MUI) or similar component library
- **State Management**: Redux Toolkit or Zustand
- **Routing**: React Router
- **API Client**: Axios or React Query
- **Styling**: CSS-in-JS (Emotion) or Tailwind CSS
- **Testing**: Jest, React Testing Library
- **Build Tool**: Vite or Create React App

---

## Design Resources

### Design Tools

- **Figma**: Primary design tool for mockups and prototypes
- **Storybook**: Component documentation and testing
- **Design Tokens**: JSON-based design tokens for consistency

### Design Assets

- **Icons**: Material Icons or custom icon set
- **Illustrations**: Custom illustrations for empty states and onboarding
- **Brand Assets**: Logo, color palette, typography

---

## Contributing to UI Documentation

To update UI documentation:

1. Edit the relevant `.md` file in `docs/UI/`
2. Update design mockups in Figma (if applicable)
3. Update component documentation in Storybook
4. Update version and date
5. Submit PR with documentation changes

---

---

## Documentation Coverage

### ✅ Complete Coverage

The UI/UX documentation now provides comprehensive coverage for:

1. **Design Foundation** (100%)
   - Design principles and philosophy
   - Complete design system with tokens
   - Comprehensive component library
   - UI specifications for all personas

2. **Implementation Guides** (100%)
   - API integration (REST, GraphQL, WebSocket)
   - Authentication flows and UI
   - Real-time features and WebSocket patterns
   - Error handling and recovery
   - Testing strategy (unit, component, E2E)
   - Performance optimization
   - Internationalization
   - Analytics integration
   - Deployment strategies

3. **Development Resources** (100%)
   - Developer experience guide
   - Component development workflows
   - Code style guidelines
   - Git workflow
   - Debugging guides

### 📋 Ready for Implementation

All documentation is **engineering-grade** and ready for implementation planning:
- ✅ Complete API integration patterns
- ✅ Authentication UI specifications
- ✅ Real-time features implementation
- ✅ Comprehensive error handling
- ✅ Full testing strategy
- ✅ Performance optimization guide
- ✅ Deployment configurations
- ✅ Developer onboarding materials

---

**Last Updated**: 2026-03-22  
**Version**: 2.0.0


---

# Real-Time Features UI Patterns

**Last Updated**: 2026-03-22  
**Version**: 1.0.0

---

## Table of Contents

1. [Overview](#overview)
2. [WebSocket Connection Status](#websocket-connection-status)
3. [Real-Time Notifications](#real-time-notifications)
4. [Live Job Status Updates](#live-job-status-updates)
5. [Real-Time Collaboration](#real-time-collaboration)
6. [Connection Management](#connection-management)
7. [Reconnection Handling](#reconnection-handling)
8. [Event Subscription Patterns](#event-subscription-patterns)

---

## Overview

This document describes UI patterns and components for real-time features in the Interoperable Data Hub platform. Real-time features are powered by WebSocket connections and provide live updates for jobs, workflows, assets, contracts, and system events.

**Real-Time Features**:
- Job status updates
- Workflow progress tracking
- Asset/contract change notifications
- System event notifications
- Live collaboration indicators
- Real-time data quality results

**Key Principles**:
- Always show connection status
- Graceful degradation when offline
- Automatic reconnection
- Clear visual feedback
- Non-intrusive notifications

---

## WebSocket Connection Status

### Connection Status Indicator Component

**Component**: `ConnectionStatusIndicator`

**Purpose**: Show WebSocket connection status to users

**Layout**:
```
┌─────────────────────────────────────────┐
│ Header                                  │
│  [Logo] [Nav] ... [User] [🟢 Connected]│
└─────────────────────────────────────────┘
```

**States**:
- **Connected**: Green dot, "Connected"
- **Connecting**: Yellow dot, "Connecting..."
- **Disconnected**: Red dot, "Disconnected"
- **Reconnecting**: Yellow dot, "Reconnecting... (attempt 2/5)"

**Component Specification**:
```typescript
interface ConnectionStatusIndicatorProps {
  status: 'connected' | 'connecting' | 'disconnected' | 'reconnecting';
  reconnectAttempt?: number;
  maxReconnectAttempts?: number;
}

export function ConnectionStatusIndicator({
  status,
  reconnectAttempt,
  maxReconnectAttempts = 5,
}: ConnectionStatusIndicatorProps) {
  const statusConfig = {
    connected: { color: 'success', icon: '🟢', text: 'Connected' },
    connecting: { color: 'warning', icon: '🟡', text: 'Connecting...' },
    disconnected: { color: 'error', icon: '🔴', text: 'Disconnected' },
    reconnecting: {
      color: 'warning',
      icon: '🟡',
      text: `Reconnecting... (${reconnectAttempt}/${maxReconnectAttempts})`,
    },
  };

  const config = statusConfig[status];

  return (
    <Tooltip title={config.text}>
      <Chip
        icon={<span>{config.icon}</span>}
        label={config.text}
        color={config.color}
        size="small"
        variant="outlined"
      />
    </Tooltip>
  );
}
```

**Placement**:
- Header: Always visible in top-right corner
- Footer: Alternative placement for mobile
- Toast: Show connection status changes as toast notifications

---

## Real-Time Notifications

### Notification Center Component

**Component**: `NotificationCenter`

**Purpose**: Display real-time notifications from WebSocket events

**Layout**:
```
┌─────────────────────────────────────────┐
│ Notifications                    [🔔 3] │
├─────────────────────────────────────────┤
│                                         │
│  ┌───────────────────────────────────┐ │
│  │ ✓ Contract validated              │ │
│  │   Customer Orders contract        │ │
│  │   2 minutes ago                   │ │
│  └───────────────────────────────────┘ │
│                                         │
│  ┌───────────────────────────────────┐ │
│  │ ⚠ DQ Run completed with warnings  │ │
│  │   Sales Data asset                 │ │
│  │   5 minutes ago                    │ │
│  └───────────────────────────────────┘ │
│                                         │
│  ┌───────────────────────────────────┐ │
│  │ ✗ Job failed                      │ │
│  │   Data ingestion job              │ │
│  │   10 minutes ago                   │ │
│  └───────────────────────────────────┘ │
│                                         │
│  [Mark all as read]  [View all]        │
│                                         │
└─────────────────────────────────────────┘
```

**Component Specification**:
```typescript
interface Notification {
  id: string;
  type: 'success' | 'warning' | 'error' | 'info';
  title: string;
  message: string;
  timestamp: Date;
  read: boolean;
  actionUrl?: string;
  metadata?: Record<string, any>;
}

interface NotificationCenterProps {
  notifications: Notification[];
  onMarkAsRead: (id: string) => void;
  onMarkAllAsRead: () => void;
  onNotificationClick: (notification: Notification) => void;
}

export function NotificationCenter({
  notifications,
  onMarkAsRead,
  onMarkAllAsRead,
  onNotificationClick,
}: NotificationCenterProps) {
  const unreadCount = notifications.filter(n => !n.read).length;

  return (
    <Popover>
      <IconButton>
        <Badge badgeContent={unreadCount} color="error">
          <NotificationsIcon />
        </Badge>
      </IconButton>
      <PopoverContent>
        <NotificationList
          notifications={notifications}
          onMarkAsRead={onMarkAsRead}
          onNotificationClick={onNotificationClick}
        />
        <Button onClick={onMarkAllAsRead}>Mark all as read</Button>
      </PopoverContent>
    </Popover>
  );
}
```

**Notification Types**:
- **Success**: Green, checkmark icon (e.g., "Contract validated")
- **Warning**: Yellow, warning icon (e.g., "DQ run completed with warnings")
- **Error**: Red, error icon (e.g., "Job failed")
- **Info**: Blue, info icon (e.g., "Asset updated")

**Interactions**:
- Click notification: Navigate to related resource
- Mark as read: Remove from unread count
- Mark all as read: Mark all notifications as read
- Auto-dismiss: Success notifications auto-dismiss after 5 seconds

**Real-Time Updates**:
- New notifications appear at top
- Unread count updates automatically
- Sound notification (optional, user preference)

---

## Live Job Status Updates

### Job Status Component

**Component**: `JobStatusIndicator`

**Purpose**: Show real-time job progress and status

**Layout**:
```
┌─────────────────────────────────────────┐
│ Job: Data Quality Run                   │
├─────────────────────────────────────────┤
│                                         │
│  Status: ⏳ Running                     │
│                                         │
│  Progress: ████████░░ 80%              │
│                                         │
│  Current Step: Validating schemas       │
│                                         │
│  Started: 2 minutes ago                  │
│  Estimated completion: 1 minute        │
│                                         │
│  [View Details] [Cancel]                │
│                                         │
└─────────────────────────────────────────┘
```

**Component Specification**:
```typescript
interface JobStatus {
  id: string;
  name: string;
  status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled';
  progress?: number; // 0-100
  currentStep?: string;
  startedAt: Date;
  completedAt?: Date;
  estimatedCompletion?: Date;
  error?: string;
}

interface JobStatusIndicatorProps {
  job: JobStatus;
  onViewDetails: () => void;
  onCancel?: () => void;
}

export function JobStatusIndicator({
  job,
  onViewDetails,
  onCancel,
}: JobStatusIndicatorProps) {
  const statusConfig = {
    pending: { color: 'default', icon: '⏸', label: 'Pending' },
    running: { color: 'primary', icon: '⏳', label: 'Running' },
    completed: { color: 'success', icon: '✓', label: 'Completed' },
    failed: { color: 'error', icon: '✗', label: 'Failed' },
    cancelled: { color: 'default', icon: '⊘', label: 'Cancelled' },
  };

  const config = statusConfig[job.status];

  return (
    <Card>
      <CardContent>
        <Box display="flex" alignItems="center" gap={2}>
          <Chip
            icon={<span>{config.icon}</span>}
            label={config.label}
            color={config.color}
          />
          <Typography variant="h6">{job.name}</Typography>
        </Box>

        {job.status === 'running' && job.progress !== undefined && (
          <>
            <LinearProgress
              variant="determinate"
              value={job.progress}
              sx={{ mt: 2, mb: 1 }}
            />
            <Typography variant="body2" color="text.secondary">
              {job.progress}% complete
            </Typography>
            {job.currentStep && (
              <Typography variant="body2" color="text.secondary">
                Current step: {job.currentStep}
              </Typography>
            )}
          </>
        )}

        {job.status === 'failed' && job.error && (
          <Alert severity="error" sx={{ mt: 2 }}>
            {job.error}
          </Alert>
        )}

        <Box display="flex" gap={1} mt={2}>
          <Button onClick={onViewDetails}>View Details</Button>
          {job.status === 'running' && onCancel && (
            <Button onClick={onCancel} color="error">
              Cancel
            </Button>
          )}
        </Box>
      </CardContent>
    </Card>
  );
}
```

**Real-Time Updates**:
- Progress bar updates automatically
- Current step updates in real-time
- Status changes trigger visual updates
- Completion triggers success notification

---

## Real-Time Collaboration

### Active Users Indicator

**Component**: `ActiveUsersIndicator`

**Purpose**: Show who is currently viewing/editing a resource

**Layout**:
```
┌─────────────────────────────────────────┐
│ Contract Editor                         │
│                                         │
│  👤 Active Users (2)                   │
│  • John Doe (editing)                  │
│  • Jane Smith (viewing)                │
│                                         │
│  [Content]                              │
│                                         │
└─────────────────────────────────────────┘
```

**Component Specification**:
```typescript
interface ActiveUser {
  id: string;
  name: string;
  email: string;
  status: 'viewing' | 'editing';
  cursor?: { line: number; column: number };
  color: string; // Color for user's cursor/selection
}

interface ActiveUsersIndicatorProps {
  users: ActiveUser[];
  currentUserId: string;
}

export function ActiveUsersIndicator({
  users,
  currentUserId,
}: ActiveUsersIndicatorProps) {
  const otherUsers = users.filter(u => u.id !== currentUserId);

  return (
    <Box>
      <Typography variant="caption">
        👤 Active Users ({users.length})
      </Typography>
      <List dense>
        {otherUsers.map(user => (
          <ListItem key={user.id}>
            <ListItemAvatar>
              <Avatar sx={{ bgcolor: user.color }}>
                {user.name[0]}
              </Avatar>
            </ListItemAvatar>
            <ListItemText
              primary={user.name}
              secondary={user.status}
            />
          </ListItem>
        ))}
      </List>
    </Box>
  );
}
```

### Collaborative Cursors

**Component**: `CollaborativeCursor`

**Purpose**: Show other users' cursors in real-time editors

**Visual**:
- Colored cursor line with user's name
- User's selection highlighted in their color
- Smooth cursor movement animations

---

## Connection Management

### Connection Manager Hook

**Hook**: `useWebSocketConnection`

**Purpose**: Manage WebSocket connection lifecycle

```typescript
export function useWebSocketConnection() {
  const [status, setStatus] = useState<'connected' | 'disconnected' | 'reconnecting'>('disconnected');
  const [reconnectAttempt, setReconnectAttempt] = useState(0);
  const wsRef = useRef<WebSocketClient | null>(null);

  useEffect(() => {
    const connect = async () => {
      try {
        setStatus('connecting');
        await wsClient.connect();
        setStatus('connected');
        setReconnectAttempt(0);
      } catch (error) {
        setStatus('disconnected');
      }
    };

    connect();

    // Listen to connection events
    const handleConnect = () => setStatus('connected');
    const handleDisconnect = () => setStatus('disconnected');
    const handleReconnect = (attempt: number) => {
      setStatus('reconnecting');
      setReconnectAttempt(attempt);
    };

    wsClient.on('connect', handleConnect);
    wsClient.on('disconnect', handleDisconnect);
    wsClient.on('reconnect', handleReconnect);

    return () => {
      wsClient.off('connect', handleConnect);
      wsClient.off('disconnect', handleDisconnect);
      wsClient.off('reconnect', handleReconnect);
      wsClient.disconnect();
    };
  }, []);

  return { status, reconnectAttempt };
}
```

---

## Reconnection Handling

### Reconnection UI Patterns

**Pattern 1: Automatic Reconnection (Silent)**
- Show connection status indicator
- Automatically reconnect in background
- No user intervention required
- Show toast on successful reconnection

**Pattern 2: Manual Reconnection**
- Show reconnection dialog
- Allow user to manually retry
- Show connection status

**Reconnection Dialog**:
```
┌─────────────────────────────────────────┐
│ Connection Lost                         │
├─────────────────────────────────────────┤
│                                         │
│  Unable to connect to server.           │
│                                         │
│  Attempting to reconnect...             │
│  (Attempt 2 of 5)                       │
│                                         │
│  [Retry Now]  [Work Offline]           │
│                                         │
└─────────────────────────────────────────┘
```

**Reconnection Strategy**:
- Exponential backoff: 1s, 2s, 4s, 8s, 16s
- Max attempts: 5
- Show attempt count to user
- Allow manual retry
- Option to work offline

---

## Event Subscription Patterns

### Event Subscription Hook

**Hook**: `useEventSubscription`

**Purpose**: Subscribe to specific event types

```typescript
export function useEventSubscription(
  eventTypes: WebSocketEventType[],
  onEvent: (event: WebSocketEvent) => void
) {
  const queryClient = useQueryClient();

  useEffect(() => {
    // Subscribe to events
    wsClient.subscribe(eventTypes);

    // Set up listeners
    const unsubscribes = eventTypes.map(eventType =>
      wsClient.on(eventType, (event) => {
        // Invalidate relevant queries
        if (eventType.startsWith('asset.')) {
          queryClient.invalidateQueries({ queryKey: ['assets'] });
        } else if (eventType.startsWith('contract.')) {
          queryClient.invalidateQueries({ queryKey: ['contracts'] });
        } else if (eventType.startsWith('job.')) {
          queryClient.invalidateQueries({ queryKey: ['jobs'] });
        }

        // Call custom handler
        onEvent(event);
      })
    );

    return () => {
      unsubscribes.forEach(unsubscribe => unsubscribe());
      wsClient.unsubscribe(eventTypes);
    };
  }, [eventTypes, onEvent, queryClient]);
}
```

### Usage Examples

**Example 1: Job Status Updates**
```typescript
function JobDetailPage({ jobId }: { jobId: string }) {
  const { data: job } = useJob(jobId);

  useEventSubscription(
    ['job.started', 'job.completed', 'job.failed', 'job.progress'],
    (event) => {
      if (event.data.job_id === jobId) {
        // Update job status
        queryClient.setQueryData(['jobs', jobId], (old: Job) => ({
          ...old,
          status: event.data.status,
          progress: event.data.progress,
        }));
      }
    }
  );

  return <JobStatusIndicator job={job} />;
}
```

**Example 2: Contract Validation Updates**
```typescript
function ContractEditor({ contractId }: { contractId: string }) {
  useEventSubscription(
    ['contract.validated'],
    (event) => {
      if (event.data.contract_id === contractId) {
        // Show validation result
        showNotification({
          type: 'success',
          title: 'Contract validated',
          message: 'Validation completed successfully',
        });
      }
    }
  );

  return <ContractEditorContent />;
}
```

---

## Offline Mode Handling

### Offline Indicator

**Component**: `OfflineIndicator`

**Purpose**: Show when application is offline

**Layout**:
```
┌─────────────────────────────────────────┐
│ ⚠️ You're offline. Some features may    │
│    not be available.                    │
└─────────────────────────────────────────┘
```

**Behavior**:
- Detect offline status (navigator.onLine)
- Show banner at top of page
- Disable real-time features
- Queue actions for when online
- Show sync status when reconnected

---

## Performance Considerations

1. **Event Throttling**: Throttle high-frequency events (e.g., cursor movements)
2. **Selective Subscriptions**: Only subscribe to needed events
3. **Connection Pooling**: Reuse WebSocket connections
4. **Message Batching**: Batch multiple events when possible
5. **Memory Management**: Clean up event listeners on unmount

---

## Accessibility

1. **Status Announcements**: Announce connection status changes to screen readers
2. **Notification Alerts**: Notifications announced to screen readers
3. **Keyboard Navigation**: All real-time UI elements keyboard accessible
4. **Focus Management**: Manage focus during real-time updates

---

**Last Updated**: 2026-03-22  
**Version**: 1.0.0


---

# Resource Pickers

**Last Updated**: 2026-03-22  
**Version**: 1.0.0  
**Reference**: [tasks.md 29.69](../../openspec/changes/useronboardfix/tasks.md), [RESOURCE_PICKER_LINKING_PLAN.md](../../openspec/changes/useronboardfix/RESOURCE_PICKER_LINKING_PLAN.md)

---

## Overview

Resource pickers are searchable dropdown components for selecting assets, contracts, datasets, and files. They replace manual UUID entry with a search-and-select UX, improving usability and reducing errors.

**Location**: `frontend/src/shared/components/pickers/`

**Components**:
- **Single-select**: AssetPicker, ContractPicker, DatasetPicker, FilePicker
- **Multi-select**: AssetMultiPicker, DatasetMultiPicker, FileMultiPicker

**Feature flag**: `VITE_FEATURE_RESOURCE_PICKERS_ENABLED` (default: true). When false, pickers render plain text inputs for manual UUID entry.

---

## AssetPicker

Searchable, single-select picker for choosing an asset.

### Props

| Prop | Type | Default | Description |
|------|------|---------|-------------|
| `value` | `string \| null` | — | Selected asset ID (UUID) or null |
| `onChange` | `(assetId: string \| null) => void` | — | Called when selection changes |
| `placeholder` | `string` | `'Search and select an asset...'` | Placeholder text |
| `disabled` | `boolean` | `false` | Disable the picker |
| `data-testid` | `string` | `'asset-picker'` | Test ID for E2E |

### Usage

```tsx
import { AssetPicker } from '@/shared/components/pickers';

function MyForm() {
  const [assetId, setAssetId] = useState<string | null>(null);

  return (
    <AssetPicker
      value={assetId}
      onChange={setAssetId}
      placeholder="Select target asset"
      data-testid="my-asset-picker"
    />
  );
}
```

### Where Used

- ODPSUploadPage (asset selection)
- DatasetCreatePage (asset selection)
- DatasetDetailPage (edit: link to asset)
- RetentionPolicyCreatePage/EditPage
- DQRunListPage, ComplianceRunListPage (create modal)

---

## ContractPicker

Searchable, single-select picker for choosing a contract. Optional `specType` filter for ODPS-only contracts.

### Props

| Prop | Type | Default | Description |
|------|------|---------|-------------|
| `value` | `string \| null` | — | Selected contract ID (UUID) or null |
| `onChange` | `(contractId: string \| null) => void` | — | Called when selection changes |
| `placeholder` | `string` | `'Search and select a contract...'` | Placeholder text |
| `disabled` | `boolean` | `false` | Disable the picker |
| `specType` | `string` | — | Filter by spec_type (e.g. `ODPS` for ODPS Link page) |
| `data-testid` | `string` | `'contract-picker'` | Test ID for E2E |

### Usage

```tsx
import { ContractPicker } from '@/shared/components/pickers';

function ODPSLinkForm() {
  const [contractId, setContractId] = useState<string | null>(null);

  return (
    <ContractPicker
      value={contractId}
      onChange={setContractId}
      specType="ODPS"
      placeholder="Select ODPS contract"
      data-testid="odps-link-contract-picker"
    />
  );
}
```

### Where Used

- AssetDetailPage (attach contract)
- ODPSLinkPage (Link Existing ODPS mode)
- ScheduledExportCreatePage/EditPage (contract_id)

---

## DatasetPicker

Searchable, single-select picker for choosing a dataset. Optional `assetId` for cascading (filter datasets by asset).

### Props

| Prop | Type | Default | Description |
|------|------|---------|-------------|
| `value` | `string \| null` | — | Selected dataset ID (UUID) or null |
| `onChange` | `(datasetId: string \| null) => void` | — | Called when selection changes |
| `placeholder` | `string` | `'Search and select a dataset...'` | Placeholder text |
| `disabled` | `boolean` | `false` | Disable the picker |
| `assetId` | `string \| undefined` | — | Filter by asset_id (cascading) |
| `data-testid` | `string` | `'dataset-picker'` | Test ID for E2E |

### Usage

```tsx
import { AssetPicker, DatasetPicker } from '@/shared/components/pickers';

function DQCreateForm() {
  const [assetId, setAssetId] = useState<string | null>(null);
  const [datasetId, setDatasetId] = useState<string | null>(null);

  return (
    <>
      <AssetPicker value={assetId} onChange={setAssetId} />
      <DatasetPicker
        value={datasetId}
        onChange={setDatasetId}
        assetId={assetId ?? undefined}
      />
    </>
  );
}
```

### Where Used

- AssetDetailPage (attach dataset)
- DQRunListPage, ComplianceRunListPage (create modal)
- RetentionPolicyCreatePage/EditPage

---

## FilePicker

Searchable, single-select picker for choosing a file. Optional `assetId` and `datasetId` for cascading (passed for future use; backend files API does not yet support these filters).

### Props

| Prop | Type | Default | Description |
|------|------|---------|-------------|
| `value` | `string \| null` | — | Selected file ID (UUID) or null |
| `onChange` | `(fileId: string \| null) => void` | — | Called when selection changes |
| `placeholder` | `string` | `'Search and select a file...'` | Placeholder text |
| `disabled` | `boolean` | `false` | Disable the picker |
| `assetId` | `string \| undefined` | — | Filter by asset_id (future use) |
| `datasetId` | `string \| undefined` | — | Filter by dataset_id (future use) |
| `data-testid` | `string` | `'file-picker'` | Test ID for E2E |

### Usage

```tsx
import { AssetPicker, DatasetPicker, FilePicker } from '@/shared/components/pickers';

function AccessRequestForm() {
  const [assetId, setAssetId] = useState<string | null>(null);
  const [datasetId, setDatasetId] = useState<string | null>(null);
  const [fileId, setFileId] = useState<string | null>(null);

  return (
    <>
      <AssetPicker value={assetId} onChange={setAssetId} />
      <DatasetPicker
        value={datasetId}
        onChange={setDatasetId}
        assetId={assetId ?? undefined}
      />
      <FilePicker
        value={fileId}
        onChange={setFileId}
        assetId={assetId ?? undefined}
        datasetId={datasetId ?? undefined}
      />
    </>
  );
}
```

### Where Used

- DQRunListPage, ComplianceRunListPage (create modal)
- AccessRequestCreatePage
- RetentionPolicyCreatePage/EditPage

---

## AssetMultiPicker

Searchable, multi-select picker for choosing multiple assets.
Selected items display as tags with remove buttons.

### Props

| Prop | Type | Default | Description |
|------|------|---------|-------------|
| `value` | `string[]` | — | Array of selected asset IDs |
| `onChange` | `(assetIds: string[]) => void` | — | Called when selection changes |
| `placeholder` | `string` | `'Search and select assets...'` | Placeholder text |
| `disabled` | `boolean` | `false` | Disable the picker |
| `data-testid` | `string` | `'asset-multi-picker'` | Test ID for E2E |

### Usage

```tsx
import { AssetMultiPicker } from '@/shared/components/pickers';

function ScheduledExportForm() {
  const [assetIds, setAssetIds] = useState<string[]>([]);

  return (
    <AssetMultiPicker
      value={assetIds}
      onChange={setAssetIds}
      placeholder="Select assets to export"
      data-testid="scheduled-export-asset-picker"
    />
  );
}
```

### Where Used

- ScheduledExportCreatePage/EditPage (asset_ids)

---

## DatasetMultiPicker

Searchable, multi-select picker for choosing multiple datasets.

### Props

| Prop | Type | Default | Description |
|------|------|---------|-------------|
| `value` | `string[]` | — | Array of selected dataset IDs |
| `onChange` | `(datasetIds: string[]) => void` | — | Called when selection changes |
| `placeholder` | `string` | `'Search and select datasets...'` | Placeholder text |
| `disabled` | `boolean` | `false` | Disable the picker |
| `assetId` | `string \| undefined` | — | Filter by asset_id (cascading) |
| `data-testid` | `string` | `'dataset-multi-picker'` | Test ID for E2E |

---

## FileMultiPicker

Searchable, multi-select picker for choosing multiple files.

### Props

| Prop | Type | Default | Description |
|------|------|---------|-------------|
| `value` | `string[]` | — | Array of selected file IDs |
| `onChange` | `(fileIds: string[]) => void` | — | Called when selection changes |
| `placeholder` | `string` | `'Search and select files...'` | Placeholder text |
| `disabled` | `boolean` | `false` | Disable the picker |
| `assetId` | `string \| undefined` | — | Filter by asset_id (future use) |
| `datasetId` | `string \| undefined` | — | Filter by dataset_id (future use) |
| `data-testid` | `string` | `'file-multi-picker'` | Test ID for E2E |

### Where Used

- ScheduledExportCreatePage/EditPage (dataset_ids, file_ids)

---

## Backend API

Pickers call list APIs with search, filter, and ordering:

| Endpoint | search | filter | ordering |
|----------|--------|--------|----------|
| GET /api/v1/assets/ | name, key, description | domain, status, visibility | name, key, created_at, updated_at |
| GET /api/v1/contracts/ | info.name, info.title | status, spec_type, etc. | created_at, updated_at, quality_score |
| GET /api/v1/datasets/ | file name, format | asset_id, dataset_format | created_at, updated_at, format |
| GET /api/v1/files/ | name | status | name, created_at, updated_at |

See [API_REFERENCE.md](../API_REFERENCE.md#list-api-query-parameters-resource-pickers).

---

## Accessibility

- **ARIA**: combobox, listbox, aria-expanded, aria-multiselectable (multi)
- **Keyboard**: ArrowDown/Up, Enter (select), Escape (close)
- **Labels**: aria-label on search input and options

---

## Troubleshooting

See [docs/runbooks/RESOURCE_PICKER_TROUBLESHOOTING.md](../runbooks/RESOURCE_PICKER_TROUBLESHOOTING.md).

---

## Related

- [docs/API_REFERENCE.md](../API_REFERENCE.md) — List API params
- [docs/runbooks/RESOURCE_PICKER_TROUBLESHOOTING.md](../runbooks/RESOURCE_PICKER_TROUBLESHOOTING.md)
- [scripts/run_resource_picker_tests.sh](../../scripts/run_resource_picker_tests.sh)

---

# Responsive Design Guidelines

**Last Updated**: 2026-03-22  
**Version**: 1.0.0

---

## Table of Contents

1. [Overview](#overview)
2. [Breakpoints](#breakpoints)
3. [Mobile-First Approach](#mobile-first-approach)
4. [Layout Patterns](#layout-patterns)
5. [Component Responsiveness](#component-responsiveness)
6. [Typography Scaling](#typography-scaling)
7. [Touch Targets](#touch-targets)
8. [Navigation Patterns](#navigation-patterns)
9. [Image and Media](#image-and-media)
10. [Testing Responsive Design](#testing-responsive-design)

---

## Overview

This document provides comprehensive guidelines for responsive design across the Interoperable Data Hub platform. All interfaces must work seamlessly across devices, from mobile phones to large desktop screens.

**Responsive Design Principles**:
- **Mobile-First**: Design for mobile, enhance for larger screens
- **Fluid Layouts**: Use flexible layouts that adapt to screen size
- **Touch-Friendly**: Ensure touch targets are appropriately sized
- **Performance**: Optimize for mobile network conditions
- **Accessibility**: Maintain accessibility across all screen sizes

---

## Breakpoints

### Standard Breakpoints

The design system uses the following breakpoints:

| Breakpoint | Min Width | Device Type | Usage |
|------------|-----------|-------------|-------|
| `xs` | 0px | Mobile (portrait) | Small phones |
| `sm` | 600px | Mobile (landscape), Tablet (portrait) | Large phones, small tablets |
| `md` | 960px | Tablet (landscape) | Tablets |
| `lg` | 1280px | Desktop | Laptops, small desktops |
| `xl` | 1920px | Large Desktop | Large monitors |

### Breakpoint Usage

```tsx
// Material-UI breakpoints
const theme = {
  breakpoints: {
    values: {
      xs: 0,
      sm: 600,
      md: 960,
      lg: 1280,
      xl: 1920
    }
  }
};

// Usage in components
<Box
  sx={{
    width: { xs: '100%', sm: '50%', md: '33%', lg: '25%' }
  }}
>
  Content
</Box>
```

---

## Mobile-First Approach

### Design Strategy

1. **Start with Mobile**: Design for smallest screen first
2. **Progressive Enhancement**: Add features and complexity for larger screens
3. **Content Priority**: Show most important content first
4. **Performance**: Optimize for mobile network speeds

### Implementation

```css
/* Mobile-first CSS */
.container {
  padding: 16px; /* Mobile default */
}

@media (min-width: 600px) {
  .container {
    padding: 24px; /* Tablet and up */
  }
}

@media (min-width: 1280px) {
  .container {
    padding: 32px; /* Desktop */
    max-width: 1200px;
    margin: 0 auto;
  }
}
```

---

## Layout Patterns

### Pattern: Single Column to Multi-Column

**Mobile**: Single column, full width
**Tablet**: 2 columns
**Desktop**: 3-4 columns

```tsx
<Grid container spacing={2}>
  <Grid item xs={12} sm={6} md={4} lg={3}>
    <Card>Item 1</Card>
  </Grid>
  <Grid item xs={12} sm={6} md={4} lg={3}>
    <Card>Item 2</Card>
  </Grid>
</Grid>
```

### Pattern: Stack to Side-by-Side

**Mobile**: Stacked vertically
**Desktop**: Side-by-side

```tsx
<Stack
  direction={{ xs: 'column', md: 'row' }}
  spacing={2}
>
  <Box flex={1}>Left Content</Box>
  <Box flex={1}>Right Content</Box>
</Stack>
```

### Pattern: Hidden on Small Screens

**Mobile**: Hide less important content
**Desktop**: Show all content

```tsx
<Box
  sx={{
    display: { xs: 'none', md: 'block' }
  }}
>
  Additional Content
</Box>
```

---

## Component Responsiveness

### Header

**Mobile**:
- Collapsed navigation (hamburger menu)
- Simplified logo
- Essential actions only

**Desktop**:
- Full navigation visible
- Complete logo
- All actions visible

### Sidebar

**Mobile**:
- Hidden by default (drawer)
- Overlay when open
- Full width when open

**Desktop**:
- Always visible
- Collapsible (240px → 64px)
- No overlay

### Tables

**Mobile**:
- Horizontal scroll
- Simplified columns
- Card view option

**Desktop**:
- All columns visible
- Full functionality
- Inline actions

### Forms

**Mobile**:
- Single column
- Full-width inputs
- Stacked buttons

**Desktop**:
- Multi-column where appropriate
- Optimal input widths
- Side-by-side buttons

---

## Typography Scaling

### Responsive Typography

```tsx
const theme = {
  typography: {
    h1: {
      fontSize: '2rem',      // 32px on mobile
      '@media (min-width:600px)': {
        fontSize: '2.5rem'  // 40px on tablet+
      }
    },
    body1: {
      fontSize: '1rem',      // 16px (consistent)
      lineHeight: 1.5
    }
  }
};
```

### Readable Line Length

- **Mobile**: Full width (with padding)
- **Desktop**: Max 75 characters per line
- **Large Text**: Slightly wider (80-90 characters)

---

## Touch Targets

### Minimum Sizes

- **Touch Target**: 44px × 44px minimum (iOS), 48px × 48px (Material Design)
- **Button Height**: 40px minimum (mobile), 48px preferred
- **Input Height**: 48px minimum
- **Icon Button**: 48px × 48px

### Spacing

- **Between Touch Targets**: 8px minimum
- **Padding**: 12px minimum inside touch targets
- **Safe Areas**: Account for device notches and home indicators

### Examples

```tsx
// Good: Large touch target
<IconButton size="large" sx={{ minWidth: 48, minHeight: 48 }}>
  <Icon />
</IconButton>

// Good: Adequate spacing
<Stack direction="row" spacing={2}>
  <Button>Action 1</Button>
  <Button>Action 2</Button>
</Stack>
```

---

## Navigation Patterns

### Mobile Navigation

**Pattern**: Bottom Navigation or Hamburger Menu

```tsx
// Bottom Navigation (for primary actions)
<BottomNavigation>
  <BottomNavigationAction icon={<HomeIcon />} label="Home" />
  <BottomNavigationAction icon={<AssetsIcon />} label="Assets" />
  <BottomNavigationAction icon={<MarketplaceIcon />} label="Marketplace" />
</BottomNavigation>

// Hamburger Menu (for secondary navigation)
<Drawer anchor="left" open={open} onClose={handleClose}>
  <List>
    <ListItem>Assets</ListItem>
    <ListItem>Marketplace</ListItem>
  </List>
</Drawer>
```

### Desktop Navigation

**Pattern**: Horizontal Navigation Bar

```tsx
<AppBar>
  <Toolbar>
    <Logo />
    <Tabs>
      <Tab label="Assets" />
      <Tab label="Marketplace" />
    </Tabs>
    <UserMenu />
  </Toolbar>
</AppBar>
```

---

## Image and Media

### Responsive Images

```tsx
<img
  src="image.jpg"
  srcSet="image-small.jpg 600w, image-large.jpg 1200w"
  sizes="(max-width: 600px) 100vw, 50vw"
  alt="Description"
/>
```

### Aspect Ratios

Maintain aspect ratios across screen sizes:

```css
.image-container {
  aspect-ratio: 16 / 9;
  width: 100%;
  object-fit: cover;
}
```

### Video

- **Mobile**: Full width, autoplay disabled
- **Desktop**: Optimal size, autoplay optional
- **Controls**: Always visible and accessible

---

## Testing Responsive Design

### Device Testing

Test on real devices:
- **Mobile**: iPhone, Android phones
- **Tablet**: iPad, Android tablets
- **Desktop**: Various screen sizes

### Browser Testing

Test in:
- Chrome (desktop and mobile)
- Safari (desktop and iOS)
- Firefox
- Edge

### Tools

- **Browser DevTools**: Responsive design mode
- **Chrome DevTools**: Device toolbar
- **BrowserStack**: Cross-browser testing
- **Lighthouse**: Performance and accessibility

### Checklist

- [ ] Layout works on all breakpoints
- [ ] Text is readable on all screen sizes
- [ ] Touch targets are appropriately sized
- [ ] Navigation is accessible on mobile
- [ ] Forms are usable on mobile
- [ ] Images scale appropriately
- [ ] No horizontal scrolling (unless intentional)
- [ ] Performance is acceptable on mobile networks

---

## Common Responsive Patterns

### Pattern: Responsive Grid

```tsx
<Grid container spacing={2}>
  <Grid item xs={12} sm={6} md={4}>
    {/* 1 column mobile, 2 tablet, 3 desktop */}
  </Grid>
</Grid>
```

### Pattern: Responsive Typography

```tsx
<Typography
  variant="h1"
  sx={{
    fontSize: { xs: '1.5rem', sm: '2rem', md: '2.5rem' }
  }}
>
  Title
</Typography>
```

### Pattern: Responsive Spacing

```tsx
<Box
  sx={{
    padding: { xs: 2, sm: 3, md: 4 }
  }}
>
  Content
</Box>
```

### Pattern: Show/Hide Based on Screen Size

```tsx
<Box
  sx={{
    display: { xs: 'none', md: 'block' }
  }}
>
  Desktop Only Content
</Box>

<Box
  sx={{
    display: { xs: 'block', md: 'none' }
  }}
>
  Mobile Only Content
</Box>
```

---

**Last Updated**: 2026-03-22  
**Version**: 1.0.0


---

# Frontend Testing Strategy

**Last Updated**: 2026-03-22  
**Version**: 1.0.0

---

## Table of Contents

1. [Overview](#overview)
2. [Testing Pyramid](#testing-pyramid)
3. [Unit Testing](#unit-testing)
4. [Component Testing](#component-testing)
5. [Integration Testing](#integration-testing)
6. [End-to-End Testing](#end-to-end-testing)
7. [Visual Regression Testing](#visual-regression-testing)
8. [Accessibility Testing](#accessibility-testing)
9. [Performance Testing](#performance-testing)
10. [Test Data Management](#test-data-management)
11. [Mocking Strategies](#mocking-strategies)
12. [CI/CD Integration](#cicd-integration)

---

## Overview

This document outlines the comprehensive testing strategy for the frontend application. The strategy follows the testing pyramid approach, emphasizing unit and component tests with fewer integration and E2E tests.

**Testing Principles**:
- **Test User Behavior**: Test what users see and do, not implementation details
- **Fast Feedback**: Tests should run quickly
- **Reliable**: Tests should be deterministic and not flaky
- **Maintainable**: Tests should be easy to update
- **Comprehensive**: Cover critical paths and edge cases

**Testing Tools**:
- **Unit/Component**: Jest, React Testing Library
- **E2E**: Cypress or Playwright
- **Visual**: Chromatic or Percy
- **Accessibility**: jest-axe, pa11y
- **Coverage**: Istanbul/nyc

---

## Testing Pyramid

```
        /\
       /  \
      / E2E \          (10%)
     /--------\
    /          \
   / Integration \     (20%)
  /--------------\
 /                \
/   Unit/Component  \  (70%)
/--------------------\
```

**Distribution**:
- **70%**: Unit and Component Tests (fast, isolated)
- **20%**: Integration Tests (moderate speed, test interactions)
- **10%**: E2E Tests (slower, test complete flows)

---

## Unit Testing

### Testing Utilities

**Setup**: `src/test-utils/index.ts`

```typescript
import { render, RenderOptions } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ThemeProvider } from '@mui/material/styles';
import { theme } from '@/theme';

function createTestQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
        cacheTime: 0,
      },
      mutations: {
        retry: false,
      },
    },
  });
}

export function renderWithProviders(
  ui: React.ReactElement,
  options?: RenderOptions
) {
  const queryClient = createTestQueryClient();

  function Wrapper({ children }: { children: React.ReactNode }) {
    return (
      <QueryClientProvider client={queryClient}>
        <ThemeProvider theme={theme}>
          {children}
        </ThemeProvider>
      </QueryClientProvider>
    );
  }

  return render(ui, { wrapper: Wrapper, ...options });
}

export * from '@testing-library/react';
export { renderWithProviders as render };
```

### Example Unit Test

**File**: `src/components/Button.test.tsx`

```typescript
import { render, screen } from '@/test-utils';
import { Button } from './Button';

describe('Button', () => {
  it('renders with text', () => {
    render(<Button>Click me</Button>);
    expect(screen.getByRole('button', { name: /click me/i })).toBeInTheDocument();
  });

  it('calls onClick when clicked', () => {
    const handleClick = jest.fn();
    render(<Button onClick={handleClick}>Click me</Button>);
    
    screen.getByRole('button').click();
    expect(handleClick).toHaveBeenCalledTimes(1);
  });

  it('is disabled when disabled prop is true', () => {
    render(<Button disabled>Click me</Button>);
    expect(screen.getByRole('button')).toBeDisabled();
  });

  it('applies variant styles correctly', () => {
    const { container } = render(<Button variant="contained">Click me</Button>);
    expect(container.firstChild).toHaveClass('MuiButton-contained');
  });
});
```

### Testing Hooks

**File**: `src/hooks/useAssets.test.ts`

```typescript
import { renderHook, waitFor } from '@testing-library/react';
import { QueryClientProvider } from '@tanstack/react-query';
import { useAssets } from './useAssets';
import { createTestQueryClient } from '@/test-utils';
import { server } from '@/test-utils/msw';
import { rest } from 'msw';

describe('useAssets', () => {
  it('fetches assets successfully', async () => {
    server.use(
      rest.get('/api/v1/assets/assets/', (req, res, ctx) => {
        return res(
          ctx.json({
            count: 2,
            results: [
              { id: '1', name: 'Asset 1' },
              { id: '2', name: 'Asset 2' },
            ],
          })
        );
      })
    );

    const queryClient = createTestQueryClient();
    const wrapper = ({ children }: { children: React.ReactNode }) => (
      <QueryClientProvider client={queryClient}>
        {children}
      </QueryClientProvider>
    );

    const { result } = renderHook(() => useAssets(), { wrapper });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(result.current.data?.results).toHaveLength(2);
  });
});
```

---

## Component Testing

### Component Test Example

**File**: `src/components/AssetCard.test.tsx`

```typescript
import { render, screen, userEvent } from '@/test-utils';
import { AssetCard } from './AssetCard';
import type { Asset } from '@/types';

const mockAsset: Asset = {
  id: '1',
  name: 'Test Asset',
  key: 'test-asset',
  status: 'ACTIVE',
  description: 'Test description',
};

describe('AssetCard', () => {
  it('renders asset information', () => {
    render(<AssetCard asset={mockAsset} />);
    
    expect(screen.getByText('Test Asset')).toBeInTheDocument();
    expect(screen.getByText('test-asset')).toBeInTheDocument();
    expect(screen.getByText('Test description')).toBeInTheDocument();
  });

  it('shows status badge', () => {
    render(<AssetCard asset={mockAsset} />);
    expect(screen.getByText('ACTIVE')).toBeInTheDocument();
  });

  it('calls onEdit when edit button is clicked', async () => {
    const onEdit = jest.fn();
    render(<AssetCard asset={mockAsset} onEdit={onEdit} />);
    
    const editButton = screen.getByRole('button', { name: /edit/i });
    await userEvent.click(editButton);
    
    expect(onEdit).toHaveBeenCalledWith(mockAsset.id);
  });

  it('handles loading state', () => {
    render(<AssetCard asset={mockAsset} loading />);
    expect(screen.getByRole('progressbar')).toBeInTheDocument();
  });
});
```

### Testing Forms

**File**: `src/components/AssetForm.test.tsx`

```typescript
import { render, screen, waitFor } from '@/test-utils';
import userEvent from '@testing-library/user-event';
import { AssetForm } from './AssetForm';

describe('AssetForm', () => {
  it('validates required fields', async () => {
    const onSubmit = jest.fn();
    render(<AssetForm onSubmit={onSubmit} />);

    const submitButton = screen.getByRole('button', { name: /create/i });
    await userEvent.click(submitButton);

    await waitFor(() => {
      expect(screen.getByText(/name is required/i)).toBeInTheDocument();
    });

    expect(onSubmit).not.toHaveBeenCalled();
  });

  it('submits form with valid data', async () => {
    const onSubmit = jest.fn();
    render(<AssetForm onSubmit={onSubmit} />);

    await userEvent.type(screen.getByLabelText(/name/i), 'Test Asset');
    await userEvent.type(screen.getByLabelText(/key/i), 'test-asset');
    await userEvent.click(screen.getByRole('button', { name: /create/i }));

    await waitFor(() => {
      expect(onSubmit).toHaveBeenCalledWith({
        name: 'Test Asset',
        key: 'test-asset',
      });
    });
  });
});
```

---

## Integration Testing

### Integration Test Example

**File**: `src/features/assets/AssetList.test.tsx`

```typescript
import { render, screen, waitFor } from '@/test-utils';
import { AssetList } from './AssetList';
import { server } from '@/test-utils/msw';
import { rest } from 'msw';

describe('AssetList Integration', () => {
  it('loads and displays assets', async () => {
    server.use(
      rest.get('/api/v1/assets/assets/', (req, res, ctx) => {
        return res(
          ctx.json({
            count: 2,
            results: [
              { id: '1', name: 'Asset 1', status: 'ACTIVE' },
              { id: '2', name: 'Asset 2', status: 'DRAFT' },
            ],
          })
        );
      })
    );

    render(<AssetList />);

    await waitFor(() => {
      expect(screen.getByText('Asset 1')).toBeInTheDocument();
      expect(screen.getByText('Asset 2')).toBeInTheDocument();
    });
  });

  it('handles pagination', async () => {
    const user = userEvent.setup();
    
    server.use(
      rest.get('/api/v1/assets/assets/', (req, res, ctx) => {
        const page = req.url.searchParams.get('page') || '1';
        return res(
          ctx.json({
            count: 50,
            page: parseInt(page),
            total_pages: 3,
            results: Array.from({ length: 20 }, (_, i) => ({
              id: `${page}-${i}`,
              name: `Asset ${page}-${i}`,
            })),
          })
        );
      })
    );

    render(<AssetList />);

    await waitFor(() => {
      expect(screen.getByText('Asset 1-0')).toBeInTheDocument();
    });

    const nextButton = screen.getByRole('button', { name: /next/i });
    await user.click(nextButton);

    await waitFor(() => {
      expect(screen.getByText('Asset 2-0')).toBeInTheDocument();
    });
  });

  it('handles search', async () => {
    const user = userEvent.setup();
    
    server.use(
      rest.get('/api/v1/assets/assets/', (req, res, ctx) => {
        const search = req.url.searchParams.get('search') || '';
        return res(
          ctx.json({
            count: 1,
            results: search
              ? [{ id: '1', name: 'Matching Asset' }]
              : [{ id: '1', name: 'Asset 1' }],
          })
        );
      })
    );

    render(<AssetList />);

    const searchInput = screen.getByPlaceholderText(/search/i);
    await user.type(searchInput, 'Matching');

    await waitFor(() => {
      expect(screen.getByText('Matching Asset')).toBeInTheDocument();
    });
  });
});
```

---

## End-to-End Testing

### Cypress Setup

**File**: `cypress.config.ts`

```typescript
import { defineConfig } from 'cypress';

export default defineConfig({
  e2e: {
    baseUrl: 'http://localhost:3000',
    viewportWidth: 1280,
    viewportHeight: 720,
    video: true,
    screenshotOnRunFailure: true,
    setupNodeEvents(on, config) {
      // implement node event listeners here
    },
  },
  component: {
    devServer: {
      framework: 'react',
      bundler: 'vite',
    },
  },
});
```

### E2E Test Example

**File**: `cypress/e2e/asset-creation.cy.ts`

```typescript
describe('Asset Creation Flow', () => {
  beforeEach(() => {
    // Login
    cy.login('user@example.com', 'password');
    cy.visit('/assets');
  });

  it('creates a new asset via data-first flow', () => {
    // Click create asset button
    cy.findByRole('button', { name: /create asset/i }).click();

    // Fill in basic metadata
    cy.findByLabelText(/asset name/i).type('Customer Orders');
    cy.findByLabelText(/description/i).type('Customer order data');
    cy.findByLabelText(/domain/i).select('Sales');

    // Select data-first onboarding mode
    cy.findByLabelText(/data first/i).check();

    // Continue to file upload
    cy.findByRole('button', { name: /continue/i }).click();

    // Upload file
    cy.findByLabelText(/upload file/i).attachFile('sample.csv');

    // Wait for file processing
    cy.findByText(/file uploaded successfully/i).should('be.visible');

    // Continue to contract editor
    cy.findByRole('button', { name: /continue/i }).click();

    // Verify contract editor is shown
    cy.findByText(/edit contract/i).should('be.visible');

    // Save and activate
    cy.findByRole('button', { name: /save/i }).click();
    cy.findByRole('button', { name: /activate/i }).click();

    // Verify success
    cy.findByText(/asset created successfully/i).should('be.visible');
    cy.url().should('include', '/assets/');
  });
});
```

### Custom Cypress Commands

**File**: `cypress/support/commands.ts`

```typescript
declare global {
  namespace Cypress {
    interface Chainable {
      login(email: string, password: string): Chainable<void>;
      createAsset(data: Partial<Asset>): Chainable<string>;
      waitForJob(jobId: string): Chainable<void>;
    }
  }
}

Cypress.Commands.add('login', (email: string, password: string) => {
  cy.request({
    method: 'POST',
    url: '/api/v1/auth/login/',
    body: { email, password },
  }).then((response) => {
    window.localStorage.setItem('auth_token', response.body.access);
    window.localStorage.setItem('tenant_id', response.body.user.tenant_id);
  });
});

Cypress.Commands.add('createAsset', (data: Partial<Asset>) => {
  return cy.request({
    method: 'POST',
    url: '/api/v1/assets/assets/',
    headers: {
      Authorization: `Bearer ${window.localStorage.getItem('auth_token')}`,
    },
    body: data,
  }).then((response) => {
    return response.body.id;
  });
});

Cypress.Commands.add('waitForJob', (jobId: string) => {
  cy.request({
    method: 'GET',
    url: `/api/v1/jobs/${jobId}/`,
    headers: {
      Authorization: `Bearer ${window.localStorage.getItem('auth_token')}`,
    },
  }).then((response) => {
    if (response.body.status === 'running') {
      cy.wait(2000);
      cy.waitForJob(jobId);
    }
  });
});
```

---

## Visual Regression Testing

### Chromatic Setup

**File**: `package.json`

```json
{
  "scripts": {
    "chromatic": "chromatic --project-token=YOUR_TOKEN"
  }
}
```

### Storybook Stories for Visual Testing

**File**: `src/components/Button.stories.tsx`

```typescript
import type { Meta, StoryObj } from '@storybook/react';
import { Button } from './Button';

const meta: Meta<typeof Button> = {
  title: 'Components/Button',
  component: Button,
  tags: ['autodocs'],
};

export default meta;
type Story = StoryObj<typeof Button>;

export const Primary: Story = {
  args: {
    children: 'Button',
    variant: 'contained',
  },
};

export const Secondary: Story = {
  args: {
    children: 'Button',
    variant: 'outlined',
  },
};

export const Disabled: Story = {
  args: {
    children: 'Button',
    disabled: true,
  },
};
```

---

## Accessibility Testing

### jest-axe Setup

**File**: `src/test-utils/accessibility.ts`

```typescript
import { toHaveNoViolations } from 'jest-axe';
import { axe } from 'jest-axe';

expect.extend(toHaveNoViolations);

export async function checkAccessibility(container: HTMLElement) {
  const results = await axe(container);
  expect(results).toHaveNoViolations();
}
```

### Accessibility Test Example

**File**: `src/components/AssetCard.a11y.test.tsx`

```typescript
import { render } from '@/test-utils';
import { checkAccessibility } from '@/test-utils/accessibility';
import { AssetCard } from './AssetCard';

describe('AssetCard Accessibility', () => {
  it('has no accessibility violations', async () => {
    const { container } = render(
      <AssetCard
        asset={{
          id: '1',
          name: 'Test Asset',
          key: 'test-asset',
          status: 'ACTIVE',
        }}
      />
    );

    await checkAccessibility(container);
  });

  it('is keyboard navigable', async () => {
    const { container } = render(<AssetCard asset={mockAsset} />);
    
    // Tab to card
    const card = container.querySelector('[role="article"]');
    card?.focus();
    expect(card).toHaveFocus();

    // Tab to action buttons
    const buttons = container.querySelectorAll('button');
    buttons.forEach((button) => {
      expect(button).toBeVisible();
    });
  });
});
```

---

## Performance Testing

### Performance Test Example

**File**: `src/components/AssetList.perf.test.tsx`

```typescript
import { render, screen } from '@/test-utils';
import { AssetList } from './AssetList';

describe('AssetList Performance', () => {
  it('renders large lists efficiently', () => {
    const start = performance.now();
    
    render(<AssetList />);
    
    const end = performance.now();
    const renderTime = end - start;

    // Should render in under 100ms
    expect(renderTime).toBeLessThan(100);
  });

  it('handles virtual scrolling for large datasets', () => {
    const { container } = render(<AssetList />);
    
    // Check that only visible items are rendered
    const renderedItems = container.querySelectorAll('[data-testid="asset-item"]');
    expect(renderedItems.length).toBeLessThan(50); // Only visible items
  });
});
```

---

## Test Data Management

### Mock Service Worker (MSW) Setup

**File**: `src/test-utils/msw.ts`

```typescript
import { setupServer } from 'msw/node';
import { rest } from 'msw';

export const server = setupServer(
  // Default handlers
  rest.get('/api/v1/assets/assets/', (req, res, ctx) => {
    return res(
      ctx.json({
        count: 0,
        results: [],
      })
    );
  }),
);

beforeAll(() => server.listen());
afterEach(() => server.resetHandlers());
afterAll(() => server.close());
```

### Test Data Factories

**File**: `src/test-utils/factories.ts`

```typescript
import { faker } from '@faker-js/faker';
import type { Asset, Contract } from '@/types';

export function createMockAsset(overrides?: Partial<Asset>): Asset {
  return {
    id: faker.string.uuid(),
    name: faker.company.name(),
    key: faker.string.alphanumeric(10),
    status: 'ACTIVE',
    description: faker.lorem.sentence(),
    created_at: faker.date.past().toISOString(),
    ...overrides,
  };
}

export function createMockContract(overrides?: Partial<Contract>): Contract {
  return {
    id: faker.string.uuid(),
    version: '1.0.0',
    status: 'VALID',
    ...overrides,
  };
}
```

---

## Mocking Strategies

### API Mocking

**Strategy**: Use MSW for API mocking in tests

```typescript
// Mock successful response
server.use(
  rest.get('/api/v1/assets/assets/', (req, res, ctx) => {
    return res(ctx.json({ count: 1, results: [createMockAsset()] }));
  })
);

// Mock error response
server.use(
  rest.get('/api/v1/assets/assets/', (req, res, ctx) => {
    return res(ctx.status(500), ctx.json({ error: 'Server error' }));
  })
);
```

### Component Mocking

**Strategy**: Mock external dependencies, not components under test

```typescript
// Mock external library
jest.mock('@/lib/api/websocket', () => ({
  wsClient: {
    connect: jest.fn(),
    subscribe: jest.fn(),
    on: jest.fn(),
  },
}));
```

---

## CI/CD Integration

### GitHub Actions Workflow

**File**: `.github/workflows/frontend-tests.yml`

```yaml
name: Frontend Tests

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main, develop]

jobs:
  test:
    runs-on: ubuntu-latest
    
    steps:
      - uses: actions/checkout@v3
      
      - name: Setup Node.js
        uses: actions/setup-node@v3
        with:
          node-version: '18'
          cache: 'npm'
      
      - name: Install dependencies
        run: npm ci
      
      - name: Run unit tests
        run: npm run test:unit
      
      - name: Run component tests
        run: npm run test:component
      
      - name: Run E2E tests
        run: npm run test:e2e
      
      - name: Upload coverage
        uses: codecov/codecov-action@v3
        with:
          files: ./coverage/lcov.info
```

### Test Scripts

**File**: `package.json`

```json
{
  "scripts": {
    "test": "jest",
    "test:unit": "jest --testPathPattern=test",
    "test:component": "jest --testPathPattern=component",
    "test:e2e": "cypress run",
    "test:e2e:open": "cypress open",
    "test:coverage": "jest --coverage",
    "test:watch": "jest --watch",
    "test:a11y": "jest --testPathPattern=a11y"
  }
}
```

---

## Coverage Goals

**Target Coverage**:
- **Overall**: 80%+
- **Components**: 85%+
- **Hooks**: 90%+
- **Utils**: 95%+
- **Critical Paths**: 100%

**Coverage Exclusions**:
- Test files
- Storybook files
- Type definitions
- Generated code

---

## Best Practices

1. **Test Behavior, Not Implementation**: Test what users see and do
2. **Use Semantic Queries**: Prefer `getByRole`, `getByLabelText` over `getByTestId`
3. **Avoid Testing Implementation Details**: Don't test internal state or methods
4. **Keep Tests Simple**: One assertion per test when possible
5. **Use Descriptive Names**: Test names should describe what they test
6. **Mock External Dependencies**: Mock APIs, WebSockets, etc.
7. **Test Edge Cases**: Test error states, empty states, loading states
8. **Maintain Test Data**: Use factories for consistent test data
9. **Clean Up**: Reset mocks and state between tests
10. **Fast Tests**: Keep unit tests under 100ms

---

**Last Updated**: 2026-03-22  
**Version**: 1.0.0


---

# User Interface Specifications

**Last Updated**: 2026-03-22  
**Version**: 1.0.0

---

## Table of Contents

1. [Overview](#overview)
2. [Data Product Owner Interfaces](#data-product-owner-interfaces)
3. [Data Engineer Interfaces](#data-engineer-interfaces)
4. [Compliance Officer Interfaces](#compliance-officer-interfaces)
5. [Data Consumer Interfaces](#data-consumer-interfaces)
6. [Tenant Admin Interfaces](#tenant-admin-interfaces)
7. [Platform Admin Interfaces](#platform-admin-interfaces)
8. [Common Interface Patterns](#common-interface-patterns)
9. [Screen Specifications](#screen-specifications)

---

## Overview

This document provides detailed UI specifications for all personas and use cases in the Interoperable Data Hub platform. Each interface specification includes layout, components, interactions, and state management.

**Specification Format**:
- **Screen ID**: Unique identifier
- **Screen Name**: Descriptive name
- **Persona**: Primary persona(s)
- **Purpose**: What the screen accomplishes
- **Layout**: Screen structure and components
- **Components**: Specific components used
- **Interactions**: User interactions and behaviors
- **States**: Different states of the screen
- **Responsive Behavior**: How it adapts to different screen sizes

---

## Data Product Owner Interfaces

### UI-DPO-001: Asset Creation (Data-First Flow)

**Screen ID**: UI-DPO-001  
**Screen Name**: Create Asset - Data-First  
**Persona**: Data Product Owner  
**Purpose**: Onboard new asset via data-first flow

**Layout**:
```
┌─────────────────────────────────────────┐
│ Header (Logo, Navigation, User Menu)     │
├─────────────────────────────────────────┤
│ Breadcrumbs: Assets > Create Asset      │
├─────────────────────────────────────────┤
│                                         │
│  Title: Create New Asset                │
│                                         │
│  ┌─────────────────┬─────────────────┐ │
│  │ Basic Metadata  │ Onboarding Mode │ │
│  │                 │                 │ │
│  │ [Asset Name*]   │ ○ Data First    │ │
│  │ [Description]   │ ● Contract First│ │
│  │ [Domain]        │ ○ Contract Only │ │
│  │ [Tags]          │                 │ │
│  └─────────────────┴─────────────────┘ │
│                                         │
│  [Cancel]              [Continue →]     │
└─────────────────────────────────────────┘
```

**Components**:
- Header (with navigation)
- Breadcrumbs
- Container (max-width: lg)
- Grid (2 columns)
- TextInput (Asset Name, Description)
- Select (Domain)
- TagInput (Tags)
- RadioGroup (Onboarding Mode)
- Button (Cancel, Continue)

**Interactions**:
- Asset Name: Required, auto-generates slug on blur
- Domain: Dropdown with common domains
- Tags: Multi-select with autocomplete
- Continue: Validates required fields, navigates to file upload

**States**:
- **Default**: Empty form
- **Validating**: Show validation errors
- **Loading**: Disable form during submission

**Responsive Behavior**:
- Desktop: 2-column layout
- Tablet: 2-column layout (stacked)
- Mobile: Single column, full width

---

### UI-DPO-002: File Upload

**Screen ID**: UI-DPO-002  
**Screen Name**: Upload Data File  
**Persona**: Data Product Owner  
**Purpose**: Upload data file for analysis

**Layout**:
```
┌─────────────────────────────────────────┐
│ Breadcrumbs: Assets > Create > Upload   │
├─────────────────────────────────────────┤
│                                         │
│  Title: Upload Data File                │
│                                         │
│  ┌───────────────────────────────────┐ │
│  │                                     │ │
│  │     Drag & Drop File Here          │ │
│  │     or click to browse              │ │
│  │                                     │ │
│  │     Supported: CSV, JSON, Parquet  │ │
│  │                                     │ │
│  └───────────────────────────────────┘ │
│                                         │
│  ┌───────────────────────────────────┐ │
│  │ What happens next?                 │ │
│  │ 1. File is uploaded                │ │
│  │ 2. Schema is inferred               │ │
│  │ 3. DQ & Compliance checks run       │ │
│  │ 4. You review and edit contract    │ │
│  └───────────────────────────────────┘ │
│                                         │
│  [← Back]              [Upload & Analyze]│
└─────────────────────────────────────────┘
```

**Components**:
- FileUpload (drag-and-drop zone)
- Card (info card)
- Button (Back, Upload & Analyze)
- ProgressBar (during upload)

**Interactions**:
- Drag & Drop: Highlight zone, accept file
- Click to Browse: Open file picker
- Upload: Show progress, validate file
- File Selected: Show file name, size, type

**States**:
- **Empty**: Dropzone visible
- **Dragging**: Highlighted border
- **File Selected**: Show file info
- **Uploading**: Progress bar, disable actions
- **Error**: Show error message

---

### UI-DPO-003: Analyzing Data

**Screen ID**: UI-DPO-003  
**Screen Name**: Analyzing Data  
**Persona**: Data Product Owner  
**Purpose**: Show progress of data analysis

**Layout**:
```
┌─────────────────────────────────────────┐
│ Title: Analyzing Data for "Asset Name"  │
├─────────────────────────────────────────┤
│                                         │
│  Progress Steps:                        │
│  ✓ 1. Upload file                       │
│  → 2. Infer schema          [In Progress]│
│  ○ 3. Run data quality checks           │
│  ○ 4. Run compliance checks             │
│  ○ 5. Prepare contract draft            │
│                                         │
│  ┌───────────────────────────────────┐ │
│  │                                     │ │
│  │         [Loading Spinner]           │ │
│  │                                     │ │
│  │    "Inferring schema..."            │ │
│  │                                     │ │
│  └───────────────────────────────────┘ │
│                                         │
│  Note: You can navigate away; analysis  │
│  will continue in the background        │
└─────────────────────────────────────────┘
```

**Components**:
- Stepper (progress steps)
- LoadingSpinner
- StatusIndicator
- Alert (if errors)

**Interactions**:
- Auto-updates as jobs complete
- Shows current step and status
- Updates progress indicators
- Navigates to next screen when complete

**States**:
- **In Progress**: Show spinner, current step
- **Error**: Show error alert, allow retry
- **Complete**: Navigate to contract editor

---

### UI-DPO-004: Contract Editor

**Screen ID**: UI-DPO-004  
**Screen Name**: Contract Editor  
**Persona**: Data Product Owner  
**Purpose**: Edit and validate contract

> **📋 Detailed Specification**: See [Contract Editor Specification](./CONTRACT_EDITOR_SPECIFICATION.md) for comprehensive component specifications, architecture, and implementation details.

**Layout**:
```
┌─────────────────────────────────────────┐
│ Title: Edit Contract                    │
├─────────────────────────────────────────┤
│                                         │
│  ┌─────────────────┬─────────────────┐ │
│  │ Contract Form    │ Raw Contract    │ │
│  │                 │ & Validation    │ │
│  │ [Tabs]          │                 │ │
│  │ Overview        │ [View: Form]    │ │
│  │ Schema          │ [Raw YAML]      │ │
│  │ Quality         │                 │ │
│  │ Compliance      │ ┌─────────────┐ │ │
│  │ Lifecycle       │ │ Validation  │ │ │
│  │ Marketplace     │ │ Status: ✓   │ │ │
│  │                 │ │ Valid       │ │ │
│  │ [Form Fields]  │ └─────────────┘ │ │
│  └─────────────────┴─────────────────┘ │
│                                         │
│  [Run Validation]  [Save Draft] [Activate]│
└─────────────────────────────────────────┘
```

**Components**:
- EditorHeader (contract metadata, status badges)
- EditorTabs (Overview, Schema, Quality, Compliance, Lifecycle, Marketplace, Raw)
- Form components (TextInput, Select, TagInput, etc.)
- CodeEditor (Monaco Editor for raw YAML/JSON)
- ValidationPanel (real-time validation feedback)
- SchemaComparison (contract-first flow: inferred vs contract schema)
- Button (Run Validation, Save Draft, Activate)

**Interactions**:
- Form editing: Auto-save draft (every 30 seconds)
- Real-time validation: Debounced validation on field changes
- Schema tab: Edit field properties with field editor modal
- Raw view: Edit YAML/JSON directly with syntax highlighting
- Schema comparison: Resolve differences between inferred and contract schema
- Activate: Only enabled when validation status is VALID or WARNING_ONLY

**States**:
- **Editing**: Form editable, show unsaved changes indicator
- **Validating**: Show loading spinner, disable actions
- **Valid**: Green badge, activate button enabled
- **Invalid**: Red badge, show errors in validation panel, activate disabled
- **Warning**: Yellow badge, show warnings, activate enabled (per tenant policy)
- **Normalizing**: Show normalization status (NORMALIZED_OK, WITH_WARNINGS, FAILED)

**HubContract-Specific Features**:
- Quality rules editor (custom DQ rules with dimensions, severity, expressions)
- Compliance policy editor (PII categories, jurisdictions, legal bases, retention)
- Lifecycle policy editor (data source, refresh cadence, SLAs)
- Marketplace policy editor (license, intended use, restricted use)
- Schema comparison view (for contract-first onboarding flow)
- Normalization status display

---

### UI-DPO-005: Asset List

**Screen ID**: UI-DPO-005  
**Screen Name**: Assets List  
**Persona**: Data Product Owner  
**Purpose**: Browse and manage assets

**Layout**:
```
┌─────────────────────────────────────────┐
│ Title: Assets                            │
├─────────────────────────────────────────┤
│                                         │
│  [Search]  [Status Filter] [Domain Filter]│
│                                         │
│  ┌───────────────────────────────────┐ │
│  │ Name    │ Domain │ Status │ Quality│ │
│  ├─────────┼────────┼────────┼────────┤ │
│  │ Asset 1 │ Sales  │ Active │ ✓ Pass │ │
│  │ Asset 2 │ Mktg   │ Draft  │ ⚠ Warn │ │
│  │ Asset 3 │ Sales  │ Active │ ✗ Fail │ │
│  └───────────────────────────────────┘ │
│                                         │
│  [← Previous]  Page 1 of 5  [Next →]   │
│                                         │
│  [+ New Asset] (floating button)       │
└─────────────────────────────────────────┘
```

**Components**:
- SearchInput
- FilterDropdown (Status, Domain)
- Table (sortable, filterable)
- Pagination
- FloatingActionButton (New Asset)
- Badge (Status, Quality, Compliance)

**Interactions**:
- Search: Real-time filtering
- Filters: Multi-select, apply immediately
- Sort: Click column headers
- Row click: Navigate to asset detail
- Actions: Edit, Delete, More menu

**States**:
- **Loading**: Skeleton loaders
- **Empty**: Empty state with CTA
- **Error**: Error message with retry

---

## Data Engineer Interfaces

### UI-DE-001: API Documentation

**Screen ID**: UI-DE-001  
**Screen Name**: API Documentation  
**Persona**: Data Engineer  
**Purpose**: Browse API documentation

**Layout**:
```
┌─────────────────────────────────────────┐
│ Title: API Documentation                 │
├─────────────────────────────────────────┤
│                                         │
│  ┌───────────┬─────────────────────────┐ │
│  │ Endpoints │ Endpoint Details        │ │
│  │           │                         │ │
│  │ Assets    │ POST /api/v1/assets     │ │
│  │ Contracts │                         │ │
│  │ Files     │ Description:            │ │
│  │ DQ Runs   │ Create a new asset      │ │
│  │ ...       │                         │ │
│  │           │ Request:                │ │
│  │           │ { ... }                 │ │
│  │           │                         │ │
│  │           │ Response:               │ │
│  │           │ { ... }                 │ │
│  └───────────┴─────────────────────────┘ │
│                                         │
│  [Try It] [Copy cURL] [Copy Python]    │
└─────────────────────────────────────────┘
```

**Components**:
- Sidebar (endpoint list)
- CodeBlock (request/response examples)
- Tabs (Description, Request, Response, Examples)
- Button (Try It, Copy)

**Interactions**:
- Endpoint selection: Show details
- Code blocks: Syntax highlighting, copy
- Try It: Interactive API tester
- Examples: Language-specific examples

---

## Compliance Officer Interfaces

### UI-CPO-001: Compliance Dashboard

**Screen ID**: UI-CPO-001  
**Screen Name**: Compliance Dashboard  
**Persona**: Compliance Officer  
**Purpose**: Overview of compliance status

**Layout**:
```
┌─────────────────────────────────────────┐
│ Title: Compliance Dashboard             │
├─────────────────────────────────────────┤
│                                         │
│  ┌─────────┬─────────┬─────────┬──────┐ │
│  │ Total   │ Pass    │ Warn    │ Fail │ │
│  │ Assets  │         │         │      │ │
│  │ 150     │ 120     │ 20      │ 10   │ │
│  └─────────┴─────────┴─────────┴──────┘ │
│                                         │
│  ┌───────────────────────────────────┐ │
│  │ Compliance Status by Regulation    │ │
│  │ [Chart: GDPR, HIPAA, SOX, etc.]   │ │
│  └───────────────────────────────────┘ │
│                                         │
│  ┌───────────────────────────────────┐ │
│  │ Recent Compliance Runs            │ │
│  │ [Table: Asset, Status, Date]     │ │
│  └───────────────────────────────────┘ │
└─────────────────────────────────────────┘
```

**Components**:
- StatCard (metrics)
- Chart (compliance by regulation)
- Table (recent runs)
- FilterDropdown (regulation, date range)

**Interactions**:
- Click metrics: Filter to that status
- Click chart: Drill down to details
- Click table row: Navigate to compliance report

---

### UI-CPO-002: Compliance Report

**Screen ID**: UI-CPO-002  
**Screen Name**: Compliance Report  
**Persona**: Compliance Officer  
**Purpose**: Detailed compliance report

**Layout**:
```
┌─────────────────────────────────────────┐
│ Title: Compliance Report - Asset Name   │
├─────────────────────────────────────────┤
│                                         │
│  Summary Card:                          │
│  ┌───────────────────────────────────┐ │
│  │ Status: ⚠ Warning                 │ │
│  │ Risk Level: Medium                │ │
│  │ Allowed to Store: Yes              │ │
│  │ Regulations: GDPR, LGPD           │ │
│  └───────────────────────────────────┘ │
│                                         │
│  Detected Categories:                   │
│  [PII_EMAIL] [PII_NAME] [FINANCIAL]    │
│                                         │
│  Column Findings:                       │
│  ┌───────────────────────────────────┐ │
│  │ Column │ Categories │ Risk │ Notes│ │
│  ├────────┼────────────┼──────┼──────┤ │
│  │ email  │ PII_EMAIL  │ High │ ...  │ │
│  │ name   │ PII_NAME   │ Med  │ ...  │ │
│  └───────────────────────────────────┘ │
│                                         │
│  [Export PDF] [Export CSV] [Add Note] │
└─────────────────────────────────────────┘
```

**Components**:
- SummaryCard
- Badge (categories)
- Table (column findings)
- Button (Export, Add Note)

**Interactions**:
- Export: Generate PDF/CSV report
- Add Note: Add compliance annotation
- Column click: Show detailed findings

---

## Data Consumer Interfaces

### UI-DC-001: Marketplace

**Screen ID**: UI-DC-001  
**Screen Name**: Marketplace  
**Persona**: Data Consumer  
**Purpose**: Browse and discover marketplace assets

**Layout**:
```
┌─────────────────────────────────────────┐
│ Title: Marketplace                      │
├─────────────────────────────────────────┤
│                                         │
│  [Search: "customer data"]               │
│                                         │
│  Filters:                               │
│  [Domain ▼] [Price ▼] [Quality ▼]      │
│                                         │
│  ┌───────────┬───────────┬───────────┐ │
│  │ Asset 1   │ Asset 2   │ Asset 3   │ │
│  │           │           │           │ │
│  │ Title     │ Title     │ Title     │ │
│  │ Provider  │ Provider  │ Provider  │ │
│  │ ✓ Quality │ ⚠ Quality │ ✓ Quality │ │
│  │ $99       │ Free      │ $199      │ │
│  │ [View]    │ [View]    │ [View]    │ │
│  └───────────┴───────────┴───────────┘ │
│                                         │
│  [← Previous]  Page 1 of 10  [Next →] │
└─────────────────────────────────────────┘
```

**Components**:
- SearchInput
- FilterDropdown (Domain, Price, Quality)
- CardGrid (asset cards)
- Pagination
- Badge (Quality, Compliance)

**Interactions**:
- Search: Real-time filtering
- Filters: Apply immediately
- Card click: Navigate to asset detail
- View button: Navigate to asset detail

---

### UI-DC-002: Marketplace Asset Detail

**Screen ID**: UI-DC-002  
**Screen Name**: Marketplace Asset Detail  
**Persona**: Data Consumer  
**Purpose**: View asset details and purchase

**Layout**:
```
┌─────────────────────────────────────────┐
│ Title: Customer Orders Dataset          │
│ Provider: Acme Corp                     │
├─────────────────────────────────────────┤
│                                         │
│  ┌─────────────────┬─────────────────┐ │
│  │ Asset Details   │ Purchase Info   │ │
│  │                 │                 │ │
│  │ Description:    │ Price: $99     │ │
│  │ Customer order  │ License: ...    │ │
│  │ data with...    │                 │ │
│  │                 │ [Request Access]│ │
│  │ Schema Preview: │                 │ │
│  │ - order_id      │ Quality: ✓ Pass │ │
│  │ - customer_id   │ Compliance: ✓   │ │
│  │ - total         │                 │ │
│  │                 │                 │ │
│  │ Sample Data:    │                 │ │
│  │ [Table preview] │                 │ │
│  └─────────────────┴─────────────────┘ │
└─────────────────────────────────────────┘
```

**Components**:
- Card (asset details, purchase info)
- Table (schema preview, sample data)
- Badge (Quality, Compliance)
- Button (Request Access, Buy Now)

**Interactions**:
- Request Access: Create order, show confirmation
- Buy Now: Process payment (if applicable)
- Schema preview: Expandable table
- Sample data: Limited preview

---

## Tenant Admin Interfaces

### UI-TA-001: User Management

**Screen ID**: UI-TA-001  
**Screen Name**: User Management  
**Persona**: Tenant Admin  
**Purpose**: Manage tenant users

**Layout**:
```
┌─────────────────────────────────────────┐
│ Title: User Management                  │
├─────────────────────────────────────────┤
│                                         │
│  [Search]  [Status Filter] [Role Filter]│
│                                         │
│  ┌───────────────────────────────────┐ │
│  │ Name      │ Email    │ Role │ Status│ │
│  ├───────────┼──────────┼──────┼───────┤ │
│  │ John Doe  │ j@...    │ Admin│ Active│ │
│  │ Jane Smith│ jane@... │ Prov │ Active│ │
│  └───────────────────────────────────┘ │
│                                         │
│  [+ Invite User]                        │
└─────────────────────────────────────────┘
```

**Components**:
- SearchInput
- FilterDropdown (Status, Role)
- Table (users)
- Button (Invite User)
- Avatar (user avatars)

**Interactions**:
- Invite User: Open invite modal
- Row click: Navigate to user detail
- Actions: Edit, Deactivate, Delete

---

## Platform Admin Interfaces

### UI-PA-001: Tenant Management

**Screen ID**: UI-PA-001  
**Screen Name**: Tenant Management  
**Persona**: Platform Admin  
**Purpose**: Manage all tenants

**Layout**:
```
┌─────────────────────────────────────────┐
│ Title: Tenant Management                │
├─────────────────────────────────────────┤
│                                         │
│  ┌─────────┬─────────┬─────────┬──────┐ │
│  │ Total   │ Active  │ Susp.   │ KYC  │ │
│  │ Tenants │         │         │      │ │
│  │ 50      │ 45      │ 3       │ 40   │ │
│  └─────────┴─────────┴─────────┴──────┘ │
│                                         │
│  [Search]  [Status Filter] [KYC Filter]│
│                                         │
│  ┌───────────────────────────────────┐ │
│  │ Name    │ Status │ KYC │ Users │ ...│ │
│  ├─────────┼────────┼─────┼───────┼────┤ │
│  │ Acme    │ Active │ ✓   │ 25    │ ...│ │
│  │ Beta    │ Susp.  │ ✗   │ 10    │ ...│ │
│  └───────────────────────────────────┘ │
│                                         │
│  [+ Create Tenant]                      │
└─────────────────────────────────────────┘
```

**Components**:
- StatCard (tenant metrics)
- SearchInput
- FilterDropdown (Status, KYC)
- Table (tenants)
- Button (Create Tenant)

**Interactions**:
- Create Tenant: Open creation modal
- Row click: Navigate to tenant detail
- Actions: Suspend, Reactivate, Delete

---

## Common Interface Patterns

### Pattern-001: Data Table

**Purpose**: Display tabular data with sorting, filtering, pagination

**Components**:
- Table
- SearchInput
- FilterDropdown
- Pagination
- Action buttons

**Specifications**:
- Sortable columns
- Filterable columns
- Pagination (10, 25, 50, 100 per page)
- Row selection (checkbox)
- Bulk actions
- Export (CSV, JSON)

---

### Pattern-002: Form Layout

**Purpose**: Consistent form layout and validation

**Components**:
- Container
- Grid (2 columns on desktop)
- Form fields (TextInput, Select, etc.)
- Button group (Cancel, Submit)

**Specifications**:
- Required field indicators (*)
- Inline validation
- Error messages below fields
- Help text for complex fields
- Auto-save draft (where applicable)

---

### Pattern-003: Status Dashboard

**Purpose**: Display metrics and status overview

**Components**:
- StatCard (metrics)
- Chart (visualizations)
- Table (recent items)
- FilterDropdown

**Specifications**:
- Real-time updates (polling or WebSocket)
- Click to drill down
- Export capabilities
- Date range filters

---

## Screen Specifications

### Responsive Breakpoints

- **Mobile**: < 600px
- **Tablet**: 600px - 960px
- **Desktop**: 960px - 1280px
- **Large Desktop**: > 1280px

### Screen States

All screens support:
- **Loading**: Skeleton loaders or spinners
- **Empty**: Empty state with CTA
- **Error**: Error message with retry
- **Success**: Success message (toast)

### Navigation Patterns

- **Breadcrumbs**: Show current location
- **Back Button**: Return to previous screen
- **Cancel**: Close/discard changes
- **Save**: Save changes (with validation)

---

**Last Updated**: 2026-03-22  
**Version**: 1.0.0


---

# UX Patterns and Interactions

**Last Updated**: 2026-03-22  
**Version**: 1.0.0

---

## Table of Contents

1. [Overview](#overview)
2. [Navigation Patterns](#navigation-patterns)
3. [Form Patterns](#form-patterns)
4. [Data Display Patterns](#data-display-patterns)
5. [Feedback Patterns](#feedback-patterns)
6. [Error Handling Patterns](#error-handling-patterns)
7. [Loading Patterns](#loading-patterns)
8. [Empty State Patterns](#empty-state-patterns)
9. [Onboarding Patterns](#onboarding-patterns)
10. [Search and Discovery Patterns](#search-and-discovery-patterns)

---

## Overview

This document describes common UX patterns and interaction design guidelines for the Interoperable Data Hub platform. These patterns ensure consistency, usability, and a cohesive user experience across all interfaces.

**Pattern Principles**:
- **Consistency**: Use patterns consistently across the platform
- **Familiarity**: Follow platform conventions and user expectations
- **Efficiency**: Patterns should reduce cognitive load and time to complete tasks
- **Accessibility**: All patterns must be accessible to all users

---

## Navigation Patterns

### Pattern: Primary Navigation

**Purpose**: Main navigation for authenticated users

**Structure**:
- **Header**: Logo, primary navigation, user menu
- **Sidebar**: Secondary navigation (collapsible)
- **Breadcrumbs**: Current location trail

**Behavior**:
- Sticky header (stays at top on scroll)
- Sidebar collapses on mobile (hamburger menu)
- Active navigation item highlighted
- Breadcrumbs show full path

**Example**:
```
Header: [Logo] [Assets] [Marketplace] [Admin] ... [User Menu]
Sidebar: [Assets] [Onboarding] [DQ & Compliance] [Marketplace]
Breadcrumbs: Assets > Customer Orders > Edit
```

---

### Pattern: Tab Navigation

**Purpose**: Organize related content within a page

**Structure**:
- Horizontal tabs at top of content area
- Active tab highlighted with underline
- Tab content below tabs

**Behavior**:
- Click tab to switch content
- Keyboard navigation (arrow keys)
- URL updates with tab ID (for bookmarking)
- Smooth transition between tabs

**Example**:
```
[Overview] [Schema] [Quality] [Compliance] [Audit]
────────────────────────────────────────────────────
Content for selected tab appears here
```

---

### Pattern: Breadcrumb Navigation

**Purpose**: Show current location and enable quick navigation

**Structure**:
- Horizontal list of links
- Separator between items (/, >, or •)
- Last item is current page (not clickable)

**Behavior**:
- Click any breadcrumb to navigate
- Truncate long paths (show ... for middle items)
- Show full path on hover (tooltip)

**Example**:
```
Assets > Customer Orders > Edit Contract
```

---

## Form Patterns

### Pattern: Progressive Disclosure

**Purpose**: Show essential fields first, advanced options on demand

**Structure**:
- Basic fields visible by default
- "Advanced" or "More Options" expandable section
- Advanced fields hidden until expanded

**Behavior**:
- Click to expand/collapse
- Remember expanded state (localStorage)
- Smooth animation on expand/collapse

**Example**:
```
Basic Information:
[Asset Name*]
[Description]
[Domain]

[▼ Advanced Options]
  [Tags]
  [Custom Metadata]
  [Retention Policy]
```

---

### Pattern: Inline Validation

**Purpose**: Validate form fields as user types

**Structure**:
- Validation runs on blur (or after delay on type)
- Error message appears below field
- Success indicator (checkmark) for valid fields
- Field border changes color (red for error, green for success)

**Behavior**:
- Don't show errors until user interacts
- Clear errors when field becomes valid
- Show validation rules before user starts typing (helper text)

**Example**:
```
[Asset Name*]
✓ Valid name

[Email]
✗ Invalid email format
  Please enter a valid email address
```

---

### Pattern: Multi-Step Form

**Purpose**: Break complex forms into manageable steps

**Structure**:
- Stepper showing current step and progress
- One step visible at a time
- Navigation buttons (Back, Next, Skip)
- Summary step before submission

**Behavior**:
- Validate current step before proceeding
- Save progress automatically
- Allow navigation between completed steps
- Show progress indicator

**Example**:
```
Step 1: Basic Info        [Current]
Step 2: Upload Data       [Next]
Step 3: Review & Submit   [Future]

[← Back]              [Continue →]
```

---

## Data Display Patterns

### Pattern: Data Table

**Purpose**: Display tabular data with sorting, filtering, pagination

**Structure**:
- Table with sortable column headers
- Search bar above table
- Filters (dropdowns or chips)
- Pagination below table
- Row actions (menu or buttons)

**Behavior**:
- Click column header to sort (ascending/descending)
- Apply filters immediately
- Show loading state during data fetch
- Empty state when no data
- Row selection (checkbox) for bulk actions

**Example**:
```
[Search] [Status: All ▼] [Domain: All ▼]

┌─────────┬─────────┬─────────┬─────────┐
│ Name ▲  │ Domain  │ Status  │ Actions │
├─────────┼─────────┼─────────┼─────────┤
│ Asset 1 │ Sales   │ Active  │ [⋮]     │
│ Asset 2 │ Mktg    │ Draft   │ [⋮]     │
└─────────┴─────────┴─────────┴─────────┘

[← Previous]  Page 1 of 5  [Next →]
```

---

### Pattern: Card Grid

**Purpose**: Display items in a grid layout

**Structure**:
- Responsive grid (1-4 columns based on screen size)
- Cards with consistent structure
- Image/icon, title, description, actions
- Hover effects (elevation, scale)

**Behavior**:
- Click card to navigate to detail
- Hover shows additional actions
- Consistent card heights
- Loading skeleton while fetching

**Example**:
```
┌─────────┐ ┌─────────┐ ┌─────────┐
│ Asset 1 │ │ Asset 2 │ │ Asset 3 │
│ Title   │ │ Title   │ │ Title   │
│ Desc... │ │ Desc... │ │ Desc... │
│ [View]  │ │ [View]  │ │ [View]  │
└─────────┘ └─────────┘ └─────────┘
```

---

### Pattern: Detail View

**Purpose**: Show detailed information about a single item

**Structure**:
- Header with title and actions
- Summary cards (key metrics)
- Tabs for different sections
- Related items section

**Behavior**:
- Sticky header on scroll
- Tabs switch content smoothly
- Actions always accessible
- Breadcrumb navigation

**Example**:
```
┌─────────────────────────────────────┐
│ Asset Name              [Edit] [⋮] │
├─────────────────────────────────────┤
│ ┌──────┐ ┌──────┐ ┌──────┐ ┌────┐ │
│ │Contract│ │Quality│ │Comply│ │Mkt │ │
│ │ Valid  │ │ Pass  │ │ Pass │ │ ...│ │
│ └──────┘ └──────┘ └──────┘ └────┘ │
├─────────────────────────────────────┤
│ [Overview] [Schema] [Quality] ...  │
├─────────────────────────────────────┤
│ Content for selected tab            │
└─────────────────────────────────────┘
```

---

## Feedback Patterns

### Pattern: Toast Notifications

**Purpose**: Provide non-intrusive feedback for user actions

**Structure**:
- Small notification card
- Icon, message, optional action
- Auto-dismiss after duration
- Stack vertically when multiple

**Behavior**:
- Appear from top-right (or configurable)
- Slide in animation
- Auto-dismiss after 5 seconds (configurable)
- Manual dismiss (X button)
- Click to navigate (if applicable)

**Example**:
```
┌────────────────────────┐
│ ✓ Asset created        │
│   successfully         │
└────────────────────────┘
```

---

### Pattern: Inline Messages

**Purpose**: Provide contextual feedback within forms or content

**Structure**:
- Message box above or below related content
- Icon, title, message, optional action
- Color-coded by severity

**Behavior**:
- Dismissible (X button)
- Persistent until dismissed or condition changes
- Link to related content or actions

**Example**:
```
┌─────────────────────────────────────┐
│ ⚠ Warning                           │
│ Data quality issues detected.        │
│ [View Details]              [×]     │
└─────────────────────────────────────┘
```

---

### Pattern: Progress Indicators

**Purpose**: Show progress of long-running operations

**Structure**:
- Progress bar with percentage
- Step indicator (for multi-step processes)
- Estimated time remaining
- Cancel button (if applicable)

**Behavior**:
- Update in real-time
- Show current step and next steps
- Allow cancellation (with confirmation)
- Show completion message

**Example**:
```
Uploading file...
[████████░░] 80%
Estimated time: 30 seconds remaining
[Cancel]
```

---

## Error Handling Patterns

### Pattern: Form Validation Errors

**Purpose**: Show validation errors clearly and helpfully

**Structure**:
- Error message below field
- Field border turns red
- Error icon next to field
- Summary of all errors at top (optional)

**Behavior**:
- Show errors on blur or submit
- Clear errors when field becomes valid
- Focus first error field on submit
- Provide specific, actionable error messages

**Example**:
```
┌─────────────────────────────┐
│ ✗ Please fix the following: │
│   • Asset name is required  │
│   • Invalid email format    │
└─────────────────────────────┘

[Asset Name*]
✗ This field is required

[Email]
✗ Invalid email format
  Please enter a valid email address
```

---

### Pattern: Error Boundaries

**Purpose**: Handle unexpected errors gracefully

**Structure**:
- Error message with explanation
- Retry button
- Support link
- Error ID for reporting

**Behavior**:
- Catch and display errors
- Don't crash entire application
- Provide recovery options
- Log errors for debugging

**Example**:
```
┌─────────────────────────────────────┐
│ ⚠ Something went wrong              │
│                                     │
│ We encountered an unexpected error. │
│ Error ID: ERR-12345                 │
│                                     │
│ [Retry]  [Contact Support]          │
└─────────────────────────────────────┘
```

---

## Loading Patterns

### Pattern: Skeleton Loaders

**Purpose**: Show content structure while loading

**Structure**:
- Placeholder shapes matching content layout
- Animated shimmer effect
- Same dimensions as actual content

**Behavior**:
- Show immediately on load
- Replace with actual content when ready
- Smooth transition

**Example**:
```
┌─────────────────────────┐
│ ░░░░░░░░░░░░░░░░░░░░░░ │  (Title skeleton)
│ ░░░░░░░░░░░░░░░░░░░░░░ │  (Description)
│ ░░░░░░░░░░░░░░░░░░░░░░ │
└─────────────────────────┘
```

---

### Pattern: Loading Spinners

**Purpose**: Indicate operation in progress

**Structure**:
- Circular spinner
- Optional message
- Centered or inline

**Behavior**:
- Show immediately
- Smooth rotation animation
- Replace with content or error when done

**Example**:
```
    [Spinner]
  Loading...
```

---

## Empty State Patterns

### Pattern: Empty State with CTA

**Purpose**: Guide users when no data exists

**Structure**:
- Illustration or icon
- Title and description
- Primary action button
- Optional secondary actions

**Behavior**:
- Show when list/table is empty
- Provide clear next steps
- Link to relevant documentation

**Example**:
```
┌─────────────────────────────┐
│        [Illustration]        │
│                             │
│    No Assets Yet            │
│                             │
│    Create your first asset  │
│    to get started           │
│                             │
│    [+ Create Asset]         │
└─────────────────────────────┘
```

---

### Pattern: Empty Search Results

**Purpose**: Handle empty search results

**Structure**:
- Search icon or illustration
- Message about no results
- Suggestions or tips
- Clear search button

**Behavior**:
- Show when search returns no results
- Suggest alternative search terms
- Provide filters to refine search

**Example**:
```
┌─────────────────────────────┐
│        [Search Icon]         │
│                             │
│    No results found         │
│                             │
│    Try different keywords   │
│    or adjust your filters   │
│                             │
│    [Clear Search]           │
└─────────────────────────────┘
```

---

## Onboarding Patterns

### Pattern: Guided Tour

**Purpose**: Introduce new users to key features

**Structure**:
- Step-by-step tooltips
- Highlight relevant UI elements
- Progress indicator
- Skip option

**Behavior**:
- Show on first visit (or opt-in)
- Allow skipping
- Remember completion (don't show again)
- Smooth transitions between steps

**Example**:
```
┌─────────────────────────────┐
│ Welcome to Data Hub!         │
│                             │
│ This is the Assets page.    │
│ Create your first asset to  │
│ get started.                │
│                             │
│ [Skip Tour]  [Next →]       │
└─────────────────────────────┘
```

---

### Pattern: Contextual Help

**Purpose**: Provide help when and where needed

**Structure**:
- Help icon (?) next to complex fields
- Tooltip or popover with explanation
- Link to detailed documentation

**Behavior**:
- Show on hover or click
- Context-specific content
- Don't obstruct workflow

**Example**:
```
[Asset Name*]  [?]
               ┌─────────────────────┐
               │ Asset Name          │
               │                     │
               │ A unique identifier │
               │ for your asset      │
               │                     │
               │ [Learn More →]      │
               └─────────────────────┘
```

---

## Search and Discovery Patterns

### Pattern: Global Search

**Purpose**: Quick access to search across platform

**Structure**:
- Search bar in header
- Autocomplete suggestions
- Recent searches
- Quick filters

**Behavior**:
- Focus with keyboard shortcut (Cmd/Ctrl+K)
- Show suggestions as user types
- Highlight search terms in results
- Navigate to result on selection

**Example**:
```
[Search: "customer orders"        ]
┌─────────────────────────────────┐
│ Recent Searches:                │
│ • customer data                 │
│ • order history                 │
│                                 │
│ Suggestions:                    │
│ • customer_orders (Asset)       │
│ • customer_data (Asset)         │
└─────────────────────────────────┘
```

---

### Pattern: Advanced Filters

**Purpose**: Refine search and filter results

**Structure**:
- Filter panel or dropdowns
- Multiple filter types (text, select, date range)
- Active filters shown as chips
- Clear all option

**Behavior**:
- Apply filters immediately
- Show active filter count
- Allow removing individual filters
- Save filter presets (future)

**Example**:
```
Filters:
[Status: Active ▼] [Domain: Sales ▼]
[Date Range: Last 30 days ▼]

Active Filters:
[Status: Active ×] [Domain: Sales ×]
[Clear All]
```

---

**Last Updated**: 2026-03-22  
**Version**: 1.0.0


---

# Frontend Integration API Migration Plan

**Task**: 7.10 — Replace axios mocks in frontend unit tests with real API integration tests  
**Last Updated**: 2026-03-22  
**Related**: [TEST_ASSERTION_CONVENTIONS.md](TEST_ASSERTION_CONVENTIONS.md), [TEST_EXECUTION_PLAN.md](TEST_EXECUTION_PLAN.md)

---

## 1. Overview

Critical frontend flows (auth, assets, contracts, marketplace) currently use axios mocks in unit tests. This plan migrates those tests to **real API integration tests** that run against a live backend. No mocks or stubs; root-cause validation only.

---

## 2. Migration Order (by Criticality)

| Priority | Flow       | Current State                                      | Target State                                      |
|----------|------------|----------------------------------------------------|---------------------------------------------------|
| 1        | **Auth**   | `authService.test.ts`, `LoginPage.test.tsx` — axios mocks | Real API integration tests (`auth.integration.test.ts`) |
| 2        | **Assets** | `assetService.test.ts`, `useAssets.test.tsx` — axios mocks | Real API integration tests (`assets.integration.test.ts`) |
| 3        | **Contracts** | `contractService.test.ts`, `useContracts.test.tsx` — axios mocks | Real API integration tests (`contracts.integration.test.ts`) |
| 4        | **Marketplace** | No unit tests; services exist (`listingService`, `orderService`, `entitlementService`) | Real API integration tests (`marketplace.integration.test.ts`) |

**Removed (replaced by integration tests)**: `authService.test.ts`, `assetService.test.ts`, `contractService.test.ts`, `useAssets.test.tsx`, `useContracts.test.tsx`, `LoginPage.test.tsx` — all used axios mocks; coverage now via `src/integration/*.integration.test.ts` and E2E.

---

## 3. How to Run

### 3.1 Prerequisites

- Backend running (API at port 8000 or 8001)
- E2E test user: `e2e_test@example.com` / `TestPass123` (created by `ensure_e2e_user_roles` or `ensure_e2e_subscription`)
- Run `docker exec hub-test-api python hub/manage.py ensure_e2e_user_roles` (or equivalent for dev stack) before first run

### 3.2 Commands

| Command | Description |
|---------|-------------|
| `cd frontend && npm run test:integration:api` | Auto-detect backend (8000/8001), set `VITE_API_BASE_URL`, run integration tests |
| `VITE_API_BASE_URL=http://localhost:8001/api/v1 npx vitest run --config vitest.integration.config.ts` | Explicit API URL (e.g. for CI) |

### 3.3 Script Behavior

`scripts/run-integration-api-tests.sh`:

1. Detects backend at port 8000 (dev) or 8001 (test)
2. Sets `VITE_API_BASE_URL` and exports for Vitest
3. Optionally runs `ensure_e2e_user_roles` when using test stack
4. Runs `vitest --run` with `src/integration/**/*.integration.test.ts`
5. Exits 1 if backend not found or tests fail

---

## 4. Environment Requirements

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `VITE_API_BASE_URL` | No (auto-detected) | `http://localhost:8000/api/v1` or `http://localhost:8001/api/v1` | Full API base URL |
| Backend | Yes | — | `docker compose up` (dev or test) |
| E2E users | Yes | — | `ensure_e2e_user_roles` run once per stack |

---

## 5. Test File Layout

```
frontend/src/integration/
├── auth.integration.test.ts        # Auth: login, logout, refresh, me
├── assets.integration.test.ts     # Assets: list, get, create, update, delete
├── contracts.integration.test.ts  # Contracts: list, get, create, validate
└── marketplace.integration.test.ts # Marketplace: listings, orders (if endpoints exist)
```

---

## 6. What Stays as Unit Tests

- Pure logic (no HTTP): error handling, data transformation, validation helpers
- Components that only need store/context (no API): keep unit tests with store mocks only where necessary
- Tests that assert UI behavior without API: keep if they don't mock axios

---

## 7. References

- [TEST_ASSERTION_CONVENTIONS.md](TEST_ASSERTION_CONVENTIONS.md) — Section 6: Frontend real-API integration tests
- [E2E_ENVIRONMENT_REQUIREMENTS.md](E2E_ENVIRONMENT_REQUIREMENTS.md) — Service availability
- [TEST_EXECUTION_PLAN.md](TEST_EXECUTION_PLAN.md) — Phase 12A.2.1, 12A.2.2
