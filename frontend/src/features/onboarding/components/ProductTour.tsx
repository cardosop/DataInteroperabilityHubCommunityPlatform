/**
 * Phase 278.B.1 — First-login product tour with persona-aware copy.
 *
 * 5-step overlay: Assets, Contracts, Marketplace, Compliance, Help.
 * State persisted in localStorage + backend User.has_seen_tour.
 * Persona-aware: DE sees ingestion flow, DPO sees GDPR, CPO sees billing.
 */
import { useState, useCallback, type FC } from 'react';
import './ProductTour.css';

type TourStep = 'assets' | 'contracts' | 'marketplace' | 'compliance' | 'help';

interface TourStepDef {
  key: TourStep;
  title: string;
  description: string;
  highlightSelector?: string;
}

const TOUR_STEPS: Record<string, TourStepDef[]> = {
  default: [
    {
      key: 'assets',
      title: 'Your Assets',
      description: 'Upload, organize, and manage your data assets. Every file and dataset lives here.',
    },
    {
      key: 'contracts',
      title: 'Data Contracts',
      description: 'Define ODPS or ODCS contracts that describe your data structure and quality rules.',
    },
    {
      key: 'marketplace',
      title: 'Marketplace',
      description: 'Browse listings, place orders, publish your own data products for other tenants.',
    },
    {
      key: 'compliance',
      title: 'Compliance',
      description: 'Run automated DQ and compliance scans. Monitor GDPR, CCPA, and custom regulations.',
    },
    {
      key: 'help',
      title: 'Help & Support',
      description: 'Access runbooks, docs, and support. Press ? for keyboard shortcuts.',
    },
  ],
  DE: [
    {
      key: 'assets',
      title: 'Ingest Your Data',
      description: 'Upload files, configure scheduled ingestions, and create data assets.',
    },
    {
      key: 'contracts',
      title: 'Validate Contracts',
      description: 'Create ODPS/ODCS contracts, run DQ checks, and validate schema consistency.',
    },
    {
      key: 'marketplace',
      title: 'Publish to Marketplace',
      description: 'Publish your validated assets as marketplace listings for other tenants to discover.',
    },
    {
      key: 'compliance',
      title: 'Monitor Quality',
      description: 'Track DQ scores, compliance status, and pipeline health across all your assets.',
    },
    {
      key: 'help',
      title: 'Pipeline Runbooks',
      description: 'Find ingestion troubleshooting guides and scheduled-job documentation.',
    },
  ],
  DPO: [
    {
      key: 'assets',
      title: 'Asset Inventory',
      description: 'Audit all data assets across your tenant, including retention policies and classifications.',
    },
    {
      key: 'contracts',
      title: 'Contract Review',
      description: 'Review data contracts for GDPR alignment — purposes, retention, third-party transfers.',
    },
    {
      key: 'marketplace',
      title: 'Marketplace Oversight',
      description: 'Monitor published listings for compliance with your data-sharing policies.',
    },
    {
      key: 'compliance',
      title: 'Your Compliance Hub',
      description: 'Run DSARs, manage DPIAs, track breach incidents, and generate RoPA reports.',
    },
    {
      key: 'help',
      title: 'Compliance Runbooks',
      description: 'Access GDPR response procedures and regulatory notification templates.',
    },
  ],
  CPO: [
    {
      key: 'assets',
      title: 'Platform Inventory',
      description: 'Overview of all tenant assets — data volume, type distribution, growth trends.',
    },
    {
      key: 'contracts',
      title: 'Contract Health',
      description: 'Contract compliance status across tenants — identify risk before it impacts revenue.',
    },
    {
      key: 'marketplace',
      title: 'Marketplace Performance',
      description: 'Listing volume, order conversion, revenue trends, and provider onboarding.',
    },
    {
      key: 'compliance',
      title: 'Regulatory Readiness',
      description: 'At-a-glance GDPR, CCPA, and LGPD posture across all tenants.',
    },
    {
      key: 'help',
      title: 'Cost & Billing',
      description: 'Cost overview dashboard — per-tenant, per-feature breakdown with MoM trends.',
    },
  ],
};

function isDismissed(): boolean {
  try {
    return localStorage.getItem('meshant.tour.completed') === 'true';
  } catch {
    return false;
  }
}

function markDismissed(): void {
  try {
    localStorage.setItem('meshant.tour.completed', 'true');
  } catch {
    // noop
  }
}

export const ProductTour: FC<{ persona?: string; onComplete?: () => void }> = ({
  persona = 'default',
  onComplete,
}) => {
  const [currentStep, setCurrentStep] = useState(0);
  const [dismissed, setDismissed] = useState(isDismissed);

  const steps = TOUR_STEPS[persona] ?? TOUR_STEPS.default;
  const step = steps[currentStep];
  const isLast = currentStep === steps.length - 1;

  const handleNext = useCallback(() => {
    if (isLast) {
      markDismissed();
      setDismissed(true);
      onComplete?.();
    } else {
      setCurrentStep((s) => s + 1);
    }
  }, [isLast, onComplete]);

  const handleSkip = useCallback(() => {
    markDismissed();
    setDismissed(true);
    onComplete?.();
  }, [onComplete]);

  if (dismissed) return null;

  return (
    <div className="product-tour-overlay" role="dialog" aria-label="Product tour" data-testid="product-tour">
      <div className="product-tour-card">
        <div className="product-tour-progress">
          {steps.map((_, i) => (
            <span
              key={i}
              className={`product-tour-dot ${i === currentStep ? 'active' : ''} ${i < currentStep ? 'done' : ''}`}
            />
          ))}
        </div>
        <h2 className="product-tour-title">{step.title}</h2>
        <p className="product-tour-desc">{step.description}</p>
        <div className="product-tour-actions">
          <button
            type="button"
            className="product-tour-btn product-tour-btn--skip"
            onClick={handleSkip}
          >
            Skip tour
          </button>
          <button
            type="button"
            className="product-tour-btn product-tour-btn--next"
            onClick={handleNext}
            data-testid="tour-next"
          >
            {isLast ? 'Got it!' : 'Next'}
          </button>
        </div>
      </div>
    </div>
  );
};
