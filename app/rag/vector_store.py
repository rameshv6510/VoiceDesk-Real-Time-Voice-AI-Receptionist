"""ChromaDB Vector Store and Clinic Knowledge Base for VoiceDesk."""
import os
from pathlib import Path
from typing import List, Dict, Any, Optional
from loguru import logger
import chromadb
from chromadb.config import Settings as ChromaSettings

from app.config import settings, clinic_config

COLLECTION_NAME = "clinic_knowledge"

def get_chroma_client():
    persist_dir = Path(settings.CHROMA_PERSIST_DIR).resolve()
    persist_dir.mkdir(parents=True, exist_ok=True)
    return chromadb.PersistentClient(
        path=str(persist_dir),
        settings=ChromaSettings(anonymized_telemetry=False)
    )

CLINIC_KNOWLEDGE_DOCS = [
    {
        "id": "faq_toothache_symptoms",
        "category": "clinical_guidance",
        "title": "Tooth Pain, Toothache, and Dental Discomfort (Hallu Novu)",
        "text": "If a patient experiences toothache, tooth pain (hallu novu, daant dard), or chewing sensitivity, advise them to visit SmileCare Dental Clinic as soon as possible. Dr. Ananya Rao or Dr. Vikram Hegde will conduct a clinical examination and X-ray to diagnose the cause (cavity, pulpitis, or infection) and provide pain relief treatment. Consultation fee is INR 500."
    },
    {
        "id": "faq_root_canal_post_care",
        "category": "post_op_care",
        "title": "Root Canal Post-Procedure Care",
        "text": "After a root canal treatment, avoid eating hard, crunchy, or sticky foods until the permanent crown is placed. Mild tenderness is normal for 48-72 hours and can be managed with prescribed pain relievers. If severe swelling occurs, contact the clinic immediately."
    },
    {
        "id": "faq_extraction_post_care",
        "category": "post_op_care",
        "title": "Tooth Extraction Care",
        "text": "Keep the gauze pad in place for 45 minutes with firm pressure. Do not rinse vigorously, spit, drink through a straw, or smoke for 24 hours to prevent dry socket. Eat soft and cold foods like yogurt, ice cream, or khichdi."
    },
    {
        "id": "faq_teeth_whitening",
        "category": "services",
        "title": "Teeth Whitening Procedure & Aftercare",
        "text": "In-clinic professional whitening takes 45 to 60 minutes. Avoid colored liquids like black coffee, tea, red wine, and turmeric-heavy foods for 48 hours following the procedure to ensure optimal results."
    },
    {
        "id": "faq_insurance_emi",
        "category": "billing",
        "title": "Dental Insurance & EMI Options",
        "text": "SmileCare accepts major dental insurance networks including Star Health, Care Health, HDFC ERGO, and Bajaj Allianz. For treatments above INR 5,000, 3-to-12 months zero-cost EMI is available via credit card and Bajaj Finserv."
    },
    {
        "id": "faq_location_parking",
        "category": "facilities",
        "title": "Location, Directions, and Parking",
        "text": "The clinic is located at 102, Indiranagar 100ft Road, Bengaluru, just 200 meters from the Indiranagar Metro Station. Dedicated valet parking for cars and two-wheelers is available free of charge."
    },
    {
        "id": "faq_children_dentistry",
        "category": "services",
        "title": "Pediatric / Children Dentistry",
        "text": "We provide specialized, gentle dental care for children of all ages, including cavity prevention, fluoride treatments, and dental sealants in a friendly, fear-free environment."
    },
    {
        "id": "faq_cancellation_policy",
        "category": "policy",
        "title": "Appointment Rescheduling & Cancellation Policy",
        "text": "Patients may reschedule or cancel appointments at no charge with at least 2 hours advance notice before the scheduled appointment time."
    }
]

def initialize_knowledge_base():
    """Initializes and seeds ChromaDB with clinic FAQs and clinical care documents."""
    client = get_chroma_client()
    collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"description": "SmileCare Dental Clinic Knowledge Base"}
    )

    # Ingest from clinic.yaml FAQs
    yaml_faqs = clinic_config.get("faqs", [])
    all_docs = list(CLINIC_KNOWLEDGE_DOCS)
    
    for idx, faq in enumerate(yaml_faqs):
        all_docs.append({
            "id": f"yaml_faq_{idx}",
            "category": "general_faq",
            "title": faq["question"],
            "text": f"Question: {faq['question']} Answer: {faq['answer']}"
        })

    # Upsert all documents
    ids = [d["id"] for d in all_docs]
    documents = [f"{d['title']}\n{d['text']}" for d in all_docs]
    metadatas = [{"category": d["category"], "title": d["title"]} for d in all_docs]

    collection.upsert(
        ids=ids,
        documents=documents,
        metadatas=metadatas
    )
    logger.info(f"Initialized knowledge base with {len(all_docs)} documents.")

def query_knowledge_base(query: str, n_results: int = 2) -> List[Dict[str, Any]]:
    """Performs semantic similarity search against the clinic knowledge base."""
    client = get_chroma_client()
    collection = client.get_or_create_collection(name=COLLECTION_NAME)
    
    results = collection.query(
        query_texts=[query],
        n_results=min(n_results, collection.count() or 1)
    )

    formatted = []
    if results and "documents" in results and results["documents"]:
        docs = results["documents"][0]
        metas = results["metadatas"][0] if "metadatas" in results and results["metadatas"] else []
        distances = results.get("distances", [[]])[0] if "distances" in results and results["distances"] else []

        for i, doc in enumerate(docs):
            meta = metas[i] if i < len(metas) else {}
            dist = distances[i] if i < len(distances) else 0.0
            formatted.append({
                "document": doc,
                "metadata": meta,
                "score": dist
            })
    return formatted

def format_knowledge_context(query: str, n_results: int = 2) -> str:
    """Returns a concise text summary of matching knowledge for prompt injection or tool response."""
    results = query_knowledge_base(query, n_results=n_results)
    if not results:
        return "No specific clinic knowledge found."
    
    snippets = [f"- {r['document']}" for r in results]
    return "\n".join(snippets)
