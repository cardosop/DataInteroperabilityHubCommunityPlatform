/**
 * Unauthorized Page
 *
 * Page shown when user doesn't have required permissions or roles.
 */

import React from 'react'
import { Container, Typography, Box, Button } from '@mui/material'
import { useNavigate } from 'react-router-dom'

export const Unauthorized: React.FC = () => {
  const navigate = useNavigate()

  return (
    <Container maxWidth="sm">
      <Box
        sx={{
          padding: 4,
          marginTop: 8,
          textAlign: 'center',
        }}
      >
        <Typography variant="h2" gutterBottom>
          403 - Unauthorized
        </Typography>
        <Typography variant="body1" color="text.secondary" paragraph>
          You don't have permission to access this page.
        </Typography>
        <Button variant="contained" onClick={() => navigate('/')}>
          Go to Home
        </Button>
      </Box>
    </Container>
  )
}

