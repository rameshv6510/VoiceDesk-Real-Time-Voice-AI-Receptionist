"""Appointment management tools and function handlers for Pipecat LLM."""
from typing import Dict, Any, List
from loguru import logger
from pipecat.services.llm_service import FunctionCallParams
from app.db import repository

# Tool JSON schemas in standard OpenAI function format
APPOINTMENT_TOOLS: List[Dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "check_availability",
            "description": "Check available time slots for a doctor on a given date (YYYY-MM-DD). Use this when the caller asks what times are open or wants to schedule on a certain day.",
            "parameters": {
                "type": "object",
                "properties": {
                    "doctor_id": {
                        "type": "string",
                        "description": "Doctor ID (e.g. 'dr_ananya', 'dr_vikram') or full doctor name."
                    },
                    "date": {
                        "type": "string",
                        "description": "Appointment date in YYYY-MM-DD format (e.g. '2026-10-15')."
                    }
                },
                "required": ["doctor_id", "date"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "book_appointment",
            "description": "Books a confirmed appointment after the caller agrees to the date, time, and service. NEVER call this until the caller confirms the details.",
            "parameters": {
                "type": "object",
                "properties": {
                    "patient_name": {
                        "type": "string",
                        "description": "Caller / patient's full name."
                    },
                    "phone": {
                        "type": "string",
                        "description": "Caller's 10-digit mobile phone number."
                    },
                    "doctor_id": {
                        "type": "string",
                        "description": "Doctor ID (e.g. 'dr_ananya', 'dr_vikram') or doctor name."
                    },
                    "service_id": {
                        "type": "string",
                        "description": "Service ID (e.g. 'general_checkup', 'cleaning', 'root_canal_consult') or service name."
                    },
                    "date": {
                        "type": "string",
                        "description": "Appointment date in YYYY-MM-DD format."
                    },
                    "time_slot": {
                        "type": "string",
                        "description": "Confirmed time slot in HH:MM 24hr format (e.g. '10:00', '14:30')."
                    },
                    "notes": {
                        "type": "string",
                        "description": "Optional notes or chief complaint (non-medical, e.g. routine checkup)."
                    }
                },
                "required": ["patient_name", "phone", "doctor_id", "service_id", "date", "time_slot"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "reschedule_appointment",
            "description": "Reschedules an existing confirmed appointment to a new date and time.",
            "parameters": {
                "type": "object",
                "properties": {
                    "appointment_id": {
                        "type": "string",
                        "description": "The appointment ID (e.g. 'APT-1A2B3C')."
                    },
                    "new_date": {
                        "type": "string",
                        "description": "The new desired date in YYYY-MM-DD format."
                    },
                    "new_time": {
                        "type": "string",
                        "description": "The new desired time slot in HH:MM format."
                    }
                },
                "required": ["appointment_id", "new_date", "new_time"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "cancel_appointment",
            "description": "Cancels an existing appointment.",
            "parameters": {
                "type": "object",
                "properties": {
                    "appointment_id": {
                        "type": "string",
                        "description": "The appointment ID to cancel."
                    },
                    "phone": {
                        "type": "string",
                        "description": "The caller's phone number for verification (optional)."
                    }
                },
                "required": ["appointment_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_appointment_details",
            "description": "Look up an existing appointment status and details by appointment ID (e.g. 'APT-685915' or digits '685915') or caller's registered phone number.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Appointment ID, confirmation code, or phone number to look up."
                    }
                },
                "required": ["query"]
            }
        }
    }
]

# Business logic execution helpers (directly testable)
async def execute_check_availability(doctor_id: str, date: str) -> Dict[str, Any]:
    return repository.get_available_slots(doctor_id, date)

async def execute_book_appointment(
    patient_name: str,
    phone: str,
    doctor_id: str,
    service_id: str,
    date: str,
    time_slot: str,
    notes: str = ""
) -> Dict[str, Any]:
    return repository.create_appointment(
        patient_name=patient_name,
        phone=phone,
        doctor_id=doctor_id,
        service_id=service_id,
        date=date,
        time_slot=time_slot,
        notes=notes
    )

async def execute_reschedule_appointment(appointment_id: str, new_date: str, new_time: str) -> Dict[str, Any]:
    return repository.reschedule_appointment(appointment_id, new_date, new_time)

async def execute_cancel_appointment(appointment_id: str, phone: str = "") -> Dict[str, Any]:
    return repository.cancel_appointment(appointment_id, phone if phone else None)

async def execute_get_appointment_details(query: str) -> Dict[str, Any]:
    return repository.get_appointment_details(query)

# Pipecat Function Call Handlers
async def handle_check_availability(params: FunctionCallParams):
    args = params.arguments
    doc_id = args.get("doctor_id", "")
    date_val = args.get("date", "")
    logger.info(f"Tool check_availability called for doctor={doc_id}, date={date_val}")
    res = await execute_check_availability(doc_id, date_val)
    await params.result_callback(res)

async def handle_book_appointment(params: FunctionCallParams):
    args = params.arguments
    logger.info(f"Tool book_appointment called with args: {args}")
    res = await execute_book_appointment(
        patient_name=args.get("patient_name", ""),
        phone=args.get("phone", ""),
        doctor_id=args.get("doctor_id", ""),
        service_id=args.get("service_id", ""),
        date=args.get("date", ""),
        time_slot=args.get("time_slot", ""),
        notes=args.get("notes", "")
    )
    await params.result_callback(res)

async def handle_reschedule_appointment(params: FunctionCallParams):
    args = params.arguments
    logger.info(f"Tool reschedule_appointment called: {args}")
    res = await execute_reschedule_appointment(
        appointment_id=args.get("appointment_id", ""),
        new_date=args.get("new_date", ""),
        new_time=args.get("new_time", "")
    )
    await params.result_callback(res)

async def handle_cancel_appointment(params: FunctionCallParams):
    args = params.arguments
    logger.info(f"Tool cancel_appointment called: {args}")
    res = await execute_cancel_appointment(
        appointment_id=args.get("appointment_id", ""),
        phone=args.get("phone", "")
    )
    await params.result_callback(res)

async def handle_get_appointment_details(params: FunctionCallParams):
    args = params.arguments
    query = args.get("query", "")
    logger.info(f"Tool get_appointment_details called for query: {query}")
    res = await execute_get_appointment_details(query)
    await params.result_callback(res)

def register_appointment_tools(llm_service):
    """Registers all appointment booking function handlers on the Pipecat LLM service."""
    llm_service.register_function("check_availability", handle_check_availability)
    llm_service.register_function("book_appointment", handle_book_appointment)
    llm_service.register_function("reschedule_appointment", handle_reschedule_appointment)
    llm_service.register_function("cancel_appointment", handle_cancel_appointment)
    llm_service.register_function("get_appointment_details", handle_get_appointment_details)
    logger.info("Registered appointment tools on LLM service.")
