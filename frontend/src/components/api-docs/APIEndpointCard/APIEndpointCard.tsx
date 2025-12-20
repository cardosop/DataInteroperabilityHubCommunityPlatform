/**
 * APIEndpointCard Component
 *
 * Card component for displaying API endpoint information:
 * - HTTP method badge
 * - Endpoint path
 * - Description
 * - Selection state
 * - Click handling
 */

import React from 'react'
import { Card, CardContent, Box, Chip, Typography } from '@mui/material'
import type { APIEndpoint } from './types'

export interface APIEndpointCardProps {
  /**
   * API endpoint information
   */
  endpoint: APIEndpoint
  /**
   * Whether this card is selected
   */
  selected?: boolean
  /**
   * Click handler
   */
  onClick: (endpoint: APIEndpoint) => void
  /**
   * Additional CSS class name
   */
  className?: string
}

/**
 * Get color for HTTP method badge
 */
function getMethodColor(method: APIEndpoint['method']): 'primary' | 'success' | 'warning' | 'error' | 'default' {
  switch (method) {
    case 'GET':
      return 'primary'
    case 'POST':
      return 'success'
    case 'PUT':
    case 'PATCH':
      return 'warning'
    case 'DELETE':
      return 'error'
    default:
      return 'default'
  }
}

/**
 * APIEndpointCard component
 */
export const APIEndpointCard: React.FC<APIEndpointCardProps> = ({
  endpoint,
  selected = false,
  onClick,
  className,
}) => {
  const handleClick = () => {
    onClick(endpoint)
  }

  return (
    <Card
      className={className}
      sx={{
        cursor: 'pointer',
        border: selected ? 2 : 1,
        borderColor: selected ? 'primary.main' : 'divider',
        transition: 'all 0.2s ease-in-out',
        '&:hover': {
          borderColor: 'primary.main',
          boxShadow: 2,
        },
      }}
      onClick={handleClick}
    >
      <CardContent sx={{ p: 2, '&:last-child': { pb: 2 } }}>
        <Box sx={{ display: 'flex', gap: 1, alignItems: 'center', mb: 1 }}>
          <Chip
            label={endpoint.method}
            size="small"
            color={getMethodColor(endpoint.method)}
          />
          <Typography
            variant="body2"
            sx={{
              fontFamily: 'monospace',
              fontSize: '0.75rem',
              flex: 1,
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
            }}
          >
            {endpoint.path}
          </Typography>
        </Box>
        <Typography variant="body2" color="text.secondary">
          {endpoint.description}
        </Typography>
      </CardContent>
    </Card>
  )
}

APIEndpointCard.displayName = 'APIEndpointCard'

