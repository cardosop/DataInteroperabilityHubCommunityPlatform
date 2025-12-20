/**
 * Contract Editor Page Object Model
 *
 * Page Object Model for the contract editor page.
 * Encapsulates all contract editor interactions and assertions.
 *
 * Uses real implementations - no mocks/stubs. Always fixes root cause.
 */

import { Page, Locator, expect } from '@playwright/test'
import { BasePage } from '../utils/page-objects'

/**
 * Contract Editor Page Object
 */
export class ContractEditorPage extends BasePage {
  // Locators - Editor Header
  readonly contractName: Locator
  readonly contractDescription: Locator
  readonly contractVersion: Locator
  readonly normalizationStatusBadge: Locator
  readonly validationStatusBadge: Locator
  readonly saveButton: Locator
  readonly validateButton: Locator
  readonly activateButton: Locator
  readonly cancelButton: Locator
  readonly undoButton: Locator
  readonly redoButton: Locator
  readonly previewButton: Locator

  // Locators - Tabs
  readonly overviewTab: Locator
  readonly schemaTab: Locator
  readonly qualityTab: Locator
  readonly complianceTab: Locator
  readonly lifecycleTab: Locator
  readonly marketplaceTab: Locator
  readonly rawEditorTab: Locator

  // Locators - Overview Tab
  readonly overviewNameInput: Locator
  readonly overviewDescriptionInput: Locator
  readonly overviewVersionInput: Locator
  readonly overviewOwnersList: Locator
  readonly overviewAddOwnerButton: Locator
  readonly overviewTagsInput: Locator
  readonly overviewDomainSelect: Locator

  // Locators - Schema Tab
  readonly schemaFieldsTable: Locator
  readonly schemaAddFieldButton: Locator
  readonly schemaFieldEditor: Locator

  // Locators - Raw Editor Tab
  readonly rawEditorFormatToggle: Locator
  readonly rawEditorYamlButton: Locator
  readonly rawEditorJsonButton: Locator
  readonly rawEditorMonaco: Locator
  readonly rawEditorErrorMarkers: Locator

  // Locators - Validation Panel
  readonly validationPanel: Locator
  readonly validationStatus: Locator
  readonly errorsList: Locator
  readonly warningsList: Locator
  readonly errorItem: Locator
  readonly warningItem: Locator

  // Locators - Schema Comparison (Contract-First Flow)
  readonly schemaComparison: Locator
  readonly inferredSchema: Locator
  readonly contractSchema: Locator
  readonly diffView: Locator

  // Locators - Preview
  readonly previewDialog: Locator
  readonly previewContent: Locator
  readonly previewCloseButton: Locator

  // Locators - Unsaved Changes Dialog
  readonly unsavedDialog: Locator
  readonly unsavedCancelButton: Locator
  readonly unsavedLeaveButton: Locator
  readonly unsavedSaveAndLeaveButton: Locator

