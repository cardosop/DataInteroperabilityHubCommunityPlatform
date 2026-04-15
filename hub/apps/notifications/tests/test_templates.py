"""
Unit tests for email template rendering.
"""
from django.test import TestCase
from django.template import Context, Template

from hub.apps.notifications.templates import (
    render_email_template,
    get_base_url,
    build_invitation_url,
    build_password_reset_url,
    build_job_url
)


class EmailTemplateRenderingTest(TestCase):
    """Tests for email template rendering"""
    
    def test_render_email_template_html_only(self):
        """Test rendering HTML template"""
        context = {
            'user': {'display_name': 'Test User'},
            'tenant': {'name': 'Test Tenant'},
            'invitation_url': 'http://example.com/invite?token=123'
        }
        
        result = render_email_template(
            'notifications/emails/user_invitation.html',
            context
        )
        
        self.assertIn('html', result)
        self.assertIn('text', result)
        self.assertIn('Test User', result['html'])
        self.assertIn('Test Tenant', result['html'])
        # Check for the actual URL value, not the variable name
        self.assertIn('http://example.com/invite?token=123', result['html'])
    
    def test_render_email_template_with_text_template(self):
        """Test rendering with explicit text template"""
        context = {'message': 'Test message'}
        
        # This would require a text template, but we test the logic
        result = render_email_template(
            'notifications/emails/user_invitation.html',
            context,
            text_template_name=None  # Auto-generate from HTML
        )
        
        self.assertIn('html', result)
        self.assertIn('text', result)
        # Text should be generated from HTML
        self.assertTrue(len(result['text']) > 0)
    
    def test_get_base_url_default(self):
        """Test getting default base URL"""
        with self.settings(EMAIL_BASE_URL=None):
            url = get_base_url()
            self.assertEqual(url, 'http://localhost:8000')
    
    def test_get_base_url_from_settings(self):
        """Test getting base URL from settings"""
        with self.settings(EMAIL_BASE_URL='https://hub.example.com'):
            url = get_base_url()
            self.assertEqual(url, 'https://hub.example.com')
    
    def test_build_invitation_url(self):
        """Test building invitation URL"""
        with self.settings(EMAIL_BASE_URL='https://hub.example.com'):
            url = build_invitation_url('test-token-123')
            self.assertEqual(url, 'https://hub.example.com/auth/accept-invitation?token=test-token-123')
    
    def test_build_password_reset_url(self):
        """Test building password reset URL — token in fragment (221.1.3)"""
        with self.settings(EMAIL_BASE_URL='https://hub.example.com'):
            url = build_password_reset_url('reset-token-456')
            self.assertEqual(url, 'https://hub.example.com/auth/password-reset/confirm#token=reset-token-456')
    
    def test_build_job_url(self):
        """Test building job URL"""
        with self.settings(EMAIL_BASE_URL='https://hub.example.com'):
            url = build_job_url('job-uuid-789')
            self.assertEqual(url, 'https://hub.example.com/api/v1/jobs/job-uuid-789')

