"""
Comprehensive tests for standardized pagination.
"""

import base64
import json
import uuid
from unittest.mock import Mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.request import Request
from rest_framework.test import APIRequestFactory

from hub.apps.api.standards.pagination import (
    StandardCursorPagination,
    StandardPageNumberPagination,
    get_pagination_params,
    paginate_queryset_cursor,
    validate_pagination_params,
)

User = get_user_model()


class TestStandardCursorPagination(TestCase):
    """Test StandardCursorPagination class."""

    def setUp(self):
        """Set up test fixtures."""
        self.pagination = StandardCursorPagination()
        self.factory = APIRequestFactory()

    def test_default_page_size(self):
        """Test default page size."""
        self.assertEqual(self.pagination.page_size, 50)

    def test_max_page_size(self):
        """Test max page size."""
        self.assertEqual(self.pagination.max_page_size, 100)

    def test_ordering(self):
        """Test default ordering."""
        self.assertEqual(self.pagination.ordering, "-created_at")

    def test_encode_cursor(self):
        """Test cursor encoding."""
        position = [1234567890.0]
        cursor = self.pagination.encode_cursor(position)

        self.assertIsNotNone(cursor)
        # Decode to verify
        decoded = base64.b64decode(cursor.encode("utf-8")).decode("utf-8")
        decoded_position = json.loads(decoded)
        self.assertEqual(decoded_position, position)

    def test_encode_cursor_none(self):
        """Test encoding None cursor."""
        cursor = self.pagination.encode_cursor(None)
        self.assertIsNone(cursor)

    def test_decode_cursor(self):
        """Test cursor decoding."""
        position = [1234567890.0]
        encoded = base64.b64encode(json.dumps(position).encode("utf-8")).decode("utf-8")
        decoded = self.pagination.decode_cursor(encoded)

        self.assertEqual(decoded, tuple(position))

    def test_decode_cursor_none(self):
        """Test decoding None cursor."""
        decoded = self.pagination.decode_cursor(None)
        self.assertIsNone(decoded)

    def test_decode_cursor_invalid(self):
        """Test decoding invalid cursor."""
        decoded = self.pagination.decode_cursor("invalid_cursor")
        self.assertIsNone(decoded)

    def test_get_paginated_response(self):
        """Test getting paginated response."""
        # Create mock page
        mock_page = Mock()
        mock_page.paginator = Mock()
        mock_page.paginator.count = 100
        self.pagination.page = mock_page
        self.pagination.page_size = 50

        # Mock get_next_link and get_previous_link
        self.pagination.get_next_link = Mock(return_value="next_cursor")
        self.pagination.get_previous_link = Mock(return_value="prev_cursor")

        data = [{"id": "1"}, {"id": "2"}]
        response = self.pagination.get_paginated_response(data)

        self.assertEqual(response.data["count"], 100)
        self.assertEqual(response.data["next_cursor"], "next_cursor")
        self.assertEqual(response.data["previous_cursor"], "prev_cursor")
        self.assertEqual(response.data["page_size"], 50)
        self.assertEqual(response.data["results"], data)


class TestStandardPageNumberPagination(TestCase):
    """Test StandardPageNumberPagination class."""

    def setUp(self):
        """Set up test fixtures."""
        self.pagination = StandardPageNumberPagination()
        self.factory = APIRequestFactory()

    def test_default_page_size(self):
        """Test default page size."""
        self.assertEqual(self.pagination.page_size, 50)

    def test_max_page_size(self):
        """Test max page size."""
        self.assertEqual(self.pagination.max_page_size, 100)

    def test_get_paginated_response(self):
        """Test getting paginated response."""
        # Create mock page
        mock_page = Mock()
        mock_page.number = 2
        mock_page.paginator = Mock()
        mock_page.paginator.count = 100
        mock_page.paginator.per_page = 50
        mock_page.paginator.num_pages = 2
        self.pagination.page = mock_page

        # Mock get_next_link and get_previous_link
        self.pagination.get_next_link = Mock(return_value="next_url")
        self.pagination.get_previous_link = Mock(return_value="prev_url")

        data = [{"id": "1"}, {"id": "2"}]
        response = self.pagination.get_paginated_response(data)

        self.assertEqual(response.data["count"], 100)
        self.assertEqual(response.data["page"], 2)
        self.assertEqual(response.data["page_size"], 50)
        self.assertEqual(response.data["total_pages"], 2)
        self.assertEqual(response.data["next"], "next_url")
        self.assertEqual(response.data["previous"], "prev_url")
        self.assertEqual(response.data["results"], data)


