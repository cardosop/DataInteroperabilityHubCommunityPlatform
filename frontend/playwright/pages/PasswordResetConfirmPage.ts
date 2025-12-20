/**
 * Password Reset Confirm Page Object Model
 *
 * Page Object Model for the password reset confirm page.
 * Encapsulates all password reset confirm page interactions and assertions.
 *
 * Uses real implementations - no mocks/stubs. Always fixes root cause.
 */

import { Page, Locator, expect } from '@playwright/test'
import { BasePage } from '../utils/page-objects'

/**
 * Password Reset Confirm Page Object
 */
export class PasswordResetConfirmPage extends BasePage {
  // Locators
  readonly newPasswordInput: Locator
  readonly confirmPasswordInput: Locator
  readonly submitButton: Locator
  readonly backToLoginLink: Locator
  readonly successAlert: Locator
  readonly errorAlert: Locator
  readonly pageTitle: Locator
  readonly invalidTokenAlert: Locator

  constructor(page: Page) {
    super(page, '/auth/password-reset/confirm')

    // Store baseURL for custom navigation
    this.baseURL = process.env.PLAYWRIGHT_BASE_URL || 'http://localhost:3000'

    // Initialize locators
    this.newPasswordInput = page.locator('input[type="password"][name="new_password"], input[type="password"]:first-of-type')
    this.confirmPasswordInput = page.locator('input[type="password"][name="confirm_password"], input[type="password"]:nth-of-type(2)')
    this.submitButton = page.locator('button[type="submit"]:has-text("Reset Password"), button:has-text("Resetting")')
    this.backToLoginLink = page.locator('a[href*="login"], a:has-text("Back to Sign In"), a:has-text("Go to Sign In")')
    this.successAlert = page.locator('[role="alert"]:has-text("Password Reset Successful"), .alert-success, [class*="success"]')
    this.errorAlert = page.locator('[role="alert"]:has-text("error"), .alert-error, [class*="error"]')
    this.pageTitle = page.locator('h1, h2, h3, h4:has-text("Reset Password")')
    this.invalidTokenAlert = page.locator('[role="alert"]:has-text("Invalid"), [role="alert"]:has-text("missing reset token")')
  }

  /**
   * Navigate to password reset confirm page with token
   */
  async goto(token: string): Promise<void> {
    const baseURL = process.env.PLAYWRIGHT_BASE_URL || 'http://localhost:3000'
    const url = `${baseURL}/auth/password-reset/confirm?token=${encodeURIComponent(token)}`
    await this.page.goto(url, { waitUntil: 'networkidle' })
    await this.waitForPageLoad()
  }

  /**
   * Wait for password reset confirm page to be fully loaded
   */
  async waitForPageLoad(): Promise<void> {
    // Wait for either the form or invalid token message
    await Promise.race([
      this.page.waitForSelector('input[type="password"]', { timeout: 10000 }),
      this.page.waitForSelector('[role="alert"]:has-text("Invalid"), [role="alert"]:has-text("missing")', { timeout: 10000 }),
    ])
  }

  /**
   * Fill new password field
   */
  async fillNewPassword(password: string): Promise<void> {
    await this.newPasswordInput.waitFor({ state: 'visible', timeout: 10000 })
    await this.newPasswordInput.fill(password)
  }

  /**
   * Fill confirm password field
   */
  async fillConfirmPassword(password: string): Promise<void> {
    await this.confirmPasswordInput.waitFor({ state: 'visible', timeout: 10000 })
    await this.confirmPasswordInput.fill(password)
  }

  /**
   * Submit password reset confirm form
   */
  async submitForm(options?: { waitForSuccess?: boolean; waitForNavigation?: boolean }): Promise<void> {
    const { waitForSuccess = true, waitForNavigation = true } = options || {}

    if (waitForSuccess && waitForNavigation) {
      // Wait for redirect to login page
      await Promise.all([
        this.page.waitForURL(/.*login.*/, { timeout: 15000 }),
        this.submitButton.click(),
      ])
    } else if (waitForSuccess) {
      // Wait for success message
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
   * Perform complete password reset confirm flow
   */
  async confirmPasswordReset(newPassword: string, options?: { waitForNavigation?: boolean }): Promise<void> {
    await this.fillNewPassword(newPassword)
    await this.fillConfirmPassword(newPassword)
    await this.submitForm({ waitForSuccess: true, waitForNavigation: options?.waitForNavigation })
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
   * Get invalid token message text
   */
  async getInvalidTokenMessage(): Promise<string | null> {
    const alertExists = await this.invalidTokenAlert.count() > 0
    if (!alertExists) {
      return null
    }

    await this.invalidTokenAlert.waitFor({ state: 'visible', timeout: 5000 })
    return await this.invalidTokenAlert.textContent()
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
   * Check if invalid token message is displayed
   */
  async hasInvalidTokenMessage(): Promise<boolean> {
    return (await this.invalidTokenAlert.count()) > 0 && await this.invalidTokenAlert.isVisible()
  }

  /**
   * Get new password field error message
   */
  async getNewPasswordError(): Promise<string | null> {
    const passwordField = this.newPasswordInput
    const errorId = await passwordField.getAttribute('aria-describedby')

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
   * Get confirm password field error message
   */
  async getConfirmPasswordError(): Promise<string | null> {
    const passwordField = this.confirmPasswordInput
    const errorId = await passwordField.getAttribute('aria-describedby')

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
    return buttonText.includes('Resetting') || buttonText.includes('Loading')
  }

  /**
   * Clear form fields
   */
  async clearForm(): Promise<void> {
    await this.newPasswordInput.clear()
    await this.confirmPasswordInput.clear()
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
    // Page might show form or invalid token message
    const hasForm = await this.newPasswordInput.count() > 0
    const hasInvalidToken = await this.invalidTokenAlert.count() > 0

    expect(hasForm || hasInvalidToken).toBe(true)
  }

  /**
   * Assert success message is displayed
   */
  async assertSuccessMessage(expectedMessage?: string | RegExp): Promise<void> {
    await this.assertVisible('[role="alert"]:has-text("Password Reset Successful"), .alert-success')

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
   * Assert invalid token message is displayed
   */
  async assertInvalidTokenMessage(expectedMessage?: string | RegExp): Promise<void> {
    await this.assertVisible('[role="alert"]:has-text("Invalid"), [role="alert"]:has-text("missing")')

    if (expectedMessage) {
      const message = await this.getInvalidTokenMessage()
      expect(message).toMatch(expectedMessage)
    }
  }

  /**
   * Assert password field errors
   */
  async assertPasswordErrors(): Promise<void> {
    const newPasswordError = await this.getNewPasswordError()
    const confirmPasswordError = await this.getConfirmPasswordError()

    // At least one field should have an error
    expect(newPasswordError || confirmPasswordError).not.toBeNull()
  }

  /**
   * Assert successful password reset (redirected to login)
   */
  async assertPasswordResetSuccess(): Promise<void> {
    const currentUrl = this.getUrl()
    expect(currentUrl).toMatch(/.*login.*/)

    // Check for success parameter in URL
    const url = new URL(currentUrl)
    const passwordResetParam = url.searchParams.get('password_reset')
    expect(passwordResetParam).toBe('true')
  }
}

