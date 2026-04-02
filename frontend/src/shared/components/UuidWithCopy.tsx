/**
 * UuidWithCopy Component
 * Displays a UUID with a copy-to-clipboard button for manual linking
 */

import { useState, useRef, useCallback } from 'react';
import { Button } from './Button';
import './UuidWithCopy.css';

export interface UuidWithCopyProps {
  /** The UUID value to display and copy */
  value: string;
  /** Optional label (e.g. "Asset ID", "Dataset ID") */
  label?: string;
}

export function UuidWithCopy({ value, label }: UuidWithCopyProps) {
  const [copied, setCopied] = useState(false);
  const timerRef = useRef<ReturnType<typeof setTimeout>>(undefined);

  const handleCopy = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(value);
      setCopied(true);
      clearTimeout(timerRef.current);
      timerRef.current = setTimeout(() => setCopied(false), 2000);
    } catch {
      // Fallback for older browsers or non-HTTPS
      setCopied(false);
    }
  }, [value]);

  return (
    <div className="uuid-with-copy">
      {label && <label className="uuid-label">{label}</label>}
      <div className="uuid-value-row">
        <code className="uuid-value">{value}</code>
        <Button
          variant="ghost"
          size="sm"
          onClick={handleCopy}
          aria-label="Copy UUID"
          title={copied ? 'Copied!' : 'Copy to clipboard'}
          className="uuid-copy-btn"
        >
          {copied ? '✓' : '📋'}
        </Button>
      </div>
    </div>
  );
}
