"""Unit tests for Milestone 2: SQLite database, slot generation, and appointment booking tools."""
import pytest
import os
from pathlib import Path

from app.db import database, repository
from app.tools.appointment_tools import (
    APPOINTMENT_TOOLS,
    execute_check_availability,
    execute_book_appointment,
    execute_reschedule_appointment,
    execute_cancel_appointment
)

@pytest.fixture(autouse=True)
def setup_test_db(tmp_path, monkeypatch):
    """Use a temporary database for test isolation."""
    test_db = tmp_path / "test_voicedesk.db"
    monkeypatch.setattr(database.settings, "DATABASE_URL", f"sqlite:///{test_db}")
    repository.seed_clinic_data_if_needed()
    yield

def test_database_seeding():
    docs = repository.get_doctors()
    services = repository.get_services()
    assert len(docs) >= 2
    assert len(services) >= 3
    doctor_names = [d["name"] for d in docs]
    assert "Dr. Ananya Rao" in doctor_names
    assert "Dr. Vikram Hegde" in doctor_names

def test_available_slots_weekday():
    # 2026-10-14 is Wednesday
    slots_res = repository.get_available_slots("dr_ananya", "2026-10-14")
    assert slots_res["success"] is True
    assert len(slots_res["available_slots"]) > 0
    assert "09:00" in slots_res["available_slots"]
    assert "10:00" in slots_res["available_slots"]

def test_sunday_closed():
    # 2026-10-18 is Sunday
    slots_res = repository.get_available_slots("dr_ananya", "2026-10-18")
    assert slots_res["success"] is True
    assert len(slots_res["available_slots"]) == 0
    assert "closed" in slots_res["message"].lower()

def test_holiday_closed():
    # 2026-10-20 is in clinic.yaml holidays
    slots_res = repository.get_available_slots("dr_ananya", "2026-10-20")
    assert slots_res["success"] is True
    assert len(slots_res["available_slots"]) == 0
    assert "holiday" in slots_res["message"].lower()

@pytest.mark.asyncio
async def test_appointment_booking_and_double_booking():
    # 1. Book first appointment
    res1 = await execute_book_appointment(
        patient_name="Rahul Sharma",
        phone="9876543210",
        doctor_id="dr_ananya",
        service_id="general_checkup",
        date="2026-10-14",
        time_slot="10:00"
    )
    assert res1["success"] is True
    appt_id = res1["appointment_id"]
    assert appt_id.startswith("APT-")
    assert res1["patient_name"] == "Rahul Sharma"

    # 2. Attempt double-booking on same slot
    res2 = await execute_book_appointment(
        patient_name="Priya Patel",
        phone="9876500000",
        doctor_id="dr_ananya",
        service_id="cleaning",
        date="2026-10-14",
        time_slot="10:00"
    )
    assert res2["success"] is False
    assert "not available" in res2["error"]

@pytest.mark.asyncio
async def test_appointment_cancellation():
    book_res = await execute_book_appointment(
        patient_name="Aarav Gupta",
        phone="9123456789",
        doctor_id="dr_vikram",
        service_id="root_canal_consult",
        date="2026-10-15",
        time_slot="11:30"
    )
    appt_id = book_res["appointment_id"]

    # Cancel
    cancel_res = await execute_cancel_appointment(appt_id, phone="9123456789")
    assert cancel_res["success"] is True
    assert cancel_res["status"] == "cancelled"

    # Slot should now be available again
    slots_res = await execute_check_availability("dr_vikram", "2026-10-15")
    assert "11:30" in slots_res["available_slots"]

@pytest.mark.asyncio
async def test_appointment_rescheduling():
    book_res = await execute_book_appointment(
        patient_name="Sneha Sen",
        phone="9988776655",
        doctor_id="dr_ananya",
        service_id="general_checkup",
        date="2026-10-16",
        time_slot="14:00"
    )
    appt_id = book_res["appointment_id"]

    # Reschedule to 15:00
    resched_res = await execute_reschedule_appointment(appt_id, new_date="2026-10-16", new_time="15:00")
    assert resched_res["success"] is True
    assert resched_res["new_time"] == "15:00"

    appt = repository.get_appointment(appt_id)
    assert appt["time_slot"] == "15:00"

def test_tool_schemas():
    tool_names = [t["function"]["name"] for t in APPOINTMENT_TOOLS]
    assert "check_availability" in tool_names
    assert "book_appointment" in tool_names
    assert "reschedule_appointment" in tool_names
    assert "cancel_appointment" in tool_names
