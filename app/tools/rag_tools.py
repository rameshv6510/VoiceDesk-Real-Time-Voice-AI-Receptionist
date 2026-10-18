"""RAG knowledge lookup tool for Pipecat LLM."""
from typing import Dict, Any, List
from loguru import logger
from pipecat.services.llm_service import FunctionCallParams
from app.rag import query_knowledge_base, format_knowledge_context

RAG_TOOLS: List[Dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "lookup_clinic_info",
            "description": "Searches the clinic knowledge base for detailed FAQs, pre/post-procedure care, insurance networks, parking, and clinic policies. Use this when a caller asks a specific question about treatment care, insurance, or clinic facilities.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search topic or question (e.g. 'root canal care', 'insurance cashless', 'parking')."
                    }
                },
                "required": ["query"]
            }
        }
    }
]

async def execute_lookup_clinic_info(query: str) -> Dict[str, Any]:
    context = format_knowledge_context(query, n_results=2)
    return {
        "success": True,
        "query": query,
        "information": context
    }

async def handle_lookup_clinic_info(params: FunctionCallParams):
    args = params.arguments
    query = args.get("query", "")
    logger.info(f"Tool lookup_clinic_info called for query='{query}'")
    res = await execute_lookup_clinic_info(query)
    await params.result_callback(res)

def register_rag_tools(llm_service):
    llm_service.register_function("lookup_clinic_info", handle_lookup_clinic_info)
    logger.info("Registered RAG tools on LLM service.")
