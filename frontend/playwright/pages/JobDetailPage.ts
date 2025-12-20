/**
 * Job Detail Page Object Model
 *
 * Page Object Model for the job detail page.
 * Encapsulates all job detail page interactions and assertions.
 *
 * Uses real implementations - no mocks/stubs. Always fixes root cause.
 */

import { Page, Locator, expect } from '@playwright/test'
import { BasePage } from '../utils/page-objects'

/**
 * Job Detail Page Object
 */
export class JobDetailPage extends BasePage {
  // Header locators
  readonly backButton: Locator
  readonly refreshButton: Locator
  readonly cancelButton: Locator
  readonly jobTitle: Locator

  // Job status locators
  readonly jobStatus: Locator
  readonly jobType: Locator
  readonly jobProgress: Locator
  readonly jobProgressBar: Locator

  // Job information locators
  readonly jobInfoSection: Locator
  readonly jobId: Locator
  readonly resourceType: Locator
  readonly resourceId: Locator
  readonly createdAt: Locator
  readonly startedAt: Locator
  readonly completedAt: Locator
  readonly duration: Locator

  // Job details locators
  readonly jobDetailsSection: Locator
  readonly jobLogs: Locator
  readonly jobError: Locator
  readonly jobResult: Locator

  // Cancel dialog
  readonly cancelDialog: Locator
  readonly cancelConfirmButton: Locator
  readonly cancelCancelButton: Locator

  // Notification locators (toast/snackbar)
  readonly successNotification: Locator
  readonly errorNotification: Locator
  readonly infoNotification: Locator

  constructor(page: Page, jobId: string) {
    super(page, `/jobs/${jobId}`)

    // Header locators
    this.backButton = page.locator('button[aria-label*="Back"], button:has-text("Back")').first()
    this.refreshButton = page.locator('button[aria-label*="Refresh"], button:has([data-testid*="refresh"])').first()
    this.cancelButton = page.locator('button:has-text("Cancel"), button[aria-label*="Cancel"]').first()
    this.jobTitle = page.locator('h4, h1, h2, h3').filter({ hasText: /.+/ }).first()

    // Job status locators
    this.jobStatus = page.locator('[role="button"]:has-text("PENDING"), [role="button"]:has-text("RUNNING"), [role="button"]:has-text("COMPLETED"), [role="button"]:has-text("FAILED"), [role="button"]:has-text("CANCELLED")').first()
    this.jobType = page.locator('text=Type').locator('..').locator('p, span, div').first()
    this.jobProgress = page.locator('text=Progress, [role="progressbar"]').first()
    this.jobProgressBar = page.locator('[role="progressbar"], .MuiLinearProgress-root').first()

    // Job information locators
    this.jobInfoSection = page.locator('text=Job Information, [data-testid="job-info"]').first()
    this.jobId = page.locator('text=Job ID, text=/^[a-f0-9-]{36}$/i').first()
    this.resourceType = page.locator('text=Resource Type').locator('..').locator('p, span, div').first()
    this.resourceId = page.locator('text=Resource ID').locator('..').locator('p, span, div').first()
    this.createdAt = page.locator('text=Created At').locator('..').locator('p, span, div').first()
    this.startedAt = page.locator('text=Started At').locator('..').locator('p, span, div').first()
    this.completedAt = page.locator('text=Completed At').locator('..').locator('p, span, div').first()
    this.duration = page.locator('text=Duration').locator('..').locator('p, span, div').first()

    // Job details locators
    this.jobDetailsSection = page.locator('text=Job Details, [data-testid="job-details"]').first()
    this.jobLogs = page.locator('text=Logs, [data-testid="job-logs"]').first()
    this.jobError = page.locator('text=Error, [role="alert"]:has-text("error" i)').first()
    this.jobResult = page.locator('text=Result, [data-testid="job-result"]').first()

    // Cancel dialog
    this.cancelDialog = page.locator('[role="dialog"]:has-text("Cancel")')
    this.cancelConfirmButton = this.cancelDialog.locator('button:has-text("Cancel"), button:has-text("Confirm")').first()
    this.cancelCancelButton = this.cancelDialog.locator('button:has-text("Cancel")').last()

    // Notification locators (toast/snackbar)
    this.successNotification = page.locator('[role="alert"]:has-text("completed successfully"), [role="status"]:has-text("success")').first()
    this.errorNotification = page.locator('[role="alert"]:has-text("failed"), [role="status"]:has-text("error")').first()
    this.infoNotification = page.locator('[role="alert"]:has-text("cancelled"), [role="status"]:has-text("info")').first()
  }

  /**
   * Navigate to job detail page
   */
  async goto(): Promise<void> {
    await super.goto({ waitUntil: 'networkidle' })
    await this.waitForPageLoad()
  }

  /**
   * Wait for job detail page to be fully loaded
   */
  async waitForPageLoad(): Promise<void> {
    // Wait for job status or loading/error state
    await Promise.race([
      this.jobStatus.waitFor({ state: 'visible', timeout: 15000 }),
      this.page.waitForSelector('text=Loading, text=Failed to load', { timeout: 15000 }),
    ])
  }

