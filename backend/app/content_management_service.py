"""
Content Management Service for file upload, text extraction, embedding generation,
and Qdrant indexing.

Implements Requirements 6.1-6.5 (upload & indexing) and 7.1-7.5 (file management).
"""

import json
import logging
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, FieldCondition, Filter, MatchValue, PointStruct, VectorParams

from .embeddings import embed_text_batch
from .folder_service import FolderService
from .folder_models import Folder
from .document_utils import extract_text_from_pdf, chunk_text

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# File record data model
# ---------------------------------------------------------------------------

_BACKEND_DIR = Path(__file__).parent.parent  # backend/
_DEFAULT_FILES_PATH = _BACKEND_DIR / "storage" / "files" / "files.json"
_DEFAULT_UPLOADS_DIR = _BACKEND_DIR / "storage" / "uploads"


class FileRecord:
    """Metadata record for an uploaded file."""

    def __init__(
        self,
        id: str,
        filename: str,
        original_filename: str,
        folder_id: str,
        file_size: int,
        content_type: str,
        upload_date: str,
        chunk_count: int,
        status: str,
        file_path: str,
    ) -> None:
        self.id = id
        self.filename = filename
        self.original_filename = original_filename
        self.folder_id = folder_id
        self.file_size = file_size
        self.content_type = content_type
        self.upload_date = upload_date
        self.chunk_count = chunk_count
        self.status = status
        self.file_path = file_path

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "filename": self.filename,
            "original_filename": self.original_filename,
            "folder_id": self.folder_id,
            "file_size": self.file_size,
            "content_type": self.content_type,
            "upload_date": self.upload_date,
            "chunk_count": self.chunk_count,
            "status": self.status,
            "file_path": self.file_path,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FileRecord":
        return cls(
            id=data["id"],
            filename=data["filename"],
            original_filename=data["original_filename"],
            folder_id=data["folder_id"],
            file_size=data["file_size"],
            content_type=data["content_type"],
            upload_date=data["upload_date"],
            chunk_count=data["chunk_count"],
            status=data["status"],
            file_path=data["file_path"],
        )


class BulkDeleteResult:
    """Result of a bulk delete operation."""

    def __init__(
        self,
        deleted: List[str],
        failed: List[str],
        errors: Dict[str, str],
    ) -> None:
        self.deleted = deleted
        self.failed = failed
        self.errors = errors

    def to_dict(self) -> Dict[str, Any]:
        return {
            "deleted": self.deleted,
            "failed": self.failed,
            "errors": self.errors,
            "deleted_count": len(self.deleted),
            "failed_count": len(self.failed),
        }


# ---------------------------------------------------------------------------
# Content Management Service
# ---------------------------------------------------------------------------


