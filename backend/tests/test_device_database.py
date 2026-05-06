"""
Unit tests for the device database and new device API endpoints.

Covers Task 5 requirements:
- 1.1-1.4: Device recognition and information retrieval
- 2.1-2.4: QR code scanning and documentation lookup
"""

import sys
import os
import tempfile
import json
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from fastapi.testclient import TestClient

from app.device_database import DeviceDatabase, DeviceRecord


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_db(tmp_path: Path) -> DeviceDatabase:
    """Create a DeviceDatabase backed by a temporary file."""
    storage_file = str(tmp_path / "devices.json")
    return DeviceDatabase(storage_path=storage_file)


# ---------------------------------------------------------------------------
# Unit tests: DeviceDatabase CRUD
# ---------------------------------------------------------------------------


class TestDeviceDatabaseCRUD:
    """Unit tests for DeviceDatabase CRUD operations."""

    def test_create_returns_device_record(self, tmp_path):
        db = make_db(tmp_path)
        record = db.create(name="Arduino Uno", manufacturer="Arduino", model="Uno R3")
        assert isinstance(record, DeviceRecord)
        assert record.name == "Arduino Uno"
        assert record.manufacturer == "Arduino"
        assert record.model == "Uno R3"
        assert record.id  # non-empty UUID

    def test_create_persists_to_disk(self, tmp_path):
        db = make_db(tmp_path)
        record = db.create(name="ESP32", manufacturer="Espressif", model="ESP32-WROOM")
        # Re-open the same file
        db2 = DeviceDatabase(storage_path=str(tmp_path / "devices.json"))
        fetched = db2.get(record.id)
        assert fetched is not None
        assert fetched.name == "ESP32"

    def test_get_returns_none_for_missing_id(self, tmp_path):
        db = make_db(tmp_path)
        assert db.get("nonexistent-id") is None

    def test_get_returns_correct_record(self, tmp_path):
        db = make_db(tmp_path)
        r1 = db.create(name="Device A", manufacturer="Mfr A", model="Model A")
        r2 = db.create(name="Device B", manufacturer="Mfr B", model="Model B")
        fetched = db.get(r1.id)
        assert fetched is not None
        assert fetched.id == r1.id
        assert fetched.name == "Device A"

    def test_list_all_returns_all_records(self, tmp_path):
        db = make_db(tmp_path)
        db.create(name="D1", manufacturer="M1", model="M1")
        db.create(name="D2", manufacturer="M2", model="M2")
        db.create(name="D3", manufacturer="M3", model="M3")
        records = db.list_all()
        assert len(records) == 3

    def test_list_all_empty_database(self, tmp_path):
        db = make_db(tmp_path)
        assert db.list_all() == []

    def test_update_modifies_fields(self, tmp_path):
        db = make_db(tmp_path)
        record = db.create(name="Old Name", manufacturer="Mfr", model="Model")
        updated = db.update(record.id, name="New Name", category="electronics")
        assert updated is not None
        assert updated.name == "New Name"
        assert updated.category == "electronics"
        # Unchanged fields stay the same
        assert updated.manufacturer == "Mfr"

    def test_update_returns_none_for_missing_id(self, tmp_path):
        db = make_db(tmp_path)
        result = db.update("nonexistent", name="X")
        assert result is None

    def test_update_persists_changes(self, tmp_path):
        db = make_db(tmp_path)
        record = db.create(name="Original", manufacturer="Mfr", model="Model")
        db.update(record.id, name="Updated")
        db2 = DeviceDatabase(storage_path=str(tmp_path / "devices.json"))
        fetched = db2.get(record.id)
        assert fetched is not None
        assert fetched.name == "Updated"

    def test_delete_removes_record(self, tmp_path):
        db = make_db(tmp_path)
        record = db.create(name="ToDelete", manufacturer="Mfr", model="Model")
        deleted = db.delete(record.id)
        assert deleted is True
        assert db.get(record.id) is None

    def test_delete_returns_false_for_missing_id(self, tmp_path):
        db = make_db(tmp_path)
        assert db.delete("nonexistent") is False

    def test_delete_does_not_affect_other_records(self, tmp_path):
        db = make_db(tmp_path)
        r1 = db.create(name="Keep", manufacturer="Mfr", model="Model")
        r2 = db.create(name="Delete", manufacturer="Mfr", model="Model")
        db.delete(r2.id)
        assert db.get(r1.id) is not None
        assert len(db.list_all()) == 1

    def test_create_with_qr_codes_and_docs(self, tmp_path):
        db = make_db(tmp_path)
        record = db.create(
            name="Device",
            manufacturer="Mfr",
            model="Model",
            qr_codes=["QR123", "QR456"],
            documentation_urls=["https://example.com/docs"],
        )
        assert record.qr_codes == ["QR123", "QR456"]
        assert record.documentation_urls == ["https://example.com/docs"]

    def test_create_with_specifications(self, tmp_path):
        db = make_db(tmp_path)
        specs = {"voltage": "5V", "current": "500mA"}
        record = db.create(
            name="Device", manufacturer="Mfr", model="Model", specifications=specs
        )
        assert record.specifications == specs


