# User Personas

**Last Updated**: 2025-01-10
**Version**: 2.1.0

---

## Overview

The Data Interoperability Hub serves **12 personas** (8 original + 4 new), each with distinct goals, responsibilities, and technical capabilities. This document provides comprehensive profiles for all personas, their role mappings, and how they interact with the platform.

**Key Principles:**
- **Multi-tenant isolation**: Each persona operates within tenant boundaries (except Platform Admin)
- **Role-based access control**: Permissions are granted through roles, not direct user attributes
- **Audit trails**: All actions are logged for compliance and debugging
- **API-first**: All personas can access functionality via APIs, with UI as a convenience layer

---

## Table of Contents

1. [Persona 1: Data Product Owner](#persona-1-data-product-owner)
2. [Persona 2: Data Engineer / Contract Author](#persona-2-data-engineer--contract-author)
3. [Persona 3: Compliance & Privacy Officer](#persona-3-compliance--privacy-officer)
4. [Persona 4: Data Consumer / Buyer](#persona-4-data-consumer--buyer)
5. [Persona 5: Tenant Admin](#persona-5-tenant-admin)
6. [Persona 6: Platform Admin / Marketplace Operator](#persona-6-platform-admin--marketplace-operator)
7. [Persona 7: External Developer / Integrator](#persona-7-external-developer--integrator)
8. [Persona 8: Auditor](#persona-8-auditor)
9. [Persona 9: Data Scientist / ML Engineer](#persona-9-data-scientist--ml-engineer) **NEW**
10. [Persona 10: Data Analyst](#persona-10-data-analyst) **NEW**
11. [Persona 11: Community Manager / Data Steward](#persona-11-community-manager--data-steward) **NEW**
12. [Persona 12: Data Mesh Domain Owner](#persona-12-data-mesh-domain-owner) **NEW**
13. [Role Mapping Matrix](#role-mapping-matrix)
14. [Access Control Summary](#access-control-summary)

---

## Persona 1: Data Product Owner

**Aliases**: Data Steward, Domain Data Owner, Data Product Manager
**Typical Role Mapping**: `DATA_PROVIDER` (sometimes `TENANT_ADMIN`)
**Seniority**: Mid to senior
**Technical Level**: Medium – understands data and schemas; not deeply into infrastructure/CLI

### Summary

Owns one or more datasets inside an organization and wants to publish them as **data products** in the hub, either for internal reuse (within the tenant) or for sale in the **marketplace**. Responsible for the meaning, quality, and lifecycle of the asset, but usually collaborates with data engineers for technical implementation.

They work primarily through the **web UI**, relying on the platform to enforce data contract standards, data quality, and compliance gates.

### Goals

- Turn internal datasets into **well-described, trustworthy and compliant data products**
- Publish assets to the **tenant catalog** and optionally to the **cross-tenant marketplace** ("on the shelf")
- **Publish assets to external data marketplaces** (Snowflake, AWS Data Exchange, Azure, GCP, etc.) via marketplace integration
- **Manage marketplace connections** to external platforms for asset distribution
- Keep contracts, documentation, and metadata **up to date across versions** (while the platform guarantees they stay `VALID`)
- Be confident that mandatory **data-quality** and **compliance** checks ran, and that everything is backed by audit logs

### Key Responsibilities / Tasks

#### Onboarding Flows

1. **Data First Flow**
   - Upload data file via browser (up to size limits) or via SDK/CLI (for larger files)
   - System infers schema and extracts sample
   - **NEW**: AI schema matching suggests field mappings
   - **NEW**: Auto-classification detects PII and categorizes data
   - System runs compliance validation (mandatory gate)
   - System runs basic data quality checks (`intake_basic`)
   - **NEW**: ML-based anomaly detection identifies quality issues
   - If checks fail: receive reports, correct/remediate data externally, retry
   - If checks pass: edit and refine contract in UI
   - Trigger DataContract CLI validation (lint + validate)
   - After successful validation: contract + dataset registered in catalog
   - Contract and asset mapped into semantic layer

2. **Contract First Flow**
   - Upload data contract file (ODCS or DataContract.com format)
   - System runs DataContract CLI validation
   - If errors: fix and re-run validation
   - After validation: upload data file
   - System validates data matches contract schema
   - System runs compliance and DQ checks
   - If checks pass: asset registered in catalog

3. **Contract Only Flow**
   - Upload contract without data (for external data sources)
   - System validates contract
   - Contract registered in catalog
   - Asset can reference external data source

#### Asset Management

- **Update Assets**: Update metadata, contracts, documentation
- **Version Management**: Create new versions, track version history
- **Quality Monitoring**: Monitor data quality scores, receive alerts
- **Compliance Monitoring**: Monitor compliance status, address violations
- **Marketplace Publishing**: Publish assets to marketplace with pricing models
- **NEW**: **Transformation Pipelines**: Create and manage transformation pipelines for assets
- **NEW**: **Social Features**: Respond to ratings and reviews, manage asset reputation
- **NEW**: **Data Mesh**: Configure domain ownership, manage domain-scoped assets

#### Marketplace Integration (External Marketplaces)

- **Create Marketplace Connections**: Set up connections to external marketplaces (Snowflake, AWS, Azure, GCP, Databricks, CKAN, etc.)
- **Test Connections**: Verify marketplace connection credentials and connectivity
- **PUSH Sync Operations**: Sync assets to external marketplaces for broader distribution
  - Select assets to publish
  - Configure sync options (metadata only, full sync, etc.)
  - Monitor sync job progress
  - Review sync results and errors
- **Manage Sync Jobs**: View, monitor, and cancel marketplace sync jobs
- **View Mappings**: Track mappings between Hub assets and external marketplace listings
- **Update Marketplace Listings**: Keep marketplace listings synchronized with Hub assets
- **Marketplace-Specific Configuration**: Configure marketplace-specific settings per platform

### Technical Capabilities

- **UI Access**: Full access to asset management UI
- **API Access**: Full access to asset APIs
- **SDK Access**: Can use SDKs for automation
- **CLI Access**: Limited (prefers UI)

### Pain Points

- Understanding technical contract details
- Waiting for quality/compliance checks
- Keeping contracts in sync with data changes
- Managing asset versions

### Success Metrics

- Asset onboarding time
- Contract validation success rate
- Quality score improvements
- Marketplace sales (if applicable)
- **External marketplace sync success rate**
- **Number of external marketplace connections**
- **Assets published to external marketplaces**

---

## Persona 2: Data Engineer / Contract Author

**Aliases**: Data Engineer, Contract Developer, Technical Data Owner
**Typical Role Mapping**: `DATA_PROVIDER`
**Seniority**: Mid to senior
**Technical Level**: High – comfortable with APIs, SDKs, CLI, infrastructure

### Summary

Technical implementer who creates contracts, sets up data pipelines, integrates external systems, and automates data operations. Works primarily through **APIs, SDKs, and CLI**, but also uses UI for complex operations.

### Goals

- Automate asset onboarding and management
- Integrate hub with external systems (CI/CD, data sources, BI tools)
- Create and validate contracts programmatically
- Set up scheduled ingestions
- **NEW**: Create and manage transformation pipelines
- **NEW**: Integrate AI/ML features into workflows
- **NEW**: Set up data virtualization and federation

### Key Responsibilities / Tasks

#### Contract Management

- Create contracts programmatically (API/SDK/CLI)
- Validate contracts in CI/CD pipelines
- Manage contract versions
- **NEW**: Use AI schema matching to generate contracts
- **NEW**: Integrate auto-classification into contract creation

#### Integration

- Set up scheduled ingestions
- Integrate with external data sources
- Set up CI/CD integration
- **NEW**: Create custom connectors
- **NEW**: Set up reverse ETL
- **NEW**: Integrate BI tools

#### Pipeline Management

- **NEW**: Create transformation pipelines
- **NEW**: Execute and monitor pipelines
- **NEW**: Integrate pipelines with asset lifecycle
- **NEW**: Set up data virtualization

### Technical Capabilities

- **UI Access**: Full access (for complex operations)
- **API Access**: Full access to all APIs
- **SDK Access**: Full access to all SDKs
- **CLI Access**: Full access to CLI tool

### Pain Points

- API documentation completeness
- Integration complexity
- Error handling
- Performance optimization

### Success Metrics

- Integration success rate
- Automation coverage
- Pipeline execution success rate
- Integration time

---

## Persona 3: Compliance & Privacy Officer

**Aliases**: Compliance Officer, Privacy Officer, Governance Officer
**Typical Role Mapping**: `AUDITOR` (read-only) or `TENANT_ADMIN` (with compliance permissions)
**Seniority**: Mid to senior
**Technical Level**: Low to medium – understands compliance requirements, not deeply technical

### Summary

Ensures data assets comply with regulations (GDPR, HIPAA, SOX, LGPD, CCPA) and organizational policies. Monitors compliance status, reviews reports, and manages access requests. Works primarily through **web UI dashboards and reports**.

### Goals

- Ensure all data assets comply with regulations
- Monitor compliance status across all assets
- Review and approve access requests
- Generate compliance reports for audits
- Identify and remediate compliance violations
- **NEW**: Configure automated compliance enforcement
- **NEW**: Manage GDPR right to be forgotten workflows
- **NEW**: Track and manage consent

### Key Responsibilities / Tasks

#### Compliance Monitoring

- View compliance status dashboard
- Generate compliance reports (GDPR, HIPAA, SOX, etc.)
- Receive alerts for compliance violations
- Monitor compliance trends over time
- **NEW**: Review AI auto-classification results for compliance
- **NEW**: Configure automated compliance rules

#### Access Management

- Review and approve/deny access requests
- Conduct periodic access certifications
- Review access logs for audit purposes
- Configure data masking rules based on classification
- **NEW**: Manage consent tracking and workflows

#### Policy Management

- Configure automatic data classification rules
- Configure data retention policies
- Configure fine-grained access control policies
- Configure compliance scanning rules
- **NEW**: Configure automated retention policies
- **NEW**: Set up GDPR deletion workflows

#### Audit & Reporting

- Review audit logs for all data operations
- Generate scheduled compliance reports
- Review and track compliance violations
- Track remediation of compliance issues
- **NEW**: Generate GDPR compliance reports
- **NEW**: Generate consent tracking reports

### Technical Capabilities

- **UI Access**: Full access to compliance dashboards and reports
- **API Access**: Limited (read-only for reports and logs)
- **SDK Access**: Limited (for report generation automation)
- **CLI Access**: None (prefers UI)

### Pain Points

- Understanding technical implementation details
- Navigating complex compliance reports
- Keeping up with changing regulations
- Proving compliance during audits

### Success Metrics

- Compliance pass rate
- Time to identify violations
- Access request processing time
- Audit report generation time

---

## Persona 4: Data Consumer / Buyer

**Aliases**: Data Consumer, Data Buyer, Data Analyst, Business User
**Typical Role Mapping**: `DATA_CONSUMER`
**Seniority**: Junior to senior
**Technical Level**: Low to medium – understands data needs, not deeply technical

### Summary

Discovers, evaluates, and accesses data assets for analysis, reporting, or integration. May purchase assets from marketplace or request access to internal assets. Works primarily through **web UI catalog and marketplace**.

### Goals

- Discover relevant data assets quickly
- Evaluate data quality and compliance before use
- Access data assets easily (download, API, or direct connection)
- Understand data lineage and dependencies
- Purchase data assets from marketplace (if applicable)
- **Discover and import assets from external data marketplaces** (Snowflake, AWS, Azure, GCP, etc.)
- **Access federated assets** imported from external marketplaces
- **NEW**: Use natural language search to find data
- **NEW**: Create transformation pipelines for data
- **NEW**: Rate and review assets
- **NEW**: Join data communities
- **NEW**: Query virtual datasets

### Key Responsibilities / Tasks

#### Discovery

- Browse tenant catalog for internal assets
- Browse marketplace for external assets
- **Browse external data marketplaces** via marketplace integration (Snowflake, AWS, Azure, GCP, etc.)
- Search assets by name, description, tags, domain
- **NEW**: Use natural language search ("show me customer data from last quarter")
- Filter assets by type, quality, compliance, domain
- Use semantic search for concept-based discovery
- **NEW**: Use asset recommendations

#### Evaluation

- Review asset metadata and documentation
- Review data quality scores and reports
- Review compliance status
- **NEW**: Preview data before purchase
- **NEW**: Review ratings and reviews
- **NEW**: View trust signals (quality SLAs, badges)

#### Access

- Request access to internal assets
- Purchase assets from marketplace
- Download purchased data
- Access data via API
- **NEW**: Execute transformation pipelines
- **NEW**: Query virtual datasets

#### Marketplace Integration (External Marketplaces)

- **PULL Sync Operations**: Discover and import assets from external marketplaces
  - Browse available listings in external marketplaces
  - Filter and search marketplace listings
  - Select listings to import
  - Configure import options (metadata only, full data, selective resources)
  - Monitor sync job progress
  - Review imported federated assets
- **Access Federated Assets**: Use assets imported from external marketplaces
  - Query federated assets with dual contracts (ODPS + ODCS)
  - Access marketplace resources
  - View marketplace metadata
- **View Mappings**: Track relationships between Hub assets and external marketplace listings

#### Collaboration

- **NEW**: Rate and review assets
- **NEW**: Comment on assets
- **NEW**: Join data communities
- **NEW**: Participate in discussions

### Technical Capabilities

- **UI Access**: Full access to catalog and marketplace
- **API Access**: Limited (for accessing purchased data)
- **SDK Access**: Limited (for data access)
- **CLI Access**: None (prefers UI)

### Pain Points

- Finding relevant assets
- Understanding data quality
- Approval delays
- **NEW**: Understanding transformation pipelines
- **NEW**: Using natural language search effectively

### Success Metrics

- Discovery time
- Purchase completion rate
- User satisfaction
- **NEW**: Transformation pipeline usage
- **NEW**: Social engagement (ratings, reviews)
- **External marketplace discovery success rate**
- **Federated assets imported from external marketplaces**
- **Usage of federated assets**

---

## Persona 5: Tenant Admin

**Aliases**: Organization Admin, Tenant Administrator
**Typical Role Mapping**: `TENANT_ADMIN`
**Seniority**: Mid to senior
**Technical Level**: Medium – understands administration, not deeply technical

### Summary

Manages tenant-level configuration, users, and settings. Ensures tenant compliance with platform policies. Works primarily through **web UI administration panels**.

### Goals

- Manage tenant users and roles
- Configure tenant settings
- Monitor tenant usage and costs
- Ensure tenant compliance
- **NEW**: Configure data mesh domains
- **NEW**: Set up advanced governance
- **NEW**: Monitor cost tracking
- **NEW**: Configure integration ecosystem

### Key Responsibilities / Tasks

#### User Management

- Onboard new users
- Assign roles and permissions
- Manage user access
- Deactivate users

#### Tenant Configuration

- Configure tenant settings
- Set up tenant policies
- Configure tenant branding
- **NEW**: Configure data mesh domains
- **NEW**: Set up federated governance

#### Monitoring

- Monitor tenant usage
- Monitor tenant costs
- **NEW**: Monitor cost tracking and optimization
- Generate tenant reports

#### Integration

- **NEW**: Install and configure connectors
- **NEW**: Set up BI tool integrations
- **NEW**: Configure reverse ETL

### Technical Capabilities

- **UI Access**: Full access to admin panels
- **API Access**: Full access to admin APIs
- **SDK Access**: Limited (for automation)
- **CLI Access**: Limited (for automation)

### Pain Points

- Managing large numbers of users
- Understanding platform policies
- Cost management
- **NEW**: Data mesh configuration complexity

### Success Metrics

- User onboarding time
- Tenant compliance rate
- Cost optimization
- **NEW**: Data mesh adoption

---

## Persona 6: Platform Admin / Marketplace Operator

**Aliases**: Platform Administrator, Marketplace Operator
**Typical Role Mapping**: `PLATFORM_ADMIN`
**Seniority**: Senior
**Technical Level**: High – understands platform infrastructure and operations

### Summary

Manages platform-wide configuration, monitors platform health, and operates the marketplace. Works through **web UI administration panels and APIs**.

### Goals

- Onboard new tenants
- Monitor platform health
- Manage marketplace operations (internal marketplace)
- **Manage external marketplace integrations** across all tenants
- **Monitor marketplace connection health** and sync job performance
- Configure platform settings
- **NEW**: Manage connector marketplace
- **NEW**: Configure advanced marketplace features
- **NEW**: Monitor data mesh topology
- **NEW**: Configure advanced observability

### Key Responsibilities / Tasks

#### Tenant Management

- Onboard new tenants
- Configure tenant settings
- Monitor tenant health
- Manage tenant billing

#### Marketplace Operations

- Manage marketplace listings (internal marketplace)
- Process marketplace orders (internal marketplace)
- Monitor marketplace health (internal marketplace)
- **NEW**: Manage connector marketplace
- **NEW**: Configure usage-based pricing
- **NEW**: Set up trust signals
- **NEW**: Configure data previews

#### External Marketplace Integration Management

- **Monitor Marketplace Connections**: Oversee all tenant marketplace connections
  - View connection status across all tenants
  - Monitor connection health and test results
  - Identify and resolve connection issues
  - Review connection usage statistics
- **Monitor Sync Jobs**: Track marketplace sync operations across platform
  - View all sync jobs (PUSH and PULL) across tenants
  - Monitor sync job success rates and performance
  - Identify and resolve sync job failures
  - Generate sync job reports and analytics
- **Marketplace Platform Management**: Manage supported marketplace platforms
  - Configure marketplace platform settings
  - Manage marketplace connector availability
  - Monitor marketplace API rate limits and quotas
  - Coordinate with marketplace platform providers
- **Troubleshooting and Support**: Provide support for marketplace integration issues
  - Investigate connection failures
  - Resolve sync job errors
  - Provide guidance on marketplace-specific requirements
  - Coordinate with marketplace platform support teams

#### Platform Monitoring

- Monitor platform health
- Monitor platform performance
- **NEW**: Monitor data mesh topology
- **NEW**: Monitor reliability scores
- **NEW**: Track platform costs
- **NEW**: Set up predictive alerts

#### Platform Configuration

- Configure platform settings
- Manage platform policies
- **NEW**: Configure advanced observability
- **NEW**: Manage plugin marketplace

### Technical Capabilities

- **UI Access**: Full access to all admin panels
- **API Access**: Full access to all APIs
- **SDK Access**: Full access to all SDKs
- **CLI Access**: Full access to CLI tool

### Pain Points

- Managing platform scale
- Monitoring complexity
- Marketplace operations
- **NEW**: Data mesh topology management

### Success Metrics

- Platform uptime
- Marketplace transaction volume (internal marketplace)
- Tenant satisfaction
- **NEW**: Data mesh adoption
- **NEW**: Connector marketplace usage
- **External marketplace connection success rate**
- **Marketplace sync job success rate**
- **Number of active marketplace connections**
- **Assets synced to/from external marketplaces**

---

## Persona 7: External Developer / Integrator

**Aliases**: Developer, Integrator, API User
**Typical Role Mapping**: `DATA_CONSUMER` or `DATA_PROVIDER` (depending on use case)
**Seniority**: Junior to senior
**Technical Level**: High – comfortable with APIs, SDKs, CLI, programming

### Summary

Builds integrations between the hub and external systems. Uses APIs, SDKs, and CLI to automate operations. Works primarily through **APIs, SDKs, and CLI**.

### Goals

- Integrate hub with external systems
- Automate data operations
- Build custom applications
- **Integrate with external data marketplaces** via marketplace integration APIs
- **Automate marketplace sync operations** (PUSH and PULL)
- **Build custom marketplace connectors** for unsupported platforms
- **NEW**: Use natural language search API
- **NEW**: Integrate transformation pipeline API
- **NEW**: Build custom connectors
- **NEW**: Use plugin system
- **NEW**: Access developer portal

### Key Responsibilities / Tasks

#### Integration Development

- Review API documentation
- Obtain API credentials
- Initialize SDK/client
- Implement integrations
- **NEW**: Use natural language search API
- **NEW**: Integrate transformation pipeline API
- **NEW**: Build custom connectors

#### Marketplace Integration Development

- **Marketplace Connection Management**: Create, update, test, and delete marketplace connections via API
  - Use `/api/v1/integrations/marketplace/connections/` endpoints
  - Configure marketplace-specific connection parameters
  - Test connection credentials programmatically
- **Sync Job Automation**: Automate marketplace sync operations
  - Create PUSH sync jobs to publish assets to external marketplaces
  - Create PULL sync jobs to import assets from external marketplaces
  - Monitor sync job progress via API
  - Handle sync job errors and retries
  - Cancel sync jobs programmatically
- **Mapping Management**: Track and manage asset-to-marketplace mappings
  - Query mappings between Hub assets and marketplace listings
  - Monitor sync status via mappings
- **Custom Connector Development**: Build connectors for unsupported marketplaces
  - Implement `MarketplaceConnector` interface
  - Register custom connectors via factory pattern
  - Test and validate custom connectors

#### Plugin Development

- **NEW**: Browse plugin marketplace
- **NEW**: Install plugins
- **NEW**: Create custom plugins
- **NEW**: Publish plugins to marketplace

#### Developer Resources

- **NEW**: Access developer portal
- **NEW**: Use sandbox environment
- **NEW**: Review code examples
- **NEW**: Follow tutorials

### Technical Capabilities

- **UI Access**: Limited (for testing)
- **API Access**: Full access to all APIs
- **SDK Access**: Full access to all SDKs (Python, JavaScript, R, Go)
- **CLI Access**: Full access to CLI tool

### Pain Points

- API documentation completeness
- Authentication complexity
- Error handling
- **NEW**: Plugin development complexity

### Success Metrics

- Integration success rate
- Integration time
- Developer satisfaction
- **NEW**: Plugin adoption
- **Marketplace integration API usage**
- **Custom connector development success**
- **Marketplace sync automation coverage**

---

## Persona 8: Auditor

**Aliases**: Internal Auditor, External Auditor, Compliance Auditor
**Typical Role Mapping**: `AUDITOR` (read-only)
**Seniority**: Mid to senior
**Technical Level**: Low to medium – understands audit requirements, not deeply technical

### Summary

Reviews system audit logs, generates audit reports, and verifies compliance. Works primarily through **web UI audit dashboards and reports**.

### Goals

- Review audit logs for compliance
- Generate audit reports
- Verify compliance with regulations
- Export audit data for external analysis
- **NEW**: Review data mesh governance
- **NEW**: Audit transformation pipelines
- **NEW**: Review social feature activity

### Key Responsibilities / Tasks

#### Audit Review

- Review audit logs
- Generate audit reports
- Export audit data
- **NEW**: Review data mesh governance
- **NEW**: Audit transformation pipelines
- **NEW**: Review social feature activity

#### Compliance Verification

- Verify compliance with regulations
- Review access logs
- Review policy compliance
- **NEW**: Verify data mesh domain compliance

### Technical Capabilities

- **UI Access**: Full access to audit dashboards
- **API Access**: Read-only access to audit APIs
- **SDK Access**: None (prefers UI)
- **CLI Access**: None (prefers UI)

### Pain Points

- Navigating audit logs
- Generating comprehensive reports
- Understanding technical details
- **NEW**: Understanding data mesh governance

### Success Metrics

- Audit report generation time
- Compliance verification rate
- Audit coverage

---

## Persona 9: Data Scientist / ML Engineer **NEW**

**Aliases**: ML Engineer, Data Scientist, AI Engineer
**Typical Role Mapping**: `DATA_PROVIDER` or `DATA_CONSUMER` (depending on use case)
**Seniority**: Mid to senior
**Technical Level**: High – expert in ML/AI, data science, programming

### Summary

Uses AI/ML features to build models, analyze data patterns, and leverage intelligent features. Works through **APIs, SDKs, and UI** for different tasks.

### Goals

- Use natural language search to discover data
- Leverage AI schema matching for data integration
- Use ML-based anomaly detection for data quality
- Configure recommendation engines
- Train and deploy ML models
- Analyze data patterns using AI/ML

### Key Responsibilities / Tasks

#### Natural Language Search

- Use natural language queries to discover data
- Review query interpretations
- Refine queries based on results
- Save and reuse queries

#### Schema Matching

- Use AI schema matching for data integration
- Review matching suggestions with confidence scores
- Accept/reject/modify mappings
- Integrate schema matching into workflows

#### ML Model Management

- Train ML models for anomaly detection
- Deploy ML models for quality checks
- Monitor model performance
- Update models based on feedback

#### Recommendation Engine

- Configure recommendation algorithms
- Tune recommendation parameters
- Monitor recommendation performance
- Analyze recommendation feedback

#### Auto-Classification

- Review auto-classification results
- Validate PII detection
- Improve classification models
- Configure classification rules

### Technical Capabilities

- **UI Access**: Full access to AI/ML features
- **API Access**: Full access to AI/ML APIs
- **SDK Access**: Full access to all SDKs
- **CLI Access**: Full access to CLI tool

### Pain Points

- ML model training time
- Model accuracy
- Integration complexity
- Cost management (LLM API costs)

### Success Metrics

- Model accuracy
- Query success rate
- Schema matching accuracy
- Recommendation relevance

---

## Persona 10: Data Analyst **NEW**

**Aliases**: Business Analyst, Data Analyst, Analytics User
**Typical Role Mapping**: `DATA_CONSUMER`
**Seniority**: Junior to senior
**Technical Level**: Medium – understands data analysis, SQL, not deeply technical

### Summary

Uses transformation pipelines, data wrangling, and virtualization to analyze data. Works primarily through **web UI** for visual tools, **APIs** for programmatic access.

### Goals

- Create transformation pipelines for data analysis
- Wrangle data interactively
- Query virtual datasets
- Execute federated queries
- Analyze data across sources

### Key Responsibilities / Tasks

#### Transformation Pipelines

- Create transformation pipelines using visual builder
- Configure transformation nodes
- Execute pipelines
- Monitor pipeline execution
- Review transformation results

#### Data Wrangling

- Clean data interactively
- Perform column operations (split, merge, rename, type conversion)
- Perform row operations (filter, sort, deduplicate)
- Preview wrangling results
- Save wrangling history

#### Virtualization

- Create virtual datasets
- Query virtual datasets
- Execute federated queries
- Monitor query performance
- Cache query results

#### Analysis

- Analyze transformed data
- Export analysis results
- Share analysis with team
- **NEW**: Use natural language search for data discovery

### Technical Capabilities

- **UI Access**: Full access to transformation and virtualization UI
- **API Access**: Full access to transformation and virtualization APIs
- **SDK Access**: Limited (for automation)
- **CLI Access**: Limited (for automation)

### Pain Points

- Pipeline complexity
- Query performance
- Data quality issues
- Understanding virtualization

### Success Metrics

- Pipeline execution success rate
- Query performance
- Analysis completion time
- User satisfaction

---

## Persona 11: Community Manager / Data Steward **NEW**

**Aliases**: Community Manager, Data Steward, Social Manager
**Typical Role Mapping**: `DATA_PROVIDER` or `TENANT_ADMIN`
**Seniority**: Mid to senior
**Technical Level**: Low to medium – understands community management, not deeply technical

### Summary

Manages social features, communities, data stewardship, and collaboration. Works primarily through **web UI** for community management.

### Goals

- Manage data communities
- Moderate reviews and ratings
- Assign data stewards
- Manage activity feeds
- Foster collaboration

### Key Responsibilities / Tasks

#### Community Management

- Create and manage data communities
- Manage community membership
- Moderate community discussions
- Manage community knowledge base

#### Review Moderation

- Moderate asset reviews
- Approve/reject reviews
- Manage review helpfulness voting
- Handle review disputes

#### Data Stewardship

- Assign data stewards to assets
- Manage steward responsibilities
- Monitor steward activity
- Generate stewardship reports

#### Activity Management

- Monitor activity feeds
- Filter and search activities
- Manage activity notifications
- Generate activity reports

### Technical Capabilities

- **UI Access**: Full access to social and community features
- **API Access**: Limited (for automation)
- **SDK Access**: None (prefers UI)
- **CLI Access**: None (prefers UI)

### Pain Points

- Managing large communities
- Review moderation workload
- Activity feed management
- Steward assignment

### Success Metrics

- Community engagement
- Review moderation time
- Steward assignment coverage
- Activity feed usage

---

## Persona 12: Data Mesh Domain Owner **NEW**

**Aliases**: Domain Owner, Mesh Domain Manager
**Typical Role Mapping**: `DATA_PROVIDER` or `TENANT_ADMIN`
**Seniority**: Senior
**Technical Level**: Medium to high – understands data mesh architecture, governance

### Summary

Manages data mesh domains, federated governance, and domain topology. Works through **web UI** for domain management and **APIs** for automation.

### Goals

- Create and manage data mesh domains
- Configure federated governance
- Manage domain topology
- Assign domain ownership
- Monitor domain health

### Key Responsibilities / Tasks

#### Domain Management

- Create data mesh domains
- Define domain boundaries
- Assign domain ownership
- Manage domain-scoped assets
- Monitor domain health

#### Federated Governance

- Configure domain-specific policies
- Apply federated governance rules
- Monitor policy compliance
- Generate governance reports

#### Topology Management

- Visualize mesh topology
- Manage domain relationships
- Monitor topology health
- Update topology as needed

#### Domain Operations

- Transfer asset ownership between domains
- Migrate assets to domains
- Configure domain infrastructure
- Monitor domain costs

### Technical Capabilities

- **UI Access**: Full access to data mesh UI
- **API Access**: Full access to data mesh APIs
- **SDK Access**: Full access to SDKs
- **CLI Access**: Full access to CLI tool

### Pain Points

- Domain boundary definition
- Federated governance complexity
- Topology management
- Asset ownership transfer

### Success Metrics

- Domain creation time
- Governance compliance rate
- Topology health
- Asset ownership accuracy

---

## Role Mapping Matrix

| Persona | Primary Role | Secondary Roles | Access Level |
|---------|-------------|-----------------|--------------|
| Data Product Owner | `DATA_PROVIDER` | `TENANT_ADMIN` | Full (tenant-scoped) |
| Data Engineer | `DATA_PROVIDER` | - | Full (tenant-scoped) |
| Compliance Officer | `AUDITOR` | `TENANT_ADMIN` | Read-only or Full (tenant-scoped) |
| Data Consumer | `DATA_CONSUMER` | - | Limited (consumer access) |
| Tenant Admin | `TENANT_ADMIN` | - | Full (tenant-scoped) |
| Platform Admin | `PLATFORM_ADMIN` | - | Full (platform-wide) |
| External Developer | `DATA_CONSUMER` or `DATA_PROVIDER` | - | Varies by use case |
| Auditor | `AUDITOR` | - | Read-only |
| Data Scientist / ML Engineer | `DATA_PROVIDER` or `DATA_CONSUMER` | - | Varies by use case |
| Data Analyst | `DATA_CONSUMER` | - | Limited (consumer access) |
| Community Manager | `DATA_PROVIDER` or `TENANT_ADMIN` | - | Full (tenant-scoped) |
| Data Mesh Domain Owner | `DATA_PROVIDER` or `TENANT_ADMIN` | - | Full (domain-scoped) |

---

## Access Control Summary

### UI Access

- **Full Access**: Data Product Owner, Data Engineer, Tenant Admin, Platform Admin, Data Scientist, Data Analyst, Community Manager, Data Mesh Domain Owner
- **Limited Access**: Data Consumer, External Developer
- **Read-Only Access**: Compliance Officer, Auditor

### API Access

- **Full Access**: Data Engineer, Platform Admin, External Developer, Data Scientist, Data Analyst, Data Mesh Domain Owner
- **Limited Access**: Data Product Owner, Tenant Admin, Community Manager
- **Read-Only Access**: Compliance Officer, Auditor, Data Consumer

### SDK Access

- **Full Access**: Data Engineer, Platform Admin, External Developer, Data Scientist, Data Analyst, Data Mesh Domain Owner
- **Limited Access**: Data Product Owner, Tenant Admin
- **No Access**: Compliance Officer, Auditor, Data Consumer, Community Manager

### CLI Access

- **Full Access**: Data Engineer, Platform Admin, External Developer, Data Scientist, Data Analyst, Data Mesh Domain Owner
- **Limited Access**: Data Product Owner, Tenant Admin
- **No Access**: Compliance Officer, Auditor, Data Consumer, Community Manager

---

**Last Updated**: 2025-01-10
**Version**: 2.1.0 (Added marketplace integration capabilities to Data Product Owner, Data Consumer, External Developer, and Platform Administrator personas)

