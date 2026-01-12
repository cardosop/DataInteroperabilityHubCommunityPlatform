"""
Base Marketplace Connector Interface

Provides abstract base classes and data structures for implementing
data marketplace connectors that support bidirectional synchronization
between the Hub and external data marketplaces.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Any, List, Optional
from datetime import datetime

from hub.apps.assets.models import AssetSourceType


class MarketplaceType(str, Enum):
    """
    Enumeration of supported data marketplace types.

    Represents 15 major data marketplace platforms that can be integrated
    with the Hub for bidirectional asset synchronization.
    """
    SNOWFLAKE_DATA_MARKETPLACE = "SNOWFLAKE_DATA_MARKETPLACE"
    AWS_DATA_EXCHANGE = "AWS_DATA_EXCHANGE"
    DATABRICKS_MARKETPLACE = "DATABRICKS_MARKETPLACE"
    GOOGLE_CLOUD_MARKETPLACE = "GOOGLE_CLOUD_MARKETPLACE"
    AZURE_MARKETPLACE = "AZURE_MARKETPLACE"
    DATA_WORLD = "DATA_WORLD"
    KAGGLE = "KAGGLE"
    QUANDL = "QUANDL"
    APIS_GURU = "APIS_GURU"
    RAPIDAPI = "RAPIDAPI"
    PROGRAMMABLE_WEB = "PROGRAMMABLE_WEB"
    DATA_GOV = "DATA_GOV"
    EUROPEAN_DATA_PORTAL = "EUROPEAN_DATA_PORTAL"
    CKAN_INSTANCE = "CKAN_INSTANCE"
    CUSTOM = "CUSTOM"


class SyncDirection(str, Enum):
    """
    Enumeration of synchronization directions.

    Defines the direction of data flow between the Hub and external marketplaces.
    """
    PUSH = "PUSH"
    PULL = "PULL"
    BIDIRECTIONAL = "BIDIRECTIONAL"


class SyncStatus(str, Enum):
    """
    Enumeration of synchronization operation statuses.

    Represents the current state of a synchronization operation.
    """
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    PARTIAL = "PARTIAL"


@dataclass
class MarketplaceListing:
    """
    Unified representation of a marketplace listing.

    Provides a standardized structure for representing listings across
    different marketplace platforms, abstracting platform-specific details.

    Attributes:
        marketplace_id: Unique identifier for the listing in the marketplace
        marketplace_type: Type of marketplace (from MarketplaceType enum)
        title: Listing title
        description: Listing description
        product_id: Product identifier (e.g., ODPS productID)
        category: Product category
        tags: List of tags associated with the listing
        pricing_plans: List of pricing plans (ODPS format)
        access_methods: Dictionary of access methods (ODPS format)
        payment_gateways: Dictionary of payment gateways (ODPS format)
        metadata: Additional platform-specific metadata
        resources: List of MarketplaceResource objects associated with this listing
        created_at: Listing creation timestamp
        updated_at: Listing last update timestamp
        url: URL to the listing in the marketplace
    """
    marketplace_id: str
    marketplace_type: MarketplaceType
    title: str
    description: Optional[str] = None
    product_id: Optional[str] = None
    category: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    pricing_plans: List[Dict[str, Any]] = field(default_factory=list)
    access_methods: Dict[str, Any] = field(default_factory=dict)
    payment_gateways: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    resources: List['MarketplaceResource'] = field(default_factory=list)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    url: Optional[str] = None


@dataclass
class MarketplaceResource:
    """
    Unified representation of a marketplace resource.

    Represents a downloadable resource associated with a marketplace listing,
    such as data files, API endpoints, or database connections.

    Attributes:
        resource_id: Unique identifier for the resource
        resource_type: Type of resource (e.g., "FILE", "API", "DATABASE")
        name: Resource name
        description: Resource description
        url: URL to access/download the resource
        format: Resource format (e.g., "CSV", "JSON", "PARQUET")
        size_bytes: Resource size in bytes (if applicable)
        metadata: Additional resource-specific metadata
    """
    resource_id: str
    resource_type: str
    name: str
    description: Optional[str] = None
    url: Optional[str] = None
    format: Optional[str] = None
    size_bytes: Optional[int] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SyncResult:
    """
    Result of a synchronization operation.

    Provides detailed information about the outcome of a sync operation,
    including success status, counts, and any errors encountered.

    Attributes:
        status: Sync operation status (from SyncStatus enum)
        total_items: Total number of items processed
        successful_items: Number of successfully processed items
        failed_items: Number of failed items
        skipped_items: Number of skipped items
        errors: List of error messages encountered
        metadata: Additional operation metadata
        started_at: Operation start timestamp
        completed_at: Operation completion timestamp
    """
    status: SyncStatus
    total_items: int = 0
    successful_items: int = 0
    failed_items: int = 0
    skipped_items: int = 0
    errors: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


@dataclass
class MarketplaceAssetMapping:
    """
    Federated asset mapping result.

    Represents the mapping between a Hub asset and a marketplace listing,
    including all metadata required for federated asset creation and
    synchronization.

    Attributes:
        asset_data: Dictionary containing Hub asset fields (name, description,
            domain, status, visibility, etc.)
        source_type: Asset source type (from AssetSourceType enum).
            Should be FEDERATED for imported assets.
        source_metadata: Dictionary containing marketplace source metadata:
            - marketplace_type: Type of marketplace
            - marketplace_id: Marketplace-specific identifier
            - listing_id: Listing identifier in the marketplace
            - listing_url: URL to the listing
            - synced_at: Timestamp when sync occurred
            - sync_job_id: ID of the sync job that created this mapping
        odps_metadata: Optional dictionary containing ODPS contract data extracted
            from marketplace listing (product details, pricing, access, payment).
            None if ODPS metadata is not available.
        odcs_metadata: Optional dictionary containing ODCS contract data
            (schema, quality, SLA) if available from marketplace, None otherwise
        resources: List of MarketplaceResource objects representing resources
            to download from the marketplace
    """
    asset_data: Dict[str, Any]
    source_type: AssetSourceType
    source_metadata: Dict[str, Any]
    odps_metadata: Optional[Dict[str, Any]] = None
    odcs_metadata: Optional[Dict[str, Any]] = None
    resources: List[MarketplaceResource] = field(default_factory=list)


class DataMarketplaceConnector(ABC):
    """
    Abstract base class for data marketplace connectors implementing metadata-first architecture.

    Defines the interface that all marketplace connector implementations must follow to enable
    bidirectional synchronization between the Hub and external data marketplaces. All connectors
    follow a consistent metadata-first architecture pattern that enables fast harvesting, clear
    separation of concerns, and scalable marketplace integration.

    **Metadata-First Architecture Pattern**:
    Connectors follow a metadata-first approach where:
    1. `sync_pull()` discovers listings and maps them to MarketplaceAssetMapping objects
       - Does NOT create assets (workflow handles this)
       - Does NOT download data (only maps resources with external references)
       - Only maps listings with external resource references
    2. Asset creation happens in workflow via `create_federated_asset_with_contracts()`
       - Workflow orchestrates asset creation based on `data_strategy` parameter
       - Workflow handles validation, checks, indexing, and notifications
    3. Data downloads happen on-demand via `download_resource()` when `data_strategy != "METADATA_ONLY"`
       - Marketplace-specific operations (database creation, subscriptions, etc.) happen here
       - Resources downloaded only when explicitly requested

    **Connector Responsibilities**:
    - **Discovery**: `list_listings()`, `get_listing()`, `list_resources()` - Discover marketplace listings
    - **Mapping**: `map_to_hub_asset()` → MarketplaceAssetMapping - Convert marketplace listing to Hub asset format
    - **Harvest**: `sync_pull()` → SyncResult with mappings - Discover listings and map to MarketplaceAssetMapping
    - **Download**: `download_resource()` → On-demand resource download - Handle marketplace-specific operations

    **Connector Must NOT**:
    - Create assets directly (workflow handles this via `create_federated_asset_with_contracts()`)
    - Download data in `sync_pull()` (only map resources with external references)
    - Access external data sources in `sync_pull()` (only store references)

    **Workflow Integration**:
    Connectors are integrated into the workflow system:
    ```
    sync_from_marketplace() → Creates sync job → Triggers workflow
    Workflow: marketplace_sync_pull
      ├─ discover_listings_task → Calls connector.list_listings()
      ├─ map_listings_to_assets_task → Calls connector.map_to_hub_asset()
      └─ create_federated_assets_task → Calls create_federated_asset_with_contracts()
          └─ Based on data_strategy:
              - METADATA_ONLY: Store external references only
              - DOWNLOAD_SELECTIVE: Download specific resources via connector.download_resource()
              - DOWNLOAD_ALL: Download all resources via connector.download_resource()
    ```

    **Metadata-First Benefits**:
    - **Fast Harvesting**: Create thousands of federated assets quickly without downloading data (seconds vs hours)
    - **Scalability**: Harvest large marketplaces without storage overhead (metadata-only assets are lightweight)
    - **Clear Separation**: Federated assets (external metadata) vs Virtualized assets (virtual queries)
    - **Lazy Data Access**: Download data only when explicitly requested (reduces storage costs, improves performance)
    - **Governance/Compliance/Semantic Layers**: All layers work with metadata-first federated assets

    **Reference Implementations**:
    - CKAN Connector (`hub/apps/integrations/connectors/ckan_connector.py`) - Reference implementation
    - DadosGovBr Connector (`hub/apps/integrations/connectors/dados_gov_br_connector.py`) - Reference implementation

    All methods are abstract and must be implemented by concrete connector classes for specific
    marketplace platforms. See `docs/connectors/DEVELOPMENT.md` for detailed implementation guide.
    """

    @property
    @abstractmethod
    def marketplace_type(self) -> MarketplaceType:
        """
        Get the marketplace type this connector supports.

        Returns:
            MarketplaceType enum value representing the marketplace platform
        """
        pass

    @property
    @abstractmethod
    def supported_sync_directions(self) -> List[SyncDirection]:
        """
        Get the list of sync directions supported by this connector.

        Returns:
            List of SyncDirection enum values that this connector supports.
            Must contain at least one direction.
        """
        pass

    @abstractmethod
    def authenticate(self, credentials: Dict[str, Any]) -> bool:
        """
        Authenticate with the marketplace using provided credentials.

        Args:
            credentials: Dictionary containing authentication credentials
                (e.g., API keys, OAuth tokens, username/password)

        Returns:
            True if authentication successful, False otherwise

        Raises:
            ValueError: If credentials are invalid or missing required fields
            ConnectionError: If unable to connect to marketplace
        """
        pass

    @abstractmethod
    def test_connection(self) -> bool:
        """
        Test the connection to the marketplace.

        Performs a lightweight operation to verify that the connector
        can successfully communicate with the marketplace API.

        Returns:
            True if connection test successful, False otherwise

        Raises:
            ConnectionError: If unable to connect to marketplace
        """
        pass

    @abstractmethod
    def list_listings(
        self,
        filters: Optional[Dict[str, Any]] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None
    ) -> List[MarketplaceListing]:
        """
        List available listings from the marketplace.

        Args:
            filters: Optional dictionary of filters to apply (e.g., category, tags)
            limit: Optional maximum number of listings to return
            offset: Optional offset for pagination

        Returns:
            List of MarketplaceListing objects

        Raises:
            ConnectionError: If unable to connect to marketplace
            ValueError: If filters or pagination parameters are invalid
        """
        pass

    @abstractmethod
    def get_listing(self, listing_id: str) -> MarketplaceListing:
        """
        Get a specific listing by its marketplace ID.

        Args:
            listing_id: Unique identifier for the listing in the marketplace

        Returns:
            MarketplaceListing object

        Raises:
            NotFoundError: If listing not found
            ConnectionError: If unable to connect to marketplace
        """
        pass

    @abstractmethod
    def list_resources(self, listing_id: str) -> List[MarketplaceResource]:
        """
        List resources associated with a marketplace listing.

        Args:
            listing_id: Unique identifier for the listing

        Returns:
            List of MarketplaceResource objects

        Raises:
            NotFoundError: If listing not found
            ConnectionError: If unable to connect to marketplace
        """
        pass

    @abstractmethod
    def create_listing(
        self,
        listing: MarketplaceListing
    ) -> MarketplaceListing:
        """
        Create a new listing in the marketplace (PUSH operation).

        Args:
            listing: MarketplaceListing object with listing details

        Returns:
            Created MarketplaceListing object with marketplace-assigned ID

        Raises:
            ValueError: If listing data is invalid
            ConnectionError: If unable to connect to marketplace
            PermissionError: If user lacks permission to create listings
        """
        pass

    @abstractmethod
    def update_listing(
        self,
        listing_id: str,
        listing: MarketplaceListing
    ) -> MarketplaceListing:
        """
        Update an existing listing in the marketplace (PUSH operation).

        Args:
            listing_id: Unique identifier for the listing to update
            listing: MarketplaceListing object with updated details

        Returns:
            Updated MarketplaceListing object

        Raises:
            NotFoundError: If listing not found
            ValueError: If listing data is invalid
            ConnectionError: If unable to connect to marketplace
            PermissionError: If user lacks permission to update listing
        """
        pass

    @abstractmethod
    def publish_resource(
        self,
        listing_id: str,
        resource: MarketplaceResource
    ) -> MarketplaceResource:
        """
        Publish a resource to a marketplace listing (PUSH operation).

        Args:
            listing_id: Unique identifier for the listing
            resource: MarketplaceResource object with resource details

        Returns:
            Published MarketplaceResource object with marketplace-assigned ID

        Raises:
            NotFoundError: If listing not found
            ValueError: If resource data is invalid
            ConnectionError: If unable to connect to marketplace
            PermissionError: If user lacks permission to publish resources
        """
        pass

    @abstractmethod
    def download_resource(
        self,
        resource_id: str,
        destination_path: str
    ) -> str:
        """
        Download a resource from the marketplace on-demand (PULL operation).

        **On-Demand Download Behavior**:
        This method handles on-demand resource downloads when `data_strategy != "METADATA_ONLY"`.
        It is called by the workflow system (`create_federated_asset_with_contracts()`) when
        resources need to be downloaded. Marketplace-specific operations (database creation,
        subscriptions, snapshot triggering, etc.) happen here, not in `sync_pull()`.

        **What This Method Does**:
        1. Handles marketplace-specific operations required to access the resource:
           - Snowflake: Request listing, accept legal terms, create database from listing, extract schema
           - AWS Data Exchange: Subscribe to dataset, create export job, wait for completion, download from S3
           - Azure Data Share: Accept invitation, trigger snapshot, wait for completion, access shared data
           - GCP Marketplace: Subscribe to listing, create linked dataset, extract schema from BigQuery
           - Databricks: Consume share, create catalog from share, extract schema
        2. Downloads resource data to `destination_path`
        3. Returns path to downloaded file

        **When This Method Is Called**:
        - Called by workflow when `data_strategy == "DOWNLOAD_SELECTIVE"` (specific resources)
        - Called by workflow when `data_strategy == "DOWNLOAD_ALL"` (all resources)
        - NOT called when `data_strategy == "METADATA_ONLY"` (default, metadata-only harvesting)

        Args:
            resource_id: Unique identifier for the resource. For some marketplaces, this may be:
                - A listing ID (Snowflake: database creation happens here)
                - A dataset/revision ID (AWS Data Exchange: export job creation happens here)
                - A share/dataset ID (Azure Data Share: snapshot triggering happens here)
                - A table identifier (GCP Marketplace: schema extraction happens here)
            destination_path: Local filesystem path where resource should be saved.
                The directory will be created if it doesn't exist.

        Returns:
            Path to the downloaded file (may be same as destination_path or a modified path)

        Raises:
            NotFoundError: If resource not found in marketplace
            ConnectionError: If unable to connect to marketplace
            IOError: If unable to write to destination path
            PermissionError: If user lacks permission to download resource or perform marketplace-specific operations
            ValueError: If resource_id is invalid or marketplace-specific operation fails

        **Example**:
        ```python
        # Snowflake: Create database and export table data
        def download_resource(self, resource_id, destination_path):
            # Request listing and accept legal terms
            self._request_listing(resource_id)
            self._accept_legal_terms(resource_id)
            # Create database from listing
            db_name = self._create_database_from_listing(resource_id)
            # Extract schema metadata
            schema = self._extract_schema_metadata(db_name)
            # Export table data to file
            self._export_table_to_file(db_name, destination_path)
            return destination_path

        # AWS Data Exchange: Subscribe, export, download
        def download_resource(self, resource_id, destination_path):
            # Subscribe to dataset if not subscribed
            self._subscribe_to_dataset(resource_id)
            # Create export job
            job_id = self._create_export_job(resource_id)
            # Wait for job completion
            self._wait_for_job_completion(job_id)
            # Download from S3
            self._download_from_s3(job_id, destination_path)
            return destination_path
        ```

        **Note**: This method should handle marketplace-specific operations that were deferred from
        `sync_pull()`. The metadata-first pattern ensures these operations happen only when data
        is explicitly requested, not during initial harvesting.
        """
        pass

    @abstractmethod
    def map_to_hub_asset(
        self,
        listing: MarketplaceListing,
        sync_job_id: Optional[str] = None
    ) -> MarketplaceAssetMapping:
        """
        Map a marketplace listing to a Hub asset representation following metadata-first pattern.

        Converts a MarketplaceListing object to MarketplaceAssetMapping, extracting all metadata
        required for federated asset creation. This method does NOT access external data sources
        or download data - it only extracts metadata and stores external resource references.

        **What This Method Does**:
        1. Extracts asset metadata (name, description, domain, tags, status, visibility)
        2. Extracts ODPS contract metadata (product details, pricing plans, access methods, payment gateways)
        3. Extracts ODCS contract metadata (schema hints, quality hints, SLA hints) if available
        4. Builds source_metadata with marketplace connection and listing information
        5. Includes external resource references in `resources` list (does NOT download resources)

        **What This Method Does NOT Do**:
        - Access external data sources (only stores references)
        - Download data (only maps resources with external URLs/identifiers)
        - Create assets (workflow handles this via `create_federated_asset_with_contracts()`)
        - Create databases, subscribe to datasets, trigger snapshots, etc. (these happen in `download_resource()`)

        Args:
            listing: MarketplaceListing object to map
            sync_job_id: Optional sync job ID for tracking synchronization operations.
                If provided, will be included in source_metadata for audit and tracking purposes.

        Returns:
            MarketplaceAssetMapping object containing:
            - asset_data: Dictionary with Hub asset fields (name, description, domain, tags, status, visibility)
            - source_type: AssetSourceType.FEDERATED (always FEDERATED for marketplace assets)
            - source_metadata: Dictionary with marketplace connection and listing information:
                - marketplace_type: Type of marketplace (from MarketplaceType enum)
                - marketplace_id: Marketplace-specific identifier (connection ID)
                - listing_id: Listing identifier in the marketplace
                - listing_url: URL to the listing in the marketplace
                - synced_at: Timestamp when sync occurred (ISO format)
                - sync_job_id: ID of the sync job (if provided)
            - odps_metadata: Optional dictionary with ODPS contract data (product details, pricing, access, payment)
                - Can be None if ODPS metadata is not available (minimal ODPS contract will be created)
            - odcs_metadata: Optional dictionary with ODCS contract data (schema hints, quality hints, SLA hints)
                - Can be None if ODCS metadata is not available (minimal ODCS contract will be created)
            - resources: List of MarketplaceResource objects with external references:
                - resource_id: External resource identifier
                - name: Resource name
                - url: External resource URL or identifier (for on-demand download)
                - format: Resource format (CSV, JSON, PARQUET, SNOWFLAKE_DATABASE, etc.)
                - size_bytes: Resource size if known, None otherwise
                - metadata.external: True flag indicating external resource
                - metadata.download_url: URL for on-demand download

        Raises:
            ValueError: If listing data cannot be mapped or is invalid

        **Example**:
        ```python
        # Correct: Extract metadata and store external references
        def map_to_hub_asset(self, listing, sync_job_id=None):
            resources = [
                MarketplaceResource(
                    resource_id=resource.id,
                    name=resource.name,
                    url=resource.external_url,  # Store reference
                    format=resource.format,
                    metadata={"external": True, "download_url": resource.external_url}
                )
                for resource in listing.resources
            ]
            return MarketplaceAssetMapping(
                asset_data={"name": listing.title, ...},
                source_type=AssetSourceType.FEDERATED,
                source_metadata={"marketplace_type": ..., "listing_id": ...},
                odps_metadata={...},
                odcs_metadata={...},
                resources=resources  # External references only
            )

        # Wrong: Accessing external data sources or downloading data
        def map_to_hub_asset(self, listing, sync_job_id=None):
            # ❌ Don't do this:
            data = download_from_marketplace(listing)  # download_resource() handles this
            schema = extract_schema_from_database(listing)  # download_resource() handles this
        ```
        """
        pass

    @abstractmethod
    def map_from_hub_asset(
        self,
        asset_data: Dict[str, Any],
        odps_metadata: Optional[Dict[str, Any]] = None,
        odcs_metadata: Optional[Dict[str, Any]] = None
    ) -> MarketplaceListing:
        """
        Map a Hub asset to a marketplace listing representation.

        Converts Hub asset data and contract metadata into a format suitable
        for creating or updating a marketplace listing.

        Args:
            asset_data: Dictionary containing Hub asset fields
            odps_metadata: Optional ODPS contract data
            odcs_metadata: Optional ODCS contract data

        Returns:
            MarketplaceListing object ready for marketplace operations

        Raises:
            ValueError: If asset data cannot be mapped
        """
        pass

    @abstractmethod
    def sync_push(
        self,
        asset_ids: List[str],
        options: Optional[Dict[str, Any]] = None
    ) -> SyncResult:
        """
        Perform bulk push synchronization (Hub → Marketplace).

        Synchronizes multiple Hub assets to the marketplace, creating or
        updating listings as needed.

        Args:
            asset_ids: List of Hub asset IDs to synchronize
            options: Optional dictionary of sync options (e.g., dry_run, force_update)

        Returns:
            SyncResult object with operation details

        Raises:
            ValueError: If asset IDs are invalid
            ConnectionError: If unable to connect to marketplace
        """
        pass

    @abstractmethod
    def sync_pull(
        self,
        listing_ids: Optional[List[str]] = None,
        filters: Optional[Dict[str, Any]] = None,
        options: Optional[Dict[str, Any]] = None
    ) -> SyncResult:
        """
        Perform bulk pull synchronization (Marketplace → Hub) following metadata-first pattern.

        **Metadata-First Behavior**:
        This method discovers listings and maps them to MarketplaceAssetMapping objects. It does
        NOT create assets or download data. Asset creation happens in the workflow via
        `create_federated_asset_with_contracts()`. Data downloads happen on-demand via
        `download_resource()` when `data_strategy != "METADATA_ONLY"`.

        **What This Method Does**:
        1. Discovers listings from marketplace (by IDs or via filters)
        2. Maps each listing to MarketplaceAssetMapping using `map_to_hub_asset()`
        3. Returns mappings in SyncResult.metadata["mappings"] for workflow processing

        **What This Method Does NOT Do**:
        - Create assets (workflow handles this)
        - Download data (only maps resources with external references)
        - Access external data sources (only stores references)
        - Create databases, subscribe to datasets, trigger snapshots, etc. (these happen in `download_resource()`)

        Args:
            listing_ids: Optional list of specific listing IDs to sync.
                If None, syncs all listings matching filters.
            filters: Optional dictionary of filters to apply (e.g., category, tags, provider)
            options: Optional dictionary of sync options:
                - dry_run: If True, simulate sync without creating assets
                - limit: Maximum number of listings to sync (default: None, sync all)
                - include_resources: If True, fetch resources for each listing (default: True)

        Returns:
            SyncResult object with:
            - status: SyncStatus (COMPLETED, PARTIAL, FAILED)
            - successful_count: Number of successfully mapped listings
            - failed_count: Number of failed mappings
            - metadata: Dictionary containing:
                - "mappings": List of MarketplaceAssetMapping objects (serialized as dicts)
                - "errors": List of error messages for failed mappings
            - started_at: Operation start timestamp
            - completed_at: Operation completion timestamp

        Raises:
            ValueError: If filters or options are invalid
            ConnectionError: If unable to connect to marketplace

        **Workflow Integration**:
        This method is called by the `marketplace_sync_pull` workflow:
        1. `discover_listings_task` calls `connector.list_listings()` or `connector.get_listing()`
        2. `map_listings_to_assets_task` calls `connector.map_to_hub_asset()` for each listing
        3. `create_federated_assets_task` calls `create_federated_asset_with_contracts()` for each mapping

        **Example**:
        ```python
        # Correct: Map listings only, return mappings
        def sync_pull(self, listing_ids=None, filters=None, options=None):
            listings = self.list_listings(filters=filters) if not listing_ids else \
                      [self.get_listing(id) for id in listing_ids]
            mappings = []
            for listing in listings:
                mapping = self.map_to_hub_asset(listing)
                mappings.append(mapping)
            return SyncResult(
                status=SyncStatus.COMPLETED,
                successful_count=len(mappings),
                metadata={"mappings": [mapping.__dict__ for mapping in mappings]}
            )

        # Wrong: Creating assets or downloading data
        def sync_pull(self, ...):
            # ❌ Don't do this:
            asset = create_asset(listing)  # Workflow handles this
            download_data(listing)  # download_resource() handles this
        ```
        """
        pass

    def _track_connector_operation(
        self,
        operation_type: str,
        func,
        *args,
        tenant_id: Optional[str] = None,
        **kwargs
    ):
        """
        Helper method to track connector operations with metrics.

        This method wraps connector operations to automatically track:
        - Operation count
        - Operation duration
        - Operation errors

        Args:
            operation_type: Type of operation (e.g., 'list_listings', 'get_listing', 'sync_pull', 'sync_push', 'download_resource')
            func: The function to execute
            *args: Positional arguments for the function
            tenant_id: Optional tenant ID for metrics
            **kwargs: Keyword arguments for the function

        Returns:
            Result from the function execution

        Raises:
            Any exception raised by the function
        """
        import time
        import structlog

        logger = structlog.get_logger(__name__)
        start_time = time.time()
        status = "success"
        error_type = None
        error_message = None

        # Get correlation context
        try:
            from hub.apps.integrations.logging_utils import get_correlation_context
            correlation_context = get_correlation_context()
        except Exception:
            correlation_context = {}

        # Log operation start
        marketplace_type_str = self.marketplace_type.value if hasattr(self.marketplace_type, 'value') else str(self.marketplace_type)
        logger.info(
            "connector_operation_started",
            operation_type=operation_type,
            marketplace_type=marketplace_type_str,
            tenant_id=tenant_id,
            **correlation_context,
        )

        try:
            result = func(*args, **kwargs)
            return result
        except Exception as e:
            status = "error"
            error_type = type(e).__name__
            error_message = str(e)
            raise
        finally:
            duration = time.time() - start_time

            try:
                from hub.apps.observability.otel_metrics import (
                    marketplace_connector_operations_total,
                    marketplace_connector_operation_duration_seconds,
                    marketplace_connector_operation_errors_total,
                )

                # Record operation count
                marketplace_connector_operations_total.labels(
                    marketplace_type=marketplace_type_str,
                    operation_type=operation_type,
                    status=status,
                    tenant_id=tenant_id or "unknown",
                ).inc()

                # Record duration
                marketplace_connector_operation_duration_seconds.labels(
                    marketplace_type=marketplace_type_str,
                    operation_type=operation_type,
                    status=status,
                ).observe(duration)

                # Record errors if any
                if status == "error" and error_type:
                    marketplace_connector_operation_errors_total.labels(
                        marketplace_type=marketplace_type_str,
                        operation_type=operation_type,
                        error_type=error_type,
                        tenant_id=tenant_id or "unknown",
                    ).inc()
            except Exception as e:
                # Log but don't fail operation if metrics fail
                logger.warning(
                    "metrics_recording_failed",
                    operation_type=operation_type,
                    marketplace_type=marketplace_type_str,
                    error=str(e),
                    error_type=type(e).__name__,
                    **correlation_context,
                    exc_info=True,
                )

            # Log operation completion with structured fields
            log_level = "error" if status == "error" else "info"
            logger.log(
                log_level,
                "connector_operation_completed",
                operation_type=operation_type,
                marketplace_type=marketplace_type_str,
                tenant_id=tenant_id,
                status=status,
                duration_seconds=duration,
                error_type=error_type,
                error_message=error_message,
                **correlation_context,
            )

