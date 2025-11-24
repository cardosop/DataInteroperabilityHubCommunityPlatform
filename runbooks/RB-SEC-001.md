# RB-SEC-001: Security Incident Response

**Runbook ID:** `RB-SEC-001`  
**Title:** Security Incident Response  
**Last Updated:** 2025-01-15  
**Version:** 1.0

---

## Scope

This runbook covers response procedures for suspected or confirmed security incidents.

**In Scope:**
- Account compromise
- Unauthorized access
- Data exfiltration
- Vulnerability exploitation
- DDoS attacks

**Out of Scope:**
- Operational incidents (see operational runbooks)
- Compliance violations (handled separately)

---

## Severity Classification

### SEV-1 (Critical)
- Active data exfiltration
- System compromise
- Ransomware attack
- Production system breach

### SEV-2 (High)
- Suspected account compromise
- Unauthorized access detected
- Vulnerability exploitation attempt
- Privilege escalation detected

### SEV-3 (Medium)
- Failed authentication attempts
- Suspicious activity detected
- Security scan findings
- Policy violations

---

## Prerequisites

**Tools Required:**
- Log analysis tools
- Database query access
- Cloud provider security tools
- Incident tracking system

**Access Required:**
- Security team access
- Database admin access
- Cloud console access
- Audit log access

**Contacts:**
- Security team on-call
- Legal/compliance team
- Management escalation

---

## Symptoms

### Alert Indicators

- `security_unauthorized_access`
- `security_account_compromise`
- `security_data_exfiltration`
- `security_privilege_escalation`

### User Reports

- Unusual account activity
- Unauthorized data access
- Suspicious API usage
- Account lockouts

### Log Indicators

**Unauthorized Access:**
```
ERROR: Authentication failed for user: suspicious_user
WARN: Multiple failed login attempts from IP: 203.0.113.10
ERROR: Access denied: user attempted to access tenant: tenant-123
```

**Suspicious Activity:**
```
INFO: Unusual API usage pattern detected
WARN: High rate of requests from single IP
ERROR: Cross-tenant access attempt detected
```

---

## Immediate Actions

### Step 1: Containment

**1.1 Revoke Affected Credentials**
```bash
# Revoke API keys
python manage.py revoke_api_key --key-id <key-id>

# Lock user accounts
python manage.py lock_user --user-id <user-id>

# Revoke JWT tokens (if possible)
# Invalidate refresh tokens in database
```

**1.2 Block IP Addresses**
```bash
# Add to firewall/security group
# Block at load balancer level
# Update WAF rules
```

**1.3 Disable Affected Services (if needed)**
```bash
# Scale down affected services
kubectl scale deployment/api-service --replicas=0 -n production

# Enable maintenance mode
kubectl set env deployment/api-service MAINTENANCE_MODE=true -n production
```

### Step 2: Evidence Preservation

**2.1 Snapshot Logs**
```bash
# Export relevant log entries
kubectl logs deployment/api-service -n production \
  --since-time="2025-01-15T10:00:00Z" > incident-logs.txt

# Export audit events
python manage.py export_audit_events \
  --start-time "2025-01-15T10:00:00Z" \
  --output incident-audit.json
```

**2.2 Snapshot Database State**
```sql
-- Export relevant database records
COPY (
  SELECT * FROM audit_events 
  WHERE occurred_at > '2025-01-15 10:00:00'
) TO '/tmp/incident-audit.csv' WITH CSV HEADER;
```

**2.3 Preserve System State**
- Take snapshots of affected systems
- Preserve configuration files
- Document current state

---

## Investigation

### Step 1: Identify Impact

**1.1 Determine Affected Tenants/Users**
```sql
-- Find affected tenants
SELECT DISTINCT tenant_id 
FROM audit_events 
WHERE occurred_at > '2025-01-15 10:00:00'
  AND action LIKE '%UNAUTHORIZED%';

-- Find affected users
SELECT DISTINCT actor_user_id 
FROM audit_events 
WHERE occurred_at > '2025-01-15 10:00:00'
  AND action LIKE '%COMPROMISE%';
```

**1.2 Determine Time Range**
```sql
-- Find first suspicious activity
SELECT MIN(occurred_at) as first_incident
FROM audit_events
WHERE action LIKE '%UNAUTHORIZED%' OR action LIKE '%COMPROMISE%';
```

**1.3 Identify Entry Points**
- Review authentication logs
- Check API access logs
- Review network logs
- Check for vulnerability exploitation

### Step 2: Analyze Attack Vector

**2.1 Review Authentication Logs**
```sql
-- Failed login attempts
SELECT 
    ip_address,
    user_email,
    COUNT(*) as attempt_count,
    MIN(occurred_at) as first_attempt,
    MAX(occurred_at) as last_attempt
FROM audit_events
WHERE action = 'AUTH_FAILED'
  AND occurred_at > '2025-01-15 10:00:00'
GROUP BY ip_address, user_email
ORDER BY attempt_count DESC;
```

