# Analytics Integration Guide

**Last Updated**: 2025-12-13  
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

**Last Updated**: 2025-12-13  
**Version**: 1.0.0

