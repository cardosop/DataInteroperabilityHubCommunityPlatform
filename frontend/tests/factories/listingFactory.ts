/**
 * Marketplace Listing Factory
 *
 * Factory for creating test MarketplaceListing objects.
 */

import type {
  MarketplaceListing,
  ListingStatus,
  PricingModel,
} from '@/lib/api/marketplace'
import { generateId, generateUUID, randomDate, type FactoryOptions, type FactoryTrait } from './utils'

/**
 * Marketplace listing factory implementation
 */
class ListingFactory implements FactoryTrait<MarketplaceListing> {
  /**
   * Build a single MarketplaceListing
   */
  build(options: FactoryOptions<MarketplaceListing> = {}): MarketplaceListing {
    const { overrides = {}, uniqueIds = true } = options
    const id = uniqueIds ? generateUUID() : 'test-listing-1'
    const now = new Date().toISOString()
    const title = `Test Listing ${id.substring(0, 8)}`

    return {
      id,
      tenant: 'test-tenant',
      asset: 'test-asset-1',
      status: 'PUBLISHED' as ListingStatus,
      pricing_model: 'FREE' as PricingModel,
      metadata_json: {
        title,
        short_description: `Short description for ${title}`,
        long_description: `Long description for ${title}. This is a comprehensive description of the listing.`,
        price_amount: null,
        currency: null,
        tags: ['test', 'listing'],
        domain: 'test-domain',
      },
      published_at: now,
      created_at: randomDate(new Date(Date.now() - 30 * 24 * 60 * 60 * 1000)),
      updated_at: now,
      // Convenience fields
      title,
      description: `Long description for ${title}. This is a comprehensive description of the listing.`,
      short_description: `Short description for ${title}`,
      long_description: `Long description for ${title}. This is a comprehensive description of the listing.`,
      price_amount: null,
      currency: null,
      tags: ['test', 'listing'],
      domain: 'test-domain',
      ...overrides,
    }
  }

  buildMany(count: number, options: FactoryOptions<MarketplaceListing> = {}): MarketplaceListing[] {
    return Array.from({ length: count }, (_, index) =>
      this.build({
        ...options,
        overrides: {
          ...options.overrides,
          metadata_json: {
            title: `Test Listing ${index + 1}`,
            short_description: `Short description for listing ${index + 1}`,
            tags: ['test', 'listing'],
          },
          title: `Test Listing ${index + 1}`,
        },
      })
    )
  }

  buildSequence(builder: (index: number) => Partial<MarketplaceListing>): MarketplaceListing[] {
    const listings: MarketplaceListing[] = []
    let index = 0
    let listing = this.build({ overrides: builder(index) })

    while (listing) {
      listings.push(listing)
      index++
      const overrides = builder(index)
      if (overrides === null || overrides === undefined) {
        break
      }
      listing = this.build({ overrides })
    }

    return listings
  }

  /**
   * Build a DRAFT listing
   */
  draft(options: FactoryOptions<MarketplaceListing> = {}): MarketplaceListing {
    return this.build({
      ...options,
      overrides: {
        ...options.overrides,
        status: 'DRAFT' as ListingStatus,
        published_at: null,
      },
    })
  }

  /**
   * Build a PUBLISHED listing
   */
  published(options: FactoryOptions<MarketplaceListing> = {}): MarketplaceListing {
    return this.build({
      ...options,
      overrides: {
        ...options.overrides,
        status: 'PUBLISHED' as ListingStatus,
        published_at: new Date().toISOString(),
      },
    })
  }

  /**
   * Build an UNLISTED listing
   */
  unlisted(options: FactoryOptions<MarketplaceListing> = {}): MarketplaceListing {
    return this.build({
      ...options,
      overrides: {
        ...options.overrides,
        status: 'UNLISTED' as ListingStatus,
      },
    })
  }

  /**
   * Build a FREE listing
   */
  free(options: FactoryOptions<MarketplaceListing> = {}): MarketplaceListing {
    return this.build({
      ...options,
      overrides: {
        ...options.overrides,
        pricing_model: 'FREE' as PricingModel,
        metadata_json: {
          ...(options.overrides?.metadata_json || {}),
          price_amount: null,
          currency: null,
        },
        price_amount: null,
        currency: null,
      },
    })
  }

  /**
   * Build a FREE_AUTO_APPROVE listing
   */
  freeAutoApprove(options: FactoryOptions<MarketplaceListing> = {}): MarketplaceListing {
    return this.build({
      ...options,
      overrides: {
        ...options.overrides,
        pricing_model: 'FREE_AUTO_APPROVE' as PricingModel,
        metadata_json: {
          ...(options.overrides?.metadata_json || {}),
          price_amount: null,
          currency: null,
        },
        price_amount: null,
        currency: null,
      },
    })
  }

  /**
   * Build a REQUEST_APPROVAL listing with price
   */
  requestApproval(priceAmount: number, currency: string = 'USD', options: FactoryOptions<MarketplaceListing> = {}): MarketplaceListing {
    return this.build({
      ...options,
      overrides: {
        ...options.overrides,
        pricing_model: 'REQUEST_APPROVAL' as PricingModel,
        metadata_json: {
          ...(options.overrides?.metadata_json || {}),
          price_amount: priceAmount,
          currency,
        },
        price_amount: priceAmount,
        currency,
      },
    })
  }

  /**
   * Build a listing for a specific asset
   */
  forAsset(assetId: string, options: FactoryOptions<MarketplaceListing> = {}): MarketplaceListing {
    return this.build({
      ...options,
      overrides: {
        ...options.overrides,
        asset: assetId,
      },
    })
  }

  /**
   * Build a listing with specific tags
   */
  withTags(tags: string[], options: FactoryOptions<MarketplaceListing> = {}): MarketplaceListing {
    return this.build({
      ...options,
      overrides: {
        ...options.overrides,
        metadata_json: {
          ...(options.overrides?.metadata_json || {}),
          tags,
        },
        tags,
      },
    })
  }
}

export const listingFactory = new ListingFactory()
export { ListingFactory }

