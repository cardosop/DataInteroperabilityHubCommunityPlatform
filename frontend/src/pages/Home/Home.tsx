/**
 * Home Page
 *
 * Landing page for authenticated users.
 */

import React from 'react'
import { Container, Typography, Box } from '@mui/material'
import { config } from '@/lib/config'

export const Home: React.FC = () => {
  return (
    <Container maxWidth="lg">
      <Box sx={{ padding: 4 }}>
        <Typography variant="h1" gutterBottom>
          Data Interoperability Hub
        </Typography>
        <Typography variant="body1" paragraph>
          Welcome to the Data Interoperability Hub frontend application.
        </Typography>
        <Typography variant="body2" color="text.secondary">
          Environment: {config.env}
        </Typography>
      </Box>
    </Container>
  )
}