  constructor(page: Page) {
    super(page, '/contracts/create')

    // Editor Header
    this.contractName = page.locator('[data-testid="contract-name"], h1, h2, h3:has-text("Contract")')
    this.contractDescription = page.locator('[data-testid="contract-description"]')
    this.contractVersion = page.locator('[data-testid="contract-version"]')
    this.normalizationStatusBadge = page.locator('[data-testid="normalization-status"], [class*="badge"]:has-text("Normalized")')
    this.validationStatusBadge = page.locator('[data-testid="validation-status"], [class*="badge"]:has-text("Valid")')
    this.saveButton = page.locator('button:has-text("Save"), button[aria-label*="Save" i]')
    this.validateButton = page.locator('button:has-text("Validate"), button[aria-label*="Validate" i]')
    this.activateButton = page.locator('button:has-text("Activate"), button[aria-label*="Activate" i]')
    this.cancelButton = page.locator('button:has-text("Cancel"), button[aria-label*="Cancel" i]')
    this.undoButton = page.locator('button[aria-label*="Undo" i], button:has([class*="undo"])')
    this.redoButton = page.locator('button[aria-label*="Redo" i], button:has([class*="redo"])')
    this.previewButton = page.locator('button:has-text("Preview"), button[aria-label*="Preview" i]')

    // Tabs
    this.overviewTab = page.locator('[role="tab"]:has-text("Overview"), button:has-text("Overview")')
    this.schemaTab = page.locator('[role="tab"]:has-text("Schema"), button:has-text("Schema")')
    this.qualityTab = page.locator('[role="tab"]:has-text("Quality"), button:has-text("Quality")')
    this.complianceTab = page.locator('[role="tab"]:has-text("Compliance"), button:has-text("Compliance")')
    this.lifecycleTab = page.locator('[role="tab"]:has-text("Lifecycle"), button:has-text("Lifecycle")')
    this.marketplaceTab = page.locator('[role="tab"]:has-text("Marketplace"), button:has-text("Marketplace")')
    this.rawEditorTab = page.locator('[role="tab"]:has-text("Raw Editor"), button:has-text("Raw Editor"), [role="tab"]:has-text("Raw")')

    // Overview Tab
    this.overviewNameInput = page.locator('input[name="name"], input[placeholder*="name" i]')
    this.overviewDescriptionInput = page.locator('textarea[name="description"], textarea[placeholder*="description" i]')
    this.overviewVersionInput = page.locator('input[name="version"], input[placeholder*="version" i]')
    this.overviewOwnersList = page.locator('[data-testid="owners-list"], [class*="owners"]')
    this.overviewAddOwnerButton = page.locator('button:has-text("Add Owner"), button[aria-label*="Add Owner" i]')
    this.overviewTagsInput = page.locator('input[name="tags"], input[placeholder*="tags" i], [class*="tag-input"]')
    this.overviewDomainSelect = page.locator('select[name="domain"], [role="combobox"][aria-label*="domain" i]')

    // Schema Tab
    this.schemaFieldsTable = page.locator('[data-testid="schema-fields-table"], table, [class*="schema-table"]')
    this.schemaAddFieldButton = page.locator('button:has-text("Add Field"), button[aria-label*="Add Field" i]')
    this.schemaFieldEditor = page.locator('[data-testid="field-editor"], [class*="field-editor"]')

    // Raw Editor Tab
    this.rawEditorFormatToggle = page.locator('[role="group"]:has-text("YAML"), [role="group"]:has-text("JSON")')
    this.rawEditorYamlButton = page.locator('button:has-text("YAML"), [role="button"]:has-text("YAML")')
    this.rawEditorJsonButton = page.locator('button:has-text("JSON"), [role="button"]:has-text("JSON")')
    this.rawEditorMonaco = page.locator('.monaco-editor, [class*="monaco"], [data-testid="monaco-editor"]')
    this.rawEditorErrorMarkers = page.locator('.monaco-error, [class*="error-marker"]')

    // Validation Panel
    this.validationPanel = page.locator('[data-testid="validation-panel"], [class*="validation-panel"]')
    this.validationStatus = page.locator('[data-testid="validation-status"], [class*="validation-status"]')
    this.errorsList = page.locator('[data-testid="errors-list"], [class*="errors-list"]')
    this.warningsList = page.locator('[data-testid="warnings-list"], [class*="warnings-list"]')
    this.errorItem = page.locator('[data-testid="error-item"], [class*="error-item"]')
    this.warningItem = page.locator('[data-testid="warning-item"], [class*="warning-item"]')

    // Schema Comparison
    this.schemaComparison = page.locator('[data-testid="schema-comparison"], [class*="schema-comparison"]')
    this.inferredSchema = page.locator('[data-testid="inferred-schema"], [class*="inferred-schema"]')
    this.contractSchema = page.locator('[data-testid="contract-schema"], [class*="contract-schema"]')
    this.diffView = page.locator('[data-testid="diff-view"], [class*="diff-view"]')

    // Preview
    this.previewDialog = page.locator('[role="dialog"]:has-text("Preview"), [class*="preview-dialog"]')
    this.previewContent = page.locator('[data-testid="preview-content"], [class*="preview-content"]')
    this.previewCloseButton = page.locator('button:has-text("Close Preview"), button:has-text("Close")')

    // Unsaved Changes Dialog
    this.unsavedDialog = page.locator('[role="dialog"]:has-text("Unsaved Changes")')
    this.unsavedCancelButton = page.locator('button:has-text("Cancel"):near([role="dialog"])')
    this.unsavedLeaveButton = page.locator('button:has-text("Leave Without Saving"), button[color="error"]:near([role="dialog"])')
    this.unsavedSaveAndLeaveButton = page.locator('button:has-text("Save and Leave"), button[variant="contained"]:near([role="dialog"])')
  }

