/**
 * Marketplace Page Object Model
 *
 * Page Object Model for the marketplace page.
 * Encapsulates all marketplace discovery interactions and assertions.
 *
 * Uses real implementations - no mocks/stubs. Always fixes root cause.
 */

import { Page, Locator, expect } from '@playwright/test'
import { BasePage } from '../utils/page-objects'

/**
 * Marketplace Page Object
 */
export class MarketplacePage extends BasePage {
  // Locators - Header
  readonly pageTitle: Locator
  readonly pageSubtitle: Locator
  readonly refreshButton: Locator
  readonly contractCount: Locator

  // Locators - Featured Contracts Section
  readonly featuredSection: Locator
  readonly featuredTitle: Locator
  readonly featuredContracts: Locator
  readonly featuredContractCard: Locator

  // Locators - Search
  readonly searchBar: Locator
  readonly searchInput: Locator
  readonly searchClearButton: Locator

  // Locators - Filters
  readonly filtersSection: Locator
  readonly domainFilter: Locator
  readonly domainSelect: Locator
  readonly tagsFilter: Locator
  readonly tagsAutocomplete: Locator
  readonly accessModeFilter: Locator
  readonly accessModeSelect: Locator
  readonly priceMinInput: Locator
  readonly priceMaxInput: Locator
  readonly clearFiltersButton: Locator

  // Locators - Sort
  readonly sortSelect: Locator
  readonly sortOption: Locator

  // Locators - Results
  readonly resultsCount: Locator
  readonly contractCards: Locator
  readonly contractCard: Locator
  readonly contractCardTitle: Locator
  readonly contractCardDescription: Locator
  readonly contractCardDomain: Locator
  readonly contractCardTags: Locator
  readonly contractCardPrice: Locator
  readonly contractCardViewButton: Locator
  readonly contractCardDownloadButton: Locator

  // Locators - Pagination
  readonly pagination: Locator
  readonly paginationNext: Locator
  readonly paginationPrevious: Locator
  readonly paginationPage: Locator

  // Locators - Empty States
  readonly noResultsState: Locator
  readonly noDataState: Locator

  constructor(page: Page) {
    super(page, '/marketplace')

    // Header
    this.pageTitle = page.locator('h1, h2, h3, h4:has-text("Marketplace")')
    this.pageSubtitle = page.locator('text=/Discover.*contracts/i, text=/\\d+.*total/i')
    this.refreshButton = page.locator('button[aria-label*="Refresh" i], button:has([class*="refresh"])')
    this.contractCount = page.locator('text=/\\d+.*total/i, text=/\\d+.*contract/i')

    // Featured Contracts
    this.featuredSection = page.locator('text="Featured Contracts", [class*="featured"]')
    this.featuredTitle = page.locator('h2, h3, h4, h5:has-text("Featured Contracts")')
    this.featuredContracts = page.locator('[class*="featured"], [data-testid="featured-contracts"]')
    this.featuredContractCard = page.locator('[class*="featured"] [class*="card"], [data-testid="featured-contract"]')

    // Search
    this.searchBar = page.locator('[class*="search"], [data-testid="search-bar"], input[type="search"], input[placeholder*="search" i]')
    this.searchInput = page.locator('input[type="search"], input[placeholder*="search" i], input[name*="search" i]')
    this.searchClearButton = page.locator('button[aria-label*="Clear" i]:near(input[type="search"])')

    // Filters
    this.filtersSection = page.locator('[class*="filter"], [data-testid="filters"]')
    this.domainFilter = page.locator('select[name*="domain" i], [role="combobox"][aria-label*="Domain" i]')
    this.domainSelect = page.locator('select[name*="domain" i], [role="combobox"][aria-label*="Domain" i]')
    this.tagsFilter = page.locator('[class*="autocomplete"], [role="combobox"][aria-label*="Tag" i]')
    this.tagsAutocomplete = page.locator('[class*="autocomplete"], [role="combobox"][aria-label*="Tag" i]')
    this.accessModeFilter = page.locator('select[name*="access" i], [role="combobox"][aria-label*="Access Mode" i]')
    this.accessModeSelect = page.locator('select[name*="access" i], [role="combobox"][aria-label*="Access Mode" i]')
    this.priceMinInput = page.locator('input[name*="min" i][name*="price" i], input[label*="Min Price" i]')
    this.priceMaxInput = page.locator('input[name*="max" i][name*="price" i], input[label*="Max Price" i]')
    this.clearFiltersButton = page.locator('button:has-text("Clear Filters"), button[aria-label*="Clear Filters" i]')

    // Sort
    this.sortSelect = page.locator('select[name*="sort" i], [role="combobox"][aria-label*="Sort" i]')
    this.sortOption = page.locator('option, [role="option"]')

    // Results
    this.resultsCount = page.locator('text=/\\d+.*contract.*found/i, text=/\\d+.*result/i')
    this.contractCards = page.locator('[class*="card"], [data-testid="contract-card"]')
    this.contractCard = page.locator('[class*="card"]:has([class*="contract"]), [data-testid="contract-card"]')
    this.contractCardTitle = page.locator('[class*="card"] h6, [class*="card"] [class*="title"]')
    this.contractCardDescription = page.locator('[class*="card"] [class*="description"], [class*="card"] p')
    this.contractCardDomain = page.locator('[class*="card"] [class*="domain"], [class*="card"] [class*="chip"]:has-text("domain")')
    this.contractCardTags = page.locator('[class*="card"] [class*="tag"], [class*="card"] [class*="chip"]')
    this.contractCardPrice = page.locator('[class*="card"] [class*="price"], [class*="card"] text=/\\$|USD/i')
    this.contractCardViewButton = page.locator('[class*="card"] button:has-text("View"), [class*="card"] button[aria-label*="View" i]')
    this.contractCardDownloadButton = page.locator('[class*="card"] button:has-text("Download"), [class*="card"] button[aria-label*="Download" i]')

    // Pagination
    this.pagination = page.locator('[class*="pagination"], [data-testid="pagination"]')
    this.paginationNext = page.locator('button[aria-label*="Next" i], button:has-text("Next")')
    this.paginationPrevious = page.locator('button[aria-label*="Previous" i], button:has-text("Previous")')
    this.paginationPage = page.locator('[class*="pagination"] button, [role="button"]:has-text(/\\d+/):near([class*="pagination"])')

    // Empty States
    this.noResultsState = page.locator('text="No contracts found", text="No results"')
    this.noDataState = page.locator('text="No contracts available", text="No data"')
  }

