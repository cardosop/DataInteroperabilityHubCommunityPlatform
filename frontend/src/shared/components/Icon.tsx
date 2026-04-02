/**
 * Icon — Phase 34 (32.2)
 *
 * Wrapper for lucide-react icons with token-driven sizing,
 * semantic aria attributes, and className passthrough.
 */

import type { LucideIcon } from 'lucide-react';

type IconSize = 'xs' | 'sm' | 'md' | 'lg';

const SIZE_MAP: Record<IconSize, string> = {
  xs: 'var(--icon-size-xs, 12px)',
  sm: 'var(--icon-size-sm, 16px)',
  md: 'var(--icon-size-md, 20px)',
  lg: 'var(--icon-size-lg, 24px)',
};

export interface IconProps {
  icon: LucideIcon;
  size?: IconSize;
  'aria-hidden'?: boolean;
  'aria-label'?: string;
  className?: string;
}

export function Icon({
  icon: LucideComponent,
  size = 'md',
  'aria-hidden': ariaHidden = true,
  'aria-label': ariaLabel,
  className,
}: IconProps) {
  const dim = SIZE_MAP[size];

  return (
    <LucideComponent
      style={{ width: dim, height: dim }}
      aria-hidden={ariaLabel ? false : ariaHidden}
      aria-label={ariaLabel}
      className={className}
    />
  );
}