**2.2 Review API Access Patterns**
```sql
-- Unusual API usage
SELECT 
    actor_user_id,
    route,
    COUNT(*) as request_count,
    COUNT(DISTINCT tenant_id) as tenant_count
FROM audit_events
WHERE occurred_at > '2025-01-15 10:00:00'
  AND resource_type = 'API_REQUEST'
GROUP BY actor_user_id, route
HAVING tenant_count > 1  -- Cross-tenant access
ORDER BY request_count DESC;
```

**2.3 Check for Data Exfiltration**
```sql
-- Large data exports
SELECT 
    actor_user_id,
    tenant_id,
    resource_type,
    COUNT(*) as access_count,
    SUM(CASE WHEN action LIKE '%EXPORT%' THEN 1 ELSE 0 END) as export_count
FROM audit_events
WHERE occurred_at > '2025-01-15 10:00:00'
GROUP BY actor_user_id, tenant_id, resource_type
HAVING export_count > 10
ORDER BY export_count DESC;
```

---

## Eradication & Recovery

### Step 1: Remove Attacker Access

**1.1 Revoke All Credentials**
- Revoke API keys
- Invalidate JWT tokens
- Reset user passwords
- Lock compromised accounts

**1.2 Patch Vulnerabilities**
- Apply security patches
- Update dependencies
- Fix configuration issues

**1.3 Update Security Controls**
- Update firewall rules
- Update WAF rules
- Enhance monitoring
- Add additional security layers

### Step 2: Validate Access Removal

**2.1 Verify Credentials Revoked**
```sql
-- Check for active sessions
SELECT COUNT(*) FROM user_sessions 
WHERE user_id = <compromised_user_id> AND expires_at > NOW();

-- Check for active API keys
SELECT COUNT(*) FROM api_keys 
WHERE user_id = <compromised_user_id> AND status = 'ACTIVE';
```

**2.2 Monitor for Continued Access**
- Watch authentication logs
- Monitor API access
- Check for new suspicious activity

### Step 3: Restore Services

**3.1 Re-enable Services**
```bash
# Scale services back up
kubectl scale deployment/api-service --replicas=3 -n production

# Disable maintenance mode
kubectl set env deployment/api-service MAINTENANCE_MODE=false -n production
```

**3.2 Verify Functionality**
- Run smoke tests
- Verify authentication works
- Check API endpoints
- Monitor for errors

---

## Communication

### Internal Notifications

**Initial Alert:**
```
🚨 SECURITY INCIDENT
Severity: SEV-1
Type: [Account Compromise / Unauthorized Access / etc.]
Status: Investigating
Impact: [Affected tenants/users]
```

**Investigation Update:**
```
🔄 Security Incident - Update
Status: [Containing / Investigating / Remediating]
Findings: [Summary of findings]
ETA: [Time]
```

**Resolution:**
```
✅ Security Incident - Resolved
Status: Remediated
Duration: [X hours]
Actions Taken: [Summary]
```

### External Notifications

**Affected Tenants:**
- Notify impacted tenants
- Provide incident summary
- Explain remediation steps
- Offer support

**Regulatory (if required):**
- GDPR: Notify within 72 hours
- Other regulations: Follow specific requirements
- Coordinate with legal/compliance team

---

## Post-Incident

### Immediate Actions

- [ ] Document incident details
- [ ] Create postmortem ticket
- [ ] Update security controls
- [ ] Enhance monitoring/alerting

### Long-Term Actions

- [ ] Conduct full root cause analysis
- [ ] Update security policies
- [ ] Improve security controls
- [ ] Schedule security review
- [ ] Update this runbook

---

## Related Runbooks

- `RB-DB-001`: Database Outage / Degradation
- `RB-SVC-001`: Service Crash Recovery

---

## Appendix

### Security Incident Checklist

```markdown
- [ ] Incident declared
- [ ] Severity classified
- [ ] Containment actions taken
- [ ] Evidence preserved
- [ ] Investigation started
- [ ] Impact assessed
- [ ] Remediation executed
- [ ] Access removed
- [ ] Services restored
- [ ] Monitoring enhanced
- [ ] Stakeholders notified
- [ ] Documentation updated
```

### Common Attack Vectors

**SQL Injection:**
- Review query logs
- Check for unusual query patterns
- Verify input validation

**Cross-Site Scripting (XSS):**
- Review user input
- Check for script execution
- Verify output encoding

**Privilege Escalation:**
- Review role assignments
- Check for unauthorized role changes
- Verify access controls

**API Key Compromise:**
- Review API key usage
- Check for unusual patterns
- Verify key rotation

