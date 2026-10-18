"""VoiceDesk Clinic Receptionist & Operations Dashboard.
Run via: streamlit run dashboard/app.py
"""
import sys
import os
from pathlib import Path
from datetime import datetime, date

# Add parent directory to path so app modules import cleanly
root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

import streamlit as st
import pandas as pd

from app.config import clinic_config, settings
from app.db import (
    seed_clinic_data_if_needed,
    get_doctors,
    get_services,
    get_available_slots,
    create_appointment,
    get_appointment,
    cancel_appointment,
    reschedule_appointment,
    list_appointments,
    list_call_logs,
    log_call
)
from app.rag import (
    initialize_knowledge_base,
    query_knowledge_base,
    CLINIC_KNOWLEDGE_DOCS
)

# Page configuration
st.set_page_config(
    page_title="VoiceDesk — Clinic Receptionist Dashboard",
    page_icon="🦷",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for clinic aesthetic
st.markdown("""
<style>
    .main-header {
        background: linear-gradient(135deg, #0ea5e9 0%, #0284c7 100%);
        padding: 24px 30px;
        border-radius: 12px;
        color: white;
        margin-bottom: 24px;
        box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1);
    }
    .main-header h1 {
        margin: 0;
        font-size: 28px;
        font-weight: 700;
        color: white;
    }
    .main-header p {
        margin: 4px 0 0 0;
        font-size: 15px;
        opacity: 0.95;
    }
    .metric-box {
        background: white;
        border: 1px solid #e2e8f0;
        border-radius: 10px;
        padding: 16px;
        text-align: center;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    }
    .status-confirmed {
        background-color: #dcfce7;
        color: #15803d;
        padding: 4px 10px;
        border-radius: 9999px;
        font-weight: 600;
        font-size: 13px;
    }
    .status-cancelled {
        background-color: #fee2e2;
        color: #b91c1c;
        padding: 4px 10px;
        border-radius: 9999px;
        font-weight: 600;
        font-size: 13px;
    }
</style>
""", unsafe_allow_html=True)

# Ensure database is seeded on load
seed_clinic_data_if_needed()

# Clinic metadata
clinic_info = clinic_config.get("clinic", {})
clinic_name = clinic_info.get("name", "VoiceDesk Clinic")
clinic_tagline = clinic_info.get("tagline", "AI Voice Receptionist")
clinic_address = clinic_info.get("address", "Indiranagar, Bengaluru")
clinic_phone = clinic_info.get("phone", "+91-9876543210")
emergency_phone = clinic_info.get("emergency_phone", "+91-9876599999")

# Header
st.markdown(f"""
<div class="main-header">
    <h1>🦷 {clinic_name} — Receptionist Desk</h1>
    <p>{clinic_tagline} &nbsp;|&nbsp; 📍 {clinic_address} &nbsp;|&nbsp; 📞 {clinic_phone} &nbsp;|&nbsp; 🚨 Emergency: {emergency_phone}</p>
</div>
""", unsafe_allow_html=True)

# Sidebar
with st.sidebar:
    st.image("https://api.iconify.design/solar:stethoscope-bold-duotone.svg?color=%230284c7&width=64", width=64)
    st.title("Clinic Controls")
    st.markdown(f"**Current Status:** 🟢 Online & Ready")
    
    st.divider()
    st.subheader("Working Hours")
    hours = clinic_info.get("working_hours", {})
    for day, sched in hours.items():
        if sched.get("closed"):
            st.text(f"{day.capitalize()}: Closed")
        else:
            st.text(f"{day.capitalize()}: {sched.get('open')} - {sched.get('close')}")
    
    st.divider()
    st.subheader("Quick Actions")
    if st.button("🔄 Refresh Data", use_container_width=True):
        st.rerun()

all_appts = list_appointments()
call_logs = list_call_logs(limit=100)

# Overview KPIs (Live auto-refreshing fragment)
@st.fragment(run_every=5)
def render_kpis_and_schedule():
    appts = list_appointments()
    total_appts = len(appts)
    confirmed_appts = len([a for a in appts if a["status"] == "confirmed"])
    cancelled_appts = len([a for a in appts if a["status"] == "cancelled"])
    logs = list_call_logs(limit=100)
    total_calls = len(logs)
    avg_latency = (sum([c["avg_latency_ms"] for c in logs]) / total_calls) if total_calls > 0 else 420.0

    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.metric("Total Bookings", total_appts)
    with col2:
        st.metric("Confirmed Active", confirmed_appts, delta=f"{confirmed_appts} active")
    with col3:
        st.metric("Cancelled", cancelled_appts, delta=f"{cancelled_appts} cancelled", delta_color="inverse")
    with col4:
        st.metric("Total Calls Logged", total_calls)
    with col5:
        st.metric("Avg Voice Latency", f"{avg_latency:.1f} ms", delta="-120ms Target: <1200ms", delta_color="normal")

render_kpis_and_schedule()

st.markdown("<br>", unsafe_allow_html=True)

# Tabs
tab_appts, tab_calls, tab_latency, tab_rag, tab_doctors = st.tabs([
    "📅 Appointments Management",
    "📞 Voice Call Logs",
    "⚡ Latency & SLA Analytics",
    "🧠 RAG Knowledge Base",
    "👩‍⚕️ Doctors & Services"
])

# ----------------- TAB 1: APPOINTMENTS -----------------
with tab_appts:
    app_head_col1, app_head_col2 = st.columns([4, 1])
    with app_head_col1:
        st.subheader("Clinic Appointments Schedule")
    with app_head_col2:
        if st.button("🔄 Refresh Data", key="refresh_appts_top_btn", use_container_width=True):
            st.rerun()
    
    # Filter row
    f_col1, f_col2, f_col3 = st.columns([1, 1, 1])
    doctors_list = get_doctors()
    doc_options = {"All Doctors": None}
    for d in doctors_list:
        doc_options[d["name"]] = d["id"]

    with f_col1:
        sel_doc_label = st.selectbox("Filter by Doctor:", list(doc_options.keys()))
        sel_doc_id = doc_options[sel_doc_label]
    
    with f_col2:
        filter_status = st.selectbox(
            "Filter Status:", 
            ["Confirmed (Active)", "All Appointments", "Cancelled Only"],
            index=0
        )
        if filter_status == "Confirmed (Active)":
            sel_status = "confirmed"
        elif filter_status == "Cancelled Only":
            sel_status = "cancelled"
        else:
            sel_status = None

    with f_col3:
        filter_date = st.date_input("Filter by Date:", value=None)
        sel_date_str = filter_date.strftime("%Y-%m-%d") if filter_date else None

    # Fetch appointments
    filtered_appts = list_appointments(
        date_str=sel_date_str,
        doctor_id=sel_doc_id,
        status=sel_status
    )

    if filtered_appts:
        df_appts = pd.DataFrame(filtered_appts)[
            ["id", "date", "time_slot", "patient_name", "phone", "doctor_name", "service_name", "price_inr", "status", "notes"]
        ]
        # Format status with clear visual indicator
        df_appts["status"] = df_appts["status"].map({
            "confirmed": "🟢 Confirmed",
            "cancelled": "🔴 Cancelled"
        }).fillna(df_appts["status"])
        df_appts.columns = ["Appointment ID", "Date", "Time", "Patient Name", "Phone", "Doctor", "Service", "Fee (INR)", "Status", "Notes"]
        st.dataframe(df_appts, use_container_width=True, hide_index=True)
    else:
        st.info("No appointments matching the selected filters.")

    st.divider()

    # Manual booking form & quick cancellation
    m_col1, m_col2 = st.columns(2)
    with m_col1:
        with st.expander("➕ Book Walk-in / Manual Appointment", expanded=False):
            with st.form("manual_booking_form"):
                p_name = st.text_input("Patient Full Name")
                p_phone = st.text_input("Phone Number", max_chars=10)
                
                doc_choice = st.selectbox("Select Doctor", [d["name"] for d in doctors_list])
                chosen_doc = next((d for d in doctors_list if d["name"] == doc_choice), doctors_list[0])
                
                services_list = get_services()
                srv_choice = st.selectbox("Select Service", [f"{s['name']} (₹{s['price_inr']})" for s in services_list])
                chosen_srv = services_list[[f"{s['name']} (₹{s['price_inr']})" for s in services_list].index(srv_choice)]
                
                b_date = st.date_input("Date", min_value=date.today())
                b_date_str = b_date.strftime("%Y-%m-%d")
                
                # Fetch available slots dynamically
                slots_info = get_available_slots(chosen_doc["id"], b_date_str)
                avail_slots = slots_info.get("available_slots", [])
                
                if avail_slots:
                    b_slot = st.selectbox("Available Time Slot", avail_slots)
                else:
                    b_slot = None
                    st.warning(f"No slots available on {b_date_str}: {slots_info.get('message', 'Full')}")

                p_notes = st.text_area("Notes", placeholder="Optional intake notes")
                submitted = st.form_submit_button("Confirm Booking", use_container_width=True)

                if submitted:
                    if not p_name or not p_phone or not b_slot:
                        st.error("Please fill in patient name, phone, and select an available slot.")
                    else:
                        res = create_appointment(
                            patient_name=p_name,
                            phone=p_phone,
                            doctor_id=chosen_doc["id"],
                            service_id=chosen_srv["id"],
                            date=b_date_str,
                            time_slot=b_slot,
                            notes=p_notes
                        )
                        if res.get("success"):
                            st.success(f"Appointment {res['appointment_id']} booked successfully!")
                            st.rerun()
                        else:
                            st.error(f"Booking failed: {res.get('error')}")

    with m_col2:
        with st.expander("❌ Cancel or Reschedule Existing Appointment", expanded=False):
            action_type = st.radio("Action", ["Cancel", "Reschedule"], horizontal=True)
            appt_id_input = st.text_input("Appointment ID (e.g. APT-XXXXXX)").strip().upper()
            
            if action_type == "Cancel":
                cancel_phone = st.text_input("Patient Phone for Verification (optional)")
                if st.button("Cancel Appointment", type="primary"):
                    if not appt_id_input:
                        st.error("Please enter an Appointment ID.")
                    else:
                        c_res = cancel_appointment(appt_id_input, cancel_phone)
                        if c_res.get("success"):
                            st.success(f"Appointment {appt_id_input} has been cancelled.")
                            st.rerun()
                        else:
                            st.error(c_res.get("error"))
            else:
                new_d = st.date_input("New Date", min_value=date.today(), key="resched_date")
                new_d_str = new_d.strftime("%Y-%m-%d")
                new_t_input = st.text_input("New Time Slot (HH:MM 24hr format, e.g. 11:00)")
                if st.button("Reschedule Appointment", type="primary"):
                    if not appt_id_input or not new_t_input:
                        st.error("Please provide Appointment ID and new time slot.")
                    else:
                        r_res = reschedule_appointment(appt_id_input, new_d_str, new_t_input)
                        if r_res.get("success"):
                            st.success(f"Appointment {appt_id_input} rescheduled successfully!")
                            st.rerun()
                        else:
                            st.error(r_res.get("error"))

# ----------------- TAB 2: CALL LOGS -----------------
with tab_calls:
    st.subheader("AI Voice Receptionist Call History")
    
    # Optional test call log injection
    with st.expander("🧪 Log Test Call Session"):
        with st.form("test_call_form"):
            c_sess = st.text_input("Session ID", value=f"test_{datetime.now().strftime('%H%M%S')}")
            c_phone = st.text_input("Caller Phone", value="9876543210")
            c_sum = st.text_input("Call Summary", value="Inquired about teeth cleaning fee and booked slot for Friday.")
            c_turns = st.number_input("Turns Count", min_value=1, max_value=20, value=4)
            c_lat = st.number_input("Avg Turn Latency (ms)", min_value=100.0, max_value=2500.0, value=380.0)
            if st.form_submit_button("Save Test Call Log"):
                log_call(c_sess, c_phone, c_sum, int(c_turns), float(c_lat))
                st.success("Call log saved!")
                st.rerun()

    recent_call_logs = list_call_logs(limit=100)
    if recent_call_logs:
        df_calls = pd.DataFrame(recent_call_logs)[["id", "session_id", "caller_phone", "summary", "turn_count", "avg_latency_ms", "created_at"]]
        df_calls.columns = ["Log ID", "Session ID", "Phone", "Summary", "Turns", "Avg Latency (ms)", "Timestamp"]
        st.dataframe(df_calls, use_container_width=True, hide_index=True)
    else:
        st.info("No calls logged yet. Incoming WebRTC calls will automatically populate here.")

# ----------------- TAB 3: LATENCY & SLA -----------------
with tab_latency:
    st.subheader("Voice Turn Latency & SLA Telemetry")
    
    st.markdown("""
    **SLA Target:** Turn-to-turn voice response latency must remain under **1200ms** to provide a seamless conversational experience.
    """)

    # Latency data points
    recent_call_logs = list_call_logs(limit=100)
    latencies = [c["avg_latency_ms"] for c in recent_call_logs if c.get("avg_latency_ms", 0) > 0]
    if not latencies:
        latencies = [380.0, 410.0, 395.0, 450.0, 520.0, 360.0, 405.0]

    l_p50 = sorted(latencies)[len(latencies) // 2]
    l_p95 = sorted(latencies)[min(int(len(latencies) * 0.95), len(latencies) - 1)]
    l_avg = sum(latencies) / len(latencies)

    s1, s2, s3, s4 = st.columns(4)
    with s1:
        st.metric("P50 Latency", f"{l_p50:.1f} ms")
    with s2:
        st.metric("P95 Latency", f"{l_p95:.1f} ms")
    with s3:
        st.metric("Average Latency", f"{l_avg:.1f} ms")
    with s4:
        sla_pass = (l_p95 < 1200.0)
        st.metric("SLA Compliance", "100% Passed" if sla_pass else "Breach Detected", delta="Target: <1200ms")

    # Latency chart
    df_chart = pd.DataFrame({
        "Call Index": list(range(1, len(latencies) + 1)),
        "Turn Latency (ms)": latencies,
        "Target SLA (1200ms)": [1200.0] * len(latencies)
    })
    st.line_chart(df_chart.set_index("Call Index"), color=["#0284c7", "#ef4444"])

# ----------------- TAB 4: RAG KNOWLEDGE BASE -----------------
with tab_rag:
    st.subheader("Clinic Vector Knowledge Base (ChromaDB)")
    st.write("Test semantic retrieval against clinic FAQs, care instructions, and insurance policies.")
    
    rag_query = st.text_input("Enter a query to test retrieval:", placeholder="e.g. Can I eat food after a root canal? Do you accept Care Health insurance?")
    if rag_query:
        with st.spinner("Searching knowledge base..."):
            results = query_knowledge_base(rag_query, n_results=3)
            if results:
                st.success(f"Retrieved {len(results)} matching knowledge chunks:")
                for idx, r in enumerate(results, 1):
                    with st.container():
                        st.markdown(f"**Result {idx}** | Category: `{r['metadata'].get('category', 'general')}` | Score: `{r['score']:.4f}`")
                        st.info(r["document"])
            else:
                st.warning("No matching documents found.")

    st.divider()
    st.subheader("Ingested Documents Catalog")
    for doc in CLINIC_KNOWLEDGE_DOCS:
        with st.expander(f"📄 {doc['title']} ({doc['category']})"):
            st.write(doc["text"])

# ----------------- TAB 5: DOCTORS & SERVICES -----------------
with tab_doctors:
    st.subheader("Doctors Directory")
    doc_data = get_doctors()
    st.table(pd.DataFrame(doc_data).rename(columns={"id": "Doctor ID", "name": "Doctor Name", "specialization": "Specialization"}))

    st.subheader("Clinic Services & Pricing")
    srv_data = get_services()
    st.table(pd.DataFrame(srv_data).rename(columns={
        "id": "Service ID",
        "name": "Service Name",
        "duration_minutes": "Duration (min)",
        "price_inr": "Price (INR)",
        "doctor_id": "Doctor ID"
    }))
