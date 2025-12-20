/**
 * Password Reset Request Page Object Model
 *
 * Page Object Model for the password reset request page.
 * Encapsulates all password reset request page interactions and assertions.
 *
 * Uses real implementations - no mocks/stubs. Always fixes root cause.
 */

import { Page, Locator, expect } from '@playwright/test'
import { BasePage } from '../utils/page-objects'

/**
 * Password Reset Request Page Object
 */
export class PasswordResetRequestPage extends BasePage {
  // Locators
  readonly emailInput: Locator
  readonly submitButton: Locator
  readonly backToLoginLink: Locator
  readonly successAlert: Locator
  readonly errorAlert: Locator
  readonly pageTitle: Locator
  readonly pageSubtitle: Locator

  constructor(page: Page) {
    super(page, '/auth/password-reset')

    // Initialize locators
    this.emailInput = page.locator('input[type="email"], input[name="email"]')
    this.submitButton = page.locator('button[type="submit"]:has-text("Send Reset Link"), button:has-text("Sending")')
    this.backToLoginLink = page.locator('a[href*="login"], a:has-text("Back to Sign In")')
    this.successAlert = page.locator('[role="alert"]:has-text("Check your email"), .alert-success, [class*="success"]')
    this.errorAlert = page.locator('[role="alert"]:has-text("error"), .alert-error, [class*="error"]')
    this.pageTitle = page.locator('h1, h2, h3, h4:has-text("Reset Password")')
    this.pageSubtitle = page.locator('p, span:has-text("Enter your email")')
  }

  /**
   * Navigate to password reset request page
   */
  async goto(): Promise<void> {
    await super.goto({ waitUntil: 'networkidle' })
    await this.waitForPageLoad()
  }

  /**
   * Wait for password reset request page to be fully loaded
   */
  async waitForPageLoad(): Promise<void> {
    await this.waitForVisible('input[type="email"]', { timeout: 10000 })
    await this.waitForVisible('button[type="submit"]', { timeout: 10000 })
  }

  /**
   * Fill email field
   */
  async fillEmail(email: string): Promise<void> {
    await this.emailInput.waitFor({ state: 'visible', timeout: 10000 })
    await this.emailInput.fill(email)
  }

  /**
   * Submit password reset request form
   */
  async submitForm(options?: { waitForSuccess?: boolean }): Promise<void> {
    const { waitForSuccess = true } = options || {}

    if (waitForSuccess) {
      // Wait for success message to appear
      await Promise.all([
        this.successAlert.waitFor({ state: 'visible', timeout: 15000 }).catch(() => {
          // If success doesn't appear, check for error
        }),
        this.submitButton.click(),
      ])
    } else {
      await this.submitButton.click()
    }
  }

  /**
   * Perform complete password reset request flow
   */
  async requestPasswordReset(email: string): Promise<void> {
    await this.fillEmail(email)
    await this.submitForm({ waitForSuccess: true })
  }

  /**
   * Get success message text
   */
  async getSuccessMessage(): Promise<string | null> {
    const successExists = await this.successAlert.count() > 0
    if (!successExists) {
      return null
    }

    await this.successAlert.waitFor({ state: 'visible', timeout: 5000 })
    return await this.successAlert.textContent()
  }

  /**
   * Get error message text
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
   * Check if success message is displayed
   */
  async hasSuccessMessage(): Promise<boolean> {
    return (await this.successAlert.count()) > 0 && await this.successAlert.isVisible()
  }

  /**
   * Check if error message is displayed
   */
  async hasErrorMessage(): Promise<boolean> {
    return (await this.errorAlert.count()) > 0 && await this.errorAlert.isVisible()
  }

  /**
   * Get email field error message
   */
  async getEmailError(): Promise<string | null> {
    const emailField = this.emailInput
    const errorId = await emailField.getAttribute('aria-describedby')

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
   * Check if submit button is disabled
   */
  async isSubmitButtonDisabled(): Promise<boolean> {
    await this.submitButton.waitFor({ state: 'attached', timeout: 10000 })
    return await this.submitButton.isDisabled()
  }

  /**
   * Get submit button text
   */
  async getSubmitButtonText(): Promise<string> {
    await this.submitButton.waitFor({ state: 'visible', timeout: 10000 })
    return await this.submitButton.textContent() || ''
  }

  /**
   * Check if form is in loading/submitting state
   */
  async isSubmitting(): Promise<boolean> {
    const buttonText = await this.getSubmitButtonText()
    return buttonText.includes('Sending') || buttonText.includes('Loading')
  }

  /**
   * Clear form fields
   */
  async clearForm(): Promise<void> {
    await this.emailInput.clear()
  }

  /**
   * Click back to login link
   */
  async clickBackToLogin(): Promise<void> {
    await this.backToLoginLink.click()
    await this.page.waitForURL(/.*login.*/, { timeout: 10000 })
  }

  /**
   * Assert page is loaded correctly
   */
  async assertPageLoaded(): Promise<void> {
    await this.assertVisible('input[type="email"]')
    await this.assertVisible('button[type="submit"]')
    await this.assertText('h1, h2, h3, h4', /Reset Password/i)
  }

  /**
   * Assert success message is displayed
   */
  async assertSuccessMessage(expectedMessage?: string | RegExp): Promise<void> {
    await this.assertVisible('[role="alert"]:has-text("Check your email"), .alert-success')

    if (expectedMessage) {
      const message = await this.getSuccessMessage()
      expect(message).toMatch(expectedMessage)
    }
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
   * Assert email field error
   */
  async assertEmailError(expectedError?: string | RegExp): Promise<void> {
    const error = await this.getEmailError()
    expect(error).not.toBeNull()

    if (expectedError) {
      expect(error).toMatch(expectedError)
    }
  }
}

