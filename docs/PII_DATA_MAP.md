# PII Data Map

**Total apps**: 12 | **Total PII fields**: 25

## auth
- `LoginAttempt.email` — email
- `LoginAttempt.ip_address` — address
- `LoginAttempt.ip_address` — ip_address

## billing
- `ConnectAccount.country` — address

## contracts
- `LineageSubscription.email` — email
- `SecurityAuditLog.ip_address` — address
- `SecurityAuditLog.ip_address` — ip_address

## dsar
- `DSARRequest.email_otp_attempts` — email
- `DSARRequest.email_otp_digest` — email
- `DSARRequest.email_otp_expires_at` — email

## governance
- `ComplianceReport.email_recipients` — email
- `ComplianceReport.email_sent` — email
- `ComplianceReport.email_sent_at` — email

## notifications
- `EmailDelivery.email_type` — email

## orchestration
- `WorkflowInstance.state_data` — address
- `WorkflowState.state_data` — address
- `WorkflowState.step_states` — address

## processor_agreements
- `Processor.country_code` — address

## scheduled_ingestion
- `ScheduledIngestion.ingestion_state` — address

## search
- `SearchAnalytics.ip_address` — address
- `SearchAnalytics.ip_address` — ip_address

## tenants
- `LimitDimension.display_name` — name
- `Tenant.tax_address` — address
- `Tenant.tax_id` — ssn

## transformation
- `WranglingSession.current_state` — address

## Exemptions
- `email_verified`: Boolean — verification status only
- `invitation_token`: SHA-256 hash, not plaintext
- `password`: Hashed by Django (PBKDF2/bcrypt)
- `tax_id_type`: Enum — type classifier, not the ID itself
- `tax_id_verified`: Boolean — verification status only