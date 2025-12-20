/**
 * Asset Form Page Object Model
 *
 * Page Object Model for the asset creation/editing page.
 * Encapsulates all asset form interactions and assertions.
 *
 * Uses real implementations - no mocks/stubs. Always fixes root cause.
 */

import { Page, Locator, expect } from '@playwright/test'
import { BasePage } from '../utils/page-objects'

/**
 * Asset Form Page Object
 */
export class AssetFormPage extends BasePage {
  // Locators - Basic Information Step
  readonly nameInput: Locator
  readonly keyInput: Locator
  readonly descriptionInput: Locator
  readonly domainSelect: Locator
  readonly visibilitySelect: Locator
  readonly onboardingModeRadio: Locator
  readonly dataFirstRadio: Locator
  readonly contractFirstRadio: Locator
  readonly contractOnlyRadio: Locator

  // Locators - File Upload Step
  readonly fileUploadInput: Locator
  readonly fileUploadZone: Locator
  readonly uploadProgress: Locator
  readonly uploadedFileInfo: Locator

  // Locators - Contract Upload Step
  readonly contractCreateTab: Locator
  readonly contractUploadTab: Locator
  readonly contractNameInput: Locator
  readonly contractJsonInput: Locator
  readonly contractFileUpload: Locator

  // Locators - Activation Step
  readonly activateButton: Locator
  readonly saveDraftButton: Locator

  // Locators - Wizard Navigation
  readonly nextButton: Locator
  readonly backButton: Locator
  readonly cancelButton: Locator
  readonly wizardStep: Locator

  // Locators - Error Messages
  readonly errorAlert: Locator
  readonly fieldError: Locator

  constructor(page: Page) {
    super(page, '/assets/create')

    // Basic Information Step
    this.nameInput = page.locator('input[name="name"], input[placeholder*="name" i]')
    this.keyInput = page.locator('input[name="key"], input[placeholder*="key" i]')
    this.descriptionInput = page.locator('textarea[name="description"], textarea[placeholder*="description" i]')
    this.domainSelect = page.locator('select[name="domain"], [role="combobox"][aria-label*="domain" i]')
    this.visibilitySelect = page.locator('select[name="visibility"], [role="combobox"][aria-label*="visibility" i]')
    this.onboardingModeRadio = page.locator('input[type="radio"][name*="onboarding"], input[type="radio"][value*="first"], input[type="radio"][value*="only"]')
    this.dataFirstRadio = page.locator('input[type="radio"][value="data-first"], input[type="radio"]:has-text("Data-First")')
    this.contractFirstRadio = page.locator('input[type="radio"][value="contract-first"], input[type="radio"]:has-text("Contract-First")')
    this.contractOnlyRadio = page.locator('input[type="radio"][value="contract-only"], input[type="radio"]:has-text("Contract-Only")')

    // File Upload Step
    this.fileUploadInput = page.locator('input[type="file"]')
    this.fileUploadZone = page.locator('[role="button"]:has-text("Upload"), [class*="upload"], [data-testid*="upload"]')
    this.uploadProgress = page.locator('[role="progressbar"], [class*="progress"]')
    this.uploadedFileInfo = page.locator('[class*="file-info"], [class*="uploaded"]')

    // Contract Upload Step
    this.contractCreateTab = page.locator('button:has-text("Create New"), [role="tab"]:has-text("Create")')
    this.contractUploadTab = page.locator('button:has-text("Upload File"), [role="tab"]:has-text("Upload")')
    this.contractNameInput = page.locator('input[name*="contract"][name*="name"], input[placeholder*="contract" i][placeholder*="name" i]')
    this.contractJsonInput = page.locator('textarea[name*="contract"], textarea[placeholder*="JSON"]')
    this.contractFileUpload = page.locator('input[type="file"][accept*="json"]')

    // Activation Step
    this.activateButton = page.locator('button:has-text("Activate Asset"), button:has-text("Activate")')
    this.saveDraftButton = page.locator('button:has-text("Save as Draft"), button:has-text("Draft")')

    // Wizard Navigation
    this.nextButton = page.locator('button:has-text("Next"), button[type="submit"]:not([disabled])')
    this.backButton = page.locator('button:has-text("Back"), button:has-text("Previous")')
    this.cancelButton = page.locator('button:has-text("Cancel"), button:has-text("Back"):first-of-type')
    this.wizardStep = page.locator('[class*="wizard-step"], [class*="step"], [data-testid*="step"]')

    // Error Messages
    this.errorAlert = page.locator('[role="alert"], .alert, [class*="error"]')
    this.fieldError = page.locator('[class*="error"], [aria-invalid="true"]')
  }

