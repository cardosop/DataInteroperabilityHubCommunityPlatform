/**
 * Paid listing checkout: summary + Stripe card + terms + purchase API (402 / 3DS).
 */
import { Elements } from '@stripe/react-stripe-js';
import { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import type { Stripe } from '@stripe/stripe-js';
import { getStripe } from '../../../shared/config/stripe';
import { Breadcrumbs } from '../../../shared/components/Breadcrumbs';
import { Button } from '../../../shared/components/Button';
import { DetailPageSkeleton } from '../../../shared/components/skeletons/DetailPageSkeleton';
import { ErrorDisplay } from '../../../shared/components/ErrorDisplay';
import { useListing } from '../hooks/useListings';
import { orderService } from '../services/orderService';
import { PaymentForm } from './PaymentForm';
import './CheckoutPage.css';

function CheckoutInner({
  listingId,
  stripe,
}: {
  listingId: string;
  stripe: Stripe;
}) {
  const navigate = useNavigate();
  const [terms, setTerms] = useState(false);
  const [fatal, setFatal] = useState<string | null>(null);

  const runPurchase = async (paymentMethodId: string) => {
    setFatal(null);
    const result = await orderService.purchaseWithPayment({
      listing_id: listingId,
      payment_method: 'card',
      payment_method_details: { payment_method_id: paymentMethodId },
      gateway: 'stripe',
    });

    if (result.kind === 'success') {
      const oid = (result.data as { order?: { id: string } }).order?.id;
      if (oid) navigate(`/marketplace/orders/${oid}`);
      return;
    }

    const { error, paymentIntent } = await stripe.confirmCardPayment(result.client_secret);
    if (error) {
      setFatal(error.message || '3D Secure failed');
      return;
    }
    if (paymentIntent?.status === 'succeeded') {
      const confirmed = await orderService.confirmPayment(result.order_id);
      const oid = (confirmed as { order?: { id: string } }).order?.id || result.order_id;
      navigate(`/marketplace/orders/${oid}`);
    }
  };

  return (
    <>
      <label className="marketplace-checkout-terms">
        <input
          type="checkbox"
          checked={terms}
          onChange={(e) => setTerms(e.target.checked)}
        />{' '}
        I agree to the marketplace terms for this purchase.
      </label>
      {fatal && <p className="marketplace-payment-error">{fatal}</p>}
      <PaymentForm
        disabled={!terms}
        submitLabel="Complete purchase"
        onSubmitPaymentMethod={runPurchase}
      />
    </>
  );
}

export function CheckoutPage() {
  const { listingId } = useParams<{ listingId: string }>();
  const navigate = useNavigate();
  const { data: listing, isLoading, error, refetch } = useListing(listingId || null);
  const [stripe, setStripe] = useState<Stripe | null | undefined>(undefined);

  useEffect(() => {
    let cancelled = false;
    void getStripe().then((s) => {
      if (!cancelled) setStripe(s);
    });
    return () => {
      cancelled = true;
    };
  }, []);

  if (!listingId) {
    return <ErrorDisplay error="Missing listing" title="Checkout" />;
  }

  if (isLoading || stripe === undefined) {
    return <DetailPageSkeleton />;
  }

  if (error) {
    return <ErrorDisplay error={error} title="Failed to load listing" onRetry={() => refetch()} />;
  }

  if (!listing) {
    return <ErrorDisplay error="Listing not found" title="Checkout" />;
  }

  if (!stripe) {
    return (
      <div className="marketplace-checkout-page">
        <p>
          Stripe is not configured (set <code>VITE_STRIPE_PUBLISHABLE_KEY</code>). Paid checkout is
          unavailable in this environment.
        </p>
        <Button variant="ghost" onClick={() => navigate(-1)}>
          Back
        </Button>
      </div>
    );
  }

  const price = listing.price_amount != null ? Number(listing.price_amount) : 0;
  if (!(price > 0)) {
    return (
      <div className="marketplace-checkout-page">
        <p>This listing does not require payment. Use “Get Access” from the listing page.</p>
        <Button variant="ghost" onClick={() => navigate(`/marketplace/listings/${listingId}`)}>
          Back to listing
        </Button>
      </div>
    );
  }

  return (
    <div className="marketplace-checkout-page">
      <Breadcrumbs
        items={[
          { label: 'Home', href: '/' },
          { label: 'Marketplace', href: '/marketplace' },
          { label: listing.title || 'Checkout' },
        ]}
      />
      <h1>Checkout</h1>
      <div className="marketplace-checkout-summary">
        <h2>{listing.title || 'Listing'}</h2>
        <p>
          Total: {listing.currency || 'USD'} {price.toFixed(2)}
        </p>
      </div>
      <Elements stripe={stripe}>
        <CheckoutInner listingId={listingId} stripe={stripe} />
      </Elements>
    </div>
  );
}
