import React from 'react'
import { cn } from '@/components/utils'
import { colors, borderRadius } from '@/styles/tokens'

export interface AvatarProps {
  /**
   * Image source URL
   */
  src?: string
  /**
   * Alt text
   */
  alt?: string
  /**
   * Size of the avatar
   * @default 'md'
   */
  size?: 'sm' | 'md' | 'lg'
  /**
   * Initials to display if no image
   */
  initials?: string
  className?: string
}

const sizeMap = {
  sm: 32,
  md: 40,
  lg: 48,
} as const

/**
 * Avatar component for user avatars
 */
export const Avatar: React.FC<AvatarProps> = ({
  src,
  alt,
  size = 'md',
  initials,
  className,
}) => {
  const avatarSize = sizeMap[size]

  if (src) {
    return (
      <img
        src={src}
        alt={alt || 'Avatar'}
        className={cn('avatar', className)}
        style={{
          width: avatarSize,
          height: avatarSize,
          borderRadius: borderRadius.full,
          objectFit: 'cover',
        }}
      />
    )
  }

  return (
    <div
      className={cn('avatar', 'avatar-initials', className)}
      style={{
        width: avatarSize,
        height: avatarSize,
        borderRadius: borderRadius.full,
        background: colors.primary[500],
        color: '#FFFFFF',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        fontSize: size === 'sm' ? '12px' : size === 'md' ? '14px' : '16px',
        fontWeight: 500,
      }}
      aria-label={alt || 'Avatar'}
    >
      {initials || '?'}
    </div>
  )
}

Avatar.displayName = 'Avatar'

