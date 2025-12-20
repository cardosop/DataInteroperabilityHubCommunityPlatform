/**
 * Asset Actions Component
 *
 * Action buttons for asset operations (view, edit, delete, etc.)
 * Provides consistent action button patterns for assets.
 */

import React from 'react'
import {
  IconButton,
  Button,
  ButtonGroup,
  Menu,
  MenuItem,
  ListItemIcon,
  ListItemText,
  Tooltip,
  CircularProgress,
} from '@mui/material'
import {
  Edit as EditIcon,
  Delete as DeleteIcon,
  Visibility as ViewIcon,
  MoreVert as MoreVertIcon,
  Refresh as RefreshIcon,
  ContentCopy as CopyIcon,
  Download as DownloadIcon,
} from '@mui/icons-material'
import type { Asset } from '@/lib/api/assets'

export interface AssetActionsProps {
  /**
   * Asset data
   */
  asset: Asset
  /**
   * Show as icon buttons or regular buttons
   * @default 'icon'
   */
  variant?: 'icon' | 'button' | 'menu'
  /**
   * Size of buttons
   * @default 'small'
   */
  size?: 'small' | 'medium' | 'large'
  /**
   * Show view action
   * @default true
   */
  showView?: boolean
  /**
   * Show edit action
   * @default true
   */
  showEdit?: boolean
  /**
   * Show delete action
   * @default true
   */
  showDelete?: boolean
  /**
   * Show refresh action
   * @default false
   */
  showRefresh?: boolean
  /**
   * Show copy action
   * @default false
   */
  showCopy?: boolean
  /**
   * Show download action
   * @default false
   */
  showDownload?: boolean
  /**
   * Loading state
   * @default false
   */
  loading?: boolean
  /**
   * Disabled state
   * @default false
   */
  disabled?: boolean
  /**
   * Callback when view is clicked
   */
  onView?: (asset: Asset) => void
  /**
   * Callback when edit is clicked
   */
  onEdit?: (asset: Asset) => void
  /**
   * Callback when delete is clicked
   */
  onDelete?: (asset: Asset) => void
  /**
   * Callback when refresh is clicked
   */
  onRefresh?: (asset: Asset) => void
  /**
   * Callback when copy is clicked
   */
  onCopy?: (asset: Asset) => void
  /**
   * Callback when download is clicked
   */
  onDownload?: (asset: Asset) => void
  /**
   * Additional menu items
   */
  additionalMenuItems?: Array<{
    label: string
    icon?: React.ReactNode
    onClick: (asset: Asset) => void
    disabled?: boolean
  }>
}

/**
 * Asset Actions Component
 *
 * @example
 * ```tsx
 * <AssetActions
 *   asset={asset}
 *   variant="icon"
 *   onView={(asset) => navigate(`/assets/${asset.id}`)}
 *   onEdit={(asset) => navigate(`/assets/${asset.id}/edit`)}
 *   onDelete={(asset) => handleDelete(asset)}
 * />
 * ```
 */
