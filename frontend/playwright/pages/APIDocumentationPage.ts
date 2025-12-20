/**
 * API Documentation Page Object Model
 *
 * Page Object Model for the API documentation page.
 * Encapsulates all API documentation page interactions and assertions.
 *
 * Uses real implementations - no mocks/stubs. Always fixes root cause.
 */

import { Page, Locator, expect } from '@playwright/test'
import { BasePage } from '../utils/page-objects'

/**
 * API Documentation Page Object
 */
export class APIDocumentationPage extends BasePage {
  // Header locators
  readonly pageTitle: Locator
  readonly pageSubtitle: Locator

  // Search and filters
  readonly searchInput: Locator
  readonly apiVersionSelect: Locator
  readonly authTokenInput: Locator

  // Tab locators
  readonly overviewTab: Locator
  readonly restApiTab: Locator
  readonly graphqlTab: Locator
  readonly websocketTab: Locator
  readonly apiExplorerTab: Locator

  // REST API tab locators
  readonly endpointCards: Locator
  readonly selectedEndpointCard: Locator
  readonly endpointMethodChip: Locator
  readonly endpointPath: Locator
  readonly endpointDescription: Locator
  readonly parametersSection: Locator
  readonly responsesSection: Locator
  readonly codeExamplesSection: Locator
  readonly codeLanguageButtons: Locator
  readonly curlButton: Locator
  readonly javascriptButton: Locator
  readonly pythonButton: Locator
  readonly copyCodeButton: Locator
  readonly codeBlock: Locator

  // GraphQL tab locators
  readonly graphqlEndpoint: Locator
  readonly graphqlQueryExample: Locator
  readonly graphqlMutationExample: Locator
  readonly graphqlSchemaExplorer: Locator

  // WebSocket tab locators
  readonly websocketConnectionExample: Locator
  readonly websocketEventTypesTable: Locator
  readonly websocketSubscriptionExample: Locator

  // API Explorer tab locators
  readonly endpointSelect: Locator
  readonly sendRequestButton: Locator
  readonly requestCodeBlock: Locator

  constructor(page: Page) {
    super(page, '/api-docs')

    // Header
    this.pageTitle = page.locator('h3, h2, h1:has-text("API Documentation")')
    this.pageSubtitle = page.locator('p, span:has-text("Comprehensive API documentation")')

    // Search and filters
    this.searchInput = page.locator('input[placeholder*="Search"], input[type="text"]').first()
    this.apiVersionSelect = page.locator('label:has-text("API Version")').locator('..').locator('select, [role="combobox"]')
    this.authTokenInput = page.locator('input[type="password"], input[label*="Auth Token"]')

    // Tabs
    this.overviewTab = page.locator('button[role="tab"]:has-text("Overview"), [role="tab"]:has-text("Overview")')
    this.restApiTab = page.locator('button[role="tab"]:has-text("REST API"), [role="tab"]:has-text("REST API")')
    this.graphqlTab = page.locator('button[role="tab"]:has-text("GraphQL"), [role="tab"]:has-text("GraphQL")')
    this.websocketTab = page.locator('button[role="tab"]:has-text("WebSocket"), [role="tab"]:has-text("WebSocket")')
    this.apiExplorerTab = page.locator('button[role="tab"]:has-text("API Explorer"), [role="tab"]:has-text("API Explorer")')

    // REST API tab
    this.endpointCards = page.locator('[class*="Card"], [class*="card"]').filter({ hasText: /GET|POST|PUT|PATCH|DELETE/ })
    this.selectedEndpointCard = page.locator('[class*="Card"][class*="border"], [class*="card"][class*="border"]')
    this.endpointMethodChip = page.locator('[class*="Chip"], span:has-text(/GET|POST|PUT|PATCH|DELETE/)')
    this.endpointPath = page.locator('code, [class*="monospace"]:has-text("/api/")')
    this.endpointDescription = page.locator('p, span:has-text("List"), p:has-text("Create"), p:has-text("Get")')
    this.parametersSection = page.locator('h6:has-text("Parameters"), h5:has-text("Parameters"), h4:has-text("Parameters")')
    this.responsesSection = page.locator('h6:has-text("Responses"), h5:has-text("Responses"), h4:has-text("Responses")')
    this.codeExamplesSection = page.locator('h6:has-text("Code Examples"), h5:has-text("Code Examples"), h4:has-text("Code Examples")')
    this.codeLanguageButtons = page.locator('button:has-text("cURL"), button:has-text("JavaScript"), button:has-text("Python")')
    this.curlButton = page.locator('button:has-text("cURL")')
    this.javascriptButton = page.locator('button:has-text("JavaScript")')
    this.pythonButton = page.locator('button:has-text("Python")')
    this.copyCodeButton = page.locator('button[aria-label*="Copy"], button[title*="Copy"], button:has([class*="CopyIcon"])')
    this.codeBlock = page.locator('pre, code, [class*="CodeBlock"], [class*="code-block"]')

    // GraphQL tab
    this.graphqlEndpoint = page.locator('code:has-text("/graphql"), code:has-text("/api/v1/graphql")')
    this.graphqlQueryExample = page.locator('pre:has-text("query"), code:has-text("query")')
    this.graphqlMutationExample = page.locator('pre:has-text("mutation"), code:has-text("mutation")')
    this.graphqlSchemaExplorer = page.locator('code:has-text("graphql"), a:has-text("playground")')

    // WebSocket tab
    this.websocketConnectionExample = page.locator('code:has-text("WebSocket"), code:has-text("ws://"), code:has-text("wss://")')
    this.websocketEventTypesTable = page.locator('table, [class*="Table"]')
    this.websocketSubscriptionExample = page.locator('code:has-text("subscribe"), pre:has-text("WebSocket")')

    // API Explorer tab
    this.endpointSelect = page.locator('label:has-text("Select Endpoint")').locator('..').locator('select, [role="combobox"]')
    this.sendRequestButton = page.locator('button:has-text("Send Request"), button:has([class*="PlayIcon"])')
    this.requestCodeBlock = page.locator('pre, code, [class*="CodeBlock"]')
  }

