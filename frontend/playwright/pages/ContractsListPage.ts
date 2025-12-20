/**
 * Contracts List Page Object Model
 *
 * Page Object Model for the contracts list page.
 * Encapsulates all contract list page interactions and assertions.
 *
 * Uses real implementations - no mocks/stubs. Always fixes root cause.
 */

import { Page, Locator, expect } from '@playwright/test'
import { BasePage } from '../utils/page-objects'

/**
 * Contracts List Page Object
 */
export class ContractsListPage extends BasePage {
  // Locators
  readonly pageTitle: Locator
  readonly createButton: Locator
  readonly refreshButton: Locator
  readonly searchBar: Locator
  readonly contractsTable: Locator
  readonly contractRows: Locator
  readonly pagination: Locator
  readonly emptyState: Locator
  readonly loadingState: Locator
  readonly errorState: Locator
  readonly filterChips: Locator
  readonly clearFiltersButton: Locator

  constructor(page: Page) {
    super(page, '/contracts')

    // Initialize locators
    this.pageTitle = page.locator('h4, h1, h2, h3:has-text("Contracts")').first()
    this.createButton = page.locator('button:has-text("Create Contract"), button:has-text("Create")').first()
    this.refreshButton = page.locator('button[aria-label*="Refresh"], button:has([data-testid*="refresh"])').first()
    this.searchBar = page.locator('input[type="search"], input[placeholder*="Search"], input[placeholder*="owner name"]').first()
    this.contractsTable = page.locator('table, [role="table"]').first()
    this.contractRows = this.contractsTable.locator('tbody tr, [role="row"]')
    this.pagination = page.locator('[data-testid="pagination"], .MuiPagination-root, button:has-text("Next"), button:has-text("Previous")').first()
    this.emptyState = page.locator('text=No contracts, text=No contracts yet, text=Get started')
    this.loadingState = page.locator('text=Loading contracts, [role="progressbar"]')
    this.errorState = page.locator('text=Failed to load, text=Error, [role="alert"]')
    this.filterChips = page.locator('[role="button"]:has-text("Owner Email"), [role="button"]:has-text("Tag"), [role="button"]:has-text("Compliance"), [role="button"]:has-text("Quality")')
    this.clearFiltersButton = page.locator('button:has-text("Clear All"), button:has-text("Clear Filters")')
  }

  /**
   * Navigate to contracts list page
   */
  async goto(): Promise<void> {
    await super.goto({ waitUntil: 'networkidle' })
    await this.waitForPageLoad()
  }

  /**
   * Wait for contracts list page to be fully loaded
   */
  async waitForPageLoad(): Promise<void> {
    // Wait for either content or loading/error state
    await Promise.race([
      this.page.waitForSelector('table, [role="table"], text=No contracts', { timeout: 15000 }),
      this.page.waitForSelector('text=Loading contracts', { timeout: 5000 }),
      this.page.waitForSelector('text=Failed to load', { timeout: 5000 }),
    ])
  }

  /**
   * Get contract count from header
   */
  async getContractCount(): Promise<number | null> {
    const countText = this.page.locator('text=/\\d+ total/').first()
    if (await countText.count() > 0) {
      const text = await countText.textContent()
      const match = text?.match(/(\d+)\s+total/)
      return match ? parseInt(match[1], 10) : null
    }
    return null
  }

  /**
   * Get number of visible contract rows
   */
  async getVisibleContractCount(): Promise<number> {
    await this.contractsTable.waitFor({ state: 'visible', timeout: 10000 }).catch(() => {})
    return await this.contractRows.count()
  }

  /**
   * Get contract name from a row
   */
  async getContractName(rowIndex: number = 0): Promise<string | null> {
    const row = this.contractRows.nth(rowIndex)
    if (await row.count() > 0) {
      const nameCell = row.locator('td').first()
      const nameText = await nameCell.textContent()
      return nameText?.trim() || null
    }
    return null
  }

  /**
   * Get contract status from a row
   */
  async getContractStatus(rowIndex: number = 0): Promise<string | null> {
    const row = this.contractRows.nth(rowIndex)
    if (await row.count() > 0) {
      // Status is typically in the second column
      const statusCell = row.locator('td').nth(1)
      const statusText = await statusCell.textContent()
      return statusText?.trim() || null
    }
    return null
  }

  /**
   * Click on a contract row to navigate to detail
   */
  async clickContract(rowIndex: number = 0): Promise<void> {
    const row = this.contractRows.nth(rowIndex)
    await row.waitFor({ state: 'visible', timeout: 10000 })
    await Promise.all([
      this.page.waitForURL(/.*contracts\/.*/, { timeout: 10000 }),
      row.click(),
    ])
  }

  /**
   * Search by owner name
   */
  async searchByOwnerName(query: string): Promise<void> {
    await this.searchBar.waitFor({ state: 'visible', timeout: 10000 })
    await this.searchBar.fill(query)
    await this.page.waitForTimeout(500) // Wait for debounce
    await this.page.waitForLoadState('networkidle')
  }

  /**
   * Clear search
   */
  async clearSearch(): Promise<void> {
    await this.searchBar.waitFor({ state: 'visible', timeout: 10000 })
    await this.searchBar.clear()
    await this.page.waitForTimeout(500)
    await this.page.waitForLoadState('networkidle')
  }

  /**
   * Get current page number
   */
  async getCurrentPage(): Promise<number> {
    const pageInput = this.pagination.locator('input[type="number"], [aria-label*="page"]').first()
    if (await pageInput.count() > 0) {
      const value = await pageInput.inputValue()
      return parseInt(value, 10) || 1
    }
    return 1
  }

