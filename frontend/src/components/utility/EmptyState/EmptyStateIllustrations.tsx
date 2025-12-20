import React from 'react'
import { colors } from '@/styles/tokens'

export interface EmptyStateIllustrationProps {
  /**
   * Size of the illustration
   * @default 120
   */
  size?: number
  /**
   * Color of the illustration
   * @default colors.semantic.textSecondary
   */
  color?: string
}

/**
 * Empty box illustration
 */
export const EmptyBoxIllustration: React.FC<EmptyStateIllustrationProps> = ({
  size = 120,
  color = colors.semantic.textSecondary,
}) => {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 120 120"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      aria-hidden="true"
    >
      <rect
        x="20"
        y="30"
        width="80"
        height="70"
        rx="4"
        stroke={color}
        strokeWidth="2"
        strokeDasharray="4 4"
        fill="none"
        opacity="0.3"
      />
      <path
        d="M20 30 L60 50 L100 30"
        stroke={color}
        strokeWidth="2"
        fill="none"
        opacity="0.5"
      />
      <circle cx="60" cy="65" r="8" fill={color} opacity="0.2" />
    </svg>
  )
}

/**
 * Empty folder illustration
 */
export const EmptyFolderIllustration: React.FC<EmptyStateIllustrationProps> = ({
  size = 120,
  color = colors.semantic.textSecondary,
}) => {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 120 120"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      aria-hidden="true"
    >
      <path
        d="M20 40 L30 30 L50 30 L60 40 L100 40 L100 90 L20 90 Z"
        fill={color}
        fillOpacity="0.1"
        stroke={color}
        strokeWidth="2"
      />
      <path
        d="M30 30 L50 30 L60 40 L30 40 Z"
        fill={color}
        fillOpacity="0.2"
        stroke={color}
        strokeWidth="2"
      />
      <circle cx="60" cy="65" r="6" fill={color} opacity="0.3" />
    </svg>
  )
}

/**
 * Empty search illustration
 */
export const EmptySearchIllustration: React.FC<EmptyStateIllustrationProps> = ({
  size = 120,
  color = colors.semantic.textSecondary,
}) => {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 120 120"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      aria-hidden="true"
    >
      <circle
        cx="45"
        cy="45"
        r="25"
        stroke={color}
        strokeWidth="2"
        fill="none"
        opacity="0.5"
      />
      <path
        d="M65 65 L85 85"
        stroke={color}
        strokeWidth="2"
        strokeLinecap="round"
        opacity="0.5"
      />
      <path
        d="M30 30 Q20 20 10 30 Q20 40 30 30"
        stroke={color}
        strokeWidth="1.5"
        fill="none"
        opacity="0.3"
      />
    </svg>
  )
}

/**
 * Empty list illustration
 */
export const EmptyListIllustration: React.FC<EmptyStateIllustrationProps> = ({
  size = 120,
  color = colors.semantic.textSecondary,
}) => {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 120 120"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      aria-hidden="true"
    >
      <rect
        x="20"
        y="25"
        width="80"
        height="12"
        rx="2"
        fill={color}
        fillOpacity="0.1"
        stroke={color}
        strokeWidth="1"
        opacity="0.5"
      />
      <rect
        x="20"
        y="45"
        width="80"
        height="12"
        rx="2"
        fill={color}
        fillOpacity="0.1"
        stroke={color}
        strokeWidth="1"
        opacity="0.5"
      />
      <rect
        x="20"
        y="65"
        width="60"
        height="12"
        rx="2"
        fill={color}
        fillOpacity="0.1"
        stroke={color}
        strokeWidth="1"
        opacity="0.5"
      />
      <circle cx="60" cy="85" r="8" fill={color} opacity="0.2" />
    </svg>
  )
}

/**
 * Empty data illustration
 */
export const EmptyDataIllustration: React.FC<EmptyStateIllustrationProps> = ({
  size = 120,
  color = colors.semantic.textSecondary,
}) => {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 120 120"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      aria-hidden="true"
    >
      <rect
        x="25"
        y="30"
        width="70"
        height="60"
        rx="4"
        fill={color}
        fillOpacity="0.05"
        stroke={color}
        strokeWidth="2"
        strokeDasharray="6 6"
      />
      <path
        d="M35 50 L55 50 M35 60 L75 60 M35 70 L65 70"
        stroke={color}
        strokeWidth="2"
        strokeLinecap="round"
        opacity="0.3"
      />
      <circle cx="60" cy="45" r="4" fill={color} opacity="0.3" />
    </svg>
  )
}

/**
 * Empty network illustration
 */
export const EmptyNetworkIllustration: React.FC<EmptyStateIllustrationProps> = ({
  size = 120,
  color = colors.semantic.textSecondary,
}) => {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 120 120"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      aria-hidden="true"
    >
      <circle cx="30" cy="30" r="12" fill={color} fillOpacity="0.1" stroke={color} strokeWidth="2" />
      <circle cx="90" cy="30" r="12" fill={color} fillOpacity="0.1" stroke={color} strokeWidth="2" />
      <circle cx="60" cy="60" r="12" fill={color} fillOpacity="0.1" stroke={color} strokeWidth="2" />
      <circle cx="30" cy="90" r="12" fill={color} fillOpacity="0.1" stroke={color} strokeWidth="2" />
      <circle cx="90" cy="90" r="12" fill={color} fillOpacity="0.1" stroke={color} strokeWidth="2" />
      <line x1="30" y1="30" x2="60" y2="60" stroke={color} strokeWidth="1.5" opacity="0.3" />
      <line x1="90" y1="30" x2="60" y2="60" stroke={color} strokeWidth="1.5" opacity="0.3" />
      <line x1="30" y1="90" x2="60" y2="60" stroke={color} strokeWidth="1.5" opacity="0.3" />
      <line x1="90" y1="90" x2="60" y2="60" stroke={color} strokeWidth="1.5" opacity="0.3" />
    </svg>
  )
}

