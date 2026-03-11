/**
 * UuidWithCopy Component
 * Displays a UUID with a copy-to-clipboard button for manual linking
 */

import { useState } from 'react';
import './UuidWithCopy.css';

export interface UuidWithCopyProps {
  /** The UUID value to display and copy */
  value: string;
  /** Optional label (e.g. "Asset ID", "Dataset ID") */
  label?: string;
}

export function UuidWithCopy({ value, label }: UuidWithCopyProps) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(value);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Fallback for older browsers or non-HTTPS
      setCopied(false);
    }
  };

  return (
    <div className="uuid-with-copy">
      {label && <label className="uuid-label">{label}</label>}
      <div className="uuid-value-row">
        <code className="uuid-value">{value}</code>
        <button
          type="button"
          className="uuid-copy-btn"
          onClick={handleCopy}
          aria-label="Copy UUID"
          title={copied ? 'Copied!' : 'Copy to clipboard'}
        >
          {copied ? '✓' : '📋'}
        </button>
      </div>
    </div>
  );
}
