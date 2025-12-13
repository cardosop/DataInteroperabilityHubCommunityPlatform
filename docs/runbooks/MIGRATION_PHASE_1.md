# Migration Runbook: Phase 1 - Read-Only Services

**Phase:** Phase 1  
**Services:** Search Service, Observability Service  
**Risk Level:** Low  
**Duration:** 2 weeks

---

## Pre-Migration Checklist

- [ ] API Gateway (Traefik) deployed and operational
- [ ] Event Bus (Redis) operational
- [ ] Distributed Tracing (Jaeger) operational
- [ ] Service Discovery configured
- [ ] Monitoring dashboards ready
- [ ] Rollback plan documented
- [ ] Team briefed on migration plan

---

## Migration Steps: Search Service

### Step 1: Prepare Search Service

1. **Create Service Directory**
   ```bash
   mkdir -p services/search-service/{app,tests}
   ```

2. **Review Existing Service**
   - Check if `search-service` already exists
   - Review implementation
   - Identify gaps

3. **Extract Models**
   ```bash
   # Copy SearchIndex and SearchAnalytics models
   cp hub/apps/search/models.py services/search-service/app/models.py
   ```

4. **Create Database Migration**
   ```bash
   # Create new schema
   psql -U hub -d hub -c "CREATE SCHEMA IF NOT EXISTS search_service;"
   
   # Migrate data
   python manage.py migrate search --database=search_service
   ```

### Step 2: Extract Search Logic

1. **Extract Search Views**
   ```bash
   cp hub/apps/search/views.py services/search-service/app/views.py
   ```

2. **Extract Search Indexing**
   ```bash
   cp hub/apps/search/indexing.py services/search-service/app/indexing.py
   ```

3. **Create FastAPI Application**
   ```python
   # services/search-service/app/main.py
   from fastapi import FastAPI
   from services.shared.tracing import setup_opentelemetry_fastapi
   
   app = FastAPI(title="Search Service")
   setup_opentelemetry_fastapi('search-service')
   
   # Add routes
   ```

### Step 3: Set Up Event Subscriptions

1. **Subscribe to Events**
   ```python
   # services/search-service/app/events.py
   from hub.apps.core.events.bus import EventBus
   
   event_bus = EventBus()
   
   @event_bus.subscribe('contract.created')
   def index_contract(event):
       # Index contract
       pass
   
   @event_bus.subscribe('asset.created')
   def index_asset(event):
       # Index asset
       pass
   ```

### Step 4: Configure API Gateway

1. **Add Route to Traefik**
   ```yaml
   # infrastructure/traefik/dynamic/routes.yml
   search-service:
     rule: "PathPrefix(`/api/v1/search`)"
     service: search-service
   ```

2. **Update docker-compose.yml**
   ```yaml
   search-service:
     # ... existing configuration
     labels:
       - "traefik.enable=true"
       - "traefik.http.routers.search-service.rule=PathPrefix(`/api/v1/search`)"
   ```

### Step 5: Deploy and Test

1. **Deploy Service**
   ```bash
   docker-compose up -d search-service
   ```

2. **Run Integration Tests**
   ```bash
   pytest tests/integration/test_search_service.py
   ```

3. **Monitor Health**
   ```bash
   curl http://search-service:8085/health
   ```

### Step 6: Switch Traffic

1. **Route 10% Traffic**
   ```yaml
   # Update Traefik routing
   # Route 10% to new service
   ```

2. **Monitor for 24 Hours**
   - Check error rates
   - Check response times
   - Check search result accuracy

3. **Increase to 100%**
   - If stable, route 100% traffic
   - Continue monitoring

### Step 7: Decommission Old Code

1. **Remove Search Views from Monolith**
   ```bash
   # Comment out search views
   # hub/apps/search/views.py
   ```

2. **Keep Models for Migration Period**
   - Keep models for 2 weeks
   - Monitor for issues

3. **Remove After Validation**
   ```bash
   # After 2 weeks, remove models
   rm hub/apps/search/models.py
   ```

---

