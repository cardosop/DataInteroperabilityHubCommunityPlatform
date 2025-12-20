/**
 * Asset Analyzing Page Object Model
 *
 * Page Object Model for the Asset Analyzing Page (UI-DPO-003).
 * Encapsulates all analyzing page interactions and assertions.
 *
 * Uses real implementations - no mocks/stubs. Always fixes root cause.
 */

import { Page, Locator, expect } from '@playwright/test'
import { BasePage } from '../utils/page-objects'

/**
 * Asset Analyzing Page Object
 */
export class AssetAnalyzingPage extends BasePage {
  // Locators
  readonly pageTitle: Locator
  readonly pageDescription: Locator
  readonly progressStepper: Locator
  readonly stepItems: Locator
  readonly loadingSpinner: Locator
  readonly statusMessage: Locator
  readonly progressPercentage: Locator
  readonly progressBar: Locator
  readonly errorAlert: Locator
  readonly retryButton: Locator
  readonly backgroundProcessingNote: Locator
  readonly viewAssetsButton: Locator
  readonly continueToAssetsButton: Locator

  // Step locators
  readonly uploadStep: Locator
  readonly inferSchemaStep: Locator
  readonly dqChecksStep: Locator
  readonly complianceChecksStep: Locator
  readonly prepareContractStep: Locator

  constructor(page: Page, datasetId: string) {
    super(page, `/assets/analyzing/${datasetId}`)

    // Page elements
    this.pageTitle = page.locator('h4:has-text("Analyzing Data")')
    this.pageDescription = page.locator('text=/We\'re analyzing your data/')
    this.progressStepper = page.locator('[role="region"]:has-text("stepper"), [class*="Stepper"]').first()
    this.stepItems = this.progressStepper.locator('[role="group"], [class*="Step"]')
    this.loadingSpinner = page.locator('.MuiCircularProgress-root, [class*="CircularProgress"]')
    this.statusMessage = page.locator('h6, [class*="status"]').first()
    this.progressPercentage = page.locator('text=/\\d+% complete/')
    this.progressBar = page.locator('.MuiLinearProgress-root, [class*="LinearProgress"]')
    this.errorAlert = page.locator('[role="alert"]:has-text("error"), .MuiAlert-root[severity="error"]')
    this.retryButton = this.errorAlert.locator('button:has-text("Retry")')
    this.backgroundProcessingNote = page.locator('[role="alert"]:has-text("background"), .MuiAlert-root[severity="info"]')
    this.viewAssetsButton = page.locator('button:has-text("View Assets")')
    this.continueToAssetsButton = page.locator('button:has-text("Continue to Assets")')

    // Step locators
    this.uploadStep = this.stepItems.filter({ hasText: 'Upload file' }).first()
    this.inferSchemaStep = this.stepItems.filter({ hasText: 'Infer schema' }).first()
    this.dqChecksStep = this.stepItems.filter({ hasText: 'Run data quality checks' }).first()
    this.complianceChecksStep = this.stepItems.filter({ hasText: 'Run compliance checks' }).first()
    this.prepareContractStep = this.stepItems.filter({ hasText: 'Prepare contract draft' }).first()
  }

  async goto(): Promise<void> {
    await super.goto({ waitUntil: 'networkidle' })
    await this.waitForPageLoad()
  }

  async waitForPageLoad(): Promise<void> {
    await this.pageTitle.waitFor({ state: 'visible', timeout: 15000 })
    await Promise.race([
      this.progressStepper.waitFor({ state: 'visible', timeout: 10000 }),
      this.errorAlert.waitFor({ state: 'visible', timeout: 10000 }),
    ])
  }

  /**
   * Get step status
   */
  async getStepStatus(stepLabel: string): Promise<'pending' | 'in-progress' | 'completed' | 'error' | null> {
    const step = this.stepItems.filter({ hasText: stepLabel }).first()
    if (!(await step.isVisible().catch(() => false))) {
      return null
    }

    // Check for status indicators
    const hasCheckIcon = await step.locator('[class*="CheckCircle"], svg[data-testid*="Check"]').isVisible().catch(() => false)
    const hasErrorIcon = await step.locator('[class*="Error"], svg[data-testid*="Error"]').isVisible().catch(() => false)
    const isActive = await step.evaluate((el) => {
      return el.classList.contains('active') || el.getAttribute('aria-current') === 'step'
    }).catch(() => false)

    if (hasCheckIcon) return 'completed'
    if (hasErrorIcon) return 'error'
    if (isActive) return 'in-progress'
    return 'pending'
  }

