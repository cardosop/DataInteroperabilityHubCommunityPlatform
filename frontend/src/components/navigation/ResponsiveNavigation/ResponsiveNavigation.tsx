/**
 * ResponsiveNavigation Component
 *
 * Navigation component that adapts to screen size:
 * - Mobile: Hamburger menu with drawer
 * - Desktop: Horizontal navigation bar
 */

import React, { useState } from 'react'
import {
  AppBar,
  Toolbar,
  IconButton,
  Drawer,
  List,
  ListItem,
  ListItemButton,
  ListItemText,
  Box,
  useTheme,
  useMediaQuery,
} from '@mui/material'
import MenuIcon from '@mui/icons-material/Menu'
import CloseIcon from '@mui/icons-material/Close'
import { useIsMobile } from '@/hooks/useMediaQuery'

export interface NavigationItem {
  label: string
  href: string
  icon?: React.ReactNode
}

export interface ResponsiveNavigationProps {
  /**
   * Logo component or element
   */
  logo?: React.ReactNode
  /**
   * Navigation items
   */
  items: NavigationItem[]
  /**
   * User menu component (shown on desktop)
   */
  userMenu?: React.ReactNode
  /**
   * Additional actions (shown on desktop)
   */
  actions?: React.ReactNode
  /**
   * Callback when navigation item is clicked
   */
  onItemClick?: (item: NavigationItem) => void
}

/**
 * ResponsiveNavigation component
 */
export const ResponsiveNavigation: React.FC<ResponsiveNavigationProps> = ({
  logo,
  items,
  userMenu,
  actions,
  onItemClick,
}) => {
  const [drawerOpen, setDrawerOpen] = useState(false)
  const isMobile = useIsMobile()
  const theme = useTheme()
  const isDesktop = useMediaQuery(theme.breakpoints.up('md'))

  const handleDrawerToggle = () => {
    setDrawerOpen(!drawerOpen)
  }

  const handleItemClick = (item: NavigationItem) => {
    if (onItemClick) {
      onItemClick(item)
    }
    if (isMobile) {
      setDrawerOpen(false)
    }
  }

  // Mobile drawer content
  const drawerContent = (
    <Box
      sx={{
        width: 280,
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
      }}
    >
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: 2,
          borderBottom: 1,
          borderColor: 'divider',
        }}
      >
        {logo}
        <IconButton onClick={handleDrawerToggle} aria-label="close drawer">
          <CloseIcon />
        </IconButton>
      </Box>
      <List sx={{ flex: 1, padding: 2 }}>
        {items.map((item) => (
          <ListItem key={item.href} disablePadding>
            <ListItemButton
              onClick={() => handleItemClick(item)}
              href={item.href}
              sx={{
                minHeight: 48, // Touch-friendly target
                borderRadius: 1,
                marginBottom: 1,
              }}
            >
              {item.icon && (
                <Box sx={{ marginRight: 2, display: 'flex', alignItems: 'center' }}>
                  {item.icon}
                </Box>
              )}
              <ListItemText primary={item.label} />
            </ListItemButton>
          </ListItem>
        ))}
      </List>
      {userMenu && (
        <Box sx={{ padding: 2, borderTop: 1, borderColor: 'divider' }}>
          {userMenu}
        </Box>
      )}
    </Box>
  )

  return (
    <>
      <AppBar position="sticky" elevation={1}>
        <Toolbar>
          {/* Mobile: Hamburger menu */}
          {isMobile && (
            <IconButton
              edge="start"
              color="inherit"
              aria-label="open drawer"
              onClick={handleDrawerToggle}
              sx={{ marginRight: 2 }}
            >
              <MenuIcon />
            </IconButton>
          )}

          {/* Logo */}
          {logo && (
            <Box
              sx={{
                flexGrow: isMobile ? 1 : 0,
                marginRight: isDesktop ? 4 : 0,
              }}
            >
              {logo}
            </Box>
          )}

          {/* Desktop: Horizontal navigation */}
          {isDesktop && (
            <Box
              sx={{
                display: 'flex',
                flex: 1,
                alignItems: 'center',
                gap: 2,
              }}
            >
              {items.map((item) => (
                <Box
                  key={item.href}
                  component="a"
                  href={item.href}
                  onClick={(e) => {
                    e.preventDefault()
                    handleItemClick(item)
                  }}
                  sx={{
                    color: 'inherit',
                    textDecoration: 'none',
                    padding: '8px 16px',
                    borderRadius: 1,
                    '&:hover': {
                      backgroundColor: 'action.hover',
                    },
                    minHeight: 48, // Touch-friendly
                    display: 'flex',
                    alignItems: 'center',
                    gap: 1,
                  }}
                >
                  {item.icon}
                  {item.label}
                </Box>
              ))}
            </Box>
          )}

          {/* Actions */}
          {actions && (
            <Box
              sx={{
                display: 'flex',
                alignItems: 'center',
                gap: 1,
                marginLeft: 'auto',
              }}
            >
              {actions}
            </Box>
          )}

          {/* User menu (desktop only) */}
          {isDesktop && userMenu && (
            <Box sx={{ marginLeft: 2 }}>{userMenu}</Box>
          )}
        </Toolbar>
      </AppBar>

      {/* Mobile drawer */}
      <Drawer
        anchor="left"
        open={drawerOpen}
        onClose={handleDrawerToggle}
        ModalProps={{
          keepMounted: true, // Better mobile performance
        }}
        sx={{
          display: { xs: 'block', md: 'none' },
          '& .MuiDrawer-paper': {
            boxSizing: 'border-box',
            width: 280,
          },
        }}
      >
        {drawerContent}
      </Drawer>
    </>
  )
}

