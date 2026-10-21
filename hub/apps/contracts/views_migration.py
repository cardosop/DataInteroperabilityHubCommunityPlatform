"""
Contract Views Migration Operations

Migration actions for contract viewsets.

SAVING CHECKPOINT: This module contains migration-related actions.
"""

from drf_spectacular.utils import (
    OpenApiResponse,
    extend_schema,
)
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response

from .migration import MigrationStrategy, get_current_hubcontract_version
from .migration_manager import ContractMigrationManager
from .serializers import ContractSerializer


class ContractMigrationMixin:
    """
    Mixin for Contract migration operations.

    Provides contract migration endpoints for upgrading HubContract versions.
    """

    @extend_schema(
        summary="Migrate contract",
        description="""
        Migrate contract to a new HubContract version.

        Supports ON_WRITE (persistent), ON_READ (lazy), and BACKGROUND (async) strategies.
        """,
        request=None,
        responses={
            200: OpenApiResponse(description="Migration completed"),
            202: OpenApiResponse(description="Migration job created"),
            400: OpenApiResponse(description="Migration failed or not needed"),
        },
        tags=["Contracts", "Migration"],
    )
    @action(detail=True, methods=["post"], url_path="migrate")
    def migrate_contract(self, request, id=None):
        """
        Migrate contract to a new HubContract version.

        POST /contracts/{id}/migrate
        Body: {
            "target_hub_contract_version": "2.0.0" (optional, defaults to current),
            "migration_strategy": "ON_WRITE" | "ON_READ" | "BACKGROUND" (optional, default: "ON_WRITE")
        }

        Returns migration result or job ID for BACKGROUND strategy.
        """
        contract = self.get_object()

        target_version = request.data.get("target_hub_contract_version")
        if not target_version:
            target_version = get_current_hubcontract_version()

        strategy = request.data.get("migration_strategy", MigrationStrategy.ON_WRITE)

        if strategy not in [
            MigrationStrategy.ON_WRITE,
            MigrationStrategy.ON_READ,
            MigrationStrategy.BACKGROUND,
        ]:
            return Response(
                {"error": f"Invalid migration_strategy: {strategy}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Check if migration is needed
        if not contract.hub_contract_json or not contract.hub_contract_version:
            return Response(
                {"error": "Contract is not normalized. Cannot migrate."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if contract.hub_contract_version == target_version:
            return Response(
                {
                    "contract": ContractSerializer(contract).data,
                    "migration_applied": False,
                    "migration_details": {
                        "source_version": contract.hub_contract_version,
                        "target_version": target_version,
                        "message": "Contract is already at target version",
                    },
                },
                status=status.HTTP_200_OK,
            )

        # Execute migration based on strategy
        if strategy == MigrationStrategy.ON_WRITE:
            migrated, migrated_hub_contract, warnings = ContractMigrationManager.migrate_on_write(
                contract
            )

            if not migrated:
                # Migration not needed (already at target version) or failed
                # Check if it's because migration isn't needed
                from .migration import needs_migration

                if not needs_migration(contract.hub_contract_version):
                    # Already at target version - return success
                    return Response(
                        {
                            "contract": ContractSerializer(contract).data,
                            "migration_applied": False,
                            "migration_details": {
                                "source_version": contract.hub_contract_version,
                                "target_version": target_version,
                                "message": "Contract is already at target version",
                            },
                        },
                        status=status.HTTP_200_OK,
                    )
                else:
                    # Migration failed
                    return Response(
                        {"error": "Migration failed or not supported"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

            # Refresh contract from DB
            contract.refresh_from_db()

            return Response(
                {
                    "contract": ContractSerializer(contract).data,
                    "migration_applied": True,
                    "migration_details": {
                        "source_version": contract.hub_contract_version,
                        "target_version": target_version,
                        "migration_strategy": strategy,
                        "warnings": warnings,
                    },
                },
                status=status.HTTP_200_OK,
            )

        elif strategy == MigrationStrategy.ON_READ:
            migrated_hub_contract, warnings = ContractMigrationManager.migrate_on_read(contract)

            # Return migrated version (in-memory, not persisted)
            serializer = ContractSerializer(contract)
            response_data = serializer.data
            response_data["hub_contract_json"] = migrated_hub_contract

            return Response(
                {
                    "contract": response_data,
                    "migration_applied": True,
                    "migration_details": {
                        "source_version": contract.hub_contract_version,
                        "target_version": target_version,
                        "migration_strategy": strategy,
                        "warnings": warnings,
                        "note": "Migration applied in-memory only (lazy migration)",
                    },
                },
                status=status.HTTP_200_OK,
            )

        elif strategy == MigrationStrategy.BACKGROUND:
            job = ContractMigrationManager.migrate_background(contract, user=request.user)

            if not job:
                # Check if migration isn't needed (already at target version)
                from .migration import needs_migration

                if not needs_migration(contract.hub_contract_version):
                    # Already at target version - return success
                    return Response(
                        {
                            "contract": ContractSerializer(contract).data,
                            "migration_applied": False,
                            "migration_details": {
                                "source_version": contract.hub_contract_version,
                                "target_version": target_version,
                                "message": "Contract is already at target version",
                            },
                        },
                        status=status.HTTP_200_OK,
                    )
                else:
                    # Migration failed
                    return Response(
                        {"error": "Migration failed or not needed"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

            return Response(
                {
                    "job": {
                        "id": str(job.id),
                        "type": job.type,
                        "status": job.status,
                        "resource_type": job.resource_type,
                        "resource_id": str(job.resource_id),
                    },
                    "migration_details": {
                        "source_version": contract.hub_contract_version,
                        "target_version": target_version,
                        "migration_strategy": strategy,
                    },
                },
                status=status.HTTP_202_ACCEPTED,
            )