  /**
   * Navigate to asset creation page
   */
  async goto(): Promise<void> {
    await super.goto({ waitUntil: 'networkidle' })
    await this.waitForPageLoad()
  }

  /**
   * Wait for asset form page to be fully loaded
   */
  async waitForPageLoad(): Promise<void> {
    await this.waitForVisible('input[name="name"], input[placeholder*="name" i]', { timeout: 10000 })
  }

  /**
   * Fill asset name
   */
  async fillName(name: string): Promise<void> {
    await this.nameInput.waitFor({ state: 'visible', timeout: 10000 })
    await this.nameInput.fill(name)
  }

  /**
   * Fill asset key
   */
  async fillKey(key: string): Promise<void> {
    await this.keyInput.waitFor({ state: 'visible', timeout: 10000 })
    await this.keyInput.fill(key)
  }

  /**
   * Fill asset description
   */
  async fillDescription(description: string): Promise<void> {
    await this.descriptionInput.waitFor({ state: 'visible', timeout: 10000 })
    await this.descriptionInput.fill(description)
  }

  /**
   * Select domain
   */
  async selectDomain(domain: string): Promise<void> {
    await this.domainSelect.waitFor({ state: 'visible', timeout: 10000 })
    await this.domainSelect.selectOption(domain)
  }

  /**
   * Select visibility
   */
  async selectVisibility(visibility: 'INTERNAL' | 'PUBLIC'): Promise<void> {
    await this.visibilitySelect.waitFor({ state: 'visible', timeout: 10000 })
    await this.visibilitySelect.selectOption(visibility)
  }

  /**
   * Select onboarding mode
   */
  async selectOnboardingMode(mode: 'data-first' | 'contract-first' | 'contract-only'): Promise<void> {
    const radioMap = {
      'data-first': this.dataFirstRadio,
      'contract-first': this.contractFirstRadio,
      'contract-only': this.contractOnlyRadio,
    }

    const radio = radioMap[mode]
    await radio.waitFor({ state: 'visible', timeout: 10000 })
    await radio.check()
  }

  /**
   * Upload file
   */
  async uploadFile(filePath: string): Promise<void> {
    await this.fileUploadInput.waitFor({ state: 'attached', timeout: 10000 })
    await this.fileUploadInput.setInputFiles(filePath)

    // Wait for upload to complete
    await this.page.waitForTimeout(2000)
  }

  /**
   * Fill contract name
   */
  async fillContractName(name: string): Promise<void> {
    await this.contractNameInput.waitFor({ state: 'visible', timeout: 10000 })
    await this.contractNameInput.fill(name)
  }

  /**
   * Fill contract JSON
   */
  async fillContractJson(json: string): Promise<void> {
    await this.contractJsonInput.waitFor({ state: 'visible', timeout: 10000 })
    await this.contractJsonInput.fill(json)
  }

  /**
   * Switch to contract create tab
   */
  async switchToContractCreateTab(): Promise<void> {
    await this.contractCreateTab.waitFor({ state: 'visible', timeout: 10000 })
    await this.contractCreateTab.click()
  }

  /**
   * Switch to contract upload tab
   */
  async switchToContractUploadTab(): Promise<void> {
    await this.contractUploadTab.waitFor({ state: 'visible', timeout: 10000 })
    await this.contractUploadTab.click()
  }

  /**
   * Upload contract file
   */
  async uploadContractFile(filePath: string): Promise<void> {
    await this.contractFileUpload.waitFor({ state: 'attached', timeout: 10000 })
    await this.contractFileUpload.setInputFiles(filePath)

    // Wait for upload to complete
    await this.page.waitForTimeout(2000)
  }

  /**
   * Click next button
   */
  async clickNext(): Promise<void> {
    await this.nextButton.waitFor({ state: 'visible', timeout: 10000 })
    await this.nextButton.click()
    await this.page.waitForTimeout(1000) // Wait for step transition
  }

  /**
   * Click back button
   */
  async clickBack(): Promise<void> {
    await this.backButton.waitFor({ state: 'visible', timeout: 10000 })
    await this.backButton.click()
    await this.page.waitForTimeout(1000) // Wait for step transition
  }

  /**
   * Click activate button
   */
  async clickActivate(): Promise<void> {
    await this.activateButton.waitFor({ state: 'visible', timeout: 10000 })
    await this.activateButton.click()
  }

  /**
   * Get current wizard step
   */
  async getCurrentStep(): Promise<string | null> {
    const step = this.wizardStep.first()
    if (await step.count() > 0) {
      return await step.textContent()
    }
    return null
  }

