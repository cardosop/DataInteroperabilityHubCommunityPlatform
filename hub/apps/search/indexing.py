"""
Search Indexing

Indexing logic for contracts, assets, datasets, schemas, descriptions, and lineage metadata.
"""
from typing import Dict, List, Any, Optional
from django.db import transaction
from django.contrib.postgres.search import SearchVector
from django.utils import timezone
import structlog

from .models import SearchIndex
from hub.apps.contracts.models import Contract
from hub.apps.assets.models import Asset
from hub.apps.datasets.models import Dataset
from hub.apps.governance.models import DataClassification, ClassificationCategory

logger = structlog.get_logger(__name__)


class SearchIndexer:
    """
    Indexes resources for full-text search.
    """

    @staticmethod
    def _flatten_schema(schema_json: Optional[Dict[str, Any]]) -> str:
        """Flatten schema JSON to searchable text"""
        if not schema_json:
            return ""

        text_parts = []

        # Extract field names and types
        if isinstance(schema_json, dict):
            if "fields" in schema_json:
                for field in schema_json["fields"]:
                    if isinstance(field, dict):
                        field_name = field.get("name", "")
                        field_type = field.get("type") or field.get("data_type", "")
                        if field_name:
                            text_parts.append(field_name)
                        if field_type:
                            text_parts.append(field_type)

            # Extract other schema properties
            for key, value in schema_json.items():
                if key != "fields" and isinstance(value, (str, int, float)):
                    text_parts.append(str(value))

        return " ".join(text_parts)

    @staticmethod
    def _flatten_lineage(lineage_json: Optional[Dict[str, Any]]) -> str:
        """Flatten lineage JSON to searchable text"""
        if not lineage_json:
            return ""

        text_parts = []

        # Extract contract references
        if isinstance(lineage_json, dict):
            if "contracts" in lineage_json:
                for contract in lineage_json.get("contracts", []):
                    if isinstance(contract, dict):
                        name = contract.get("name", "")
                        namespace = contract.get("namespace", "")
                        if name:
                            text_parts.append(name)
                        if namespace:
                            text_parts.append(namespace)

            # Extract model references
            if "models" in lineage_json:
                for model in lineage_json.get("models", []):
                    if isinstance(model, dict):
                        name = model.get("name", "")
                        if name:
                            text_parts.append(name)

            # Extract field references
            if "fields" in lineage_json:
                for field in lineage_json.get("fields", []):
                    if isinstance(field, dict):
                        name = field.get("name", "")
                        if name:
                            text_parts.append(name)

        return " ".join(text_parts)

    @staticmethod
    def _flatten_tags(tags: Optional[List[str]]) -> str:
        """Flatten tags list to searchable text"""
        if not tags:
            return ""
        return " ".join(str(tag) for tag in tags if tag)

    @staticmethod
    def _get_classification(tenant_id: str, resource_type: str, resource_id: str) -> Optional[str]:
        """Get highest classification for a resource"""
        try:
            classifications = None
            if resource_type == "DATASET":
                classifications = DataClassification.objects.filter(
                    tenant_id=tenant_id,
                    dataset_id=resource_id
                ).exclude(status="REJECTED")  # Include APPROVED and PENDING, exclude REJECTED
            elif resource_type == "ASSET":
                classifications = DataClassification.objects.filter(
                    tenant_id=tenant_id,
                    asset_id=resource_id
                ).exclude(status="REJECTED")  # Include APPROVED and PENDING, exclude REJECTED
            elif resource_type == "CONTRACT":
                # Contracts might have classifications via related assets/datasets
                # For now, return None (can be enhanced later)
                return None
            else:
                return None

            if classifications and classifications.exists():
                # Get highest classification
                # Convert to list to avoid queryset evaluation issues
                classification_list = list(classifications)
                if classification_list:
                    highest = max(
                        classification_list,
                        key=lambda c: SearchIndexer._get_classification_priority(c.category)
                    )
                    return highest.category

        except Exception as e:
            logger.warning(
                "Failed to get classification",
                tenant_id=tenant_id,
                resource_type=resource_type,
                resource_id=resource_id,
                error=str(e)
            )

        return None

    @staticmethod
    def _get_classification_priority(category: str) -> int:
        """Get classification priority (higher = more sensitive)"""
        priorities = {
            ClassificationCategory.PUBLIC.value: 1,
            ClassificationCategory.INTERNAL.value: 2,
            ClassificationCategory.CONFIDENTIAL.value: 3,
            ClassificationCategory.RESTRICTED.value: 4,
            ClassificationCategory.PII.value: 5,
            ClassificationCategory.PHI.value: 6,
            ClassificationCategory.PCI.value: 6,
            ClassificationCategory.FINANCIAL.value: 4,
            ClassificationCategory.LEGAL.value: 4,
        }
        return priorities.get(category, 2)

    @classmethod
    @transaction.atomic
    def index_contract(cls, contract: Contract) -> SearchIndex:
        """Index a contract"""
        # Extract contract data
        hub_contract = contract.hub_contract_json or {}
        info = hub_contract.get("info", {})

        # Get title from hub_contract_json or use contract ID as fallback
        title = None
        if contract.hub_contract_json and isinstance(contract.hub_contract_json, dict):
            info = contract.hub_contract_json.get("info", {})
            if isinstance(info, dict):
                title = info.get("title") or info.get("name")
        if not title:
            title = f"Contract {contract.id}"
        description = info.get("description", "")

        # Extract schema from models
        models_data = hub_contract.get("models", [])
        schema_fields = []
        schema_text_parts = []

        for model in models_data:
            if isinstance(model, dict):
                model_name = model.get("name", "")
                if model_name:
                    schema_text_parts.append(model_name)

                fields = model.get("fields", [])
                for field in fields:
                    if isinstance(field, dict):
                        field_name = field.get("name", "")
                        field_type = field.get("type", "")
                        if field_name:
                            schema_fields.append({"name": field_name, "type": field_type})
                            schema_text_parts.append(field_name)
                        if field_type:
                            schema_text_parts.append(field_type)

        schema_text = " ".join(schema_text_parts)

        # Extract lineage
        lineage = hub_contract.get("lineage", {})
        lineage_text = cls._flatten_lineage(lineage)

        # Extract tags
        tags = info.get("tags", [])
        tags_text = cls._flatten_tags(tags)

        # Get classification
        classification = cls._get_classification(
            str(contract.tenant_id),
            "CONTRACT",
            str(contract.id)
        )

        # Get owner
        owner_id = contract.created_by_id
        owner_email = contract.created_by.email if contract.created_by else None

        # Create or update search index
        search_index, created = SearchIndex.objects.update_or_create(
            tenant=contract.tenant,
            resource_type="CONTRACT",
            resource_id=contract.id,
            defaults={
                "title": title,
                "description": description,
                "schema_fields": schema_fields,
                "schema_text": schema_text,
                "lineage_metadata": lineage,
                "lineage_text": lineage_text,
                "tags": tags,
                "tags_text": tags_text,
                "owner_id": owner_id,
                "owner_email": owner_email,
                "classification": classification,
            }
        )

        # Update search vector
        search_index.search_vector = (
            SearchVector("title", weight="A", config="english") +
            SearchVector("description", weight="B", config="english") +
            SearchVector("schema_text", weight="C", config="english") +
            SearchVector("lineage_text", weight="C", config="english") +
            SearchVector("tags_text", weight="C", config="english")
        )
        search_index.save()

        logger.info(
            "Indexed contract",
            contract_id=str(contract.id),
            tenant_id=str(contract.tenant_id),
            created=created
        )

        return search_index

    @classmethod
    @transaction.atomic
    def index_asset(cls, asset: Asset) -> SearchIndex:
        """Index an asset"""
        title = asset.name
        description = asset.description or ""

        # Extract tags (Asset model doesn't have tags field, use empty list)
        tags = getattr(asset, 'tags', []) or []
        tags_text = cls._flatten_tags(tags)

        # Get classification
        classification = cls._get_classification(
            str(asset.tenant_id),
            "ASSET",
            str(asset.id)
        )

        # Get owner
        owner_id = asset.created_by_id
        owner_email = asset.created_by.email if asset.created_by else None

        # Create or update search index
        search_index, created = SearchIndex.objects.update_or_create(
            tenant=asset.tenant,
            resource_type="ASSET",
            resource_id=asset.id,
            defaults={
                "title": title,
                "description": description,
                "tags": tags,
                "tags_text": tags_text,
                "domain": asset.domain,
                "owner_id": owner_id,
                "owner_email": owner_email,
                "classification": classification,
            }
        )

        # Update search vector
        search_index.search_vector = (
            SearchVector("title", weight="A", config="english") +
            SearchVector("description", weight="B", config="english") +
            SearchVector("tags_text", weight="C", config="english")
        )
        search_index.save()

        logger.info(
            "Indexed asset",
            asset_id=str(asset.id),
            tenant_id=str(asset.tenant_id),
            created=created
        )

        return search_index

    @classmethod
    @transaction.atomic
    def index_dataset(cls, dataset: Dataset) -> SearchIndex:
        """Index a dataset"""
        # Dataset doesn't have a name field, use file name or fallback
        title = getattr(dataset, 'name', None) or (dataset.file.name if dataset.file else f"Dataset {dataset.id}")
        description = getattr(dataset, 'description', None) or ""

        # Extract schema
        schema_json = dataset.schema_json
        schema_fields = []
        schema_text = cls._flatten_schema(schema_json)

        if schema_json and isinstance(schema_json, dict):
            if "fields" in schema_json:
                schema_fields = schema_json["fields"]

        # Get classification
        classification = cls._get_classification(
            str(dataset.tenant_id),
            "DATASET",
            str(dataset.id)
        )

        # Get owner
        owner_id = dataset.created_by_id
        owner_email = dataset.created_by.email if dataset.created_by else None

        # Create or update search index
        search_index, created = SearchIndex.objects.update_or_create(
            tenant=dataset.tenant,
            resource_type="DATASET",
            resource_id=dataset.id,
            defaults={
                "title": title,
                "description": description,
                "schema_fields": schema_fields,
                "schema_text": schema_text,
                "owner_id": owner_id,
                "owner_email": owner_email,
                "classification": classification,
            }
        )

        # Update search vector
        search_index.search_vector = (
            SearchVector("title", weight="A", config="english") +
            SearchVector("description", weight="B", config="english") +
            SearchVector("schema_text", weight="C", config="english")
        )
        search_index.save()

        logger.info(
            "Indexed dataset",
            dataset_id=str(dataset.id),
            tenant_id=str(dataset.tenant_id),
            created=created
        )

        return search_index

    @classmethod
    @transaction.atomic
    def index_virtual_dataset(cls, virtual_dataset) -> SearchIndex:
        """
        Index a virtual dataset for search.

        Args:
            virtual_dataset: VirtualDataset instance to index

        Returns:
            SearchIndex instance
        """
        from hub.apps.virtualization.models import VirtualDataset

        # Extract virtual dataset data
        title = virtual_dataset.name
        description = virtual_dataset.description or ""

        # Extract schema
        schema_json = virtual_dataset.schema
        schema_fields = []
        schema_text = cls._flatten_schema(schema_json)

        if schema_json and isinstance(schema_json, dict):
            if "fields" in schema_json:
                schema_fields = schema_json["fields"]
            else:
                # If schema is a dict with field names as keys, convert to fields list
                schema_fields = [
                    {"name": key, "type": value.get("type", "") if isinstance(value, dict) else str(value)}
                    for key, value in schema_json.items()
                ]

        # Extract query type and query text for search
        query_type = virtual_dataset.query_type
        query_text = virtual_dataset.query or ""

        # Extract source information
        sources = virtual_dataset.sources or []
        sources_text = " ".join([
            str(source.get("type", "")) + " " + str(source.get("host", ""))
            for source in sources
            if isinstance(source, dict)
        ])

        # Combine searchable text: description, schema, query type, sources
        searchable_text = f"{description} {schema_text} {query_type} {sources_text}".strip()

        # Get classification (virtual datasets may not have direct classification)
        classification = cls._get_classification(
            str(virtual_dataset.tenant_id),
            "VIRTUAL_DATASET",
            str(virtual_dataset.id)
        )

        # Get owner
        owner_id = virtual_dataset.created_by_id
        owner_email = virtual_dataset.created_by.email if virtual_dataset.created_by else None

        # Extract tags if available (virtual datasets don't have tags field, use empty list)
        tags = []
        tags_text = ""

        # Create or update search index
        search_index, created = SearchIndex.objects.update_or_create(
            tenant=virtual_dataset.tenant,
            resource_type="VIRTUAL_DATASET",
            resource_id=virtual_dataset.id,
            defaults={
                "title": title,
                "description": description,
                "schema_fields": schema_fields,
                "schema_text": schema_text,
                "owner_id": owner_id,
                "owner_email": owner_email,
                "classification": classification,
                "tags": tags,
                "tags_text": tags_text,
            }
        )

        # Update search vector - include query type and sources in search
        search_index.search_vector = (
            SearchVector("title", weight="A", config="english") +
            SearchVector("description", weight="B", config="english") +
            SearchVector("schema_text", weight="C", config="english")
        )
        search_index.save()

        logger.info(
            "Indexed virtual dataset",
            virtual_dataset_id=str(virtual_dataset.id),
            tenant_id=str(virtual_dataset.tenant_id),
            created=created
        )

        return search_index

    @staticmethod
    @transaction.atomic
    def delete_index(tenant_id: str, resource_type: str, resource_id: str):
        """Delete a search index"""
        SearchIndex.objects.filter(
            tenant_id=tenant_id,
            resource_type=resource_type,
            resource_id=resource_id
        ).delete()

        logger.info(
            "Deleted search index",
            tenant_id=tenant_id,
            resource_type=resource_type,
            resource_id=resource_id
        )

    @staticmethod
    def rebuild_index(tenant_id: Optional[str] = None):
        """Rebuild search index for all resources or a specific tenant"""
        from django.db.models import Q

        queryset = Q()
        if tenant_id:
            queryset = Q(tenant_id=tenant_id)

        # Index contracts
        contracts = Contract.objects.filter(queryset)
        for contract in contracts:
            try:
                SearchIndexer.index_contract(contract)
            except Exception as e:
                logger.error(
                    "Failed to index contract",
                    contract_id=str(contract.id),
                    error=str(e)
                )

        # Index assets
        assets = Asset.objects.filter(queryset)
        for asset in assets:
            try:
                SearchIndexer.index_asset(asset)
            except Exception as e:
                logger.error(
                    "Failed to index asset",
                    asset_id=str(asset.id),
                    error=str(e)
                )

        # Index datasets
        datasets = Dataset.objects.filter(queryset)
        for dataset in datasets:
            try:
                SearchIndexer.index_dataset(dataset)
            except Exception as e:
                logger.error(
                    "Failed to index dataset",
                    dataset_id=str(dataset.id),
                    error=str(e)
                )

        # Index virtual datasets
        try:
            from hub.apps.virtualization.models import VirtualDataset
            virtual_datasets = VirtualDataset.objects.filter(queryset)
            for virtual_dataset in virtual_datasets:
                try:
                    SearchIndexer.index_virtual_dataset(virtual_dataset)
                except Exception as e:
                    logger.error(
                        "Failed to index virtual dataset",
                        virtual_dataset_id=str(virtual_dataset.id),
                        error=str(e)
                    )
        except ImportError:
            # VirtualDataset model not available (e.g., in migrations)
            pass

        logger.info(
            "Rebuilt search index",
            tenant_id=tenant_id or "all"
        )

