/**
 * Contract Detail Modal Page Object Model
 *
 * Page Object Model for the ContractDetailModal component.
 * Encapsulates all contract detail modal interactions and assertions.
 *
 * Uses real implementations - no mocks/stubs. Always fixes root cause.
 */

import { Page, Locator, expect } from '@playwright/test'
import { BasePage } from '../utils/page-objects'

/**
 * Contract Detail Modal Page Object
 */
export class ContractDetailModalPage extends BasePage {
  // Modal locators
  readonly modal: Locator
  readonly modalTitle: Locator
  readonly closeButton: Locator

  // Tab locators
  readonly detailsTab: Locator
  readonly previewTab: Locator

  // Content locators
  readonly description: Locator
  readonly domain: Locator
  readonly accessMode: Locator
  readonly price: Locator
  readonly publishedDate: Locator
  readonly tags: Locator

  // Action buttons
  readonly downloadButton: Locator
  readonly requestAccessButton: Locator
  readonly closeModalButton: Locator

  // Loading/Error states
  readonly loadingIndicator: Locator
  readonly errorAlert: Locator
  readonly noContractAlert: Locator

  // Preview content
  readonly contractPreview: Locator

  constructor(page: Page) {
    super(page, '')

    // Modal locators
    this.modal = page.locator('[role="dialog"]:has-text("Contract Details"), [role="dialog"]').first()
    this.modalTitle = this.modal.locator('h6, [role="heading"]').first()
    this.closeButton = this.modal.locator('button[aria-label*="close"], button:has([data-testid*="close"])').first()

    // Tab locators
    this.detailsTab = this.modal.locator('button[role="tab"]:has-text("Details")').first()
    this.previewTab = this.modal.locator('button[role="tab"]:has-text("Preview")').first()

    // Content locators
    this.description = this.modal.locator('text=Description').locator('..').locator('p, span, div').first()
    this.domain = this.modal.locator('text=Domain').locator('..').locator('p, span, div').first()
    this.accessMode = this.modal.locator('text=Access Mode').locator('..').locator('p, span, div').first()
    this.price = this.modal.locator('text=Price').locator('..').locator('p, span, div').first()
    this.publishedDate = this.modal.locator('text=Published').locator('..').locator('p, span, div').first()
    this.tags = this.modal.locator('text=Tags').locator('..')

    // Action buttons
    this.downloadButton = this.modal.locator('button:has-text("Download Contract"), button:has([data-testid*="download"])').first()
    this.requestAccessButton = this.modal.locator('button:has-text("Request Access"), button:has([data-testid*="request-access"])').first()
    this.closeModalButton = this.modal.locator('button:has-text("Close")').first()

    // Loading/Error states
    this.loadingIndicator = this.modal.locator('[role="progressbar"], .MuiCircularProgress-root').first()
    this.errorAlert = this.modal.locator('[role="alert"]:has-text("Could not load"), [role="alert"]:has-text("error")').first()
    this.noContractAlert = this.modal.locator('[role="alert"]:has-text("does not have an associated contract")').first()

    // Preview content
    this.contractPreview = this.modal.locator('[data-testid="contract-preview"], .contract-preview').first()
  }

  /**
   * Wait for modal to be visible
   */
  async waitForModal(): Promise<void> {
    await this.modal.waitFor({ state: 'visible', timeout: 10000 })
  }

  /**
   * Wait for modal to be hidden
   */
  async waitForModalHidden(): Promise<void> {
    await this.modal.waitFor({ state: 'hidden', timeout: 5000 })
  }

  /**
   * Get modal title
   */
  async getModalTitle(): Promise<string> {
    await this.modalTitle.waitFor({ state: 'visible', timeout: 10000 })
    return (await this.modalTitle.textContent()) || ''
  }

  /**
   * Get description text
   */
  async getDescription(): Promise<string | null> {
    if ((await this.description.count()) > 0) {
      return await this.description.textContent()
    }
    return null
  }

  /**
   * Get domain
   */
  async getDomain(): Promise<string | null> {
    if ((await this.domain.count()) > 0) {
      return await this.domain.textContent()
    }
    return null
  }

  /**
   * Get access mode
   */
  async getAccessMode(): Promise<string | null> {
    if ((await this.accessMode.count()) > 0) {
      return await this.accessMode.textContent()
    }
    return null
  }

  /**
   * Get price
   */
  async getPrice(): Promise<string | null> {
    if ((await this.price.count()) > 0) {
      return await this.price.textContent()
    }
    return null
  }

  /**
   * Get published date
   */
  async getPublishedDate(): Promise<string | null> {
    if ((await this.publishedDate.count()) > 0) {
      return await this.publishedDate.textContent()
    }
    return null
  }

  /**
   * Get tags
   */
  async getTags(): Promise<string[]> {
    const tagElements = this.tags.locator('span, p, div').filter({ hasText: /.+/ })
    const count = await tagElements.count()
    const tags: string[] = []
    for (let i = 0; i < count; i++) {
      const tag = await tagElements.nth(i).textContent()
      if (tag) tags.push(tag)
    }
    return tags
  }

