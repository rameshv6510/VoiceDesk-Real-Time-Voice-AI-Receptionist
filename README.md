# VoiceDesk — Real-Time Voice AI Receptionist for Small Clinics

VoiceDesk is an autonomous, real-time voice receptionist designed specifically for small medical and dental clinics. Built on top of **Pipecat**, **WebRTC**, **Deepgram**, **OpenAI**, **SQLite**, and **ChromaDB**, it delivers sub-500ms conversational turn latency, robust appointment management, dynamic clinical knowledge retrieval, and emergency guardrails.

---

## Architecture Overview

```text
       Browser WebRTC (Microphone / Speaker)
                       │
                       ▼
            [SmallWebRTCTransport]
                       │
       ┌───────────────┴───────────────┐
       ▼                               ▲
[Deepgram STT]                  [Deepgram TTS]
 (nova-2 streaming)             (aura-asteria-en)
       │                               ▲
       ▼                               │
[User Aggregator]             [TurnLatencyTracker]
       │                        (p50/p95 latency)
       ▼                               ▲
 [OpenAI LLM (gpt-4o-mini) + Tool Calling]
       │
 ┌─────┴────────────────────────────────┐
 ▼                                      ▼
[Appointment Tools]             [RAG Knowledge Base]
 (check_availability,            (ChromaDB vector store,
  book_appointment,               pre/post-op care,
  reschedule, cancel)             insurance, clinic FAQs)
       │                                │
       ▼                                ▼
 [SQLite Database]               [ChromaDB Local Embeddings]
```

---

## Completed Milestones

### 🟢 Milestone 1: Real-time Voice Loop & Telemetry
- **FastAPI Signaling & WebRTC Transport**: Direct browser audio streaming via WebRTC (`/api/offer`).
- **Low-Latency Pipeline**: Real-time STT (Deepgram nova-2), LLM (OpenAI gpt-4o-mini), TTS (Deepgram Aura), and VAD (Silero).
- **Turn Latency Tracker**: Measures precise caller-speech-stop to first-agent-audio latency.
- **Web Client**: Interactive browser phone interface with live audio visualizer and latency counter in `static/client/`.

### 🟢 Milestone 2: SQLite Database & Appointment Tool Calling
- **Data Layer (`app/db/`)**: Relational database supporting `doctors`, `services`, `appointments`, and `call_logs`.
- **Operating Hours & Guardrails**: Automatic enforcement of clinic schedules (Mon-Fri 9-18, Sat 9-14, Sun closed, holiday checks).
- **Pipecat Function Tools (`app/tools/appointment_tools.py`)**:
  - `check_availability(doctor_id, date)`
  - `book_appointment(patient_name, phone, doctor_id, service_id, date, time_slot)`
  - `reschedule_appointment(appointment_id, new_date, new_time)`
  - `cancel_appointment(appointment_id, phone)`
- **Double-booking Prevention**: Atomically ensures slots cannot be double-booked.

### 🟢 Milestone 3: Clinic RAG Knowledge Base
- **Vector Store (`app/rag/vector_store.py`)**: Persistent ChromaDB vector database.
- **Clinical Ingestion**: Ingests FAQs from `clinic.yaml` plus detailed clinical documents (root canal post-op care, extraction recovery, teeth whitening, cashless insurance networks, zero-cost EMI options, parking/metro directions, and cancellation policies).
- **LLM RAG Tool (`app/tools/rag_tools.py`)**: `lookup_clinic_info(query)` dynamically fetches relevant knowledge snippets.

### 🟢 Milestone 4: Clinic Receptionist Dashboard
- **Streamlit Application (`dashboard/app.py`)**:
  - **Appointments Schedule**: Interactive schedule with filters for date, doctor, and status.
  - **Manual Booking / Receptionist Form**: Quickly book walk-in appointments.
  - **Call Logs & Transcripts**: Audit trail of all AI voice calls, turn counts, and summaries.
  - **Latency Telemetry & SLA Compliance**: Interactive chart of turn latency with SLA threshold (<1200ms).
  - **RAG Playground**: Live semantic search testing against ChromaDB.
  - **Doctors Directory & Services**: Reference guide for staff.

### 🟢 Milestone 5: Evaluations & Safety Suite
- **Emergency Keyword Detection (`evals/safety_eval.py`)**: Immediately detects emergency conditions (severe bleeding, knocked out tooth, chest pain, difficulty breathing), halts booking, and routes to emergency contact.
- **Medical Advice Refusal**: Rejects prescription or diagnosis requests and guides callers to an in-person doctor visit.
- **Synthetic Latency Benchmark (`evals/latency_benchmark.py`)**: Benchmarks turn-to-turn latency distribution (p50, p95).
- **Booking Accuracy Evaluator (`evals/booking_accuracy_eval.py`)**: Validates parameter extraction and rejection of closed dates.
- **Automated CLI Runner (`evals/run_evals.py`)**: Generates structured reports in `evals/results/report.json`.

---

## Getting Started

### 1. Environment Setup
```bash
# Clone and enter directory
cd VoiceDesk

# Configure API keys in .env
copy .env.example .env
```
Ensure your `.env` contains:
```env
OPENAI_API_KEY=sk-...
DEEPGRAM_API_KEY=...
```

### 2. Run the VoiceDesk Server (FastAPI + WebRTC)
```bash
python app/main.py
```
Open [http://localhost:7860](http://localhost:7860) to test live calls in your browser.

### 3. Run the Receptionist Dashboard (Streamlit)
```bash
streamlit run dashboard/app.py
```
Opens the clinic operations dashboard at [http://localhost:8501](http://localhost:8501).

### 4. Run the Evaluation Suite
```bash
python evals/run_evals.py
```

### 5. Run the Automated Tests (25 unit tests)
```bash
pytest tests/
```
Output:
```text
tests/test_dashboard_m4.py .
tests/test_evals_m5.py ......
tests/test_pipeline_m1.py ...
tests/test_rag_m3.py .......
tests/test_tools_m2.py ........
============================= 25 passed in 32.95s =============================
```