  /**
   * Navigate to API documentation page
   */
  async goto(options?: { waitUntil?: 'load' | 'domcontentloaded' | 'networkidle' | 'commit'; timeout?: number }): Promise<void> {
    await super.goto(options)
    await this.waitForPageLoad()
  }

  /**
   * Wait for API documentation page to be fully loaded
   */
  async waitForPageLoad(): Promise<void> {
    await this.waitForVisible('h3:has-text("API Documentation"), h2:has-text("API Documentation"), h1:has-text("API Documentation")', { timeout: 10000 })
    await this.waitForVisible('button[role="tab"]', { timeout: 10000 })
  }

  /**
   * Assert page is loaded
   */
  async assertPageLoaded(): Promise<void> {
    await this.assertVisible('h3:has-text("API Documentation"), h2:has-text("API Documentation"), h1:has-text("API Documentation")')
    await this.assertVisible('button[role="tab"]')
  }

  /**
   * Search for endpoints
   */
  async search(query: string): Promise<void> {
    await this.searchInput.waitFor({ state: 'visible', timeout: 10000 })
    await this.searchInput.fill(query)
    await this.page.waitForTimeout(300) // Wait for debounce
  }

  /**
   * Clear search
   */
  async clearSearch(): Promise<void> {
    await this.searchInput.clear()
    await this.page.waitForTimeout(300)
  }

  /**
   * Select API version
   */
  async selectApiVersion(version: string): Promise<void> {
    await this.apiVersionSelect.waitFor({ state: 'visible', timeout: 10000 })
    // Try selectOption first, fallback to click if it's a combobox
    try {
      await this.apiVersionSelect.selectOption(version)
    } catch {
      await this.apiVersionSelect.click()
      await this.page.waitForTimeout(300)
      await this.page.locator(`text=${version}`).click()
    }
    await this.page.waitForTimeout(300)
  }

  /**
   * Set auth token
   */
  async setAuthToken(token: string): Promise<void> {
    await this.authTokenInput.waitFor({ state: 'visible', timeout: 10000 })
    await this.authTokenInput.fill(token)
  }

  /**
   * Click on tab
   */
  async clickTab(tabName: 'Overview' | 'REST API' | 'GraphQL' | 'WebSocket' | 'API Explorer'): Promise<void> {
    const tabMap = {
      'Overview': this.overviewTab,
      'REST API': this.restApiTab,
      'GraphQL': this.graphqlTab,
      'WebSocket': this.websocketTab,
      'API Explorer': this.apiExplorerTab,
    }
    const tab = tabMap[tabName]
    await tab.waitFor({ state: 'visible', timeout: 10000 })
    await tab.click()
    await this.page.waitForTimeout(500) // Wait for tab content to load
  }

