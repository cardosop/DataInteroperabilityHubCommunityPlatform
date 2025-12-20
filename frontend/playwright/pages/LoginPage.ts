/**
 * Login Page Object Model
 *
 * Page Object Model for the login page.
 * Encapsulates all login page interactions and assertions.
 *
 * Uses real implementations - no mocks/stubs. Always fixes root cause.
 */

import { Locator, Page, expect } from '@playwright/test'
import { BasePage } from '../utils/page-objects'

/**
 * Login Page Object
 */
export class LoginPage extends BasePage {
  // Locators
  readonly emailInput: Locator
  readonly passwordInput: Locator
  readonly rememberMeCheckbox: Locator
  readonly rememberMeLabel: Locator
  readonly submitButton: Locator
  readonly forgotPasswordLink: Locator
  readonly signUpLink: Locator
  readonly errorAlert: Locator
  readonly pageTitle: Locator
  readonly pageSubtitle: Locator

  constructor(page: Page) {
    super(page, '/auth/login')

    // Initialize locators - use more flexible selectors
    this.emailInput = page.locator(
      'input[type="email"], input[name="email"], input[autocomplete="email"]'
    )
    this.passwordInput = page.locator(
      'input[type="password"], input[name="password"], input[autocomplete="current-password"]'
    )
    this.rememberMeCheckbox = page.locator(
      'input[type="checkbox"][id="remember_me"], input[type="checkbox"][name="remember_me"]'
    )
    this.rememberMeLabel = page.locator('label[for="remember_me"]')
    this.submitButton = page.locator(
      'button[type="submit"]:has-text("Sign In"), button:has-text("Signing in")'
    )
    this.forgotPasswordLink = page.locator(
      'a[href*="password-reset"], a:has-text("Forgot password")'
    )
    this.signUpLink = page.locator('a[href*="register"], a:has-text("Sign up")')
    this.errorAlert = page.locator('[role="alert"], .alert, [class*="error"]')
    this.pageTitle = page.locator('h1, h2, h3, h4:has-text("Sign In")')
    this.pageSubtitle = page.locator('p, span:has-text("Enter your credentials")')
  }

  /**
   * Navigate to login page
   */
  async goto(options?: {
    redirectTo?: string
    waitUntil?: 'load' | 'domcontentloaded' | 'networkidle' | 'commit'
    timeout?: number
  }): Promise<void> {
    const url = options?.redirectTo
      ? `/auth/login?redirect=${encodeURIComponent(options.redirectTo)}`
      : '/auth/login'

    // Collect console errors and page errors BEFORE navigation
    const consoleErrors: string[] = []
    const pageErrors: string[] = []

    this.page.on('console', msg => {
      if (msg.type() === 'error') {
        consoleErrors.push(msg.text())
      }
    })

    this.page.on('pageerror', error => {
      pageErrors.push(error.message)
    })

    // Navigate to the page
    const response = await this.page.goto(url, {
      waitUntil: options?.waitUntil || 'domcontentloaded',
      timeout: options?.timeout || 30000,
    })

    // Check if navigation was successful
    if (!response || !response.ok()) {
      throw new Error(
        `Failed to navigate to ${url}: ${response?.status()} ${response?.statusText()}`
      )
    }

    // Wait for page to be fully loaded
    await this.page.waitForLoadState('domcontentloaded', { timeout: 30000 })

    // Check if page is still open
    if (this.page.isClosed()) {
      throw new Error(`Page was closed during navigation to ${url}`)
    }

    // Wait for React to mount - check for root element to be populated
    // Use a longer timeout and better error handling
    try {
      await this.page.waitForFunction(
        () => {
          const root = document.getElementById('root')
          return root && root.children.length > 0
        },
        { timeout: 30000 }
      )
    } catch (error) {
      // If React doesn't mount, check what's on the page
      // But first check if page is still open
      let html = ''
      let bodyText = ''
      let rootContent = ''
      let currentUrl = ''

      try {
        if (!this.page.isClosed()) {
          html = await this.page.content()
          bodyText = (await this.page.textContent('body')) || ''
          rootContent = (await this.page.textContent('#root')) || ''
          currentUrl = this.page.url()
        }
      } catch (e) {
        // Page might be closed, ignore
      }

      throw new Error(
        `React failed to mount after 30s. ` +
          `Console errors: ${consoleErrors.length > 0 ? consoleErrors.join(', ') : 'none'}. ` +
          `Page errors: ${pageErrors.length > 0 ? pageErrors.join(', ') : 'none'}. ` +
          `Root content: ${rootContent || 'empty'}. ` +
          `Body text: ${bodyText?.substring(0, 200) || 'empty'}. ` +
          `HTML length: ${html.length}. ` +
          `URL: ${this.page.isClosed() ? 'page closed' : currentUrl}. ` +
          `Original error: ${error}`
      )
    }

    // Give React time to hydrate and render
    await this.page.waitForTimeout(1000)

    await this.waitForPageLoad()
  }

