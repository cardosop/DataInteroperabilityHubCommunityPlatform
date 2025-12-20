/**
 * SkeletonContent Component
 *
 * Pre-built skeleton placeholders for common content patterns.
 */

import React from 'react'
import { Box } from '@mui/material'
import { spacing } from '@/styles/tokens'
import { Skeleton } from './Skeleton'

export interface SkeletonContentProps {
  /**
   * Type of content skeleton
   */
  variant: 'card' | 'list' | 'table' | 'form' | 'article' | 'avatar'
  /**
   * Number of items to show
   */
  count?: number
  /**
   * Animation type
   */
  animation?: 'pulse' | 'wave' | false
}

/**
 * SkeletonContent component for common content patterns
 */
export const SkeletonContent: React.FC<SkeletonContentProps> = ({
  variant,
  count = 1,
  animation = 'pulse',
}) => {
  if (variant === 'card') {
    return (
      <Box sx={{ display: 'flex', flexDirection: 'column', gap: spacing[2] }}>
        {Array.from({ length: count }).map((_, index) => (
          <Box
            key={index}
            sx={{
              padding: spacing[3],
              border: '1px solid',
              borderColor: 'divider',
              borderRadius: 1,
            }}
          >
            <Skeleton variant="rectangular" height={200} animation={animation} />
            <Box sx={{ marginTop: spacing[2] }}>
              <Skeleton variant="text" width="60%" height={24} animation={animation} />
              <Skeleton variant="text" width="40%" height={20} animation={animation} />
              <Skeleton variant="text" width="80%" height={16} animation={animation} />
            </Box>
          </Box>
        ))}
      </Box>
    )
  }

  if (variant === 'list') {
    return (
      <Box>
        {Array.from({ length: count }).map((_, index) => (
          <Box
            key={index}
            sx={{
              display: 'flex',
              gap: spacing[2],
              padding: spacing[2],
              borderBottom: index < count - 1 ? '1px solid' : 'none',
              borderColor: 'divider',
            }}
          >
            <Skeleton variant="circular" width={40} height={40} animation={animation} />
            <Box sx={{ flex: 1 }}>
              <Skeleton variant="text" width="60%" height={20} animation={animation} />
              <Skeleton variant="text" width="40%" height={16} animation={animation} />
            </Box>
          </Box>
        ))}
      </Box>
    )
  }

  if (variant === 'table') {
    return (
      <Box>
        {/* Header */}
        <Box
          sx={{
            display: 'flex',
            gap: spacing[2],
            padding: spacing[2],
            borderBottom: '2px solid',
            borderColor: 'divider',
          }}
        >
          {Array.from({ length: 4 }).map((_, index) => (
            <Skeleton
              key={index}
              variant="text"
              width="25%"
              height={20}
              animation={animation}
            />
          ))}
        </Box>
        {/* Rows */}
        {Array.from({ length: count }).map((_, rowIndex) => (
          <Box
            key={rowIndex}
            sx={{
              display: 'flex',
              gap: spacing[2],
              padding: spacing[2],
              borderBottom: '1px solid',
              borderColor: 'divider',
            }}
          >
            {Array.from({ length: 4 }).map((_, colIndex) => (
              <Skeleton
                key={colIndex}
                variant="text"
                width="25%"
                height={16}
                animation={animation}
              />
            ))}
          </Box>
        ))}
      </Box>
    )
  }

  if (variant === 'form') {
    return (
      <Box sx={{ display: 'flex', flexDirection: 'column', gap: spacing[3] }}>
        {Array.from({ length: count }).map((_, index) => (
          <Box key={index}>
            <Skeleton variant="text" width="30%" height={16} animation={animation} />
            <Skeleton
              variant="rectangular"
              width="100%"
              height={40}
              animation={animation}
              sx={{ marginTop: spacing[1] }}
            />
          </Box>
        ))}
      </Box>
    )
  }

  if (variant === 'article') {
    return (
      <Box>
        <Skeleton variant="text" width="80%" height={32} animation={animation} />
        <Skeleton variant="text" width="60%" height={20} animation={animation} />
        <Box sx={{ marginTop: spacing[3] }}>
          <Skeleton variant="rectangular" width="100%" height={300} animation={animation} />
        </Box>
        <Box sx={{ marginTop: spacing[3] }}>
          {Array.from({ length: 5 }).map((_, index) => (
            <Skeleton
              key={index}
              variant="text"
              width={index === 4 ? '60%' : '100%'}
              height={16}
              animation={animation}
              sx={{ marginTop: spacing[1] }}
            />
          ))}
        </Box>
      </Box>
    )
  }

  if (variant === 'avatar') {
    return (
      <Box sx={{ display: 'flex', alignItems: 'center', gap: spacing[2] }}>
        <Skeleton variant="circular" width={40} height={40} animation={animation} />
        <Box sx={{ flex: 1 }}>
          <Skeleton variant="text" width="60%" height={20} animation={animation} />
          <Skeleton variant="text" width="40%" height={16} animation={animation} />
        </Box>
      </Box>
    )
  }

  return null
}
