"""Data access repository for doctors, services, appointments, and call logs."""
import uuid
import re
import difflib
from datetime import datetime, time, timedelta
from typing import Dict, Any, List, Optional
from loguru import logger

from app.db.database import get_db_connection, init_db
from app.config import clinic_config

def seed_clinic_data_if_needed():
    """Seeds doctors and services from clinic_config YAML if the database is newly created."""
    init_db()
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # Check doctors
        cursor.execute("SELECT COUNT(*) as count FROM doctors")
        if cursor.fetchone()["count"] == 0:
            doctors = clinic_config.get("doctors", [])
            for doc in doctors:
                cursor.execute(
                    "INSERT INTO doctors (id, name, specialization) VALUES (?, ?, ?)",
                    (doc["id"], doc["name"], doc["specialization"])
                )
            logger.info(f"Seeded {len(doctors)} doctors.")

        # Check services
        cursor.execute("SELECT COUNT(*) as count FROM services")
        if cursor.fetchone()["count"] == 0:
            services = clinic_config.get("services", [])
            for s in services:
                cursor.execute(
                    "INSERT INTO services (id, name, duration_minutes, price_inr, doctor_id) VALUES (?, ?, ?, ?, ?)",
                    (s["id"], s["name"], s["duration_minutes"], s.get("price_inr", 0), s.get("doctor_id"))
                )
            logger.info(f"Seeded {len(services)} services.")

def get_doctors() -> List[Dict[str, Any]]:
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM doctors")
        return [dict(row) for row in cursor.fetchall()]

def get_services() -> List[Dict[str, Any]]:
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM services")
        return [dict(row) for row in cursor.fetchall()]

def get_doctor_by_id(doctor_id: str) -> Optional[Dict[str, Any]]:
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM doctors WHERE id = ? OR name LIKE ?", (doctor_id, f"%{doctor_id}%"))
        row = cursor.fetchone()
        return dict(row) if row else None

def get_service_by_id(service_id: str) -> Optional[Dict[str, Any]]:
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM services WHERE id = ? OR name LIKE ?", (service_id, f"%{service_id}%"))
        row = cursor.fetchone()
        return dict(row) if row else None

def get_available_slots(doctor_id: str, date_str: str) -> Dict[str, Any]:
    """
    Returns available time slots for a doctor on a specific date (YYYY-MM-DD).
    Respects clinic working hours, holidays, and already confirmed appointments.
    """
    try:
        req_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        return {"success": False, "error": f"Invalid date format: {date_str}. Expected YYYY-MM-DD."}

    # Check holidays
    holidays = clinic_config.get("clinic", {}).get("holidays", [])
    if date_str in holidays:
        return {"success": True, "date": date_str, "available_slots": [], "message": "Clinic is closed for a scheduled holiday."}

    # Check day of week
    day_name = req_date.strftime("%A").lower()
    working_hours = clinic_config.get("clinic", {}).get("working_hours", {})
    day_schedule = working_hours.get(day_name, {})

    if day_schedule.get("closed", False) or not day_schedule:
        return {"success": True, "date": date_str, "available_slots": [], "message": f"Clinic is closed on {req_date.strftime('%A')}s."}

    open_str = day_schedule.get("open", "09:00")
    close_str = day_schedule.get("close", "18:00")
    
    start_time = datetime.strptime(open_str, "%H:%M").time()
    end_time = datetime.strptime(close_str, "%H:%M").time()

    # Generate 30-minute standard slot intervals
    all_slots = []
    curr = datetime.combine(req_date, start_time)
    end_dt = datetime.combine(req_date, end_time)
    while curr + timedelta(minutes=30) <= end_dt:
        all_slots.append(curr.strftime("%H:%M"))
        curr += timedelta(minutes=30)

    # Fetch booked slots for the doctor on this date
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT time_slot FROM appointments 
            WHERE doctor_id = ? AND date = ? AND status = 'confirmed'
        """, (doctor_id, date_str))
        booked_slots = {row["time_slot"] for row in cursor.fetchall()}

    available = [slot for slot in all_slots if slot not in booked_slots]

    return {
        "success": True,
        "date": date_str,
        "doctor_id": doctor_id,
        "total_slots": len(all_slots),
        "available_slots": available,
        "booked_slots": list(booked_slots)
    }

def create_appointment(
    patient_name: str,
    phone: str,
    doctor_id: str,
    service_id: str,
    date: str,
    time_slot: str,
    notes: str = ""
) -> Dict[str, Any]:
    """Books a new appointment if the slot is open."""
    # Ensure doctor and service exist or resolve fuzzy
    doc = get_doctor_by_id(doctor_id)
    if not doc:
        # Default to first doctor if unspecified
        doctors = get_doctors()
        doc = doctors[0] if doctors else {"id": doctor_id, "name": doctor_id}

    srv = get_service_by_id(service_id)
    if not srv:
        services = get_services()
        srv = services[0] if services else {"id": service_id, "name": service_id, "price_inr": 500}

    # Verify slot availability
    slot_check = get_available_slots(doc["id"], date)
    if not slot_check.get("success"):
        return slot_check
    if time_slot not in slot_check.get("available_slots", []):
        return {
            "success": False,
            "error": f"Time slot {time_slot} is not available on {date} for {doc['name']}. Available slots: {slot_check.get('available_slots', [])[:4]}"
        }

    appointment_id = f"APT-{uuid.uuid4().hex[:6].upper()}"

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO appointments (id, patient_name, phone, doctor_id, service_id, date, time_slot, status, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'confirmed', ?)
        """, (appointment_id, patient_name, phone, doc["id"], srv["id"], date, time_slot, notes))

    logger.info(f"Booked appointment {appointment_id} for {patient_name} on {date} at {time_slot}")

    return {
        "success": True,
        "appointment_id": appointment_id,
        "patient_name": patient_name,
        "phone": phone,
        "doctor": doc["name"],
        "doctor_id": doc["id"],
        "service": srv["name"],
        "service_id": srv["id"],
        "price_inr": srv.get("price_inr", 0),
        "date": date,
        "time_slot": time_slot,
        "status": "confirmed",
        "message": f"Appointment {appointment_id} confirmed for {patient_name} with {doc['name']} on {date} at {time_slot}."
    }