  /**
   * Click details tab
   */
  async clickDetailsTab(): Promise<void> {
    await this.detailsTab.waitFor({ state: 'visible', timeout: 10000 })
    await this.detailsTab.click()
    await this.page.waitForTimeout(500) // Wait for tab switch
  }

  /**
   * Click preview tab
   */
  async clickPreviewTab(): Promise<void> {
    if ((await this.previewTab.count()) > 0) {
      await this.previewTab.waitFor({ state: 'visible', timeout: 10000 })
      await this.previewTab.click()
      await this.page.waitForTimeout(500) // Wait for tab switch
    }
  }

  /**
   * Click download button
   */
  async clickDownload(): Promise<void> {
    await this.downloadButton.waitFor({ state: 'visible', timeout: 10000 })
    await this.downloadButton.click()
    // Wait for download to start (browser download event)
    await this.page.waitForTimeout(1000)
  }

  /**
   * Click request access button
   */
  async clickRequestAccess(): Promise<void> {
    if ((await this.requestAccessButton.count()) > 0) {
      await this.requestAccessButton.waitFor({ state: 'visible', timeout: 10000 })
      await this.requestAccessButton.click()
    }
  }

  /**
   * Close modal
   */
  async close(): Promise<void> {
    // Try close button first, then close modal button
    if ((await this.closeButton.count()) > 0) {
      await this.closeButton.click()
    } else if ((await this.closeModalButton.count()) > 0) {
      await this.closeModalButton.click()
    } else {
      // Press Escape key as fallback
      await this.page.keyboard.press('Escape')
    }
    await this.waitForModalHidden()
  }

  /**
   * Check if modal is visible
   */
  async isVisible(): Promise<boolean> {
    return await this.modal.isVisible().catch(() => false)
  }

  /**
   * Check if details tab is active
   */
  async isDetailsTabActive(): Promise<boolean> {
    const ariaSelected = await this.detailsTab.getAttribute('aria-selected')
    return ariaSelected === 'true'
  }

  /**
   * Check if preview tab is visible
   */
  async isPreviewTabVisible(): Promise<boolean> {
    return await this.previewTab.isVisible().catch(() => false)
  }

  /**
   * Check if preview tab is active
   */
  async isPreviewTabActive(): Promise<boolean> {
    if (!(await this.isPreviewTabVisible())) {
      return false
    }
    const ariaSelected = await this.previewTab.getAttribute('aria-selected')
    return ariaSelected === 'true'
  }

  /**
   * Check if download button is visible
   */
  async isDownloadButtonVisible(): Promise<boolean> {
    return await this.downloadButton.isVisible().catch(() => false)
  }

  /**
   * Check if request access button is visible
   */
  async isRequestAccessButtonVisible(): Promise<boolean> {
    return await this.requestAccessButton.isVisible().catch(() => false)
  }

  /**
   * Check if loading indicator is visible
   */
  async isLoading(): Promise<boolean> {
    return await this.loadingIndicator.isVisible().catch(() => false)
  }

  /**
   * Check if error alert is visible
   */
  async hasError(): Promise<boolean> {
    return await this.errorAlert.isVisible().catch(() => false)
  }

  /**
   * Check if no contract alert is visible
   */
  async hasNoContractAlert(): Promise<boolean> {
    return await this.noContractAlert.isVisible().catch(() => false)
  }

  /**
   * Check if contract preview is visible
   */
  async isPreviewVisible(): Promise<boolean> {
    return await this.contractPreview.isVisible().catch(() => false)
  }

  /**
   * Assert modal is open
   */
  async assertModalOpen(): Promise<void> {
    await this.waitForModal()
    expect(await this.isVisible()).toBe(true)
  }

  /**
   * Assert modal is closed
   */
  async assertModalClosed(): Promise<void> {
    await this.waitForModalHidden()
    expect(await this.isVisible()).toBe(false)
  }

  /**
   * Assert modal title is displayed
   */
  async assertTitleDisplayed(): Promise<void> {
    const title = await this.getModalTitle()
    expect(title).not.toBe('')
  }

  /**
   * Assert description is displayed
   */
  async assertDescriptionDisplayed(): Promise<void> {
    const description = await this.getDescription()
    expect(description).not.toBeNull()
    expect(description).not.toBe('')
  }

  /**
   * Assert download button is visible
   */
  async assertDownloadButtonVisible(): Promise<void> {
    await expect(this.downloadButton).toBeVisible()
  }

  /**
   * Assert request access button is visible (for REQUEST_APPROVAL listings)
   */
  async assertRequestAccessButtonVisible(): Promise<void> {
    await expect(this.requestAccessButton).toBeVisible()
  }

  /**
   * Assert request access button is not visible (for FREE listings)
   */
  async assertRequestAccessButtonNotVisible(): Promise<void> {
    await expect(this.requestAccessButton).not.toBeVisible()
  }
}

