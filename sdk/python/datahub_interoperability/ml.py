"""
ML Model Registry, Training, and Inference operations for DataHub SDK.

Provides high-level methods for managing ML models, training jobs, and inference deployments
with ODH (Open Data Hub) integration.
"""
import re
import uuid
from typing import Dict, Any, List, Optional
from .client import DataHubClient
from .errors import (
    DataHubError,
    ValidationError,
    NotFoundError,
    ConflictError,
    ServerError,
)


class ODHIntegrationAPI:
    """
    ODH Integration API for ML Model Registry management.

    Provides methods for creating, updating, listing, and managing ML models
    with ODH Model Registry integration.
    """

    def __init__(self, client: DataHubClient):
        """
        Initialize ODH Integration API.

        Args:
            client: DataHub client instance
        """
        self.client = client

    def _validate_uuid(self, value: str, param_name: str = "id") -> None:
        """
        Validate UUID format.

        Args:
            value: UUID string to validate
            param_name: Parameter name for error messages

        Raises:
            ValidationError: If UUID format is invalid
        """
        if not value:
            raise ValidationError(
                f"{param_name} is required",
                details={"field": param_name, "expected": "non-empty UUID string"},
            )

        if not isinstance(value, str):
            raise ValidationError(
                f"{param_name} must be a string",
                details={"field": param_name, "expected": "string", "actual": type(value).__name__},
            )

        try:
            uuid.UUID(value)
        except (ValueError, TypeError):
            raise ValidationError(
                f"{param_name} must be a valid UUID",
                details={
                    "field": param_name,
                    "expected": "valid UUID format (e.g., '123e4567-e89b-12d3-a456-426614174000')",
                    "actual": value[:50] if len(value) > 50 else value,
                },
            )

    def _validate_model_type(self, model_type: Optional[str]) -> None:
        """
        Validate model type.

        Args:
            model_type: Model type to validate

        Raises:
            ValidationError: If model type is invalid
        """
        if model_type is None:
            return  # Optional parameter

        valid_types = [
            "CLASSIFICATION",
            "REGRESSION",
            "CLUSTERING",
            "NLP",
            "COMPUTER_VISION",
            "RECOMMENDATION",
            "TIME_SERIES",
            "ANOMALY_DETECTION",
            "OTHER",
        ]

        if not isinstance(model_type, str):
            raise ValidationError(
                "model_type must be a string",
                details={"field": "model_type", "expected": "string", "actual": type(model_type).__name__},
            )

        if model_type.upper() not in valid_types:
            raise ValidationError(
                f"model_type must be one of: {', '.join(valid_types)}",
                details={"field": "model_type", "expected": f"one of: {', '.join(valid_types)}", "actual": model_type},
            )

    def _validate_model_status(self, status: Optional[str]) -> None:
        """
        Validate model status.

        Args:
            status: Model status to validate

        Raises:
            ValidationError: If status is invalid
        """
        if status is None:
            return  # Optional parameter

        valid_statuses = ["TRAINING", "TRAINED", "DEPLOYED", "FAILED", "ARCHIVED"]

        if not isinstance(status, str):
            raise ValidationError(
                "status must be a string",
                details={"field": "status", "expected": "string", "actual": type(status).__name__},
            )

        if status.upper() not in valid_statuses:
            raise ValidationError(
                f"status must be one of: {', '.join(valid_statuses)}",
                details={"field": "status", "expected": f"one of: {', '.join(valid_statuses)}", "actual": status},
            )

    async def list_models(
        self,
        asset_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        List ML models with optional filters.

        Args:
            asset_id: Filter by asset ID (UUID)
            status: Filter by model status (TRAINING, TRAINED, DEPLOYED, FAILED, ARCHIVED)
            limit: Maximum number of results to return
            offset: Offset for pagination

        Returns:
            List of model dictionaries

        Raises:
            ValidationError: If parameters are invalid
            NotFoundError: If API endpoint not found
            ServerError: If API request fails
        """
        # Validate parameters
        if asset_id:
            self._validate_uuid(asset_id, "asset_id")
        if status:
            self._validate_model_status(status)
        if limit is not None and (not isinstance(limit, int) or limit < 0):
            raise ValidationError("limit must be a non-negative integer")
        if offset is not None and (not isinstance(offset, int) or offset < 0):
            raise ValidationError("offset must be a non-negative integer")

        # Build query parameters
        params: Dict[str, Any] = {}
        if asset_id:
            params["asset_id"] = asset_id
        if status:
            params["status"] = status.upper()
        if limit is not None:
            params["limit"] = limit
        if offset is not None:
            params["offset"] = offset

        try:
            response = await self.client.get("/ml/models/", params=params)
            # Handle both paginated response (dict with 'results') and direct list response
            if isinstance(response, dict):
                return response.get("results", [])
            elif isinstance(response, list):
                return response
            else:
                return []
        except NotFoundError:
            raise
        except Exception as e:
            if isinstance(e, (ValidationError, NotFoundError, ConflictError, ServerError)):
                raise
            raise ServerError(f"Failed to list models: {str(e)}")

    async def get_model(self, model_id: str) -> Dict[str, Any]:
        """
        Get ML model by ID.

        Args:
            model_id: Model ID (UUID)

        Returns:
            Model dictionary

        Raises:
            ValidationError: If model_id is invalid
            NotFoundError: If model not found
            ServerError: If API request fails
        """
        self._validate_uuid(model_id, "model_id")

        try:
            response = await self.client.get(f"/ml/models/{model_id}/")
            if isinstance(response, dict):
                return response
            else:
                raise ServerError("Invalid response format from API")
        except NotFoundError:
            raise NotFoundError(f"Model with id {model_id} not found")
        except Exception as e:
            if isinstance(e, (ValidationError, NotFoundError, ConflictError, ServerError)):
                raise
            raise ServerError(f"Failed to get model: {str(e)}")

    async def create_model(
        self,
        odh_model_id: str,
        odh_model_version: str,
        asset_id: str,
        model_type: str,
        contract_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Create a new ML model link.

        Args:
            odh_model_id: ODH Model Registry model ID
            odh_model_version: ODH Model Registry model version
            asset_id: Hub asset ID to link (UUID)
            model_type: Type of ML model (CLASSIFICATION, REGRESSION, etc.)
            contract_id: Optional Hub contract ID to link (UUID)

        Returns:
            Created model dictionary

        Raises:
            ValidationError: If parameters are invalid
            ConflictError: If model already exists
            ServerError: If API request fails
        """
        # Validate parameters
        if not odh_model_id or not isinstance(odh_model_id, str):
            raise ValidationError("odh_model_id is required and must be a string")
        if not odh_model_version or not isinstance(odh_model_version, str):
            raise ValidationError("odh_model_version is required and must be a string")
        self._validate_uuid(asset_id, "asset_id")
        self._validate_model_type(model_type)
        if contract_id:
            self._validate_uuid(contract_id, "contract_id")

        # Build request data
        data: Dict[str, Any] = {
            "odh_model_id": odh_model_id,
            "odh_model_version": odh_model_version,
            "asset_id": asset_id,
            "model_type": model_type.upper(),
        }
        if contract_id:
            data["contract_id"] = contract_id

        try:
            response = await self.client.post("/ml/models/", data=data)
            if isinstance(response, dict):
                return response
            else:
                raise ServerError("Invalid response format from API")
        except ConflictError:
            raise
        except Exception as e:
            if isinstance(e, (ValidationError, NotFoundError, ConflictError, ServerError)):
                raise
            raise ServerError(f"Failed to create model: {str(e)}")

    async def update_model(
        self,
        model_id: str,
        asset_id: Optional[str] = None,
        contract_id: Optional[str] = None,
        status: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Update ML model.

        Args:
            model_id: Model ID (UUID)
            asset_id: Optional asset ID to link (UUID)
            contract_id: Optional contract ID to link (UUID)
            status: Optional model status (TRAINING, TRAINED, DEPLOYED, FAILED, ARCHIVED)

        Returns:
            Updated model dictionary

        Raises:
            ValidationError: If parameters are invalid
            NotFoundError: If model not found
            ServerError: If API request fails
        """
        self._validate_uuid(model_id, "model_id")
        if asset_id:
            self._validate_uuid(asset_id, "asset_id")
        if contract_id:
            self._validate_uuid(contract_id, "contract_id")
        if status:
            self._validate_model_status(status)

        # Build request data
        data: Dict[str, Any] = {}
        if asset_id:
            data["asset_id"] = asset_id
        if contract_id:
            data["contract_id"] = contract_id
        if status:
            data["status"] = status.upper()

        if not data:
            raise ValidationError("At least one field (asset_id, contract_id, status) must be provided for update")

        try:
            response = await self.client.patch(f"/ml/models/{model_id}/", data=data)
            if isinstance(response, dict):
                return response
            else:
                raise ServerError("Invalid response format from API")
        except NotFoundError:
            raise NotFoundError(f"Model with id {model_id} not found")
        except Exception as e:
            if isinstance(e, (ValidationError, NotFoundError, ConflictError, ServerError)):
                raise
            raise ServerError(f"Failed to update model: {str(e)}")

    async def delete_model(self, model_id: str) -> None:
        """
        Delete ML model.

        Args:
            model_id: Model ID (UUID)

        Raises:
            ValidationError: If model_id is invalid
            NotFoundError: If model not found
            ServerError: If API request fails
        """
        self._validate_uuid(model_id, "model_id")

        try:
            await self.client.delete(f"/ml/models/{model_id}/")
        except NotFoundError:
            raise NotFoundError(f"Model with id {model_id} not found")
        except Exception as e:
            if isinstance(e, (ValidationError, NotFoundError, ConflictError, ServerError)):
                raise
            raise ServerError(f"Failed to delete model: {str(e)}")

    async def get_model_versions(self, model_id: str) -> List[Dict[str, Any]]:
        """
        Get model versions.

        Args:
            model_id: Model ID (UUID)

        Returns:
            List of model version dictionaries

        Raises:
            ValidationError: If model_id is invalid
            NotFoundError: If model not found
            ServerError: If API request fails
        """
        self._validate_uuid(model_id, "model_id")

        try:
            response = await self.client.get(f"/ml/models/{model_id}/versions/")
            if isinstance(response, dict):
                return response.get("versions", [])
            elif isinstance(response, list):
                return response
            else:
                return []
        except NotFoundError:
            raise NotFoundError(f"Model with id {model_id} not found")
        except Exception as e:
            if isinstance(e, (ValidationError, NotFoundError, ConflictError, ServerError)):
                raise
            raise ServerError(f"Failed to get model versions: {str(e)}")

    async def link_model_to_asset(self, model_id: str, asset_id: str) -> Dict[str, Any]:
        """
        Link model to asset.

        Args:
            model_id: Model ID (UUID)
            asset_id: Asset ID to link (UUID)

        Returns:
            Updated model dictionary

        Raises:
            ValidationError: If parameters are invalid
            NotFoundError: If model or asset not found
            ServerError: If API request fails
        """
        self._validate_uuid(model_id, "model_id")
        self._validate_uuid(asset_id, "asset_id")

        try:
            response = await self.client.post(f"/ml/models/{model_id}/link-asset/", data={"asset_id": asset_id})
            if isinstance(response, dict):
                return response
            else:
                raise ServerError("Invalid response format from API")
        except NotFoundError:
            raise NotFoundError(f"Model with id {model_id} or asset with id {asset_id} not found")
        except Exception as e:
            if isinstance(e, (ValidationError, NotFoundError, ConflictError, ServerError)):
                raise
            raise ServerError(f"Failed to link model to asset: {str(e)}")

    async def link_model_to_dataset(self, model_id: str, dataset_id: str, role: str) -> Dict[str, Any]:
        """
        Link model to dataset.

        Args:
            model_id: Model ID (UUID)
            dataset_id: Dataset ID to link (UUID)
            role: Dataset role (TRAINING, VALIDATION, TEST)

        Returns:
            Model dataset link dictionary

        Raises:
            ValidationError: If parameters are invalid
            NotFoundError: If model or dataset not found
            ServerError: If API request fails
        """
        self._validate_uuid(model_id, "model_id")
        self._validate_uuid(dataset_id, "dataset_id")

        valid_roles = ["TRAINING", "VALIDATION", "TEST"]
        if not isinstance(role, str) or role.upper() not in valid_roles:
            raise ValidationError(
                f"role must be one of: {', '.join(valid_roles)}",
                details={"field": "role", "expected": f"one of: {', '.join(valid_roles)}", "actual": role},
            )

        try:
            response = await self.client.post(
                f"/ml/models/{model_id}/link-dataset/", data={"dataset_id": dataset_id, "role": role.upper()}
            )
            if isinstance(response, dict):
                return response
            else:
                raise ServerError("Invalid response format from API")
        except NotFoundError:
            raise NotFoundError(f"Model with id {model_id} or dataset with id {dataset_id} not found")
        except Exception as e:
            if isinstance(e, (ValidationError, NotFoundError, ConflictError, ServerError)):
                raise
            raise ServerError(f"Failed to link model to dataset: {str(e)}")


class TrainingAPI:
    """
    Training API for ML model training job management.

    Provides methods for submitting, monitoring, and managing training jobs
    with ODH Training Operator integration.
    """

    def __init__(self, client: DataHubClient):
        """
        Initialize Training API.

        Args:
            client: DataHub client instance
        """
        self.client = client

    def _validate_uuid(self, value: str, param_name: str = "id") -> None:
        """Validate UUID format."""
        if not value:
            raise ValidationError(f"{param_name} is required")
        try:
            uuid.UUID(value)
        except (ValueError, TypeError):
            raise ValidationError(f"{param_name} must be a valid UUID")

    async def submit_training_job(
        self, model_id: str, dataset_id: str, config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Submit a training job.

        Args:
            model_id: Model ID (UUID)
            dataset_id: Training dataset ID (UUID)
            config: Training configuration dictionary

        Returns:
            Training job dictionary with job_id and status

        Raises:
            ValidationError: If parameters are invalid
            NotFoundError: If model or dataset not found
            ServerError: If API request fails
        """
        self._validate_uuid(model_id, "model_id")
        self._validate_uuid(dataset_id, "dataset_id")

        if not isinstance(config, dict):
            raise ValidationError("config must be a dictionary")

        data = {"model_id": model_id, "dataset_id": dataset_id, "config": config}

        try:
            response = await self.client.post("/ml/training/jobs/", data=data)
            if isinstance(response, dict):
                return response
            else:
                raise ServerError("Invalid response format from API")
        except NotFoundError:
            raise NotFoundError(f"Model with id {model_id} or dataset with id {dataset_id} not found")
        except Exception as e:
            if isinstance(e, (ValidationError, NotFoundError, ConflictError, ServerError)):
                raise
            raise ServerError(f"Failed to submit training job: {str(e)}")

    async def get_training_job(self, training_job_id: str) -> Dict[str, Any]:
        """
        Get training job details.

        Args:
            training_job_id: Training job ID

        Returns:
            Training job dictionary with status, progress, and metrics

        Raises:
            ValidationError: If training_job_id is invalid
            NotFoundError: If training job not found
            ServerError: If API request fails
        """
        if not training_job_id or not isinstance(training_job_id, str):
            raise ValidationError("training_job_id is required and must be a string")

        try:
            response = await self.client.get(f"/ml/training/jobs/{training_job_id}/")
            if isinstance(response, dict):
                return response
            else:
                raise ServerError("Invalid response format from API")
        except NotFoundError:
            raise NotFoundError(f"Training job with id {training_job_id} not found")
        except Exception as e:
            if isinstance(e, (ValidationError, NotFoundError, ConflictError, ServerError)):
                raise
            raise ServerError(f"Failed to get training job: {str(e)}")

    async def list_training_jobs(
        self,
        model_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        List training jobs with optional filters.

        Args:
            model_id: Filter by model ID (UUID)
            status: Filter by job status
            limit: Maximum number of results to return
            offset: Offset for pagination

        Returns:
            List of training job dictionaries

        Raises:
            ValidationError: If parameters are invalid
            ServerError: If API request fails
        """
        if model_id:
            self._validate_uuid(model_id, "model_id")
        if limit is not None and (not isinstance(limit, int) or limit < 0):
            raise ValidationError("limit must be a non-negative integer")
        if offset is not None and (not isinstance(offset, int) or offset < 0):
            raise ValidationError("offset must be a non-negative integer")

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
            response = await self.client.get("/ml/training/jobs/", params=params)
            if isinstance(response, dict):
                return response.get("results", [])
            elif isinstance(response, list):
                return response
            else:
                return []
        except Exception as e:
            if isinstance(e, (ValidationError, NotFoundError, ConflictError, ServerError)):
                raise
            raise ServerError(f"Failed to list training jobs: {str(e)}")

    async def cancel_training_job(self, training_job_id: str) -> None:
        """
        Cancel a training job.

        Args:
            training_job_id: Training job ID

        Raises:
            ValidationError: If training_job_id is invalid
            NotFoundError: If training job not found
            ServerError: If API request fails
        """
        if not training_job_id or not isinstance(training_job_id, str):
            raise ValidationError("training_job_id is required and must be a string")

        try:
            await self.client.post(f"/ml/training/jobs/{training_job_id}/cancel/")
        except NotFoundError:
            raise NotFoundError(f"Training job with id {training_job_id} not found")
        except Exception as e:
            if isinstance(e, (ValidationError, NotFoundError, ConflictError, ServerError)):
                raise
            raise ServerError(f"Failed to cancel training job: {str(e)}")

    async def get_training_logs(self, training_job_id: str) -> str:
        """
        Get training job logs.

        Args:
            training_job_id: Training job ID

        Returns:
            Training logs as string

        Raises:
            ValidationError: If training_job_id is invalid
            NotFoundError: If training job not found
            ServerError: If API request fails
        """
        if not training_job_id or not isinstance(training_job_id, str):
            raise ValidationError("training_job_id is required and must be a string")

        try:
            response = await self.client.get(f"/ml/training/jobs/{training_job_id}/logs/")
            # Logs might be returned as a string or in a dict with a 'logs' key
            if isinstance(response, str):
                return response
            elif isinstance(response, dict):
                return response.get("logs", "") or response.get("content", "") or str(response)
            else:
                return str(response)
        except NotFoundError:
            raise NotFoundError(f"Training job with id {training_job_id} not found")
        except Exception as e:
            if isinstance(e, (ValidationError, NotFoundError, ConflictError, ServerError)):
                raise
            raise ServerError(f"Failed to get training logs: {str(e)}")


class InferenceAPI:
    """
    Inference API for ML model inference deployment and prediction.

    Provides methods for deploying models, running predictions, and managing
    inference deployments with ODH Inference Scheduler integration.
    """

    def __init__(self, client: DataHubClient):
        """
        Initialize Inference API.

        Args:
            client: DataHub client instance
        """
        self.client = client

    def _validate_uuid(self, value: str, param_name: str = "id") -> None:
        """Validate UUID format."""
        if not value:
            raise ValidationError(f"{param_name} is required")
        try:
            uuid.UUID(value)
        except (ValueError, TypeError):
            raise ValidationError(f"{param_name} must be a valid UUID")

    async def deploy_model(self, model_id: str, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Deploy a model for inference.

        Args:
            model_id: Model ID (UUID)
            config: Optional deployment configuration dictionary

        Returns:
            Deployment dictionary with deployment_id and status

        Raises:
            ValidationError: If parameters are invalid
            NotFoundError: If model not found
            ServerError: If API request fails
        """
        self._validate_uuid(model_id, "model_id")

        if config is not None and not isinstance(config, dict):
            raise ValidationError("config must be a dictionary")

        data: Dict[str, Any] = {"model_id": model_id}
        if config:
            data["config"] = config

        try:
            response = await self.client.post("/ml/inference/deployments/", data=data)
            if isinstance(response, dict):
                return response
            else:
                raise ServerError("Invalid response format from API")
        except NotFoundError:
            raise NotFoundError(f"Model with id {model_id} not found")
        except Exception as e:
            if isinstance(e, (ValidationError, NotFoundError, ConflictError, ServerError)):
                raise
            raise ServerError(f"Failed to deploy model: {str(e)}")

    async def predict(self, deployment_id: str, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Run inference prediction on a deployed model.

        Args:
            deployment_id: Deployment ID
            input_data: Input data dictionary for prediction

        Returns:
            Prediction results dictionary

        Raises:
            ValidationError: If parameters are invalid
            NotFoundError: If deployment not found
            ServerError: If API request fails
        """
        if not deployment_id or not isinstance(deployment_id, str):
            raise ValidationError("deployment_id is required and must be a string")

        if not isinstance(input_data, dict):
            raise ValidationError("input_data must be a dictionary")

        data = {"deployment_id": deployment_id, "input": input_data}

        try:
            response = await self.client.post("/ml/inference/deployments/predict/", data=data)
            if isinstance(response, dict):
                return response
            else:
                raise ServerError("Invalid response format from API")
        except NotFoundError:
            raise NotFoundError(f"Deployment with id {deployment_id} not found")
        except Exception as e:
            if isinstance(e, (ValidationError, NotFoundError, ConflictError, ServerError)):
                raise
            raise ServerError(f"Failed to run prediction: {str(e)}")

    async def get_deployment(self, deployment_id: str) -> Dict[str, Any]:
        """
        Get deployment details.

        Args:
            deployment_id: Deployment ID

        Returns:
            Deployment dictionary with status and details

        Raises:
            ValidationError: If deployment_id is invalid
            NotFoundError: If deployment not found
            ServerError: If API request fails
        """
        if not deployment_id or not isinstance(deployment_id, str):
            raise ValidationError("deployment_id is required and must be a string")

        try:
            response = await self.client.get(f"/ml/inference/deployments/{deployment_id}/")
            if isinstance(response, dict):
                return response
            else:
                raise ServerError("Invalid response format from API")
        except NotFoundError:
            raise NotFoundError(f"Deployment with id {deployment_id} not found")
        except DataHubError as e:
            # Convert 404 errors to NotFoundError
            if e.http_status == 404:
                raise NotFoundError(f"Deployment with id {deployment_id} not found", e.request_id)
            raise
        except Exception as e:
            # Check if error message contains 404 (for ODH service errors)
            error_str = str(e).lower()
            if "404" in error_str or "not found" in error_str:
                # Check if it's a real 404 or a circuit breaker error
                if "circuit breaker" not in error_str:
                    raise NotFoundError(f"Deployment with id {deployment_id} not found")
            if isinstance(e, (ValidationError, NotFoundError, ConflictError, ServerError)):
                raise
            raise ServerError(f"Failed to get deployment: {str(e)}")

    async def list_deployments(
        self,
        model_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        List inference deployments with optional filters.

        Args:
            model_id: Filter by model ID (UUID)
            status: Filter by deployment status
            limit: Maximum number of results to return
            offset: Offset for pagination

        Returns:
            List of deployment dictionaries

        Raises:
            ValidationError: If parameters are invalid
            ServerError: If API request fails
        """
        if model_id:
            self._validate_uuid(model_id, "model_id")
        if limit is not None and (not isinstance(limit, int) or limit < 0):
            raise ValidationError("limit must be a non-negative integer")
        if offset is not None and (not isinstance(offset, int) or offset < 0):
            raise ValidationError("offset must be a non-negative integer")

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
            response = await self.client.get("/ml/inference/deployments/", params=params)
            if isinstance(response, dict):
                return response.get("results", [])
            elif isinstance(response, list):
                return response
            else:
                return []
        except Exception as e:
            if isinstance(e, (ValidationError, NotFoundError, ConflictError, ServerError)):
                raise
            raise ServerError(f"Failed to list deployments: {str(e)}")

    async def undeploy_model(self, deployment_id: str) -> None:
        """
        Undeploy a model.

        Args:
            deployment_id: Deployment ID

        Raises:
            ValidationError: If deployment_id is invalid
            NotFoundError: If deployment not found
            ServerError: If API request fails
        """
        if not deployment_id or not isinstance(deployment_id, str):
            raise ValidationError("deployment_id is required and must be a string")

        try:
            await self.client.delete(f"/ml/inference/deployments/{deployment_id}/")
        except NotFoundError:
            raise NotFoundError(f"Deployment with id {deployment_id} not found")
        except DataHubError as e:
            # Convert 404 errors to NotFoundError
            if e.http_status == 404:
                raise NotFoundError(f"Deployment with id {deployment_id} not found", e.request_id)
            raise
        except Exception as e:
            # Check if error message contains 404 (for ODH service errors)
            error_str = str(e).lower()
            if "404" in error_str or "not found" in error_str:
                # Check if it's a real 404 or a circuit breaker error
                if "circuit breaker" not in error_str:
                    raise NotFoundError(f"Deployment with id {deployment_id} not found")
            if isinstance(e, (ValidationError, NotFoundError, ConflictError, ServerError)):
                raise
            raise ServerError(f"Failed to undeploy deployment: {str(e)}")

    async def get_inference_metrics(self, deployment_id: str) -> Dict[str, Any]:
        """
        Get inference metrics for a deployment.

        Args:
            deployment_id: Deployment ID

        Returns:
            Inference metrics dictionary (latency, accuracy, error rate, etc.)

        Raises:
            ValidationError: If deployment_id is invalid
            NotFoundError: If deployment not found
            ServerError: If API request fails
        """
        if not deployment_id or not isinstance(deployment_id, str):
            raise ValidationError("deployment_id is required and must be a string")

        try:
            response = await self.client.get(f"/ml/inference/deployments/{deployment_id}/metrics/")
            if isinstance(response, dict):
                return response
            else:
                raise ServerError("Invalid response format from API")
        except NotFoundError:
            raise NotFoundError(f"Deployment with id {deployment_id} not found")
        except DataHubError as e:
            # Convert 404 errors to NotFoundError
            if e.http_status == 404:
                raise NotFoundError(f"Deployment with id {deployment_id} not found", e.request_id)
            raise
        except Exception as e:
            # Check if error message contains 404 (for ODH service errors)
            error_str = str(e).lower()
            if "404" in error_str or "not found" in error_str:
                # Check if it's a real 404 or a circuit breaker error
                if "circuit breaker" not in error_str:
                    raise NotFoundError(f"Deployment with id {deployment_id} not found")
            if isinstance(e, (ValidationError, NotFoundError, ConflictError, ServerError)):
                raise
            raise ServerError(f"Failed to get inference metrics: {str(e)}")
