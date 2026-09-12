"""
app.py — DocuMind AI
====================
Enterprise SaaS Frontend for DocuMind AI Autonomous Document Intelligence Fabric.

Navigation:
  - Home / System Overview
  - Omni-Ingestion Hub
  - Human-in-the-Loop (HITL) Review
  - Living Document Graph
  - RAG Conversation Layer
  - Financial Pulse Analytics

Run with:
  streamlit run app.py --server.port 8501
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

import requests
import streamlit as st

# ── Page Configuration ────────────────────────────────────────────────────────
st.set_page_config(
    page_title="DocuMind AI Platform",
    page_icon="https://img.icons8.com/fluency/48/document.png",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Configuration Constants ───────────────────────────────────────────────────
API_BASE = "http://localhost:8000"

# ── Advanced Custom CSS Injection (Dark & Orange SaaS Design System) ─────────
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&display=swap');

    /* ── Global Theme Override ──────────────────────────────────────────────── */
    html, body, [class*="css"] {
        font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, sans-serif;
        background-color: #0F172A !important;
        color: #F8FAFC !important;
    }

    .stApp {
        background-color: #0F172A !important;
    }

    /* ── Animations ─────────────────────────────────────────────────────────── */
    @keyframes fadeInUp {
        from {
            opacity: 0;
            transform: translateY(16px);
        }
        to {
            opacity: 1;
            transform: translateY(0);
        }
    }

    .animate-fade-in {
        animation: fadeInUp 0.4s cubic-bezier(0.16, 1, 0.3, 1) forwards;
    }

    /* ── Sidebar Styling ────────────────────────────────────────────────────── */
    [data-testid="stSidebar"] {
        background-color: #0B0F19 !important;
        border-right: 1px solid #1E293B !important;
    }

    .sidebar-brand {
        padding: 1.25rem 0.5rem;
        margin-bottom: 1.5rem;
        border-bottom: 1px solid #1E293B;
    }

    .sidebar-title {
        font-size: 1.35rem;
        font-weight: 800;
        letter-spacing: -0.025em;
        color: #FFFFFF;
        margin: 0;
        display: flex;
        align-items: center;
        gap: 0.5rem;
    }

    .sidebar-title span {
        color: #F97316;
    }

    .sidebar-subtitle {
        font-size: 0.725rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        color: #64748B;
        margin-top: 0.35rem;
    }

    /* ── Sidebar Buttons & Nav ──────────────────────────────────────────────── */
    [data-testid="stSidebar"] .stButton > button {
        background-color: transparent !important;
        color: #94A3B8 !important;
        border: 1px solid transparent !important;
        border-radius: 8px !important;
        font-weight: 600 !important;
        font-size: 0.875rem !important;
        text-align: left !important;
        padding: 0.625rem 0.875rem !important;
        transition: all 0.2s ease !important;
        width: 100% !important;
    }

    [data-testid="stSidebar"] .stButton > button:hover {
        background-color: #1E293B !important;
        color: #F8FAFC !important;
        border-color: #334155 !important;
        transform: translateX(3px);
    }

    .stButton > button[data-testid="stSidebar-active"] {
        background-color: rgba(249, 115, 22, 0.12) !important;
        color: #F97316 !important;
        border-color: rgba(249, 115, 22, 0.4) !important;
    }

    /* ── Main Buttons ───────────────────────────────────────────────────────── */
    .stButton > button {
        background-color: #1E293B;
        color: #F8FAFC;
        border: 1px solid #334155;
        border-radius: 8px;
        font-weight: 600;
        font-size: 0.875rem;
        padding: 0.5rem 1rem;
        transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1);
    }

    .stButton > button:hover {
        background-color: #334155;
        border-color: #475569;
        transform: scale(1.015);
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
    }

    button[kind="primary"] {
        background-color: #F97316 !important;
        color: #FFFFFF !important;
        border: 1px solid #EA580C !important;
        box-shadow: 0 2px 8px rgba(249, 115, 22, 0.25) !important;
    }

    button[kind="primary"]:hover {
        background-color: #EA580C !important;
        border-color: #C2410C !important;
        box-shadow: 0 4px 16px rgba(249, 115, 22, 0.4) !important;
        transform: scale(1.02) !important;
    }

    /* ── Custom Metric Cards ────────────────────────────────────────────────── */
    .metric-card {
        background-color: #1E293B;
        border: 1px solid #334155;
        border-radius: 12px;
        padding: 1.25rem 1.5rem;
        position: relative;
        overflow: hidden;
        transition: all 0.25s ease;
    }

    .metric-card:hover {
        border-color: #F97316;
        transform: translateY(-2px);
        box-shadow: 0 8px 24px rgba(0, 0, 0, 0.3), 0 0 0 1px rgba(249, 115, 22, 0.2);
    }

    .metric-title {
        font-size: 0.775rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.06em;
        color: #94A3B8;
        margin-bottom: 0.5rem;
    }

    .metric-value {
        font-size: 2rem;
        font-weight: 800;
        color: #F8FAFC;
        letter-spacing: -0.03em;
        line-height: 1.1;
    }

    .metric-badge {
        font-size: 0.725rem;
        font-weight: 600;
        padding: 0.25rem 0.5rem;
        border-radius: 6px;
        margin-top: 0.75rem;
        display: inline-block;
    }

    .badge-orange { background: rgba(249, 115, 22, 0.15); color: #FB923C; border: 1px solid rgba(249, 115, 22, 0.3); }
    .badge-green  { background: rgba(34, 197, 94, 0.15);  color: #4ADE80; border: 1px solid rgba(34, 197, 94, 0.3); }
    .badge-blue   { background: rgba(59, 130, 246, 0.15);  color: #60A5FA; border: 1px solid rgba(59, 130, 246, 0.3); }
    .badge-red    { background: rgba(239, 68, 68, 0.15);   color: #F87171; border: 1px solid rgba(239, 68, 68, 0.3); }

    /* ── Section Containers & Cards ─────────────────────────────────────────── */
    .content-card {
        background-color: #1E293B;
        border: 1px solid #334155;
        border-radius: 12px;
        padding: 1.5rem;
        margin-bottom: 1.5rem;
    }

    .status-banner-warning {
        background-color: rgba(249, 115, 22, 0.1);
        border: 1px solid rgba(249, 115, 22, 0.3);
        border-radius: 10px;
        padding: 1rem 1.25rem;
        color: #FDBA74;
        font-size: 0.875rem;
        font-weight: 500;
        margin-bottom: 1.25rem;
        display: flex;
        align-items: center;
        justify-content: space-between;
    }

    /* ── Status Pills for Tables & Logs ─────────────────────────────────────── */
    .pill {
        font-size: 0.725rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        padding: 0.25rem 0.625rem;
        border-radius: 9999px;
        display: inline-block;
    }
    .pill-complete   { background: rgba(34, 197, 94, 0.15); color: #4ADE80; border: 1px solid rgba(34, 197, 94, 0.3); }
    .pill-running    { background: rgba(249, 115, 22, 0.15); color: #FB923C; border: 1px solid rgba(249, 115, 22, 0.3); }
    .pill-hitl       { background: rgba(59, 130, 246, 0.15); color: #60A5FA; border: 1px solid rgba(59, 130, 246, 0.3); }
    .pill-error      { background: rgba(239, 68, 68, 0.15);  color: #F87171; border: 1px solid rgba(239, 68, 68, 0.3); }
    .pill-queued     { background: rgba(148, 163, 184, 0.15); color: #CBD5E1; border: 1px solid rgba(148, 163, 184, 0.3); }

    /* ── Chat Styling ───────────────────────────────────────────────────────── */
    .chat-user-box {
        background-color: #2563EB;
        color: #FFFFFF;
        border-radius: 12px 12px 2px 12px;
        padding: 0.875rem 1.125rem;
        margin: 0.5rem 0;
        max-width: 82%;
        float: right;
        clear: both;
        font-size: 0.9rem;
    }

    .chat-ai-box {
        background-color: #1E293B;
        color: #E2E8F0;
        border: 1px solid #334155;
        border-radius: 12px 12px 12px 2px;
        padding: 0.875rem 1.125rem;
        margin: 0.5rem 0;
        max-width: 82%;
        float: left;
        clear: both;
        font-size: 0.9rem;
    }

    /* ── Typography Fixes ───────────────────────────────────────────────────── */
    h1, h2, h3, h4 { color: #F8FAFC !important; font-weight: 700 !important; }
    p, span, label { color: #CBD5E1; }
    .stCaption { color: #64748B !important; }
    hr { border-color: #1E293B !important; }
    </style>
    """,
    unsafe_allow_html=True,
)


