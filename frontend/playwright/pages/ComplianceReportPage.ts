/**
 * Compliance Report Page Object Model
 *
 * Page Object Model for the compliance report page.
 * Encapsulates all compliance report page interactions and assertions.
 *
 * Uses real implementations - no mocks/stubs. Always fixes root cause.
 */

import { Page, Locator, expect } from '@playwright/test'
import { BasePage } from '../utils/page-objects'

/**
 * Compliance Report Page Object
 */
export class ComplianceReportPage extends BasePage {
  // Header locators
  readonly pageTitle: Locator
  readonly refreshButton: Locator
  readonly scheduleReportButton: Locator
  readonly exportButton: Locator
  readonly exportMenu: Locator
  readonly exportCSVMenuItem: Locator
  readonly exportPDFMenuItem: Locator

  // Filter locators
  readonly startDateInput: Locator
  readonly endDateInput: Locator
  readonly assetSelect: Locator
  readonly jurisdictionSelect: Locator

  // Overview metrics locators
  readonly totalScansCard: Locator
  readonly totalScansValue: Locator
  readonly passRateCard: Locator
  readonly passRateValue: Locator
  readonly violationCountCard: Locator
  readonly violationCountValue: Locator
  readonly riskScoreCard: Locator
  readonly riskScoreValue: Locator

  // Violation breakdown locators
  readonly violationCategoryTable: Locator
  readonly violationJurisdictionTable: Locator
  readonly violationTimelineTable: Locator

  // Asset compliance status locators
  readonly assetComplianceTable: Locator

  // Schedule dialog locators
  readonly scheduleDialog: Locator
  readonly scheduleFrequencySelect: Locator
  readonly scheduleEmailInput: Locator
  readonly scheduleConfirmButton: Locator
  readonly scheduleCancelButton: Locator

  constructor(page: Page) {
    super(page, '/compliance/reports')

    // Header locators
    this.pageTitle = page.locator('h4, h1, h2, h3:has-text("Compliance Report")').first()
    this.refreshButton = page.locator('button[aria-label*="Refresh"], button:has([data-testid*="refresh"])').first()
    this.scheduleReportButton = page.locator('button:has-text("Schedule Report")').first()
    this.exportButton = page.locator('button:has-text("Export")').first()
    this.exportMenu = page.locator('[role="menu"]').first()
    this.exportCSVMenuItem = page.locator('[role="menuitem"]:has-text("CSV")').first()
    this.exportPDFMenuItem = page.locator('[role="menuitem"]:has-text("PDF")').first()

    // Filter locators
    this.startDateInput = page.locator('input[type="date"][label*="Start Date" i], input[type="date"]').first()
    this.endDateInput = page.locator('input[type="date"][label*="End Date" i], input[type="date"]').nth(1)
    this.assetSelect = page.locator('[role="combobox"][aria-label*="Asset" i], select, input[aria-label*="Asset" i]').first()
    this.jurisdictionSelect = page.locator('[role="combobox"][aria-label*="Jurisdiction" i], select, input[aria-label*="Jurisdiction" i]').first()

    // Overview metrics locators
    this.totalScansCard = page.locator('text=Total Scans').locator('..').locator('..').first()
    this.totalScansValue = this.totalScansCard.locator('h4, h3, h2, h1').first()
    this.passRateCard = page.locator('text=Pass Rate').locator('..').locator('..').first()
    this.passRateValue = this.passRateCard.locator('h4, h3, h2, h1').first()
    this.violationCountCard = page.locator('text=Violation Count').locator('..').locator('..').first()
    this.violationCountValue = this.violationCountCard.locator('h4, h3, h2, h1').first()
    this.riskScoreCard = page.locator('text=Risk Score').locator('..').locator('..').first()
    this.riskScoreValue = this.riskScoreCard.locator('h4, h3, h2, h1').first()

    // Violation breakdown locators
    this.violationCategoryTable = page.locator('text=Violation Breakdown by Category').locator('..').locator('table').first()
    this.violationJurisdictionTable = page.locator('text=Violation Breakdown by Jurisdiction').locator('..').locator('table').first()
    this.violationTimelineTable = page.locator('text=Violation Timeline').locator('..').locator('table').first()

    // Asset compliance status locators
    this.assetComplianceTable = page.locator('text=Asset Compliance Status').locator('..').locator('table').first()

    // Schedule dialog locators
    this.scheduleDialog = page.locator('[role="dialog"]:has-text("Schedule Compliance Report")')
    this.scheduleFrequencySelect = this.scheduleDialog.locator('[role="combobox"][aria-label*="Frequency" i], select').first()
    this.scheduleEmailInput = this.scheduleDialog.locator('input[type="text"], input[type="email"]').first()
    this.scheduleConfirmButton = this.scheduleDialog.locator('button:has-text("Schedule")').first()
    this.scheduleCancelButton = this.scheduleDialog.locator('button:has-text("Cancel")').first()
  }

