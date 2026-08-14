/**
 * HelpTip — inline help icon with popover explanation (278.J.1).
 *
 * Renders a "(?)" icon next to jargon terms. On hover/focus, shows a
 * popover with a 2-sentence explanation and a "Learn more" link.
 * Content is sourced from JARGON_GLOSSARY (278.J.3).
 */
import { type FC, useState, useRef, useCallback, useEffect } from 'react';
import { JARGON_GLOSSARY } from './HelpTip.glossary';
import './HelpTip.css';

export interface HelpTipProps {
  /** Jargon term key from the glossary (case-insensitive). */
  term: string;
  /** Override the popover text (optional). */
  description?: string;
  /** Override the learn-more URL (optional). */
  learnMoreUrl?: string;
  /** Position of the popover relative to the icon. */
  position?: 'top' | 'bottom' | 'right';
}

export const HelpTip: FC<HelpTipProps> = ({
  term,
  description,
  learnMoreUrl,
  position = 'top',
}) => {
  const [open, setOpen] = useState(false);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const popoverRef = useRef<HTMLDivElement>(null);

  const entry = JARGON_GLOSSARY[term.toUpperCase()] ?? JARGON_GLOSSARY[term.toLowerCase()];

  const desc = description ?? entry?.description ?? 'No help available for this term.';
  const url = learnMoreUrl ?? entry?.learnMoreUrl;

  const handleOpen = useCallback(() => setOpen(true), []);
  const handleClose = useCallback(() => setOpen(false), []);

  // Close on outside click
  useEffect(() => {
    if (!open) return;
    const handler = (e: MouseEvent) => {
      if (
        triggerRef.current && !triggerRef.current.contains(e.target as Node) &&
        popoverRef.current && !popoverRef.current.contains(e.target as Node)
      ) {
        setOpen(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [open]);

  // Close on Escape
  useEffect(() => {
    if (!open) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setOpen(false);
    };
    document.addEventListener('keydown', handler);
    return () => document.removeEventListener('keydown', handler);
  }, [open]);

  const popoverId = `helptip-${term.replace(/\s+/g, '-').toLowerCase()}`;

  return (
    <span className="helptip" data-testid="helptip">
      <button
        ref={triggerRef}
        type="button"
        className="helptip__trigger"
        onClick={handleOpen}
        onFocus={() => setOpen(true)}
        onBlur={(e) => {
          // Delay to allow click on popover link
          if (!popoverRef.current?.contains(e.relatedTarget as Node)) {
            setOpen(false);
          }
        }}
        aria-expanded={open}
        aria-controls={popoverId}
        aria-label={`Help: ${term}`}
        title={`What is ${term}?`}
      >
        ?
      </button>
      {open && (
        <div
          ref={popoverRef}
          id={popoverId}
          className={`helptip__popover helptip__popover--${position}`}
          role="tooltip"
        >
          <p className="helptip__text">{desc}</p>
          {url && (
            <a
              href={url}
              target="_blank"
              rel="noopener noreferrer"
              className="helptip__link"
              onClick={handleClose}
            >
              Learn more →
            </a>
          )}
        </div>
      )}
    </span>
  );
};
