"""Database package initialization."""
from app.db.database import get_db_connection, init_db, get_db_path
from app.db.repository import (
    seed_clinic_data_if_needed,
    get_doctors,
    get_services,
    get_available_slots,
    create_appointment,
    get_appointment,
    cancel_appointment,
    reschedule_appointment,
    list_appointments,
    log_call,
    list_call_logs,
)
