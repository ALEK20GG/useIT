"""
Migration service for transforming existing PDF system to folder structure.
"""

import logging
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional

from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct, Filter, FieldCondition, MatchValue
from fastapi import HTTPException, status

from .folder_service import FolderService
from .folder_models import FolderDefinition, ContentType

logger = logging.getLogger(__name__)


class MigrationResult:
    """Result of a migration operation."""

    def __init__(
        self,
        success: bool,
        message: str,
        migrated_count: int = 0,
        target_folder: Optional[str] = None,
        migration_timestamp: Optional[str] = None,
        errors: Optional[List[str]] = None,
    ):
        self.success = success
        self.message = message
        self.migrated_count = migrated_count
        self.target_folder = target_folder
        self.migration_timestamp = migration_timestamp or datetime.now(timezone.utc).isoformat()
        self.errors = errors or []


class StepResult:
    """Result of a single migration step."""

    def __init__(self, step: str, success: bool, message: str, details: Optional[Dict[str, Any]] = None):
        self.step = step
        self.success = success
        self.message = message
        self.details = details or {}


class MigrationReport:
    """Full report from a system migration execution."""

    def __init__(
        self,
        success: bool,
        steps_completed: int,
        migration_time: str,
        details: List[Dict[str, Any]],
        errors: Optional[List[str]] = None,
    ):
        self.success = success
        self.steps_completed = steps_completed
        self.migration_time = migration_time
        self.details = details
        self.errors = errors or []


