# Email Deliverability

**Version**: 1.0 | **Owner**: Platform Engineering

## DNS Records

| Record | Type | Value | Purpose |
|--------|------|-------|---------|
| SPF | TXT | `v=spf1 include:amazonses.com ~all` | Authorize SES to send |
| DKIM | CNAME | `{hash}meshant-internal.example.com` → `{hash}.dkim.amazonses.com` | Sign outgoing email |
| DMARC | TXT | `v=DMARC1; p=quarantine; rua=mailto:dmarc@meshant.com` | Policy + aggregate reports |
| MX | MX | `10 inbound-smtp.us-east-1.amazonaws.com` | Inbound email (SES) |

## Monitoring

- **Bounce rate**: alert if > 5% in 24h (indicates spam or bad addresses)
- **Complaint rate**: alert if > 0.1% (SES account suspension risk)
- **Delivery delay**: alert if p95 > 60s
- **DMARC reports**: processed weekly via `dmarc@meshant.com` aggregate reports

## Bounce Handling

1. Hard bounce (permanent): mark email as invalid, suppress future sends
2. Soft bounce (temporary): retry up to 3 times with exponential backoff
3. Complaint: immediately suppress; investigate if triggered by legitimate email

## SES Configuration

- **Region**: us-east-1
- **From address**: `noreply@meshant.com` (verified)
- **Configuration set**: `meshant-transactional` (tracks opens, clicks, bounces)
- **Sending quota**: 50,000 emails/day (standard SES limit)
