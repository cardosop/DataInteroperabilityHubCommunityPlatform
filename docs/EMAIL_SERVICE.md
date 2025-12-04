# Email Service Documentation

## Overview

The Email Service provides a unified interface for sending emails via multiple backends:
- **SendGrid**: Cloud-based email delivery service
- **AWS SES**: Amazon Simple Email Service
- **SMTP**: Generic SMTP server (for development or custom email servers)

## Configuration

### Email Backend Selection

Set `EMAIL_BACKEND` in your environment variables or `.env.dev` file:

```bash
# For SendGrid
EMAIL_BACKEND=sendgrid

# For AWS SES
EMAIL_BACKEND=ses

# For SMTP (default)
EMAIL_BACKEND=smtp
```

### SendGrid Configuration

```bash
EMAIL_BACKEND=sendgrid
SENDGRID_API_KEY=your_sendgrid_api_key
SENDGRID_FROM_EMAIL=noreply@example.com
SENDGRID_FROM_NAME=Data Interoperability Hub
```

### AWS SES Configuration

```bash
EMAIL_BACKEND=ses
AWS_SES_REGION=us-east-1
AWS_SES_FROM_EMAIL=noreply@example.com
AWS_SES_FROM_NAME=Data Interoperability Hub
AWS_ACCESS_KEY_ID=your_aws_access_key
AWS_SECRET_ACCESS_KEY=your_aws_secret_key
```

**Note**: AWS SES credentials can also be provided via IAM roles or AWS credentials file.

### SMTP Configuration

```bash
EMAIL_BASE_URL=http://localhost:8000
EMAIL_BACKEND=smtp
SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_USERNAME=your_smtp_username
SMTP_PASSWORD=your_smtp_password
SMTP_USE_TLS=true
SMTP_USE_SSL=false
SMTP_FROM_EMAIL=noreply@example.com
SMTP_FROM_NAME=Data Interoperability Hub
```

### Base URL Configuration

The `EMAIL_BASE_URL` setting is used to build links in emails (invitation links, password reset links, etc.):

```bash
EMAIL_BASE_URL=https://hub.example.com
```

### Job Notifications

Enable email notifications for job completion/failure:

```bash
EMAIL_JOB_NOTIFICATIONS_ENABLED=true
```

## Email Types

The service supports the following email types:

1. **User Invitation**: Sent when a user is invited to join a tenant
2. **Password Reset**: Sent when a user requests a password reset
3. **Job Completion**: Sent when a job completes successfully (if enabled)
4. **Job Failure**: Sent when a job fails (if enabled)
5. **API Deprecation**: Sent when an API endpoint is deprecated (future)

## Email Templates

Email templates are located in `hub/apps/notifications/templates/notifications/emails/`:

- `base.html`: Base template with styling
- `user_invitation.html`: User invitation email
- `password_reset.html`: Password reset email
- `job_completion.html`: Job completion notification
- `job_failure.html`: Job failure notification
- `api_deprecation.html`: API deprecation notice

## Email Delivery Tracking

All emails are tracked in the `EmailDelivery` model with the following statuses:

- `PENDING`: Email is queued for sending
- `SENT`: Email was sent successfully
- `DELIVERED`: Email was delivered (from webhook)
- `BOUNCED`: Email bounced
- `FAILED`: Email sending failed
- `DEFERRED`: Email deferred for retry

## Retry Logic

The email service implements automatic retry with exponential backoff:

- Initial retry: 60 seconds
- Second retry: 120 seconds
- Third retry: 240 seconds
- Maximum retries: 3 (configurable)

Failed emails are automatically retried if they haven't exceeded the maximum retry count.

## Usage

### Sending User Invitation Email

User invitation emails are automatically sent when a user is invited via the `/api/v1/users/invite/` endpoint.

### Sending Password Reset Email

Password reset emails are automatically sent when a user requests a password reset via `/api/v1/auth/password-reset`.

### Sending Job Notification Emails

Job notification emails are automatically sent when:
- A job completes successfully (if `EMAIL_JOB_NOTIFICATIONS_ENABLED=true`)
- A job fails (if `EMAIL_JOB_NOTIFICATIONS_ENABLED=true`)

### Programmatic Email Sending

You can send emails programmatically using the email service:

```python
from hub.apps.notifications.services import get_email_service

email_service = get_email_service()
result = email_service.send_email(
    to_email='user@example.com',
    subject='Test Email',
    html_content='<h1>Hello</h1><p>This is a test email.</p>',
    text_content='Hello\n\nThis is a test email.'
)
```

## Development

For local development, you can use:

1. **SMTP with a local mail server** (e.g., MailHog, MailCatcher)
2. **SMTP with Gmail** (for testing)
3. **SendGrid sandbox mode** (for testing without sending real emails)

### Using MailHog for Local Development

1. Start MailHog:
```bash
docker run -d -p 1025:1025 -p 8025:8025 mailhog/mailhog
```

2. Configure SMTP:
```bash
EMAIL_BACKEND=smtp
SMTP_HOST=localhost
SMTP_PORT=1025
SMTP_USE_TLS=false
SMTP_USE_SSL=false
SMTP_FROM_EMAIL=test@example.com
```

3. View emails at http://localhost:8025

## Troubleshooting

### Email Not Sending

1. Check email backend configuration:
   - Verify `EMAIL_BACKEND` is set correctly
   - Verify backend-specific settings (API keys, credentials, etc.)

2. Check email delivery records:
   ```python
   from hub.apps.notifications.models import EmailDelivery
   EmailDelivery.objects.filter(status='FAILED').order_by('-created_at')[:10]
   ```

3. Check logs for error messages:
   - Look for `email_send_failed_*` log entries
   - Check error messages in `EmailDelivery.error_message` field

### SendGrid Issues

- Verify API key is correct and has email sending permissions
- Check SendGrid dashboard for delivery status
- Verify sender email is verified in SendGrid

### AWS SES Issues

- Verify AWS credentials are correct
- Check SES console for sender email verification
- Verify SES is out of sandbox mode (if sending to unverified emails)
- Check IAM permissions for SES

### SMTP Issues

- Verify SMTP server is accessible
- Check SMTP credentials
- Verify TLS/SSL settings match server configuration
- Check firewall rules

## Security Considerations

1. **API Keys and Credentials**: Store email service credentials securely (use secrets manager in production)

2. **Email Content**: Never include sensitive information in emails (passwords, tokens, etc.)

3. **Rate Limiting**: Email services may have rate limits - the service implements retry logic to handle temporary failures

4. **Bounce Handling**: Implement webhook handlers for bounce notifications (future enhancement)

## Future Enhancements

- Webhook handlers for delivery status updates (SendGrid, SES)
- Email template customization per tenant
- Email preferences (opt-out for job notifications)
- Email analytics and reporting
- Support for email attachments
- Support for email CC/BCC