  /**
   * Navigate to compliance report page
   */
  async goto(): Promise<void> {
    await super.goto({ waitUntil: 'networkidle' })
    await this.waitForPageLoad()
  }

  /**
   * Wait for compliance report page to be fully loaded
   */
  async waitForPageLoad(): Promise<void> {
    // Wait for page title or loading/error state
    await Promise.race([
      this.pageTitle.waitFor({ state: 'visible', timeout: 15000 }),
      this.page.waitForSelector('text=Generating compliance report, text=Failed to generate', { timeout: 15000 }),
    ])
  }

  /**
   * Get total scans value
   */
  async getTotalScans(): Promise<number | null> {
    if ((await this.totalScansValue.count()) > 0) {
      const text = await this.totalScansValue.textContent()
      if (text) {
        const match = text.match(/(\d+)/)
        if (match) return parseInt(match[1], 10)
      }
    }
    return null
  }

  /**
   * Get pass rate value
   */
  async getPassRate(): Promise<number | null> {
    if ((await this.passRateValue.count()) > 0) {
      const text = await this.passRateValue.textContent()
      if (text) {
        const match = text.match(/(\d+\.?\d*)%/)
        if (match) return parseFloat(match[1]) / 100
      }
    }
    return null
  }

  /**
   * Get violation count value
   */
  async getViolationCount(): Promise<number | null> {
    if ((await this.violationCountValue.count()) > 0) {
      const text = await this.violationCountValue.textContent()
      if (text) {
        const match = text.match(/(\d+)/)
        if (match) return parseInt(match[1], 10)
      }
    }
    return null
  }

  /**
   * Get risk score value
   */
  async getRiskScore(): Promise<number | null> {
    if ((await this.riskScoreValue.count()) > 0) {
      const text = await this.riskScoreValue.textContent()
      if (text) {
        const match = text.match(/(\d+\.?\d*)/)
        if (match) return parseFloat(match[1])
      }
    }
    return null
  }

  /**
   * Get violation category breakdown rows
   */
  async getViolationCategoryRows(): Promise<Array<{ category: string; count: number }>> {
    const rows: Array<{ category: string; count: number }> = []
    const tableRows = this.violationCategoryTable.locator('tbody tr')
    const count = await tableRows.count()

    for (let i = 0; i < count; i++) {
      const row = tableRows.nth(i)
      const categoryCell = row.locator('td').first()
      const countCell = row.locator('td').nth(1)

      const category = await categoryCell.textContent()
      const countText = await countCell.textContent()

      if (category && countText) {
        const match = countText.match(/(\d+)/)
        if (match) {
          rows.push({
            category: category.trim(),
            count: parseInt(match[1], 10),
          })
        }
      }
    }

    return rows
  }

  /**
   * Get violation jurisdiction breakdown rows
   */
  async getViolationJurisdictionRows(): Promise<Array<{ jurisdiction: string; violations: number }>> {
    const rows: Array<{ jurisdiction: string; violations: number }> = []
    const tableRows = this.violationJurisdictionTable.locator('tbody tr')
    const count = await tableRows.count()

    for (let i = 0; i < count; i++) {
      const row = tableRows.nth(i)
      const jurisdictionCell = row.locator('td').first()
      const violationsCell = row.locator('td').nth(1)

      const jurisdiction = await jurisdictionCell.textContent()
      const violationsText = await violationsCell.textContent()

      if (jurisdiction && violationsText) {
        const match = violationsText.match(/(\d+)/)
        if (match) {
          rows.push({
            jurisdiction: jurisdiction.trim(),
            violations: parseInt(match[1], 10),
          })
        }
      }
    }

    return rows
  }

