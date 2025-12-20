/**
 * Dataset Upload Page Object Model
 *
 * Page Object Model for the dataset upload page.
 * Encapsulates all dataset upload page interactions and assertions.
 *
 * Uses real implementations - no mocks/stubs. Always fixes root cause.
 */

import { Page, Locator, expect } from '@playwright/test'
import { BasePage } from '../utils/page-objects'

/**
 * Dataset Upload Page Object
 */
export class DatasetUploadPage extends BasePage {
  // Locators - Header
  readonly pageTitle: Locator
  readonly pageSubtitle: Locator
  readonly backButton: Locator

  // Locators - File Upload Zone
  readonly fileUploadZone: Locator
  readonly fileUploadInput: Locator
  readonly dragDropText: Locator
  readonly browseText: Locator
  readonly acceptedTypesText: Locator
  readonly maxSizeText: Locator

  // Locators - Upload Progress
  readonly uploadProgress: Locator
  readonly progressBar: Locator
  readonly progressValue: Locator

  // Locators - Uploaded File Info
  readonly uploadedFileInfo: Locator
  readonly uploadedFileName: Locator
  readonly uploadedFileSize: Locator
  readonly uploadedFileType: Locator
  readonly removeFileButton: Locator

  // Locators - Success State
  readonly successMessage: Locator
  readonly successIcon: Locator
  readonly viewDatasetButton: Locator
  readonly uploadAnotherButton: Locator

  // Locators - Error State
  readonly errorAlert: Locator
  readonly errorMessage: Locator
  readonly retryButton: Locator

  // Locators - Info Section
  readonly infoSection: Locator

  constructor(page: Page) {
    super(page, '/datasets/new')

    // Header
    this.pageTitle = page.locator('h1, h2, h3, h4:has-text("Upload Dataset")')
    this.pageSubtitle = page.locator('p, span:has-text("Upload a dataset file")')
    this.backButton = page.locator('button:has-text("Back to Datasets"), button:has-text("Back")')

    // File Upload Zone
    this.fileUploadZone = page.locator('[class*="file-upload"], [data-testid="file-upload"], [role="button"]:has-text("Drag and drop")')
    this.fileUploadInput = page.locator('input[type="file"]')
    this.dragDropText = page.locator('text="Drag and drop a file here", text=/drag.*drop/i')
    this.browseText = page.locator('text="click to browse", text=/click.*browse/i')
    this.acceptedTypesText = page.locator('text=/Accepted:/i, text=/Accepted types/i')
    this.maxSizeText = page.locator('text=/Max size:/i, text=/Maximum size/i')

    // Upload Progress
    this.uploadProgress = page.locator('[role="progressbar"], [class*="progress"], [data-testid="upload-progress"]')
    this.progressBar = page.locator('[class*="progress-bar"], [class*="ProgressBar"]')
    this.progressValue = page.locator('[class*="progress-value"], text=/\\d+%/i')

    // Uploaded File Info
    this.uploadedFileInfo = page.locator('[class*="file-info"], [data-testid="uploaded-file"]')
    this.uploadedFileName = page.locator('[class*="file-name"], [class*="subtitle1"]:has-text(".")')
    this.uploadedFileSize = page.locator('text=/\\d+\\s+(Bytes|KB|MB|GB)/i')
    this.uploadedFileType = page.locator('text=/CSV|JSON|Parquet|text\\/csv|application\\/json/i')
    this.removeFileButton = page.locator('button:has-text("Remove"), button[aria-label*="Remove" i]')

    // Success State
    this.successMessage = page.locator('text="Dataset Uploaded Successfully", text=/uploaded.*successfully/i')
    this.successIcon = page.locator('[class*="success"], [data-testid="success-icon"]')
    this.viewDatasetButton = page.locator('button:has-text("View Dataset"), button:has-text("View")')
    this.uploadAnotherButton = page.locator('button:has-text("Upload Another")')

    // Error State
    this.errorAlert = page.locator('[role="alert"], .alert, [class*="error"]')
    this.errorMessage = page.locator('[role="alert"] text, .alert text, [class*="error"] text')
    this.retryButton = page.locator('button:has-text("Retry"), button[aria-label*="Retry" i]')

    // Info Section
    this.infoSection = page.locator('text="What happens after upload", [class*="info"]')
  }

  /**
   * Navigate to dataset upload page
   */
  async goto(): Promise<void> {
    await super.goto({ waitUntil: 'networkidle' })
    await this.waitForPageLoad()
  }

