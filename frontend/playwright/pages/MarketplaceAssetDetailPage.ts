/**
 * Marketplace Asset Detail Page Object Model
 *
 * Page Object Model for the marketplace asset detail page.
 * Encapsulates all marketplace asset detail page interactions and assertions.
 *
 * Uses real implementations - no mocks/stubs. Always fixes root cause.
 */

import { Page, Locator, expect } from '@playwright/test'
import { BasePage } from '../utils/page-objects'

/**
 * Marketplace Asset Detail Page Object
 */
export class MarketplaceAssetDetailPage extends BasePage {
  // Header locators
  readonly backButton: Locator
  readonly refreshButton: Locator
  readonly downloadContractButton: Locator
  readonly requestAccessButton: Locator
  readonly assetTitle: Locator

  // Section locators
  readonly assetInfoSection: Locator
  readonly contractDetailsSection: Locator
  readonly datasetInfoSection: Locator
  readonly qualityMetricsSection: Locator
  readonly complianceSection: Locator
  readonly marketplacePolicySection: Locator
  readonly relatedAssetsSection: Locator

  // Access request dialog
  readonly accessRequestDialog: Locator
  readonly accessRequestConfirmButton: Locator
  readonly accessRequestCancelButton: Locator

  constructor(page: Page, listingId: string) {
    super(page, `/marketplace/${listingId}`)

    // Header locators
    this.backButton = page.locator('button[aria-label*="Back"], button:has([data-testid*="back"])').first()
    this.refreshButton = page.locator('button[aria-label*="Refresh"], button:has([data-testid*="refresh"])').first()
    this.downloadContractButton = page.locator('button:has-text("Download Contract"), button:has([data-testid*="download"])').first()
    this.requestAccessButton = page.locator('button:has-text("Request Access"), button:has([data-testid*="request-access"])').first()
    this.assetTitle = page.locator('h4, h1, h2, h3').filter({ hasText: /.+/ }).first()

    // Section locators
    this.assetInfoSection = page.locator('text=Asset Information, [data-testid="asset-info"]').first()
    this.contractDetailsSection = page.locator('text=Contract Details, [data-testid="contract-details"]').first()
    this.datasetInfoSection = page.locator('text=Dataset Information, [data-testid="dataset-info"]').first()
    this.qualityMetricsSection = page.locator('text=Data Quality Metrics, [data-testid="quality-metrics"]').first()
    this.complianceSection = page.locator('text=Compliance Information, [data-testid="compliance"]').first()
    this.marketplacePolicySection = page.locator('text=Marketplace Policy, [data-testid="marketplace-policy"]').first()
    this.relatedAssetsSection = page.locator('text=Related Assets, [data-testid="related-assets"]').first()

    // Access request dialog
    this.accessRequestDialog = page.locator('[role="dialog"]:has-text("Request Access")')
    this.accessRequestConfirmButton = this.accessRequestDialog.locator('button:has-text("Confirm Request"), button:has-text("Confirm")').first()
    this.accessRequestCancelButton = this.accessRequestDialog.locator('button:has-text("Cancel")').first()
  }

  /**
   * Navigate to marketplace asset detail page
   */
  async goto(): Promise<void> {
    await super.goto({ waitUntil: 'networkidle' })
    await this.waitForPageLoad()
  }

  /**
   * Wait for marketplace asset detail page to be fully loaded
   */
  async waitForPageLoad(): Promise<void> {
    // Wait for asset title or loading to complete
    await this.page.waitForSelector('h4, h1, h2, h3', { timeout: 15000 })
    // Wait for either asset info or error state
    await Promise.race([
      this.page.waitForSelector('text=Asset Information, [data-testid="asset-info"]', { timeout: 10000 }),
      this.page.waitForSelector('text=Failed to load, text=Error', { timeout: 10000 }),
    ])
  }

