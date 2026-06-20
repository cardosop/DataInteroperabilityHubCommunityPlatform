"""
Virtualization operations for DataHub SDK.

Provides methods for managing virtual datasets, query executions, and topology.
"""

from typing import Any, Dict, Optional

from .client import DataHubClient
from .errors import ConflictError, NotFoundError, ValidationError


class VirtualizationAPI:
    """
    Virtualization API.

    Provides methods for managing virtual datasets, query executions, and topology.
    """

    def __init__(self, client: DataHubClient):
        """
        Initialize Virtualization API.

        Args:
            client: DataHub client instance
        """
        self.client = client

    # Validation Helpers

    def _validate_dataset_id(self, dataset_id: str, param_name: str = "dataset_id") -> None:
        """
        Validate dataset ID format.

        Args:
            dataset_id: Dataset ID to validate
            param_name: Parameter name for error messages

        Raises:
            ValidationError: If dataset ID is invalid
        """
        if not dataset_id:
            raise ValidationError(
                f"{param_name} is required and cannot be empty",
            )
        if not isinstance(dataset_id, str):
            raise ValidationError(
                f"{param_name} must be a string",
            )
        dataset_id = dataset_id.strip()
        if not dataset_id:
            raise ValidationError(
                f"{param_name} cannot be empty or whitespace",
            )

    def _validate_execution_id(self, execution_id: str, param_name: str = "execution_id") -> None:
        """
        Validate execution ID format.

        Args:
            execution_id: Execution ID to validate
            param_name: Parameter name for error messages

        Raises:
            ValidationError: If execution ID is invalid
        """
        if not execution_id:
            raise ValidationError(
                f"{param_name} is required and cannot be empty",
            )
        if not isinstance(execution_id, str):
            raise ValidationError(
                f"{param_name} must be a string",
            )
        execution_id = execution_id.strip()
        if not execution_id:
            raise ValidationError(
                f"{param_name} cannot be empty or whitespace",
            )

    def _validate_page_params(self, page: int, page_size: int) -> None:
        """
        Validate pagination parameters.

        Args:
            page: Page number (must be >= 1)
            page_size: Page size (must be between 1 and 100)

        Raises:
            ValidationError: If pagination parameters are invalid
        """
        if page < 1:
            raise ValidationError(
                "Page number must be >= 1",
            )
        if page_size < 1 or page_size > 100:
            raise ValidationError(
                "Page size must be between 1 and 100",
            )

    # Dataset Methods

    async def create_dataset(
        self,
        name: str,
        query: str,
        query_type: str,
        description: Optional[str] = None,
        schema: Optional[Dict[str, Any]] = None,
        sources: Optional[list] = None,
        version: Optional[str] = None,
        status: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Create a virtual dataset.

        Args:
            name: Dataset name (required, unique per tenant)
            query: Query definition (SQL, SPARQL, federated query, etc.)
            query_type: Type of query (SQL, SPARQL, FEDERATED, GRAPHQL, REST)
            description: Optional dataset description
            schema: Optional output schema definition as JSON object
            sources: Optional list of source system configurations
            version: Optional version string (defaults to "1.0.0")
            status: Optional status (defaults to DRAFT)

        Returns:
            Created virtual dataset as dictionary

        Raises:
            ValidationError: If validation fails
            ConflictError: If dataset with same name/version already exists
        """
        if not name or not name.strip():
            raise ValidationError("name is required and cannot be empty")
        if not query or not query.strip():
            raise ValidationError("query is required and cannot be empty")
        if not query_type or not query_type.strip():
            raise ValidationError("query_type is required and cannot be empty")

        data: Dict[str, Any] = {
            "name": name.strip(),
            "query": query.strip(),
            "query_type": query_type.strip().upper(),
        }

        if description is not None:
            data["description"] = description
        if schema is not None:
            data["schema"] = schema
        if sources is not None:
            data["sources"] = sources
        if version is not None:
            data["version"] = version
        if status is not None:
            data["status"] = status.upper()

        try:
            return await self.client.post("virtualization/datasets/", data=data)
        except ValidationError:
            raise
        except ConflictError:
            raise
        except NotFoundError:
            raise
        except Exception as e:
            # Handle specific error cases
            from .errors import DataHubError

            if isinstance(e, DataHubError):
                if e.http_status == 400:
                    raise ValidationError(
                        str(e), getattr(e, "request_id", None), getattr(e, "details", None)
                    )
                elif e.http_status == 409:
                    raise ConflictError(
                        str(e), getattr(e, "request_id", None), getattr(e, "details", None)
                    )
            raise

    async def list_datasets(
        self,
        status: Optional[str] = None,
        query_type: Optional[str] = None,
        owner: Optional[str] = None,
        created_by: Optional[str] = None,
        search: Optional[str] = None,
        ordering: Optional[str] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> Dict[str, Any]:
        """
        List virtual datasets with optional filtering and pagination.

        Args:
            status: Filter by status (DRAFT, ACTIVE, INACTIVE, ARCHIVED)
            query_type: Filter by query type (SQL, SPARQL, FEDERATED, GRAPHQL, REST)
            owner: Filter by owner/created_by user ID (alias for created_by)
            created_by: Filter by created_by user ID
            search: Search in name, description, and query fields
            ordering: Order by field (e.g., name, -created_at). Prefix with - for descending.
            page: Page number (default: 1)
            page_size: Items per page (default: 50, max: 100)

        Returns:
            Paginated list of virtual datasets as dictionary with count, next, previous, results

        Raises:
            ValidationError: If pagination parameters are invalid
        """
        # Validate pagination parameters
        self._validate_page_params(page, page_size)

        # Build query parameters
        params: Dict[str, Any] = {
            "page": page,
            "page_size": page_size,
        }

        if status:
            params["status"] = status.upper()
        if query_type:
            params["query_type"] = query_type.upper()
        if owner:
            params["owner"] = owner
        if created_by:
            params["created_by"] = created_by
        if search:
            params["search"] = search
        if ordering:
            params["ordering"] = ordering

        try:
            return await self.client.get("virtualization/datasets/", params=params)
        except ValidationError:
            raise
        except Exception as e:
            # Handle specific error cases
            from .errors import DataHubError

            if isinstance(e, DataHubError) and e.http_status == 400:
                raise ValidationError(
                    str(e), getattr(e, "request_id", None), getattr(e, "details", None)
                )
            raise

    async def get_dataset(self, dataset_id: str) -> Dict[str, Any]:
        """
        Get virtual dataset by ID.

        Args:
            dataset_id: Virtual dataset ID

        Returns:
            Virtual dataset as dictionary

        Raises:
            ValidationError: If dataset ID is invalid
            NotFoundError: If virtual dataset not found
        """
        self._validate_dataset_id(dataset_id)

        try:
            return await self.client.get(f"virtualization/datasets/{dataset_id}/")
        except ValidationError:
            raise
        except NotFoundError:
            raise
        except Exception as e:
            # Handle specific error cases
            from .errors import DataHubError

            if isinstance(e, DataHubError):
                if e.http_status == 404:
                    raise NotFoundError(
                        f"Virtual dataset with ID '{dataset_id}' not found",
                        getattr(e, "request_id", None),
                    )
                elif e.http_status == 400:
                    raise ValidationError(
                        str(e), getattr(e, "request_id", None), getattr(e, "details", None)
                    )
            raise

    async def update_dataset(
        self,
        dataset_id: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        query: Optional[str] = None,
        query_type: Optional[str] = None,
        schema: Optional[Dict[str, Any]] = None,
        sources: Optional[list] = None,
        version: Optional[str] = None,
        status: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Update virtual dataset (partial update supported).

        Args:
            dataset_id: Virtual dataset ID
            name: Optional dataset name
            description: Optional dataset description
            query: Optional query definition
            query_type: Optional query type
            schema: Optional output schema definition
            sources: Optional list of source system configurations
            version: Optional version string
            status: Optional status

        Returns:
            Updated virtual dataset as dictionary

        Raises:
            ValidationError: If validation fails
            NotFoundError: If virtual dataset not found
        """
        self._validate_dataset_id(dataset_id)

        # Build update data (only include provided fields)
        data: Dict[str, Any] = {}

        if name is not None:
            if not name.strip():
                raise ValidationError("name cannot be empty")
            data["name"] = name.strip()
        if description is not None:
            data["description"] = description
        if query is not None:
            if not query.strip():
                raise ValidationError("query cannot be empty")
            data["query"] = query.strip()
        if query_type is not None:
            if not query_type.strip():
                raise ValidationError("query_type cannot be empty")
            data["query_type"] = query_type.strip().upper()
        if schema is not None:
            data["schema"] = schema
        if sources is not None:
            data["sources"] = sources
        if version is not None:
            data["version"] = version
        if status is not None:
            data["status"] = status.upper()

        if not data:
            raise ValidationError("At least one field must be provided for update")

        try:
            return await self.client.patch(f"virtualization/datasets/{dataset_id}/", data=data)
        except ValidationError:
            raise
        except NotFoundError:
            raise
        except Exception as e:
            # Handle specific error cases
            from .errors import DataHubError

            if isinstance(e, DataHubError):
                if e.http_status == 404:
                    raise NotFoundError(
                        f"Virtual dataset with ID '{dataset_id}' not found",
                        getattr(e, "request_id", None),
                    )
                elif e.http_status == 400:
                    raise ValidationError(
                        str(e), getattr(e, "request_id", None), getattr(e, "details", None)
                    )
            raise

    async def delete_dataset(self, dataset_id: str) -> None:
        """
        Delete virtual dataset.

        Args:
            dataset_id: Virtual dataset ID

        Raises:
            ValidationError: If dataset ID is invalid
            NotFoundError: If virtual dataset not found
        """
        self._validate_dataset_id(dataset_id)

        try:
            await self.client.delete(f"virtualization/datasets/{dataset_id}/")
        except ValidationError:
            raise
        except NotFoundError:
            raise
        except Exception as e:
            # Handle specific error cases
            from .errors import DataHubError

            if isinstance(e, DataHubError):
                if e.http_status == 404:
                    raise NotFoundError(
                        f"Virtual dataset with ID '{dataset_id}' not found",
                        getattr(e, "request_id", None),
                    )
                elif e.http_status == 400:
                    raise ValidationError(
                        str(e), getattr(e, "request_id", None), getattr(e, "details", None)
                    )
            raise

    # Query Execution Methods

    async def execute_query(
        self,
        dataset_id: str,
        query: Optional[str] = None,
        parameters: Optional[Dict[str, Any]] = None,
        execution_mode: Optional[str] = None,
        force_async: bool = False,
        timeout_seconds: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Execute a query on a virtual dataset.

        Supports synchronous and asynchronous execution modes. For synchronous mode,
        the query result is returned immediately. For asynchronous mode, a query
        execution record is returned and results can be retrieved later.

        Args:
            dataset_id: Virtual dataset ID
            query: Optional query string to execute (uses dataset query if not provided)
            parameters: Optional query parameters dictionary
            execution_mode: Execution mode (SYNC, ASYNC, SCHEDULED, MANUAL, AUTOMATED)
            force_async: Force asynchronous execution even for small queries (default: False)
            timeout_seconds: Query timeout in seconds (default: 300 for sync, 3600 for async)

        Returns:
            Query execution record as dictionary with:
            - id: Execution ID
            - virtual_dataset: Virtual dataset ID
            - query: Query text executed
            - parameters: Query parameters
            - execution_mode: Execution mode
            - status: Execution status (PENDING, RUNNING, COMPLETED, FAILED, CANCELLED)
            - started_at: Start timestamp (if started)
            - completed_at: Completion timestamp (if completed)
            - metrics: Execution metrics
            - execution_log: Execution logs

        Raises:
            ValidationError: If validation fails (invalid dataset ID, parameters, etc.)
            NotFoundError: If virtual dataset not found
        """
        self._validate_dataset_id(dataset_id)

        # Build request data
        data: Dict[str, Any] = {}

        if query is not None:
            if not query.strip():
                raise ValidationError("query cannot be empty if provided")
            data["query"] = query.strip()
        if parameters is not None:
            if not isinstance(parameters, dict):
                raise ValidationError("parameters must be a dictionary")
            data["parameters"] = parameters
        if execution_mode is not None:
            valid_modes = ["SYNC", "ASYNC", "SCHEDULED", "MANUAL", "AUTOMATED"]
            if execution_mode.upper() not in valid_modes:
                raise ValidationError(
                    f"execution_mode must be one of {valid_modes}, got: {execution_mode}"
                )
            data["execution_mode"] = execution_mode.upper()
        if force_async:
            data["force_async"] = True
        if timeout_seconds is not None:
            if not isinstance(timeout_seconds, int) or timeout_seconds < 1:
                raise ValidationError("timeout_seconds must be a positive integer")
            data["timeout_seconds"] = timeout_seconds

        try:
            return await self.client.post(
                f"virtualization/datasets/{dataset_id}/queries/", data=data
            )
        except ValidationError:
            raise
        except NotFoundError:
            raise
        except Exception as e:
            # Handle specific error cases
            from .errors import DataHubError

            if isinstance(e, DataHubError):
                if e.http_status == 404:
                    raise NotFoundError(
                        f"Virtual dataset with ID '{dataset_id}' not found",
                        getattr(e, "request_id", None),
                    )
                elif e.http_status == 400:
                    raise ValidationError(
                        str(e), getattr(e, "request_id", None), getattr(e, "details", None)
                    )
            raise

    async def list_query_executions(
        self,
        dataset_id: Optional[str] = None,
        status: Optional[str] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> Dict[str, Any]:
        """
        List query executions with optional filtering and pagination.

        Args:
            dataset_id: Optional filter by virtual dataset ID
            status: Optional filter by status (PENDING, RUNNING, COMPLETED, FAILED, CANCELLED)
            page: Page number (default: 1)
            page_size: Items per page (default: 50, max: 100)

        Returns:
            Paginated list of query executions as dictionary with count, next, previous, results

        Raises:
            ValidationError: If pagination parameters or filters are invalid
        """
        # Validate pagination parameters
        self._validate_page_params(page, page_size)

        # Validate dataset_id if provided
        if dataset_id is not None:
            self._validate_dataset_id(dataset_id, "dataset_id")

        # Validate status if provided
        if status is not None:
            valid_statuses = ["PENDING", "RUNNING", "COMPLETED", "FAILED", "CANCELLED"]
            if status.upper() not in valid_statuses:
                raise ValidationError(f"status must be one of {valid_statuses}, got: {status}")

        # Build query parameters
        params: Dict[str, Any] = {
            "page": page,
            "page_size": page_size,
        }

        if dataset_id:
            params["virtual_dataset_id"] = dataset_id
        if status:
            params["status"] = status.upper()

        try:
            return await self.client.get("virtualization/queries/", params=params)
        except ValidationError:
            raise
        except Exception as e:
            # Handle specific error cases
            from .errors import DataHubError

            if isinstance(e, DataHubError) and e.http_status == 400:
                raise ValidationError(
                    str(e), getattr(e, "request_id", None), getattr(e, "details", None)
                )
            raise

    async def get_query_execution(self, execution_id: str) -> Dict[str, Any]:
        """
        Get query execution by ID.

        Args:
            execution_id: Query execution ID

        Returns:
            Query execution record as dictionary with:
            - id: Execution ID
            - virtual_dataset: Virtual dataset ID
            - virtual_dataset_name: Virtual dataset name
            - query: Query text executed
            - parameters: Query parameters
            - execution_mode: Execution mode
            - status: Execution status
            - started_at: Start timestamp
            - completed_at: Completion timestamp
            - result_cache_key: Cache key for result
            - result_storage_path: Storage path for result
            - execution_log: Execution logs
            - metrics: Execution metrics
            - job: Associated job ID (if async execution)
            - created_at: Creation timestamp
            - updated_at: Last update timestamp

        Raises:
            ValidationError: If execution ID is invalid
            NotFoundError: If query execution not found
        """
        self._validate_execution_id(execution_id)

        try:
            return await self.client.get(f"virtualization/queries/{execution_id}/")
        except ValidationError:
            raise
        except NotFoundError:
            raise
        except Exception as e:
            # Handle specific error cases
            from .errors import DataHubError

            if isinstance(e, DataHubError):
                if e.http_status == 404:
                    raise NotFoundError(
                        f"Query execution with ID '{execution_id}' not found",
                        getattr(e, "request_id", None),
                    )
                elif e.http_status == 400:
                    raise ValidationError(
                        str(e), getattr(e, "request_id", None), getattr(e, "details", None)
                    )
            raise

    async def cancel_query_execution(self, execution_id: str) -> Dict[str, Any]:
        """
        Cancel a running or pending query execution.

        Only executions with status PENDING or RUNNING can be cancelled.
        Completed, failed, or already cancelled executions cannot be cancelled.

        Args:
            execution_id: Query execution ID

        Returns:
            Cancellation response as dictionary with:
            - execution_id: Execution ID
            - status: New status (CANCELLED)
            - message: Success message

        Raises:
            ValidationError: If execution ID is invalid or execution cannot be cancelled
            NotFoundError: If query execution not found
        """
        self._validate_execution_id(execution_id)

        try:
            return await self.client.post(f"virtualization/queries/{execution_id}/cancel/")
        except ValidationError:
            raise
        except NotFoundError:
            raise
        except Exception as e:
            # Handle specific error cases
            from .errors import DataHubError

            if isinstance(e, DataHubError):
                if e.http_status == 404:
                    raise NotFoundError(
                        f"Query execution with ID '{execution_id}' not found",
                        getattr(e, "request_id", None),
                    )
                elif e.http_status == 400:
                    # Execution cannot be cancelled (already completed, failed, etc.)
                    raise ValidationError(
                        str(e), getattr(e, "request_id", None), getattr(e, "details", None)
                    )
            raise

    async def get_query_result(
        self,
        execution_id: str,
        format: str = "json",
        page: Optional[int] = None,
        page_size: Optional[int] = None,
        offset: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Get query execution result in specified format.

        Supports multiple output formats (JSON, CSV, Parquet) and pagination.
        The execution must be completed (status: COMPLETED) to retrieve results.

        Args:
            execution_id: Query execution ID
            format: Output format - "json" (default), "csv", or "parquet"
            page: Page number for pagination (1-indexed, mutually exclusive with offset)
            page_size: Items per page (default: 50, max: 1000, mutually exclusive with limit)
            offset: Offset for pagination (mutually exclusive with page)
            limit: Maximum number of items to return (default: 50, max: 1000, mutually exclusive with page_size)

        Returns:
            Result data as dictionary with format-specific structure:
            - For JSON format:
              - execution_id: Execution ID
              - data: List of result rows (dictionaries)
              - total_count: Total number of rows
              - returned_count: Number of rows in this response
              - format: Output format ("json")
              - content_type: Content type ("application/json")
              - pagination: Pagination metadata (if paginated)
            - For CSV format:
              - execution_id: Execution ID
              - data: CSV string
              - total_count: Total number of rows
              - returned_count: Number of rows in CSV
              - format: Output format ("csv")
              - content_type: Content type ("text/csv")
            - For Parquet format:
              - execution_id: Execution ID
              - data: Base64-encoded Parquet file data
              - total_count: Total number of rows
              - returned_count: Number of rows in Parquet file
              - format: Output format ("parquet")
              - content_type: Content type ("application/parquet")

        Raises:
            ValidationError: If execution ID is invalid, format is unsupported,
                            pagination parameters are invalid, or execution is not completed
            NotFoundError: If query execution not found
        """
        self._validate_execution_id(execution_id)

        # Validate format
        valid_formats = ["json", "csv", "parquet"]
        format_lower = format.lower()
        if format_lower not in valid_formats:
            raise ValidationError(f"format must be one of {valid_formats}, got: {format}")

        # Validate pagination parameters
        # Either use page/page_size OR offset/limit, but not both
        if page is not None and offset is not None:
            raise ValidationError(
                "Cannot specify both page and offset. Use either page/page_size or offset/limit."
            )
        if page_size is not None and limit is not None:
            raise ValidationError(
                "Cannot specify both page_size and limit. Use either page/page_size or offset/limit."
            )

        # Validate page/page_size — each must be checked independently because
        # callers may legitimately pass page_size without page (it then applies
        # to the implicit first page). The previous logic only validated
        # page_size when page was also set, letting page_size=0 / page_size>1000
        # slip through to the backend.
        if page is not None and (not isinstance(page, int) or page < 1):
            raise ValidationError("page must be a positive integer >= 1")
        if page_size is not None and (
            not isinstance(page_size, int) or page_size < 1 or page_size > 1000
        ):
            raise ValidationError("page_size must be between 1 and 1000")

        # Validate offset/limit independently for the same reason as above.
        if offset is not None and (not isinstance(offset, int) or offset < 0):
            raise ValidationError("offset must be a non-negative integer")
        if limit is not None and (not isinstance(limit, int) or limit < 1 or limit > 1000):
            raise ValidationError("limit must be between 1 and 1000")

        # Build query parameters
        params: Dict[str, Any] = {
            "output_format": format_lower,  # Use output_format to avoid DRF content negotiation conflict
        }

        if page is not None:
            params["page"] = page
        if page_size is not None:
            params["page_size"] = page_size
        if offset is not None:
            params["offset"] = offset
        if limit is not None:
            params["limit"] = limit

        try:
            # For CSV and Parquet formats, the response may be raw content
            # We need to handle this appropriately
            response = await self.client.request(
                "GET",
                f"virtualization/queries/{execution_id}/result/",
                params=params,
            )

            # Check content type to determine how to parse response
            content_type = response.headers.get("content-type", "").lower()

            if format_lower == "csv":
                # CSV is returned as text/csv
                if "text/csv" in content_type or "csv" in content_type:
                    # Response is CSV string
                    csv_text = response.text
                    return {
                        "execution_id": execution_id,
                        "data": csv_text,
                        "total_count": len(csv_text.split("\n")) - 1
                        if csv_text
                        else 0,  # Approximate
                        "returned_count": len(csv_text.split("\n")) - 1 if csv_text else 0,
                        "format": "csv",
                        "content_type": "text/csv",
                    }
                else:
                    # Fallback: try to parse as JSON
                    return response.json()

            elif format_lower == "parquet":
                # Parquet is returned as application/parquet (binary)
                if "application/parquet" in content_type or "parquet" in content_type:
                    # Response is binary Parquet data
                    import base64

                    parquet_bytes = response.content
                    parquet_base64 = base64.b64encode(parquet_bytes).decode("utf-8")
                    return {
                        "execution_id": execution_id,
                        "data": parquet_base64,
                        "total_count": 0,  # Cannot determine from binary data
                        "returned_count": 0,
                        "format": "parquet",
                        "content_type": "application/parquet",
                    }
                else:
                    # Fallback: try to parse as JSON
                    return response.json()

            else:
                # JSON format - parse as JSON
                return response.json()

        except ValidationError:
            raise
        except NotFoundError:
            raise
        except Exception as e:
            # Handle specific error cases
            from .errors import DataHubError

            if isinstance(e, DataHubError):
                if e.http_status == 404:
                    raise NotFoundError(
                        f"Query execution with ID '{execution_id}' not found",
                        getattr(e, "request_id", None),
                    )
                elif e.http_status == 400:
                    # Execution not completed or other validation error
                    raise ValidationError(
                        str(e), getattr(e, "request_id", None), getattr(e, "details", None)
                    )
            raise

    # Topology Methods

    async def get_topology(
        self,
        include_health_metrics: bool = True,
    ) -> Dict[str, Any]:
        """
        Get complete virtualization topology including all virtual datasets, relationships, and health metrics.

        Args:
            include_health_metrics: Include health metrics in response (default: True)

        Returns:
            Topology data containing:
            - nodes: List of virtual dataset nodes
            - edges: List of dataset relationships
            - metadata: Topology metadata (tenant_id, dataset_count, relationship_count, generated_at)
            - summary: Summary statistics (total_datasets, active_datasets, total_relationships, average_health_score)

        Raises:
            ValidationError: If request is invalid
            ServerError: If server error occurs
        """
        params: Dict[str, Any] = {
            "include_health_metrics": str(include_health_metrics).lower(),
        }

        try:
            return await self.client.get("virtualization/topology/", params=params)
        except ValidationError:
            raise
        except Exception as e:
            # Handle specific error cases
            from .errors import DataHubError, ServerError

            if isinstance(e, DataHubError):
                if e.http_status == 400:
                    raise ValidationError(
                        str(e), getattr(e, "request_id", None), getattr(e, "details", None)
                    )
                elif e.http_status >= 500:
                    error_code = getattr(e, "code", None)
                    if not isinstance(error_code, str):
                        error_code = "INTERNAL_ERROR"
                    raise ServerError(
                        str(e),
                        code=error_code,
                        http_status=e.http_status,
                        request_id=getattr(e, "request_id", None),
                    )
            raise

    async def get_dataset_topology(
        self,
        dataset_id: str,
    ) -> Dict[str, Any]:
        """
        Get topology view for a specific virtual dataset including its relationships and health metrics.

        Args:
            dataset_id: Virtual dataset UUID

        Returns:
            Dataset topology data containing:
            - dataset: Dataset node information
            - relationships: List of relationships for this dataset
            - health_metrics: Dataset health metrics

        Raises:
            ValidationError: If dataset ID is invalid
            NotFoundError: If virtual dataset not found
            ServerError: If server error occurs
        """
        self._validate_dataset_id(dataset_id)

        try:
            return await self.client.get(f"virtualization/topology/{dataset_id}/")
        except ValidationError:
            raise
        except NotFoundError:
            raise
        except Exception as e:
            # Handle specific error cases
            from .errors import DataHubError, ServerError

            if isinstance(e, DataHubError):
                if e.http_status == 404:
                    raise NotFoundError(
                        f"Virtual dataset with ID '{dataset_id}' not found",
                        getattr(e, "request_id", None),
                    )
                elif e.http_status == 400:
                    raise ValidationError(
                        str(e), getattr(e, "request_id", None), getattr(e, "details", None)
                    )
                elif e.http_status >= 500:
                    error_code = getattr(e, "code", None)
                    if not isinstance(error_code, str):
                        error_code = "INTERNAL_ERROR"
                    raise ServerError(
                        str(e),
                        code=error_code,
                        http_status=e.http_status,
                        request_id=getattr(e, "request_id", None),
                    )
            raise
