/**
 * Loading Component
 *
 * Loading indicator for route-based code splitting.
 */

import React from 'react'
import { Box, CircularProgress, Typography } from '@mui/material'

export interface LoadingProps {
  /**
   * Loading message
   */
  message?: string
  /**
   * Full screen loading
   */
  fullScreen?: boolean
}

/**
 * Loading component for route code splitting
 */
export const Loading: React.FC<LoadingProps> = ({
  message = 'Loading...',
  fullScreen = true,
}) => {
  return (
    <Box
      sx={{
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'center',
        alignItems: 'center',
        gap: 2,
        ...(fullScreen && {
          minHeight: '100vh',
        }),
      }}
    >
      <CircularProgress />
      {message && (
        <Typography variant="body2" color="text.secondary">
          {message}
        </Typography>
      )}
    </Box>
  )
}