def get_appointment(appointment_id_or_query: str, phone: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Smart appointment lookup supporting exact ID, digits only (e.g. '685915'), 
    fuzzy/typo matching (e.g. '6850915' -> 'APT-685915'), and phone search."""
    if not appointment_id_or_query:
        return None
    
    clean_query = appointment_id_or_query.strip().upper()
    digits_only = re.sub(r'[^0-9]', '', clean_query)
    alnum_only = re.sub(r'[^A-Z0-9]', '', clean_query)

    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # 1. Exact match
        cursor.execute("""
            SELECT a.*, d.name as doctor_name, s.name as service_name, s.price_inr
            FROM appointments a
            LEFT JOIN doctors d ON a.doctor_id = d.id
            LEFT JOIN services s ON a.service_id = s.id
            WHERE a.id = ?
        """, (appointment_id_or_query.strip(),))
        row = cursor.fetchone()
        if row:
            return dict(row)

        # 2. Match with "APT-" prefix added (e.g. "685915" -> "APT-685915")
        cursor.execute("""
            SELECT a.*, d.name as doctor_name, s.name as service_name, s.price_inr
            FROM appointments a
            LEFT JOIN doctors d ON a.doctor_id = d.id
            LEFT JOIN services s ON a.service_id = s.id
            WHERE a.id = ? OR a.id = ?
        """, (f"APT-{alnum_only}", f"APT-{clean_query}"))
        row = cursor.fetchone()
        if row:
            return dict(row)

        # 3. Match by phone number if query is >= 7 digits or phone provided
        search_phone = phone or (digits_only if len(digits_only) >= 7 else None)
        if search_phone:
            cursor.execute("""
                SELECT a.*, d.name as doctor_name, s.name as service_name, s.price_inr
                FROM appointments a
                LEFT JOIN doctors d ON a.doctor_id = d.id
                LEFT JOIN services s ON a.service_id = s.id
                WHERE a.phone LIKE ?
                ORDER BY a.created_at DESC LIMIT 1
            """, (f"%{search_phone}%",))
            row = cursor.fetchone()
            if row:
                return dict(row)

        # 4. Fetch recent appointments and do fuzzy similarity matching
        cursor.execute("""
            SELECT a.*, d.name as doctor_name, s.name as service_name, s.price_inr
            FROM appointments a
            LEFT JOIN doctors d ON a.doctor_id = d.id
            LEFT JOIN services s ON a.service_id = s.id
            ORDER BY a.created_at DESC LIMIT 50
        """)
        all_appts = [dict(r) for r in cursor.fetchall()]

        # Try matching by ID digits or similarity
        best_appt = None
        best_ratio = 0.0
        query_suffix = alnum_only.replace("APT", "")
        for appt in all_appts:
            appt_alnum = re.sub(r'[^A-Z0-9]', '', appt["id"]).upper()
            appt_digits = re.sub(r'[^0-9]', '', appt["id"])
            appt_suffix = appt_alnum.replace("APT", "")
            
            # Substring match (e.g. "685915" in "APT-685915")
            if query_suffix and (query_suffix in appt_suffix or appt_suffix in query_suffix):
                return appt
                
            # SequenceMatcher ratio on query vs ID
            ratio1 = difflib.SequenceMatcher(None, query_suffix, appt_suffix).ratio()
            ratio2 = difflib.SequenceMatcher(None, digits_only, appt_digits).ratio() if digits_only and appt_digits else 0
            ratio = max(ratio1, ratio2)
            if ratio > best_ratio:
                best_ratio = ratio
                best_appt = appt

        # If similarity >= 0.70 (e.g. 6850915 vs 685915 has ratio 0.92)
        if best_ratio >= 0.70 and best_appt:
            logger.info(f"Fuzzy matched appointment '{appointment_id_or_query}' to '{best_appt['id']}' with similarity {best_ratio:.2f}")
            return best_appt

        return None

def get_appointment_details(query: str, phone: Optional[str] = None) -> Dict[str, Any]:
    appt = get_appointment(query, phone=phone)
    if not appt:
        return {"success": False, "error": f"No appointment found matching '{query}'."}
    return {
        "success": True,
        "appointment_id": appt["id"],
        "patient_name": appt["patient_name"],
        "doctor": appt["doctor_name"],
        "date": appt["date"],
        "time_slot": appt["time_slot"],
        "status": appt["status"],
        "message": f"Appointment {appt['id']} for {appt['patient_name']} with {appt['doctor_name']} is {appt['status']} for {appt['date']} at {appt['time_slot']}."
    }

def cancel_appointment(appointment_id: str, phone: Optional[str] = None) -> Dict[str, Any]:
    appt = get_appointment(appointment_id, phone=phone)
    if not appt:
        return {"success": False, "error": f"Appointment {appointment_id} not found."}
    
    real_id = appt["id"]
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE appointments SET status = 'cancelled' WHERE id = ?", (real_id,))

    logger.info(f"Cancelled appointment {real_id}")
    return {
        "success": True,
        "appointment_id": real_id,
        "patient_name": appt.get("patient_name"),
        "status": "cancelled",
        "message": f"Appointment {real_id} for {appt.get('patient_name')} on {appt.get('date')} has been successfully cancelled."
    }

def reschedule_appointment(appointment_id: str, new_date: str, new_time: str) -> Dict[str, Any]:
    appt = get_appointment(appointment_id)
    if not appt:
        return {"success": False, "error": f"Appointment {appointment_id} not found."}

    real_id = appt["id"]
    # Check new slot
    slot_check = get_available_slots(appt["doctor_id"], new_date)
    if not slot_check.get("success"):
        return slot_check
    if new_time not in slot_check.get("available_slots", []):
        return {
            "success": False,
            "error": f"Slot {new_time} on {new_date} is not available. Available slots: {slot_check.get('available_slots', [])[:4]}"
        }

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE appointments 
            SET date = ?, time_slot = ?, status = 'confirmed'
            WHERE id = ?
        """, (new_date, new_time, real_id))

    logger.info(f"Rescheduled appointment {real_id} to {new_date} at {new_time}")
    return {
        "success": True,
        "appointment_id": real_id,
        "patient_name": appt.get("patient_name"),
        "new_date": new_date,
        "new_time": new_time,
        "message": f"Appointment {real_id} rescheduled to {new_date} at {new_time}."
    }