  /**
   * Navigate to next page
   */
  async goToNextPage(): Promise<void> {
    const nextButton = this.pagination.locator('button:has-text("Next"), button[aria-label*="Next"]').first()
    if (await nextButton.count() > 0 && !(await nextButton.isDisabled())) {
      await nextButton.click()
      await this.page.waitForLoadState('networkidle')
    }
  }

  /**
   * Navigate to previous page
   */
  async goToPreviousPage(): Promise<void> {
    const prevButton = this.pagination.locator('button:has-text("Previous"), button[aria-label*="Previous"]').first()
    if (await prevButton.count() > 0 && !(await prevButton.isDisabled())) {
      await prevButton.click()
      await this.page.waitForLoadState('networkidle')
    }
  }

  /**
   * Navigate to specific page
   */
  async goToPage(pageNumber: number): Promise<void> {
    const pageButton = this.pagination.locator(`button:has-text("${pageNumber}"), [aria-label*="page ${pageNumber}"]`).first()
    if (await pageButton.count() > 0) {
      await pageButton.click()
      await this.page.waitForLoadState('networkidle')
    } else {
      // Try using page input
      const pageInput = this.pagination.locator('input[type="number"]').first()
      if (await pageInput.count() > 0) {
        await pageInput.fill(String(pageNumber))
        await pageInput.press('Enter')
        await this.page.waitForLoadState('networkidle')
      }
    }
  }

  /**
   * Change page size
   */
  async changePageSize(size: number): Promise<void> {
    const pageSizeSelect = this.pagination.locator('select, [role="combobox"]').first()
    if (await pageSizeSelect.count() > 0) {
      await pageSizeSelect.selectOption(String(size))
      await this.page.waitForLoadState('networkidle')
    }
  }

  /**
   * Get active filter chips
   */
  async getActiveFilters(): Promise<string[]> {
    const chips = this.filterChips
    const count = await chips.count()
    const filters: string[] = []

    for (let i = 0; i < count; i++) {
      const chip = chips.nth(i)
      const text = await chip.textContent()
      if (text) {
        filters.push(text.trim())
      }
    }

    return filters
  }

  /**
   * Clear all filters
   */
  async clearAllFilters(): Promise<void> {
    if (await this.clearFiltersButton.count() > 0) {
      await this.clearFiltersButton.click()
      await this.page.waitForLoadState('networkidle')
    }
  }

  /**
   * Remove a specific filter chip
   */
  async removeFilter(filterText: string): Promise<void> {
    const chip = this.filterChips.filter({ hasText: filterText }).first()
    if (await chip.count() > 0) {
      const deleteButton = chip.locator('button[aria-label*="Delete"], svg[data-testid*="Cancel"]').first()
      await deleteButton.click()
      await this.page.waitForLoadState('networkidle')
    }
  }

  /**
   * Sort by column
   */
  async sortByColumn(columnName: string): Promise<void> {
    const columnHeader = this.contractsTable.locator(`th:has-text("${columnName}")`).first()
    await columnHeader.waitFor({ state: 'visible', timeout: 10000 })
    await columnHeader.click()
    await this.page.waitForLoadState('networkidle')
  }

  /**
   * Click create contract button
   */
  async clickCreate(): Promise<void> {
    await this.createButton.waitFor({ state: 'visible', timeout: 10000 })
    await Promise.all([
      this.page.waitForURL(/.*contracts\/create.*/, { timeout: 10000 }),
      this.createButton.click(),
    ])
  }

  /**
   * Click refresh button
   */
  async clickRefresh(): Promise<void> {
    await this.refreshButton.waitFor({ state: 'visible', timeout: 10000 })
    await this.refreshButton.click()
    await this.page.waitForTimeout(1000) // Wait for refresh
  }

  /**
   * Check if pagination is visible
   */
  async hasPagination(): Promise<boolean> {
    return await this.pagination.isVisible().catch(() => false)
  }

  /**
   * Check if empty state is visible
   */
  async isEmptyStateVisible(): Promise<boolean> {
    return await this.emptyState.isVisible().catch(() => false)
  }

  /**
   * Check if loading state is visible
   */
  async isLoadingStateVisible(): Promise<boolean> {
    return await this.loadingState.isVisible().catch(() => false)
  }

  /**
   * Check if error state is visible
   */
  async isErrorStateVisible(): Promise<boolean> {
    return await this.errorState.isVisible().catch(() => false)
  }

  /**
   * Assert contracts list page is loaded
   */
  async assertPageLoaded(): Promise<void> {
    await this.assertVisible('h4, h1, h2, h3:has-text("Contracts")')
  }

  /**
   * Assert contracts are displayed
   */
  async assertContractsDisplayed(): Promise<void> {
    // Either table with rows or empty state should be visible
    const hasTable = await this.contractsTable.isVisible().catch(() => false)
    const hasEmptyState = await this.isEmptyStateVisible()

    expect(hasTable || hasEmptyState).toBe(true)
  }

  /**
   * Assert pagination is displayed (if multiple pages)
   */
  async assertPaginationDisplayed(shouldExist: boolean = true): Promise<void> {
    const exists = await this.hasPagination()
    expect(exists).toBe(shouldExist)
  }

  /**
   * Assert empty state is displayed
   */
  async assertEmptyStateDisplayed(): Promise<void> {
    await this.assertVisible('text=No contracts, text=No contracts yet')
  }

  /**
   * Assert loading state is displayed
   */
  async assertLoadingStateDisplayed(): Promise<void> {
    await this.assertVisible('text=Loading contracts, [role="progressbar"]')
  }

  /**
   * Assert error state is displayed
   */
  async assertErrorStateDisplayed(): Promise<void> {
    await this.assertVisible('text=Failed to load, text=Error')
  }
}

