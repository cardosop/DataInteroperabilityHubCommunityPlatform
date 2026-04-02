/**
 * Card capture for marketplace checkout (Stripe Elements).
 */
import { CardElement, useElements, useStripe } from '@stripe/react-stripe-js';
import { useState } from 'react';
import { Button } from '../../../shared/components/Button';

const CARD_OPTIONS = {
  style: {
    base: {
      fontSize: '16px',
      color: '#1a1a2e',
      '::placeholder': { color: '#889' },
    },
    invalid: { color: '#c62828' },
  },
};

type PaymentFormProps = {
  disabled?: boolean;
  submitLabel?: string;
  onSubmitPaymentMethod: (paymentMethodId: string) => Promise<void>;
};

export function PaymentForm({
  disabled,
  submitLabel = 'Pay',
  onSubmitPaymentMethod,
}: PaymentFormProps) {
  const stripe = useStripe();
  const elements = useElements();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    if (!stripe || !elements || disabled) return;
    const card = elements.getElement(CardElement);
    if (!card) {
      setError('Card field not ready');
      return;
    }
    setBusy(true);
    try {
      const { error: pmError, paymentMethod } = await stripe.createPaymentMethod({
        type: 'card',
        card,
      });
      if (pmError || !paymentMethod) {
        setError(pmError?.message || 'Could not create payment method');
        return;
      }
      await onSubmitPaymentMethod(paymentMethod.id);
    } finally {
      setBusy(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="marketplace-payment-form">
      <div className="marketplace-card-element-wrap">
        <CardElement options={CARD_OPTIONS} />
      </div>
      {error && <p className="marketplace-payment-error">{error}</p>}
      <Button type="submit" variant="primary" disabled={!stripe || disabled || busy} loading={busy}>
        {submitLabel}
      </Button>
    </form>
  );
}