  /**
   * Wait for login page to be fully loaded
   */
  async waitForPageLoad(): Promise<void> {
    // Wait for React to hydrate - check for any React-rendered content
    // First, wait for the page to have some content
    await this.page.waitForFunction(() => document.body && document.body.children.length > 0, {
      timeout: 15000,
    })

    // Wait for email input - try multiple selectors with longer timeout
    const emailFound = await Promise.race([
      this.page
        .waitForSelector('input[type="email"]', { timeout: 15000, state: 'visible' })
        .then(() => true),
      this.page
        .waitForSelector('input[name="email"]', { timeout: 15000, state: 'visible' })
        .then(() => true),
      this.page.waitForSelector('label:has-text("Email")', { timeout: 15000 }).then(() => true),
    ]).catch(() => false)

    if (!emailFound) {
      // Debug: log what's actually on the page
      const bodyText = await this.page.textContent('body')
      const html = await this.page.content()
      throw new Error(
        `Email input not found. Page content: ${bodyText?.substring(0, 200)}... HTML length: ${html.length}`
      )
    }

    // Wait for password input
    const passwordFound = await Promise.race([
      this.page
        .waitForSelector('input[type="password"]', { timeout: 15000, state: 'visible' })
        .then(() => true),
      this.page
        .waitForSelector('input[name="password"]', { timeout: 15000, state: 'visible' })
        .then(() => true),
    ]).catch(() => false)

    if (!passwordFound) {
      throw new Error('Password input not found')
    }

    // Wait for submit button
    const submitFound = await Promise.race([
      this.page
        .waitForSelector('button[type="submit"]', { timeout: 15000, state: 'visible' })
        .then(() => true),
      this.page
        .waitForSelector('button:has-text("Sign In")', { timeout: 15000, state: 'visible' })
        .then(() => true),
      this.page
        .waitForSelector('button:has-text("Signing in")', { timeout: 15000, state: 'visible' })
        .then(() => true),
    ]).catch(() => false)

    if (!submitFound) {
      throw new Error('Submit button not found')
    }
  }

  /**
   * Fill email field
   */
  async fillEmail(email: string): Promise<void> {
    await this.emailInput.waitFor({ state: 'visible', timeout: 10000 })
    await this.emailInput.fill(email)
  }

  /**
   * Fill password field
   */
  async fillPassword(password: string): Promise<void> {
    await this.passwordInput.waitFor({ state: 'visible', timeout: 10000 })
    await this.passwordInput.fill(password)
  }

  /**
   * Check "Remember me" checkbox
   */
  async checkRememberMe(): Promise<void> {
    await this.rememberMeCheckbox.waitFor({ state: 'visible', timeout: 10000 })
    if (!(await this.rememberMeCheckbox.isChecked())) {
      await this.rememberMeCheckbox.check()
    }
  }

  /**
   * Uncheck "Remember me" checkbox
   */
  async uncheckRememberMe(): Promise<void> {
    await this.rememberMeCheckbox.waitFor({ state: 'visible', timeout: 10000 })
    if (await this.rememberMeCheckbox.isChecked()) {
      await this.rememberMeCheckbox.uncheck()
    }
  }

  /**
   * Check if "Remember me" is checked
   */
  async isRememberMeChecked(): Promise<boolean> {
    await this.rememberMeCheckbox.waitFor({ state: 'attached', timeout: 10000 })
    return await this.rememberMeCheckbox.isChecked()
  }

  /**
   * Get password input type (to check if password is visible)
   * Note: This tests the current implementation. If password visibility toggle
   * is not implemented, this will always return "password"
   */
  async getPasswordInputType(): Promise<string> {
    await this.passwordInput.waitFor({ state: 'attached', timeout: 10000 })
    return (await this.passwordInput.getAttribute('type')) || 'password'
  }

  /**
   * Toggle password visibility (if toggle button exists)
   * Note: This is a placeholder for when password visibility toggle is implemented
   */
  async togglePasswordVisibility(): Promise<void> {
    // Look for password visibility toggle button
    const toggleButton = this.page.locator(
      'button[aria-label*="password"], button[aria-label*="show"], button[aria-label*="hide"]'
    )
    const exists = (await toggleButton.count()) > 0

    if (exists) {
      await toggleButton.click()
    } else {
      // If toggle doesn't exist, we can't test it
      // This is expected if the feature isn't implemented yet
      throw new Error('Password visibility toggle not found. Feature may not be implemented.')
    }
  }

