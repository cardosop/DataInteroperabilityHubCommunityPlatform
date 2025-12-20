/**
 * Page Object Base Class for Playwright Tests
 *
 * Base class for implementing Page Object Model pattern in E2E tests.
 * Provides common functionality and best practices for page objects.
 *
 * Uses real implementations - no mocks/stubs. Always fixes root cause.
 */

import { Page, Locator, expect } from '@playwright/test'

/**
 * Page object options
 */
export interface PageOptions {
  baseURL?: string
}

/**
 * Base page object class
 *
 * All page objects should extend this class to get common functionality.
 *
 * @example
 * ```ts
 * class LoginPage extends BasePage {
 *   constructor(page: Page) {
 *     super(page, '/auth/login')
 *   }
 *
 *   get emailInput() {
 *     return this.page.locator('input[type="email"]')
 *   }
 *
 *   async login(email: string, password: string) {
 *     await this.emailInput.fill(email)
 *     await this.passwordInput.fill(password)
 *     await this.submitButton.click()
 *   }
 * }
 * ```
 */
export abstract class BasePage {
  /**
   * Playwright page instance
   */
  protected readonly page: Page

  /**
   * Base URL path for this page
   */
  protected readonly path: string

  /**
   * Base URL from config
   */
  protected readonly baseURL: string

  /**
   * Constructor
   *
   * @param page - Playwright page instance
   * @param path - Page path (relative to base URL)
   * @param options - Additional options
   */
  constructor(page: Page, path: string = '', options: PageOptions = {}) {
    this.page = page
    this.path = path
    this.baseURL = options.baseURL || process.env.PLAYWRIGHT_BASE_URL || 'http://localhost:3000'
  }

  /**
   * Navigate to this page
   *
   * @param options - Navigation options
   *
   * @example
   * ```ts
   * await loginPage.goto()
   * await loginPage.goto({ waitUntil: 'networkidle' })
   * ```
   */
  async goto(options: {
    waitUntil?: 'load' | 'domcontentloaded' | 'networkidle' | 'commit'
    timeout?: number
  } = {}): Promise<void> {
    const url = this.path.startsWith('http') ? this.path : `${this.baseURL}${this.path}`
    await this.page.goto(url, {
      waitUntil: options.waitUntil || 'networkidle',
      timeout: options.timeout || 30000,
    })
  }

  /**
   * Wait for page to be loaded
   *
   * @param options - Wait options
   *
   * @example
   * ```ts
   * await loginPage.waitForLoad()
   * ```
   */
  async waitForLoad(options: {
    state?: 'load' | 'domcontentloaded' | 'networkidle'
    timeout?: number
  } = {}): Promise<void> {
    await this.page.waitForLoadState(options.state || 'networkidle', {
      timeout: options.timeout || 30000,
    })
  }

  /**
   * Get page title
   *
   * @returns Page title
   *
   * @example
   * ```ts
   * const title = await loginPage.getTitle()
   * ```
   */
  async getTitle(): Promise<string> {
    return await this.page.title()
  }

  /**
   * Get current URL
   *
   * @returns Current URL
   *
   * @example
   * ```ts
   * const url = await loginPage.getUrl()
   * ```
   */
  getUrl(): string {
    return this.page.url()
  }

  /**
   * Check if page is at expected URL
   *
   * @param expectedPath - Expected path (relative to base URL)
   * @param options - Match options
   * @returns True if URL matches
   *
   * @example
   * ```ts
   * await expect(loginPage.isAtUrl('/auth/login')).toBeTruthy()
   * ```
   */
  async isAtUrl(
    expectedPath: string,
    options: {
      exact?: boolean
    } = {}
  ): Promise<boolean> {
    const expectedUrl = expectedPath.startsWith('http')
      ? expectedPath
      : `${this.baseURL}${expectedPath}`
    const currentUrl = this.getUrl()

    if (options.exact) {
      return currentUrl === expectedUrl
    }

    return currentUrl.startsWith(expectedUrl)
  }

  /**
   * Wait for URL to match
   *
   * @param expectedPath - Expected path (relative to base URL)
   * @param options - Wait options
   *
   * @example
   * ```ts
   * await loginPage.waitForUrl('/dashboard')
   * ```
   */
  async waitForUrl(
    expectedPath: string,
    options: {
      timeout?: number
      exact?: boolean
    } = {}
  ): Promise<void> {
    const expectedUrl = expectedPath.startsWith('http')
      ? expectedPath
      : `${this.baseURL}${expectedPath}`

    await this.page.waitForURL(expectedUrl, {
      timeout: options.timeout || 30000,
    })
  }

