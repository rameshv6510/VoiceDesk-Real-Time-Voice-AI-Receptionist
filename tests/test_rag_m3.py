"""Unit tests for Milestone 3: ChromaDB vector store and clinic RAG knowledge base."""
import pytest
import os
from pathlib import Path

from app.rag import (
    initialize_knowledge_base,
    query_knowledge_base,
    format_knowledge_context,
    vector_store
)
from app.tools.rag_tools import RAG_TOOLS, execute_lookup_clinic_info

@pytest.fixture(autouse=True)
def setup_test_rag(tmp_path, monkeypatch):
    """Use a temporary Chroma persist dir for test isolation."""
    test_chroma = tmp_path / "test_chroma"
    monkeypatch.setattr(vector_store.settings, "CHROMA_PERSIST_DIR", str(test_chroma))
    initialize_knowledge_base()
    yield

def test_knowledge_base_seeded():
    client = vector_store.get_chroma_client()
    collection = client.get_or_create_collection(vector_store.COLLECTION_NAME)
    count = collection.count()
    assert count >= len(vector_store.CLINIC_KNOWLEDGE_DOCS)

def test_query_post_op_care():
    results = query_knowledge_base("what should I eat after root canal?")
    assert len(results) > 0
    top_doc = results[0]["document"].lower()
    assert "root canal" in top_doc or "care" in top_doc

def test_query_insurance_and_emi():
    results = query_knowledge_base("do you take HDFC insurance or zero cost EMI?")
    assert len(results) > 0
    match_found = any("emi" in r["document"].lower() or "insurance" in r["document"].lower() for r in results)
    assert match_found is True

def test_query_parking():
    results = query_knowledge_base("is there car parking available at the clinic?")
    assert len(results) > 0
    match_found = any("parking" in r["document"].lower() or "metro" in r["document"].lower() for r in results)
    assert match_found is True

def test_format_knowledge_context():
    context = format_knowledge_context("tooth extraction care", n_results=1)
    assert "extraction" in context.lower() or "gauze" in context.lower()

@pytest.mark.asyncio
async def test_rag_tool_execution():
    res = await execute_lookup_clinic_info("cancellation policy")
    assert res["success"] is True
    assert "information" in res
    assert len(res["information"]) > 0

def test_rag_tool_schema():
    assert len(RAG_TOOLS) == 1
    tool = RAG_TOOLS[0]
    assert tool["function"]["name"] == "lookup_clinic_info"
    assert "query" in tool["function"]["parameters"]["properties"]
