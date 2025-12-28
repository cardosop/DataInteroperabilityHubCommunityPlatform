"""
Transformation operations for DataHub SDK.

Provides methods for managing transformation pipelines, executions, previews, and wrangling sessions.
"""
from typing import Dict, Any, Optional
from .client import DataHubClient
from .errors import ValidationError, NotFoundError, ConflictError


class TransformationAPI:
    """
    Transformation API.

    Provides methods for managing transformation pipelines, executions, previews, and wrangling sessions.
    """

    def __init__(self, client: DataHubClient):
        """
        Initialize Transformation API.

        Args:
            client: DataHub client instance
        """
        self.client = client

    # Validation Helpers

    def _validate_pipeline_id(self, pipeline_id: str, param_name: str = "pipeline_id") -> None:
        """
        Validate pipeline ID format.

        Args:
            pipeline_id: Pipeline ID to validate
            param_name: Parameter name for error messages

        Raises:
            ValidationError: If pipeline ID is invalid
        """
        if not pipeline_id:
            raise ValidationError(
                f"{param_name} is required and cannot be empty",
            )
        if not isinstance(pipeline_id, str):
            raise ValidationError(
                f"{param_name} must be a string",
            )
        pipeline_id = pipeline_id.strip()
        if not pipeline_id:
            raise ValidationError(
                f"{param_name} cannot be empty or whitespace",
            )

    def _validate_pipeline_name(self, name: str) -> None:
        """
        Validate pipeline name.

        Args:
            name: Pipeline name to validate

        Raises:
            ValidationError: If pipeline name is invalid
        """
        if not name:
            raise ValidationError(
                "Pipeline name is required and cannot be empty",
            )
        if not isinstance(name, str):
            raise ValidationError(
                "Pipeline name must be a string",
            )
        name = name.strip()
        if not name:
            raise ValidationError(
                "Pipeline name cannot be empty or whitespace",
            )

    def _validate_status(self, status: str, allowed_statuses: Optional[list] = None) -> None:
        """
        Validate pipeline status.

        Args:
            status: Status to validate
            allowed_statuses: List of allowed status values (default: ["DRAFT", "ACTIVE", "ARCHIVED"])

        Raises:
            ValidationError: If status is invalid
        """
        if allowed_statuses is None:
            allowed_statuses = ["DRAFT", "ACTIVE", "ARCHIVED"]

        if status not in allowed_statuses:
            raise ValidationError(
                f"Status must be one of {allowed_statuses}, got: {status}",
            )

    def _validate_page_params(self, page: int, page_size: int) -> None:
        """
        Validate pagination parameters.

        Args:
            page: Page number
            page_size: Page size

        Raises:
            ValidationError: If pagination parameters are invalid
        """
        if page < 1:
            raise ValidationError(
                "Page number must be >= 1",
            )
        if page_size < 1:
            raise ValidationError(
                "Page size must be >= 1",
            )
        # Note: page_size is capped at 100 in list_pipelines, not validated here
        # This allows the method to cap it rather than raise an error

    # Pipeline Management

    async def create_pipeline(
        self,
        name: str,
        description: Optional[str] = None,
        pipeline_definition: Optional[Dict[str, Any]] = None,
        version: Optional[str] = None,
        status: str = "DRAFT",
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Create a new transformation pipeline.

        Args:
            name: Pipeline name (required)
            description: Pipeline description (optional)
            pipeline_definition: Pipeline definition as dict (optional)
            version: Pipeline version (optional)
            status: Pipeline status - "DRAFT", "ACTIVE", or "ARCHIVED" (default: "DRAFT")
            **kwargs: Additional pipeline parameters

        Returns:
            Created pipeline data

        Raises:
            ValidationError: If pipeline data is invalid
            ConflictError: If pipeline name already exists
        """
        # Validate inputs
        self._validate_pipeline_name(name)
        self._validate_status(status)

        # Prepare data
        data: Dict[str, Any] = {
            "name": name.strip(),
            "status": status,
        }

        if description is not None:
            if not isinstance(description, str):
                raise ValidationError(
                    "Description must be a string",
                )
            data["description"] = description.strip() if description else description

        if pipeline_definition is not None:
            if not isinstance(pipeline_definition, dict):
                raise ValidationError(
                    "Pipeline definition must be a dictionary",
                )
            data["pipeline_definition"] = pipeline_definition

        if version:
            if not isinstance(version, str):
                raise ValidationError(
                    "Version must be a string",
                )
            data["version"] = version.strip()

        data.update(kwargs)

        try:
            return await self.client.post("transformation/pipelines/", data=data)
        except ValidationError:
            raise
        except ConflictError:
            raise
        except Exception as e:
            # Handle other errors appropriately
            from .errors import DataHubError
            if isinstance(e, DataHubError) and e.http_status == 409:
                raise ConflictError(
                    f"Pipeline with name '{name}' already exists",
                    getattr(e, 'request_id', None),
                )
            raise

    async def list_pipelines(
        self,
        status: Optional[str] = None,
        version: Optional[str] = None,
        search: Optional[str] = None,
        ordering: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Dict[str, Any]:
        """
        List transformation pipelines with filtering and pagination.

        Args:
            status: Filter by status - "DRAFT", "ACTIVE", or "ARCHIVED" (optional)
            version: Filter by version (optional)
            search: Search in name and description (optional)
            ordering: Order by field - "name", "status", "version", "created_at", "updated_at".
                     Prefix with "-" for descending (e.g., "-created_at") (optional)
            page: Page number (default: 1)
            page_size: Items per page, max 100 (default: 20)

        Returns:
            Paginated list of pipelines

        Raises:
            ValidationError: If filter parameters are invalid
        """
        # Validate pagination parameters
        self._validate_page_params(page, page_size)

        # Validate status if provided
        if status:
            self._validate_status(status)

        # Prepare parameters
        params: Dict[str, Any] = {
            "page": page,
            "page_size": min(page_size, 100),  # Enforce max page size
        }

        if status:
            params["status"] = status
        if version:
            if not isinstance(version, str):
                raise ValidationError(
                    "Version must be a string",
                )
            params["version"] = version.strip()
        if search:
            if not isinstance(search, str):
                raise ValidationError(
                    "Search must be a string",
                )
            params["search"] = search.strip()
        if ordering:
            if not isinstance(ordering, str):
                raise ValidationError(
                    "Ordering must be a string",
                )
            params["ordering"] = ordering.strip()

        return await self.client.get("transformation/pipelines/", params=params)

    async def get_pipeline(self, pipeline_id: str) -> Dict[str, Any]:
        """
        Get a transformation pipeline by ID.

        Args:
            pipeline_id: Pipeline ID

        Returns:
            Pipeline data

        Raises:
            ValidationError: If pipeline_id is invalid
            NotFoundError: If pipeline not found
        """
        # Validate pipeline ID
        self._validate_pipeline_id(pipeline_id)

        try:
            return await self.client.get(f"transformation/pipelines/{pipeline_id}/")
        except NotFoundError:
            raise
        except Exception as e:
            # Handle 404 errors
            from .errors import DataHubError
            if isinstance(e, DataHubError) and e.http_status == 404:
                raise NotFoundError(
                    f"Pipeline with ID '{pipeline_id}' not found",
                    getattr(e, 'request_id', None),
                )
            raise

    async def update_pipeline(
        self,
        pipeline_id: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        pipeline_definition: Optional[Dict[str, Any]] = None,
        version: Optional[str] = None,
        status: Optional[str] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Update a transformation pipeline.

        Args:
            pipeline_id: Pipeline ID
            name: Pipeline name (optional)
            description: Pipeline description (optional)
            pipeline_definition: Pipeline definition as dict (optional)
            version: Pipeline version (optional)
            status: Pipeline status - "DRAFT", "ACTIVE", or "ARCHIVED" (optional)
            **kwargs: Additional pipeline parameters

        Returns:
            Updated pipeline data

        Raises:
            ValidationError: If pipeline_id or data is invalid
            NotFoundError: If pipeline not found
            ConflictError: If pipeline name already exists
        """
        # Validate pipeline ID
        self._validate_pipeline_id(pipeline_id)

        # Validate inputs if provided
        if name is not None:
            self._validate_pipeline_name(name)
        if status is not None:
            self._validate_status(status)

        # Prepare data
        data: Dict[str, Any] = {}

        if name is not None:
            data["name"] = name.strip()
        if description is not None:
            if not isinstance(description, str):
                raise ValidationError(
                    "Description must be a string",
                )
            data["description"] = description.strip() if description else description
        if pipeline_definition is not None:
            if not isinstance(pipeline_definition, dict):
                raise ValidationError(
                    "Pipeline definition must be a dictionary",
                )
            data["pipeline_definition"] = pipeline_definition
        if version is not None:
            if not isinstance(version, str):
                raise ValidationError(
                    "Version must be a string",
                )
            data["version"] = version.strip()
        if status is not None:
            data["status"] = status
        data.update(kwargs)

        # Ensure at least one field is being updated
        if not data:
            raise ValidationError(
                "At least one field must be provided for update",
            )

        try:
            return await self.client.patch(f"transformation/pipelines/{pipeline_id}/", data=data)
        except ValidationError:
            raise
        except NotFoundError:
            raise
        except ConflictError:
            raise
        except Exception as e:
            # Handle specific error cases
            from .errors import DataHubError
            if isinstance(e, DataHubError):
                if e.http_status == 404:
                    raise NotFoundError(
                        f"Pipeline with ID '{pipeline_id}' not found",
                        getattr(e, 'request_id', None),
                    )
                elif e.http_status == 409:
                    raise ConflictError(
                        f"Pipeline with name '{name}' already exists",
                        getattr(e, 'request_id', None),
                    )
            raise

    async def delete_pipeline(self, pipeline_id: str) -> None:
        """
        Delete a transformation pipeline.

        Args:
            pipeline_id: Pipeline ID

        Raises:
            ValidationError: If pipeline_id is invalid
            NotFoundError: If pipeline not found
        """
        # Validate pipeline ID
        self._validate_pipeline_id(pipeline_id)

        try:
            await self.client.delete(f"transformation/pipelines/{pipeline_id}/")
        except NotFoundError:
            raise
        except Exception as e:
            # Handle 404 errors
            from .errors import DataHubError
            if isinstance(e, DataHubError) and e.http_status == 404:
                raise NotFoundError(
                    f"Pipeline with ID '{pipeline_id}' not found",
                    getattr(e, 'request_id', None),
                )
            raise

    # Execution Management

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

    def _validate_execution_mode(self, execution_mode: str) -> None:
        """
        Validate execution mode.

        Args:
            execution_mode: Execution mode to validate

        Raises:
            ValidationError: If execution mode is invalid
        """
        valid_modes = ["SYNC", "ASYNC"]
        if execution_mode not in valid_modes:
            raise ValidationError(
                f"Execution mode must be one of {valid_modes}, got: {execution_mode}",
            )

    async def execute_pipeline(
        self,
        pipeline_id: str,
        asset_id: str,
        execution_mode: str = "ASYNC",
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Execute a transformation pipeline.

        Args:
            pipeline_id: Pipeline ID to execute
            asset_id: Source asset ID to transform
            execution_mode: Execution mode - "ASYNC" or "SYNC" (default: "ASYNC")
            **kwargs: Additional execution parameters (e.g., idempotency_key)

        Returns:
            Execution data with execution_id, status, pipeline_id, and asset_id

        Raises:
            ValidationError: If pipeline_id, asset_id, or execution_mode is invalid
            NotFoundError: If pipeline or asset not found
            ConflictError: If execution conflicts (e.g., duplicate idempotency_key)
            ServerError: If server error occurs
            NetworkError: If network error occurs
        """
        # Validate inputs
        self._validate_pipeline_id(pipeline_id)
        # Validate asset_id
        if not asset_id:
            raise ValidationError("asset_id is required and cannot be empty")
        if not isinstance(asset_id, str):
            raise ValidationError("asset_id must be a string")
        asset_id = asset_id.strip()
        if not asset_id:
            raise ValidationError("asset_id cannot be empty or whitespace")
        if execution_mode:
            self._validate_execution_mode(execution_mode)

        # Prepare request data
        data: Dict[str, Any] = {
            "asset_id": asset_id,
            "execution_mode": execution_mode,
        }
        data.update(kwargs)

        try:
            return await self.client.post(
                f"transformation/pipelines/{pipeline_id}/execute/",
                data=data,
            )
        except ValidationError:
            raise
        except NotFoundError:
            raise
        except ConflictError:
            raise
        except Exception as e:
            # Handle specific error cases
            from .errors import DataHubError
            if isinstance(e, DataHubError):
                if e.http_status == 404:
                    raise NotFoundError(
                        f"Pipeline with ID '{pipeline_id}' or asset not found",
                        getattr(e, 'request_id', None),
                    )
                elif e.http_status == 409:
                    raise ConflictError(
                        f"Execution conflict: {str(e)}",
                        getattr(e, 'request_id', None),
                    )
            raise

    async def list_executions(
        self,
        pipeline_id: str,
        status: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Dict[str, Any]:
        """
        List pipeline executions with filtering and pagination.

        Args:
            pipeline_id: Pipeline ID
            status: Filter by status - "PENDING", "RUNNING", "COMPLETED", "FAILED", "CANCELLED" (optional)
            page: Page number (default: 1, must be >= 1)
            page_size: Items per page, max 100 (default: 20, must be >= 1 and <= 100)

        Returns:
            Paginated list of executions with count, next, previous, and results

        Raises:
            ValidationError: If pipeline_id or pagination parameters are invalid
            NotFoundError: If pipeline not found
            ServerError: If server error occurs
            NetworkError: If network error occurs
        """
        # Validate inputs
        self._validate_pipeline_id(pipeline_id)
        self._validate_page_params(page, page_size)

        # Prepare query parameters
        params: Dict[str, Any] = {
            "page": page,
            "page_size": min(page_size, 100),  # Enforce max page size
        }

        if status:
            if not isinstance(status, str):
                raise ValidationError("Status must be a string")
            status = status.strip().upper()
            valid_statuses = ["PENDING", "RUNNING", "COMPLETED", "FAILED", "CANCELLED"]
            if status not in valid_statuses:
                raise ValidationError(
                    f"Status must be one of {valid_statuses}, got: {status}",
                )
            params["status"] = status

        try:
            return await self.client.get(
                f"transformation/pipelines/{pipeline_id}/executions/",
                params=params,
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
                        f"Pipeline with ID '{pipeline_id}' not found",
                        getattr(e, 'request_id', None),
                    )
            raise

    async def get_execution(self, execution_id: str) -> Dict[str, Any]:
        """
        Get a pipeline execution by ID.

        Args:
            execution_id: Execution ID

        Returns:
            Execution data with full execution details

        Raises:
            ValidationError: If execution_id is invalid
            NotFoundError: If execution not found
            ServerError: If server error occurs
            NetworkError: If network error occurs
        """
        # Validate execution ID
        self._validate_execution_id(execution_id)

        try:
            return await self.client.get(f"transformation/executions/{execution_id}/")
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
                        f"Execution with ID '{execution_id}' not found",
                        getattr(e, 'request_id', None),
                    )
            raise

    async def cancel_execution(self, execution_id: str) -> Dict[str, Any]:
        """
        Cancel a pipeline execution.

        Args:
            execution_id: Execution ID

        Returns:
            Cancellation result with execution_id, status, and message

        Raises:
            ValidationError: If execution_id is invalid or execution cannot be cancelled
            NotFoundError: If execution not found
            ServerError: If server error occurs
            NetworkError: If network error occurs
        """
        # Validate execution ID
        self._validate_execution_id(execution_id)

        try:
            return await self.client.post(f"transformation/executions/{execution_id}/cancel/")
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
                        f"Execution with ID '{execution_id}' not found",
                        getattr(e, 'request_id', None),
                    )
                elif e.http_status == 400:
                    # Execution cannot be cancelled (e.g., already completed)
                    raise ValidationError(
                        f"Execution cannot be cancelled: {str(e)}",
                        getattr(e, 'request_id', None),
                    )
            raise

    # Preview Management

    def _validate_asset_id(self, asset_id: str, param_name: str = "asset_id") -> None:
        """
        Validate asset ID format.

        Args:
            asset_id: Asset ID to validate
            param_name: Parameter name for error messages

        Raises:
            ValidationError: If asset ID is invalid
        """
        if not asset_id:
            raise ValidationError(
                f"{param_name} is required and cannot be empty",
            )
        if not isinstance(asset_id, str):
            raise ValidationError(
                f"{param_name} must be a string",
            )
        asset_id = asset_id.strip()
        if not asset_id:
            raise ValidationError(
                f"{param_name} cannot be empty or whitespace",
            )

    def _validate_sample_size(self, sample_size: int) -> None:
        """
        Validate sample size.

        Args:
            sample_size: Sample size to validate

        Raises:
            ValidationError: If sample size is invalid
        """
        if not isinstance(sample_size, int):
            raise ValidationError(
                "sample_size must be an integer",
            )
        if sample_size < 1:
            raise ValidationError(
                "sample_size must be >= 1",
            )
        if sample_size > 10000:
            raise ValidationError(
                "sample_size cannot exceed 10000",
            )

    def _validate_sampling_method(self, sampling_method: str) -> None:
        """
        Validate sampling method.

        Args:
            sampling_method: Sampling method to validate

        Raises:
            ValidationError: If sampling method is invalid
        """
        if not isinstance(sampling_method, str):
            raise ValidationError(
                "sampling_method must be a string",
            )
        sampling_method = sampling_method.strip().lower()
        if sampling_method not in ["first_n", "random"]:
            raise ValidationError(
                "sampling_method must be 'first_n' or 'random'",
            )

    def _validate_preview_id(self, preview_id: str, param_name: str = "preview_id") -> None:
        """
        Validate preview ID format.

        Args:
            preview_id: Preview ID to validate
            param_name: Parameter name for error messages

        Raises:
            ValidationError: If preview ID is invalid
        """
        if not preview_id:
            raise ValidationError(
                f"{param_name} is required and cannot be empty",
            )
        if not isinstance(preview_id, str):
            raise ValidationError(
                f"{param_name} must be a string",
            )
        preview_id = preview_id.strip()
        if not preview_id:
            raise ValidationError(
                f"{param_name} cannot be empty or whitespace",
            )

    async def generate_preview(
        self,
        pipeline_id: str,
        asset_id: str,
        sample_size: int = 100,
        sampling_method: str = "first_n",
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Generate a preview of transformation results.

        Generates a preview by executing the pipeline on a sample of data from the asset.
        The preview includes input sample, output sample, and analysis of the transformation.

        Args:
            pipeline_id: Pipeline ID to preview
            asset_id: Input asset ID
            sample_size: Number of rows to sample (default: 100, max: 10000)
            sampling_method: Sampling method - "first_n" or "random" (default: "first_n")
            **kwargs: Additional preview parameters

        Returns:
            Dictionary with preview results:
            - preview_id: Unique preview identifier
            - pipeline_id: Pipeline ID
            - pipeline_name: Pipeline name
            - asset_id: Asset ID
            - asset_name: Asset name
            - input_sample: Sample input data (first 10 rows)
            - output_sample: Sample output data (first 10 rows)
            - input_sample_size: Number of rows in input sample
            - output_sample_size: Number of rows in output sample
            - analysis: Result analysis (row_count_changes, schema_changes, quality_impact)
            - cached: Whether result was from cache
            - generated_at: Timestamp when preview was generated
            - expires_at: Timestamp when preview expires

        Raises:
            ValidationError: If preview parameters are invalid
            NotFoundError: If pipeline or asset not found
            RateLimitError: If rate limit exceeded
            ServerError: If server error occurs
        """
        # Validate inputs
        self._validate_pipeline_id(pipeline_id)
        self._validate_asset_id(asset_id)
        self._validate_sample_size(sample_size)
        self._validate_sampling_method(sampling_method)

        # Prepare data
        data: Dict[str, Any] = {
            "asset_id": asset_id.strip(),
            "sample_size": sample_size,
            "sampling_method": sampling_method.strip().lower(),
        }
        data.update(kwargs)

        try:
            return await self.client.post(f"transformation/pipelines/{pipeline_id}/preview/", data=data)
        except ValidationError:
            raise
        except NotFoundError:
            raise
        except Exception as e:
            # Handle specific error cases
            http_status = getattr(e, 'http_status', None)
            if http_status is not None:
                if http_status == 404:
                    raise NotFoundError(
                        f"Pipeline with ID '{pipeline_id}' or asset with ID '{asset_id}' not found",
                        getattr(e, 'request_id', None),
                    )
                elif http_status == 429:
                    from .errors import RateLimitError
                    retry_after = getattr(e, 'retry_after', None)
                    raise RateLimitError(
                        "Rate limit exceeded for preview generation. Please try again later.",
                        getattr(e, 'request_id', None),
                        retry_after,
                    )
                elif http_status >= 500:
                    from .errors import ServerError
                    raise ServerError(
                        f"Server error occurred while generating preview: {str(e)}",
                        getattr(e, 'code', 'INTERNAL_ERROR'),
                        http_status,
                        getattr(e, 'request_id', None),
                    )
            raise

    async def get_preview(self, preview_id: str) -> Dict[str, Any]:
        """
        Get a preview result by ID.

        Retrieves a previously generated preview result. Preview results are cached
        and expire after a certain time period (typically 1 hour).

        Args:
            preview_id: Preview ID returned from generate_preview()

        Returns:
            Dictionary with preview results:
            - preview_id: Unique preview identifier
            - pipeline_id: Pipeline ID
            - pipeline_name: Pipeline name
            - asset_id: Asset ID
            - asset_name: Asset name
            - input_sample: Sample input data (first 10 rows)
            - output_sample: Sample output data (first 10 rows)
            - input_sample_size: Number of rows in input sample
            - output_sample_size: Number of rows in output sample
            - analysis: Result analysis (row_count_changes, schema_changes, quality_impact)
            - cached: Whether result was from cache
            - generated_at: Timestamp when preview was generated
            - expires_at: Timestamp when preview expires

        Raises:
            ValidationError: If preview_id is invalid
            NotFoundError: If preview not found
            ServerError: If preview has expired (410) or server error occurs
        """
        # Validate preview ID
        self._validate_preview_id(preview_id)

        try:
            return await self.client.get(f"transformation/previews/{preview_id}/")
        except NotFoundError:
            raise
        except Exception as e:
            # Handle specific error cases
            from .errors import DataHubError
            if isinstance(e, DataHubError):
                if e.http_status == 404:
                    raise NotFoundError(
                        f"Preview with ID '{preview_id}' not found",
                        getattr(e, 'request_id', None),
                    )
                elif e.http_status == 410:
                    # Preview expired
                    from .errors import ServerError
                    raise ServerError(
                        f"Preview with ID '{preview_id}' has expired",
                        "PREVIEW_EXPIRED",
                        410,
                        getattr(e, 'request_id', None),
                    )
                elif e.http_status >= 500:
                    from .errors import ServerError
                    raise ServerError(
                        f"Server error occurred while retrieving preview: {str(e)}",
                        getattr(e, 'code', 'INTERNAL_ERROR'),
                        e.http_status,
                        getattr(e, 'request_id', None),
                    )
            raise

    # Wrangling Management

    def _validate_session_id(self, session_id: str, param_name: str = "session_id") -> None:
        """
        Validate session ID format.

        Args:
            session_id: Session ID to validate
            param_name: Parameter name for error messages

        Raises:
            ValidationError: If session ID is invalid
        """
        if not session_id:
            raise ValidationError(
                f"{param_name} is required and cannot be empty",
            )
        if not isinstance(session_id, str):
            raise ValidationError(
                f"{param_name} must be a string",
            )
        session_id = session_id.strip()
        if not session_id:
            raise ValidationError(
                f"{param_name} cannot be empty or whitespace",
            )

    def _validate_wrangling_operation(self, operation: Dict[str, Any]) -> None:
        """
        Validate wrangling operation structure.

        Args:
            operation: Operation dictionary to validate

        Raises:
            ValidationError: If operation is invalid
        """
        if not isinstance(operation, dict):
            raise ValidationError(
                "Operation must be a dictionary",
            )
        if "type" not in operation:
            raise ValidationError(
                "Operation must have 'type' field",
            )
        if not isinstance(operation["type"], str):
            raise ValidationError(
                "Operation 'type' must be a string",
            )
        operation_type = operation["type"].strip()
        if not operation_type:
            raise ValidationError(
                "Operation 'type' cannot be empty or whitespace",
            )
        if "parameters" not in operation:
            raise ValidationError(
                "Operation must have 'parameters' field",
            )
        if not isinstance(operation["parameters"], dict):
            raise ValidationError(
                "Operation 'parameters' must be a dictionary",
            )

    async def start_wrangling(
        self,
        asset_id: str,
        operation: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Start a new wrangling session for an asset.

        Creates a new wrangling session and applies an initial operation.
        If no operation is provided, a default no-op filter operation is used.

        Args:
            asset_id: Asset ID to wrangle (required)
            operation: Optional initial operation to apply (dict with 'type' and 'parameters')
            **kwargs: Additional wrangling session parameters

        Returns:
            Dictionary with wrangling session data:
            - session_id: Unique session identifier
            - asset_id: Asset ID being wrangled
            - asset_name: Asset name
            - current_state: Current data state after operations
            - operation_history: List of operations performed
            - applied_operations_count: Number of applied operations
            - can_undo: Whether undo is possible
            - can_redo: Whether redo is possible
            - wrangling_script: Generated script representation
            - created_at: Session creation timestamp
            - updated_at: Last update timestamp

        Raises:
            ValidationError: If asset_id or operation is invalid
            NotFoundError: If asset not found
            ServerError: If server error occurs
            NetworkError: If network error occurs
        """
        # Validate asset_id
        self._validate_asset_id(asset_id)

        # Backend requires operation, so provide a default no-op filter if none provided
        if operation is None:
            operation = {
                "type": "FILTER",
                "parameters": {
                    "condition": "1 == 1"  # No-op filter that doesn't change data
                }
            }

        # Validate operation
        self._validate_wrangling_operation(operation)

        # Prepare data
        data: Dict[str, Any] = {
            "asset_id": asset_id.strip(),
            "operation": operation,
        }

        data.update(kwargs)

        try:
            return await self.client.post("transformation/wrangling/", data=data)
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
                        f"Asset with ID '{asset_id}' not found",
                        getattr(e, 'request_id', None),
                    )
                elif e.http_status == 400:
                    raise ValidationError(
                        f"Invalid wrangling parameters: {str(e)}",
                        getattr(e, 'request_id', None),
                    )
            raise

    async def apply_wrangling_operation(
        self,
        session_id: str,
        operation: Dict[str, Any],
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Apply a wrangling operation to an existing session.

        Applies a new operation to the wrangling session, updating the current state
        and adding the operation to the history.

        Args:
            session_id: Wrangling session ID (required)
            operation: Operation definition with 'type' and 'parameters' fields (required)
            **kwargs: Additional operation parameters

        Returns:
            Dictionary with updated session data:
            - session_id: Session identifier
            - operation_id: ID of the applied operation
            - asset_id: Asset ID being wrangled
            - current_state: Updated data state after operation
            - operation_history: Updated list of operations
            - applied_operations_count: Updated count of applied operations
            - can_undo: Whether undo is possible
            - can_redo: Whether redo is possible
            - wrangling_script: Updated script representation
            - updated_at: Last update timestamp

        Raises:
            ValidationError: If session_id or operation is invalid
            NotFoundError: If session not found
            ServerError: If server error occurs
            NetworkError: If network error occurs
        """
        # Validate session_id
        self._validate_session_id(session_id)

        # Validate operation
        self._validate_wrangling_operation(operation)

        # Backend requires asset_id even when applying to existing session
        # Get the session first to extract asset_id
        try:
            session = await self.get_wrangling_session(session_id)
            asset_id = session.get('asset_id')
            if not asset_id:
                raise ValidationError(
                    "Session does not have an asset_id. Cannot apply operation.",
                )
        except NotFoundError:
            raise
        except Exception as e:
            # If getting session fails, try without asset_id (will fail with proper error)
            asset_id = None

        # Prepare data
        data: Dict[str, Any] = {
            "session_id": session_id.strip(),
            "operation": operation,
        }

        # Include asset_id if we have it (backend requires it)
        if asset_id:
            data["asset_id"] = str(asset_id)

        data.update(kwargs)

        try:
            return await self.client.post("transformation/wrangling/", data=data)
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
                        f"Wrangling session with ID '{session_id}' not found",
                        getattr(e, 'request_id', None),
                    )
                elif e.http_status == 400:
                    raise ValidationError(
                        f"Invalid wrangling operation: {str(e)}",
                        getattr(e, 'request_id', None),
                    )
            raise

    async def undo_wrangling(self, session_id: str) -> Dict[str, Any]:
        """
        Undo the last wrangling operation in a session.

        Reverts the most recently applied operation, moving the history position
        backward and restoring the previous data state.

        Args:
            session_id: Wrangling session ID (required)

        Returns:
            Dictionary with updated session data:
            - session_id: Session identifier
            - undone_operation: The operation that was undone (or None if none)
            - can_undo: Whether another undo is possible
            - can_redo: Whether redo is possible
            - applied_operations_count: Updated count of applied operations
            - updated_at: Last update timestamp

        Raises:
            ValidationError: If session_id is invalid or no operations to undo
            NotFoundError: If session not found
            ServerError: If server error occurs
            NetworkError: If network error occurs
        """
        # Validate session_id
        self._validate_session_id(session_id)

        try:
            return await self.client.post(f"transformation/wrangling/{session_id}/undo/")
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
                        f"Wrangling session with ID '{session_id}' not found",
                        getattr(e, 'request_id', None),
                    )
                elif e.http_status == 400:
                    # Cannot undo (e.g., no operations to undo)
                    raise ValidationError(
                        f"Cannot undo: {str(e)}",
                        getattr(e, 'request_id', None),
                    )
            raise

    async def redo_wrangling(self, session_id: str) -> Dict[str, Any]:
        """
        Redo the next wrangling operation in a session.

        Re-applies the next operation in the history, moving the history position
        forward and updating the data state.

        Args:
            session_id: Wrangling session ID (required)

        Returns:
            Dictionary with updated session data:
            - session_id: Session identifier
            - redone_operation: The operation that was redone (or None if none)
            - can_undo: Whether undo is possible
            - can_redo: Whether another redo is possible
            - applied_operations_count: Updated count of applied operations
            - updated_at: Last update timestamp

        Raises:
            ValidationError: If session_id is invalid or no operations to redo
            NotFoundError: If session not found
            ServerError: If server error occurs
            NetworkError: If network error occurs
        """
        # Validate session_id
        self._validate_session_id(session_id)

        try:
            return await self.client.post(f"transformation/wrangling/{session_id}/redo/")
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
                        f"Wrangling session with ID '{session_id}' not found",
                        getattr(e, 'request_id', None),
                    )
                elif e.http_status == 400:
                    # Cannot redo (e.g., no operations to redo)
                    raise ValidationError(
                        f"Cannot redo: {str(e)}",
                        getattr(e, 'request_id', None),
                    )
            raise

    async def get_wrangling_session(self, session_id: str) -> Dict[str, Any]:
        """
        Get a wrangling session by ID.

        Retrieves detailed information about a wrangling session including
        current state, operation history, and metadata.

        Args:
            session_id: Wrangling session ID (required)

        Returns:
            Dictionary with session data:
            - session_id: Session identifier
            - asset_id: Asset ID being wrangled
            - asset_name: Asset name
            - name: Session name
            - description: Session description
            - current_state: Current data state after all operations
            - operation_history: List of all operations in the session
            - history_position: Current position in operation history
            - applied_operations_count: Number of applied operations
            - can_undo: Whether undo is possible
            - can_redo: Whether redo is possible
            - wrangling_script: Generated script representation
            - metadata: Additional metadata
            - created_at: Session creation timestamp
            - updated_at: Last update timestamp

        Raises:
            ValidationError: If session_id is invalid
            NotFoundError: If session not found
            ServerError: If server error occurs
            NetworkError: If network error occurs
        """
        # Validate session_id
        self._validate_session_id(session_id)

        try:
            return await self.client.get(f"transformation/wrangling/{session_id}/")
        except NotFoundError:
            raise
        except Exception as e:
            # Handle specific error cases
            from .errors import DataHubError
            if isinstance(e, DataHubError):
                if e.http_status == 404:
                    raise NotFoundError(
                        f"Wrangling session with ID '{session_id}' not found",
                        getattr(e, 'request_id', None),
                    )
                elif e.http_status >= 500:
                    from .errors import ServerError
                    raise ServerError(
                        f"Server error occurred while retrieving wrangling session: {str(e)}",
                        getattr(e, 'code', 'INTERNAL_ERROR'),
                        e.http_status,
                        getattr(e, 'request_id', None),
                    )
            raise