  /**
   * Take screenshot
   *
   * @param name - Screenshot name
   * @param options - Screenshot options
   *
   * @example
   * ```ts
   * await loginPage.screenshot('login-page')
   * ```
   */
  async screenshot(
    name: string,
    options: {
      fullPage?: boolean
      path?: string
    } = {}
  ): Promise<Buffer> {
    return await this.page.screenshot({
      path: options.path,
      fullPage: options.fullPage || false,
    })
  }

  /**
   * Wait for element to be visible
   *
   * @param selector - Element selector
   * @param options - Wait options
   * @returns Locator for the element
   *
   * @example
   * ```ts
   * await loginPage.waitForVisible('button[type="submit"]')
   * ```
   */
  async waitForVisible(
    selector: string,
    options: {
      timeout?: number
    } = {}
  ): Promise<Locator> {
    const locator = this.page.locator(selector)
    await locator.waitFor({
      state: 'visible',
      timeout: options.timeout || 30000,
    })
    return locator
  }

  /**
   * Wait for element to be hidden
   *
   * @param selector - Element selector
   * @param options - Wait options
   *
   * @example
   * ```ts
   * await loginPage.waitForHidden('.loading-spinner')
   * ```
   */
  async waitForHidden(
    selector: string,
    options: {
      timeout?: number
    } = {}
  ): Promise<void> {
    const locator = this.page.locator(selector)
    await locator.waitFor({
      state: 'hidden',
      timeout: options.timeout || 30000,
    })
  }

  /**
   * Wait for element to be attached to DOM
   *
   * @param selector - Element selector
   * @param options - Wait options
   * @returns Locator for the element
   *
   * @example
   * ```ts
   * await loginPage.waitForAttached('.modal')
   * ```
   */
  async waitForAttached(
    selector: string,
    options: {
      timeout?: number
    } = {}
  ): Promise<Locator> {
    const locator = this.page.locator(selector)
    await locator.waitFor({
      state: 'attached',
      timeout: options.timeout || 30000,
    })
    return locator
  }

  /**
   * Wait for element text to match
   *
   * @param selector - Element selector
   * @param text - Expected text (can be regex)
   * @param options - Wait options
   *
   * @example
   * ```ts
   * await loginPage.waitForText('h1', 'Sign In')
   * ```
   */
  async waitForText(
    selector: string,
    text: string | RegExp,
    options: {
      timeout?: number
    } = {}
  ): Promise<void> {
    const locator = this.page.locator(selector)
    await expect(locator).toHaveText(text, {
      timeout: options.timeout || 30000,
    })
  }

  /**
   * Fill form field
   *
   * @param selector - Field selector
   * @param value - Value to fill
   * @param options - Fill options
   *
   * @example
   * ```ts
   * await loginPage.fillField('input[type="email"]', 'test@example.com')
   * ```
   */
  async fillField(
    selector: string,
    value: string,
    options: {
      timeout?: number
      clear?: boolean
    } = {}
  ): Promise<void> {
    const locator = this.page.locator(selector)
    await locator.waitFor({ state: 'visible', timeout: options.timeout || 30000 })

    if (options.clear !== false) {
      await locator.clear()
    }

    await locator.fill(value)
  }

  /**
   * Click element
   *
   * @param selector - Element selector
   * @param options - Click options
   *
   * @example
   * ```ts
   * await loginPage.click('button[type="submit"]')
   * ```
   */
  async click(
    selector: string,
    options: {
      timeout?: number
      force?: boolean
      waitForNavigation?: boolean
    } = {}
  ): Promise<void> {
    const locator = this.page.locator(selector)
    await locator.waitFor({ state: 'visible', timeout: options.timeout || 30000 })

    if (options.waitForNavigation) {
      await Promise.all([
        this.page.waitForNavigation({ timeout: options.timeout || 30000 }),
        locator.click({ force: options.force }),
      ])
    } else {
      await locator.click({ force: options.force })
    }
  }

  /**
   * Select option from dropdown
   *
   * @param selector - Select element selector
   * @param value - Option value or label
   * @param options - Select options
   *
   * @example
   * ```ts
   * await loginPage.selectOption('select[name="status"]', 'ACTIVE')
   * ```
   */
  async selectOption(
    selector: string,
    value: string | { label?: string; value?: string; index?: number },
    options: {
      timeout?: number
    } = {}
  ): Promise<void> {
    const locator = this.page.locator(selector)
    await locator.waitFor({ state: 'visible', timeout: options.timeout || 30000 })
    await locator.selectOption(value)
  }