  /**
   * Get step description
   */
  async getStepDescription(stepLabel: string): Promise<string | null> {
    const step = this.stepItems.filter({ hasText: stepLabel }).first()
    if (!(await step.isVisible().catch(() => false))) {
      return null
    }

    const description = step.locator('text=/.*/').nth(1) // Second text element is usually description
    return await description.textContent().catch(() => null)
  }

  /**
   * Get current status message
   */
  async getStatusMessage(): Promise<string | null> {
    return await this.statusMessage.textContent()
  }

  /**
   * Get progress percentage
   */
  async getProgressPercentage(): Promise<number> {
    const text = await this.progressPercentage.textContent()
    if (!text) return 0
    const match = text.match(/(\d+)%/)
    return match ? parseInt(match[1], 10) : 0
  }

  /**
   * Check if loading spinner is visible
   */
  async isLoadingSpinnerVisible(): Promise<boolean> {
    return await this.loadingSpinner.isVisible().catch(() => false)
  }

  /**
   * Check if error alert is visible
   */
  async isErrorVisible(): Promise<boolean> {
    return await this.errorAlert.isVisible().catch(() => false)
  }

  /**
   * Get error message
   */
  async getErrorMessage(): Promise<string | null> {
    if (!(await this.isErrorVisible())) {
      return null
    }
    return await this.errorAlert.textContent()
  }

  /**
   * Click retry button
   */
  async clickRetry(): Promise<void> {
    await this.retryButton.click()
    await this.page.waitForTimeout(500)
  }

  /**
   * Check if background processing note is visible
   */
  async isBackgroundProcessingNoteVisible(): Promise<boolean> {
    return await this.backgroundProcessingNote.isVisible().catch(() => false)
  }

  /**
   * Navigate to assets page
   */
  async navigateToAssets(): Promise<void> {
    await this.viewAssetsButton.click()
    await this.page.waitForURL(/.*assets.*/, { timeout: 10000 })
  }

  /**
   * Wait for step to complete
   */
  async waitForStepComplete(stepLabel: string, timeout: number = 30000): Promise<void> {
    await this.page.waitForFunction(
      async (label) => {
        const step = Array.from(document.querySelectorAll('[role="group"], [class*="Step"]')).find((el) =>
          el.textContent?.includes(label)
        )
        if (!step) return false
        const hasCheck = step.querySelector('[class*="CheckCircle"], svg[data-testid*="Check"]')
        return hasCheck !== null
      },
      stepLabel,
      { timeout }
    )
  }

  /**
   * Wait for step to be in progress
   */
  async waitForStepInProgress(stepLabel: string, timeout: number = 30000): Promise<void> {
    await this.page.waitForFunction(
      async (label) => {
        const step = Array.from(document.querySelectorAll('[role="group"], [class*="Step"]')).find((el) =>
          el.textContent?.includes(label)
        )
        if (!step) return false
        const isActive = step.classList.contains('active') || step.getAttribute('aria-current') === 'step'
        return isActive
      },
      stepLabel,
      { timeout }
    )
  }

  /**
   * Assert all 5 steps are displayed
   */
  async assertAllStepsDisplayed(): Promise<void> {
    await expect(this.uploadStep).toBeVisible()
    await expect(this.inferSchemaStep).toBeVisible()
    await expect(this.dqChecksStep).toBeVisible()
    await expect(this.complianceChecksStep).toBeVisible()
    await expect(this.prepareContractStep).toBeVisible()
  }

  /**
   * Assert step status
   */
  async assertStepStatus(stepLabel: string, expectedStatus: 'pending' | 'in-progress' | 'completed' | 'error'): Promise<void> {
    const status = await this.getStepStatus(stepLabel)
    expect(status).toBe(expectedStatus)
  }

  /**
   * Assert status message contains text
   */
  async assertStatusMessageContains(text: string): Promise<void> {
    const message = await this.getStatusMessage()
    expect(message).toContain(text)
  }

  /**
   * Assert progress percentage
   */
  async assertProgressPercentage(min: number, max: number = 100): Promise<void> {
    const percentage = await this.getProgressPercentage()
    expect(percentage).toBeGreaterThanOrEqual(min)
    expect(percentage).toBeLessThanOrEqual(max)
  }

  /**
   * Assert page loaded
   */
  async assertPageLoaded(): Promise<void> {
    await expect(this.pageTitle).toBeVisible()
    await expect(this.progressStepper).toBeVisible()
  }
}

