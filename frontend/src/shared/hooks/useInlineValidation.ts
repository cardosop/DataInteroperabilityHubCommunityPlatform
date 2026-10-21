/**
 * Phase 278.G.2 — inline form validation with debounce + fix hints.
 *
 * Usage:
 *   const { error, validate } = useInlineValidation(rules, { delayMs: 500 });
 *   <input onChange={(e) => validate(e.target.value)} />
 *   {error && <span className="field-hint">{error}</span>}
 */
import { useCallback, useRef, useState } from 'react';

export interface ValidationRule {
  /** Human-readable error message when this rule fails. */
  message: string;
  /** Predicate: return true if the value passes this rule. */
  test: (value: string) => boolean;
}

export interface ValidationResult {
  error: string | null;
  valid: boolean;
}

interface UseInlineValidationOptions {
  delayMs?: number;
}

export function useInlineValidation(
  rules: ValidationRule[],
  options: UseInlineValidationOptions = {},
): {
  error: string | null;
  valid: boolean;
  validate: (value: string) => void;
  reset: () => void;
} {
  const [error, setError] = useState<string | null>(null);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const { delayMs = 500 } = options;

  const validate = useCallback(
    (value: string) => {
      if (timerRef.current) {
        clearTimeout(timerRef.current);
      }
      timerRef.current = setTimeout(() => {
        for (const rule of rules) {
          if (!rule.test(value)) {
            setError(rule.message);
            return;
          }
        }
        setError(null);
      }, delayMs);
    },
    [rules, delayMs],
  );

  const reset = useCallback(() => {
    if (timerRef.current) {
      clearTimeout(timerRef.current);
    }
    setError(null);
  }, []);

  return {
    error,
    valid: error === null,
    validate,
    reset,
  };
}

/** Preset validation rules for common form fields. */
export const CommonRules = {
  required: (label: string): ValidationRule => ({
    message: `${label} is required.`,
    test: (v) => v.trim().length > 0,
  }),
  minLength: (label: string, min: number): ValidationRule => ({
    message: `${label} must be at least ${min} characters.`,
    test: (v) => v.length >= min,
  }),
  maxLength: (label: string, max: number): ValidationRule => ({
    message: `${label} must be under ${max} characters.`,
    test: (v) => v.length <= max,
  }),
  email: (): ValidationRule => ({
    message: 'Please enter a valid email address.',
    test: (v) => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(v),
  }),
  url: (label: string): ValidationRule => ({
    message: `${label} must be a valid URL (https://...).`,
    test: (v) => /^https?:\/\/.+/.test(v),
  }),
  slug: (label: string): ValidationRule => ({
    message: `${label} must contain only lowercase letters, numbers, and hyphens.`,
    test: (v) => /^[a-z0-9][a-z0-9-]*[a-z0-9]$/.test(v) || v.length <= 2 && /^[a-z0-9]+$/.test(v),
  }),
};
