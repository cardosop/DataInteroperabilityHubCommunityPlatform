/**
 * Button Component
 *
 * Reusable button with variant, size, loading state, and optional icons.
 * Replaces scattered .btn-primary / .btn-secondary / .btn-danger / .btn-back
 * classes with a single composable component.
 */

import { forwardRef } from 'react';
import type { ComponentType, SVGProps } from 'react';
import './Button.css';

/** Lucide-style icon component type (accepts size, className, etc.) */
type IconComponent = ComponentType<SVGProps<SVGSVGElement> & { size?: number | string }>;

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'danger' | 'ghost';
  size?: 'sm' | 'md' | 'lg';
  loading?: boolean;
  leadingIcon?: IconComponent;
  trailingIcon?: IconComponent;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  {
    variant = 'primary',
    size = 'md',
    loading = false,
    leadingIcon: LeadingIcon,
    trailingIcon: TrailingIcon,
    disabled,
    className,
    children,
    type = 'button',
    ...rest
  },
  ref,
) {
  const isDisabled = disabled || loading;

  const classes = [
    'btn',
    `btn--${variant}`,
    `btn--${size}`,
    loading ? 'btn--loading' : '',
    className ?? '',
  ]
    .filter(Boolean)
    .join(' ');

  return (
    <button
      ref={ref}
      type={type}
      className={classes}
      disabled={isDisabled}
      aria-busy={loading || undefined}
      {...rest}
    >
      {loading && (
        <span className="btn__spinner" aria-hidden="true" />
      )}
      {!loading && LeadingIcon && (
        <LeadingIcon className="btn__icon" size={16} aria-hidden="true" />
      )}
      {children && <span className="btn__label">{children}</span>}
      {!loading && TrailingIcon && (
        <TrailingIcon className="btn__icon" size={16} aria-hidden="true" />
      )}
    </button>
  );
});
