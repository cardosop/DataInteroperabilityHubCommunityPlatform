"""
Comprehensive tests for standardized filtering.
"""

import uuid
from unittest.mock import Mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.request import Request
from rest_framework.test import APIRequestFactory

from hub.apps.api.standards.filtering import (
    StandardFilterBackend,
    apply_filters,
    parse_filter_params,
    validate_filter_params,
)

User = get_user_model()


class TestStandardFilterBackend(TestCase):
    """Test StandardFilterBackend class."""

    def setUp(self):
        """Set up test fixtures."""
        self.backend = StandardFilterBackend()
        self.factory = APIRequestFactory()

    def test_filter_queryset_no_params(self):
        """Test filtering with no parameters."""
        _uid = uuid.uuid4().hex[:8]
        User.objects.create_user(
            email=f"filter-noparam-1-{_uid}@example.com", password="testpass123"
        )
        User.objects.create_user(
            email=f"filter-noparam-2-{_uid}@example.com", password="testpass123"
        )

        request = self.factory.get("/api/v1/users/")
        drf_request = Request(request)
        queryset = User.objects.filter(email__contains=_uid)

        filtered = self.backend.filter_queryset(drf_request, queryset, Mock())

        self.assertEqual(filtered.count(), 2)

    def test_filter_queryset_with_exact_match(self):
        """Test filtering with exact match."""
        _uid = uuid.uuid4().hex[:8]
        email1 = f"user1-{_uid}@example.com"
        email2 = f"user2-{_uid}@example.com"
        User.objects.create_user(email=email1, password="testpass123")
        User.objects.create_user(email=email2, password="testpass123")

        request = self.factory.get(f"/api/v1/users/?email={email1}")
        drf_request = Request(request)
        queryset = User.objects.all()

        filtered = self.backend.filter_queryset(drf_request, queryset, Mock())

        self.assertEqual(filtered.count(), 1)
        self.assertEqual(filtered.first().email, email1)

    def test_filter_queryset_with_allowed_fields(self):
        """Test filtering with allowed fields restriction."""
        _uid = uuid.uuid4().hex[:8]
        email1 = f"user1-{_uid}@example.com"
        User.objects.create_user(email=email1, password="testpass123")
        User.objects.create_user(email=f"user2-{_uid}@example.com", password="testpass123")

        request = self.factory.get(f"/api/v1/users/?email={email1}&name=test")
        drf_request = Request(request)
        queryset = User.objects.all()

        # Mock view with filter_fields
        mock_view = Mock()
        mock_view.filter_fields = ["email"]

        filtered = self.backend.filter_queryset(drf_request, queryset, mock_view)

        # Should only filter by email (name is not in allowed fields)
        self.assertEqual(filtered.count(), 1)


class TestFilterHelpers(TestCase):
    """Test filtering helper functions."""

    def setUp(self):
        """Set up test fixtures."""
        self.factory = APIRequestFactory()

    def test_parse_filter_params_drf_request(self):
        """Test parsing filter params from DRF request."""
        request = self.factory.get("/api/v1/resources/?status=active&name__contains=test&page=1")
        drf_request = Request(request)

        params = parse_filter_params(drf_request)

        self.assertEqual(params["status"], "active")
        self.assertEqual(params["name__contains"], "test")
        self.assertNotIn("page", params)  # Pagination params excluded

    def test_parse_filter_params_django_request(self):
        """Test parsing filter params from Django request."""
        request = self.factory.get("/api/v1/resources/?status=active")

        params = parse_filter_params(request)

        self.assertEqual(params["status"], "active")

    def test_parse_filter_params_skip_special(self):
        """Test parsing filter params skips special parameters."""
        request = self.factory.get("/api/v1/resources/?status=active&_internal=test")

        params = parse_filter_params(request)

        self.assertEqual(params["status"], "active")
        self.assertNotIn("_internal", params)

    def test_validate_filter_params_no_restrictions(self):
        """Test validating filter params with no restrictions."""
        params = {"status": "active", "name": "test"}

        is_valid, error = validate_filter_params(params)

        self.assertTrue(is_valid)
        self.assertIsNone(error)

    def test_validate_filter_params_with_allowed_fields(self):
        """Test validating filter params with allowed fields."""
        params = {"status": "active", "name": "test"}
        allowed_fields = ["status"]

        is_valid, error = validate_filter_params(params, allowed_fields)

        self.assertFalse(is_valid)
        self.assertIn("name", error)

    def test_validate_filter_params_with_operator(self):
        """Test validating filter params with operators."""
        params = {"name__contains": "test"}
        allowed_fields = ["name"]

        is_valid, error = validate_filter_params(params, allowed_fields)

        self.assertTrue(is_valid)
        self.assertIsNone(error)

    def test_apply_filters_exact_match(self):
        """Test applying exact match filter."""
        _uid = uuid.uuid4().hex[:8]
        email1 = f"user1-{_uid}@example.com"
        User.objects.create_user(email=email1, password="testpass123")
        User.objects.create_user(email=f"user2-{_uid}@example.com", password="testpass123")

        queryset = User.objects.all()
        filter_params = {"email": email1}

        filtered = apply_filters(queryset, filter_params)

        self.assertEqual(filtered.count(), 1)
        self.assertEqual(filtered.first().email, email1)

    def test_apply_filters_in_operator(self):
        """Test applying 'in' operator filter returns exactly the matching records."""
        _uid = uuid.uuid4().hex[:8]
        email1 = f"user1-{_uid}@example.com"
        email2 = f"user2-{_uid}@example.com"
        email3 = f"user3-{_uid}@example.com"
        User.objects.create_user(email=email1, password="testpass123")
        User.objects.create_user(email=email2, password="testpass123")
        User.objects.create_user(email=email3, password="testpass123")

        queryset = User.objects.all()
        filter_params = {"email__in": f"{email1},{email2}"}

        filtered = apply_filters(queryset, filter_params)

        self.assertEqual(filtered.count(), 2)
        # Verify the CORRECT records were returned, not just the count
        returned_emails = set(filtered.values_list("email", flat=True))
        self.assertEqual(returned_emails, {email1, email2})

    def test_apply_filters_isnull_operator(self):
        """Test applying 'isnull' operator filter."""
        _uid = uuid.uuid4().hex[:8]
        User.objects.create_user(
            email=f"filter-isnull-1-{_uid}@example.com", password="testpass123"
        )
        User.objects.create_user(
            email=f"filter-isnull-2-{_uid}@example.com", password="testpass123"
        )

        queryset = User.objects.filter(email__contains=_uid)
        filter_params = {"email__isnull": "false"}

        filtered = apply_filters(queryset, filter_params)

        self.assertEqual(filtered.count(), 2)

    def test_apply_filters_empty_value(self):
        """Test applying filters with empty value (should be skipped)."""
        _uid = uuid.uuid4().hex[:8]
        User.objects.create_user(
            email=f"filter-emptyval-1-{_uid}@example.com", password="testpass123"
        )

        queryset = User.objects.filter(email__contains=_uid)
        filter_params = {"email": ""}

        filtered = apply_filters(queryset, filter_params)

        self.assertEqual(filtered.count(), 1)  # No filtering applied
