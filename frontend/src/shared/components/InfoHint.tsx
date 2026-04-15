/**
 * InfoHint — inline contextual help marker.
 *
 * Renders a small help-circle icon button that surfaces a tooltip on hover
 * or keyboard focus. Use inline next to field labels or column headers to
 * explain technical terms without cluttering the UI.
 */

import { HelpCircle } from 'lucide-react';
import { forwardRef, type ReactNode, type Ref } from 'react';
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

// Forwarded-ref wrapper so Tooltip can attach its floating-ui reference to the
// real <button> element rather than a DOM wrapper, preserving focus ring and
// native keyboard semantics.
const HintTrigger = forwardRef(function HintTrigger(
  props: { label: string; size: number } & Record<string, unknown>,
  ref: Ref<HTMLButtonElement>,
) {
  const { label, size, ...rest } = props;
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
});

export function InfoHint({ label, content, size = 14 }: InfoHintProps) {
  return (
    <Tooltip content={content}>
      <HintTrigger label={label} size={size} />
    </Tooltip>
  );
}
