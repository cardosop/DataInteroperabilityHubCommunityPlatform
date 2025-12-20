/**
 * Asset Detail Page Object Model
 *
 * Page Object Model for the asset detail page.
 * Encapsulates all asset detail page interactions and assertions.
 *
 * Uses real implementations - no mocks/stubs. Always fixes root cause.
 */

import { Page, Locator, expect } from '@playwright/test'
import { BasePage } from '../utils/page-objects'

/**
 * Asset Detail Page Object
 */
export class AssetDetailPage extends BasePage {
  // Locators
  readonly backButton: Locator
  readonly assetName: Locator
  readonly assetKey: Locator
  readonly refreshButton: Locator
  readonly editButton: Locator
  readonly deleteButton: Locator
  readonly assetInfoSection: Locator
  readonly contractSection: Locator
  readonly datasetSection: Locator
  readonly historySection: Locator
  readonly deleteDialog: Locator
  readonly deleteConfirmButton: Locator
  readonly deleteCancelButton: Locator

  constructor(page: Page, assetId: string) {
    super(page, `/assets/${assetId}`)

    // Initialize locators
    this.backButton = page.locator('button[aria-label*="Back"], button:has-text("Back")').first()
    this.assetName = page.locator('h4, h1, h2, h3:has-text("")').first()
    this.assetKey = page.locator('text=/^[a-zA-Z0-9_-]+$/').first()
    this.refreshButton = page.locator('button[aria-label*="Refresh"], button:has([data-testid*="refresh"])').first()
    this.editButton = page.locator('button:has-text("Edit"), button[aria-label*="Edit"]').first()
    this.deleteButton = page.locator('button:has-text("Delete"), button[aria-label*="Delete"]').first()
    this.assetInfoSection = page.locator('text=Asset Information, [data-testid="asset-info"]').first()
    this.contractSection = page.locator('text=Associated Contract, [data-testid="contract-section"]').first()
    this.datasetSection = page.locator('text=Associated Dataset, [data-testid="dataset-section"]').first()
    this.historySection = page.locator('text=History, [data-testid="history-section"]').first()
    this.deleteDialog = page.locator('[role="dialog"]:has-text("Delete Asset")')
    this.deleteConfirmButton = this.deleteDialog.locator('button:has-text("Delete")')
    this.deleteCancelButton = this.deleteDialog.locator('button:has-text("Cancel")')
  }

  /**
   * Navigate to asset detail page
   */
  async goto(): Promise<void> {
    await super.goto({ waitUntil: 'networkidle' })
    await this.waitForPageLoad()
  }

  /**
   * Wait for asset detail page to be fully loaded
   */
  async waitForPageLoad(): Promise<void> {
    // Wait for asset name or loading to complete
    await this.page.waitForSelector('h4, h1, h2, h3, [data-testid="asset-name"]', { timeout: 15000 })
    // Wait for either asset info or error state
    await Promise.race([
      this.page.waitForSelector('text=Asset Information, [data-testid="asset-info"]', { timeout: 10000 }),
      this.page.waitForSelector('text=Failed to load, text=Error', { timeout: 10000 }),
    ])
  }

  /**
   * Get asset name
   */
  async getAssetName(): Promise<string> {
    await this.assetName.waitFor({ state: 'visible', timeout: 10000 })
    return await this.assetName.textContent() || ''
  }

  /**
   * Get asset key
   */
  async getAssetKey(): Promise<string> {
    const keyElement = this.page.locator('text=/^[a-zA-Z0-9_-]+$/').first()
    await keyElement.waitFor({ state: 'visible', timeout: 10000 })
    return await keyElement.textContent() || ''
  }

  /**
   * Get asset status
   */
  async getAssetStatus(): Promise<string | null> {
    const statusChip = this.page.locator('text=Status').locator('..').locator('span, [role="button"]').first()
    if (await statusChip.count() > 0) {
      return await statusChip.textContent()
    }
    return null
  }

  /**
   * Get asset description
   */
  async getAssetDescription(): Promise<string | null> {
    const descElement = this.page.locator('text=Description').locator('..').locator('p, span').first()
    if (await descElement.count() > 0) {
      return await descElement.textContent()
    }
    return null
  }

  /**
   * Click edit button
   */
  async clickEdit(): Promise<void> {
    await this.editButton.waitFor({ state: 'visible', timeout: 10000 })
    await this.editButton.click()
    await this.page.waitForURL(/.*assets\/.*\/edit.*/, { timeout: 10000 })
  }

  /**
   * Click delete button
   */
  async clickDelete(): Promise<void> {
    await this.deleteButton.waitFor({ state: 'visible', timeout: 10000 })
    await this.deleteButton.click()
    await this.deleteDialog.waitFor({ state: 'visible', timeout: 5000 })
  }

  /**
   * Confirm delete in dialog
   */
  async confirmDelete(): Promise<void> {
    await this.deleteConfirmButton.waitFor({ state: 'visible', timeout: 5000 })
    await Promise.all([
      this.page.waitForURL(/.*assets.*/, { timeout: 15000 }),
      this.deleteConfirmButton.click(),
    ])
  }

  /**
   * Cancel delete in dialog
   */
  async cancelDelete(): Promise<void> {
    await this.deleteCancelButton.waitFor({ state: 'visible', timeout: 5000 })
    await this.deleteCancelButton.click()
    await this.deleteDialog.waitFor({ state: 'hidden', timeout: 5000 })
  }