  /**
   * Wait for dataset upload page to be fully loaded
   */
  async waitForPageLoad(): Promise<void> {
    await this.waitForVisible('input[type="file"], [class*="file-upload"]', { timeout: 10000 })
  }

  /**
   * Upload file via file picker
   */
  async uploadFileViaPicker(filePath: string): Promise<void> {
    await this.fileUploadInput.waitFor({ state: 'attached', timeout: 10000 })
    await this.fileUploadInput.setInputFiles(filePath)

    // Wait for upload to start
    await this.page.waitForTimeout(1000)
  }

  /**
   * Upload file via drag-and-drop
   *
   * Note: Playwright doesn't support native file drag-and-drop from the file system.
   * We simulate it by:
   * 1. Creating a DataTransfer object with the file
   * 2. Dispatching drag events (dragover, drop)
   * 3. The component's handleDrop will process the file
   */
  async uploadFileViaDragDrop(filePath: string): Promise<void> {
    // Read file using Node.js fs
    const fs = require('fs')
    const path = require('path')
    const fileContent = fs.readFileSync(filePath)
    const fileName = path.basename(filePath)
    const fileSize = fileContent.length

    // Get MIME type from extension
    const ext = path.extname(fileName).toLowerCase()
    const mimeTypes: Record<string, string> = {
      '.csv': 'text/csv',
      '.json': 'application/json',
      '.parquet': 'application/parquet',
    }
    const mimeType = mimeTypes[ext] || 'application/octet-stream'

    // Create DataTransfer object with file
    await this.page.evaluate(
      ({ content, name, size, type }) => {
        // Create a File object
        const file = new File([new Uint8Array(content)], name, { type })

        // Create DataTransfer
        const dataTransfer = new DataTransfer()
        dataTransfer.items.add(file)

        // Get the file upload zone
        const uploadZone = document.querySelector('[class*="file-upload"], [data-testid="file-upload"]') as HTMLElement
        if (uploadZone) {
          // Dispatch dragover event
          const dragOverEvent = new DragEvent('dragover', {
            bubbles: true,
            cancelable: true,
            dataTransfer,
          })
          uploadZone.dispatchEvent(dragOverEvent)

          // Dispatch drop event
          const dropEvent = new DragEvent('drop', {
            bubbles: true,
            cancelable: true,
            dataTransfer,
          })
          uploadZone.dispatchEvent(dropEvent)
        }
      },
      {
        content: Array.from(fileContent),
        name: fileName,
        size: fileSize,
        type: mimeType,
      }
    )

    // Wait for upload to start
    await this.page.waitForTimeout(1000)
  }

  /**
   * Click on upload zone to trigger file picker
   */
  async clickUploadZone(): Promise<void> {
    await this.fileUploadZone.waitFor({ state: 'visible', timeout: 10000 })
    await this.fileUploadZone.click()
  }

  /**
   * Get upload progress percentage
   */
  async getUploadProgress(): Promise<number | null> {
    if (await this.progressValue.count() > 0) {
      const text = await this.progressValue.textContent()
      if (text) {
        const match = text.match(/(\d+)%/)
        if (match) {
          return parseInt(match[1], 10)
        }
      }
    }
    return null
  }

  /**
   * Wait for upload to complete
   */
  async waitForUploadComplete(timeout: number = 60000): Promise<void> {
    await this.page.waitForFunction(
      () => {
        const progress = document.querySelector('[role="progressbar"]')
        if (!progress) return false
        const value = progress.getAttribute('aria-valuenow') || progress.getAttribute('value')
        return value === '100' || value === '100%'
      },
      { timeout }
    )
  }

  /**
   * Get uploaded file name
   */
  async getUploadedFileName(): Promise<string | null> {
    if (await this.uploadedFileName.count() > 0) {
      return await this.uploadedFileName.textContent()
    }
    return null
  }

  /**
   * Get uploaded file size
   */
  async getUploadedFileSize(): Promise<string | null> {
    if (await this.uploadedFileSize.count() > 0) {
      return await this.uploadedFileSize.textContent()
    }
    return null
  }

  /**
   * Get uploaded file type
   */
  async getUploadedFileType(): Promise<string | null> {
    if (await this.uploadedFileType.count() > 0) {
      return await this.uploadedFileType.textContent()
    }
    return null
  }