# ---------------------------------------------------------------------------
# Unit tests: DeviceDatabase search
# ---------------------------------------------------------------------------


class TestDeviceDatabaseSearch:
    """Unit tests for DeviceDatabase search functionality."""

    def test_search_by_name(self, tmp_path):
        db = make_db(tmp_path)
        db.create(name="Arduino Uno", manufacturer="Arduino", model="Uno R3")
        db.create(name="Raspberry Pi", manufacturer="RPi Foundation", model="Pi 4")
        results = db.search("arduino")
        assert len(results) == 1
        assert results[0].name == "Arduino Uno"

    def test_search_by_manufacturer(self, tmp_path):
        db = make_db(tmp_path)
        db.create(name="ESP32", manufacturer="Espressif", model="ESP32-WROOM")
        db.create(name="Arduino", manufacturer="Arduino", model="Uno")
        results = db.search("espressif")
        assert len(results) == 1
        assert results[0].manufacturer == "Espressif"

    def test_search_by_model(self, tmp_path):
        db = make_db(tmp_path)
        db.create(name="Device", manufacturer="Mfr", model="NUCLEO-F401RE")
        results = db.search("nucleo")
        assert len(results) == 1

    def test_search_case_insensitive(self, tmp_path):
        db = make_db(tmp_path)
        db.create(name="Arduino Uno", manufacturer="Arduino", model="Uno R3")
        assert len(db.search("ARDUINO")) == 1
        assert len(db.search("arduino")) == 1
        assert len(db.search("Arduino")) == 1

    def test_search_empty_query_returns_all(self, tmp_path):
        db = make_db(tmp_path)
        db.create(name="D1", manufacturer="M1", model="M1")
        db.create(name="D2", manufacturer="M2", model="M2")
        results = db.search("")
        assert len(results) == 2

    def test_search_no_match_returns_empty(self, tmp_path):
        db = make_db(tmp_path)
        db.create(name="Arduino", manufacturer="Arduino", model="Uno")
        results = db.search("zyxwvuts")
        assert results == []

    def test_search_multiple_matches(self, tmp_path):
        db = make_db(tmp_path)
        db.create(name="Arduino Uno", manufacturer="Arduino", model="Uno R3")
        db.create(name="Arduino Mega", manufacturer="Arduino", model="Mega 2560")
        results = db.search("arduino")
        assert len(results) == 2


# ---------------------------------------------------------------------------
# Unit tests: DeviceDatabase QR code lookup
# ---------------------------------------------------------------------------


class TestDeviceDatabaseQRLookup:
    """Unit tests for QR code-based device lookup (Requirement 2.3)."""

    def test_find_by_qr_code_returns_device(self, tmp_path):
        db = make_db(tmp_path)
        record = db.create(
            name="Arduino Uno",
            manufacturer="Arduino",
            model="Uno R3",
            qr_codes=["https://arduino.cc/en/Main/ArduinoBoardUno"],
        )
        found = db.find_by_qr_code("https://arduino.cc/en/Main/ArduinoBoardUno")
        assert found is not None
        assert found.id == record.id

    def test_find_by_qr_code_returns_none_when_not_found(self, tmp_path):
        db = make_db(tmp_path)
        db.create(name="Device", manufacturer="Mfr", model="Model", qr_codes=["QR1"])
        assert db.find_by_qr_code("UNKNOWN_QR") is None

    def test_find_by_qr_code_exact_match(self, tmp_path):
        db = make_db(tmp_path)
        db.create(name="D1", manufacturer="M1", model="M1", qr_codes=["QR_EXACT"])
        db.create(name="D2", manufacturer="M2", model="M2", qr_codes=["QR_OTHER"])
        found = db.find_by_qr_code("QR_EXACT")
        assert found is not None
        assert found.name == "D1"

    def test_find_by_qr_code_device_format(self, tmp_path):
        db = make_db(tmp_path)
        record = db.create(
            name="STM32 Nucleo",
            manufacturer="STMicroelectronics",
            model="NUCLEO-F401RE",
            qr_codes=["DEVICE:STM32-NUCLEO-F401RE:SN123456"],
            documentation_urls=["https://st.com/nucleo-docs"],
        )
        found = db.find_by_qr_code("DEVICE:STM32-NUCLEO-F401RE:SN123456")
        assert found is not None
        assert found.documentation_urls == ["https://st.com/nucleo-docs"]