  /**
   * Get error message
   */
  async getErrorMessage(): Promise<string | null> {
    const errorExists = await this.errorAlert.count() > 0
    if (!errorExists) {
      return null
    }

    await this.errorAlert.waitFor({ state: 'visible', timeout: 5000 })
    return await this.errorAlert.textContent()
  }

  /**
   * Get field error message
   */
  async getFieldError(fieldName: string): Promise<string | null> {
    const field = this.page.locator(`input[name="${fieldName}"], textarea[name="${fieldName}"]`)
    const errorId = await field.getAttribute('aria-describedby')

    if (!errorId) {
      return null
    }

    const errorElement = this.page.locator(`#${errorId}`)
    if (await errorElement.count() > 0) {
      return await errorElement.textContent()
    }

    return null
  }

  /**
   * Check if file is uploaded
   */
  async isFileUploaded(): Promise<boolean> {
    return (await this.uploadedFileInfo.count()) > 0 && await this.uploadedFileInfo.isVisible()
  }

  /**
   * Check if upload is in progress
   */
  async isUploading(): Promise<boolean> {
    return (await this.uploadProgress.count()) > 0 && await this.uploadProgress.isVisible()
  }

  /**
   * Complete data-first onboarding flow
   */
  async completeDataFirstFlow(options: {
    name: string
    description?: string
    domain?: string
    filePath: string
  }): Promise<void> {
    // Step 1: Basic Information
    await this.fillName(options.name)
    if (options.description) {
      await this.fillDescription(options.description)
    }
    if (options.domain) {
      await this.selectDomain(options.domain)
    }
    await this.selectOnboardingMode('data-first')
    await this.clickNext()

    // Step 2: File Upload
    await this.uploadFile(options.filePath)
    // Wait for upload and analysis to complete
    await this.page.waitForTimeout(5000)
    await this.clickNext()

    // Step 3: Activation (if shown)
    const currentStep = await this.getCurrentStep()
    if (currentStep?.toLowerCase().includes('activate') || currentStep?.toLowerCase().includes('review')) {
      await this.clickActivate()
    }
  }

  /**
   * Complete contract-first onboarding flow
   */
  async completeContractFirstFlow(options: {
    name: string
    description?: string
    domain?: string
    contractName: string
    contractJson?: string
    contractFilePath?: string
    filePath?: string
  }): Promise<void> {
    // Step 1: Basic Information
    await this.fillName(options.name)
    if (options.description) {
      await this.fillDescription(options.description)
    }
    if (options.domain) {
      await this.selectDomain(options.domain)
    }
    await this.selectOnboardingMode('contract-first')
    await this.clickNext()

    // Step 2: Contract Creation/Upload
    if (options.contractFilePath) {
      await this.switchToContractUploadTab()
      await this.uploadContractFile(options.contractFilePath)
    } else {
      await this.switchToContractCreateTab()
      await this.fillContractName(options.contractName)
      if (options.contractJson) {
        await this.fillContractJson(options.contractJson)
      }
      // Click create contract button (implementation specific)
      const createButton = this.page.locator('button:has-text("Create Contract"), button:has-text("Create")')
      if (await createButton.count() > 0) {
        await createButton.click()
        await this.page.waitForTimeout(2000)
      }
    }
    await this.clickNext()

    // Step 3: Dataset Attachment (if file provided)
    if (options.filePath) {
      await this.uploadFile(options.filePath)
      await this.page.waitForTimeout(5000)
      await this.clickNext()
    }

    // Step 4: Activation
    const currentStep = await this.getCurrentStep()
    if (currentStep?.toLowerCase().includes('activate') || currentStep?.toLowerCase().includes('review')) {
      await this.clickActivate()
    }
  }

  /**
   * Assert page is loaded correctly
   */
  async assertPageLoaded(): Promise<void> {
    await this.assertVisible('input[name="name"], input[placeholder*="name" i]')
  }

  /**
   * Assert error message is displayed
   */
  async assertErrorMessage(expectedMessage?: string | RegExp): Promise<void> {
    await this.assertVisible('[role="alert"], .alert, [class*="error"]')

    if (expectedMessage) {
      const errorText = await this.getErrorMessage()
      expect(errorText).toMatch(expectedMessage)
    }
  }

  /**
   * Assert field error
   */
  async assertFieldError(fieldName: string, expectedError?: string | RegExp): Promise<void> {
    const error = await this.getFieldError(fieldName)
    expect(error).not.toBeNull()

    if (expectedError) {
      expect(error).toMatch(expectedError)
    }
  }
}