  /**
   * Get violation timeline rows
   */
  async getViolationTimelineRows(): Promise<Array<{ date: string; violations: number }>> {
    const rows: Array<{ date: string; violations: number }> = []
    const tableRows = this.violationTimelineTable.locator('tbody tr')
    const count = await tableRows.count()

    for (let i = 0; i < count; i++) {
      const row = tableRows.nth(i)
      const dateCell = row.locator('td').first()
      const violationsCell = row.locator('td').nth(2)

      const date = await dateCell.textContent()
      const violationsText = await violationsCell.textContent()

      if (date && violationsText) {
        const match = violationsText.match(/(\d+)/)
        if (match) {
          rows.push({
            date: date.trim(),
            violations: parseInt(match[1], 10),
          })
        }
      }
    }

    return rows
  }

  /**
   * Get asset compliance status rows
   */
  async getAssetComplianceRows(): Promise<Array<{ assetId: string; status: string; violationCount: number }>> {
    const rows: Array<{ assetId: string; status: string; violationCount: number }> = []
    const tableRows = this.assetComplianceTable.locator('tbody tr')
    const count = await tableRows.count()

    for (let i = 0; i < count; i++) {
      const row = tableRows.nth(i)
      const assetIdCell = row.locator('td').first()
      const statusCell = row.locator('td').nth(2)
      const violationCountCell = row.locator('td').nth(4)

      const assetId = await assetIdCell.textContent()
      const status = await statusCell.textContent()
      const violationCountText = await violationCountCell.textContent()

      if (assetId && status && violationCountText) {
        const match = violationCountText.match(/(\d+)/)
        if (match) {
          rows.push({
            assetId: assetId.trim(),
            status: status.trim(),
            violationCount: parseInt(match[1], 10),
          })
        }
      }
    }

    return rows
  }

  /**
   * Set start date filter
   */
  async setStartDate(date: string): Promise<void> {
    await this.startDateInput.waitFor({ state: 'visible', timeout: 10000 })
    await this.startDateInput.fill(date)
    await this.page.waitForTimeout(500) // Wait for filter to apply
  }

  /**
   * Set end date filter
   */
  async setEndDate(date: string): Promise<void> {
    await this.endDateInput.waitFor({ state: 'visible', timeout: 10000 })
    await this.endDateInput.fill(date)
    await this.page.waitForTimeout(500) // Wait for filter to apply
  }

  /**
   * Select asset filter
   */
  async selectAsset(assetName: string): Promise<void> {
    await this.assetSelect.waitFor({ state: 'visible', timeout: 10000 })
    await this.assetSelect.click()
    await this.page.waitForTimeout(500)
    await this.page.locator(`[role="option"]:has-text("${assetName}")`).click()
    await this.page.waitForTimeout(500) // Wait for filter to apply
  }

