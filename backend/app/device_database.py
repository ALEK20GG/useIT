"""
Device database for storing and retrieving device information.

Implements Requirements 1.1-1.4, 2.1-2.4:
- Device CRUD operations backed by JSON file storage
- Search by name, manufacturer, model
- QR code association for documentation lookup
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Device data models
# ---------------------------------------------------------------------------


class DeviceRecord(BaseModel):
    """Full device record stored in the database."""

    id: str = Field(description="Unique device identifier")
    name: str = Field(description="Human-readable device name")
    manufacturer: str = Field(description="Device manufacturer")
    model: str = Field(description="Device model number/name")
    category: str = Field(default="other", description="Device category")
    specifications: Dict[str, Any] = Field(
        default_factory=dict, description="Technical specifications"
    )
    qr_codes: List[str] = Field(
        default_factory=list, description="Associated QR code values"
    )
    documentation_urls: List[str] = Field(
        default_factory=list, description="Links to documentation"
    )
    created_at: str = Field(description="ISO-8601 creation timestamp")
    updated_at: str = Field(description="ISO-8601 last-update timestamp")


# ---------------------------------------------------------------------------
# Device database
# ---------------------------------------------------------------------------


class DeviceDatabase:
    """
    Simple JSON-backed device database.

    Stores device records in ``backend/storage/devices/devices.json``.
    All operations are synchronous and load/save the full JSON file on
    each write (suitable for the expected small dataset size).
    """

    def __init__(self, storage_path: Optional[str] = None) -> None:
        if storage_path is None:
            # Default: backend/storage/devices/devices.json
            _backend_dir = Path(__file__).parent.parent
            storage_path = str(_backend_dir / "storage" / "devices" / "devices.json")

        self._path = Path(storage_path)
        self._path.parent.mkdir(parents=True, exist_ok=True)

        # Ensure the file exists with an empty list
        if not self._path.exists():
            self._path.write_text("[]", encoding="utf-8")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _load(self) -> List[Dict[str, Any]]:
        """Load all records from disk."""
        try:
            text = self._path.read_text(encoding="utf-8")
            data = json.loads(text)
            if isinstance(data, list):
                return data
            return []
        except (json.JSONDecodeError, OSError):
            return []

    def _save(self, records: List[Dict[str, Any]]) -> None:
        """Persist all records to disk."""
        self._path.write_text(
            json.dumps(records, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    @staticmethod
    def _now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()

    # ------------------------------------------------------------------
    # CRUD operations
    # ------------------------------------------------------------------

    def create(
        self,
        name: str,
        manufacturer: str,
        model: str,
        category: str = "other",
        specifications: Optional[Dict[str, Any]] = None,
        qr_codes: Optional[List[str]] = None,
        documentation_urls: Optional[List[str]] = None,
    ) -> DeviceRecord:
        """Create a new device record and persist it."""
        now = self._now_iso()
        record = DeviceRecord(
            id=str(uuid4()),
            name=name,
            manufacturer=manufacturer,
            model=model,
            category=category,
            specifications=specifications or {},
            qr_codes=qr_codes or [],
            documentation_urls=documentation_urls or [],
            created_at=now,
            updated_at=now,
        )
        records = self._load()
        records.append(record.model_dump())
        self._save(records)
        return record

    def get(self, device_id: str) -> Optional[DeviceRecord]:
        """Return a device by ID, or None if not found."""
        for raw in self._load():
            if raw.get("id") == device_id:
                return DeviceRecord(**raw)
        return None

    def list_all(self) -> List[DeviceRecord]:
        """Return all device records."""
        return [DeviceRecord(**raw) for raw in self._load()]

    def update(
        self,
        device_id: str,
        name: Optional[str] = None,
        manufacturer: Optional[str] = None,
        model: Optional[str] = None,
        category: Optional[str] = None,
        specifications: Optional[Dict[str, Any]] = None,
        qr_codes: Optional[List[str]] = None,
        documentation_urls: Optional[List[str]] = None,
    ) -> Optional[DeviceRecord]:
        """Update an existing device record. Returns None if not found."""
        records = self._load()
        for i, raw in enumerate(records):
            if raw.get("id") == device_id:
                if name is not None:
                    raw["name"] = name
                if manufacturer is not None:
                    raw["manufacturer"] = manufacturer
                if model is not None:
                    raw["model"] = model
                if category is not None:
                    raw["category"] = category
                if specifications is not None:
                    raw["specifications"] = specifications
                if qr_codes is not None:
                    raw["qr_codes"] = qr_codes
                if documentation_urls is not None:
                    raw["documentation_urls"] = documentation_urls
                raw["updated_at"] = self._now_iso()
                records[i] = raw
                self._save(records)
                return DeviceRecord(**raw)
        return None

    def delete(self, device_id: str) -> bool:
        """Delete a device by ID. Returns True if deleted, False if not found."""
        records = self._load()
        new_records = [r for r in records if r.get("id") != device_id]
        if len(new_records) == len(records):
            return False
        self._save(new_records)
        return True

    def search(self, query: str) -> List[DeviceRecord]:
        """
        Search devices by name, manufacturer, or model (case-insensitive substring).
        """
        q = query.lower().strip()
        if not q:
            return self.list_all()

        results: List[DeviceRecord] = []
        for raw in self._load():
            if (
                q in raw.get("name", "").lower()
                or q in raw.get("manufacturer", "").lower()
                or q in raw.get("model", "").lower()
                or q in raw.get("category", "").lower()
            ):
                results.append(DeviceRecord(**raw))
        return results

    def find_by_qr_code(self, qr_content: str) -> Optional[DeviceRecord]:
        """
        Find a device whose qr_codes list contains the given QR content.

        Used by Requirement 2.3 to automatically retrieve documentation
        when a QR code contains device identification data.
        """
        for raw in self._load():
            if qr_content in raw.get("qr_codes", []):
                return DeviceRecord(**raw)
        return None


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_device_db: Optional[DeviceDatabase] = None


def get_device_database() -> DeviceDatabase:
    """Return the module-level DeviceDatabase singleton."""
    global _device_db
    if _device_db is None:
        _device_db = DeviceDatabase()
    return _device_db