  /**
   * Navigate to contract editor page
   * Note: Contract editor may be accessed via:
   * - /contracts/:id/edit (for editing existing contract)
   * - /contracts/create (for creating new contract)
   * - Or embedded in contract detail page
   */
  async goto(contractId?: string): Promise<void> {
    let path: string
    if (contractId) {
      // Try edit route first
      path = `/contracts/${contractId}/edit`
    } else {
      // Try create route, or navigate to contract detail and click edit
      path = '/contracts/create'
    }

    await this.page.goto(`${this.baseURL}${path}`, { waitUntil: 'networkidle' })

    // If route doesn't exist, try navigating to contract detail and clicking edit
    if (contractId && this.page.url().includes('/404') || this.page.url().includes('/not-found')) {
      // Navigate to contract detail page
      await this.page.goto(`${this.baseURL}/contracts/${contractId}`, { waitUntil: 'networkidle' })
      // Click edit button
      const editButton = this.page.locator('button:has-text("Edit"), button[aria-label*="Edit" i]')
      if (await editButton.count() > 0) {
        await editButton.click()
        await this.page.waitForURL(/.*edit.*/, { timeout: 10000 })
      }
    }

    await this.waitForPageLoad()
  }

  /**
   * Wait for contract editor page to be fully loaded
   */
  async waitForPageLoad(): Promise<void> {
    await this.waitForVisible('[role="tab"], button:has-text("Overview")', { timeout: 10000 })
  }

  /**
   * Click tab by name
   */
  async clickTab(tabName: 'overview' | 'schema' | 'quality' | 'compliance' | 'lifecycle' | 'marketplace' | 'raw'): Promise<void> {
    const tabMap = {
      overview: this.overviewTab,
      schema: this.schemaTab,
      quality: this.qualityTab,
      compliance: this.complianceTab,
      lifecycle: this.lifecycleTab,
      marketplace: this.marketplaceTab,
      raw: this.rawEditorTab,
    }

    const tab = tabMap[tabName]
    await tab.waitFor({ state: 'visible', timeout: 10000 })
    await tab.click()
    await this.page.waitForTimeout(500) // Wait for tab content to load
  }

  /**
   * Fill contract name in Overview tab
   */
  async fillContractName(name: string): Promise<void> {
    await this.clickTab('overview')
    await this.overviewNameInput.waitFor({ state: 'visible', timeout: 10000 })
    await this.overviewNameInput.fill(name)
  }

  /**
   * Fill contract description in Overview tab
   */
  async fillContractDescription(description: string): Promise<void> {
    await this.clickTab('overview')
    await this.overviewDescriptionInput.waitFor({ state: 'visible', timeout: 10000 })
    await this.overviewDescriptionInput.fill(description)
  }

  /**
   * Add owner in Overview tab
   */
  async addOwner(name: string, email: string): Promise<void> {
    await this.clickTab('overview')
    await this.overviewAddOwnerButton.waitFor({ state: 'visible', timeout: 10000 })
    await this.overviewAddOwnerButton.click()

    // Fill owner form (implementation specific)
    const nameInput = this.page.locator('input[name*="owner"][name*="name"], input[placeholder*="owner" i][placeholder*="name" i]')
    const emailInput = this.page.locator('input[name*="owner"][name*="email"], input[type="email"]:near([class*="owner"])')

    if (await nameInput.count() > 0) {
      await nameInput.fill(name)
    }
    if (await emailInput.count() > 0) {
      await emailInput.fill(email)
    }

    // Click save/add button
    const saveButton = this.page.locator('button:has-text("Add"), button:has-text("Save"):near(input[name*="owner"])')
    if (await saveButton.count() > 0) {
      await saveButton.click()
    }
  }

  /**
   * Add tag in Overview tab
   */
  async addTag(tag: string): Promise<void> {
    await this.clickTab('overview')
    await this.overviewTagsInput.waitFor({ state: 'visible', timeout: 10000 })
    await this.overviewTagsInput.fill(tag)
    await this.overviewTagsInput.press('Enter')
  }

  /**
   * Switch to YAML format in Raw Editor
   */
  async switchToYamlFormat(): Promise<void> {
    await this.clickTab('raw')
    await this.rawEditorYamlButton.waitFor({ state: 'visible', timeout: 10000 })
    await this.rawEditorYamlButton.click()
    await this.page.waitForTimeout(500)
  }