class ContentManagementService:
    """
    Manages file uploads, text extraction, embedding generation, and Qdrant indexing.

    Supports PDF, DOC, DOCX, and TXT file formats (Requirement 6.1).
    Requires folder assignment during upload (Requirement 6.2).
    Automatically extracts text and generates embeddings (Requirement 6.3).
    Indexes content in the appropriate Qdrant collection (Requirement 6.4).
    """

    SUPPORTED_FORMATS = {".pdf", ".doc", ".docx", ".txt"}

    def __init__(
        self,
        qdrant_client: QdrantClient,
        folder_service: FolderService,
        files_path: Optional[str] = None,
        uploads_dir: Optional[str] = None,
    ) -> None:
        self.qdrant_client = qdrant_client
        self.folder_service = folder_service

        self._files_path = Path(files_path) if files_path else _DEFAULT_FILES_PATH
        self._uploads_dir = Path(uploads_dir) if uploads_dir else _DEFAULT_UPLOADS_DIR

        # Ensure storage directories exist
        self._files_path.parent.mkdir(parents=True, exist_ok=True)
        self._uploads_dir.mkdir(parents=True, exist_ok=True)

        # Ensure files.json exists
        if not self._files_path.exists():
            self._files_path.write_text("[]", encoding="utf-8")

    # ------------------------------------------------------------------
    # Internal helpers – file metadata store
    # ------------------------------------------------------------------

    def _load_records(self) -> List[Dict[str, Any]]:
        """Load all file records from disk."""
        try:
            text = self._files_path.read_text(encoding="utf-8")
            data = json.loads(text)
            return data if isinstance(data, list) else []
        except (json.JSONDecodeError, OSError):
            return []

    def _save_records(self, records: List[Dict[str, Any]]) -> None:
        """Persist all file records to disk."""
        self._files_path.write_text(
            json.dumps(records, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    def _add_record(self, record: FileRecord) -> None:
        records = self._load_records()
        records.append(record.to_dict())
        self._save_records(records)

    def _update_record(self, record: FileRecord) -> None:
        records = self._load_records()
        for i, r in enumerate(records):
            if r.get("id") == record.id:
                records[i] = record.to_dict()
                self._save_records(records)
                return

    def _remove_record(self, file_id: str) -> bool:
        records = self._load_records()
        new_records = [r for r in records if r.get("id") != file_id]
        if len(new_records) == len(records):
            return False
        self._save_records(new_records)
        return True

    # ------------------------------------------------------------------
    # Text extraction helpers
    # ------------------------------------------------------------------

    async def extract_text(self, file_path: str, filename: str) -> str:
        """
        Extract text from a file based on its extension.

        Supports PDF, DOCX, DOC, and TXT formats (Requirement 6.1).
        """
        path = Path(file_path)
        ext = path.suffix.lower()

        if ext == ".pdf":
            return self._extract_pdf_text(path)
        elif ext == ".txt":
            return self._extract_txt_text(path)
        elif ext in (".docx", ".doc"):
            return self._extract_docx_text(path)
        else:
            raise ValueError(f"Unsupported file format: {ext}")

    def _extract_pdf_text(self, path: Path) -> str:
        """Extract text from a PDF file."""
        with open(path, "rb") as f:
            file_content = f.read()
        pages = extract_text_from_pdf(file_content)
        return "\n\n".join(text for _, text in pages)

    def _extract_txt_text(self, path: Path) -> str:
        """Extract text from a plain text file."""
        try:
            return path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            return path.read_text(encoding="latin-1")

    def _extract_docx_text(self, path: Path) -> str:
        """Extract text from a DOCX/DOC file using python-docx if available."""
        try:
            import docx  # type: ignore
            doc = docx.Document(str(path))
            paragraphs = [para.text for para in doc.paragraphs if para.text.strip()]
            return "\n\n".join(paragraphs)
        except ImportError:
            logger.warning("python-docx not available; reading DOCX as plain text")
            return self._extract_txt_text(path)
        except Exception as e:
            logger.warning(f"Failed to parse DOCX with python-docx: {e}; falling back to plain text")
            return self._extract_txt_text(path)

    # ------------------------------------------------------------------
    # Indexing
    # ------------------------------------------------------------------

    async def index_content(
        self,
        text: str,
        file_record: FileRecord,
        folder: Folder,
    ) -> int:
        """
        Chunk text, generate embeddings in batches, and index into the folder's
        Qdrant collection.

        Processes in small batches to avoid OOM crashes on large files.
        Returns the number of chunks indexed (Requirement 6.4).
        """
        if not text or not text.strip():
            logger.warning(f"No text to index for file {file_record.id}")
            return 0

        # Chunk text into ~500 character chunks with overlap
        chunks = chunk_text(text, chunk_size=500, overlap=100)
        if not chunks:
            return 0

        # Hard limit: cap at 2000 chunks to prevent OOM on huge files
        if len(chunks) > 2000:
            logger.warning(
                f"File {file_record.id} produced {len(chunks)} chunks; "
                "truncating to 2000 to prevent memory exhaustion."
            )
            chunks = chunks[:2000]

        # Determine vector size from a small sample first
        sample_vectors = embed_text_batch([chunks[0]])
        if not sample_vectors:
            return 0
        vector_size = len(sample_vectors[0])

        # Ensure Qdrant collection exists with correct vector size
        collection_name = folder.qdrant_collection
        try:
            collection_info = self.qdrant_client.get_collection(collection_name)
            existing_size = collection_info.config.params.vectors.size
            if existing_size != vector_size:
                self.qdrant_client.delete_collection(collection_name=collection_name)
                self.qdrant_client.create_collection(
                    collection_name=collection_name,
                    vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
                )
        except Exception:
            self.qdrant_client.create_collection(
                collection_name=collection_name,
                vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
            )

        namespace = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")
        total_indexed = 0
        BATCH_SIZE = 50  # Process 50 chunks at a time to keep RAM usage low

        for batch_start in range(0, len(chunks), BATCH_SIZE):
            batch_chunks = chunks[batch_start:batch_start + BATCH_SIZE]

            # Generate embeddings for this batch only
            vectors = embed_text_batch(batch_chunks)
            if not vectors:
                continue

            points: List[PointStruct] = []
            for chunk_idx, (chunk_text_content, vector) in enumerate(
                zip(batch_chunks, vectors), start=batch_start
            ):
                unique_name = f"{file_record.id}:{chunk_idx}"
                point_id = str(uuid.uuid5(namespace, unique_name))

                payload = {
                    "file_id": file_record.id,
                    "filename": file_record.filename,
                    "original_filename": file_record.original_filename,
                    "folder_id": file_record.folder_id,
                    "chunk_index": chunk_idx,
                    "chunk_text": chunk_text_content[:500],
                    "total_chunks": len(chunks),
                    "upload_date": file_record.upload_date,
                    "content_type": file_record.content_type,
                }

                points.append(PointStruct(id=point_id, vector=vector, payload=payload))

            self.qdrant_client.upsert(collection_name=collection_name, points=points)
            total_indexed += len(points)
            logger.debug(
                f"Indexed batch {batch_start}-{batch_start + len(batch_chunks)} "
                f"for file {file_record.id}"
            )

        logger.info(
            f"Indexed {total_indexed} chunks for file {file_record.id} "
            f"into collection '{collection_name}'"
        )
        return total_indexed

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def upload_file(
        self,
        file_data: bytes,
        filename: str,
        folder_id: str,
        content_type: str = "application/octet-stream",
    ) -> FileRecord:
        """
        Upload a file, save to disk, extract text, generate embeddings, and index.

        Requirements 6.1-6.5.
        """
        # Validate file format (Requirement 6.1)
        original_filename = os.path.basename(filename)
        ext = Path(original_filename).suffix.lower()
        if ext not in self.SUPPORTED_FORMATS:
            raise ValueError(
                f"Unsupported file format '{ext}'. "
                f"Supported formats: {', '.join(sorted(self.SUPPORTED_FORMATS))}"
            )

        # Validate folder exists (Requirement 6.2)
        folder = await self.folder_service.get_folder(folder_id)
        if folder is None:
            raise ValueError(f"Folder '{folder_id}' not found")

        # Block duplicate filenames in the same folder
        existing = self._load_records()
        for rec in existing:
            if (
                rec.get("folder_id") == folder_id
                and rec.get("original_filename") == original_filename
                and rec.get("status") != "failed"
            ):
                raise ValueError(
                    f"Il file '{original_filename}' esiste già nella cartella "
                    f"'{folder.name}'. Elimina il file esistente prima di ricaricare."
                )

        # Generate unique file ID and safe filename
        file_id = str(uuid4())
        safe_filename = f"{file_id}{ext}"

        # Save file to uploads/{folder_id}/ directory
        folder_upload_dir = self._uploads_dir / folder_id
        folder_upload_dir.mkdir(parents=True, exist_ok=True)
        file_path = folder_upload_dir / safe_filename

        file_path.write_bytes(file_data)
        logger.info(f"Saved file {original_filename} -> {file_path}")

        # Create initial file record with 'processing' status
        record = FileRecord(
            id=file_id,
            filename=safe_filename,
            original_filename=original_filename,
            folder_id=folder_id,
            file_size=len(file_data),
            content_type=content_type,
            upload_date=datetime.now(timezone.utc).isoformat(),
            chunk_count=0,
            status="processing",
            file_path=str(file_path),
        )
        self._add_record(record)

        try:
            # Extract text (Requirement 6.3)
            text = await self.extract_text(str(file_path), original_filename)

            # Index content (Requirement 6.4)
            chunk_count = await self.index_content(text, record, folder)

            # Update record with final status
            record.chunk_count = chunk_count
            record.status = "indexed"
            self._update_record(record)

            # Update folder content count
            await self.folder_service._update_folder_content_count(folder_id, 1)

            logger.info(
                f"File {original_filename} uploaded and indexed: "
                f"{chunk_count} chunks in folder '{folder.name}'"
            )
        except Exception as e:
            # Mark as failed but keep the record (Requirement 6.5)
            record.status = "failed"
            self._update_record(record)
            logger.error(f"Failed to process file {original_filename}: {e}")
            raise

        return record

    async def list_files(
        self,
        folder_id: Optional[str] = None,
    ) -> List[FileRecord]:
        """
        List all uploaded files, optionally filtered by folder.

        Requirement 7.1.
        """
        records = self._load_records()
        file_records = [FileRecord.from_dict(r) for r in records]

        if folder_id is not None:
            file_records = [r for r in file_records if r.folder_id == folder_id]

        return file_records

    async def get_file(self, file_id: str) -> Optional[FileRecord]:
        """
        Get file metadata by ID.

        Requirement 7.2.
        """
        for raw in self._load_records():
            if raw.get("id") == file_id:
                return FileRecord.from_dict(raw)
        return None

    async def delete_file(self, file_id: str) -> bool:
        """
        Delete a file from disk storage and remove its Qdrant index entries.

        Requirement 7.3.
        """
        record = await self.get_file(file_id)
        if record is None:
            return False

        # Remove Qdrant index entries
        folder = await self.folder_service.get_folder(record.folder_id)
        if folder is not None:
            try:
                self.qdrant_client.delete(
                    collection_name=folder.qdrant_collection,
                    points_selector=Filter(
                        must=[
                            FieldCondition(
                                key="file_id",
                                match=MatchValue(value=file_id),
                            )
                        ]
                    ),
                )
                logger.info(
                    f"Deleted Qdrant entries for file {file_id} "
                    f"from collection '{folder.qdrant_collection}'"
                )
            except Exception as e:
                logger.warning(f"Failed to delete Qdrant entries for file {file_id}: {e}")

        # Remove file from disk
        file_path = Path(record.file_path)
        if file_path.exists():
            file_path.unlink()
            logger.info(f"Deleted file from disk: {file_path}")

        # Remove metadata record
        self._remove_record(file_id)

        # Update folder content count
        if folder is not None and record.status == "indexed":
            await self.folder_service._update_folder_content_count(record.folder_id, -1)

        return True

    async def bulk_delete_files(self, file_ids: List[str]) -> BulkDeleteResult:
        """
        Delete multiple files at once.

        Requirement 7.5.
        """
        deleted: List[str] = []
        failed: List[str] = []
        errors: Dict[str, str] = {}

        for file_id in file_ids:
            try:
                success = await self.delete_file(file_id)
                if success:
                    deleted.append(file_id)
                else:
                    failed.append(file_id)
                    errors[file_id] = "File not found"
            except Exception as e:
                failed.append(file_id)
                errors[file_id] = str(e)
                logger.error(f"Failed to delete file {file_id}: {e}")

        return BulkDeleteResult(deleted=deleted, failed=failed, errors=errors)
