/**
 * Not Found Page
 *
 * 404 page for routes that don't exist.
 */

import React from 'react'
import { Container, Typography, Box, Button } from '@mui/material'
import { useNavigate } from 'react-router-dom'

export const NotFound: React.FC = () => {
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
          404 - Not Found
        </Typography>
        <Typography variant="body1" color="text.secondary" paragraph>
          The page you're looking for doesn't exist.
        </Typography>
        <Button variant="contained" onClick={() => navigate('/')}>
          Go to Home
        </Button>
      </Box>
    </Container>
  )
}

