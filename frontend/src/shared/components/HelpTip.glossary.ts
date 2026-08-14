/**
 * Jargon glossary — inline help content for HelpTip component (278.J.3).
 *
 * Each entry maps a term key to a 1-2 sentence explanation and an
 * optional "Learn more" link from ``docs/mvpdocs/concepts/``.
 */

export interface GlossaryEntry {
  /** 1-2 sentence plain-language explanation. */
  description: string;
  /** Optional deep-link for "Learn more". */
  learnMoreUrl?: string;
}

export const JARGON_GLOSSARY: Record<string, GlossaryEntry> = {
  // ── Data standards ──────────────────────────────────────────────────────
  ODCS: {
    description:
      'Open Data Contract Standard. Defines the schema, quality rules, and terms for a data product. Think of it as a machine-readable data agreement.',
    learnMoreUrl: 'https://opendatacontractstandard.org',
  },
  ODPS: {
    description:
      'Open Data Product Standard. Wraps an ODCS contract with pricing, marketplace metadata, and access methods. It turns a data contract into a sellable product.',
    learnMoreUrl: 'https://opendataproducts.org',
  },

  // ── Privacy & compliance ────────────────────────────────────────────────
  ROPA: {
    description:
      'Record of Processing Activities. A GDPR-required inventory of all data processing your organization does. The RoPA dashboard generates this from your configured purposes.',
  },
  DPIA: {
    description:
      'Data Protection Impact Assessment. A risk assessment required under GDPR before processing that could pose high risk to individuals. Run the DPIA wizard for high-risk assets.',
  },
  DSAR: {
    description:
      'Data Subject Access Request. A formal request from an individual to access, correct, or delete their personal data. Processed via the DSAR queue.',
  },

  // ── Security ────────────────────────────────────────────────────────────
  RLS: {
    description:
      'Row-Level Security. A database feature that automatically filters rows based on the current tenant. Ensures tenant A can never see tenant B\'s data, even if a query is miswritten.',
  },
  ABAC: {
    description:
      'Attribute-Based Access Control. Grants or denies access based on user attributes (role, department), resource attributes (classification, owner), and environment context. More flexible than simple role-based access.',
  },
  KYB: {
    description:
      'Know Your Business. Identity verification for organizations selling on the marketplace. Required before a provider can receive payments.',
  },
  KYC: {
    description:
      'Know Your Customer. Identity verification status for tenants. VERIFIED tenants have completed onboarding checks; UNVERIFIED tenants have limited marketplace access.',
  },

  // ── Data concepts ───────────────────────────────────────────────────────
  DQ: {
    description:
      'Data Quality. Automated checks that measure completeness, accuracy, consistency, and timeliness of your data. Run DQ scans to get a quality scorecard.',
  },
  DLQ: {
    description:
      'Dead Letter Queue. A holding area for messages or deliveries that failed after all retry attempts. Items in the DLQ need manual investigation.',
  },
  SPARQL: {
    description:
      'SPARQL Protocol and RDF Query Language. A query language for semantic (RDF) data. Use it to ask graph-based questions across linked datasets.',
  },
  SHACL: {
    description:
      'Shapes Constraint Language. A way to validate RDF data against a set of rules (shapes). Like a schema validator for semantic data.',
  },
  RDF: {
    description:
      'Resource Description Framework. A W3C standard for representing linked data as subject-predicate-object triples. Used by the semantic (Fuseki) engine.',
  },

  // ── Infrastructure ──────────────────────────────────────────────────────
  SSE: {
    description:
      'Server-Sent Events. A lightweight protocol where the server pushes real-time updates to the browser over a single HTTP connection. Used for notification streams.',
  },
  BaaS: {
    description:
      'Backend-as-a-Service. Lets external developers build apps on top of your data products using API keys, SDKs, and a developer portal.',
  },
  Prefect: {
    description:
      'A workflow orchestration engine that runs scheduled ingestions, exports, and data transformations. When you trigger a pipeline, Prefect executes it.',
  },

  // ── Plans & limits ──────────────────────────────────────────────────────
  'Plan tier': {
    description:
      'Your subscription level (FREE, PRO, ENTERPRISE). Each tier sets limits on how many assets, datasets, API calls, and other resources you can use. Upgrade anytime from Settings → Billing.',
  },
  'Plan limit': {
    description:
      'A cap on a specific resource (e.g., max 10 assets on FREE). When you reach 80%, you\'ll see a warning. At 100%, new operations are blocked until you upgrade or free up resources.',
  },

  // ── Marketplace ─────────────────────────────────────────────────────────
  'Marketplace listing': {
    description:
      'A published data product available for other tenants to discover and purchase. Listings include pricing, a data contract, and compliance status.',
  },
  'Compliance threshold': {
    description:
      'The maximum risk level your tenant accepts for marketplace listings. If a scan exceeds this threshold, the listing cannot be published without admin override.',
  },

  // ── General ─────────────────────────────────────────────────────────────
  Tenant: {
    description:
      'Your organization\'s isolated workspace in Meshant. Each tenant has its own users, data, plans, and settings. No tenant can access another tenant\'s data.',
  },
  Webhook: {
    description:
      'An HTTP callback that notifies your external system when events happen in Meshant (e.g., a new asset is created). Configure webhook URLs and event subscriptions.',
  },
  Idempotency: {
    description:
      'A safety mechanism that prevents duplicate operations when you retry a request. Even if you send the same request twice, the result is applied only once.',
  },

  // ── UX & Productivity (Phase 278) ──────────────────────────────────────────
  Recommendations: {
    description:
      'AI-powered suggestions for marketplace listings you might find useful. Shows "Trending in your domain" and "You might also like" based on your activity and listing popularity.',
  },
  'Trust signals': {
    description:
      'At-a-glance indicators on marketplace listing cards showing KYC verification status, compliance grade, sample data availability, and how recently the listing was updated.',
  },
  'Comparison view': {
    description:
      'A side-by-side tool that lets you select 2-3 marketplace listings and compare their schema, pricing, compliance, and sample data in a single view.',
  },
  'Saved search': {
    description:
      'Save your current marketplace filters as a named search. You can re-apply saved searches anytime and optionally get notified when new matching listings appear.',
  },
  'Quick preview': {
    description:
      'Instantly explore sample data, schema fields, and quality metrics before purchasing a marketplace listing. Available from any listing card or the detail page.',
  },
  'Product tour': {
    description:
      'A guided walkthrough that introduces key features based on your persona (Data Engineer, Compliance Officer, etc.). Available from the onboarding checklist or help menu.',
  },
  'Approval inbox': {
    description:
      'A unified queue showing all items waiting for your approval — access requests, DSARs, breach incidents, and DPIAs — with inline approve/reject actions.',
  },
  'Command palette': {
    description:
      'A keyboard-driven search bar (Cmd+K or Ctrl+K) that lets you jump to any page or run common actions without using the mouse. Fuzzy search finds what you need even if you don\'t know the exact name.',
  },
  'Bulk selection': {
    description:
      'Select multiple items in a list using checkboxes, then act on all of them at once — approve, reject, or compare. Saves time when processing many similar items.',
  },
  'Inline validation': {
    description:
      'Real-time form field checking that shows error hints as you type, without waiting for form submission. Uses a short delay (debounce) so it doesn\'t interrupt your typing flow.',
  },
};