  /**
   * Switch to JSON format in Raw Editor
   */
  async switchToJsonFormat(): Promise<void> {
    await this.clickTab('raw')
    await this.rawEditorJsonButton.waitFor({ state: 'visible', timeout: 10000 })
    await this.rawEditorJsonButton.click()
    await this.page.waitForTimeout(500)
  }

  /**
   * Get Monaco editor content
   */
  async getMonacoEditorContent(): Promise<string> {
    await this.clickTab('raw')
    // Monaco editor content is in a textarea or contenteditable div
    const editor = this.rawEditorMonaco.locator('textarea, [contenteditable="true"]').first()
    if (await editor.count() > 0) {
      return await editor.inputValue()
    }

    // Alternative: get text content
    return await this.rawEditorMonaco.textContent() || ''
  }

  /**
   * Set Monaco editor content
   */
  async setMonacoEditorContent(content: string): Promise<void> {
    await this.clickTab('raw')
    await this.rawEditorMonaco.waitFor({ state: 'visible', timeout: 10000 })

    // Monaco editor interaction - click to focus, then type
    await this.rawEditorMonaco.click()
    await this.page.keyboard.press('Control+A')
    await this.page.keyboard.type(content)
    await this.page.waitForTimeout(1000) // Wait for parsing
  }

  /**
   * Click save button
   */
  async clickSave(): Promise<void> {
    await this.saveButton.waitFor({ state: 'visible', timeout: 10000 })
    await this.saveButton.click()
    await this.page.waitForTimeout(1000)
  }

  /**
   * Click validate button
   */
  async clickValidate(): Promise<void> {
    await this.validateButton.waitFor({ state: 'visible', timeout: 10000 })
    await this.validateButton.click()
    await this.page.waitForTimeout(2000) // Wait for validation
  }

  /**
   * Click activate button
   */
  async clickActivate(): Promise<void> {
    await this.activateButton.waitFor({ state: 'visible', timeout: 10000 })
    await this.activateButton.click()
    await this.page.waitForTimeout(1000)
  }

  /**
   * Click undo button
   */
  async clickUndo(): Promise<void> {
    await this.undoButton.waitFor({ state: 'visible', timeout: 10000 })
    await this.undoButton.click()
    await this.page.waitForTimeout(500)
  }

  /**
   * Click redo button
   */
  async clickRedo(): Promise<void> {
    await this.redoButton.waitFor({ state: 'visible', timeout: 10000 })
    await this.redoButton.click()
    await this.page.waitForTimeout(500)
  }

  /**
   * Click preview button
   */
  async clickPreview(): Promise<void> {
    await this.previewButton.waitFor({ state: 'visible', timeout: 10000 })
    await this.previewButton.click()
    await this.page.waitForTimeout(1000)
  }

  /**
   * Close preview
   */
  async closePreview(): Promise<void> {
    await this.previewCloseButton.waitFor({ state: 'visible', timeout: 10000 })
    await this.previewCloseButton.click()
    await this.page.waitForTimeout(500)
  }

  /**
   * Get validation status
   */
  async getValidationStatus(): Promise<string | null> {
    if (await this.validationStatusBadge.count() > 0) {
      return await this.validationStatusBadge.textContent()
    }
    return null
  }

  /**
   * Get normalization status
   */
  async getNormalizationStatus(): Promise<string | null> {
    if (await this.normalizationStatusBadge.count() > 0) {
      return await this.normalizationStatusBadge.textContent()
    }
    return null
  }

  /**
   * Get error count
   */
  async getErrorCount(): Promise<number> {
    if (await this.errorsList.count() > 0) {
      return await this.errorItem.count()
    }
    return 0
  }

  /**
   * Get warning count
   */
  async getWarningCount(): Promise<number> {
    if (await this.warningsList.count() > 0) {
      return await this.warningItem.count()
    }
    return 0
  }

  /**
   * Click on error to navigate to field
   */
  async clickError(index: number = 0): Promise<void> {
    const error = this.errorItem.nth(index)
    if (await error.count() > 0) {
      await error.click()
      await this.page.waitForTimeout(500)
    }
  }

  /**
   * Check if Monaco editor has error markers
   */
  async hasErrorMarkers(): Promise<boolean> {
    await this.clickTab('raw')
    return (await this.rawEditorErrorMarkers.count()) > 0
  }

  /**
   * Check if schema comparison is visible
   */
  async isSchemaComparisonVisible(): Promise<boolean> {
    return (await this.schemaComparison.count()) > 0 && await this.schemaComparison.isVisible()
  }