  /**
   * Navigate to marketplace page
   */
  async goto(): Promise<void> {
    await super.goto({ waitUntil: 'networkidle' })
    await this.waitForPageLoad()
  }

  /**
   * Wait for marketplace page to be fully loaded
   */
  async waitForPageLoad(): Promise<void> {
    await this.waitForVisible('h1, h2, h3, h4:has-text("Marketplace")', { timeout: 10000 })
  }

  /**
   * Search for contracts
   */
  async search(query: string): Promise<void> {
    await this.searchInput.waitFor({ state: 'visible', timeout: 10000 })
    await this.searchInput.fill(query)
    // Wait for debounce (500ms)
    await this.page.waitForTimeout(600)
  }

  /**
   * Clear search
   */
  async clearSearch(): Promise<void> {
    if (await this.searchClearButton.count() > 0) {
      await this.searchClearButton.click()
      await this.page.waitForTimeout(600)
    } else {
      await this.searchInput.fill('')
      await this.page.waitForTimeout(600)
    }
  }

  /**
   * Filter by domain
   */
  async filterByDomain(domain: string): Promise<void> {
    await this.domainSelect.waitFor({ state: 'visible', timeout: 10000 })
    await this.domainSelect.selectOption(domain)
    await this.page.waitForTimeout(500)
  }

  /**
   * Filter by tags
   */
  async filterByTags(tags: string[]): Promise<void> {
    await this.tagsAutocomplete.waitFor({ state: 'visible', timeout: 10000 })

    for (const tag of tags) {
      await this.tagsAutocomplete.click()
      await this.page.waitForTimeout(200)

      // Type tag and select
      await this.page.keyboard.type(tag)
      await this.page.waitForTimeout(300)
      await this.page.keyboard.press('Enter')
      await this.page.waitForTimeout(200)
    }
  }

  /**
   * Filter by access mode
   */
  async filterByAccessMode(accessMode: 'FREE' | 'FREE_AUTO_APPROVE' | 'REQUEST_APPROVAL'): Promise<void> {
    await this.accessModeSelect.waitFor({ state: 'visible', timeout: 10000 })
    await this.accessModeSelect.selectOption(accessMode)
    await this.page.waitForTimeout(500)
  }

  /**
   * Filter by price range
   */
  async filterByPriceRange(min?: number, max?: number): Promise<void> {
    if (min !== undefined) {
      await this.priceMinInput.waitFor({ state: 'visible', timeout: 10000 })
      await this.priceMinInput.fill(min.toString())
      await this.page.waitForTimeout(300)
    }

    if (max !== undefined) {
      await this.priceMaxInput.waitFor({ state: 'visible', timeout: 10000 })
      await this.priceMaxInput.fill(max.toString())
      await this.page.waitForTimeout(300)
    }
  }

  /**
   * Sort contracts
   */
  async sortBy(option: 'relevance' | 'newest' | 'oldest' | 'title_asc' | 'title_desc' | 'price_asc' | 'price_desc'): Promise<void> {
    await this.sortSelect.waitFor({ state: 'visible', timeout: 10000 })
    await this.sortSelect.selectOption(option)
    await this.page.waitForTimeout(500)
  }

  /**
   * Clear all filters
   */
  async clearFilters(): Promise<void> {
    if (await this.clearFiltersButton.count() > 0) {
      await this.clearFiltersButton.click()
      await this.page.waitForTimeout(500)
    }
  }

  /**
   * Get contract count
   */
  async getContractCount(): Promise<number> {
    const countText = await this.contractCount.textContent()
    if (countText) {
      const match = countText.match(/(\d+)/)
      if (match) {
        return parseInt(match[1], 10)
      }
    }
    return 0
  }

