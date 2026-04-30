"""
Phase 227 Wave 1 (227.L9.2) — DRF renderer + content negotiation for
JSON Schema responses.

The canonical IANA media type for JSON Schema documents is
``application/schema+json`` (registered at
https://www.iana.org/assignments/media-types/application/schema+json).
Some JSON Schema validators (e.g., ``ajv-cli``,
``json-schema-validator``) branch on the content-type to decide
whether to treat the body as a schema or as a regular JSON document.
Serving plain ``application/json`` works but loses that signal.

DRF's default ``JSONRenderer`` hard-codes ``media_type = "application/json"``
and ``Response.render()`` writes that string into the
``Content-Type`` header at finalisation — overwriting any header we
set manually on the response object. Subclassing ``JSONRenderer`` and
configuring ``renderer_classes`` on the ``@action`` decorator is the
canonical DRF pattern; the renderer's ``media_type`` propagates
through ``response.accepted_renderer`` to the final header.

Content negotiation
-------------------
A bare ``JSONSchemaRenderer`` would 406-Not-Acceptable any client
that sends ``Accept: application/json`` (a very common default).
RFC 6839 §3.1 says structured-suffix media types (e.g.
``application/schema+json``) SHOULD be considered compatible with
their base type (``application/json``) — but DRF's default
``DefaultContentNegotiation.media_type_matches`` does string-level
matching only and does NOT honour the suffix rule.

``StructuredSuffixContentNegotiation`` below implements that
compatibility: when the client sends ``Accept: application/json``,
it matches any renderer whose ``media_type`` ends in ``+json``. The
RESPONSE Content-Type is still the renderer's full media type
(``application/schema+json``) — so the server upgrades the type
hint per RFC 7231 §3.1.1.5 (the server may select a more specific
media type when satisfying an ``Accept`` request).
"""

from rest_framework.exceptions import NotAcceptable
from rest_framework.negotiation import DefaultContentNegotiation
from rest_framework.renderers import JSONRenderer
from rest_framework.utils.mediatypes import _MediaType


class JSONSchemaRenderer(JSONRenderer):
    """JSON renderer with the IANA-registered ``application/schema+json``
    media type. Body serialisation is byte-identical to ``JSONRenderer``;
    only the response Content-Type changes."""

    media_type = "application/schema+json"
    format = "schema+json"


class StructuredSuffixContentNegotiation(DefaultContentNegotiation):
    """Content-negotiation class that honours RFC 6839 structured
    suffixes. ``Accept: application/json`` matches any renderer whose
    ``media_type`` ends in ``+json``; the response is served with the
    renderer's full media type (e.g. ``application/schema+json``).

    Without this class, a client sending ``Accept: application/json``
    against an endpoint configured with only ``JSONSchemaRenderer``
    would receive HTTP 406 Not Acceptable — even though the renderer
    produces a valid JSON document. With this class, the client gets
    the response and a ``Content-Type: application/schema+json``
    header, which DRF-aware clients can branch on while plain JSON
    clients see a regular JSON body.
    """

    def select_renderer(self, request, renderers, format_suffix=None):
        # Try DRF's default first — covers exact matches and ``*/*``.
        try:
            return super().select_renderer(
                request, renderers, format_suffix=format_suffix
            )
        except NotAcceptable:
            # Fall through to the RFC 6839 suffix-matching path below.
            pass

        # RFC 6839 fallback: parse Accept header, look for any media
        # type with subtype ``json`` (structured-suffix or not), and
        # match against renderers whose ``media_type`` is ``+json``-
        # suffixed.
        header = request.META.get("HTTP_ACCEPT", "*/*")
        accept_list = [token.strip() for token in header.split(",")]

        for accept_media_type in accept_list:
            try:
                accept_parsed = _MediaType(accept_media_type)
            except Exception:
                continue
            # Only fire the suffix relaxation when the client
            # explicitly asked for ``application/json`` (or any
            # ``*/json``). Avoid relaxing for ``text/html`` etc.
            if (
                accept_parsed.full_type != "application/json"
                and accept_parsed.sub_type != "json"
            ):
                continue
            for renderer in renderers:
                renderer_media = getattr(renderer, "media_type", "")
                if renderer_media and renderer_media.endswith("+json"):
                    # The server-chosen media type is the renderer's
                    # full media type per RFC 7231 §3.1.1.5 — the
                    # server may upgrade the response type when the
                    # client's Accept is satisfiable in a more
                    # specific way.
                    return renderer, renderer_media

        # No suffix-relaxed match either — re-raise NotAcceptable.
        raise NotAcceptable()