  /**
   * Get error message
   */
  async getErrorMessage(): Promise<string | null> {
    if (await this.errorAlert.count() > 0) {
      await this.errorAlert.waitFor({ state: 'visible', timeout: 5000 })
      return await this.errorAlert.textContent()
    }
    return null
  }

  /**
   * Check if upload is in progress
   */
  async isUploading(): Promise<boolean> {
    return (await this.uploadProgress.count()) > 0 && await this.uploadProgress.isVisible()
  }

  /**
   * Check if upload is complete
   */
  async isUploadComplete(): Promise<boolean> {
    return (await this.successMessage.count()) > 0 && await this.successMessage.isVisible()
  }

  /**
   * Check if file info is displayed
   */
  async isFileInfoDisplayed(): Promise<boolean> {
    return (await this.uploadedFileInfo.count()) > 0 && await this.uploadedFileInfo.isVisible()
  }

  /**
   * Remove uploaded file
   */
  async removeFile(): Promise<void> {
    await this.removeFileButton.waitFor({ state: 'visible', timeout: 10000 })
    await this.removeFileButton.click()
    await this.page.waitForTimeout(500)
  }

  /**
   * Click retry button
   */
  async clickRetry(): Promise<void> {
    await this.retryButton.waitFor({ state: 'visible', timeout: 10000 })
    await this.retryButton.click()
    await this.page.waitForTimeout(1000)
  }

  /**
   * Click view dataset button
   */
  async clickViewDataset(): Promise<void> {
    await this.viewDatasetButton.waitFor({ state: 'visible', timeout: 10000 })
    await this.viewDatasetButton.click()
    await this.page.waitForURL(/.*datasets\/.*/, { timeout: 15000 })
  }

  /**
   * Click upload another button
   */
  async clickUploadAnother(): Promise<void> {
    await this.uploadAnotherButton.waitFor({ state: 'visible', timeout: 10000 })
    await this.uploadAnotherButton.click()
    await this.page.waitForTimeout(1000)
  }

  /**
   * Check if drag-and-drop zone is visible
   */
  async isDragDropZoneVisible(): Promise<boolean> {
    return (await this.fileUploadZone.count()) > 0 && await this.fileUploadZone.isVisible()
  }

  /**
   * Check if drag-and-drop zone is in dragging state
   */
  async isDragging(): Promise<boolean> {
    // Check for dragging visual state (background color, border color, etc.)
    const zone = this.fileUploadZone
    if (await zone.count() > 0) {
      const bgColor = await zone.evaluate((el) => {
        return window.getComputedStyle(el).backgroundColor
      })
      // Dragging state typically has a different background color
      return bgColor !== 'rgba(0, 0, 0, 0)' && bgColor !== 'transparent'
    }
    return false
  }

  /**
   * Assert page is loaded correctly
   */
  async assertPageLoaded(): Promise<void> {
    await this.assertVisible('input[type="file"], [class*="file-upload"]')
    await this.assertText('h1, h2, h3, h4', /Upload Dataset/i)
  }

  /**
   * Assert file upload zone is visible
   */
  async assertUploadZoneVisible(): Promise<void> {
    await this.assertVisible('[class*="file-upload"], [data-testid="file-upload"]')
  }

  /**
   * Assert upload progress is displayed
   */
  async assertUploadProgress(): Promise<void> {
    await this.assertVisible('[role="progressbar"], [class*="progress"]')
  }

  /**
   * Assert file info is displayed
   */
  async assertFileInfoDisplayed(): Promise<void> {
    await this.assertVisible('[class*="file-info"], [data-testid="uploaded-file"]')
  }

  /**
   * Assert file info contains name, size, and type
   */
  async assertFileInfoComplete(): Promise<void> {
    const name = await this.getUploadedFileName()
    const size = await this.getUploadedFileSize()
    const type = await this.getUploadedFileType()

    expect(name).not.toBeNull()
    expect(size).not.toBeNull()
    expect(type).not.toBeNull()
  }

  /**
   * Assert upload success
   */
  async assertUploadSuccess(): Promise<void> {
    await this.assertVisible('text="Dataset Uploaded Successfully", text=/uploaded.*successfully/i')
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
   * Assert file validation error
   */
  async assertFileValidationError(expectedError?: string | RegExp): Promise<void> {
    await this.assertErrorMessage(expectedError || /file type|file size|format|invalid/i)
  }
}

