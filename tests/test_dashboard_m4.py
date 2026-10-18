"""Unit tests for Milestone 4: Dashboard operations and data loaders."""
import pytest
from app.db import (
    seed_clinic_data_if_needed,
    get_doctors,
    get_services,
    list_appointments,
    list_call_logs,
    log_call,
    create_appointment
)

def test_dashboard_data_loaders(tmp_path, monkeypatch):
    from app.db import database
    test_db = tmp_path / "test_dash.db"
    monkeypatch.setattr(database.settings, "DATABASE_URL", f"sqlite:///{test_db}")
    seed_clinic_data_if_needed()

    # Verify doctors and services
    docs = get_doctors()
    services = get_services()
    assert len(docs) >= 2
    assert len(services) >= 3

    # Log a test call and check retrieval
    log_id = log_call(
        session_id="session_dash_1",
        caller_phone="9876543210",
        summary="Test call summary for dashboard",
        turn_count=3,
        avg_latency_ms=412.5
    )
    assert log_id.startswith("CALL-")

    logs = list_call_logs(limit=10)
    assert len(logs) >= 1
    assert logs[0]["session_id"] == "session_dash_1"
    assert logs[0]["avg_latency_ms"] == 412.5

    # Book an appointment and list
    create_appointment(
        patient_name="Dashboard Test Patient",
        phone="9988776655",
        doctor_id=docs[0]["id"],
        service_id=services[0]["id"],
        date="2026-10-15",
        time_slot="10:00",
        notes="Dashboard test note"
    )

    appts = list_appointments(date_str="2026-10-15")
    assert len(appts) >= 1
    assert appts[0]["patient_name"] == "Dashboard Test Patient"
