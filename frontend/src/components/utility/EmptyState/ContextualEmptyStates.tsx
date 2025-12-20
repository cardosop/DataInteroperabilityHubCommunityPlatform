import React from 'react'
import { EnhancedEmptyState, type EmptyStateAction, type HelpLink } from './EnhancedEmptyState'

export interface ContextualEmptyStateProps {
  /**
   * Primary action
   */
  primaryAction?: EmptyStateAction
  /**
   * Secondary actions
   */
  secondaryActions?: EmptyStateAction[]
  /**
   * Help links
   */
  helpLinks?: HelpLink[]
  /**
   * Custom help text
   */
  helpText?: string
  /**
   * Custom title override
   */
  title?: string
  /**
   * Custom description override
   */
  description?: string
}

/**
 * No Data Empty State
 *
 * Use when there's no data to display (e.g., empty table, empty list)
 */
export const NoDataEmptyState: React.FC<ContextualEmptyStateProps> = ({
  primaryAction,
  secondaryActions,
  helpLinks,
  helpText,
  title,
  description,
}) => {
  return (
    <EnhancedEmptyState
      context="no-data"
      title={title || 'No data available'}
      description={
        description ||
        'There is no data to display. Create your first item to get started.'
      }
      primaryAction={primaryAction}
      secondaryActions={secondaryActions}
      helpText={helpText}
      helpLinks={helpLinks}
    />
  )
}

/**
 * No Results Empty State
 *
 * Use when search or filter returns no results
 */
export const NoResultsEmptyState: React.FC<ContextualEmptyStateProps> = ({
  primaryAction,
  secondaryActions,
  helpLinks,
  helpText,
  title,
  description,
}) => {
  return (
    <EnhancedEmptyState
      context="no-results"
      title={title || 'No results found'}
      description={
        description ||
        "Try adjusting your search or filters to find what you're looking for."
      }
      primaryAction={primaryAction}
      secondaryActions={secondaryActions}
      helpText={helpText}
      helpLinks={helpLinks}
    />
  )
}

/**
 * No Items Empty State
 *
 * Use when a list is empty
 */
export const NoItemsEmptyState: React.FC<ContextualEmptyStateProps> = ({
  primaryAction,
  secondaryActions,
  helpLinks,
  helpText,
  title,
  description,
}) => {
  return (
    <EnhancedEmptyState
      context="no-items"
      title={title || 'No items yet'}
      description={
        description || 'Get started by adding your first item to the list.'
      }
      primaryAction={primaryAction}
      secondaryActions={secondaryActions}
      helpText={helpText}
      helpLinks={helpLinks}
    />
  )
}

/**
 * No Files Empty State
 *
 * Use when there are no files or documents
 */
export const NoFilesEmptyState: React.FC<ContextualEmptyStateProps> = ({
  primaryAction,
  secondaryActions,
  helpLinks,
  helpText,
  title,
  description,
}) => {
  return (
    <EnhancedEmptyState
      context="no-files"
      title={title || 'No files yet'}
      description={
        description || 'Upload your first file to get started organizing your documents.'
      }
      primaryAction={primaryAction}
      secondaryActions={secondaryActions}
      helpText={helpText}
      helpLinks={helpLinks}
    />
  )
}

/**
 * No Connections Empty State
 *
 * Use when there are no connections or integrations
 */
export const NoConnectionsEmptyState: React.FC<ContextualEmptyStateProps> = ({
  primaryAction,
  secondaryActions,
  helpLinks,
  helpText,
  title,
  description,
}) => {
  return (
    <EnhancedEmptyState
      context="no-connections"
      title={title || 'No connections'}
      description={
        description ||
        'Connect your first service to start syncing data and automating workflows.'
      }
      primaryAction={primaryAction}
      secondaryActions={secondaryActions}
      helpText={helpText}
      helpLinks={helpLinks}
    />
  )
}

/**
 * Error Empty State
 *
 * Use when an error occurs and no data can be displayed
 */
export const ErrorEmptyState: React.FC<ContextualEmptyStateProps> = ({
  primaryAction,
  secondaryActions,
  helpLinks,
  helpText,
  title,
  description,
}) => {
  return (
    <EnhancedEmptyState
      context="error"
      title={title || 'Something went wrong'}
      description={
        description ||
        'We encountered an error while loading the data. Please try again.'
      }
      primaryAction={primaryAction}
      secondaryActions={secondaryActions}
      helpText={helpText}
      helpLinks={helpLinks}
    />
  )
}

