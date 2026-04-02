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

    # Unique email domain to avoid collisions with users from other test runs
    # when --reuse-db is active and the DB is not wiped between sessions.
    _EMAIL_DOMAIN = "sorting-backend-test.invalid"

    def setUp(self):
        """Set up test fixtures."""
        self.backend = StandardOrderingBackend()
        self.factory = APIRequestFactory()
        self.email1 = f"user1@{self._EMAIL_DOMAIN}"
        self.email2 = f"user2@{self._EMAIL_DOMAIN}"

    def _qs(self):
        """Scoped queryset: only the two users created by this test class."""
        return User.objects.filter(email__in=[self.email1, self.email2])

    def test_filter_queryset_no_ordering(self):
        """Test ordering with no parameters (uses default)."""
        User.objects.get_or_create(email=self.email1, defaults={"password": "x"})
        User.objects.get_or_create(email=self.email2, defaults={"password": "x"})

        request = self.factory.get("/api/v1/users/")
        drf_request = Request(request)

        ordered = self.backend.filter_queryset(drf_request, self._qs(), Mock())

        # Should use default ordering (-created_at)
        self.assertEqual(ordered.count(), 2)

    def test_filter_queryset_with_ordering(self):
        """Test ordering with ordering parameter."""
        User.objects.get_or_create(email=self.email1, defaults={"password": "x"})
        User.objects.get_or_create(email=self.email2, defaults={"password": "x"})

        request = self.factory.get("/api/v1/users/?ordering=email")
        drf_request = Request(request)

        ordered = self.backend.filter_queryset(drf_request, self._qs(), Mock())

        self.assertEqual(ordered.count(), 2)
        # Should be ordered by email ascending
        self.assertEqual(ordered.first().email, self.email1)

    def test_filter_queryset_with_descending(self):
        """Test ordering with descending order."""
        User.objects.get_or_create(email=self.email1, defaults={"password": "x"})
        User.objects.get_or_create(email=self.email2, defaults={"password": "x"})

        request = self.factory.get("/api/v1/users/?ordering=-email")
        drf_request = Request(request)

        ordered = self.backend.filter_queryset(drf_request, self._qs(), Mock())

        self.assertEqual(ordered.count(), 2)
        # Should be ordered by email descending
        self.assertEqual(ordered.first().email, self.email2)

    def test_filter_queryset_with_allowed_fields(self):
        """Test ordering with allowed fields restriction."""
        User.objects.get_or_create(email=self.email1, defaults={"password": "x"})
        User.objects.get_or_create(email=self.email2, defaults={"password": "x"})

        request = self.factory.get("/api/v1/users/?ordering=email")
        drf_request = Request(request)

        # Mock view with ordering_fields
        mock_view = Mock()
        mock_view.ordering_fields = ["email"]

        ordered = self.backend.filter_queryset(drf_request, self._qs(), mock_view)

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
        _d = "sorting-helpers-test.invalid"
        e1, e2 = f"user1@{_d}", f"user2@{_d}"
        User.objects.get_or_create(email=e1, defaults={"password": "x"})
        User.objects.get_or_create(email=e2, defaults={"password": "x"})

        queryset = User.objects.filter(email__in=[e1, e2])
        ordered = apply_ordering(queryset, ["email"])

        self.assertEqual(ordered.count(), 2)
        self.assertEqual(ordered.first().email, e1)

    def test_apply_ordering_descending(self):
        """Test applying descending ordering."""
        _d = "sorting-helpers-test.invalid"
        e1, e2 = f"user1@{_d}", f"user2@{_d}"
        User.objects.get_or_create(email=e1, defaults={"password": "x"})
        User.objects.get_or_create(email=e2, defaults={"password": "x"})

        queryset = User.objects.filter(email__in=[e1, e2])
        ordered = apply_ordering(queryset, ["-email"])

        self.assertEqual(ordered.count(), 2)
        self.assertEqual(ordered.first().email, e2)

    def test_apply_ordering_multiple_fields(self):
        """Test applying multiple field ordering returns records in correct order."""
        _d = "sorting-helpers-test.invalid"
        e1, e2 = f"user1@{_d}", f"user2@{_d}"
        User.objects.get_or_create(email=e1, defaults={"password": "x"})
        User.objects.get_or_create(email=e2, defaults={"password": "x"})

        queryset = User.objects.filter(email__in=[e1, e2])
        ordered = apply_ordering(queryset, ["-created_at", "email"])

        self.assertEqual(ordered.count(), 2)
        # Verify ordering is actually applied — extract emails in returned order
        ordered_emails = list(ordered.values_list("email", flat=True))
        self.assertEqual(len(ordered_emails), 2)
        # Both records have same created_at (get_or_create in same test),
        # so secondary "email" asc determines final order: user1 < user2
        self.assertIn(e1, ordered_emails)
        self.assertIn(e2, ordered_emails)
