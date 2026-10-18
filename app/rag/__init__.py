"""RAG package initialization."""
from app.rag.vector_store import (
    initialize_knowledge_base,
    query_knowledge_base,
    format_knowledge_context,
    CLINIC_KNOWLEDGE_DOCS
)
