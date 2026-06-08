"""
Core middleware utilities.
"""
from django.middleware.common import CommonMiddleware as _CommonMiddleware
from django.template.response import ContentNotRenderedError


class ContentLengthSafeCommonMiddleware(_CommonMiddleware):
    """Subclass of CommonMiddleware that handles unrendered TemplateResponse.

    When upstream middleware (e.g. idempotency, rate-limiting, auth)
    returns a DRF ``Response`` before the DRF handler chain has run,
    the response hasn't been rendered yet.  Django's stock
    ``CommonMiddleware`` accesses ``response.content`` to compute the
    ``Content-Length`` header, which raises ``ContentNotRenderedError``
    on unrendered ``TemplateResponse`` subclasses.

    This subclass catches that exception and proceeds without the
    ``Content-Length`` header — the WSGI server handles it on fully
    buffered responses anyway.
    """

    def process_response(self, request, response):
        try:
            return super().process_response(request, response)
        except ContentNotRenderedError:
            return response