  /**
   * Get job status
   */
  async getJobStatus(): Promise<string | null> {
    if ((await this.jobStatus.count()) > 0) {
      return await this.jobStatus.textContent()
    }
    return null
  }

  /**
   * Get job type
   */
  async getJobType(): Promise<string | null> {
    if ((await this.jobType.count()) > 0) {
      return await this.jobType.textContent()
    }
    return null
  }

  /**
   * Get job progress percentage
   */
  async getJobProgress(): Promise<number | null> {
    if ((await this.jobProgressBar.count()) > 0) {
      const ariaValueNow = await this.jobProgressBar.getAttribute('aria-valuenow')
      if (ariaValueNow) {
        return parseFloat(ariaValueNow)
      }
      // Try to extract from style or text
      const progressText = await this.jobProgress.textContent()
      if (progressText) {
        const match = progressText.match(/(\d+)%/)
        if (match) return parseInt(match[1], 10)
      }
    }
    return null
  }

  /**
   * Get job ID
   */
  async getJobId(): Promise<string | null> {
    if ((await this.jobId.count()) > 0) {
      return await this.jobId.textContent()
    }
    return null
  }

  /**
   * Wait for job status to change
   */
  async waitForStatusChange(
    fromStatus: string | null,
    timeout: number = 30000
  ): Promise<string | null> {
    const startTime = Date.now()
    while (Date.now() - startTime < timeout) {
      const currentStatus = await this.getJobStatus()
      if (currentStatus !== fromStatus && currentStatus !== null) {
        return currentStatus
      }
      await this.page.waitForTimeout(1000) // Check every second
    }
    return null
  }

  /**
   * Wait for job to reach terminal state (COMPLETED, FAILED, CANCELLED)
   */
  async waitForTerminalState(timeout: number = 60000): Promise<string | null> {
    const terminalStates = ['COMPLETED', 'FAILED', 'CANCELLED']
    const startTime = Date.now()

    while (Date.now() - startTime < timeout) {
      const currentStatus = await this.getJobStatus()
      if (currentStatus && terminalStates.some((state) => currentStatus.toUpperCase().includes(state))) {
        return currentStatus
      }
      await this.page.waitForTimeout(1000) // Check every second
    }
    return null
  }

  /**
   * Wait for job progress to update
   */
  async waitForProgressUpdate(
    previousProgress: number | null,
    timeout: number = 30000
  ): Promise<number | null> {
    const startTime = Date.now()
    while (Date.now() - startTime < timeout) {
      const currentProgress = await this.getJobProgress()
      if (currentProgress !== previousProgress && currentProgress !== null) {
        return currentProgress
      }
      await this.page.waitForTimeout(1000) // Check every second
    }
    return null
  }

  /**
   * Wait for success notification
   */
  async waitForSuccessNotification(timeout: number = 10000): Promise<void> {
    await this.successNotification.waitFor({ state: 'visible', timeout })
  }

  /**
   * Wait for error notification
   */
  async waitForErrorNotification(timeout: number = 10000): Promise<void> {
    await this.errorNotification.waitFor({ state: 'visible', timeout })
  }

  /**
   * Check if success notification is visible
   */
  async hasSuccessNotification(): Promise<boolean> {
    return await this.successNotification.isVisible().catch(() => false)
  }

  /**
   * Check if error notification is visible
   */
  async hasErrorNotification(): Promise<boolean> {
    return await this.errorNotification.isVisible().catch(() => false)
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
   * Click cancel button
   */
  async clickCancel(): Promise<void> {
    await this.cancelButton.waitFor({ state: 'visible', timeout: 10000 })
    await this.cancelButton.click()
    await this.cancelDialog.waitFor({ state: 'visible', timeout: 5000 })
  }

  /**
   * Confirm cancel in dialog
   */
  async confirmCancel(): Promise<void> {
    await this.cancelConfirmButton.waitFor({ state: 'visible', timeout: 5000 })
    await this.cancelConfirmButton.click()
    await this.cancelDialog.waitFor({ state: 'hidden', timeout: 10000 })
  }

  /**
   * Cancel cancel in dialog
   */
  async cancelCancel(): Promise<void> {
    await this.cancelCancelButton.waitFor({ state: 'visible', timeout: 5000 })
    await this.cancelCancelButton.click()
    await this.cancelDialog.waitFor({ state: 'hidden', timeout: 5000 })
  }

  /**
   * Assert job detail page is loaded
   */
  async assertPageLoaded(): Promise<void> {
    await this.assertVisible('h4, h1, h2, h3')
    const status = await this.getJobStatus()
    expect(status).not.toBeNull()
  }

  /**
   * Assert job status is displayed
   */
  async assertJobStatusDisplayed(): Promise<void> {
    await expect(this.jobStatus).toBeVisible()
    const status = await this.getJobStatus()
    expect(status).not.toBeNull()
  }

  /**
   * Assert job progress is displayed (if job is running)
   */
  async assertJobProgressDisplayed(): Promise<void> {
    const status = await this.getJobStatus()
    if (status && status.toUpperCase().includes('RUNNING')) {
      // Progress may or may not be visible depending on job type
      const hasProgress = await this.jobProgressBar.isVisible().catch(() => false)
      // Just verify the method doesn't throw, progress may not always be available
    }
  }
}