  /**
   * Check checkbox or radio button
   *
   * @param selector - Checkbox/radio selector
   * @param options - Check options
   *
   * @example
   * ```ts
   * await loginPage.check('input[type="checkbox"][name="remember_me"]')
   * ```
   */
  async check(
    selector: string,
    options: {
      timeout?: number
      force?: boolean
    } = {}
  ): Promise<void> {
    const locator = this.page.locator(selector)
    await locator.waitFor({ state: 'visible', timeout: options.timeout || 30000 })
    await locator.check({ force: options.force })
  }

  /**
   * Uncheck checkbox
   *
   * @param selector - Checkbox selector
   * @param options - Uncheck options
   *
   * @example
   * ```ts
   * await loginPage.uncheck('input[type="checkbox"]')
   * ```
   */
  async uncheck(
    selector: string,
    options: {
      timeout?: number
      force?: boolean
    } = {}
  ): Promise<void> {
    const locator = this.page.locator(selector)
    await locator.waitFor({ state: 'visible', timeout: options.timeout || 30000 })
    await locator.uncheck({ force: options.force })
  }

  /**
   * Get element text
   *
   * @param selector - Element selector
   * @param options - Get text options
   * @returns Element text
   *
   * @example
   * ```ts
   * const title = await loginPage.getText('h1')
   * ```
   */
  async getText(
    selector: string,
    options: {
      timeout?: number
    } = {}
  ): Promise<string> {
    const locator = this.page.locator(selector)
    await locator.waitFor({ state: 'visible', timeout: options.timeout || 30000 })
    return await locator.textContent() || ''
  }

  /**
   * Get element attribute
   *
   * @param selector - Element selector
   * @param attribute - Attribute name
   * @param options - Get attribute options
   * @returns Attribute value
   *
   * @example
   * ```ts
   * const href = await loginPage.getAttribute('a', 'href')
   * ```
   */
  async getAttribute(
    selector: string,
    attribute: string,
    options: {
      timeout?: number
    } = {}
  ): Promise<string | null> {
    const locator = this.page.locator(selector)
    await locator.waitFor({ state: 'attached', timeout: options.timeout || 30000 })
    return await locator.getAttribute(attribute)
  }

  /**
   * Check if element is visible
   *
   * @param selector - Element selector
   * @param options - Check options
   * @returns True if element is visible
   *
   * @example
   * ```ts
   * const isVisible = await loginPage.isVisible('button[type="submit"]')
   * ```
   */
  async isVisible(
    selector: string,
    options: {
      timeout?: number
    } = {}
  ): Promise<boolean> {
    try {
      const locator = this.page.locator(selector)
      await locator.waitFor({ state: 'visible', timeout: options.timeout || 5000 })
      return true
    } catch {
      return false
    }
  }

  /**
   * Check if element exists in DOM
   *
   * @param selector - Element selector
   * @param options - Check options
   * @returns True if element exists
   *
   * @example
   * ```ts
   * const exists = await loginPage.exists('.modal')
   * ```
   */
  async exists(
    selector: string,
    options: {
      timeout?: number
    } = {}
  ): Promise<boolean> {
    try {
      const locator = this.page.locator(selector)
      await locator.waitFor({ state: 'attached', timeout: options.timeout || 5000 })
      return true
    } catch {
      return false
    }
  }

  /**
   * Wait for network request to complete
   *
   * @param urlPattern - URL pattern to wait for (regex or string)
   * @param options - Wait options
   * @returns Response object
   *
   * @example
   * ```ts
   * const response = await loginPage.waitForRequest(/\/api\/v1\/auth\/login/)
   * ```
   */
  async waitForRequest(
    urlPattern: string | RegExp,
    options: {
      timeout?: number
    } = {}
  ): Promise<any> {
    return await this.page.waitForRequest(urlPattern, {
      timeout: options.timeout || 30000,
    })
  }

  /**
   * Wait for network response
   *
   * @param urlPattern - URL pattern to wait for (regex or string)
   * @param options - Wait options
   * @returns Response object
   *
   * @example
   * ```ts
   * const response = await loginPage.waitForResponse(/\/api\/v1\/auth\/login/)
   * ```
   */
  async waitForResponse(
    urlPattern: string | RegExp,
    options: {
      timeout?: number
    } = {}
  ): Promise<any> {
    return await this.page.waitForResponse(urlPattern, {
      timeout: options.timeout || 30000,
    })
  }

  /**
   * Execute JavaScript in page context
   *
   * @param script - JavaScript code to execute
   * @param args - Arguments to pass to script
   * @returns Script return value
   *
   * @example
   * ```ts
   * const value = await loginPage.evaluate(() => localStorage.getItem('token'))
   * ```
   */
  async evaluate<T = any>(script: string | Function, ...args: any[]): Promise<T> {
    return await this.page.evaluate(script as any, ...args)
  }

