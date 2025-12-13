"""
Comprehensive tests for standardized sorting.
"""
from unittest.mock import Mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.request import Request
from rest_framework.test import APIRequestFactory

from hub.apps.api.standards.sorting import (
    StandardOrderingBackend,
    apply_ordering,
    parse_ordering_params,
    validate_ordering_params,
)

User = get_user_model()


class TestStandardOrderingBackend(TestCase):
    """Test StandardOrderingBackend class."""

    def setUp(self):
        """Set up test fixtures."""
        self.backend = StandardOrderingBackend()
        self.factory = APIRequestFactory()

    def test_filter_queryset_no_ordering(self):
        """Test ordering with no parameters (uses default)."""
        User.objects.create_user(email="user1@example.com", password="testpass123")
        User.objects.create_user(email="user2@example.com", password="testpass123")

        request = self.factory.get("/api/v1/users/")
        drf_request = Request(request)
        queryset = User.objects.all()

        ordered = self.backend.filter_queryset(drf_request, queryset, Mock())

        # Should use default ordering (-created_at)
        self.assertEqual(ordered.count(), 2)

    def test_filter_queryset_with_ordering(self):
        """Test ordering with ordering parameter."""
        user1 = User.objects.create_user(email="user1@example.com", password="testpass123")
        user2 = User.objects.create_user(email="user2@example.com", password="testpass123")

        request = self.factory.get("/api/v1/users/?ordering=email")
        drf_request = Request(request)
        queryset = User.objects.all()

        ordered = self.backend.filter_queryset(drf_request, queryset, Mock())

        self.assertEqual(ordered.count(), 2)
        # Should be ordered by email ascending
        self.assertEqual(ordered.first().email, "user1@example.com")

    def test_filter_queryset_with_descending(self):
        """Test ordering with descending order."""
        user1 = User.objects.create_user(email="user1@example.com", password="testpass123")
        user2 = User.objects.create_user(email="user2@example.com", password="testpass123")

        request = self.factory.get("/api/v1/users/?ordering=-email")
        drf_request = Request(request)
        queryset = User.objects.all()

        ordered = self.backend.filter_queryset(drf_request, queryset, Mock())

        self.assertEqual(ordered.count(), 2)
        # Should be ordered by email descending
        self.assertEqual(ordered.first().email, "user2@example.com")

    def test_filter_queryset_with_allowed_fields(self):
        """Test ordering with allowed fields restriction."""
        User.objects.create_user(email="user1@example.com", password="testpass123")
        User.objects.create_user(email="user2@example.com", password="testpass123")

        request = self.factory.get("/api/v1/users/?ordering=email")
        drf_request = Request(request)
        queryset = User.objects.all()

        # Mock view with ordering_fields
        mock_view = Mock()
        mock_view.ordering_fields = ["email"]

        ordered = self.backend.filter_queryset(drf_request, queryset, mock_view)

        self.assertEqual(ordered.count(), 2)


class TestSortingHelpers(TestCase):
    """Test sorting helper functions."""

    def setUp(self):
        """Set up test fixtures."""
        self.factory = APIRequestFactory()

    def test_parse_ordering_params_drf_request(self):
        """Test parsing ordering params from DRF request."""
        request = self.factory.get("/api/v1/resources/?ordering=-created_at,name")
        drf_request = Request(request)

        params = parse_ordering_params(drf_request)

        self.assertEqual(params, ["-created_at", "name"])

    def test_parse_ordering_params_django_request(self):
        """Test parsing ordering params from Django request."""
        request = self.factory.get("/api/v1/resources/?ordering=name")

        params = parse_ordering_params(request)

        self.assertEqual(params, ["name"])

    def test_parse_ordering_params_no_ordering(self):
        """Test parsing ordering params with no ordering parameter."""
        request = self.factory.get("/api/v1/resources/")

        params = parse_ordering_params(request)

        self.assertEqual(params, [])

    def test_parse_ordering_params_order_by_alias(self):
        """Test parsing ordering params with order_by alias."""
        request = self.factory.get("/api/v1/resources/?order_by=name")

        params = parse_ordering_params(request)

        self.assertEqual(params, ["name"])

    def test_validate_ordering_params_no_restrictions(self):
        """Test validating ordering params with no restrictions."""
        params = ["-created_at", "name"]

        is_valid, error = validate_ordering_params(params)

        self.assertTrue(is_valid)
        self.assertIsNone(error)

    def test_validate_ordering_params_with_allowed_fields(self):
        """Test validating ordering params with allowed fields."""
        params = ["-created_at", "name"]
        allowed_fields = ["created_at", "name"]

        is_valid, error = validate_ordering_params(params, allowed_fields)

        self.assertTrue(is_valid)
        self.assertIsNone(error)

    def test_validate_ordering_params_invalid_field(self):
        """Test validating ordering params with invalid field."""
        params = ["invalid_field"]
        allowed_fields = ["created_at", "name"]

        is_valid, error = validate_ordering_params(params, allowed_fields)

        self.assertFalse(is_valid)
        self.assertIn("invalid_field", error)

    def test_apply_ordering_single_field(self):
        """Test applying single field ordering."""
        user1 = User.objects.create_user(email="user1@example.com", password="testpass123")
        user2 = User.objects.create_user(email="user2@example.com", password="testpass123")

        queryset = User.objects.all()
        ordering = ["email"]

        ordered = apply_ordering(queryset, ordering)

        self.assertEqual(ordered.count(), 2)
        self.assertEqual(ordered.first().email, "user1@example.com")

    def test_apply_ordering_descending(self):
        """Test applying descending ordering."""
        user1 = User.objects.create_user(email="user1@example.com", password="testpass123")
        user2 = User.objects.create_user(email="user2@example.com", password="testpass123")

        queryset = User.objects.all()
        ordering = ["-email"]

        ordered = apply_ordering(queryset, ordering)

        self.assertEqual(ordered.count(), 2)
        self.assertEqual(ordered.first().email, "user2@example.com")

    def test_apply_ordering_multiple_fields(self):
        """Test applying multiple field ordering."""
        User.objects.create_user(email="user1@example.com", password="testpass123")
        User.objects.create_user(email="user2@example.com", password="testpass123")

        queryset = User.objects.all()
        ordering = ["-created_at", "email"]

        ordered = apply_ordering(queryset, ordering)

        self.assertEqual(ordered.count(), 2)