class MigrationService:
    """Handles migration from existing PDF system to folder structure."""

    def __init__(self, qdrant_client: QdrantClient, folder_service: FolderService):
        self.qdrant_client = qdrant_client
        self.folder_service = folder_service
        self.pdf_collection = "pdfs"

    async def migrate_existing_pdfs(self) -> MigrationResult:
        """Migrate existing PDF collection to Dispositivi folder.

        This operation is idempotent: running it multiple times will not
        duplicate data because Qdrant upsert uses the original point IDs.
        """

        try:
            logger.info("Starting PDF migration to folder structure...")

            # Check if PDF collection exists
            try:
                pdf_collection_info = self.qdrant_client.get_collection(self.pdf_collection)
                logger.info(f"Found existing PDF collection with {pdf_collection_info.points_count} points")
            except Exception:
                logger.info("No existing PDF collection found, migration not needed")
                return MigrationResult(
                    success=True,
                    message="No existing PDF data to migrate",
                    migrated_count=0,
                )

            # Ensure Dispositivi folder exists
            dispositivi_folder = await self._ensure_dispositivi_folder()

            # Get all existing PDF points
            existing_points = await self._get_all_pdf_points()

            if not existing_points:
                return MigrationResult(
                    success=True,
                    message="No PDF points found to migrate",
                    migrated_count=0,
                    target_folder=dispositivi_folder.id,
                )

            # Transform and migrate points (idempotent via upsert)
            migration_timestamp = datetime.now(timezone.utc).isoformat()
            migrated_count = await self._migrate_points_to_folder(
                existing_points, dispositivi_folder.id, migration_timestamp
            )

            logger.info(f"Successfully migrated {migrated_count} PDF documents to Dispositivi folder")

            return MigrationResult(
                success=True,
                message=f"Successfully migrated {migrated_count} PDF documents to Dispositivi folder",
                migrated_count=migrated_count,
                target_folder=dispositivi_folder.id,
                migration_timestamp=migration_timestamp,
            )

        except Exception as e:
            logger.error(f"Migration failed: {e}")
            return MigrationResult(
                success=False,
                message=f"Migration failed: {str(e)}",
                errors=[str(e)],
            )

    async def _ensure_dispositivi_folder(self):
        """Ensure Dispositivi folder exists, create if not."""

        # Try to find existing Dispositivi folder
        dispositivi_folder = await self.folder_service.get_folder_by_name("Dispositivi")

        if dispositivi_folder:
            logger.info("Found existing Dispositivi folder")
            return dispositivi_folder

        # Create Dispositivi folder
        logger.info("Creating Dispositivi folder for migration")

        folder_def = FolderDefinition(
            name="Dispositivi",
            description="Device documentation migrated from PDF system",
            content_types=[ContentType.DEVICE_DOCUMENTATION, ContentType.PDF_DOCUMENTS],
            metadata={
                "is_default": True,
                "migrated_from": "pdfs",
                "migration_timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )

        return await self.folder_service.create_folder(folder_def, collection_name="dispositivi")

    async def _get_all_pdf_points(self) -> List[Any]:
        """Get all points from the PDF collection."""

        all_points = []
        offset = None

        try:
            while True:
                points, next_offset = self.qdrant_client.scroll(
                    collection_name=self.pdf_collection,
                    limit=100,
                    offset=offset,
                    with_payload=True,
                    with_vectors=True,
                )

                all_points.extend(points)

                if next_offset is None:
                    break
                offset = next_offset

            logger.info(f"Retrieved {len(all_points)} points from PDF collection")
            return all_points

        except Exception as e:
            logger.error(f"Failed to retrieve PDF points: {e}")
            raise

    async def _migrate_points_to_folder(
        self, points: List[Any], folder_id: str, migration_timestamp: str
    ) -> int:
        """Migrate points to the new folder collection (idempotent via upsert)."""

        dispositivi_folder = await self.folder_service.get_folder(folder_id)
        if not dispositivi_folder:
            raise ValueError(f"Folder {folder_id} not found")

        migrated_count = 0
        batch_size = 100

        # Process points in batches
        for i in range(0, len(points), batch_size):
            batch = points[i : i + batch_size]
            transformed_points = []

            for point in batch:
                try:
                    # Preserve all existing payload fields and add folder metadata
                    enhanced_payload = {
                        **point.payload,
                        "folder_id": folder_id,
                        "content_type": ContentType.DEVICE_DOCUMENTATION.value,
                        "migrated_from": self.pdf_collection,
                        "migration_timestamp": migration_timestamp,
                    }

                    transformed_point = PointStruct(
                        id=point.id,
                        vector=point.vector,
                        payload=enhanced_payload,
                    )
                    transformed_points.append(transformed_point)

                except Exception as e:
                    logger.warning(f"Failed to transform point {point.id}: {e}")
                    continue

            if transformed_points:
                # Upsert batch to new collection (idempotent)
                self.qdrant_client.upsert(
                    collection_name=dispositivi_folder.qdrant_collection,
                    points=transformed_points,
                )

                migrated_count += len(transformed_points)
                logger.info(f"Migrated batch of {len(transformed_points)} points")

        # Update folder content count to reflect actual Qdrant count
        try:
            collection_info = self.qdrant_client.get_collection(dispositivi_folder.qdrant_collection)
            actual_count = collection_info.points_count or 0
            # Reset and set to actual count
            delta = actual_count - dispositivi_folder.content_count
            if delta != 0:
                await self.folder_service._update_folder_content_count(folder_id, delta)
        except Exception as e:
            logger.warning(f"Could not sync folder content count: {e}")

        return migrated_count

    async def validate_migration(self) -> Dict[str, Any]:
        """Validate migration integrity by comparing document counts."""

        try:
            # Get original PDF collection count
            original_count = 0
            try:
                pdf_collection_info = self.qdrant_client.get_collection(self.pdf_collection)
                original_count = pdf_collection_info.points_count or 0
            except Exception:
                pass

            # Get Dispositivi folder count
            dispositivi_folder = await self.folder_service.get_folder_by_name("Dispositivi")
            migrated_count = 0
            dispositivi_folder_id = None

            if dispositivi_folder:
                dispositivi_folder_id = dispositivi_folder.id
                try:
                    dispositivi_collection_info = self.qdrant_client.get_collection(
                        dispositivi_folder.qdrant_collection
                    )
                    migrated_count = dispositivi_collection_info.points_count or 0
                except Exception:
                    pass

            validation_result = {
                "original_pdf_count": original_count,
                "migrated_count": migrated_count,
                "migration_complete": migrated_count > 0,
                "counts_match": original_count == migrated_count,
                "dispositivi_folder_id": dispositivi_folder_id,
                "validation_timestamp": datetime.now(timezone.utc).isoformat(),
            }

            logger.info(f"Migration validation: {validation_result}")
            return validation_result

        except Exception as e:
            logger.error(f"Migration validation failed: {e}")
            return {
                "error": str(e),
                "validation_timestamp": datetime.now(timezone.utc).isoformat(),
            }

    async def rollback_migration(self) -> MigrationResult:
        """Rollback migration by removing migrated content from Dispositivi folder."""

        try:
            logger.info("Starting migration rollback...")

            dispositivi_folder = await self.folder_service.get_folder_by_name("Dispositivi")
            if not dispositivi_folder:
                return MigrationResult(
                    success=True,
                    message="No Dispositivi folder found, rollback not needed",
                )

            # Delete points that were migrated (have migration metadata)
            try:
                self.qdrant_client.delete(
                    collection_name=dispositivi_folder.qdrant_collection,
                    points_selector=Filter(
                        must=[
                            FieldCondition(
                                key="migrated_from",
                                match=MatchValue(value=self.pdf_collection),
                            )
                        ]
                    ),
                )

                logger.info("Removed migrated points from Dispositivi collection")

            except Exception as e:
                logger.warning(f"Failed to remove migrated points: {e}")

            # Reset folder content count to 0 (all migrated content removed)
            try:
                collection_info = self.qdrant_client.get_collection(dispositivi_folder.qdrant_collection)
                actual_count = collection_info.points_count or 0
                delta = actual_count - dispositivi_folder.content_count
                if delta != 0:
                    await self.folder_service._update_folder_content_count(dispositivi_folder.id, delta)
                elif dispositivi_folder.content_count > 0:
                    await self.folder_service._update_folder_content_count(
                        dispositivi_folder.id, -dispositivi_folder.content_count
                    )
            except Exception as e:
                logger.warning(f"Could not sync folder content count after rollback: {e}")

            return MigrationResult(
                success=True,
                message="Migration rollback completed successfully",
            )

        except Exception as e:
            logger.error(f"Migration rollback failed: {e}")
            return MigrationResult(
                success=False,
                message=f"Migration rollback failed: {str(e)}",
                errors=[str(e)],
            )

    async def get_migration_status(self) -> Dict[str, Any]:
        """Get current migration status without executing migration."""

        try:
            # Check source collection
            source_exists = False
            source_count = 0
            try:
                pdf_info = self.qdrant_client.get_collection(self.pdf_collection)
                source_exists = True
                source_count = pdf_info.points_count or 0
            except Exception:
                pass

            # Check destination folder
            dispositivi_folder = await self.folder_service.get_folder_by_name("Dispositivi")
            destination_exists = dispositivi_folder is not None
            destination_count = 0
            destination_folder_id = None

            if dispositivi_folder:
                destination_folder_id = dispositivi_folder.id
                try:
                    dest_info = self.qdrant_client.get_collection(dispositivi_folder.qdrant_collection)
                    destination_count = dest_info.points_count or 0
                except Exception:
                    pass

            # Determine migration state
            if not source_exists and not destination_exists:
                migration_state = "no_data"
            elif not source_exists and destination_exists:
                migration_state = "source_removed"
            elif source_exists and not destination_exists:
                migration_state = "not_started"
            elif destination_count == 0:
                migration_state = "not_started"
            elif destination_count >= source_count and source_count > 0:
                migration_state = "completed"
            else:
                migration_state = "partial"

            return {
                "migration_state": migration_state,
                "source_collection": self.pdf_collection,
                "source_exists": source_exists,
                "source_count": source_count,
                "destination_folder": "Dispositivi",
                "destination_folder_id": destination_folder_id,
                "destination_exists": destination_exists,
                "destination_count": destination_count,
                "counts_match": source_count == destination_count,
                "status_timestamp": datetime.now(timezone.utc).isoformat(),
            }

        except Exception as e:
            logger.error(f"Failed to get migration status: {e}")
            return {
                "migration_state": "error",
                "error": str(e),
                "status_timestamp": datetime.now(timezone.utc).isoformat(),
            }


class SystemMigrationService:
    """Orchestrates complete system migration from PDF system to folder structure."""

    def __init__(self, qdrant_client: QdrantClient, folder_service: FolderService):
        self.qdrant_client = qdrant_client
        self.folder_service = folder_service
        self.migration_service = MigrationService(qdrant_client, folder_service)

    async def execute_migration(self) -> MigrationReport:
        """Execute complete migration process with step tracking and rollback on failure.

        This is idempotent: running it multiple times is safe because Qdrant
        upsert uses the original point IDs and the Dispositivi folder creation
        is guarded by a name lookup.
        """

        migration_time = datetime.now(timezone.utc).isoformat()
        results: List[StepResult] = []

        migration_steps = [
            ("create_folder_infrastructure", self._create_folder_infrastructure),
            ("migrate_pdf_data", self._migrate_pdf_data),
            ("validate_migration", self._validate_migration),
        ]

        for step_name, step_fn in migration_steps:
            try:
                result = await step_fn()
                results.append(result)
                logger.info(f"Migration step '{step_name}' completed: {result.message}")

                if not result.success:
                    # Attempt rollback on failure
                    logger.warning(f"Step '{step_name}' failed, attempting rollback...")
                    await self._rollback_migration(results)
                    return MigrationReport(
                        success=False,
                        steps_completed=len(results),
                        migration_time=migration_time,
                        details=[self._step_to_dict(r) for r in results],
                        errors=[result.message],
                    )

            except Exception as e:
                error_msg = f"Migration failed at step '{step_name}': {e}"
                logger.error(error_msg)
                await self._rollback_migration(results)
                return MigrationReport(
                    success=False,
                    steps_completed=len(results),
                    migration_time=migration_time,
                    details=[self._step_to_dict(r) for r in results],
                    errors=[error_msg],
                )

        return MigrationReport(
            success=True,
            steps_completed=len(results),
            migration_time=migration_time,
            details=[self._step_to_dict(r) for r in results],
        )

    def _step_to_dict(self, result: StepResult) -> Dict[str, Any]:
        return {
            "step": result.step,
            "success": result.success,
            "message": result.message,
            "details": result.details,
        }

    async def _create_folder_infrastructure(self) -> StepResult:
        """Ensure the Dispositivi folder and Qdrant collection exist."""
        try:
            folder = await self.migration_service._ensure_dispositivi_folder()
            return StepResult(
                step="create_folder_infrastructure",
                success=True,
                message=f"Dispositivi folder ready (ID: {folder.id})",
                details={"folder_id": folder.id, "collection": folder.qdrant_collection},
            )
        except Exception as e:
            return StepResult(
                step="create_folder_infrastructure",
                success=False,
                message=f"Failed to create folder infrastructure: {e}",
            )

    async def _migrate_pdf_data(self) -> StepResult:
        """Migrate existing PDF data to folder structure."""
        try:
            result = await self.migration_service.migrate_existing_pdfs()
            return StepResult(
                step="migrate_pdf_data",
                success=result.success,
                message=result.message,
                details={
                    "migrated_count": result.migrated_count,
                    "target_folder": result.target_folder,
                    "migration_timestamp": result.migration_timestamp,
                    "errors": result.errors,
                },
            )
        except Exception as e:
            return StepResult(
                step="migrate_pdf_data",
                success=False,
                message=f"PDF data migration failed: {e}",
            )

    async def _validate_migration(self) -> StepResult:
        """Validate migration integrity."""
        try:
            validation = await self.migration_service.validate_migration()
            success = "error" not in validation
            return StepResult(
                step="validate_migration",
                success=success,
                message=(
                    f"Validation complete: {validation.get('migrated_count', 0)} points migrated, "
                    f"counts_match={validation.get('counts_match', False)}"
                ),
                details=validation,
            )
        except Exception as e:
            return StepResult(
                step="validate_migration",
                success=False,
                message=f"Validation failed: {e}",
            )

    async def _rollback_migration(self, completed_steps: List[StepResult]) -> None:
        """Rollback migration steps that were completed."""
        logger.info(f"Rolling back {len(completed_steps)} completed migration steps...")
        try:
            rollback_result = await self.migration_service.rollback_migration()
            if rollback_result.success:
                logger.info("Rollback completed successfully")
            else:
                logger.error(f"Rollback failed: {rollback_result.message}")
        except Exception as e:
            logger.error(f"Rollback encountered an error: {e}")