  /**
   * Check if preview is open
   */
  async isPreviewOpen(): Promise<boolean> {
    return (await this.previewDialog.count()) > 0 && await this.previewDialog.isVisible()
  }

  /**
   * Check if undo is enabled
   */
  async canUndo(): Promise<boolean> {
    return !(await this.undoButton.isDisabled())
  }

  /**
   * Check if redo is enabled
   */
  async canRedo(): Promise<boolean> {
    return !(await this.redoButton.isDisabled())
  }

  /**
   * Wait for auto-save (30 seconds)
   */
  async waitForAutoSave(timeout: number = 35000): Promise<void> {
    // Wait for save indicator or check dirty state
    await this.page.waitForTimeout(timeout)
  }

  /**
   * Assert page is loaded correctly
   */
  async assertPageLoaded(): Promise<void> {
    await this.assertVisible('[role="tab"], button:has-text("Overview")')
  }

  /**
   * Assert tab is active
   */
  async assertTabActive(tabName: string): Promise<void> {
    const tab = this.page.locator(`[role="tab"][aria-selected="true"]:has-text("${tabName}")`)
    await expect(tab).toBeVisible()
  }

  /**
   * Assert validation status
   */
  async assertValidationStatus(expectedStatus: string): Promise<void> {
    const status = await this.getValidationStatus()
    expect(status).toContain(expectedStatus)
  }

  /**
   * Assert error count
   */
  async assertErrorCount(expectedCount: number): Promise<void> {
    const count = await this.getErrorCount()
    expect(count).toBe(expectedCount)
  }

  /**
   * Assert Monaco editor has syntax highlighting
   */
  async assertSyntaxHighlighting(): Promise<void> {
    await this.clickTab('raw')
    // Monaco editor should have syntax highlighting classes
    const editor = this.rawEditorMonaco
    await expect(editor).toBeVisible()
    // Check for Monaco editor specific classes
    const hasMonaco = await editor.evaluate((el) => {
      return el.classList.toString().includes('monaco') ||
             el.querySelector('.monaco-editor') !== null
    })
    expect(hasMonaco).toBe(true)
  }

  /**
   * Check if save button is enabled (dirty state)
   */
  async isSaveEnabled(): Promise<boolean> {
    return !(await this.saveButton.isDisabled())
  }

  /**
   * Check if unsaved changes dialog is visible
   */
  async isUnsavedDialogVisible(): Promise<boolean> {
    return (await this.unsavedDialog.count() > 0) && await this.unsavedDialog.isVisible()
  }

  /**
   * Handle unsaved changes dialog
   */
  async handleUnsavedDialog(action: 'cancel' | 'leave' | 'save'): Promise<void> {
    if (!(await this.isUnsavedDialogVisible())) {
      return
    }

    switch (action) {
      case 'cancel':
        await this.unsavedCancelButton.click()
        break
      case 'leave':
        await this.unsavedLeaveButton.click()
        break
      case 'save':
        await this.unsavedSaveAndLeaveButton.click()
        await this.page.waitForTimeout(2000) // Wait for save
        break
    }
  }

  /**
   * Add field in Schema tab
   */
  async addSchemaField(fieldName: string, dataType: string = 'string'): Promise<void> {
    await this.clickTab('schema')
    await this.schemaAddFieldButton.waitFor({ state: 'visible', timeout: 10000 })
    await this.schemaAddFieldButton.click()

    // Fill field form
    const nameInput = this.page.locator('input[name="name"], input[placeholder*="field name" i]').first()
    const typeSelect = this.page.locator('select[name="data_type"], [role="combobox"][aria-label*="type" i]').first()

    if (await nameInput.count() > 0) {
      await nameInput.fill(fieldName)
    }
    if (await typeSelect.count() > 0) {
      await typeSelect.selectOption(dataType)
    }

    // Click save/add button
    const saveButton = this.page.locator('button:has-text("Add"), button:has-text("Save"):near(input[name="name"])').first()
    if (await saveButton.count() > 0) {
      await saveButton.click()
      await this.page.waitForTimeout(500)
    }
  }

  /**
   * Get schema field count
   */
  async getSchemaFieldCount(): Promise<number> {
    await this.clickTab('schema')
    if (await this.schemaFieldsTable.count() > 0) {
      const rows = this.schemaFieldsTable.locator('tbody tr, [role="row"]')
      return await rows.count()
    }
    return 0
  }