  /**
   * Check if contract section is visible
   */
  async hasContractSection(): Promise<boolean> {
    return await this.contractSection.isVisible().catch(() => false)
  }

  /**
   * Get contract name
   */
  async getContractName(): Promise<string | null> {
    if (!(await this.hasContractSection())) {
      return null
    }

    const contractName = this.page.locator('text=Contract Name').locator('..').locator('p, span, a').first()
    if (await contractName.count() > 0) {
      return await contractName.textContent()
    }
    return null
  }

  /**
   * Click view contract details button
   */
  async clickViewContract(): Promise<void> {
    const viewContractButton = this.page.locator('button:has-text("View Contract"), a:has-text("View Contract")').first()
    await viewContractButton.waitFor({ state: 'visible', timeout: 10000 })
    await Promise.all([
      this.page.waitForURL(/.*contracts\/.*/, { timeout: 10000 }),
      viewContractButton.click(),
    ])
  }

  /**
   * Check if dataset section is visible
   */
  async hasDatasetSection(): Promise<boolean> {
    return await this.datasetSection.isVisible().catch(() => false)
  }

  /**
   * Get dataset ID
   */
  async getDatasetId(): Promise<string | null> {
    if (!(await this.hasDatasetSection())) {
      return null
    }

    const datasetId = this.page.locator('text=Dataset ID').locator('..').locator('p, span').first()
    if (await datasetId.count() > 0) {
      return await datasetId.textContent()
    }
    return null
  }

  /**
   * Click view dataset details button
   */
  async clickViewDataset(): Promise<void> {
    const viewDatasetButton = this.page.locator('button:has-text("View Dataset"), a:has-text("View Dataset")').first()
    await viewDatasetButton.waitFor({ state: 'visible', timeout: 10000 })
    await Promise.all([
      this.page.waitForURL(/.*datasets\/.*/, { timeout: 10000 }),
      viewDatasetButton.click(),
    ])
  }

  /**
   * Check if history section is visible
   */
  async hasHistorySection(): Promise<boolean> {
    return await this.historySection.isVisible().catch(() => false)
  }

  /**
   * Get audit event count
   */
  async getAuditEventCount(): Promise<number> {
    if (!(await this.hasHistorySection())) {
      return 0
    }

    // Count audit event cards
    const eventCards = this.page.locator('[data-testid="audit-event"], .MuiCard-root').filter({ hasText: /created|updated|deleted/i })
    return await eventCards.count()
  }

  /**
   * Get first audit event action
   */
  async getFirstAuditEventAction(): Promise<string | null> {
    if (!(await this.hasHistorySection())) {
      return null
    }

    const firstEvent = this.page.locator('[data-testid="audit-event"], .MuiCard-root').first()
    if (await firstEvent.count() > 0) {
      const actionText = firstEvent.locator('p, span, div').first()
      return await actionText.textContent()
    }
    return null
  }

  /**
   * Click view all history button
   */
  async clickViewAllHistory(): Promise<void> {
    const viewAllButton = this.page.locator('button:has-text("View All"), a:has-text("View All")').first()
    if (await viewAllButton.count() > 0) {
      await Promise.all([
        this.page.waitForURL(/.*history.*/, { timeout: 10000 }),
        viewAllButton.click(),
      ])
    }
  }

  /**
   * Click back button
   */
  async clickBack(): Promise<void> {
    await this.backButton.waitFor({ state: 'visible', timeout: 10000 })
    await Promise.all([
      this.page.waitForURL(/.*assets.*/, { timeout: 10000 }),
      this.backButton.click(),
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
   * Assert asset detail page is loaded
   */
  async assertPageLoaded(): Promise<void> {
    await this.assertVisible('h4, h1, h2, h3')
    const assetName = await this.getAssetName()
    expect(assetName).not.toBe('')
  }

  /**
   * Assert asset information is displayed
   */
  async assertAssetInfoDisplayed(): Promise<void> {
    await this.assertVisible('text=Asset Information, [data-testid="asset-info"]')

    const name = await this.getAssetName()
    expect(name).not.toBe('')

    const key = await this.getAssetKey()
    expect(key).not.toBe('')
  }

  /**
   * Assert edit button is visible
   */
  async assertEditButtonVisible(): Promise<void> {
    await this.assertVisible('button:has-text("Edit")')
  }

  /**
   * Assert delete button is visible
   */
  async assertDeleteButtonVisible(): Promise<void> {
    await this.assertVisible('button:has-text("Delete")')
  }

  /**
   * Assert contract section is displayed (if contract exists)
   */
  async assertContractSection(shouldExist: boolean = true): Promise<void> {
    const exists = await this.hasContractSection()
    expect(exists).toBe(shouldExist)
  }

  /**
   * Assert dataset section is displayed (if dataset exists)
   */
  async assertDatasetSection(shouldExist: boolean = true): Promise<void> {
    const exists = await this.hasDatasetSection()
    expect(exists).toBe(shouldExist)
  }

  /**
   * Assert history section is displayed
   */
  async assertHistorySectionDisplayed(): Promise<void> {
    await this.assertVisible('text=History, [data-testid="history-section"]')
  }
}