  /**
   * Get asset title
   */
  async getAssetTitle(): Promise<string> {
    await this.assetTitle.waitFor({ state: 'visible', timeout: 10000 })
    return (await this.assetTitle.textContent()) || ''
  }

  /**
   * Get asset description
   */
  async getAssetDescription(): Promise<string | null> {
    const descElement = this.page.locator('text=Description').locator('..').locator('p, span, div').first()
    if ((await descElement.count()) > 0) {
      return await descElement.textContent()
    }
    return null
  }

  /**
   * Get asset domain
   */
  async getAssetDomain(): Promise<string | null> {
    const domainChip = this.page.locator('text=Domain').locator('..').locator('[role="button"], span').first()
    if ((await domainChip.count()) > 0) {
      return await domainChip.textContent()
    }
    return null
  }

  /**
   * Get asset tags
   */
  async getAssetTags(): Promise<string[]> {
    const tagChips = this.page.locator('text=Tags').locator('..').locator('[role="button"], span').filter({ hasText: /.+/ })
    const count = await tagChips.count()
    const tags: string[] = []
    for (let i = 0; i < count; i++) {
      const tag = await tagChips.nth(i).textContent()
      if (tag) tags.push(tag)
    }
    return tags
  }

  /**
   * Get contract status
   */
  async getContractStatus(): Promise<string | null> {
    const statusElement = this.page.locator('text=Status').locator('..').locator('[role="button"], span').first()
    if ((await statusElement.count()) > 0) {
      return await statusElement.textContent()
    }
    return null
  }

  /**
   * Get pricing model
   */
  async getPricingModel(): Promise<string | null> {
    const pricingElement = this.page.locator('text=Pricing Model').locator('..').locator('[role="button"], span').first()
    if ((await pricingElement.count()) > 0) {
      return await pricingElement.textContent()
    }
    return null
  }

  /**
   * Get dataset total rows
   */
  async getDatasetTotalRows(): Promise<number | null> {
    const rowsText = this.page.locator('text=Total Rows').locator('..').locator('p, span, div').first()
    if ((await rowsText.count()) > 0) {
      const text = await rowsText.textContent()
      if (text) {
        const match = text.replace(/,/g, '').match(/\d+/)
        if (match) return parseInt(match[0], 10)
      }
    }
    return null
  }

  /**
   * Get schema fields count
   */
  async getSchemaFieldsCount(): Promise<number | null> {
    const fieldsText = this.page.locator('text=Schema Fields').locator('..').locator('p, span, div').first()
    if ((await fieldsText.count()) > 0) {
      const text = await fieldsText.textContent()
      if (text) {
        const match = text.match(/\d+/)
        if (match) return parseInt(match[0], 10)
      }
    }
    return null
  }

  /**
   * Get overall quality score
   */
  async getOverallQualityScore(): Promise<number | null> {
    const scoreText = this.page.locator('text=Overall Score').locator('..').locator('p, span, h6').first()
    if ((await scoreText.count()) > 0) {
      const text = await scoreText.textContent()
      if (text) {
        const match = text.match(/(\d+)%/)
        if (match) return parseInt(match[1], 10) / 100
      }
    }
    return null
  }

  /**
   * Get completeness score
   */
  async getCompletenessScore(): Promise<number | null> {
    const completenessText = this.page.locator('text=Completeness').locator('..').locator('p, span').first()
    if ((await completenessText.count()) > 0) {
      const text = await completenessText.textContent()
      if (text) {
        const match = text.match(/(\d+)%/)
        if (match) return parseInt(match[1], 10) / 100
      }
    }
    return null
  }

  /**
   * Get accuracy score
   */
  async getAccuracyScore(): Promise<number | null> {
    const accuracyText = this.page.locator('text=Accuracy').locator('..').locator('p, span').first()
    if ((await accuracyText.count()) > 0) {
      const text = await accuracyText.textContent()
      if (text) {
        const match = text.match(/(\d+)%/)
        if (match) return parseInt(match[1], 10) / 100
      }
    }
    return null
  }