class TestPaginationHelpers(TestCase):
    """Test pagination helper functions."""

    def setUp(self):
        """Set up test fixtures."""
        self.factory = APIRequestFactory()

    def test_get_pagination_params_drf_request(self):
        """Test getting pagination params from DRF request."""
        request = self.factory.get("/api/v1/resources/?page=2&page_size=25&cursor=abc123")
        drf_request = Request(request)

        params = get_pagination_params(drf_request)

        self.assertEqual(params["page"], 2)
        self.assertEqual(params["page_size"], 25)
        self.assertEqual(params["cursor"], "abc123")

    def test_get_pagination_params_django_request(self):
        """Test getting pagination params from Django request."""
        request = self.factory.get("/api/v1/resources/?page=3&page_size=30")

        params = get_pagination_params(request)

        self.assertEqual(params["page"], 3)
        self.assertEqual(params["page_size"], 30)

    def test_get_pagination_params_defaults(self):
        """Test getting pagination params with defaults."""
        request = self.factory.get("/api/v1/resources/")

        params = get_pagination_params(request)

        self.assertEqual(params["page"], 1)
        self.assertEqual(params["page_size"], 50)
        self.assertIsNone(params["cursor"])

    def test_get_pagination_params_invalid_page(self):
        """Test getting pagination params with invalid page."""
        request = self.factory.get("/api/v1/resources/?page=invalid")

        params = get_pagination_params(request)

        self.assertEqual(params["page"], 1)  # Defaults to 1

    def test_get_pagination_params_invalid_page_size(self):
        """Test getting pagination params with invalid page_size."""
        request = self.factory.get("/api/v1/resources/?page_size=invalid")

        params = get_pagination_params(request)

        self.assertEqual(params["page_size"], 50)  # Defaults to 50

    def test_get_pagination_params_page_size_clamping(self):
        """Test page size clamping."""
        request = self.factory.get("/api/v1/resources/?page_size=200")  # > max

        params = get_pagination_params(request)

        self.assertEqual(params["page_size"], 100)  # Clamped to max

        request = self.factory.get("/api/v1/resources/?page_size=0")  # < min

        params = get_pagination_params(request)

        self.assertEqual(params["page_size"], 50)  # Defaults to 50

    def test_validate_pagination_params_valid(self):
        """Test validating valid pagination params."""
        is_valid, error = validate_pagination_params(page=1, page_size=50)

        self.assertTrue(is_valid)
        self.assertIsNone(error)

    def test_validate_pagination_params_invalid_page(self):
        """Test validating invalid page number."""
        is_valid, error = validate_pagination_params(page=0)

        self.assertFalse(is_valid)
        self.assertIn("must be >= 1", error)

    def test_validate_pagination_params_invalid_page_size(self):
        """Test validating invalid page size."""
        is_valid, error = validate_pagination_params(page_size=0)

        self.assertFalse(is_valid)
        self.assertIn("must be >= 1", error)

        is_valid, error = validate_pagination_params(page_size=200)

        self.assertFalse(is_valid)
        self.assertIn("must be <= 100", error)

    def test_validate_pagination_params_both_page_and_cursor(self):
        """Test validating both page and cursor (should fail)."""
        is_valid, error = validate_pagination_params(page=1, cursor="abc123")

        self.assertFalse(is_valid)
        self.assertIn("Cannot use both", error)

    def test_paginate_queryset_cursor_no_cursor(self):
        """Test cursor pagination without cursor returns correct page size and data."""
        _uid = uuid.uuid4().hex[:8]
        for i in range(10):
            User.objects.create_user(email=f"user{i}-{_uid}@example.com", password="testpass123")

        queryset = User.objects.all()
        paginated, next_cursor, prev_cursor = paginate_queryset_cursor(queryset, page_size=5)

        self.assertEqual(paginated.count(), 5)
        self.assertIsNotNone(next_cursor)
        self.assertIsNone(prev_cursor)
        # Verify the returned items are actual DB records, not empty stubs
        page_ids = list(paginated.values_list("id", flat=True))
        self.assertEqual(len(page_ids), 5)
        self.assertEqual(len(set(page_ids)), 5, "Page items must be unique")

    def test_paginate_queryset_cursor_with_cursor(self):
        """Test cursor pagination across multiple pages with no overlap.

        Creates 15 users so that:
          page 1 → 5 items, next_cursor1 set
          page 2 → 5 items, next_cursor2 set  (5 items remain on page 3)
          page 3 → 5 items, no next_cursor
        """
        # Create enough users for at least 3 pages so page 2 still has a next cursor
        _uid = uuid.uuid4().hex[:8]
        users = []
        for i in range(15):
            user = User.objects.create_user(
                email=f"user{i}-{_uid}@example.com", password="testpass123"
            )
            users.append(user)

        queryset = User.objects.all()
        # Get first page
        paginated1, next_cursor1, _ = paginate_queryset_cursor(queryset, page_size=5)

        # Get second page using cursor
        paginated2, next_cursor2, prev_cursor2 = paginate_queryset_cursor(
            queryset, page_size=5, cursor=next_cursor1
        )

        self.assertEqual(paginated2.count(), 5)
        self.assertIsNotNone(next_cursor2)  # page 3 exists
        self.assertEqual(prev_cursor2, next_cursor1)
        # Verify no overlap between pages 1 and 2
        ids1 = set(paginated1.values_list("id", flat=True))
        ids2 = set(paginated2.values_list("id", flat=True))
        self.assertEqual(len(ids1.intersection(ids2)), 0)

    def test_paginate_queryset_cursor_invalid_cursor(self):
        """Test cursor pagination with invalid cursor."""
        _uid = uuid.uuid4().hex[:8]
        User.objects.create_user(
            email=f"paginate-invalid-cursor-{_uid}@example.com", password="testpass123"
        )

        queryset = User.objects.filter(email__contains=_uid)
        paginated, next_cursor, prev_cursor = paginate_queryset_cursor(
            queryset, page_size=5, cursor="invalid_cursor"
        )

        self.assertEqual(paginated.count(), 0)
        self.assertIsNone(next_cursor)
        self.assertIsNone(prev_cursor)
