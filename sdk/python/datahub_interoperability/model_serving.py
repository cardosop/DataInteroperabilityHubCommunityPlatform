"""
Model serving operations for DataHub SDK.

Provides high-level methods for deploying models as APIs, running predictions,
managing deployments, and conducting A/B tests with contract validation support.
"""
import asyncio
import re
import uuid
from typing import Dict, Any, List, Optional

from .client import DataHubClient
from .errors import (
    ValidationError,
    UnauthorizedError,
    ForbiddenError,
    NotFoundError,
    ServerError,
    ConflictError,
)


class ModelServingAPI:
    """
    Model serving API.

    Provides methods for deploying models as APIs, running predictions,
    managing deployments, A/B testing, and quality monitoring with
    contract validation integration.
    """

    def __init__(self, client: DataHubClient):
        """
        Initialize Model Serving API.

        Args:
            client: DataHub client instance
        """
        self.client = client

    def _validate_model_id(self, model_id: str, param_name: str = "model_id") -> None:
        """
        Validate model ID format (UUID).

        Args:
            model_id: Model ID to validate
            param_name: Parameter name for error messages

        Raises:
            ValidationError: If model ID is invalid
        """
        if not model_id:
            raise ValidationError(
                f"{param_name} is required",
                request_id=None,
                details={"field": param_name, "expected": "non-empty string (UUID)", "actual": "empty or None"},
            )

        if not isinstance(model_id, str):
            raise ValidationError(
                f"{param_name} must be a string",
                request_id=None,
                details={"field": param_name, "expected": "string (UUID)", "actual": type(model_id).__name__},
            )

        # Validate UUID format
        try:
            uuid.UUID(model_id)
        except (ValueError, TypeError):
            raise ValidationError(
                f"{param_name} must be a valid UUID",
                request_id=None,
                details={
                    "field": param_name,
                    "expected": "valid UUID format (e.g., '123e4567-e89b-12d3-a456-426614174000')",
                    "actual": model_id[:50] if len(model_id) > 50 else model_id,
                },
            )

    def _validate_serving_id(self, serving_id: str, param_name: str = "serving_id") -> None:
        """
        Validate serving ID format.

        Args:
            serving_id: Serving ID to validate
            param_name: Parameter name for error messages

        Raises:
            ValidationError: If serving ID is invalid
        """
        if not serving_id:
            raise ValidationError(
                f"{param_name} is required",
                request_id=None,
                details={"field": param_name, "expected": "non-empty string", "actual": "empty or None"},
            )

        if not isinstance(serving_id, str):
            raise ValidationError(
                f"{param_name} must be a string",
                request_id=None,
                details={"field": param_name, "expected": "string", "actual": type(serving_id).__name__},
            )

    def _validate_traffic_split(self, traffic_split: str) -> None:
        """
        Validate traffic split format.

        Traffic split should be in format "X:Y" where X and Y are integers
        representing the percentage split between variants.

        Args:
            traffic_split: Traffic split string to validate

        Raises:
            ValidationError: If traffic split format is invalid
        """
        if not traffic_split:
            raise ValidationError(
                "traffic_split is required",
                request_id=None,
                details={"field": "traffic_split", "expected": "non-empty string", "actual": "empty or None"},
            )

        if not isinstance(traffic_split, str):
            raise ValidationError(
                "traffic_split must be a string",
                request_id=None,
                details={"field": "traffic_split", "expected": "string", "actual": type(traffic_split).__name__},
            )

        # Validate format: "X:Y" where X and Y are integers
        traffic_split_pattern = r"^\d+:\d+$"
        if not re.match(traffic_split_pattern, traffic_split.strip()):
            raise ValidationError(
                "traffic_split must be in format 'X:Y' where X and Y are integers (e.g., '50:50', '80:20')",
                request_id=None,
                details={
                    "field": "traffic_split",
                    "expected": "string in format 'X:Y' (e.g., '50:50')",
                    "actual": traffic_split,
                },
            )

        # Validate that percentages sum to 100
        parts = traffic_split.strip().split(":")
        if len(parts) == 2:
            try:
                x = int(parts[0])
                y = int(parts[1])
                if x + y != 100:
                    raise ValidationError(
                        f"traffic_split percentages must sum to 100, got {x + y}",
                        request_id=None,
                        details={
                            "field": "traffic_split",
                            "expected": "percentages summing to 100",
                            "actual": f"{x + y}",
                        },
                    )
            except ValueError:
                raise ValidationError(
                    "traffic_split must contain integer values",
                    request_id=None,
                    details={"field": "traffic_split", "expected": "integers", "actual": traffic_split},
                )

    def _validate_input_data(self, input_data: Dict[str, Any]) -> None:
        """
        Validate input data for predictions.

        Args:
            input_data: Input data dictionary to validate

        Raises:
            ValidationError: If input data is invalid
        """
        if not isinstance(input_data, dict):
            raise ValidationError(
                "input_data must be a dictionary",
                request_id=None,
                details={"field": "input_data", "expected": "dict", "actual": type(input_data).__name__},
            )

        if not input_data:
            raise ValidationError(
                "input_data cannot be empty",
                request_id=None,
                details={"field": "input_data", "expected": "non-empty dict", "actual": "empty dict"},
            )

    async def _validate_contract_for_model(self, model_id: str) -> Optional[Dict[str, Any]]:
        """
        Validate model contract if available.

        Args:
            model_id: Model ID to validate contract for

        Returns:
            Contract data if found, None otherwise
        """
        try:
            # Try to get contract associated with model
            # This assumes models can be linked to contracts via asset_id or similar
            # For now, we'll attempt to get the model and check for contract
            from .contracts import ContractsAPI

            contracts_api = ContractsAPI(self.client)
            # Search for contracts with model_name matching
            # This is a placeholder - actual implementation depends on contract-model linking
            return None
        except Exception:
            # If contract validation fails, return None (non-blocking)
            return None

    async def deploy_model_as_api(
        self, model_id: str, endpoint: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Deploy a model as an API endpoint.

        Args:
            model_id: Model ID (UUID) to deploy
            endpoint: Optional custom endpoint URL (if not provided, system generates one)

        Returns:
            Dictionary containing serving details with endpoint URL:
            {
                "serving_id": str,
                "model_id": str,
                "endpoint": str,
                "status": str,
                "created_at": str,
                ...
            }

        Raises:
            ValidationError: If parameters are invalid
            NotFoundError: If model not found
            ConflictError: If model is already deployed
            ServerError: If deployment fails
        """
        # Validate parameters
        self._validate_model_id(model_id, "model_id")

        # Validate contract if available (non-blocking)
        await self._validate_contract_for_model(model_id)

        # Prepare deployment data
        data: Dict[str, Any] = {"model_id": model_id}
        if endpoint:
            data["endpoint"] = endpoint

        try:
            # Deploy via inference API endpoint
            response = await self.client.post("ml/inference/deployments/", data=data)
            if isinstance(response, dict):
                # Map response to serving details format
                return {
                    "serving_id": response.get("deployment_id", ""),
                    "model_id": response.get("model_id", model_id),
                    "endpoint": response.get("endpoint", ""),
                    "status": response.get("status", "DEPLOYING"),
                    "created_at": response.get("created_at", ""),
                    "updated_at": response.get("updated_at"),
                }
            else:
                raise ServerError("Invalid response format from API", "INVALID_RESPONSE", 500)
        except NotFoundError:
            raise NotFoundError(f"Model with id {model_id} not found")
        except ConflictError:
            raise ConflictError(f"Model {model_id} is already deployed")
        except Exception as e:
            if isinstance(e, (ValidationError, UnauthorizedError, ForbiddenError, NotFoundError, ConflictError, ServerError)):
                raise
            raise ServerError(f"Failed to deploy model: {str(e)}", "DEPLOYMENT_ERROR", 500)

    async def predict_via_api(self, model_id: str, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Run prediction via API using model ID.

        This method finds the active deployment for the model and runs prediction.

        Args:
            model_id: Model ID (UUID) to run prediction for
            input_data: Input data dictionary for prediction

        Returns:
            Dictionary containing prediction results:
            {
                "output": Any,
                "model_id": str,
                "serving_id": str,
                "status": str,
                ...
            }

        Raises:
            ValidationError: If parameters are invalid
            NotFoundError: If model or deployment not found
            ServerError: If prediction fails
        """
        # Validate parameters
        self._validate_model_id(model_id, "model_id")
        self._validate_input_data(input_data)

        # Validate contract inputs/outputs if available (non-blocking)
        contract = await self._validate_contract_for_model(model_id)
        if contract:
            # TODO: Add contract input validation logic here
            # This would validate input_data against contract schema
            pass

        try:
            # Wait for a READY deployment. Deployments are async — a freshly-
            # deployed model may still be in DEPLOYING state.  Poll up to 10s
            # (5 attempts × 2s interval) before giving up.
            serving_id = None
            max_attempts = 5
            for attempt in range(max_attempts):
                deployments = await self.list_deployed_models(model_id=model_id, status="READY")
                if deployments:
                    serving_id = deployments[0].get("serving_id") or deployments[0].get("deployment_id")
                    break
                if attempt < max_attempts - 1:
                    # Check if any deployment exists at all before waiting
                    all_deployments = await self.list_deployed_models(model_id=model_id)
                    if not all_deployments:
                        raise NotFoundError(f"No deployment found for model {model_id}")
                    await asyncio.sleep(2)

            if not serving_id:
                raise NotFoundError(f"No active deployment found for model {model_id}")

            # Run prediction
            prediction_data = {"deployment_id": serving_id, "input": input_data}
            response = await self.client.post("ml/inference/deployments/predict/", data=prediction_data)

            if isinstance(response, dict):
                # Map response to prediction results format
                result = {
                    "output": response.get("output", response),
                    "model_id": model_id,
                    "serving_id": serving_id,
                    "status": response.get("status", "success"),
                }

                # Validate contract outputs if available (non-blocking)
                if contract:
                    # TODO: Add contract output validation logic here
                    # This would validate result against contract schema
                    pass

                return result
            else:
                raise ServerError("Invalid response format from API", "INVALID_RESPONSE", 500)
        except NotFoundError:
            raise
        except Exception as e:
            if isinstance(e, (ValidationError, UnauthorizedError, ForbiddenError, NotFoundError, ConflictError, ServerError)):
                raise
            raise ServerError(f"Failed to run prediction: {str(e)}", "PREDICTION_ERROR", 500)

    async def list_deployed_models(
        self,
        model_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        List deployed models with optional filters.

        Args:
            model_id: Optional model ID to filter by
            status: Optional status to filter by (e.g., "READY", "DEPLOYING", "FAILED")
            limit: Optional maximum number of results to return
            offset: Optional offset for pagination

        Returns:
            List of dictionaries containing deployment information:
            [
                {
                    "serving_id": str,
                    "model_id": str,
                    "status": str,
                    "endpoint": str,
                    "created_at": str,
                    ...
                },
                ...
            ]

        Raises:
            ValidationError: If parameters are invalid
            ServerError: If API request fails
        """
        # Validate parameters
        if model_id:
            self._validate_model_id(model_id, "model_id")
        if limit is not None and (not isinstance(limit, int) or limit < 0):
            raise ValidationError(
                "limit must be a non-negative integer",
                request_id=None,
                details={"field": "limit", "expected": "non-negative integer", "actual": limit},
            )
        if offset is not None and (not isinstance(offset, int) or offset < 0):
            raise ValidationError(
                "offset must be a non-negative integer",
                request_id=None,
                details={"field": "offset", "expected": "non-negative integer", "actual": offset},
            )

        # Build query parameters
        params: Dict[str, Any] = {}
        if model_id:
            params["model_id"] = model_id
        if status:
            params["status"] = status
        if limit is not None:
            params["limit"] = limit
        if offset is not None:
            params["offset"] = offset

        try:
            response = await self.client.get("ml/inference/deployments/", params=params)
            if isinstance(response, dict):
                deployments = response.get("results", [])
            elif isinstance(response, list):
                deployments = response
            else:
                deployments = []

            # Map to serving format
            result = []
            for deployment in deployments:
                result.append({
                    "serving_id": deployment.get("deployment_id", ""),
                    "model_id": deployment.get("model_id", ""),
                    "status": deployment.get("status", "UNKNOWN"),
                    "endpoint": deployment.get("endpoint", ""),
                    "created_at": deployment.get("created_at", ""),
                    "updated_at": deployment.get("updated_at"),
                })

            return result
        except Exception as e:
            if isinstance(e, (ValidationError, UnauthorizedError, ForbiddenError, NotFoundError, ConflictError, ServerError)):
                raise
            raise ServerError(f"Failed to list deployed models: {str(e)}", "LIST_ERROR", 500)

    async def get_model_serving_details(self, serving_id: str) -> Dict[str, Any]:
        """
        Get detailed information about a model serving deployment.

        Args:
            serving_id: Serving ID (deployment ID) to get details for

        Returns:
            Dictionary containing serving details:
            {
                "serving_id": str,
                "model_id": str,
                "status": str,
                "endpoint": str,
                "created_at": str,
                "updated_at": str,
                "replicas": int,
                "metrics": dict,
                ...
            }

        Raises:
            ValidationError: If serving_id is invalid
            NotFoundError: If serving not found
            ServerError: If API request fails
        """
        # Validate parameters
        self._validate_serving_id(serving_id, "serving_id")

        try:
            response = await self.client.get(f"ml/inference/deployments/{serving_id}/")
            if isinstance(response, dict):
                # Map to serving details format
                return {
                    "serving_id": response.get("deployment_id", serving_id),
                    "model_id": response.get("model_id", ""),
                    "status": response.get("status", "UNKNOWN"),
                    "endpoint": response.get("endpoint", ""),
                    "created_at": response.get("created_at", ""),
                    "updated_at": response.get("updated_at"),
                    "replicas": response.get("replicas", 0),
                    "metrics": response.get("metrics", {}),
                }
            else:
                raise ServerError("Invalid response format from API", "INVALID_RESPONSE", 500)
        except NotFoundError:
            raise NotFoundError(f"Serving with id {serving_id} not found")
        except Exception as e:
            if isinstance(e, (ValidationError, UnauthorizedError, ForbiddenError, NotFoundError, ConflictError, ServerError)):
                raise
            raise ServerError(f"Failed to get serving details: {str(e)}", "GET_ERROR", 500)

    async def undeploy_model(self, serving_id: str) -> None:
        """
        Undeploy a model (remove serving deployment).

        Args:
            serving_id: Serving ID (deployment ID) to undeploy

        Raises:
            ValidationError: If serving_id is invalid
            NotFoundError: If serving not found
            ServerError: If undeployment fails
        """
        # Validate parameters
        self._validate_serving_id(serving_id, "serving_id")

        try:
            await self.client.delete(f"ml/inference/deployments/{serving_id}/")
        except NotFoundError:
            raise NotFoundError(f"Serving with id {serving_id} not found")
        except Exception as e:
            if isinstance(e, (ValidationError, UnauthorizedError, ForbiddenError, NotFoundError, ConflictError, ServerError)):
                raise
            raise ServerError(f"Failed to undeploy model: {str(e)}", "UNDEPLOY_ERROR", 500)

    async def get_model_quality_metrics(self, serving_id: str) -> Dict[str, Any]:
        """
        Get quality metrics for a model serving deployment.

        Args:
            serving_id: Serving ID (deployment ID) to get metrics for

        Returns:
            Dictionary containing quality metrics:
            {
                "serving_id": str,
                "total_requests": int,
                "successful_requests": int,
                "failed_requests": int,
                "avg_latency_ms": float,
                "accuracy": float,
                "precision": float,
                "recall": float,
                "f1_score": float,
                ...
            }

        Raises:
            ValidationError: If serving_id is invalid
            NotFoundError: If serving not found
            ServerError: If API request fails
        """
        # Validate parameters
        self._validate_serving_id(serving_id, "serving_id")

        try:
            response = await self.client.get(f"ml/inference/deployments/{serving_id}/metrics/")
            if isinstance(response, dict):
                # Map to quality metrics format
                metrics = response.get("metrics", {})
                return {
                    "serving_id": serving_id,
                    "total_requests": metrics.get("total_requests", 0),
                    "successful_requests": metrics.get("successful_requests", 0),
                    "failed_requests": metrics.get("failed_requests", 0),
                    "avg_latency_ms": metrics.get("avg_latency_ms", 0.0),
                    "accuracy": metrics.get("accuracy"),
                    "precision": metrics.get("precision"),
                    "recall": metrics.get("recall"),
                    "f1_score": metrics.get("f1_score"),
                }
            else:
                raise ServerError("Invalid response format from API", "INVALID_RESPONSE", 500)
        except NotFoundError:
            raise NotFoundError(f"Serving with id {serving_id} not found")
        except Exception as e:
            if isinstance(e, (ValidationError, UnauthorizedError, ForbiddenError, NotFoundError, ConflictError, ServerError)):
                raise
            raise ServerError(f"Failed to get quality metrics: {str(e)}", "METRICS_ERROR", 500)

    async def create_ab_test(
        self, model_id: str, variant_id: str, traffic_split: str
    ) -> Dict[str, Any]:
        """
        Create an A/B test for model variants.

        Args:
            model_id: Base model ID (UUID)
            variant_id: Variant model ID (UUID) to test against
            traffic_split: Traffic split in format "X:Y" (e.g., "50:50", "80:20")

        Returns:
            Dictionary containing A/B test data:
            {
                "ab_test_id": str,
                "model_id": str,
                "variant_id": str,
                "traffic_split": str,
                "status": str,
                "created_at": str,
                ...
            }

        Raises:
            ValidationError: If parameters are invalid
            NotFoundError: If model or variant not found
            ConflictError: If A/B test already exists
            ServerError: If A/B test creation fails
        """
        # Validate parameters
        self._validate_model_id(model_id, "model_id")
        self._validate_model_id(variant_id, "variant_id")
        self._validate_traffic_split(traffic_split)

        # Prepare A/B test data
        data: Dict[str, Any] = {
            "model_id": model_id,
            "variant_id": variant_id,
            "traffic_split": traffic_split,
        }

        try:
            # Note: A/B testing endpoint may not exist yet - this is a placeholder
            # In a real implementation, this would call /ml/inference/ab-tests/ or similar
            response = await self.client.post("ml/inference/ab-tests/", data=data)
            if isinstance(response, dict):
                return {
                    "ab_test_id": response.get("ab_test_id", response.get("id", "")),
                    "model_id": response.get("model_id", model_id),
                    "variant_id": response.get("variant_id", variant_id),
                    "traffic_split": response.get("traffic_split", traffic_split),
                    "status": response.get("status", "ACTIVE"),
                    "created_at": response.get("created_at", ""),
                }
            else:
                raise ServerError("Invalid response format from API", "INVALID_RESPONSE", 500)
        except NotFoundError:
            raise NotFoundError(f"Model {model_id} or variant {variant_id} not found")
        except ConflictError:
            raise ConflictError(f"A/B test already exists for model {model_id}")
        except Exception as e:
            if isinstance(e, (ValidationError, UnauthorizedError, ForbiddenError, NotFoundError, ConflictError, ServerError)):
                raise
            raise ServerError(f"Failed to create A/B test: {str(e)}", "AB_TEST_ERROR", 500)

    async def list_ab_tests(
        self,
        model_id: Optional[str] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        List A/B tests with optional filters.

        Args:
            model_id: Optional model ID to filter by
            limit: Optional maximum number of results to return
            offset: Optional offset for pagination

        Returns:
            List of dictionaries containing A/B test information:
            [
                {
                    "ab_test_id": str,
                    "model_id": str,
                    "variant_id": str,
                    "traffic_split": str,
                    "status": str,
                    "created_at": str,
                    ...
                },
                ...
            ]

        Raises:
            ValidationError: If parameters are invalid
            ServerError: If API request fails
        """
        # Validate parameters
        if model_id:
            self._validate_model_id(model_id, "model_id")
        if limit is not None and (not isinstance(limit, int) or limit < 0):
            raise ValidationError(
                "limit must be a non-negative integer",
                request_id=None,
                details={"field": "limit", "expected": "non-negative integer", "actual": limit},
            )
        if offset is not None and (not isinstance(offset, int) or offset < 0):
            raise ValidationError(
                "offset must be a non-negative integer",
                request_id=None,
                details={"field": "offset", "expected": "non-negative integer", "actual": offset},
            )

        # Build query parameters
        params: Dict[str, Any] = {}
        if model_id:
            params["model_id"] = model_id
        if limit is not None:
            params["limit"] = limit
        if offset is not None:
            params["offset"] = offset

        try:
            # Note: A/B testing endpoint may not exist yet - this is a placeholder
            response = await self.client.get("ml/inference/ab-tests/", params=params)
            if isinstance(response, dict):
                ab_tests = response.get("results", [])
            elif isinstance(response, list):
                ab_tests = response
            else:
                ab_tests = []

            # Map to A/B test format
            result = []
            for ab_test in ab_tests:
                result.append({
                    "ab_test_id": ab_test.get("ab_test_id", ab_test.get("id", "")),
                    "model_id": ab_test.get("model_id", ""),
                    "variant_id": ab_test.get("variant_id", ""),
                    "traffic_split": ab_test.get("traffic_split", ""),
                    "status": ab_test.get("status", "UNKNOWN"),
                    "created_at": ab_test.get("created_at", ""),
                })

            return result
        except Exception as e:
            if isinstance(e, (ValidationError, UnauthorizedError, ForbiddenError, NotFoundError, ConflictError, ServerError)):
                raise
            raise ServerError(f"Failed to list A/B tests: {str(e)}", "LIST_ERROR", 500)

    async def get_ab_test_details(self, ab_test_id: str) -> Dict[str, Any]:
        """
        Get detailed information about an A/B test including metrics for each variant.

        Args:
            ab_test_id: A/B test ID to get details for

        Returns:
            Dictionary containing A/B test details with metrics:
            {
                "ab_test_id": str,
                "model_id": str,
                "variant_id": str,
                "traffic_split": str,
                "status": str,
                "created_at": str,
                "metrics": {
                    "model": {
                        "total_requests": int,
                        "successful_requests": int,
                        "avg_latency_ms": float,
                        "accuracy": float,
                        ...
                    },
                    "variant": {
                        "total_requests": int,
                        "successful_requests": int,
                        "avg_latency_ms": float,
                        "accuracy": float,
                        ...
                    }
                },
                ...
            }

        Raises:
            ValidationError: If ab_test_id is invalid
            NotFoundError: If A/B test not found
            ServerError: If API request fails
        """
        # Validate parameters
        self._validate_serving_id(ab_test_id, "ab_test_id")

        try:
            # Note: A/B testing endpoint may not exist yet - this is a placeholder
            response = await self.client.get(f"ml/inference/ab-tests/{ab_test_id}/")
            if isinstance(response, dict):
                # Map to A/B test details format with metrics
                return {
                    "ab_test_id": response.get("ab_test_id", response.get("id", ab_test_id)),
                    "model_id": response.get("model_id", ""),
                    "variant_id": response.get("variant_id", ""),
                    "traffic_split": response.get("traffic_split", ""),
                    "status": response.get("status", "UNKNOWN"),
                    "created_at": response.get("created_at", ""),
                    "metrics": {
                        "model": response.get("model_metrics", {}),
                        "variant": response.get("variant_metrics", {}),
                    },
                }
            else:
                raise ServerError("Invalid response format from API", "INVALID_RESPONSE", 500)
        except NotFoundError:
            raise NotFoundError(f"A/B test with id {ab_test_id} not found")
        except Exception as e:
            if isinstance(e, (ValidationError, UnauthorizedError, ForbiddenError, NotFoundError, ConflictError, ServerError)):
                raise
            raise ServerError(f"Failed to get A/B test details: {str(e)}", "GET_ERROR", 500)
