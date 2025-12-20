import React, { useState, useEffect, useRef } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { cn } from '@/components/utils'
import { colors, spacing, shadows } from '@/styles/tokens'
import { useActiveRoute, useKeyboardNavigation } from '../hooks'
import { ConnectionStatusIndicator } from '@/components/realtime/ConnectionStatusIndicator'

export interface NavigationItem {
  label: string
  href?: string
  path?: string // React Router path
  onClick?: () => void
  icon?: React.ReactNode
  exact?: boolean // For exact route matching
}

export interface HeaderProps {
  /**
   * Logo element
   */
  logo?: React.ReactNode
  /**
   * Navigation items
   */
  navigation?: NavigationItem[]
  /**
   * User menu element
   */
  userMenu?: React.ReactNode
  /**
   * Tenant name
   */
  tenantName?: string
  /**
   * Whether header should be sticky
   * @default true
   */
  sticky?: boolean
  /**
   * Whether to show connection status indicator
   * @default true
   */
  showConnectionStatus?: boolean
  className?: string
}

/**
 * Enhanced Header component with React Router integration and keyboard navigation
 */
export const Header: React.FC<HeaderProps> = ({
  logo,
  navigation = [],
  userMenu,
  tenantName,
  sticky = true,
  showConnectionStatus = true,
  className,
}) => {
  const [isScrolled, setIsScrolled] = useState(false)
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false)
  const location = useLocation()
  const navigate = useNavigate()
  const navRef = useRef<HTMLElement>(null)
  const mobileNavRef = useRef<HTMLDivElement>(null)

  // Determine active state based on current route
  const isItemActive = (item: NavigationItem): boolean => {
    if (item.path) {
      // Check if current path matches
      if (item.exact) {
        return location.pathname === item.path
      }
      return location.pathname.startsWith(item.path)
    }
    if (item.href) {
      return location.pathname === item.href
    }
    return false
  }

  // Keyboard navigation for desktop nav
  useKeyboardNavigation({
    containerRef: navRef,
    enabled: !isMobileMenuOpen,
    orientation: 'horizontal',
    onActivate: (element) => {
      const link = element.closest('a')
      if (link) {
        link.click()
      }
    },
  })

  // Keyboard navigation for mobile nav
  useKeyboardNavigation({
    containerRef: mobileNavRef,
    enabled: isMobileMenuOpen,
    orientation: 'vertical',
    onActivate: (element) => {
      const link = element.closest('a')
      if (link) {
        link.click()
        setIsMobileMenuOpen(false)
      }
    },
  })

  useEffect(() => {
    if (!sticky) return

    const handleScroll = () => {
      setIsScrolled(window.scrollY > 0)
    }

    window.addEventListener('scroll', handleScroll, { passive: true })
    return () => window.removeEventListener('scroll', handleScroll)
  }, [sticky])

  // Close mobile menu on route change
  useEffect(() => {
    setIsMobileMenuOpen(false)
  }, [location.pathname])

  // Close mobile menu on escape key
  useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isMobileMenuOpen) {
        setIsMobileMenuOpen(false)
      }
    }

    document.addEventListener('keydown', handleEscape)
    return () => document.removeEventListener('keydown', handleEscape)
  }, [isMobileMenuOpen])

  const handleNavigation = (item: NavigationItem) => {
    if (item.onClick) {
      item.onClick()
    } else if (item.path) {
      navigate(item.path)
    } else if (item.href) {
      navigate(item.href)
    }
  }

  const renderNavItem = (item: NavigationItem, index: number, isMobile: boolean = false) => {
    const isActive = isItemActive(item)
    const NavComponent = item.path || item.href ? Link : 'div'

    const baseStyle: React.CSSProperties = {
      display: 'flex',
      alignItems: 'center',
      gap: spacing[2],
      padding: isMobile ? spacing[3] : `${spacing[2]}px ${spacing[3]}px`,
      color: isActive
        ? colors.primary[500]
        : colors.semantic.textPrimary,
      textDecoration: 'none',
      fontSize: '14px',
      fontWeight: isActive ? 500 : 400,
      borderRadius: '4px',
      transition: 'all 0.2s',
      background: isActive
        ? colors.primary[50]
        : 'transparent',
      cursor: 'pointer',
      border: 'none',
      outline: 'none',
    }

    const props = item.path || item.href
      ? {
          to: item.path || item.href || '#',
          onClick: (e: React.MouseEvent) => {
            e.preventDefault()
            handleNavigation(item)
            if (isMobile) {
              setIsMobileMenuOpen(false)
            }
          },
        }
      : {
          onClick: () => {
            handleNavigation(item)
            if (isMobile) {
              setIsMobileMenuOpen(false)
            }
          },
        }

    return (
      <NavComponent
        key={index}
        {...props}
        style={baseStyle}
        onMouseEnter={(e: React.MouseEvent<HTMLElement>) => {
          if (!isActive) {
            e.currentTarget.style.background = colors.semantic.actionHover
          }
        }}
        onMouseLeave={(e: React.MouseEvent<HTMLElement>) => {
          if (!isActive) {
            e.currentTarget.style.background = 'transparent'
          }
        }}
        onFocus={(e: React.FocusEvent<HTMLElement>) => {
          e.currentTarget.style.outline = `2px solid ${colors.primary[500]}`
          e.currentTarget.style.outlineOffset = '2px'
        }}
        onBlur={(e: React.FocusEvent<HTMLElement>) => {
          e.currentTarget.style.outline = 'none'
        }}
        aria-current={isActive ? 'page' : undefined}
      >
        {item.icon && <span>{item.icon}</span>}
        {item.label}
      </NavComponent>
    )
  }

  return (
    <header
      className={cn('header', className)}
      style={{
        position: sticky ? 'sticky' : 'relative',
        top: 0,
        left: 0,
        right: 0,
        height: '64px',
        background: colors.semantic.backgroundDefault,
        borderBottom: `1px solid ${colors.semantic.borderDivider}`,
        boxShadow: isScrolled ? shadows.elevation1 : 'none',
        zIndex: 1000,
        display: 'flex',
        alignItems: 'center',
        padding: `0 ${spacing[4]}px`,
        transition: 'box-shadow 0.2s',
      }}
    >
      {/* Logo */}
      {logo && (
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            marginRight: spacing[6],
          }}
        >
          {logo}
        </div>
      )}

      {/* Tenant Name */}
      {tenantName && (
        <div
          style={{
            fontSize: '14px',
            fontWeight: 500,
            color: colors.semantic.textSecondary,
            marginRight: spacing[4],
            paddingRight: spacing[4],
            borderRight: `1px solid ${colors.semantic.borderDivider}`,
          }}
        >
          {tenantName}
        </div>
      )}

      {/* Desktop Navigation */}
      <nav
        ref={navRef}
        style={{
          display: 'none',
          alignItems: 'center',
          gap: spacing[2],
          flex: 1,
        }}
        className="header-nav-desktop"
        aria-label="Main navigation"
        role="navigation"
      >
        {navigation.map((item, index) => renderNavItem(item, index, false))}
      </nav>

      {/* Connection Status Indicator */}
      {showConnectionStatus && (
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            marginLeft: 'auto',
            marginRight: spacing[2],
          }}
        >
          <ConnectionStatusIndicator size="sm" showReconnectButton={true} showTooltip={true} />
        </div>
      )}

      {/* Mobile Menu Button */}
      <button
        onClick={() => setIsMobileMenuOpen(!isMobileMenuOpen)}
        aria-label="Toggle menu"
        aria-expanded={isMobileMenuOpen}
        aria-controls="mobile-navigation"
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          width: '40px',
          height: '40px',
          background: 'none',
          border: 'none',
          cursor: 'pointer',
          marginLeft: showConnectionStatus ? spacing[2] : 'auto',
          marginRight: spacing[2],
          borderRadius: '4px',
          transition: 'background 0.2s',
        }}
        className="header-menu-button"
        onFocus={(e) => {
          e.currentTarget.style.outline = `2px solid ${colors.primary[500]}`
          e.currentTarget.style.outlineOffset = '2px'
        }}
        onBlur={(e) => {
          e.currentTarget.style.outline = 'none'
        }}
        onMouseEnter={(e) => {
          e.currentTarget.style.background = colors.semantic.actionHover
        }}
        onMouseLeave={(e) => {
          e.currentTarget.style.background = 'transparent'
        }}
      >
        <svg
          width="24"
          height="24"
          viewBox="0 0 24 24"
          fill="none"
          stroke={colors.semantic.textPrimary}
          strokeWidth="2"
          aria-hidden="true"
        >
          {isMobileMenuOpen ? (
            <path d="M18 6L6 18M6 6l12 12" />
          ) : (
            <path d="M3 12h18M3 6h18M3 18h18" />
          )}
        </svg>
      </button>

      {/* User Menu */}
      {userMenu && (
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            marginLeft: spacing[2],
          }}
        >
          {userMenu}
        </div>
      )}

      {/* Mobile Menu */}
      {isMobileMenuOpen && (
        <div
          ref={mobileNavRef}
          id="mobile-navigation"
          style={{
            position: 'absolute',
            top: '64px',
            left: 0,
            right: 0,
            background: colors.semantic.backgroundDefault,
            borderBottom: `1px solid ${colors.semantic.borderDivider}`,
            boxShadow: shadows.elevation2,
            padding: spacing[2],
            display: 'flex',
            flexDirection: 'column',
            gap: spacing[1],
            maxHeight: 'calc(100vh - 64px)',
            overflowY: 'auto',
          }}
          className="header-nav-mobile"
          role="navigation"
          aria-label="Mobile navigation"
        >
          {navigation.map((item, index) => renderNavItem(item, index, true))}
        </div>
      )}

      <style>
        {`
          @media (min-width: 900px) {
            .header-nav-desktop {
              display: flex !important;
            }
            .header-menu-button {
              display: none !important;
            }
            .header-nav-mobile {
              display: none !important;
            }
          }
        `}
      </style>
    </header>
  )
}

Header.displayName = 'Header'