def list_appointments(date_str: Optional[str] = None, doctor_id: Optional[str] = None, status: Optional[str] = None) -> List[Dict[str, Any]]:
    query = """
        SELECT a.*, d.name as doctor_name, s.name as service_name, s.price_inr
        FROM appointments a
        LEFT JOIN doctors d ON a.doctor_id = d.id
        LEFT JOIN services s ON a.service_id = s.id
        WHERE 1=1
    """
    params = []
    if date_str:
        query += " AND a.date = ?"
        params.append(date_str)
    if doctor_id:
        query += " AND a.doctor_id = ?"
        params.append(doctor_id)
    if status:
        query += " AND a.status = ?"
        params.append(status)

    query += " ORDER BY a.date ASC, a.time_slot ASC"

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]

def log_call(session_id: str, caller_phone: str = "", summary: str = "", turn_count: int = 0, avg_latency_ms: float = 0.0) -> str:
    log_id = f"CALL-{uuid.uuid4().hex[:6].upper()}"
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO call_logs (id, session_id, caller_phone, summary, turn_count, avg_latency_ms)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (log_id, session_id, caller_phone, summary, turn_count, avg_latency_ms))
    return log_id

def list_call_logs(limit: int = 50) -> List[Dict[str, Any]]:
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM call_logs ORDER BY created_at DESC LIMIT ?", (limit,))
        return [dict(row) for row in cursor.fetchall()]