  /**
   * Reload page
   *
   * @param options - Reload options
   *
   * @example
   * ```ts
   * await loginPage.reload()
   * ```
   */
  async reload(options: {
    waitUntil?: 'load' | 'domcontentloaded' | 'networkidle' | 'commit'
    timeout?: number
  } = {}): Promise<void> {
    await this.page.reload({
      waitUntil: options.waitUntil || 'networkidle',
      timeout: options.timeout || 30000,
    })
  }

  /**
   * Go back in browser history
   *
   * @param options - Navigation options
   *
   * @example
   * ```ts
   * await loginPage.goBack()
   * ```
   */
  async goBack(options: {
    waitUntil?: 'load' | 'domcontentloaded' | 'networkidle' | 'commit'
    timeout?: number
  } = {}): Promise<void> {
    await this.page.goBack({
      waitUntil: options.waitUntil || 'networkidle',
      timeout: options.timeout || 30000,
    })
  }

  /**
   * Go forward in browser history
   *
   * @param options - Navigation options
   *
   * @example
   * ```ts
   * await loginPage.goForward()
   * ```
   */
  async goForward(options: {
    waitUntil?: 'load' | 'domcontentloaded' | 'networkidle' | 'commit'
    timeout?: number
  } = {}): Promise<void> {
    await this.page.goForward({
      waitUntil: options.waitUntil || 'networkidle',
      timeout: options.timeout || 30000,
    })
  }

  /**
   * Assert page is at expected URL
   *
   * @param expectedPath - Expected path (relative to base URL)
   * @param options - Assert options
   *
   * @example
   * ```ts
   * await loginPage.assertUrl('/auth/login')
   * ```
   */
  async assertUrl(
    expectedPath: string,
    options: {
      exact?: boolean
    } = {}
  ): Promise<void> {
    const expectedUrl = expectedPath.startsWith('http')
      ? expectedPath
      : `${this.baseURL}${expectedPath}`
    const currentUrl = this.getUrl()

    if (options.exact) {
      expect(currentUrl).toBe(expectedUrl)
    } else {
      expect(currentUrl).toContain(expectedPath)
    }
  }

  /**
   * Assert element is visible
   *
   * @param selector - Element selector
   * @param options - Assert options
   *
   * @example
   * ```ts
   * await loginPage.assertVisible('button[type="submit"]')
   * ```
   */
  async assertVisible(
    selector: string,
    options: {
      timeout?: number
    } = {}
  ): Promise<void> {
    const locator = this.page.locator(selector)
    await expect(locator).toBeVisible({
      timeout: options.timeout || 30000,
    })
  }

  /**
   * Assert element is hidden
   *
   * @param selector - Element selector
   * @param options - Assert options
   *
   * @example
   * ```ts
   * await loginPage.assertHidden('.loading-spinner')
   * ```
   */
  async assertHidden(
    selector: string,
    options: {
      timeout?: number
    } = {}
  ): Promise<void> {
    const locator = this.page.locator(selector)
    await expect(locator).toBeHidden({
      timeout: options.timeout || 30000,
    })
  }

  /**
   * Assert element text matches
   *
   * @param selector - Element selector
   * @param text - Expected text (can be regex)
   * @param options - Assert options
   *
   * @example
   * ```ts
   * await loginPage.assertText('h1', 'Sign In')
   * ```
   */
  async assertText(
    selector: string,
    text: string | RegExp,
    options: {
      timeout?: number
    } = {}
  ): Promise<void> {
    const locator = this.page.locator(selector)
    await expect(locator).toHaveText(text, {
      timeout: options.timeout || 30000,
    })
  }

  /**
   * Assert element has attribute
   *
   * @param selector - Element selector
   * @param attribute - Attribute name
   * @param value - Expected attribute value (optional)
   * @param options - Assert options
   *
   * @example
   * ```ts
   * await loginPage.assertAttribute('input', 'type', 'email')
   * ```
   */
  async assertAttribute(
    selector: string,
    attribute: string,
    value?: string | RegExp,
    options: {
      timeout?: number
    } = {}
  ): Promise<void> {
    const locator = this.page.locator(selector)
    await locator.waitFor({ state: 'attached', timeout: options.timeout || 30000 })

    if (value !== undefined) {
      await expect(locator).toHaveAttribute(attribute, value)
    } else {
      const attrValue = await locator.getAttribute(attribute)
      expect(attrValue).not.toBeNull()
    }
  }
}

/**
 * Page object options
 */
export interface PageOptions {
  baseURL?: string
}

