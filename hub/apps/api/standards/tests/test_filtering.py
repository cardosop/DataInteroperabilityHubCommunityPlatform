"""
Comprehensive tests for standardized filtering.
"""
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
        User.objects.create_user(email="user1@example.com", password="testpass123")
        User.objects.create_user(email="user2@example.com", password="testpass123")

        request = self.factory.get("/api/v1/users/")
        drf_request = Request(request)
        queryset = User.objects.all()

        filtered = self.backend.filter_queryset(drf_request, queryset, Mock())

        self.assertEqual(filtered.count(), 2)

    def test_filter_queryset_with_exact_match(self):
        """Test filtering with exact match."""
        User.objects.create_user(email="user1@example.com", password="testpass123")
        User.objects.create_user(email="user2@example.com", password="testpass123")

        request = self.factory.get("/api/v1/users/?email=user1@example.com")
        drf_request = Request(request)
        queryset = User.objects.all()

        filtered = self.backend.filter_queryset(drf_request, queryset, Mock())

        self.assertEqual(filtered.count(), 1)
        self.assertEqual(filtered.first().email, "user1@example.com")

    def test_filter_queryset_with_allowed_fields(self):
        """Test filtering with allowed fields restriction."""
        User.objects.create_user(email="user1@example.com", password="testpass123")
        User.objects.create_user(email="user2@example.com", password="testpass123")

        request = self.factory.get("/api/v1/users/?email=user1@example.com&name=test")
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
        request = self.factory.get(
            "/api/v1/resources/?status=active&name__contains=test&page=1"
        )
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
        User.objects.create_user(email="user1@example.com", password="testpass123")
        User.objects.create_user(email="user2@example.com", password="testpass123")

        queryset = User.objects.all()
        filter_params = {"email": "user1@example.com"}

        filtered = apply_filters(queryset, filter_params)

        self.assertEqual(filtered.count(), 1)
        self.assertEqual(filtered.first().email, "user1@example.com")

    def test_apply_filters_in_operator(self):
        """Test applying 'in' operator filter."""
        User.objects.create_user(email="user1@example.com", password="testpass123")
        User.objects.create_user(email="user2@example.com", password="testpass123")
        User.objects.create_user(email="user3@example.com", password="testpass123")

        queryset = User.objects.all()
        filter_params = {"email__in": "user1@example.com,user2@example.com"}

        filtered = apply_filters(queryset, filter_params)

        self.assertEqual(filtered.count(), 2)

    def test_apply_filters_isnull_operator(self):
        """Test applying 'isnull' operator filter."""
        user1 = User.objects.create_user(email="user1@example.com", password="testpass123")
        user2 = User.objects.create_user(email="user2@example.com", password="testpass123")

        queryset = User.objects.all()
        filter_params = {"email__isnull": "false"}

        filtered = apply_filters(queryset, filter_params)

        self.assertEqual(filtered.count(), 2)

    def test_apply_filters_empty_value(self):
        """Test applying filters with empty value (should be skipped)."""
        User.objects.create_user(email="user1@example.com", password="testpass123")

        queryset = User.objects.all()
        filter_params = {"email": ""}

        filtered = apply_filters(queryset, filter_params)

        self.assertEqual(filtered.count(), 1)  # No filtering applied