export const AssetActions: React.FC<AssetActionsProps> = ({
  asset,
  variant = 'icon',
  size = 'small',
  showView = true,
  showEdit = true,
  showDelete = true,
  showRefresh = false,
  showCopy = false,
  showDownload = false,
  loading = false,
  disabled = false,
  onView,
  onEdit,
  onDelete,
  onRefresh,
  onCopy,
  onDownload,
  additionalMenuItems = [],
}) => {
  const [menuAnchor, setMenuAnchor] = React.useState<null | HTMLElement>(null)

  const handleMenuOpen = (event: React.MouseEvent<HTMLElement>) => {
    setMenuAnchor(event.currentTarget)
  }

  const handleMenuClose = () => {
    setMenuAnchor(null)
  }

  const handleAction = (callback?: (asset: Asset) => void, event?: React.MouseEvent) => {
    if (event) {
      event.stopPropagation()
    }
    if (callback && !disabled && !loading) {
      // Call with asset (AssetActions interface)
      callback(asset)
      handleMenuClose()
    }
  }

  // Icon variant
  if (variant === 'icon') {
    return (
      <>
        {showView && onView && (
          <Tooltip title="View">
            <IconButton
              size={size}
              onClick={(e) => handleAction(onView, e)}
              disabled={disabled || loading}
              aria-label="View asset"
            >
              {loading ? <CircularProgress size={16} /> : <ViewIcon />}
            </IconButton>
          </Tooltip>
        )}
        {showEdit && onEdit && (
          <Tooltip title="Edit">
            <IconButton
              size={size}
              onClick={(e) => handleAction(onEdit, e)}
              disabled={disabled || loading}
              aria-label="Edit asset"
            >
              <EditIcon />
            </IconButton>
          </Tooltip>
        )}
        {showDelete && onDelete && (
          <Tooltip title="Delete">
            <IconButton
              size={size}
              onClick={(e) => handleAction(onDelete, e)}
              disabled={disabled || loading}
              color="error"
              aria-label="Delete asset"
            >
              <DeleteIcon />
            </IconButton>
          </Tooltip>
        )}
        {showRefresh && onRefresh && (
          <Tooltip title="Refresh">
            <IconButton
              size={size}
              onClick={() => handleAction(onRefresh)}
              disabled={disabled || loading}
              aria-label="Refresh asset"
            >
              <RefreshIcon />
            </IconButton>
          </Tooltip>
        )}
      </>
    )
  }

  // Button variant
  if (variant === 'button') {
    return (
      <ButtonGroup size={size} disabled={disabled || loading}>
        {showView && onView && (
          <Button
            startIcon={<ViewIcon />}
            onClick={() => handleAction(onView)}
            disabled={disabled || loading}
          >
            View
          </Button>
        )}
        {showEdit && onEdit && (
          <Button
            startIcon={<EditIcon />}
            onClick={() => handleAction(onEdit)}
            disabled={disabled || loading}
          >
            Edit
          </Button>
        )}
        {showDelete && onDelete && (
          <Button
            startIcon={<DeleteIcon />}
            onClick={() => handleAction(onDelete)}
            disabled={disabled || loading}
            color="error"
          >
            Delete
          </Button>
        )}
      </ButtonGroup>
    )
  }

  // Menu variant
  return (
    <>
      <Tooltip title="More actions">
        <IconButton
          size={size}
          onClick={handleMenuOpen}
          disabled={disabled || loading}
          aria-label="More actions"
        >
          <MoreVertIcon />
        </IconButton>
      </Tooltip>
      <Menu
        anchorEl={menuAnchor}
        open={Boolean(menuAnchor)}
        onClose={handleMenuClose}
        anchorOrigin={{
          vertical: 'bottom',
          horizontal: 'right',
        }}
        transformOrigin={{
          vertical: 'top',
          horizontal: 'right',
        }}
      >
        {showView && onView && (
          <MenuItem onClick={() => handleAction(onView)} disabled={disabled || loading}>
            <ListItemIcon>
              <ViewIcon fontSize="small" />
            </ListItemIcon>
            <ListItemText>View</ListItemText>
          </MenuItem>
        )}
        {showEdit && onEdit && (
          <MenuItem onClick={() => handleAction(onEdit)} disabled={disabled || loading}>
            <ListItemIcon>
              <EditIcon fontSize="small" />
            </ListItemIcon>
            <ListItemText>Edit</ListItemText>
          </MenuItem>
        )}
        {showRefresh && onRefresh && (
          <MenuItem onClick={() => handleAction(onRefresh)} disabled={disabled || loading}>
            <ListItemIcon>
              <RefreshIcon fontSize="small" />
            </ListItemIcon>
            <ListItemText>Refresh</ListItemText>
          </MenuItem>
        )}
        {showCopy && onCopy && (
          <MenuItem onClick={() => handleAction(onCopy)} disabled={disabled || loading}>
            <ListItemIcon>
              <CopyIcon fontSize="small" />
            </ListItemIcon>
            <ListItemText>Copy</ListItemText>
          </MenuItem>
        )}
        {showDownload && onDownload && (
          <MenuItem onClick={() => handleAction(onDownload)} disabled={disabled || loading}>
            <ListItemIcon>
              <DownloadIcon fontSize="small" />
            </ListItemIcon>
            <ListItemText>Download</ListItemText>
          </MenuItem>
        )}
        {additionalMenuItems.length > 0 && <MenuItem divider />}
        {additionalMenuItems.map((item, index) => (
          <MenuItem
            key={index}
            onClick={() => handleAction(item.onClick)}
            disabled={disabled || loading || item.disabled}
          >
            {item.icon && <ListItemIcon>{item.icon}</ListItemIcon>}
            <ListItemText>{item.label}</ListItemText>
          </MenuItem>
        ))}
        {showDelete && onDelete && (
          <>
            <MenuItem divider />
            <MenuItem
              onClick={() => handleAction(onDelete)}
              disabled={disabled || loading}
              sx={{ color: 'error.main' }}
            >
              <ListItemIcon>
                <DeleteIcon fontSize="small" color="error" />
              </ListItemIcon>
              <ListItemText>Delete</ListItemText>
            </MenuItem>
          </>
        )}
      </Menu>
    </>
  )
}

AssetActions.displayName = 'AssetActions'

