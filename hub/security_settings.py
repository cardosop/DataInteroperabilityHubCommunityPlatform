"""
Django 6 Security Settings

This module contains security settings optimized for Django 6.
These settings should be imported and merged into the main settings.py file.
"""

from django.conf import settings

# Django 6 Security Enhancements
# Reference: https://docs.djangoproject.com/en/6.0/ref/settings/#security

# ============================================================================
# HTTPS and SSL/TLS Security
# ============================================================================

# Force HTTPS in production (Django 6 default: False)
# Set to True in production environments
SECURE_SSL_REDIRECT = getattr(settings, "SECURE_SSL_REDIRECT", False)

# HTTP Strict Transport Security (HSTS)
# Tells browsers to only connect via HTTPS for the specified duration
SECURE_HSTS_SECONDS = getattr(
    settings, "SECURE_HSTS_SECONDS", 0
)  # Set to 31536000 (1 year) in production
SECURE_HSTS_INCLUDE_SUBDOMAINS = getattr(settings, "SECURE_HSTS_INCLUDE_SUBDOMAINS", False)
SECURE_HSTS_PRELOAD = getattr(settings, "SECURE_HSTS_PRELOAD", False)

# Secure cookies
SECURE_COOKIES = getattr(settings, "SECURE_COOKIES", False)  # Set to True in production with HTTPS
SESSION_COOKIE_SECURE = getattr(
    settings, "SESSION_COOKIE_SECURE", False
)  # Set to True in production
CSRF_COOKIE_SECURE = getattr(settings, "CSRF_COOKIE_SECURE", False)  # Set to True in production

# ============================================================================
# Content Security Policy (CSP) - Django 6 Enhancement
# ============================================================================

# Django 6 includes built-in CSP support via SecurityMiddleware
# For advanced CSP, consider using django-csp package

# Content Security Policy settings (if using django-csp)
# Install: pip install django-csp
# Then add 'csp.middleware.CSPMiddleware' to MIDDLEWARE

# Basic CSP configuration (can be enhanced with django-csp)
CSP_DEFAULT_SRC = getattr(settings, "CSP_DEFAULT_SRC", ["'self'"])
CSP_SCRIPT_SRC = getattr(
    settings, "CSP_SCRIPT_SRC", ["'self'", "'unsafe-inline'"]
)  # Adjust for production
CSP_STYLE_SRC = getattr(
    settings, "CSP_STYLE_SRC", ["'self'", "'unsafe-inline'"]
)  # Adjust for production
CSP_IMG_SRC = getattr(settings, "CSP_IMG_SRC", ["'self'", "data:", "https:"])
CSP_FONT_SRC = getattr(settings, "CSP_FONT_SRC", ["'self'", "https:"])
CSP_CONNECT_SRC = getattr(settings, "CSP_CONNECT_SRC", ["'self'"])
CSP_FRAME_SRC = getattr(settings, "CSP_FRAME_SRC", ["'none'"])
CSP_OBJECT_SRC = getattr(settings, "CSP_OBJECT_SRC", ["'none'"])
CSP_BASE_URI = getattr(settings, "CSP_BASE_URI", ["'self'"])
CSP_FORM_ACTION = getattr(settings, "CSP_FORM_ACTION", ["'self'"])
CSP_FRAME_ANCESTORS = getattr(settings, "CSP_FRAME_ANCESTORS", ["'none'"])

# ============================================================================
# X-Frame-Options (Clickjacking Protection)
# ============================================================================

# Django 6 default: DENY (already set via XFrameOptionsMiddleware)
# Options: 'DENY', 'SAMEORIGIN', 'ALLOW-FROM <uri>'
X_FRAME_OPTIONS = getattr(settings, "X_FRAME_OPTIONS", "DENY")

# ============================================================================
# X-Content-Type-Options
# ============================================================================

# Prevent MIME type sniffing
SECURE_CONTENT_TYPE_NOSNIFF = getattr(settings, "SECURE_CONTENT_TYPE_NOSNIFF", True)

# ============================================================================
# X-XSS-Protection (Legacy, but still useful)
# ============================================================================

# Note: Modern browsers have built-in XSS protection, but this header
# can be set via custom middleware if needed

# ============================================================================
# Referrer Policy
# ============================================================================

# Control referrer information sent with requests
# Options: 'no-referrer', 'no-referrer-when-downgrade', 'origin',
#          'origin-when-cross-origin', 'same-origin', 'strict-origin',
#          'strict-origin-when-cross-origin', 'unsafe-url'
SECURE_REFERRER_POLICY = getattr(
    settings, "SECURE_REFERRER_POLICY", "strict-origin-when-cross-origin"
)

# ============================================================================
# Permissions Policy (formerly Feature Policy)
# ============================================================================

# Control which browser features can be used
# Django 6 supports this via SecurityMiddleware
# Example: SECURE_PERMISSIONS_POLICY = {"geolocation": "()"}

# ============================================================================
# Cross-Origin Resource Sharing (CORS)
# ============================================================================

# CORS is handled by django-cors-headers
# Configuration is in settings.py under CORS_ALLOWED_ORIGINS, etc.

# ============================================================================
# CSRF Protection
# ============================================================================

# CSRF protection is enabled by default via CsrfViewMiddleware
# Additional settings:
CSRF_COOKIE_HTTPONLY = getattr(
    settings, "CSRF_COOKIE_HTTPONLY", False
)  # Set to True for better security
CSRF_COOKIE_SAMESITE = getattr(
    settings, "CSRF_COOKIE_SAMESITE", "Lax"
)  # Options: 'Strict', 'Lax', 'None'
CSRF_TRUSTED_ORIGINS = getattr(settings, "CSRF_TRUSTED_ORIGINS", [])

# ============================================================================
# Session Security
# ============================================================================

# Session cookie settings
SESSION_COOKIE_HTTPONLY = getattr(settings, "SESSION_COOKIE_HTTPONLY", True)
SESSION_COOKIE_SAMESITE = getattr(settings, "SESSION_COOKIE_SAMESITE", "Lax")
SESSION_COOKIE_AGE = getattr(settings, "SESSION_COOKIE_AGE", 1209600)  # 2 weeks default

# ============================================================================
# Password Security
# ============================================================================

# Password validation is configured in AUTH_PASSWORD_VALIDATORS
# Django 6 includes enhanced password validators

# ============================================================================
# Security Headers Middleware (Custom)
# ============================================================================

# For additional security headers, create a custom middleware
# Example headers to add:
# - X-Content-Type-Options: nosniff (already handled by SECURE_CONTENT_TYPE_NOSNIFF)
# - X-XSS-Protection: 1; mode=block (legacy, but can be added)
# - Permissions-Policy: (configure as needed)
# - Referrer-Policy: (configured via SECURE_REFERRER_POLICY)