  /**
   * Select jurisdiction filter
   */
  async selectJurisdiction(jurisdiction: string): Promise<void> {
    await this.jurisdictionSelect.waitFor({ state: 'visible', timeout: 10000 })
    await this.jurisdictionSelect.click()
    await this.page.waitForTimeout(500)
    await this.page.locator(`[role="option"]:has-text("${jurisdiction}")`).click()
    await this.page.waitForTimeout(500) // Wait for filter to apply
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
   * Click export button
   */
  async clickExport(): Promise<void> {
    await this.exportButton.waitFor({ state: 'visible', timeout: 10000 })
    await this.exportButton.click()
    await this.exportMenu.waitFor({ state: 'visible', timeout: 5000 })
  }

  /**
   * Click export CSV menu item
   */
  async clickExportCSV(): Promise<void> {
    await this.clickExport()
    await this.exportCSVMenuItem.waitFor({ state: 'visible', timeout: 5000 })
    const downloadPromise = this.page.waitForEvent('download', { timeout: 10000 }).catch(() => null)
    await this.exportCSVMenuItem.click()
    await this.page.waitForTimeout(1000)
    return downloadPromise
  }

  /**
   * Click export PDF menu item
   */
  async clickExportPDF(): Promise<void> {
    await this.clickExport()
    await this.exportPDFMenuItem.waitFor({ state: 'visible', timeout: 5000 })
    await this.exportPDFMenuItem.click()
    await this.page.waitForTimeout(1000)
  }

  /**
   * Click schedule report button
   */
  async clickScheduleReport(): Promise<void> {
    await this.scheduleReportButton.waitFor({ state: 'visible', timeout: 10000 })
    await this.scheduleReportButton.click()
    await this.scheduleDialog.waitFor({ state: 'visible', timeout: 5000 })
  }

  /**
   * Set schedule frequency
   */
  async setScheduleFrequency(frequency: 'DAILY' | 'WEEKLY' | 'MONTHLY' | 'QUARTERLY'): Promise<void> {
    await this.scheduleFrequencySelect.waitFor({ state: 'visible', timeout: 10000 })
    await this.scheduleFrequencySelect.click()
    await this.page.waitForTimeout(500)
    await this.page.locator(`[role="option"]:has-text("${frequency}")`).click()
    await this.page.waitForTimeout(500)
  }

  /**
   * Set schedule email recipients
   */
  async setScheduleEmailRecipients(emails: string): Promise<void> {
    await this.scheduleEmailInput.waitFor({ state: 'visible', timeout: 10000 })
    await this.scheduleEmailInput.fill(emails)
  }

  /**
   * Confirm schedule
   */
  async confirmSchedule(): Promise<void> {
    await this.scheduleConfirmButton.waitFor({ state: 'visible', timeout: 5000 })
    await this.scheduleConfirmButton.click()
    await this.scheduleDialog.waitFor({ state: 'hidden', timeout: 10000 })
  }

  /**
   * Cancel schedule
   */
  async cancelSchedule(): Promise<void> {
    await this.scheduleCancelButton.waitFor({ state: 'visible', timeout: 5000 })
    await this.scheduleCancelButton.click()
    await this.scheduleDialog.waitFor({ state: 'hidden', timeout: 5000 })
  }

  /**
   * Assert compliance report page is loaded
   */
  async assertPageLoaded(): Promise<void> {
    await this.assertVisible('h4, h1, h2, h3:has-text("Compliance Report")')
  }

  /**
   * Assert compliance metrics are displayed
   */
  async assertMetricsDisplayed(): Promise<void> {
    await this.assertVisible('text=Total Scans')
    await this.assertVisible('text=Pass Rate')
    await this.assertVisible('text=Violation Count')
    await this.assertVisible('text=Risk Score')
  }

  /**
   * Assert violation breakdown by category is displayed
   */
  async assertViolationCategoryBreakdownDisplayed(): Promise<void> {
    await this.assertVisible('text=Violation Breakdown by Category')
    const hasTable = await this.violationCategoryTable.isVisible().catch(() => false)
    expect(hasTable).toBe(true)
  }

  /**
   * Assert violation breakdown by jurisdiction is displayed
   */
  async assertViolationJurisdictionBreakdownDisplayed(): Promise<void> {
    await this.assertVisible('text=Violation Breakdown by Jurisdiction')
    const hasTable = await this.violationJurisdictionTable.isVisible().catch(() => false)
    expect(hasTable).toBe(true)
  }

  /**
   * Assert violation timeline is displayed
   */
  async assertViolationTimelineDisplayed(): Promise<void> {
    await this.assertVisible('text=Violation Timeline')
    const hasTable = await this.violationTimelineTable.isVisible().catch(() => false)
    expect(hasTable).toBe(true)
  }

  /**
   * Assert asset compliance status is displayed
   */
  async assertAssetComplianceStatusDisplayed(): Promise<void> {
    await this.assertVisible('text=Asset Compliance Status')
    const hasTable = await this.assetComplianceTable.isVisible().catch(() => false)
    expect(hasTable).toBe(true)
  }
}

