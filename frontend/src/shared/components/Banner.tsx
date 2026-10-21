/**
 * Banner — dismissible notification bar with variant-driven colours.
 */

import { Info, AlertTriangle, XCircle, CheckCircle, X } from '../config/iconRegistry';
import type { ComponentType, SVGProps, ReactNode } from 'react';
import { Button } from './Button';
import './Banner.css';

type BannerVariant = 'info' | 'warning' | 'error' | 'success';

export interface BannerProps {
  variant: BannerVariant;
  children: ReactNode;
  onDismiss?: () => void;
}

type IconType = ComponentType<SVGProps<SVGSVGElement> & { size?: number | string }>;

const ICON_MAP: Record<BannerVariant, IconType> = {
  info: Info,
  warning: AlertTriangle,
  error: XCircle,
  success: CheckCircle,
};

export function Banner({ variant, children, onDismiss }: BannerProps) {
  const Icon = ICON_MAP[variant];

  return (
    <div className={`banner banner--${variant}`} role="status">
      <Icon className="banner__icon" size={18} aria-hidden="true" />
      <div className="banner__content">{children}</div>
      {onDismiss && (
        <Button
          variant="ghost"
          size="sm"
          onClick={onDismiss}
          aria-label="Dismiss"
          className="banner__dismiss"
          leadingIcon={X}
        />
      )}
    </div>
  );
}