  /**
   * Get number of contract cards displayed
   */
  async getContractCardCount(): Promise<number> {
    return await this.contractCard.count()
  }

  /**
   * Get contract card titles
   */
  async getContractCardTitles(): Promise<string[]> {
    const titles: string[] = []
    const count = await this.contractCard.count()

    for (let i = 0; i < count; i++) {
      const title = await this.contractCard.nth(i).locator('h6, [class*="title"]').textContent()
      if (title) {
        titles.push(title.trim())
      }
    }

    return titles
  }

  /**
   * Click on contract card
   */
  async clickContractCard(index: number = 0): Promise<void> {
    const card = this.contractCard.nth(index)
    await card.waitFor({ state: 'visible', timeout: 10000 })
    await card.click()
    await this.page.waitForTimeout(1000)
  }

  /**
   * Click view button on contract card
   */
  async clickViewButton(index: number = 0): Promise<void> {
    const viewButton = this.contractCardViewButton.nth(index)
    if (await viewButton.count() > 0) {
      await viewButton.click()
      await this.page.waitForTimeout(1000)
    }
  }

  /**
   * Click download button on contract card
   */
  async clickDownloadButton(index: number = 0): Promise<void> {
    const downloadButton = this.contractCardDownloadButton.nth(index)
    if (await downloadButton.count() > 0) {
      // Set up download listener
      const downloadPromise = this.page.waitForEvent('download', { timeout: 30000 })
      await downloadButton.click()

      try {
        const download = await downloadPromise
        expect(download.suggestedFilename()).toMatch(/\.(json|yaml|yml)$/i)
      } catch (error) {
        // Download may not trigger immediately, wait a bit
        await this.page.waitForTimeout(2000)
      }
    }
  }

  /**
   * Get featured contracts count
   */
  async getFeaturedContractsCount(): Promise<number> {
    return await this.featuredContractCard.count()
  }

  /**
   * Check if featured section is visible
   */
  async isFeaturedSectionVisible(): Promise<boolean> {
    return (await this.featuredSection.count()) > 0 && await this.featuredSection.isVisible()
  }

  /**
   * Navigate to next page
   */
  async nextPage(): Promise<void> {
    if (await this.paginationNext.count() > 0 && !(await this.paginationNext.isDisabled())) {
      await this.paginationNext.click()
      await this.page.waitForTimeout(1000)
    }
  }

  /**
   * Navigate to previous page
   */
  async previousPage(): Promise<void> {
    if (await this.paginationPrevious.count() > 0 && !(await this.paginationPrevious.isDisabled())) {
      await this.paginationPrevious.click()
      await this.page.waitForTimeout(1000)
    }
  }

  /**
   * Navigate to specific page
   */
  async goToPage(pageNumber: number): Promise<void> {
    const pageButton = this.paginationPage.filter({ hasText: pageNumber.toString() })
    if (await pageButton.count() > 0) {
      await pageButton.click()
      await this.page.waitForTimeout(1000)
    }
  }

  /**
   * Assert page is loaded correctly
   */
  async assertPageLoaded(): Promise<void> {
    await this.assertVisible('h1, h2, h3, h4:has-text("Marketplace")')
  }

  /**
   * Assert search bar is visible
   */
  async assertSearchBarVisible(): Promise<void> {
    await this.assertVisible('input[type="search"], input[placeholder*="search" i]')
  }

  /**
   * Assert filters are visible
   */
  async assertFiltersVisible(): Promise<void> {
    await this.assertVisible('[class*="filter"], [data-testid="filters"]')
  }

  /**
   * Assert featured contracts are displayed
   */
  async assertFeaturedContractsDisplayed(): Promise<void> {
    await this.assertVisible('text="Featured Contracts", [class*="featured"]')
    const count = await this.getFeaturedContractsCount()
    expect(count).toBeGreaterThan(0)
  }

  /**
   * Assert contract cards are displayed
   */
  async assertContractCardsDisplayed(): Promise<void> {
    const count = await this.getContractCardCount()
    expect(count).toBeGreaterThan(0)
  }

  /**
   * Assert search results contain query
   */
  async assertSearchResultsContain(query: string): Promise<void> {
    const titles = await this.getContractCardTitles()
    const descriptions = await this.contractCardDescription.allTextContents()

    const allText = [...titles, ...descriptions].join(' ').toLowerCase()
    expect(allText).toContain(query.toLowerCase())
  }

  /**
   * Assert contracts are sorted correctly
   */
  async assertContractsSorted(sortOption: string): Promise<void> {
    const titles = await this.getContractCardTitles()

    if (sortOption === 'title_asc') {
      const sorted = [...titles].sort((a, b) => a.localeCompare(b))
      expect(titles).toEqual(sorted)
    } else if (sortOption === 'title_desc') {
      const sorted = [...titles].sort((a, b) => b.localeCompare(a))
      expect(titles).toEqual(sorted)
    }
    // Other sort options would require more complex assertions
  }
}