  /**
   * Click on endpoint card
   */
  async clickEndpointCard(index: number = 0): Promise<void> {
    const cards = await this.endpointCards.all()
    if (cards.length > index) {
      await cards[index].click()
      await this.page.waitForTimeout(300)
    }
  }

  /**
   * Get endpoint card by method and path
   */
  async getEndpointCard(method: string, path: string): Promise<Locator | null> {
    const cards = await this.endpointCards.all()
    for (const card of cards) {
      const text = await card.textContent()
      if (text?.includes(method) && text?.includes(path)) {
        return card
      }
    }
    return null
  }

  /**
   * Click endpoint by method and path
   */
  async clickEndpoint(method: string, path: string): Promise<void> {
    const card = await this.getEndpointCard(method, path)
    if (card) {
      await card.click()
      await this.page.waitForTimeout(300)
    }
  }

  /**
   * Select code language
   */
  async selectCodeLanguage(language: 'curl' | 'javascript' | 'python'): Promise<void> {
    const buttonMap = {
      curl: this.curlButton,
      javascript: this.javascriptButton,
      python: this.pythonButton,
    }
    const button = buttonMap[language]
    await button.waitFor({ state: 'visible', timeout: 10000 })
    await button.click()
    await this.page.waitForTimeout(300)
  }

  /**
   * Copy code snippet
   */
  async copyCode(): Promise<void> {
    await this.copyCodeButton.waitFor({ state: 'visible', timeout: 10000 })
    await this.copyCodeButton.click()
  }

  /**
   * Get code snippet text
   */
  async getCodeSnippet(): Promise<string> {
    await this.codeBlock.first().waitFor({ state: 'visible', timeout: 10000 })
    return await this.codeBlock.first().textContent() || ''
  }

  /**
   * Assert endpoint is displayed
   */
  async assertEndpointDisplayed(method: string, path: string): Promise<void> {
    const card = await this.getEndpointCard(method, path)
    expect(card).not.toBeNull()
    if (card) {
      await expect(card).toBeVisible()
    }
  }

  /**
   * Assert endpoint details are displayed
   */
  async assertEndpointDetails(method: string, path: string): Promise<void> {
    await this.assertVisible(`text=${method}`)
    await this.assertVisible(`text=${path}`)
  }

  /**
   * Assert parameters section is visible
   */
  async assertParametersVisible(): Promise<void> {
    await this.assertVisible('h6:has-text("Parameters"), h5:has-text("Parameters"), h4:has-text("Parameters")')
  }

  /**
   * Assert responses section is visible
   */
  async assertResponsesVisible(): Promise<void> {
    await this.assertVisible('h6:has-text("Responses"), h5:has-text("Responses"), h4:has-text("Responses")')
  }

  /**
   * Assert code examples are visible
   */
  async assertCodeExamplesVisible(): Promise<void> {
    await this.assertVisible('h6:has-text("Code Examples"), h5:has-text("Code Examples"), h4:has-text("Code Examples")')
  }

  /**
   * Assert GraphQL content is displayed
   */
  async assertGraphQLContent(): Promise<void> {
    await this.assertVisible('h5:has-text("GraphQL API"), h6:has-text("GraphQL")')
    await this.assertVisible('code:has-text("/graphql"), code:has-text("/api/v1/graphql")')
  }

  /**
   * Assert WebSocket content is displayed
   */
  async assertWebSocketContent(): Promise<void> {
    await this.assertVisible('h5:has-text("WebSocket API"), h6:has-text("WebSocket")')
    await this.assertVisible('code:has-text("ws://"), code:has-text("wss://")')
  }

  /**
   * Assert API Explorer is displayed
   */
  async assertAPIExplorerVisible(): Promise<void> {
    await this.assertVisible('h5:has-text("Interactive API Explorer"), h6:has-text("API Explorer")')
  }

  /**
   * Get filtered endpoint count
   */
  async getEndpointCount(): Promise<number> {
    const cards = await this.endpointCards.all()
    return cards.length
  }

  /**
   * Assert search filters endpoints
   */
  async assertSearchFilters(query: string, expectedCount: number): Promise<void> {
    await this.search(query)
    const count = await this.getEndpointCount()
    expect(count).toBe(expectedCount)
  }
}

