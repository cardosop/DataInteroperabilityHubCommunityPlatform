"""
Tests for ``hub.apps.core.middleware.ContentLengthSafeCommonMiddleware``.

Covers the three behavioural paths of process_response:
- Normal (super delegates to CommonMiddleware)
- ContentNotRenderedError (caught gracefully, response returned)
- Other exceptions (propagated to caller)
"""

from unittest.mock import PropertyMock, patch

from django.http import HttpResponse
from django.template.response import ContentNotRenderedError
from django.test import RequestFactory, SimpleTestCase

from hub.apps.core.middleware import ContentLengthSafeCommonMiddleware


class ContentLengthSafeCommonMiddlewareTests(SimpleTestCase):
    """Tests for ContentLengthSafeCommonMiddleware.process_response."""

    def setUp(self):
        self.middleware = ContentLengthSafeCommonMiddleware(get_response=lambda r: None)
        self.factory = RequestFactory()

    def test_process_response_calls_super_and_sets_content_length(self):
        """Normal rendered response has Content-Length set by super."""
        request = self.factory.get("/")
        response = HttpResponse(b"hello")

        result = self.middleware.process_response(request, response)

        assert result is response
        assert result.has_header("Content-Length")
        assert result["Content-Length"] == "5"

    def test_process_response_catches_content_not_rendered_error(self):
        """ContentNotRenderedError raised by super is caught; response
        returned as-is without Content-Length header.

        Patches the .content property on the response instance to raise
        ContentNotRenderedError on access.  This simulates what happens
        when Django's CommonMiddleware calls ``response.content`` on an
        unrendered TemplateResponse — without breaking HttpResponse.__init__
        which assigns to ``self.content``.
        """
        request = self.factory.get("/")
        response = HttpResponse(b"stub")

        with patch.object(
            type(response),
            "content",
            new_callable=PropertyMock,
            side_effect=ContentNotRenderedError("not rendered"),
        ):
            result = self.middleware.process_response(request, response)

        # Middleware must return the original response without Content-Length
        assert result is response
        assert not result.has_header("Content-Length")

    def test_process_response_propagates_other_exceptions(self):
        """Non-ContentNotRendered errors are NOT caught — they propagate
        to the caller so they can be handled upstream."""
        request = self.factory.get("/")
        response = HttpResponse(b"stub")

        with (
            self.assertRaises(RuntimeError),
            patch.object(
                type(response),
                "content",
                new_callable=PropertyMock,
                side_effect=RuntimeError("something else broke"),
            ),
        ):
            self.middleware.process_response(request, response)

        assert "something else broke" in str(ctx.exception)
