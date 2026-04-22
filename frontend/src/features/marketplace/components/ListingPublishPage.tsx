/**
 * Listing Publish Page
 * Create a new marketplace listing
 */

import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useCreateListing } from '../hooks/useListings';
import { useAssets } from '../../assets/hooks/useAssets';
import { LoadingSpinner } from '../../../shared/components/LoadingSpinner';
import { ErrorDisplay } from '../../../shared/components/ErrorDisplay';
import { PricingModel } from '../../../shared/types/marketplace';
import './ListingPublishPage.css';
import { Button } from '../../../shared/components/Button';

export function ListingPublishPage() {
  const navigate = useNavigate();
  const createMutation = useCreateListing();
  // Only ACTIVE assets can be listed (business rule); filter to avoid user selecting DRAFT
  const { data: assetsData } = useAssets({ page_size: 100, ordering: 'name', status: 'ACTIVE' });
  
  const [formData, setFormData] = useState({
    asset_id: '',
    title: '',
    description: '',
    license_summary: '',
    pricing_model: PricingModel.FREE as PricingModel,
    price_amount: '',
    currency: 'USD',
    intended_use: [] as string[],
    restricted_use: [] as string[],
  });
  const [intendedUseInput, setIntendedUseInput] = useState('');
  const [restrictedUseInput, setRestrictedUseInput] = useState('');
  const [errors, setErrors] = useState<Record<string, string>>({});

  const validate = (): boolean => {
    const newErrors: Record<string, string> = {};
    
    if (!formData.asset_id.trim()) {
      newErrors.asset_id = 'Asset is required';
    }
    
    if (!formData.title.trim()) {
      newErrors.title = 'Title is required';
    }
    
    if (!formData.description.trim()) {
      newErrors.description = 'Description is required';
    }
    
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleAddIntendedUse = () => {
    if (intendedUseInput.trim() && !formData.intended_use.includes(intendedUseInput.trim())) {
      setFormData({
        ...formData,
        intended_use: [...formData.intended_use, intendedUseInput.trim()],
      });
      setIntendedUseInput('');
    }
  };

  const handleRemoveIntendedUse = (item: string) => {
    setFormData({
      ...formData,
      intended_use: formData.intended_use.filter((i) => i !== item),
    });
  };

  const handleAddRestrictedUse = () => {
    if (restrictedUseInput.trim() && !formData.restricted_use.includes(restrictedUseInput.trim())) {
      setFormData({
        ...formData,
        restricted_use: [...formData.restricted_use, restrictedUseInput.trim()],
      });
      setRestrictedUseInput('');
    }
  };

  const handleRemoveRestrictedUse = (item: string) => {
    setFormData({
      ...formData,
      restricted_use: formData.restricted_use.filter((i) => i !== item),
    });
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!validate()) {
      return;
    }

    try {
      // Ensure short_description is never empty (required by API)
      const shortDescription = formData.description.trim() || formData.title.trim();
      if (!shortDescription) {
        throw new Error('Description or title is required for listing creation');
      }
      
      const priceAmount = formData.price_amount.trim() ? parseFloat(formData.price_amount) : undefined;
      const listing = await createMutation.mutateAsync({
        asset_id: formData.asset_id.trim(),
        title: formData.title.trim(),
        short_description: shortDescription, // API requires short_description (non-empty)
        long_description: formData.description.trim() || undefined,
        pricing_model: formData.pricing_model,
        price_amount: priceAmount,
        currency: priceAmount ? formData.currency : undefined,
      });
      navigate(`/marketplace/listings/${listing.id}`);
    } catch {
      // Error handled by mutation
    }
  };

  return (
    <div className="listing-publish-page">
      <div className="listing-publish-header">
        <Button onClick={() => navigate('/marketplace')} variant="ghost">
          ← Back to Marketplace
        </Button>
        <h1>Publish Listing</h1>
      </div>

      {createMutation.isError && (
        <ErrorDisplay
          error={createMutation.error}
          title="Failed to create listing"
          onRetry={() => createMutation.reset()}
        />
      )}

      <form onSubmit={handleSubmit} className="listing-publish-form">
        <div className="form-section">
          <h2>Basic Information</h2>
          
          <div className="form-group">
            <label htmlFor="asset_id">
              Asset <span className="required">*</span>
            </label>
            <select
              id="asset_id"
              value={formData.asset_id}
              onChange={(e) => setFormData((prev) => ({ ...prev, asset_id: e.target.value }))}
              className={errors.asset_id ? 'error' : ''}
            >
              <option value="">Select an asset...</option>
              {assetsData?.results.map((asset) => (
                <option key={asset.id} value={asset.id}>
                  {asset.name} ({asset.key})
                </option>
              ))}
            </select>
            {errors.asset_id && <span className="error-message">{errors.asset_id}</span>}
          </div>

          <div className="form-group">
            <label htmlFor="title">
              Title <span className="required">*</span>
            </label>
            <input
              id="title"
              type="text"
              value={formData.title}
              onChange={(e) => setFormData((prev) => ({ ...prev, title: e.target.value }))}
              placeholder="Enter listing title"
              className={errors.title ? 'error' : ''}
            />
            {errors.title && <span className="error-message">{errors.title}</span>}
          </div>

          <div className="form-group">
            <label htmlFor="description">Description</label>
            <textarea
              id="description"
              value={formData.description}
              onChange={(e) => setFormData((prev) => ({ ...prev, description: e.target.value }))}
              rows={4}
              placeholder="Enter listing description..."
            />
          </div>

          <div className="form-group">
            <label htmlFor="license_summary">License Summary</label>
            <textarea
              id="license_summary"
              value={formData.license_summary}
              onChange={(e) => setFormData((prev) => ({ ...prev, license_summary: e.target.value }))}
              rows={3}
              placeholder="Enter license summary..."
            />
          </div>
        </div>

        <div className="form-section">
          <h2>Pricing</h2>
          
          <div className="form-group">
            <label htmlFor="pricing_model">Pricing Model</label>
            <select
              id="pricing_model"
              value={formData.pricing_model}
              onChange={(e) => setFormData((prev) => ({ ...prev, pricing_model: e.target.value as PricingModel }))}
            >
              <option value={PricingModel.FREE}>Free</option>
              <option value={PricingModel.FREE_AUTO_APPROVE}>Free (Auto-approve)</option>
              <option value={PricingModel.REQUEST_APPROVAL}>Request Approval</option>
            </select>
            <p className="form-help-text">
              {formData.pricing_model === PricingModel.FREE && 'Listing is free, requires approval'}
              {formData.pricing_model === PricingModel.FREE_AUTO_APPROVE && 'Listing is free, automatically approved'}
              {formData.pricing_model === PricingModel.REQUEST_APPROVAL && 'Listing requires approval for access'}
            </p>
          </div>

          <div className="form-group">
            <label htmlFor="price_amount">Price per Unit</label>
            <input
              id="price_amount"
              name="price_amount"
              type="number"
              min="0"
              step="0.01"
              value={formData.price_amount}
              onChange={(e) => setFormData((prev) => ({ ...prev, price_amount: e.target.value }))}
              placeholder="0.00 (leave empty for free)"
            />
          </div>

          <div className="form-group">
            <label htmlFor="currency">Currency</label>
            <select
              id="currency"
              name="currency"
              value={formData.currency}
              onChange={(e) => setFormData((prev) => ({ ...prev, currency: e.target.value }))}
            >
              <option value="USD">USD</option>
              <option value="EUR">EUR</option>
              <option value="GBP">GBP</option>
            </select>
          </div>
        </div>

        <div className="form-section">
          <h2>Usage Terms</h2>
          
          <div className="form-group">
            <label htmlFor="intended_use">Intended Use</label>
            <div className="tag-input-group">
              <input
                id="intended_use"
                type="text"
                value={intendedUseInput}
                onChange={(e) => setIntendedUseInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') {
                    e.preventDefault();
                    handleAddIntendedUse();
                  }
                }}
                placeholder="Enter intended use and press Enter"
              />
              <Button onClick={handleAddIntendedUse} variant="secondary">
                Add
              </Button>
            </div>
            {formData.intended_use.length > 0 && (
              <div className="tag-list">
                {formData.intended_use.map((item, idx) => (
                  <span key={idx} className="tag">
                    {item}
                    <button
                      type="button"
                      onClick={() => handleRemoveIntendedUse(item)}
                      className="tag-remove"
                    >
                      ×
                    </button>
                  </span>
                ))}
              </div>
            )}
          </div>

          <div className="form-group">
            <label htmlFor="restricted_use">Restricted Use</label>
            <div className="tag-input-group">
              <input
                id="restricted_use"
                type="text"
                value={restrictedUseInput}
                onChange={(e) => setRestrictedUseInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') {
                    e.preventDefault();
                    handleAddRestrictedUse();
                  }
                }}
                placeholder="Enter restricted use and press Enter"
              />
              <Button onClick={handleAddRestrictedUse} variant="secondary">
                Add
              </Button>
            </div>
            {formData.restricted_use.length > 0 && (
              <div className="tag-list">
                {formData.restricted_use.map((item, idx) => (
                  <span key={idx} className="tag">
                    {item}
                    <button
                      type="button"
                      onClick={() => handleRemoveRestrictedUse(item)}
                      className="tag-remove"
                    >
                      ×
                    </button>
                  </span>
                ))}
              </div>
            )}
          </div>
        </div>

        <div className="form-actions">
          <Button
 onClick={() => navigate('/marketplace')}
 variant="secondary"
 loading={createMutation.isPending}>
            Cancel
          </Button>
          <Button
 type="submit"
 variant="primary"
 loading={createMutation.isPending}>
            {createMutation.isPending ? (
              <>
                <LoadingSpinner size="small" />
                Creating...
              </>
            ) : (
              'Create Listing'
            )}
          </Button>
        </div>
      </form>
    </div>
  );
}
