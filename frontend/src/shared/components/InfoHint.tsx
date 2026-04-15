/**
 * InfoHint — inline contextual help marker.
 *
 * Renders a small help-circle icon button that surfaces a tooltip on hover
 * or keyboard focus. Use inline next to field labels or column headers to
 * explain technical terms without cluttering the UI.
 */

import { HelpCircle } from 'lucide-react';
import { forwardRef, type ReactNode, type ButtonHTMLAttributes } from 'react';
import { Tooltip } from './Tooltip';
import './InfoHint.css';

export interface InfoHintProps {
  /** Accessible label describing the concept (used as button aria-label). */
  label: string;
  /** Tooltip body content — plain text or rich nodes. */
  content: ReactNode;
  /** Icon size in px. Defaults to 14 to pair with body copy. */
  size?: number;
}

// Explicit generics on forwardRef<Element, Props> so TypeScript doesn't have
// to infer the `ref` type from the function signature — the previous version
// tripped TS2345/TS2322 because `forwardRef` strips `ref` from Props via
// `Omit<…, 'ref'>` and the intersection with `Record<string, unknown>` broke
// the narrowing. Forwarding all native <button> props lets Tooltip attach
// handlers (onMouseEnter, onFocus, …) cleanly.
type HintTriggerProps = { label: string; size: number } &
  ButtonHTMLAttributes<HTMLButtonElement>;

const HintTrigger = forwardRef<HTMLButtonElement, HintTriggerProps>(
  function HintTrigger({ label, size, ...rest }, ref) {
    return (
      <button
        type="button"
        ref={ref}
        className="info-hint-trigger"
        aria-label={label}
        {...rest}
      >
        <HelpCircle size={size} aria-hidden="true" focusable="false" />
      </button>
    );
  },
);

export function InfoHint({ label, content, size = 14 }: InfoHintProps) {
  return (
    <Tooltip content={content}>
      <HintTrigger label={label} size={size} />
    </Tooltip>
  );
}