  /**
   * Check if password visibility toggle exists
   */
  async hasPasswordVisibilityToggle(): Promise<boolean> {
    const toggleButton = this.page.locator(
      'button[aria-label*="password"], button[aria-label*="show"], button[aria-label*="hide"]'
    )
    return (await toggleButton.count()) > 0
  }

  /**
   * Submit login form
   */
  async submitForm(options?: { waitForNavigation?: boolean; redirectTo?: string }): Promise<void> {
    const { waitForNavigation = true, redirectTo } = options || {}

    if (waitForNavigation) {
      const targetUrl = redirectTo || '/'
      await Promise.all([
        this.page.waitForURL(new RegExp(targetUrl.replace(/\//g, '\\/')), { timeout: 15000 }),
        this.submitButton.click(),
      ])
    } else {
      await this.submitButton.click()
    }
  }

  /**
   * Perform complete login flow
   */
  async login(
    email: string,
    password: string,
    options?: {
      rememberMe?: boolean
      waitForNavigation?: boolean
      redirectTo?: string
    }
  ): Promise<void> {
    await this.fillEmail(email)
    await this.fillPassword(password)

    if (options?.rememberMe) {
      await this.checkRememberMe()
    }

    await this.submitForm({
      waitForNavigation: options?.waitForNavigation,
      redirectTo: options?.redirectTo,
    })
  }

  /**
   * Get error message text
   */
  async getErrorMessage(): Promise<string | null> {
    const errorExists = (await this.errorAlert.count()) > 0
    if (!errorExists) {
      return null
    }

    await this.errorAlert.waitFor({ state: 'visible', timeout: 5000 })
    return await this.errorAlert.textContent()
  }

  /**
   * Check if error message is displayed
   */
  async hasErrorMessage(): Promise<boolean> {
    return (await this.errorAlert.count()) > 0 && (await this.errorAlert.isVisible())
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
    if ((await errorElement.count()) > 0) {
      return await errorElement.textContent()
    }

    return null
  }

  /**
   * Get password field error message
   */
  async getPasswordError(): Promise<string | null> {
    const passwordField = this.passwordInput
    const errorId = await passwordField.getAttribute('aria-describedby')

    if (!errorId) {
      return null
    }

    const errorElement = this.page.locator(`#${errorId}`)
    if ((await errorElement.count()) > 0) {
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
    return (await this.submitButton.textContent()) || ''
  }

  /**
   * Check if form is in loading/submitting state
   */
  async isSubmitting(): Promise<boolean> {
    const buttonText = await this.getSubmitButtonText()
    return buttonText.includes('Signing in') || buttonText.includes('Loading')
  }

  /**
   * Clear all form fields
   */
  async clearForm(): Promise<void> {
    await this.emailInput.clear()
    await this.passwordInput.clear()
    await this.uncheckRememberMe()
  }

  /**
   * Click forgot password link
   */
  async clickForgotPassword(): Promise<void> {
    await this.forgotPasswordLink.click()
    await this.page.waitForURL(/.*password-reset.*/, { timeout: 10000 })
  }

  /**
   * Click sign up link
   */
  async clickSignUp(): Promise<void> {
    await this.signUpLink.click()
    await this.page.waitForURL(/.*register.*/, { timeout: 10000 })
  }

  /**
   * Assert page is loaded correctly
   */
  async assertPageLoaded(): Promise<void> {
    await this.assertVisible('input[type="email"]')
    await this.assertVisible('input[type="password"]')
    await this.assertVisible('button[type="submit"]')
    await this.assertText('h1, h2, h3, h4', /Sign In/i)
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

  /**
   * Assert password field error
   */
  async assertPasswordError(expectedError?: string | RegExp): Promise<void> {
    const error = await this.getPasswordError()
    expect(error).not.toBeNull()

    if (expectedError) {
      expect(error).toMatch(expectedError)
    }
  }

  /**
   * Assert successful login (redirected away from login page)
   */
  async assertLoginSuccess(expectedRedirect?: string): Promise<void> {
    const currentUrl = this.getUrl()
    expect(currentUrl).not.toContain('/login')

    if (expectedRedirect) {
      expect(currentUrl).toContain(expectedRedirect)
    }

    // Check that auth token is set
    const hasToken = await this.page.evaluate(() => {
      return localStorage.getItem('auth_access_token') !== null
    })
    expect(hasToken).toBe(true)
  }

  /**
   * Assert login failed (still on login page)
   */
  async assertLoginFailed(): Promise<void> {
    const currentUrl = this.getUrl()
    expect(currentUrl).toContain('/login')

    // Check that auth token is not set
    const hasToken = await this.page.evaluate(() => {
      return localStorage.getItem('auth_access_token') !== null
    })
    expect(hasToken).toBe(false)
  }
}
