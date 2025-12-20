# User Journeys

**Last Updated**: 2025-12-13  
**Version**: 2.0.0

---

## Overview

This document provides detailed user journey maps for all 12 personas. The platform now supports **82 total journeys** (37 original + 45 new) covering all features including the 10 strategic differentiators.

**Journey Statistics**:
- **Total Journeys**: 82
- **Total Steps**: ~600+
- **Average Steps per Journey**: ~7
- **Target Completion Rate**: 100%
- **Target Success Rate**: 95%+

---

## Table of Contents

1. [Data Product Owner Journeys](#data-product-owner-journeys) - 14 journeys (6 original + 8 new)
2. [Data Engineer Journeys](#data-engineer-journeys) - 13 journeys (6 original + 7 new)
3. [Compliance Officer Journeys](#compliance-officer-journeys) - 10 journeys (5 original + 5 new)
4. [Data Consumer Journeys](#data-consumer-journeys) - 13 journeys (5 original + 8 new)
5. [Tenant Admin Journeys](#tenant-admin-journeys) - 8 journeys (4 original + 4 new)
6. [Platform Admin Journeys](#platform-admin-journeys) - 9 journeys (4 original + 5 new)
7. [External Developer Journeys](#external-developer-journeys) - 9 journeys (4 original + 5 new)
8. [Auditor Journeys](#auditor-journeys) - 6 journeys (3 original + 3 new)
9. [Data Scientist Journeys](#data-scientist-journeys) - 5 journeys (NEW)
10. [Data Analyst Journeys](#data-analyst-journeys) - 4 journeys (NEW)
11. [Community Manager Journeys](#community-manager-journeys) - 4 journeys (NEW)
12. [Data Mesh Domain Owner Journeys](#data-mesh-domain-owner-journeys) - 5 journeys (NEW)
13. [Journey Map Matrix](#journey-map-matrix)

---

## Data Product Owner Journeys

### JOURNEY-DPO-001: Onboard New Asset via Data-First Flow

**Journey ID**: JOURNEY-DPO-001  
**Title**: Onboard New Asset via Data-First Flow  
**Persona**: Data Product Owner  
**Goal**: Turn a data file into a validated, quality-checked, compliant data product

**Steps**:
1. Create asset (draft)
2. Upload file
3. Create dataset (triggers schema inference)
4. **NEW**: AI schema matching suggests field mappings
5. **NEW**: Auto-classification detects PII and categorizes data
6. Run compliance check
7. Run DQ check
8. **NEW**: ML-based anomaly detection identifies quality issues
9. Create contract
10. Activate asset

**Success Criteria**:
- Asset created in DRAFT status
- File uploaded successfully
- Schema inferred from file
- **NEW**: AI schema matching suggestions provided
- **NEW**: Auto-classification completed
- Compliance check passes
- DQ check passes
- **NEW**: ML anomaly detection completed
- Contract created and linked
- Asset activated (status = ACTIVE)

**Performance Targets**:
- Total duration: < 5 minutes
- File upload: < 30 seconds
- Schema inference: < 10 seconds
- **NEW**: AI schema matching: < 15 seconds
- **NEW**: Auto-classification: < 20 seconds
- Compliance check: < 60 seconds
- DQ check: < 60 seconds
- **NEW**: ML anomaly detection: < 30 seconds

---

### JOURNEY-DPO-002: Publish Asset to Marketplace

**Journey ID**: JOURNEY-DPO-002  
**Title**: Publish Asset to Marketplace  
**Persona**: Data Product Owner  
**Goal**: Publish an active asset to the marketplace

**Steps**:
1. Verify asset is active
2. Check marketplace eligibility
3. **NEW**: Validate transformation pipelines (if applicable)
4. Create marketplace listing
5. **NEW**: Configure pricing model (static, usage-based, subscription)
6. **NEW**: Set up data preview
7. **NEW**: Configure trust signals (quality SLAs, badges)
8. Publish listing

**Success Criteria**:
- Asset is in ACTIVE status
- Asset passes eligibility checks
- **NEW**: Transformation pipelines validated (if applicable)
- Listing created successfully
- **NEW**: Pricing model configured
- **NEW**: Data preview configured
- **NEW**: Trust signals configured
- Listing published (status = PUBLISHED)

---

### JOURNEY-DPO-007: Use AI Schema Matching for Asset Creation **NEW**

**Journey ID**: JOURNEY-DPO-007  
**Title**: Use AI Schema Matching for Asset Creation  
**Persona**: Data Product Owner  
**Goal**: Use AI-powered schema matching to create contracts faster

**Steps**:
1. Upload data file
2. System infers schema
3. **NEW**: AI schema matching analyzes schema
4. **NEW**: Review suggested field mappings with confidence scores
5. **NEW**: Accept/reject/modify mappings
6. **NEW**: System generates contract draft with mappings
7. Review and refine contract
8. Validate contract
9. Activate asset

**Success Criteria**:
- AI schema matching completed
- Mappings suggested with confidence scores
- User accepts/rejects mappings
- Contract draft generated
- Contract validated
- Asset activated

**Performance Targets**:
- Total duration: < 3 minutes
- AI schema matching: < 15 seconds
- Mapping review: < 1 minute
- Contract generation: < 10 seconds

---

### JOURNEY-DPO-008: Create Transformation Pipeline for Asset **NEW**

**Journey ID**: JOURNEY-DPO-008  
**Title**: Create Transformation Pipeline for Asset  
**Persona**: Data Product Owner  
**Goal**: Create a transformation pipeline to transform asset data

**Steps**:
1. Select asset
2. Navigate to transformation section
3. Create new pipeline
4. **NEW**: Design pipeline using visual builder (drag-and-drop nodes)
5. **NEW**: Configure transformation nodes (filter, join, aggregate, transform)
6. **NEW**: Validate pipeline
7. **NEW**: Preview transformation results
8. **NEW**: Save pipeline
9. **NEW**: Execute pipeline
10. **NEW**: Review transformation results
11. **NEW**: Sync results with asset

**Success Criteria**:
- Pipeline created
- Pipeline validated
- Preview generated
- Pipeline executed successfully
- Results synced with asset

**Performance Targets**:
- Total duration: < 10 minutes
- Pipeline design: < 5 minutes
- Validation: < 10 seconds
- Preview: < 30 seconds
- Execution: < 5 minutes (depends on data size)

---

### JOURNEY-DPO-009: Manage Asset Ratings and Reviews **NEW**

**Journey ID**: JOURNEY-DPO-009  
**Title**: Manage Asset Ratings and Reviews  
**Persona**: Data Product Owner  
**Goal**: Manage ratings and reviews for owned assets

**Steps**:
1. Navigate to asset details
2. **NEW**: View ratings and reviews section
3. **NEW**: Review ratings (1-5 stars)
4. **NEW**: Read reviews
5. **NEW**: Respond to reviews (if needed)
6. **NEW**: View asset quality score impact
7. **NEW**: Moderate reviews (if has permissions)

**Success Criteria**:
- Ratings and reviews displayed
- Quality score updated based on ratings
- Reviews can be responded to
- Moderation works (if applicable)

---

### JOURNEY-DPO-010: Publish Asset with Usage-Based Pricing **NEW**

**Journey ID**: JOURNEY-DPO-010  
**Title**: Publish Asset with Usage-Based Pricing  
**Persona**: Data Product Owner  
**Goal**: Publish asset with usage-based pricing model

**Steps**:
1. Select asset to publish
2. Navigate to marketplace publishing
3. **NEW**: Select pricing model (usage-based)
4. **NEW**: Configure usage tiers (per-query, per-GB)
5. **NEW**: Set pricing rates
6. **NEW**: Configure billing settings
7. Create listing
8. Publish listing

**Success Criteria**:
- Usage-based pricing configured
- Pricing tiers set
- Billing settings configured
- Listing published

---

### JOURNEY-DPO-011: Assign Data Stewards **NEW**

**Journey ID**: JOURNEY-DPO-011  
**Title**: Assign Data Stewards  
**Persona**: Data Product Owner  
**Goal**: Assign data stewards to manage assets

**Steps**:
1. Navigate to asset details
2. **NEW**: Navigate to stewardship section
3. **NEW**: Assign stewards
4. **NEW**: Configure steward permissions
5. **NEW**: Notify stewards
6. **NEW**: Monitor steward activity

**Success Criteria**:
- Stewards assigned
- Permissions configured
- Stewards notified
- Activity tracked

---

### JOURNEY-DPO-012: Join Data Community **NEW**

**Journey ID**: JOURNEY-DPO-012  
**Title**: Join Data Community  
**Persona**: Data Product Owner  
**Goal**: Join a data community for collaboration

**Steps**:
1. **NEW**: Browse data communities
2. **NEW**: View community details
3. **NEW**: Join community
4. **NEW**: Participate in discussions
5. **NEW**: Share assets in community
6. **NEW**: Access community knowledge base

**Success Criteria**:
- Community joined
- Discussions accessible
- Assets can be shared
- Knowledge base accessible

---

### JOURNEY-DPO-013: Configure Data Mesh Domain **NEW**

**Journey ID**: JOURNEY-DPO-013  
**Title**: Configure Data Mesh Domain  
**Persona**: Data Product Owner  
**Goal**: Configure data mesh domain for assets

**Steps**:
1. **NEW**: Navigate to data mesh section
2. **NEW**: Create domain (or select existing)
3. **NEW**: Define domain boundaries
4. **NEW**: Assign domain ownership
5. **NEW**: Configure domain-scoped assets
6. **NEW**: Set up domain analytics

**Success Criteria**:
- Domain created/selected
- Boundaries defined
- Ownership assigned
- Assets scoped to domain
- Analytics configured

---

### JOURNEY-DPO-014: Monitor Asset Reliability Score **NEW**

**Journey ID**: JOURNEY-DPO-014  
**Title**: Monitor Asset Reliability Score  
**Persona**: Data Product Owner  
**Goal**: Monitor and improve asset reliability score

**Steps**:
1. Navigate to asset details
2. **NEW**: View reliability score dashboard
3. **NEW**: Review score breakdown (quality, freshness, compliance)
4. **NEW**: Identify issues affecting score
5. **NEW**: Address issues
6. **NEW**: Monitor score trends

**Success Criteria**:
- Reliability score displayed
- Score breakdown visible
- Issues identified
- Score improves over time

---

## Data Engineer Journeys

### JOURNEY-DE-001: Programmatic Contract-First Onboarding

**Journey ID**: JOURNEY-DE-001  
**Title**: Programmatic Contract-First Onboarding  
**Persona**: Data Engineer  
**Goal**: Onboard asset via contract-first flow using API/SDK/CLI

**Steps**:
1. Create contract via API/SDK/CLI
2. Validate contract
3. Normalize contract
4. Attach dataset
5. Create asset
6. Activate asset

---

### JOURNEY-DE-007: Create Transformation Pipeline **NEW**

**Journey ID**: JOURNEY-DE-007  
**Title**: Create Transformation Pipeline  
**Persona**: Data Engineer  
**Goal**: Create transformation pipeline programmatically or via UI

**Steps**:
1. **NEW**: Design pipeline (UI or code)
2. **NEW**: Configure transformation nodes
3. **NEW**: Validate pipeline
4. **NEW**: Test pipeline with sample data
5. **NEW**: Save pipeline
6. **NEW**: Execute pipeline
7. **NEW**: Monitor execution
8. **NEW**: Review results

**Success Criteria**:
- Pipeline designed
- Pipeline validated
- Test successful
- Execution successful
- Results reviewed

---

### JOURNEY-DE-008: Integrate AI Schema Matching into Workflow **NEW**

**Journey ID**: JOURNEY-DE-008  
**Title**: Integrate AI Schema Matching into Workflow  
**Persona**: Data Engineer  
**Goal**: Integrate AI schema matching into automated workflows

**Steps**:
1. **NEW**: Configure AI service connection
2. **NEW**: Integrate schema matching API into workflow
3. **NEW**: Test schema matching
4. **NEW**: Configure mapping acceptance rules
5. **NEW**: Deploy workflow
6. **NEW**: Monitor schema matching performance

**Success Criteria**:
- AI service connected
- Schema matching integrated
- Tests pass
- Workflow deployed
- Performance monitored

---

### JOURNEY-DE-009: Set Up Data Virtualization **NEW**

**Journey ID**: JOURNEY-DE-009  
**Title**: Set Up Data Virtualization  
**Persona**: Data Engineer  
**Goal**: Set up data virtualization for querying across sources

**Steps**:
1. **NEW**: Define virtual dataset
2. **NEW**: Configure source systems
3. **NEW**: Set up query mapping
4. **NEW**: Configure caching strategy
5. **NEW**: Test virtual dataset queries
6. **NEW**: Deploy virtual dataset
7. **NEW**: Monitor query performance

**Success Criteria**:
- Virtual dataset defined
- Sources configured
- Queries work
- Caching configured
- Performance acceptable

---

### JOURNEY-DE-010: Configure Connector for Data Source **NEW**

**Journey ID**: JOURNEY-DE-010  
**Title**: Configure Connector for Data Source  
**Persona**: Data Engineer  
**Goal**: Configure connector for external data source

**Steps**:
1. **NEW**: Browse connector marketplace
2. **NEW**: Select connector (or create custom)
3. **NEW**: Install connector
4. **NEW**: Configure connection (credentials, settings)
5. **NEW**: Test connection
6. **NEW**: Deploy connector
7. **NEW**: Monitor connector health

**Success Criteria**:
- Connector selected/created
- Connection configured
- Test successful
- Connector deployed
- Health monitored

---

### JOURNEY-DE-011: Set Up Reverse ETL **NEW**

**Journey ID**: JOURNEY-DE-011  
**Title**: Set Up Reverse ETL  
**Persona**: Data Engineer  
**Goal**: Set up reverse ETL to push data to operational systems

**Steps**:
1. **NEW**: Select data source
2. **NEW**: Configure destination (CRM, marketing platform)
3. **NEW**: Map data fields
4. **NEW**: Configure transformation (if needed)
5. **NEW**: Set up schedule
6. **NEW**: Test reverse ETL
7. **NEW**: Deploy and monitor

**Success Criteria**:
- Destination configured
- Mapping complete
- Schedule set
- Test successful
- Reverse ETL operational

---

### JOURNEY-DE-012: Create Custom Plugin **NEW**

**Journey ID**: JOURNEY-DE-012  
**Title**: Create Custom Plugin  
**Persona**: Data Engineer  
**Goal**: Create custom plugin for platform extension

**Steps**:
1. **NEW**: Design plugin (connector, transformation, quality check)
2. **NEW**: Implement plugin interface
3. **NEW**: Test plugin
4. **NEW**: Validate plugin
5. **NEW**: Publish to plugin marketplace (optional)
6. **NEW**: Deploy plugin

**Success Criteria**:
- Plugin designed
- Interface implemented
- Tests pass
- Plugin validated
- Plugin deployed

---

### JOURNEY-DE-013: Configure Data Mesh Domain **NEW**

**Journey ID**: JOURNEY-DE-013  
**Title**: Configure Data Mesh Domain  
**Persona**: Data Engineer  
**Goal**: Configure data mesh domain infrastructure

**Steps**:
1. **NEW**: Create domain
2. **NEW**: Configure domain infrastructure
3. **NEW**: Set up self-serve capabilities
4. **NEW**: Configure resource quotas
5. **NEW**: Set up governance
6. **NEW**: Deploy domain
7. **NEW**: Monitor domain

**Success Criteria**:
- Domain created
- Infrastructure configured
- Capabilities set up
- Governance configured
- Domain operational

---

## Compliance Officer Journeys

### JOURNEY-CPO-001: Review Compliance for Asset

**Journey ID**: JOURNEY-CPO-001  
**Title**: Review Compliance for Asset  
**Persona**: Compliance Officer  
**Goal**: Review compliance status and details for an asset

**Steps**:
1. Navigate to asset
2. View compliance section
3. Review compliance status
4. Review compliance details
5. **NEW**: Review AI auto-classification results
6. Generate compliance report (if needed)

---

### JOURNEY-CPO-006: Configure Automated Compliance **NEW**

**Journey ID**: JOURNEY-CPO-006  
**Title**: Configure Automated Compliance  
**Persona**: Compliance Officer  
**Goal**: Configure automated compliance detection and enforcement

**Steps**:
1. **NEW**: Navigate to compliance configuration
2. **NEW**: Define compliance rules
3. **NEW**: Configure auto-detection
4. **NEW**: Set up enforcement actions
5. **NEW**: Configure alerts
6. **NEW**: Test automated compliance
7. **NEW**: Deploy and monitor

**Success Criteria**:
- Rules defined
- Auto-detection configured
- Enforcement set up
- Tests pass
- Automated compliance operational

---

### JOURNEY-CPO-007: Set Up GDPR Right to be Forgotten **NEW**

**Journey ID**: JOURNEY-CPO-007  
**Title**: Set Up GDPR Right to be Forgotten  
**Persona**: Compliance Officer  
**Goal**: Configure GDPR deletion workflows

**Steps**:
1. **NEW**: Navigate to GDPR configuration
2. **NEW**: Configure deletion request workflow
3. **NEW**: Set up data deletion service
4. **NEW**: Configure deletion verification
5. **NEW**: Test deletion workflow
6. **NEW**: Deploy workflow
7. **NEW**: Monitor deletion requests

**Success Criteria**:
- Workflow configured
- Deletion service set up
- Verification configured
- Tests pass
- Workflow operational

---

### JOURNEY-CPO-008: Manage Consent Tracking **NEW**

**Journey ID**: JOURNEY-CPO-008  
**Title**: Manage Consent Tracking  
**Persona**: Compliance Officer  
**Goal**: Track and manage data consent

**Steps**:
1. **NEW**: Navigate to consent management
2. **NEW**: Configure consent rules
3. **NEW**: Set up consent tracking
4. **NEW**: Monitor consent status
5. **NEW**: Generate consent reports
6. **NEW**: Handle consent changes

**Success Criteria**:
- Rules configured
- Tracking set up
- Status monitored
- Reports generated
- Changes handled

---

### JOURNEY-CPO-009: Configure Automated Retention Policies **NEW**

**Journey ID**: JOURNEY-CPO-009  
**Title**: Configure Automated Retention Policies  
**Persona**: Compliance Officer  
**Goal**: Configure automated data retention

**Steps**:
1. **NEW**: Navigate to retention configuration
2. **NEW**: Define retention rules
3. **NEW**: Configure automation
4. **NEW**: Set up scheduling
5. **NEW**: Configure deletion workflows
6. **NEW**: Test retention policies
7. **NEW**: Deploy and monitor

**Success Criteria**:
- Rules defined
- Automation configured
- Scheduling set up
- Tests pass
- Retention operational

---

### JOURNEY-CPO-010: Review AI Auto-Classification Results **NEW**

**Journey ID**: JOURNEY-CPO-010  
**Title**: Review AI Auto-Classification Results  
**Persona**: Compliance Officer  
**Goal**: Review and validate AI auto-classification results

**Steps**:
1. **NEW**: Navigate to classification dashboard
2. **NEW**: View classification results
3. **NEW**: Review confidence scores
4. **NEW**: Approve/reject classifications
5. **NEW**: Update classification rules (if needed)
6. **NEW**: Generate classification reports

**Success Criteria**:
- Results reviewed
- Classifications validated
- Rules updated (if needed)
- Reports generated

---

## Data Consumer Journeys

### JOURNEY-DC-001: Discover and Purchase Marketplace Asset

**Journey ID**: JOURNEY-DC-001  
**Title**: Discover and Purchase Marketplace Asset  
**Persona**: Data Consumer  
**Goal**: Discover and purchase data asset from marketplace

**Steps**:
1. Navigate to marketplace
2. **NEW**: Use natural language search OR keyword search
3. **NEW**: View asset recommendations
4. View asset details
5. **NEW**: Preview data before purchase
6. **NEW**: Review ratings and reviews
7. **NEW**: View trust signals (quality SLAs, badges)
8. Review pricing
9. **NEW**: Select pricing model (if multiple options)
10. Purchase asset
11. Download or access data

**Success Criteria**:
- Asset discovered
- **NEW**: Natural language search works
- **NEW**: Recommendations displayed
- **NEW**: Preview accessible
- **NEW**: Ratings/reviews visible
- Purchase completed
- Data accessible

---

### JOURNEY-DC-006: Use Natural Language Search **NEW**

**Journey ID**: JOURNEY-DC-006  
**Title**: Use Natural Language Search  
**Persona**: Data Consumer  
**Goal**: Discover data using natural language queries

**Steps**:
1. **NEW**: Navigate to search
2. **NEW**: Enter natural language query ("show me customer data from last quarter")
3. **NEW**: Review query interpretation
4. **NEW**: Execute query
5. **NEW**: Review results
6. **NEW**: Refine query if needed
7. **NEW**: Save query (optional)

**Success Criteria**:
- Query understood
- Interpretation displayed
- Results returned
- Query can be refined
- Query can be saved

**Performance Targets**:
- Query understanding: < 3 seconds
- Results returned: < 5 seconds

---

### JOURNEY-DC-007: Create Transformation Pipeline for Data **NEW**

**Journey ID**: JOURNEY-DC-007  
**Title**: Create Transformation Pipeline for Data  
**Persona**: Data Consumer  
**Goal**: Create transformation pipeline to transform purchased data

**Steps**:
1. **NEW**: Select data asset
2. **NEW**: Navigate to transformation section
3. **NEW**: Create pipeline
4. **NEW**: Design pipeline (visual builder)
5. **NEW**: Configure transformations
6. **NEW**: Preview results
7. **NEW**: Execute pipeline
8. **NEW**: Download transformed data

**Success Criteria**:
- Pipeline created
- Transformations configured
- Preview generated
- Pipeline executed
- Data downloaded

---

### JOURNEY-DC-008: Rate and Review Asset **NEW**

**Journey ID**: JOURNEY-DC-008  
**Title**: Rate and Review Asset  
**Persona**: Data Consumer  
**Goal**: Rate and review data asset

**Steps**:
1. **NEW**: Navigate to asset details
2. **NEW**: Navigate to ratings/reviews section
3. **NEW**: Rate asset (1-5 stars)
4. **NEW**: Write review
5. **NEW**: Submit review
6. **NEW**: View review status (pending moderation)

**Success Criteria**:
- Rating submitted
- Review submitted
- Review pending moderation
- Review published (after moderation)

---

### JOURNEY-DC-009: Join Data Community **NEW**

**Journey ID**: JOURNEY-DC-009  
**Title**: Join Data Community  
**Persona**: Data Consumer  
**Goal**: Join data community for collaboration

**Steps**:
1. **NEW**: Browse data communities
2. **NEW**: View community details
3. **NEW**: Join community
4. **NEW**: Participate in discussions
5. **NEW**: Access community assets
6. **NEW**: Contribute to knowledge base

**Success Criteria**:
- Community joined
- Discussions accessible
- Assets accessible
- Knowledge base accessible

---

### JOURNEY-DC-010: Query Virtual Dataset **NEW**

**Journey ID**: JOURNEY-DC-010  
**Title**: Query Virtual Dataset  
**Persona**: Data Consumer  
**Goal**: Query virtual dataset across multiple sources

**Steps**:
1. **NEW**: Navigate to virtualization section
2. **NEW**: Select virtual dataset
3. **NEW**: Build query (SQL or visual builder)
4. **NEW**: Execute query
5. **NEW**: Review results
6. **NEW**: Export results (if needed)

**Success Criteria**:
- Virtual dataset selected
- Query built
- Query executed
- Results returned
- Results exported (if needed)

**Performance Targets**:
- Query execution: < 10 seconds
- Results returned: < 5 seconds

---

### JOURNEY-DC-011: Purchase Asset with Usage-Based Pricing **NEW**

**Journey ID**: JOURNEY-DC-011  
**Title**: Purchase Asset with Usage-Based Pricing  
**Persona**: Data Consumer  
**Goal**: Purchase asset with usage-based pricing

**Steps**:
1. **NEW**: Select asset with usage-based pricing
2. **NEW**: Review pricing model (per-query, per-GB)
3. **NEW**: Purchase asset
4. **NEW**: Use asset (queries, downloads)
5. **NEW**: Monitor usage
6. **NEW**: Review billing

**Success Criteria**:
- Asset purchased
- Usage tracked
- Billing accurate
- Usage monitored

---

### JOURNEY-DC-012: Preview Data Before Purchase **NEW**

**Journey ID**: JOURNEY-DC-012  
**Title**: Preview Data Before Purchase  
**Persona**: Data Consumer  
**Goal**: Preview data before purchasing

**Steps**:
1. **NEW**: Navigate to marketplace listing
2. **NEW**: Request data preview
3. **NEW**: Review sample data
4. **NEW**: Review data quality metrics
5. **NEW**: Review schema
6. **NEW**: Make purchase decision

**Success Criteria**:
- Preview requested
- Sample data displayed
- Quality metrics visible
- Schema visible
- Decision made

---

### JOURNEY-DC-013: Use Asset Recommendations **NEW**

**Journey ID**: JOURNEY-DC-013  
**Title**: Use Asset Recommendations  
**Persona**: Data Consumer  
**Goal**: Discover assets using AI recommendations

**Steps**:
1. **NEW**: Navigate to recommendations section
2. **NEW**: View "Recommended for you"
3. **NEW**: View "Similar assets"
4. **NEW**: View "Users who viewed this also used..."
5. **NEW**: Explore recommended assets
6. **NEW**: Provide feedback (like/dislike)

**Success Criteria**:
- Recommendations displayed
- Recommendations relevant
- Assets can be explored
- Feedback can be provided
- Recommendations improve over time

---

## Tenant Admin Journeys

### JOURNEY-TA-001: Onboard New User

**Journey ID**: JOURNEY-TA-001  
**Title**: Onboard New User  
**Persona**: Tenant Admin  
**Goal**: Invite and onboard a new user to the tenant

**Steps**:
1. Navigate to User Management
2. Click "Invite User"
3. Enter user email
4. Select role
5. Send invitation
6. User receives email
7. User accepts invitation
8. Verify user activated

---

### JOURNEY-TA-005: Configure Data Mesh Domains **NEW**

**Journey ID**: JOURNEY-TA-005  
**Title**: Configure Data Mesh Domains  
**Persona**: Tenant Admin  
**Goal**: Configure data mesh domains for tenant

**Steps**:
1. **NEW**: Navigate to data mesh configuration
2. **NEW**: Create domains
3. **NEW**: Assign domain owners
4. **NEW**: Configure domain policies
5. **NEW**: Monitor domains

**Success Criteria**:
- Domains created
- Owners assigned
- Policies configured
- Domains monitored

---

### JOURNEY-TA-006: Set Up Advanced Governance **NEW**

**Journey ID**: JOURNEY-TA-006  
**Title**: Set Up Advanced Governance  
**Persona**: Tenant Admin  
**Goal**: Configure advanced governance features

**Steps**:
1. **NEW**: Navigate to governance configuration
2. **NEW**: Configure automated compliance
3. **NEW**: Set up retention automation
4. **NEW**: Configure consent management
5. **NEW**: Test governance features
6. **NEW**: Deploy and monitor

**Success Criteria**:
- Automated compliance configured
- Retention automation set up
- Consent management configured
- Tests pass
- Governance operational

---

### JOURNEY-TA-007: Monitor Cost Tracking **NEW**

**Journey ID**: JOURNEY-TA-007  
**Title**: Monitor Cost Tracking  
**Persona**: Tenant Admin  
**Goal**: Monitor and optimize tenant costs

**Steps**:
1. **NEW**: Navigate to cost dashboard
2. **NEW**: View cost breakdown
3. **NEW**: Analyze costs by asset/domain
4. **NEW**: Review cost optimization recommendations
5. **NEW**: Implement optimizations
6. **NEW**: Monitor cost trends

**Success Criteria**:
- Costs displayed
- Breakdown visible
- Recommendations provided
- Optimizations implemented
- Trends monitored

---

### JOURNEY-TA-008: Configure Integration Ecosystem **NEW**

**Journey ID**: JOURNEY-TA-008  
**Title**: Configure Integration Ecosystem  
**Persona**: Tenant Admin  
**Goal**: Configure integrations for tenant

**Steps**:
1. **NEW**: Navigate to integrations
2. **NEW**: Install connectors
3. **NEW**: Configure connections
4. **NEW**: Test integrations
5. **NEW**: Deploy integrations
6. **NEW**: Monitor integration health

**Success Criteria**:
- Connectors installed
- Connections configured
- Tests pass
- Integrations deployed
- Health monitored

---

## Platform Admin Journeys

### JOURNEY-PA-001: Onboard New Tenant

**Journey ID**: JOURNEY-PA-001  
**Title**: Onboard New Tenant  
**Persona**: Platform Admin  
**Goal**: Create a new tenant organization

**Steps**:
1. Navigate to tenant management
2. Create new tenant
3. Configure tenant settings
4. Set up KYC
5. Verify tenant
6. Activate tenant

---

### JOURNEY-MPA-005: Manage Connector Marketplace **NEW**

**Journey ID**: JOURNEY-MPA-005  
**Title**: Manage Connector Marketplace  
**Persona**: Platform Admin  
**Goal**: Manage connector marketplace

**Steps**:
1. **NEW**: Navigate to connector marketplace admin
2. **NEW**: Review connector submissions
3. **NEW**: Validate connectors
4. **NEW**: Approve/reject connectors
5. **NEW**: Publish connectors
6. **NEW**: Monitor connector usage

**Success Criteria**:
- Submissions reviewed
- Connectors validated
- Connectors published
- Usage monitored

---

### JOURNEY-MPA-006: Configure Advanced Marketplace Features **NEW**

**Journey ID**: JOURNEY-MPA-006  
**Title**: Configure Advanced Marketplace Features  
**Persona**: Platform Admin  
**Goal**: Configure advanced marketplace features

**Steps**:
1. **NEW**: Navigate to marketplace configuration
2. **NEW**: Set up usage-based pricing
3. **NEW**: Configure trust signals
4. **NEW**: Set up data previews
5. **NEW**: Configure marketplace recommendations
6. **NEW**: Test features
7. **NEW**: Deploy features

**Success Criteria**:
- Usage-based pricing configured
- Trust signals set up
- Previews configured
- Recommendations configured
- Features operational

---

### JOURNEY-MPA-007: Monitor Data Mesh Topology **NEW**

**Journey ID**: JOURNEY-MPA-007  
**Title**: Monitor Data Mesh Topology  
**Persona**: Platform Admin  
**Goal**: Monitor data mesh topology across platform

**Steps**:
1. **NEW**: Navigate to mesh topology dashboard
2. **NEW**: View mesh topology visualization
3. **NEW**: Monitor domain health
4. **NEW**: Review domain relationships
5. **NEW**: Identify topology issues
6. **NEW**: Generate topology reports

**Success Criteria**:
- Topology visualized
- Health monitored
- Relationships visible
- Issues identified
- Reports generated

---

### JOURNEY-MPA-008: Configure Advanced Observability **NEW**

**Journey ID**: JOURNEY-MPA-008  
**Title**: Configure Advanced Observability  
**Persona**: Platform Admin  
**Goal**: Configure advanced observability features

**Steps**:
1. **NEW**: Navigate to observability configuration
2. **NEW**: Set up reliability scores
3. **NEW**: Configure cost tracking
4. **NEW**: Set up predictive alerts
5. **NEW**: Configure performance monitoring
6. **NEW**: Test observability
7. **NEW**: Deploy and monitor

**Success Criteria**:
- Reliability scores configured
- Cost tracking set up
- Predictive alerts configured
- Performance monitoring set up
- Observability operational

---

### JOURNEY-MPA-009: Manage Plugin Marketplace **NEW**

**Journey ID**: JOURNEY-MPA-009  
**Title**: Manage Plugin Marketplace  
**Persona**: Platform Admin  
**Goal**: Manage plugin marketplace

**Steps**:
1. **NEW**: Navigate to plugin marketplace admin
2. **NEW**: Review plugin submissions
3. **NEW**: Validate plugins
4. **NEW**: Approve/reject plugins
5. **NEW**: Publish plugins
6. **NEW**: Monitor plugin usage

**Success Criteria**:
- Submissions reviewed
- Plugins validated
- Plugins published
- Usage monitored

---

## External Developer Journeys

### JOURNEY-DEV-001: Build Custom Integration

**Journey ID**: JOURNEY-DEV-001  
**Title**: Build Custom Integration  
**Persona**: External Developer  
**Goal**: Build integration between hub and external system

**Steps**:
1. Review API documentation
2. Obtain API credentials
3. Initialize SDK/client
4. Test authentication
5. Implement integration
6. Handle errors
7. Test integration
8. Deploy application

---

### JOURNEY-DEV-005: Use Natural Language Search API **NEW**

**Journey ID**: JOURNEY-DEV-005  
**Title**: Use Natural Language Search API  
**Persona**: External Developer  
**Goal**: Integrate natural language search into application

**Steps**:
1. **NEW**: Review natural language search API documentation
2. **NEW**: Authenticate with API
3. **NEW**: Send natural language query
4. **NEW**: Receive query interpretation
5. **NEW**: Receive search results
6. **NEW**: Process results in application

**Success Criteria**:
- API authenticated
- Query sent
- Interpretation received
- Results received
- Results processed

---

### JOURNEY-DEV-006: Integrate Transformation Pipeline API **NEW**

**Journey ID**: JOURNEY-DEV-006  
**Title**: Integrate Transformation Pipeline API  
**Persona**: External Developer  
**Goal**: Integrate transformation pipelines into application

**Steps**:
1. **NEW**: Review transformation API documentation
2. **NEW**: Create pipeline via API
3. **NEW**: Execute pipeline via API
4. **NEW**: Monitor pipeline execution
5. **NEW**: Retrieve transformation results
6. **NEW**: Process results in application

**Success Criteria**:
- Pipeline created
- Pipeline executed
- Execution monitored
- Results retrieved
- Results processed

---

### JOURNEY-DEV-007: Build Custom Connector **NEW**

**Journey ID**: JOURNEY-DEV-007  
**Title**: Build Custom Connector  
**Persona**: External Developer  
**Goal**: Build custom connector for data source

**Steps**:
1. **NEW**: Review connector framework documentation
2. **NEW**: Design connector
3. **NEW**: Implement connector interface
4. **NEW**: Test connector
5. **NEW**: Validate connector
6. **NEW**: Publish connector to marketplace (optional)

**Success Criteria**:
- Connector designed
- Interface implemented
- Tests pass
- Connector validated
- Connector published (if applicable)

---

### JOURNEY-DEV-008: Use Plugin System **NEW**

**Journey ID**: JOURNEY-DEV-008  
**Title**: Use Plugin System  
**Persona**: External Developer  
**Goal**: Use or create plugins for platform extension

**Steps**:
1. **NEW**: Browse plugin marketplace
2. **NEW**: Install plugin
3. **NEW**: Configure plugin
4. **NEW**: Use plugin functionality
5. **NEW**: Create custom plugin (if needed)
6. **NEW**: Publish plugin (if applicable)

**Success Criteria**:
- Plugin installed
- Plugin configured
- Plugin functional
- Custom plugin created (if applicable)
- Plugin published (if applicable)

---

### JOURNEY-DEV-009: Integrate with Developer Portal **NEW**

**Journey ID**: JOURNEY-DEV-009  
**Title**: Integrate with Developer Portal  
**Persona**: External Developer  
**Goal**: Use developer portal for integration development

**Steps**:
1. **NEW**: Access developer portal
2. **NEW**: Review API documentation
3. **NEW**: Review code examples
4. **NEW**: Use sandbox environment
5. **NEW**: Follow tutorials
6. **NEW**: Deploy integration

**Success Criteria**:
- Portal accessed
- Documentation reviewed
- Examples used
- Sandbox used
- Integration deployed

---

## Auditor Journeys

### JOURNEY-AUD-001: Review Audit Logs

**Journey ID**: JOURNEY-AUD-001  
**Title**: Review Audit Logs  
**Persona**: Auditor  
**Goal**: Review system audit logs

**Steps**:
1. Navigate to audit dashboard
2. Filter logs
3. Review log details
4. Export logs (if needed)

---

### JOURNEY-AUD-004: Review Data Mesh Governance **NEW**

**Journey ID**: JOURNEY-AUD-004  
**Title**: Review Data Mesh Governance  
**Persona**: Auditor  
**Goal**: Audit data mesh governance

**Steps**:
1. **NEW**: Navigate to data mesh governance dashboard
2. **NEW**: View mesh topology
3. **NEW**: Review domain policies
4. **NEW**: Audit policy compliance
5. **NEW**: Generate governance audit report

**Success Criteria**:
- Topology viewed
- Policies reviewed
- Compliance audited
- Report generated

---

### JOURNEY-AUD-005: Audit Transformation Pipelines **NEW**

**Journey ID**: JOURNEY-AUD-005  
**Title**: Audit Transformation Pipelines  
**Persona**: Auditor  
**Goal**: Audit transformation pipeline executions

**Steps**:
1. **NEW**: Navigate to transformation audit dashboard
2. **NEW**: List pipelines
3. **NEW**: Review pipeline executions
4. **NEW**: Audit transformations
5. **NEW**: Generate audit report

**Success Criteria**:
- Pipelines listed
- Executions reviewed
- Transformations audited
- Report generated

---

### JOURNEY-AUD-006: Review Social Feature Activity **NEW**

**Journey ID**: JOURNEY-AUD-006  
**Title**: Review Social Feature Activity  
**Persona**: Auditor  
**Goal**: Audit social feature activity

**Steps**:
1. **NEW**: Navigate to social activity audit dashboard
2. **NEW**: View activity feeds
3. **NEW**: Review ratings and reviews
4. **NEW**: Audit moderation decisions
5. **NEW**: Generate audit report

**Success Criteria**:
- Activities viewed
- Ratings/reviews reviewed
- Moderation audited
- Report generated

---

## Data Scientist Journeys **NEW**

### JOURNEY-DS-001: Use Natural Language Search

**Journey ID**: JOURNEY-DS-001  
**Title**: Use Natural Language Search  
**Persona**: Data Scientist / ML Engineer  
**Goal**: Discover data using natural language queries

**Steps**:
1. Navigate to search
2. Enter natural language query
3. Review query interpretation
4. Execute query
5. Review results
6. Refine query
7. Save query for reuse

**Success Criteria**:
- Query understood
- Results returned
- Query can be refined
- Query saved

---

### JOURNEY-DS-002: Use AI Schema Matching

**Journey ID**: JOURNEY-DS-002  
**Title**: Use AI Schema Matching  
**Persona**: Data Scientist / ML Engineer  
**Goal**: Use AI to match schemas for data integration

**Steps**:
1. Select source and target schemas
2. Trigger AI schema matching
3. Review matching suggestions with confidence scores
4. Accept/reject/modify mappings
5. Save mappings
6. Use mappings for integration

**Success Criteria**:
- Matching completed
- Suggestions provided
- Mappings accepted
- Mappings saved
- Integration uses mappings

---

### JOURNEY-DS-003: Configure ML-Based Anomaly Detection

**Journey ID**: JOURNEY-DS-003  
**Title**: Configure ML-Based Anomaly Detection  
**Persona**: Data Scientist / ML Engineer  
**Goal**: Configure ML models for anomaly detection

**Steps**:
1. Navigate to ML configuration
2. Select anomaly detection model
3. Configure model parameters
4. Train model with historical data
5. Deploy model
6. Monitor model performance
7. Update model based on feedback

**Success Criteria**:
- Model selected
- Parameters configured
- Model trained
- Model deployed
- Performance monitored
- Model updated

---

### JOURNEY-DS-004: Tune Recommendation Engine

**Journey ID**: JOURNEY-DS-004  
**Title**: Tune Recommendation Engine  
**Persona**: Data Scientist / ML Engineer  
**Goal**: Tune recommendation algorithms

**Steps**:
1. Navigate to recommendation configuration
2. Select recommendation algorithms
3. Configure algorithm parameters
4. Test recommendations
5. Monitor recommendation performance
6. Tune parameters based on feedback
7. Deploy tuned recommendations

**Success Criteria**:
- Algorithms selected
- Parameters configured
- Tests pass
- Performance monitored
- Recommendations tuned
- Recommendations deployed

---

### JOURNEY-DS-005: Review Auto-Classification Results

**Journey ID**: JOURNEY-DS-005  
**Title**: Review Auto-Classification Results  
**Persona**: Data Scientist / ML Engineer  
**Goal**: Review and improve auto-classification models

**Steps**:
1. Navigate to classification dashboard
2. Review classification results
3. Analyze confidence scores
4. Identify misclassifications
5. Provide feedback
6. Update classification models
7. Deploy updated models

**Success Criteria**:
- Results reviewed
- Misclassifications identified
- Feedback provided
- Models updated
- Models deployed

---

## Data Analyst Journeys **NEW**

### JOURNEY-DA-001: Create Transformation Pipeline

**Journey ID**: JOURNEY-DA-001  
**Title**: Create Transformation Pipeline  
**Persona**: Data Analyst  
**Goal**: Create transformation pipeline for data analysis

**Steps**:
1. Navigate to transformation section
2. Create new pipeline
3. Design pipeline using visual builder
4. Configure transformation nodes
5. Preview transformation results
6. Execute pipeline
7. Review results
8. Export transformed data

**Success Criteria**:
- Pipeline created
- Transformations configured
- Preview generated
- Pipeline executed
- Results reviewed
- Data exported

---

### JOURNEY-DA-002: Wrangle Data Interactively

**Journey ID**: JOURNEY-DA-002  
**Title**: Wrangle Data Interactively  
**Persona**: Data Analyst  
**Goal**: Clean and transform data interactively

**Steps**:
1. Select data asset
2. Navigate to data wrangling
3. Perform column operations (split, merge, rename, type conversion)
4. Perform row operations (filter, sort, deduplicate)
5. Preview wrangling results
6. Save wrangling history
7. Apply wrangling to data

**Success Criteria**:
- Operations performed
- Results previewed
- History saved
- Wrangling applied

---

### JOURNEY-DA-003: Query Virtual Dataset

**Journey ID**: JOURNEY-DA-003  
**Title**: Query Virtual Dataset  
**Persona**: Data Analyst  
**Goal**: Query data across multiple sources

**Steps**:
1. Navigate to virtualization section
2. Select virtual dataset
3. Build query (SQL or visual builder)
4. Execute query
5. Review results
6. Refine query if needed
7. Export results

**Success Criteria**:
- Virtual dataset selected
- Query built
- Query executed
- Results returned
- Results exported

---

### JOURNEY-DA-004: Execute Federated Query

**Journey ID**: JOURNEY-DA-004  
**Title**: Execute Federated Query  
**Persona**: Data Analyst  
**Goal**: Query multiple data sources in one query

**Steps**:
1. Navigate to federation section
2. Select multiple data sources
3. Build federated query
4. Execute query
5. Review aggregated results
6. Export results

**Success Criteria**:
- Sources selected
- Query built
- Query executed
- Results aggregated
- Results exported

---

## Community Manager Journeys **NEW**

### JOURNEY-CM-001: Manage Data Community

**Journey ID**: JOURNEY-CM-001  
**Title**: Manage Data Community  
**Persona**: Community Manager  
**Goal**: Create and manage data community

**Steps**:
1. Navigate to communities section
2. Create new community
3. Configure community settings
4. Manage community membership
5. Moderate community discussions
6. Manage community knowledge base
7. Monitor community activity

**Success Criteria**:
- Community created
- Settings configured
- Membership managed
- Discussions moderated
- Knowledge base managed
- Activity monitored

---

### JOURNEY-CM-002: Moderate Reviews and Ratings

**Journey ID**: JOURNEY-CM-002  
**Title**: Moderate Reviews and Ratings  
**Persona**: Community Manager  
**Goal**: Moderate asset reviews and ratings

**Steps**:
1. Navigate to moderation dashboard
2. Review pending reviews
3. Approve/reject reviews
4. Manage review helpfulness voting
5. Handle review disputes
6. Generate moderation reports

**Success Criteria**:
- Reviews reviewed
- Reviews approved/rejected
- Voting managed
- Disputes handled
- Reports generated

---

### JOURNEY-CM-003: Assign Data Stewards

**Journey ID**: JOURNEY-CM-003  
**Title**: Assign Data Stewards  
**Persona**: Community Manager  
**Goal**: Assign data stewards to assets

**Steps**:
1. Navigate to stewardship section
2. Select assets
3. Assign stewards
4. Configure steward permissions
5. Notify stewards
6. Monitor steward activity
7. Generate stewardship reports

**Success Criteria**:
- Stewards assigned
- Permissions configured
- Stewards notified
- Activity monitored
- Reports generated

---

### JOURNEY-CM-004: Manage Activity Feeds

**Journey ID**: JOURNEY-CM-004  
**Title**: Manage Activity Feeds  
**Persona**: Community Manager  
**Goal**: Manage and monitor activity feeds

**Steps**:
1. Navigate to activity feeds
2. Filter activities
3. Search activities
4. Monitor activity trends
5. Configure activity notifications
6. Generate activity reports

**Success Criteria**:
- Activities filtered
- Activities searched
- Trends monitored
- Notifications configured
- Reports generated

---

## Data Mesh Domain Owner Journeys **NEW**

### JOURNEY-DMO-001: Create Data Mesh Domain

**Journey ID**: JOURNEY-DMO-001  
**Title**: Create Data Mesh Domain  
**Persona**: Data Mesh Domain Owner  
**Goal**: Create and configure data mesh domain

**Steps**:
1. Navigate to data mesh section
2. Create new domain
3. Define domain boundaries
4. Assign domain ownership
5. Configure domain infrastructure
6. Set up self-serve capabilities
7. Configure resource quotas
8. Deploy domain

**Success Criteria**:
- Domain created
- Boundaries defined
- Ownership assigned
- Infrastructure configured
- Capabilities set up
- Domain deployed

---

### JOURNEY-DMO-002: Configure Federated Governance

**Journey ID**: JOURNEY-DMO-002  
**Title**: Configure Federated Governance  
**Persona**: Data Mesh Domain Owner  
**Goal**: Configure federated governance for domain

**Steps**:
1. Navigate to governance configuration
2. Define domain-specific policies
3. Configure policy enforcement
4. Set up compliance checking
5. Configure policy violation alerts
6. Test governance
7. Deploy governance

**Success Criteria**:
- Policies defined
- Enforcement configured
- Compliance checking set up
- Alerts configured
- Tests pass
- Governance deployed

---

### JOURNEY-DMO-003: Manage Domain Topology

**Journey ID**: JOURNEY-DMO-003  
**Title**: Manage Domain Topology  
**Persona**: Data Mesh Domain Owner  
**Goal**: Manage data mesh topology

**Steps**:
1. Navigate to topology visualization
2. View domain relationships
3. Manage domain relationships
4. Monitor topology health
5. Update topology as needed
6. Generate topology reports

**Success Criteria**:
- Topology visualized
- Relationships managed
- Health monitored
- Topology updated
- Reports generated

---

### JOURNEY-DMO-004: Transfer Asset Ownership

**Journey ID**: JOURNEY-DMO-004  
**Title**: Transfer Asset Ownership  
**Persona**: Data Mesh Domain Owner  
**Goal**: Transfer asset ownership between domains

**Steps**:
1. Navigate to asset management
2. Select assets to transfer
3. Select target domain
4. Initiate ownership transfer
5. Verify transfer
6. Update domain topology
7. Notify stakeholders

**Success Criteria**:
- Assets selected
- Transfer initiated
- Transfer verified
- Topology updated
- Stakeholders notified

---

### JOURNEY-DMO-005: Monitor Domain Health

**Journey ID**: JOURNEY-DMO-005  
**Title**: Monitor Domain Health  
**Persona**: Data Mesh Domain Owner  
**Goal**: Monitor domain health and performance

**Steps**:
1. Navigate to domain health dashboard
2. View domain metrics
3. Monitor domain performance
4. Review domain compliance
5. Identify issues
6. Address issues
7. Generate health reports

**Success Criteria**:
- Metrics displayed
- Performance monitored
- Compliance reviewed
- Issues identified
- Issues addressed
- Reports generated

---

## Journey Map Matrix

| Journey ID | Title | Persona | Priority | Status | Category | New Feature |
|------------|-------|---------|----------|--------|----------|-------------|
| JOURNEY-DPO-001 | Onboard New Asset via Data-First Flow | Data Product Owner | High | MVP | Asset Management | Enhanced with AI |
| JOURNEY-DPO-002 | Publish Asset to Marketplace | Data Product Owner | High | MVP | Marketplace | Enhanced with transformation |
| JOURNEY-DPO-007 | Use AI Schema Matching | Data Product Owner | High | New | AI/ML | **NEW** |
| JOURNEY-DPO-008 | Create Transformation Pipeline | Data Product Owner | High | New | Transformation | **NEW** |
| JOURNEY-DPO-009 | Manage Asset Ratings and Reviews | Data Product Owner | Medium | New | Social | **NEW** |
| JOURNEY-DPO-010 | Publish with Usage-Based Pricing | Data Product Owner | Medium | New | Marketplace | **NEW** |
| JOURNEY-DPO-011 | Assign Data Stewards | Data Product Owner | Medium | New | Social | **NEW** |
| JOURNEY-DPO-012 | Join Data Community | Data Product Owner | Low | New | Social | **NEW** |
| JOURNEY-DPO-013 | Configure Data Mesh Domain | Data Product Owner | Medium | New | Data Mesh | **NEW** |
| JOURNEY-DPO-014 | Monitor Asset Reliability Score | Data Product Owner | Medium | New | Observability | **NEW** |
| JOURNEY-DE-007 | Create Transformation Pipeline | Data Engineer | High | New | Transformation | **NEW** |
| JOURNEY-DE-008 | Integrate AI Schema Matching | Data Engineer | High | New | AI/ML | **NEW** |
| JOURNEY-DE-009 | Set Up Data Virtualization | Data Engineer | High | New | Virtualization | **NEW** |
| JOURNEY-DE-010 | Configure Connector | Data Engineer | High | New | Integration | **NEW** |
| JOURNEY-DE-011 | Set Up Reverse ETL | Data Engineer | Medium | New | Integration | **NEW** |
| JOURNEY-DE-012 | Create Custom Plugin | Data Engineer | Medium | New | Developer Experience | **NEW** |
| JOURNEY-DE-013 | Configure Data Mesh Domain | Data Engineer | Medium | New | Data Mesh | **NEW** |
| JOURNEY-DC-006 | Use Natural Language Search | Data Consumer | High | New | AI/ML | **NEW** |
| JOURNEY-DC-007 | Create Transformation Pipeline | Data Consumer | High | New | Transformation | **NEW** |
| JOURNEY-DC-008 | Rate and Review Asset | Data Consumer | Medium | New | Social | **NEW** |
| JOURNEY-DC-009 | Join Data Community | Data Consumer | Low | New | Social | **NEW** |
| JOURNEY-DC-010 | Query Virtual Dataset | Data Consumer | High | New | Virtualization | **NEW** |
| JOURNEY-DC-011 | Purchase with Usage-Based Pricing | Data Consumer | Medium | New | Marketplace | **NEW** |
| JOURNEY-DC-012 | Preview Data Before Purchase | Data Consumer | High | New | Marketplace | **NEW** |
| JOURNEY-DC-013 | Use Asset Recommendations | Data Consumer | Medium | New | AI/ML | **NEW** |
| JOURNEY-DS-001 | Use Natural Language Search | Data Scientist | High | New | AI/ML | **NEW** |
| JOURNEY-DS-002 | Use AI Schema Matching | Data Scientist | High | New | AI/ML | **NEW** |
| JOURNEY-DS-003 | Configure ML Anomaly Detection | Data Scientist | High | New | AI/ML | **NEW** |
| JOURNEY-DS-004 | Tune Recommendation Engine | Data Scientist | Medium | New | AI/ML | **NEW** |
| JOURNEY-DS-005 | Review Auto-Classification | Data Scientist | Medium | New | AI/ML | **NEW** |
| JOURNEY-DA-001 | Create Transformation Pipeline | Data Analyst | High | New | Transformation | **NEW** |
| JOURNEY-DA-002 | Wrangle Data Interactively | Data Analyst | High | New | Transformation | **NEW** |
| JOURNEY-DA-003 | Query Virtual Dataset | Data Analyst | High | New | Virtualization | **NEW** |
| JOURNEY-DA-004 | Execute Federated Query | Data Analyst | High | New | Virtualization | **NEW** |
| JOURNEY-CM-001 | Manage Data Community | Community Manager | High | New | Social | **NEW** |
| JOURNEY-CM-002 | Moderate Reviews and Ratings | Community Manager | High | New | Social | **NEW** |
| JOURNEY-CM-003 | Assign Data Stewards | Community Manager | Medium | New | Social | **NEW** |
| JOURNEY-CM-004 | Manage Activity Feeds | Community Manager | Medium | New | Social | **NEW** |
| JOURNEY-DMO-001 | Create Data Mesh Domain | Data Mesh Domain Owner | High | New | Data Mesh | **NEW** |
| JOURNEY-DMO-002 | Configure Federated Governance | Data Mesh Domain Owner | High | New | Data Mesh | **NEW** |
| JOURNEY-DMO-003 | Manage Domain Topology | Data Mesh Domain Owner | Medium | New | Data Mesh | **NEW** |
| JOURNEY-DMO-004 | Transfer Asset Ownership | Data Mesh Domain Owner | Medium | New | Data Mesh | **NEW** |
| JOURNEY-DMO-005 | Monitor Domain Health | Data Mesh Domain Owner | Medium | New | Data Mesh | **NEW** |

**Total**: 82 journeys (37 original + 45 new)

---

**Last Updated**: 2025-12-13  
**Version**: 2.0.0 (Added 45 new journeys for 4 new personas and enhanced existing journeys with new features)