  /**
   * Get freshness status
   */
  async getFreshnessStatus(): Promise<string | null> {
    const freshnessChip = this.page.locator('text=Freshness').locator('..').locator('[role="button"], span').first()
    if ((await freshnessChip.count()) > 0) {
      return await freshnessChip.textContent()
    }
    return null
  }

  /**
   * Get license summary
   */
  async getLicenseSummary(): Promise<string | null> {
    const licenseText = this.page.locator('text=License').locator('..').locator('p, span, div').first()
    if ((await licenseText.count()) > 0) {
      return await licenseText.textContent()
    }
    return null
  }

  /**
   * Get intended use tags
   */
  async getIntendedUseTags(): Promise<string[]> {
    const intendedUseSection = this.page.locator('text=Intended Use').locator('..')
    const tagChips = intendedUseSection.locator('[role="button"], span').filter({ hasText: /.+/ })
    const count = await tagChips.count()
    const tags: string[] = []
    for (let i = 0; i < count; i++) {
      const tag = await tagChips.nth(i).textContent()
      if (tag) tags.push(tag)
    }
    return tags
  }

  /**
   * Get restricted use tags
   */
  async getRestrictedUseTags(): Promise<string[]> {
    const restrictedUseSection = this.page.locator('text=Restricted Use').locator('..')
    const tagChips = restrictedUseSection.locator('[role="button"], span').filter({ hasText: /.+/ })
    const count = await tagChips.count()
    const tags: string[] = []
    for (let i = 0; i < count; i++) {
      const tag = await tagChips.nth(i).textContent()
      if (tag) tags.push(tag)
    }
    return tags
  }

  /**
   * Get related assets count
   */
  async getRelatedAssetsCount(): Promise<number> {
    if (!(await this.hasRelatedAssetsSection())) {
      return 0
    }
    const assetCards = this.page.locator('[data-testid="marketplace-listing-card"], .MuiCard-root').filter({ hasText: /.+/ })
    return await assetCards.count()
  }

  /**
   * Click download contract button
   */
  async clickDownloadContract(): Promise<void> {
    await this.downloadContractButton.waitFor({ state: 'visible', timeout: 10000 })
    await this.downloadContractButton.click()
    // Wait for download to start (browser download event)
    await this.page.waitForTimeout(1000)
  }

  /**
   * Click request access button
   */
  async clickRequestAccess(): Promise<void> {
    await this.requestAccessButton.waitFor({ state: 'visible', timeout: 10000 })
    await this.requestAccessButton.click()
    await this.accessRequestDialog.waitFor({ state: 'visible', timeout: 5000 })
  }

  /**
   * Confirm access request in dialog
   */
  async confirmAccessRequest(): Promise<void> {
    await this.accessRequestConfirmButton.waitFor({ state: 'visible', timeout: 5000 })
    await this.accessRequestConfirmButton.click()
    await this.accessRequestDialog.waitFor({ state: 'hidden', timeout: 10000 })
  }

  /**
   * Cancel access request in dialog
   */
  async cancelAccessRequest(): Promise<void> {
    await this.accessRequestCancelButton.waitFor({ state: 'visible', timeout: 5000 })
    await this.accessRequestCancelButton.click()
    await this.accessRequestDialog.waitFor({ state: 'hidden', timeout: 5000 })
  }

