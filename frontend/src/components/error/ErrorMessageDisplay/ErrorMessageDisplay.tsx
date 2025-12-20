/**
 * ErrorMessageDisplay Component
 *
 * Comprehensive error message display with:
 * - User-friendly messages (no technical jargon)
 * - Suggested actions
 * - Help links
 * - Clear next steps
 * - i18n support
 */

import React from 'react'
import {
  Alert,
  AlertTitle,
  Box,
  Button,
  Link,
  List,
  ListItem,
  ListItemText,
  Typography,
  Divider,
} from '@mui/material'
import { HelpOutline as HelpIcon, ArrowForward as ArrowIcon } from '@mui/icons-material'
import { useErrorMessage } from '@/lib/errors/useErrorMessage'

export interface ErrorMessageDisplayProps {
  /**
   * Error object
   */
  error: unknown
  /**
   * Whether to show details
   * @default true
   */
  showDetails?: boolean
  /**
   * Whether to show suggested actions
   * @default true
   */
  showActions?: boolean
  /**
   * Whether to show help links
   * @default true
   */
  showHelpLinks?: boolean
  /**
   * Whether to show next steps
   * @default true
   */
  showNextSteps?: boolean
  /**
   * Additional CSS class name
   */
  className?: string
}

/**
 * ErrorMessageDisplay component
 */
export const ErrorMessageDisplay: React.FC<ErrorMessageDisplayProps> = ({
  error,
  showDetails = true,
  showActions = true,
  showHelpLinks = true,
  showNextSteps = true,
  className,
}) => {
  const {
    title,
    message,
    details,
    severity,
    suggestedActions,
    helpLinks,
    nextSteps,
    recoverable,
  } = useErrorMessage(error)

  return (
    <Alert severity={severity} className={className} sx={{ width: '100%' }}>
      <AlertTitle>{title}</AlertTitle>
      <Typography variant="body2" sx={{ mb: details ? 1 : 0 }}>
        {message}
      </Typography>

      {showDetails && details && (
        <Typography variant="body2" color="text.secondary" sx={{ mt: 1, mb: 1 }}>
          {details}
        </Typography>
      )}

      {showNextSteps && nextSteps.length > 0 && (
        <Box sx={{ mt: 2, mb: showActions || showHelpLinks ? 2 : 0 }}>
          <Typography variant="subtitle2" sx={{ mb: 1, fontWeight: 600 }}>
            Next Steps:
          </Typography>
          <List dense sx={{ py: 0 }}>
            {nextSteps.map((step, index) => (
              <ListItem key={index} sx={{ py: 0.5, pl: 0 }}>
                <ListItemText
                  primary={
                    <Typography variant="body2" component="span">
                      {step}
                    </Typography>
                  }
                  sx={{ m: 0 }}
                />
              </ListItem>
            ))}
          </List>
        </Box>
      )}

      {(showActions || showHelpLinks) && (suggestedActions.length > 0 || helpLinks.length > 0) && (
        <>
          <Divider sx={{ my: 2 }} />
          <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1, alignItems: 'center' }}>
            {showActions &&
              suggestedActions.map((action, index) => (
                <Button
                  key={index}
                  variant={action.variant === 'primary' ? 'contained' : 'outlined'}
                  size="small"
                  onClick={action.onClick}
                  endIcon={action.variant === 'primary' ? <ArrowIcon /> : undefined}
                >
                  {action.label}
                </Button>
              ))}

            {showHelpLinks &&
              helpLinks.map((link, index) => (
                <Link
                  key={index}
                  href={link.url}
                  target={link.external ? '_blank' : undefined}
                  rel={link.external ? 'noopener noreferrer' : undefined}
                  sx={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 0.5,
                    textDecoration: 'none',
                    '&:hover': {
                      textDecoration: 'underline',
                    },
                  }}
                >
                  <HelpIcon fontSize="small" />
                  <Typography variant="body2">{link.label}</Typography>
                </Link>
              ))}
          </Box>
        </>
      )}
    </Alert>
  )
}

ErrorMessageDisplay.displayName = 'ErrorMessageDisplay'

