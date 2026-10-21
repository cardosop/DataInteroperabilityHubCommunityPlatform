/**
 * FeatureErrorBoundary
 * React class-based error boundary for feature sections.
 * Catches render errors and shows a styled fallback with retry.
 */

import React from 'react';

interface FeatureErrorBoundaryProps {
  feature: string;
  children: React.ReactNode;
}

interface FeatureErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
}

export class FeatureErrorBoundary extends React.Component<
  FeatureErrorBoundaryProps,
  FeatureErrorBoundaryState
> {
  constructor(props: FeatureErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): FeatureErrorBoundaryState {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, info: React.ErrorInfo): void {
    console.error(
      `[FeatureErrorBoundary] Uncaught error in feature "${this.props.feature}":`,
      error,
      info.componentStack
    );
  }

  handleRetry = (): void => {
    this.setState({ hasError: false, error: null });
  };

  render(): React.ReactNode {
    if (this.state.hasError) {
      const { feature } = this.props;
      const message = this.state.error?.message ?? 'An unexpected error occurred';

      return (
        <div
          data-testid="feature-error-boundary-fallback"
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            minHeight: '300px',
            padding: '2rem',
          }}
        >
          <div
            style={{
              maxWidth: '480px',
              width: '100%',
              border: '1px solid #fca5a5',
              borderRadius: '8px',
              backgroundColor: '#fff5f5',
              padding: '2rem',
              textAlign: 'center',
            }}
          >
            <h2
              style={{
                fontSize: '1.25rem',
                fontWeight: 600,
                color: '#dc2626',
                marginBottom: '0.75rem',
              }}
            >
              Something went wrong
            </h2>
            <p style={{ color: '#6b7280', marginBottom: '0.5rem' }}>
              The <strong>{feature}</strong> section failed to load.
            </p>
            <p
              style={{
                fontSize: '0.875rem',
                color: '#9ca3af',
                marginBottom: '1.5rem',
                wordBreak: 'break-word',
              }}
            >
              {message}
            </p>
            <button
              data-testid="feature-error-boundary-retry"
              onClick={this.handleRetry}
              style={{
                backgroundColor: '#dc2626',
                color: '#fff',
                border: 'none',
                borderRadius: '6px',
                padding: '0.5rem 1.25rem',
                fontSize: '0.875rem',
                fontWeight: 500,
                cursor: 'pointer',
              }}
            >
              Try again
            </button>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}
