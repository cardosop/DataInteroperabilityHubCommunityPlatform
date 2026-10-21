/**
 * FullPageSpinner — full-viewport loading indicator.
 * Used as Suspense fallback and ProtectedRoute loading state.
 * Semantic alias for LoadingSpinner with full-page centering defaults.
 */
import React from 'react';
import { LoadingSpinner } from './LoadingSpinner';

interface FullPageSpinnerProps {
  message?: string;
}

export const FullPageSpinner: React.FC<FullPageSpinnerProps> = ({ message }) => {
  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        minHeight: '100vh',
        width: '100%',
      }}
    >
      <LoadingSpinner message={message} />
    </div>
  );
};