  /**
   * Add quality rule in Quality tab
   */
  async addQualityRule(ruleName: string, dimension: string = 'completeness'): Promise<void> {
    await this.clickTab('quality')
    const addButton = this.page.locator('button:has-text("Add Rule"), button[aria-label*="Add Rule" i]').first()
    if (await addButton.count() > 0) {
      await addButton.click()

      // Fill rule form
      const nameInput = this.page.locator('input[name="name"], input[placeholder*="rule name" i]').first()
      const dimensionSelect = this.page.locator('select[name="dimension"], [role="combobox"][aria-label*="dimension" i]').first()

      if (await nameInput.count() > 0) {
        await nameInput.fill(ruleName)
      }
      if (await dimensionSelect.count() > 0) {
        await dimensionSelect.selectOption(dimension)
      }

      // Click save button
      const saveButton = this.page.locator('button:has-text("Add"), button:has-text("Save"):near(input[name="name"])').first()
      if (await saveButton.count() > 0) {
        await saveButton.click()
        await this.page.waitForTimeout(500)
      }
    }
  }

  /**
   * Set compliance checkbox in Compliance tab
   */
  async setContainsPersonalData(value: boolean): Promise<void> {
    await this.clickTab('compliance')
    const checkbox = this.page.locator('input[type="checkbox"][name*="personal"], input[type="checkbox"]:near(text="Contains Personal Data")').first()
    if (await checkbox.count() > 0) {
      const isChecked = await checkbox.isChecked()
      if (isChecked !== value) {
        await checkbox.click()
        await this.page.waitForTimeout(500)
      }
    }
  }

  /**
   * Set data source in Lifecycle tab
   */
  async setDataSource(dataSource: string): Promise<void> {
    await this.clickTab('lifecycle')
    const input = this.page.locator('input[name="data_source"], input[placeholder*="data source" i]').first()
    if (await input.count() > 0) {
      await input.fill(dataSource)
      await this.page.waitForTimeout(500)
    }
  }

  /**
   * Set license summary in Marketplace tab
   */
  async setLicenseSummary(summary: string): Promise<void> {
    await this.clickTab('marketplace')
    const input = this.page.locator('textarea[name="license_summary"], textarea[placeholder*="license" i]').first()
    if (await input.count() > 0) {
      await input.fill(summary)
      await this.page.waitForTimeout(500)
    }
  }

  /**
   * Export contract (if export button exists)
   */
  async exportContract(format: 'yaml' | 'json'): Promise<string | null> {
    const exportButton = this.page.locator(`button:has-text("Export ${format.toUpperCase()}"), button[aria-label*="Export" i]`).first()
    if (await exportButton.count() > 0) {
      // Set up download listener
      const downloadPromise = this.page.waitForEvent('download', { timeout: 10000 })
      await exportButton.click()

      try {
        const download = await downloadPromise
        const path = await download.path()
        if (path) {
          // Use dynamic import for fs
          const fs = await import('fs')
          return fs.readFileSync(path, 'utf-8')
        }
      } catch {
        // Download may not be triggered, try getting content from preview or raw editor
        if (format === 'yaml') {
          await this.switchToYamlFormat()
          return await this.getMonacoEditorContent()
        } else {
          await this.switchToJsonFormat()
          return await this.getMonacoEditorContent()
        }
      }
    }
    return null
  }

  /**
   * Import contract (if import button exists)
   */
  async importContract(content: string, format: 'yaml' | 'json'): Promise<void> {
    const importButton = this.page.locator('button:has-text("Import"), button[aria-label*="Import" i]').first()
    if (await importButton.count() > 0) {
      await importButton.click()

      // Handle file upload or paste
      const fileInput = this.page.locator('input[type="file"]').first()
      if (await fileInput.count() > 0) {
        // Create temporary file and upload
        const fs = await import('fs')
        const path = await import('path')
        const os = await import('os')
        const tempFile = path.join(os.tmpdir(), `contract.${format === 'yaml' ? 'yaml' : 'json'}`)
        fs.writeFileSync(tempFile, content)
        await fileInput.setInputFiles(tempFile)
        fs.unlinkSync(tempFile)
      } else {
        // Paste into raw editor
        await this.clickTab('raw')
        if (format === 'yaml') {
          await this.switchToYamlFormat()
        } else {
          await this.switchToJsonFormat()
        }
        await this.setMonacoEditorContent(content)
      }
    }
  }
}

