# Error Handling UI Patterns

**Last Updated**: 2025-12-13  
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

**Last Updated**: 2025-12-13  
**Version**: 1.0.0