## Migration Steps: Observability Service

### Step 1: Prepare Observability Service

1. **Review Existing Service**
   - Check if `observability-service` already exists
   - Review implementation
   - Identify gaps

2. **Extract Models**
   ```bash
   cp hub/apps/observability/models.py services/observability-service/app/models.py
   ```

3. **Create Database Migration**
   ```bash
   psql -U hub -d hub -c "CREATE SCHEMA IF NOT EXISTS observability_service;"
   python manage.py migrate observability --database=observability_service
   ```

### Step 2: Extract Observability Logic

1. **Extract Observability Views**
   ```bash
   cp hub/apps/observability/views.py services/observability-service/app/views.py
   ```

2. **Extract Monitoring Logic**
   ```bash
   cp hub/apps/observability/freshness.py services/observability-service/app/freshness.py
   cp hub/apps/observability/volume.py services/observability-service/app/volume.py
   cp hub/apps/observability/schema_drift.py services/observability-service/app/schema_drift.py
   ```

3. **Create FastAPI Application**
   ```python
   # services/observability-service/app/main.py
   from fastapi import FastAPI
   from services.shared.tracing import setup_opentelemetry_fastapi
   
   app = FastAPI(title="Observability Service")
   setup_opentelemetry_fastapi('observability-service')
   ```

### Step 3: Set Up Event Subscriptions

1. **Subscribe to Events**
   ```python
   @event_bus.subscribe('dataset.created')
   def update_freshness(event):
       # Update freshness metrics
       pass
   
   @event_bus.subscribe('ingestion.completed')
   def update_volume(event):
       # Update volume metrics
       pass
   ```

### Step 4: Configure API Gateway

1. **Add Route to Traefik**
   ```yaml
   observability-service:
     rule: "PathPrefix(`/api/v1/observability`)"
     service: observability-service
   ```

### Step 5: Deploy and Test

1. **Deploy Service**
   ```bash
   docker-compose up -d observability-service
   ```

2. **Run Integration Tests**
   ```bash
   pytest tests/integration/test_observability_service.py
   ```

3. **Monitor Health**
   ```bash
   curl http://observability-service:8086/health
   ```

### Step 6: Switch Traffic

1. **Route 100% Traffic**
   - Route all traffic to new service
   - Monitor error rates
   - Validate metrics accuracy

### Step 7: Decommission Old Code

1. **Remove Observability Views**
   ```bash
   # Comment out observability views
   ```

2. **Keep Models for Migration Period**
   - Keep models for 2 weeks

3. **Remove After Validation**
   ```bash
   # After 2 weeks, remove models
   ```

---

## Validation

### Success Criteria

- [ ] Search service handles 100% of search requests
- [ ] Observability service handles 100% of observability requests
- [ ] Zero increase in error rates
- [ ] Response times within SLA
- [ ] All integration tests passing
- [ ] Monitoring dashboards operational

### Monitoring

Monitor the following metrics for 2 weeks:

- Error rates
- Response times
- Throughput
- Resource utilization
- Search result accuracy
- Metrics accuracy

---

## Rollback Procedure

### If Issues Occur

1. **Stop Traffic to New Service**
   ```bash
   # Update Traefik routing
   # Route back to monolith
   ```

2. **Restore Monolith Functionality**
   ```bash
   # Uncomment search/observability views
   # Restore models if removed
   ```

3. **Investigate Root Cause**
   - Check logs
   - Check traces
   - Identify issue

4. **Fix and Re-attempt**
   - Fix issues
   - Update migration plan
   - Re-attempt migration

---

## Post-Migration

### After 2 Weeks Validation

1. **Remove Old Code**
   - Remove search views from monolith
   - Remove observability views from monolith
   - Remove models (if data migrated)

2. **Update Documentation**
   - Update architecture diagrams
   - Update API documentation
   - Update runbooks

3. **Celebrate Success**
   - Document lessons learned
   - Share with team
   - Prepare for Phase 2

---

**Last Updated:** 2025-01-15  
**Status:** Ready for Execution