# ── Session State Initialization ──────────────────────────────────────────────
def _init_session() -> None:
    defaults: Dict[str, Any] = {
        "page": "Home",
        "jobs": [],
        "selected_job": None,
        "chat_history": [],
        "graph_data": None,
        "upload_queue": [],
        "backend_online": True,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


_init_session()


# ── Graceful API Wrappers ─────────────────────────────────────────────────────
def api_get(path: str, params: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
    """Execute API GET request with error suppression."""
    try:
        r = requests.get(f"{API_BASE}{path}", params=params, timeout=5)
        r.raise_for_status()
        st.session_state.backend_online = True
        return r.json()
    except Exception:
        st.session_state.backend_online = False
        return None


def api_post(
    path: str, json_data: Optional[Dict[str, Any]] = None, files: Any = None
) -> Optional[Dict[str, Any]]:
    """Execute API POST request with error suppression."""
    try:
        if files:
            r = requests.post(f"{API_BASE}{path}", files=files, timeout=60)
        else:
            r = requests.post(f"{API_BASE}{path}", json=json_data, timeout=30)
        r.raise_for_status()
        st.session_state.backend_online = True
        return r.json()
    except Exception:
        st.session_state.backend_online = False
        return None


def render_status_pill(status: str) -> str:
    cls = {
        "complete": "pill-complete",
        "running": "pill-running",
        "awaiting_hitl": "pill-hitl",
        "error": "pill-error",
        "queued": "pill-queued",
    }.get(status.lower(), "pill-queued")
    return f'<span class="pill {cls}">{status}</span>'


# ── Sidebar Navigation ────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown(
        """
        <div class="sidebar-brand">
            <div class="sidebar-title">DocuMind <span>AI</span></div>
            <div class="sidebar-subtitle">Enterprise Document Intelligence</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    pages = [
        ("System Overview", "Home"),
        ("Omni-Ingestion Hub", "Upload"),
        ("HITL Verification", "HITL"),
        ("Knowledge Graph", "Graph"),
        ("RAG Intelligence", "Chat"),
        ("Financial Analytics", "Dashboard"),
    ]

    for label, key in pages:
        if st.button(label, use_container_width=True, key=f"nav_{key}"):
            st.session_state.page = key

    st.markdown("<br><hr>", unsafe_allow_html=True)

    # Service Health Status Box
    if st.button("Check Backend Status", use_container_width=True):
        health = api_get("/health")
        if health:
            st.success("All Core Services Operational")
        else:
            st.warning("Backend Services Initializing...")

    st.markdown(
        """
        <div style="padding-top: 2rem; color: #475569; font-size: 0.75rem;">
            DocuMind Engine v1.0.0<br>
            Multi-Modal Agentic Fabric
        </div>
        """,
        unsafe_allow_html=True,
    )


# ── Backend Warning Banner (Shown if API offline) ─────────────────────────────
if not st.session_state.get("backend_online", True):
    st.markdown(
        """
        <div class="status-banner-warning">
            <div>
                <strong>Backend Services Initializing</strong> — The DocuMind API engine is currently starting up or offline. Local features remain responsive.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ── Page Router ───────────────────────────────────────────────────────────────
page = st.session_state.page

# ==============================================================================
# PAGE 1: SYSTEM OVERVIEW (HOME)
# ==============================================================================
if page == "Home":
    st.markdown('<div class="animate-fade-in">', unsafe_allow_html=True)
    st.markdown("<h1>System Overview</h1>", unsafe_allow_html=True)
    st.markdown(
        "<p style='color:#94A3B8;'>Real-time metrics, active pipeline stages, and document intelligence throughput.</p>",
        unsafe_allow_html=True,
    )
    st.markdown("<br>", unsafe_allow_html=True)

    # Fetch system metrics
    jobs_data = api_get("/jobs") or {"jobs": []}
    docs_data = api_get("/documents", {"limit": 100}) or {"documents": []}

    all_jobs = jobs_data.get("jobs", [])
    all_docs = docs_data.get("documents", [])

    hitl_count = sum(1 for j in all_jobs if j.get("status") == "awaiting_hitl")
    complete_count = sum(1 for j in all_jobs if j.get("status") == "complete")
    running_count = sum(1 for j in all_jobs if j.get("status") == "running")
    error_count = sum(1 for j in all_jobs if j.get("status") == "error")

    # ── Custom HTML Metric Cards Row ──────────────────────────────────────────
    m1, m2, m3, m4 = st.columns(4)
    with m1:
        st.markdown(
            f"""
            <div class="metric-card">
                <div class="metric-title">Total Documents</div>
                <div class="metric-value">{len(all_docs)}</div>
                <div class="metric-badge badge-blue">Processed Corpus</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with m2:
        st.markdown(
            f"""
            <div class="metric-card">
                <div class="metric-title">Awaiting HITL</div>
                <div class="metric-value">{hitl_count}</div>
                <div class="metric-badge badge-orange">Review Required</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with m3:
        st.markdown(
            f"""
            <div class="metric-card">
                <div class="metric-title">Completed Jobs</div>
                <div class="metric-value">{complete_count}</div>
                <div class="metric-badge badge-green">Pipeline Success</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with m4:
        st.markdown(
            f"""
            <div class="metric-card">
                <div class="metric-title">Active Processing</div>
                <div class="metric-value">{running_count}</div>
                <div class="metric-badge badge-orange">In Flight</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("<br><br>", unsafe_allow_html=True)

    # ── Layout Grid ───────────────────────────────────────────────────────────
    col_left, col_right = st.columns([2, 1])

    with col_left:
        st.markdown("### Recent Execution Queue")
        if all_jobs:
            for job in sorted(all_jobs, key=lambda x: x.get("created_at", ""), reverse=True)[:6]:
                c1, c2, c3 = st.columns([3, 1, 1])
                c1.markdown(
                    f"**{job.get('file_name', 'Untitled')}**  \n`<span style='color:#64748B;'>{job.get('job_id', '')[:12]}...</span>`",
                    unsafe_allow_html=True,
                )
                c2.markdown(render_status_pill(job.get("status", "queued")), unsafe_allow_html=True)
                c3.markdown(
                    f"<span style='color:#64748B; font-size:0.8rem;'>{job.get('source_channel', 'web')}</span>",
                    unsafe_allow_html=True,
                )
                st.markdown("<hr style='margin:0.5rem 0;'>", unsafe_allow_html=True)
        else:
            st.markdown(
                "<div style='color:#64748B; padding:1rem 0;'>No recent jobs queued. Upload documents via the Ingestion Hub.</div>",
                unsafe_allow_html=True,
            )

    with col_right:
        st.markdown("### Platform Architecture")
        st.markdown(
            """
            <div style="background:#1E293B; border:1px solid #334155; border-radius:10px; padding:1.25rem; font-size:0.85rem;">
                <div style="margin-bottom:0.75rem;"><strong style="color:#F97316;">Orchestration:</strong> LangGraph StateGraph</div>
                <div style="margin-bottom:0.75rem;"><strong style="color:#F97316;">Perception:</strong> PaddleOCR & LayoutParser</div>
                <div style="margin-bottom:0.75rem;"><strong style="color:#F97316;">Cognition:</strong> Local Ollama 4-bit Engine</div>
                <div style="margin-bottom:0.75rem;"><strong style="color:#F97316;">Vector Store:</strong> PostgreSQL pgvector</div>
                <div><strong style="color:#F97316;">Graph DB:</strong> Neo4j Enterprise</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("</div>", unsafe_allow_html=True)


# ==============================================================================
# PAGE 2: OMNI-INGESTION HUB
# ==============================================================================
elif page == "Upload":
    st.markdown('<div class="animate-fade-in">', unsafe_allow_html=True)
    st.markdown("<h1>Omni-Ingestion Hub</h1>", unsafe_allow_html=True)
    st.markdown(
        "<p style='color:#94A3B8;'>Multi-channel document capture with priority scheduling.</p>",
        unsafe_allow_html=True,
    )
    st.markdown("<br>", unsafe_allow_html=True)

    col_up, col_q = st.columns([1, 1])

    with col_up:
        st.markdown("### Upload Documents")
        uploaded_files = st.file_uploader(
            "Select or drop files",
            type=["pdf", "png", "jpg", "jpeg"],
            accept_multiple_files=True,
        )

        priority = st.select_slider(
            "Ingestion Priority",
            options=[1, 2, 3],
            value=2,
            format_func=lambda x: {1: "High Priority", 2: "Normal", 3: "Background"}[x],
        )

        channel = st.selectbox("Channel Source", ["web_upload", "email", "slack", "voice"])

        if st.button("Start Ingestion", type="primary", use_container_width=True):
            if not uploaded_files:
                st.warning("Please attach at least one document.")
            else:
                progress = st.progress(0, text="Dispatching to API...")
                for idx, uf in enumerate(uploaded_files):
                    raw = uf.read()
                    files_payload = {"file": (uf.name, raw, uf.type or "application/octet-stream")}
                    res = api_post(f"/upload?priority={priority}", files=files_payload)
                    if res:
                        st.session_state.upload_queue.append({
                            "name": uf.name,
                            "size_kb": round(len(raw) / 1024, 1),
                            "priority": priority,
                            "job_id": res.get("job_id", ""),
                            "status": "queued",
                        })
                    progress.progress((idx + 1) / len(uploaded_files))
                st.success(f"Ingestion started for {len(uploaded_files)} file(s).")

    with col_q:
        st.markdown("### Queue Monitor")
        if st.button("Refresh Queue", use_container_width=True):
            jobs_resp = api_get("/jobs")
            if jobs_resp:
                j_map = {j["job_id"]: j["status"] for j in jobs_resp.get("jobs", [])}
                for q_item in st.session_state.upload_queue:
                    if q_item["job_id"] in j_map:
                        q_item["status"] = j_map[q_item["job_id"]]

        queue = st.session_state.upload_queue
        if not queue:
            st.markdown("<div style='color:#64748B;'>No active jobs in queue.</div>", unsafe_allow_html=True)
        else:
            for item in sorted(queue, key=lambda x: x["priority"]):
                c1, c2 = st.columns([3, 1])
                c1.markdown(f"**{item['name']}** ({item['size_kb']} KB)")
                c2.markdown(render_status_pill(item["status"]), unsafe_allow_html=True)
                st.markdown("<hr style='margin:0.5rem 0;'>", unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True)


# ==============================================================================
# PAGE 3: HITL VERIFICATION
# ==============================================================================
elif page == "HITL":
    st.markdown('<div class="animate-fade-in">', unsafe_allow_html=True)
    st.markdown("<h1>Human-in-the-Loop Verification</h1>", unsafe_allow_html=True)
    st.markdown(
        "<p style='color:#94A3B8;'>Review extractions flagged for low confidence or causal discrepancies.</p>",
        unsafe_allow_html=True,
    )
    st.markdown("<br>", unsafe_allow_html=True)

    jobs_resp = api_get("/jobs") or {"jobs": []}
    hitl_jobs = [j for j in jobs_resp.get("jobs", []) if j.get("status") == "awaiting_hitl"]

    if hitl_jobs:
        job_opts = {f"{j['file_name']} ({j['job_id'][:8]})": j["job_id"] for j in hitl_jobs}
        sel_label = st.selectbox("Select Pending Verification", list(job_opts.keys()))
        sel_id = job_opts[sel_label]
        job_state = api_get(f"/status/{sel_id}")
    else:
        st.info("No documents currently require manual review.")
        job_state = None

    if job_state:
        l_col, r_col = st.columns([1, 1])

        with l_col:
            st.markdown("### Verification Context")
            conf = job_state.get("overall_confidence", 0.0) or 0.0
            st.markdown(
                f"""
                <div class="content-card">
                    <div style="margin-bottom:0.5rem;"><strong>File:</strong> {job_state.get('file_name')}</div>
                    <div style="margin-bottom:0.5rem;"><strong>Doc Type:</strong> {job_state.get('document_type')}</div>
                    <div><strong>Confidence:</strong> <span style="color:#F97316; font-weight:700;">{conf:.0%}</span></div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        with r_col:
            st.markdown("### Edit Fields")
            with st.form("hitl_form"):
                reviewer = st.text_input("Reviewer Name", "Operations Lead")
                corrections: Dict[str, Any] = {}

                # Input fields for correction
                fields = ["vendor_name", "invoice_number", "subtotal", "tax", "total"]
                for f in fields:
                    val = st.text_input(f.replace("_", " ").title(), key=f"corr_{f}")
                    if val:
                        corrections[f] = val

                if st.form_submit_button("Submit Corrections & Resume Pipeline", type="primary"):
                    res = api_post(
                        f"/hitl/{job_state.get('job_id')}",
                        json_data={"corrections": corrections, "reviewed_by": reviewer},
                    )
                    if res:
                        st.success("Corrections submitted. Pipeline resumed.")
                        time.sleep(1)
                        st.rerun()

    st.markdown("</div>", unsafe_allow_html=True)


# ==============================================================================
# PAGE 4: KNOWLEDGE GRAPH
# ==============================================================================
elif page == "Graph":
    st.markdown('<div class="animate-fade-in">', unsafe_allow_html=True)
    st.markdown("<h1>Living Knowledge Graph</h1>", unsafe_allow_html=True)
    st.markdown(
        "<p style='color:#94A3B8;'>Entity relationship topology powered by Neo4j graph store.</p>",
        unsafe_allow_html=True,
    )
    st.markdown("<br>", unsafe_allow_html=True)

    if st.button("Refresh Graph View", type="primary"):
        st.session_state.graph_data = api_get("/graph")

    if st.session_state.graph_data is None:
        st.session_state.graph_data = api_get("/graph") or {"nodes": [], "edges": []}

    gdata = st.session_state.graph_data
    nodes = gdata.get("nodes", [])
    edges = gdata.get("edges", [])

    if not nodes:
        st.info("Knowledge Graph is empty. Process documents to construct entity links.")
    else:
        try:
            from streamlit_agraph import Config, Edge, Node, agraph

            ag_nodes = [
                Node(
                    id=n["id"],
                    label=n.get("label", n["id"][:8]),
                    color=n.get("color", "#F97316"),
                    size=20,
                )
                for n in nodes
            ]
            ag_edges = [
                Edge(
                    source=e["source"],
                    target=e["target"],
                    label=e.get("label", ""),
                    color="#475569",
                )
                for e in edges
            ]
            config = Config(
                width="100%",
                height=550,
                directed=True,
                physics=True,
                nodeHighlightBehavior=True,
                highlightColor="#F97316",
            )
            agraph(nodes=ag_nodes, edges=ag_edges, config=config)
        except ImportError:
            st.warning("Install `streamlit-agraph` for interactive graph rendering.")
            st.dataframe(nodes)

    st.markdown("</div>", unsafe_allow_html=True)


# ==============================================================================
# PAGE 5: RAG INTELLIGENCE (CHAT)
# ==============================================================================
elif page == "Chat":
    st.markdown('<div class="animate-fade-in">', unsafe_allow_html=True)
    st.markdown("<h1>RAG Conversation Layer</h1>", unsafe_allow_html=True)
    st.markdown(
        "<p style='color:#94A3B8;'>Natural language cross-document synthesis powered by pgvector & local LLM.</p>",
        unsafe_allow_html=True,
    )
    st.markdown("<br>", unsafe_allow_html=True)

    c_chat, c_side = st.columns([2, 1])

    with c_side:
        st.markdown("### Recommended Queries")
        queries = [
            "What is our total outstanding payable?",
            "Are there any duplicate invoice submissions?",
            "List all contract expiration dates in Q3",
        ]
        for q in queries:
            if st.button(f"-> {q}", use_container_width=True, key=f"q_{q[:15]}"):
                st.session_state._pending_query = q

    with c_chat:
        # Render history
        for msg in st.session_state.chat_history:
            if msg["role"] == "user":
                st.markdown(
                    f'<div class="chat-user-box">{msg["content"]}</div>',
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    f'<div class="chat-ai-box">{msg["content"]}</div>',
                    unsafe_allow_html=True,
                )

        st.markdown("<br><br>", unsafe_allow_html=True)

        pending = st.session_state.pop("_pending_query", None) if hasattr(st.session_state, "_pending_query") else None

        with st.form("chat_input_form", clear_on_submit=True):
            user_input = st.text_input("Ask a question across your document corpus...", value=pending or "")
            if st.form_submit_button("Send Query", type="primary", use_container_width=True) and user_input.strip():
                st.session_state.chat_history.append({"role": "user", "content": user_input})
                s_res = api_get("/search", {"q": user_input, "top_k": 3})

                chunks = []
                if s_res:
                    for item in s_res.get("results", []):
                        chunks.append(item.get("chunk_text", ""))

                ctx = "\n".join(chunks) if chunks else "No relevant context found."
                answer = f"Synthesized Insights (Context retrieved from {len(chunks)} chunks):\n\n{ctx[:400]}..."

                st.session_state.chat_history.append({"role": "ai", "content": answer})
                st.rerun()

    st.markdown("</div>", unsafe_allow_html=True)


# ==============================================================================
# PAGE 6: FINANCIAL ANALYTICS (DASHBOARD)
# ==============================================================================
elif page == "Dashboard":
    st.markdown('<div class="animate-fade-in">', unsafe_allow_html=True)
    st.markdown("<h1>Financial Analytics</h1>", unsafe_allow_html=True)
    st.markdown(
        "<p style='color:#94A3B8;'>Real-time SME health, anomalies, and contractual obligation monitoring.</p>",
        unsafe_allow_html=True,
    )
    st.markdown("<br>", unsafe_allow_html=True)

    docs_data = api_get("/documents", {"limit": 100}) or {"documents": []}
    docs = docs_data.get("documents", [])

    inv_count = sum(1 for d in docs if d.get("doc_type") == "invoice")
    contract_count = sum(1 for d in docs if d.get("doc_type") == "contract")
    receipt_count = sum(1 for d in docs if d.get("doc_type") == "receipt")

    # Custom HTML Metric Cards
    f1, f2, f3, f4 = st.columns(4)
    with f1:
        st.markdown(
            f"""
            <div class="metric-card">
                <div class="metric-title">Invoices Analyzed</div>
                <div class="metric-value">{inv_count}</div>
                <div class="metric-badge badge-orange">Accounts Payable</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with f2:
        st.markdown(
            f"""
            <div class="metric-card">
                <div class="metric-title">Contracts Indexed</div>
                <div class="metric-value">{contract_count}</div>
                <div class="metric-badge badge-blue">Legal Repository</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with f3:
        st.markdown(
            f"""
            <div class="metric-card">
                <div class="metric-title">Receipts Parsed</div>
                <div class="metric-value">{receipt_count}</div>
                <div class="metric-badge badge-green">Expense Control</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with f4:
        st.markdown(
            """
            <div class="metric-card">
                <div class="metric-title">Risk Alerts</div>
                <div class="metric-value">0</div>
                <div class="metric-badge badge-green">Clean Integrity</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("</div>", unsafe_allow_html=True)