  /**
   * Click back button
   */
  async clickBack(): Promise<void> {
    await this.backButton.waitFor({ state: 'visible', timeout: 10000 })
    await Promise.all([
      this.page.waitForURL(/.*marketplace.*/, { timeout: 10000 }),
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
   * Click on related asset card
   */
  async clickRelatedAsset(index: number): Promise<void> {
    const assetCards = this.page.locator('[data-testid="marketplace-listing-card"], .MuiCard-root').filter({ hasText: /.+/ })
    await assetCards.nth(index).waitFor({ state: 'visible', timeout: 10000 })
    await Promise.all([
      this.page.waitForURL(/.*marketplace\/.*/, { timeout: 10000 }),
      assetCards.nth(index).click(),
    ])
  }

  /**
   * Check if asset info section is visible
   */
  async hasAssetInfoSection(): Promise<boolean> {
    return await this.assetInfoSection.isVisible().catch(() => false)
  }

  /**
   * Check if contract details section is visible
   */
  async hasContractDetailsSection(): Promise<boolean> {
    return await this.contractDetailsSection.isVisible().catch(() => false)
  }

  /**
   * Check if dataset info section is visible
   */
  async hasDatasetInfoSection(): Promise<boolean> {
    return await this.datasetInfoSection.isVisible().catch(() => false)
  }

  /**
   * Check if quality metrics section is visible
   */
  async hasQualityMetricsSection(): Promise<boolean> {
    return await this.qualityMetricsSection.isVisible().catch(() => false)
  }

  /**
   * Check if compliance section is visible
   */
  async hasComplianceSection(): Promise<boolean> {
    return await this.complianceSection.isVisible().catch(() => false)
  }

  /**
   * Check if marketplace policy section is visible
   */
  async hasMarketplacePolicySection(): Promise<boolean> {
    return await this.marketplacePolicySection.isVisible().catch(() => false)
  }

  /**
   * Check if related assets section is visible
   */
  async hasRelatedAssetsSection(): Promise<boolean> {
    return await this.relatedAssetsSection.isVisible().catch(() => false)
  }

  /**
   * Assert marketplace asset detail page is loaded
   */
  async assertPageLoaded(): Promise<void> {
    await this.assertVisible('h4, h1, h2, h3')
    const title = await this.getAssetTitle()
    expect(title).not.toBe('')
  }

  /**
   * Assert asset information is displayed
   */
  async assertAssetInfoDisplayed(): Promise<void> {
    await this.assertVisible('text=Asset Information, [data-testid="asset-info"]')

    const title = await this.getAssetTitle()
    expect(title).not.toBe('')
  }

  /**
   * Assert contract details are displayed
   */
  async assertContractDetailsDisplayed(): Promise<void> {
    await this.assertVisible('text=Contract Details, [data-testid="contract-details"]')
  }

  /**
   * Assert dataset information is displayed
   */
  async assertDatasetInfoDisplayed(): Promise<void> {
    await this.assertVisible('text=Dataset Information, [data-testid="dataset-info"]')
  }

  /**
   * Assert data quality metrics are displayed
   */
  async assertQualityMetricsDisplayed(): Promise<void> {
    await this.assertVisible('text=Data Quality Metrics, [data-testid="quality-metrics"]')
  }

  /**
   * Assert compliance information is displayed
   */
  async assertComplianceDisplayed(): Promise<void> {
    await this.assertVisible('text=Compliance Information, [data-testid="compliance"]')
  }

  /**
   * Assert marketplace policy is displayed
   */
  async assertMarketplacePolicyDisplayed(): Promise<void> {
    await this.assertVisible('text=Marketplace Policy, [data-testid="marketplace-policy"]')
  }

  /**
   * Assert related assets are displayed
   */
  async assertRelatedAssetsDisplayed(): Promise<void> {
    await this.assertVisible('text=Related Assets, [data-testid="related-assets"]')
  }

  /**
   * Assert download contract button is visible
   */
  async assertDownloadContractButtonVisible(): Promise<void> {
    await this.assertVisible('button:has-text("Download Contract")')
  }

  /**
   * Assert request access button is visible
   */
  async assertRequestAccessButtonVisible(): Promise<void> {
    await this.assertVisible('button:has-text("Request Access")')
  }

  /**
   * Assert request access button is not visible (for FREE listings)
   */
  async assertRequestAccessButtonNotVisible(): Promise<void> {
    await expect(this.requestAccessButton).not.toBeVisible()
  }
}