# ---------------------------------------------------------------------------
# API endpoint tests
# ---------------------------------------------------------------------------


@pytest.fixture
def client(tmp_path):
    """Create a TestClient with a temporary device database."""
    # Patch the get_device_database dependency to use a temp file
    from app.main import app
    from app.device_database import DeviceDatabase

    test_db = DeviceDatabase(storage_path=str(tmp_path / "test_devices.json"))

    app.dependency_overrides[
        __import__("app.device_database", fromlist=["get_device_database"]).get_device_database
    ] = lambda: test_db

    with TestClient(app) as c:
        yield c

    app.dependency_overrides.clear()


class TestDeviceAPIEndpoints:
    """Integration tests for device database API endpoints."""

    def test_list_devices_empty(self, client):
        response = client.get("/devices")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert data["devices"] == []

    def test_create_device(self, client):
        payload = {
            "name": "Arduino Uno",
            "manufacturer": "Arduino",
            "model": "Uno R3",
            "category": "microcontroller",
            "specifications": {"voltage": "5V"},
            "qr_codes": [],
            "documentation_urls": [],
        }
        response = client.post("/devices", json=payload)
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Arduino Uno"
        assert data["manufacturer"] == "Arduino"
        assert "id" in data
        assert "created_at" in data

    def test_get_device_by_id(self, client):
        # Create first
        payload = {"name": "ESP32", "manufacturer": "Espressif", "model": "ESP32-WROOM"}
        create_resp = client.post("/devices", json=payload)
        device_id = create_resp.json()["id"]

        # Then get
        response = client.get(f"/devices/{device_id}")
        assert response.status_code == 200
        assert response.json()["id"] == device_id

    def test_get_device_not_found(self, client):
        response = client.get("/devices/nonexistent-id")
        assert response.status_code == 404

    def test_list_devices_after_create(self, client):
        client.post("/devices", json={"name": "D1", "manufacturer": "M1", "model": "M1"})
        client.post("/devices", json={"name": "D2", "manufacturer": "M2", "model": "M2"})
        response = client.get("/devices")
        assert response.status_code == 200
        assert response.json()["total"] == 2

    def test_update_device(self, client):
        create_resp = client.post(
            "/devices", json={"name": "Old", "manufacturer": "Mfr", "model": "Model"}
        )
        device_id = create_resp.json()["id"]

        update_resp = client.put(f"/devices/{device_id}", json={"name": "New"})
        assert update_resp.status_code == 200
        assert update_resp.json()["name"] == "New"
        # Unchanged fields preserved
        assert update_resp.json()["manufacturer"] == "Mfr"

    def test_update_device_not_found(self, client):
        response = client.put("/devices/nonexistent", json={"name": "X"})
        assert response.status_code == 404

    def test_delete_device(self, client):
        create_resp = client.post(
            "/devices", json={"name": "ToDelete", "manufacturer": "Mfr", "model": "Model"}
        )
        device_id = create_resp.json()["id"]

        del_resp = client.delete(f"/devices/{device_id}")
        assert del_resp.status_code == 204

        get_resp = client.get(f"/devices/{device_id}")
        assert get_resp.status_code == 404

    def test_delete_device_not_found(self, client):
        response = client.delete("/devices/nonexistent")
        assert response.status_code == 404

    def test_search_devices(self, client):
        client.post("/devices", json={"name": "Arduino Uno", "manufacturer": "Arduino", "model": "Uno R3"})
        client.post("/devices", json={"name": "Raspberry Pi", "manufacturer": "RPi Foundation", "model": "Pi 4"})

        response = client.get("/devices/search?q=arduino")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["devices"][0]["name"] == "Arduino Uno"

    def test_search_devices_empty_query_returns_all(self, client):
        client.post("/devices", json={"name": "D1", "manufacturer": "M1", "model": "M1"})
        client.post("/devices", json={"name": "D2", "manufacturer": "M2", "model": "M2"})

        response = client.get("/devices/search?q=")
        assert response.status_code == 200
        assert response.json()["total"] == 2

    def test_search_devices_no_match(self, client):
        client.post("/devices", json={"name": "Arduino", "manufacturer": "Arduino", "model": "Uno"})
        response = client.get("/devices/search?q=zyxwvuts")
        assert response.status_code == 200
        assert response.json()["total"] == 0

