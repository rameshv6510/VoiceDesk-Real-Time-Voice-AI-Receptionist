"""Tools package initialization."""
from app.tools.appointment_tools import (
    APPOINTMENT_TOOLS,
    execute_check_availability,
    execute_book_appointment,
    execute_reschedule_appointment,
    execute_cancel_appointment,
    register_appointment_tools
)
from app.tools.rag_tools import (
    RAG_TOOLS,
    execute_lookup_clinic_info,
    register_rag_tools
)

# Combined tools list for LLM context
ALL_VOICE_TOOLS = APPOINTMENT_TOOLS + RAG_TOOLS

def register_all_tools(llm_service):
    register_appointment_tools(llm_service)
    register_rag_tools(llm_service)
