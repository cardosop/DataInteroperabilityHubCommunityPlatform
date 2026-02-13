"""
Contract Views Format Handling

Handles format suffix conflicts for lineage visualization and export endpoints.
"""


class ContractFormatHandlingMixin:
    """
    Mixin for handling format suffix conflicts.

    Overrides initialize_request and perform_content_negotiation to handle
    format parameter conflicts for lineage visualization and export endpoints.
    """

    def initialize_request(self, request, *args, **kwargs):
        """
        Override initialize_request to handle format suffix conflicts.

        When format is in query parameters (e.g., ?format=dot, ?format=hubcontract),
        DRF's format suffix patterns can interfere. For the lineage visualization
        and export endpoints, we need to ensure query parameters take precedence
        over format suffixes.
        """
        # Call parent to get the DRF request object
        drf_request = super().initialize_request(request, *args, **kwargs)

        # Check if this is the lineage visualization or export endpoint
        # The action name is determined by the URL path
        path = getattr(drf_request, "path", "")
        if not path and hasattr(request, "META"):
            path = request.META.get("PATH_INFO", "")
        is_lineage_visualization = "lineage/visualization" in path
        is_export = "export" in path

        if is_lineage_visualization or is_export:
            # If format is in query parameters, clear any format from kwargs
            # This prevents DRF from trying to match format suffix patterns
            if "format" in request.GET or "format" in drf_request.query_params:
                # Get format from query params to check if it's a valid format
                # suffix
                format_in_query = request.GET.get("format") or (
                    drf_request.query_params.get("format")
                )

                # Valid format suffixes for DRF (json, yaml, etc.)
                valid_format_suffixes = ["json", "yaml", "xml", "csv"]

                # Only clear format if it's NOT a valid format suffix
                # This allows format suffixes to work for other endpoints
                if format_in_query and format_in_query.lower() not in (valid_format_suffixes):
                    # Clear format from kwargs if it was set by format suffix
                    # pattern
                    if "format" in kwargs:
                        # Store it temporarily but don't use it for routing
                        drf_request._format_from_suffix = kwargs.pop("format")
                    # Also clear format attribute if it was set
                    # CRITICAL: This must be done before content negotiation
                    if hasattr(drf_request, "format") and drf_request.format:
                        drf_request._original_format = drf_request.format
                        drf_request.format = None
                    # Disable format suffix handling for this request
                    # CRITICAL: Set format_kwarg to None to prevent DRF from
                    # trying to use format suffixes
                    # This must be set on the viewset instance, not just the
                    # request
                    self.format_kwarg = None
                    # Also set on the request object for consistency
                    if hasattr(drf_request, "format_kwarg"):
                        drf_request.format_kwarg = None

        return drf_request

    def perform_content_negotiation(self, request, force=False):
        """
        Override perform_content_negotiation to handle format parameter
        conflicts.

        For export endpoint, prevent DRF from treating ?format=hubcontract as
        a format suffix.
        """
        # Check if this is the export endpoint
        # Use action name if available, otherwise check path
        is_export = False
        if hasattr(self, "action") and self.action == "export_contract":
            is_export = True
        else:
            # Check path from request
            path = getattr(request, "path", "")
            if not path and hasattr(request, "META"):
                path = request.META.get("PATH_INFO", "")
            is_export = "export" in path

        if is_export:
            # Get format from query params
            format_in_query = None
            if hasattr(request, "query_params"):
                format_in_query = request.query_params.get("format")
            elif hasattr(request, "GET"):
                format_in_query = request.GET.get("format")

            # Valid format suffixes for DRF (json, yaml, etc.)
            valid_format_suffixes = ["json", "yaml", "xml", "csv"]

            # If format is in query params and it's NOT a valid format suffix,
            # disable format suffix handling for this request
            if format_in_query and format_in_query.lower() not in (valid_format_suffixes):
                # Temporarily disable format_kwarg to prevent DRF from trying
                # to use format suffixes
                original_format_kwarg = getattr(self, "format_kwarg", None)
                self.format_kwarg = None
                try:
                    # Perform content negotiation without format suffix
                    return super().perform_content_negotiation(request, force=force)
                finally:
                    # Restore original format_kwarg
                    if original_format_kwarg is not None:
                        self.format_kwarg = original_format_kwarg
                    elif hasattr(self, "format_kwarg"):
                        # If it was None, we might need to explicitly set it
                        # back
                        # But for now, just leave it as None since we disabled
                        # it
                        pass

        # For other endpoints, use default behavior
        return super().perform_content_negotiation(request, force=force)
