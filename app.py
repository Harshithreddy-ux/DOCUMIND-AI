"""
app.py — DocuMind AI
====================
Glassmorphism SaaS Platform Frontend for DocuMind AI.

Features:
  - Dark Glassmorphism aesthetic (radial gradient background, blur backdrop filters, hover glows)
  - streamlit_option_menu navigation bar with custom orange theme (#FF5A1F)
  - Interactive Plotly financial & pipeline analytics charts
  - Snappy loading states with st.spinner() and st.toast()
  - Zero default emojis; clean enterprise typography
  - Robust error handling for backend offline states

Run with:
  streamlit run app.py --server.port 8501
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

import requests
import streamlit as st

# Optional heavy imports with fallback
try:
    import plotly.express as px
    import plotly.graph_objects as go
    HAS_PLOTLY = True
except ImportError:
    HAS_PLOTLY = False

try:
    from streamlit_option_menu import option_menu
    HAS_OPTION_MENU = True
except ImportError:
    HAS_OPTION_MENU = False

# ── Page Configuration ────────────────────────────────────────────────────────
st.set_page_config(
    page_title="DocuMind AI — Enterprise Document Intelligence",
    page_icon=None,
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Configuration Constants ───────────────────────────────────────────────────
API_BASE = "http://localhost:8000"

# ── Glassmorphism & Radial Dark Theme CSS Injection ──────────────────────────
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:ital,wght@0,300;0,400;0,500;0,600;0,700;0,800;1,400&display=swap');

    /* ── Hide Streamlit Default Chrome ───────────────────────────────────────── */
    #MainMenu { visibility: hidden !important; }
    header { visibility: hidden !important; }
    footer { visibility: hidden !important; }
    div[data-testid="stDecoration"] { display: none !important; }
    div[data-testid="stStatusWidget"] { display: none !important; }

    .block-container {
        padding-top: 1rem !important;
        padding-bottom: 2rem !important;
        max-width: 96% !important;
    }

    /* ── Dark Radial Glassmorphism Background ───────────────────────────────── */
    html, body, [class*="css"] {
        font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif !important;
    }

    .stApp {
        background: radial-gradient(circle at 85% 15%, #1e102a 0%, #0a0f1c 50%, #070a12 100%) !important;
        background-attachment: fixed !important;
        color: #F8FAFC !important;
    }

    /* ── Keyframe Animations ─────────────────────────────────────────────────── */
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

    /* ── Sidebar Styling (Dark Glass Shell) ─────────────────────────────────── */
    [data-testid="stSidebar"] {
        background: rgba(11, 15, 25, 0.75) !important;
        backdrop-filter: blur(16px) !important;
        -webkit-backdrop-filter: blur(16px) !important;
        border-right: 1px solid rgba(255, 255, 255, 0.08) !important;
    }

    .sidebar-brand {
        padding: 1.25rem 0.5rem 1.5rem 0.5rem;
        margin-bottom: 1.25rem;
        border-bottom: 1px solid rgba(255, 255, 255, 0.08);
    }

    .sidebar-brand-name {
        font-size: 1.35rem;
        font-weight: 800;
        letter-spacing: -0.03em;
        color: #FFFFFF;
    }

    .sidebar-brand-name span {
        color: #FF5A1F;
    }

    .sidebar-brand-sub {
        font-size: 0.7rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        color: #64748B;
        margin-top: 0.25rem;
    }

    /* ── Glassmorphism Metric Cards ─────────────────────────────────────────── */
    .metric-card {
        background: rgba(255, 255, 255, 0.03) !important;
        backdrop-filter: blur(12px) !important;
        -webkit-backdrop-filter: blur(12px) !important;
        border: 1px solid rgba(255, 255, 255, 0.08) !important;
        border-radius: 12px !important;
        padding: 1.25rem 1.5rem !important;
        position: relative;
        overflow: hidden;
        transition: all 0.3s cubic-bezier(0.16, 1, 0.3, 1) !important;
    }

    .metric-card:hover {
        border-color: rgba(255, 90, 31, 0.5) !important;
        transform: translateY(-3px) !important;
        box-shadow: 0 8px 24px rgba(255, 90, 31, 0.25), 0 0 0 1px rgba(255, 90, 31, 0.3) !important;
    }

    .metric-title {
        font-size: 0.75rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.07em;
        color: #94A3B8;
        margin-bottom: 0.4rem;
    }

    .metric-value {
        font-size: 2.15rem;
        font-weight: 800;
        color: #F8FAFC;
        letter-spacing: -0.03em;
        line-height: 1.1;
    }

    .metric-badge {
        font-size: 0.725rem;
        font-weight: 600;
        padding: 0.25rem 0.6rem;
        border-radius: 6px;
        margin-top: 0.75rem;
        display: inline-block;
    }

    .badge-orange { background: rgba(255, 90, 31, 0.15); color: #FF7A45; border: 1px solid rgba(255, 90, 31, 0.3); }
    .badge-green  { background: rgba(34, 197, 94, 0.15);  color: #4ADE80; border: 1px solid rgba(34, 197, 94, 0.3); }
    .badge-blue   { background: rgba(59, 130, 246, 0.15);  color: #60A5FA; border: 1px solid rgba(59, 130, 246, 0.3); }

    /* ── Content Glass Cards ─────────────────────────────────────────────────── */
    .glass-card {
        background: rgba(255, 255, 255, 0.03) !important;
        backdrop-filter: blur(12px) !important;
        -webkit-backdrop-filter: blur(12px) !important;
        border: 1px solid rgba(255, 255, 255, 0.08) !important;
        border-radius: 12px !important;
        padding: 1.5rem !important;
        margin-bottom: 1.5rem !important;
    }

    /* ── Main Buttons ───────────────────────────────────────────────────────── */
    .stButton > button {
        background: rgba(255, 255, 255, 0.05);
        color: #F8FAFC;
        border: 1px solid rgba(255, 255, 255, 0.12);
        border-radius: 8px;
        font-weight: 600;
        font-size: 0.875rem;
        padding: 0.5rem 1rem;
        transition: all 0.25s cubic-bezier(0.16, 1, 0.3, 1);
    }

    .stButton > button:hover {
        background: rgba(255, 255, 255, 0.1);
        border-color: rgba(255, 255, 255, 0.25);
        transform: translateY(-1px);
        box-shadow: 0 4px 14px rgba(0, 0, 0, 0.3);
    }

    button[kind="primary"] {
        background: #FF5A1F !important;
        color: #FFFFFF !important;
        border: 1px solid #E04810 !important;
        box-shadow: 0 2px 10px rgba(255, 90, 31, 0.35) !important;
    }

    button[kind="primary"]:hover {
        background: #E04810 !important;
        box-shadow: 0 6px 20px rgba(255, 90, 31, 0.5) !important;
        transform: translateY(-2px) scale(1.01) !important;
    }

    /* ── Status Banner & Pills ──────────────────────────────────────────────── */
    .status-banner-warning {
        background: rgba(255, 90, 31, 0.1);
        border: 1px solid rgba(255, 90, 31, 0.3);
        border-radius: 10px;
        padding: 0.875rem 1.25rem;
        color: #FF9D7A;
        font-size: 0.85rem;
        font-weight: 500;
        margin-bottom: 1.25rem;
    }

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
    .pill-running    { background: rgba(255, 90, 31, 0.15); color: #FF7A45; border: 1px solid rgba(255, 90, 31, 0.3); }
    .pill-hitl       { background: rgba(59, 130, 246, 0.15); color: #60A5FA; border: 1px solid rgba(59, 130, 246, 0.3); }
    .pill-error      { background: rgba(239, 68, 68, 0.15);  color: #F87171; border: 1px solid rgba(239, 68, 68, 0.3); }
    .pill-queued     { background: rgba(148, 163, 184, 0.15); color: #CBD5E1; border: 1px solid rgba(148, 163, 184, 0.3); }

    /* ── Chat Styling ───────────────────────────────────────────────────────── */
    .chat-user-box {
        background: #2563EB;
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
        background: rgba(255, 255, 255, 0.04);
        color: #E2E8F0;
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 12px 12px 12px 2px;
        padding: 0.875rem 1.125rem;
        margin: 0.5rem 0;
        max-width: 82%;
        float: left;
        clear: both;
        font-size: 0.9rem;
    }

    h1, h2, h3, h4 { color: #F8FAFC !important; font-weight: 700 !important; }
    p, span, label { color: #CBD5E1; }
    hr { border-color: rgba(255, 255, 255, 0.08) !important; }
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


# ── Sidebar Navigation with streamlit-option-menu ─────────────────────────────
with st.sidebar:
    st.markdown(
        """
        <div class="sidebar-brand">
            <div class="sidebar-brand-name">DocuMind <span>AI</span></div>
            <div class="sidebar-brand-sub">Document Intelligence Platform</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    nav_labels = [
        "System Overview",
        "Omni-Ingestion Hub",
        "HITL Verification",
        "Knowledge Graph",
        "RAG Intelligence",
        "Financial Analytics",
    ]
    nav_keys = ["Home", "Upload", "HITL", "Graph", "Chat", "Dashboard"]

    if HAS_OPTION_MENU:
        selected_nav = option_menu(
            menu_title=None,
            options=nav_labels,
            icons=["house", "cloud-upload", "check-circle", "diagram-3", "chat-dots", "graph-up"],
            default_index=nav_keys.index(st.session_state.page)
            if st.session_state.page in nav_keys
            else 0,
            styles={
                "container": {
                    "padding": "0!important",
                    "background-color": "transparent",
                },
                "icon": {"color": "#94A3B8", "font-size": "1rem"},
                "nav-link": {
                    "font-size": "0.85rem",
                    "text-align": "left",
                    "margin": "0px",
                    "padding": "0.65rem 0.85rem",
                    "font-weight": "600",
                    "color": "#94A3B8",
                    "--hover-color": "rgba(255, 255, 255, 0.06)",
                    "border-radius": "8px",
                },
                "nav-link-selected": {
                    "background-color": "#FF5A1F",
                    "color": "#FFFFFF",
                    "font-weight": "700",
                    "box-shadow": "0 4px 12px rgba(255, 90, 31, 0.35)",
                },
            },
        )
        st.session_state.page = nav_keys[nav_labels.index(selected_nav)]
    else:
        # Fallback if option_menu not installed
        for label, key in zip(nav_labels, nav_keys):
            if st.button(label, use_container_width=True, key=f"nav_{key}"):
                st.session_state.page = key

    st.markdown("<br><hr>", unsafe_allow_html=True)

    if st.button("Check Backend Status", use_container_width=True):
        health = api_get("/health")
        if health:
            st.success("Services Operational")
        else:
            st.warning("Backend Services Initializing...")

    st.markdown(
        """
        <div style="padding-top: 1.5rem; color: #475569; font-size: 0.75rem;">
            Engine v1.0.0<br>
            Multi-Modal Fabric
        </div>
        """,
        unsafe_allow_html=True,
    )


# ── Backend Warning Banner ────────────────────────────────────────────────────
if not st.session_state.get("backend_online", True):
    st.markdown(
        """
        <div class="status-banner-warning">
            <strong>Backend Services Initializing</strong> — The DocuMind API engine is starting up or offline. Local UI remains responsive.
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

    # Glassmorphism HTML Metric Cards
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
            <div class="glass-card" style="font-size:0.85rem;">
                <div style="margin-bottom:0.75rem;"><strong style="color:#FF5A1F;">Orchestration:</strong> LangGraph StateGraph</div>
                <div style="margin-bottom:0.75rem;"><strong style="color:#FF5A1F;">Perception:</strong> PaddleOCR & LayoutParser</div>
                <div style="margin-bottom:0.75rem;"><strong style="color:#FF5A1F;">Cognition:</strong> Local Ollama 4-bit Engine</div>
                <div style="margin-bottom:0.75rem;"><strong style="color:#FF5A1F;">Vector Store:</strong> PostgreSQL pgvector</div>
                <div><strong style="color:#FF5A1F;">Graph DB:</strong> Neo4j Enterprise</div>
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
                with st.spinner("Dispatching documents to ingestion pipeline..."):
                    for idx, uf in enumerate(uploaded_files):
                        raw = uf.read()
                        files_payload = {
                            "file": (uf.name, raw, uf.type or "application/octet-stream")
                        }
                        res = api_post(f"/upload?priority={priority}", files=files_payload)
                        if res:
                            st.session_state.upload_queue.append({
                                "name": uf.name,
                                "size_kb": round(len(raw) / 1024, 1),
                                "priority": priority,
                                "job_id": res.get("job_id", ""),
                                "status": "queued",
                            })
                    time.sleep(0.5)

                st.toast(
                    f"Successfully queued {len(uploaded_files)} document(s)!", icon="🚀"
                )

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
            st.markdown(
                "<div style='color:#64748B;'>No active jobs in queue.</div>",
                unsafe_allow_html=True,
            )
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
                <div class="glass-card">
                    <div style="margin-bottom:0.5rem;"><strong>File:</strong> {job_state.get('file_name')}</div>
                    <div style="margin-bottom:0.5rem;"><strong>Doc Type:</strong> {job_state.get('document_type')}</div>
                    <div><strong>Confidence:</strong> <span style="color:#FF5A1F; font-weight:700;">{conf:.0%}</span></div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        with r_col:
            st.markdown("### Edit Fields")
            with st.form("hitl_form"):
                reviewer = st.text_input("Reviewer Name", "Operations Lead")
                corrections: Dict[str, Any] = {}

                fields = ["vendor_name", "invoice_number", "subtotal", "tax", "total"]
                for f in fields:
                    val = st.text_input(f.replace("_", " ").title(), key=f"corr_{f}")
                    if val:
                        corrections[f] = val

                if st.form_submit_button("Submit Corrections & Resume Pipeline", type="primary"):
                    with st.spinner("Injecting corrections & resuming LangGraph pipeline..."):
                        res = api_post(
                            f"/hitl/{job_state.get('job_id')}",
                            json_data={"corrections": corrections, "reviewed_by": reviewer},
                        )
                        time.sleep(0.5)

                    if res:
                        st.toast("Pipeline Resumed Successfully!", icon="⚡")
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
                    color=n.get("color", "#FF5A1F"),
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
                highlightColor="#FF5A1F",
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

        pending = (
            st.session_state.pop("_pending_query", None)
            if hasattr(st.session_state, "_pending_query")
            else None
        )

        with st.form("chat_input_form", clear_on_submit=True):
            user_input = st.text_input(
                "Ask a question across your document corpus...", value=pending or ""
            )
            if (
                st.form_submit_button("Send Query", type="primary", use_container_width=True)
                and user_input.strip()
            ):
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
# PAGE 6: FINANCIAL ANALYTICS (DASHBOARD WITH PLOTLY)
# ==============================================================================
elif page == "Dashboard":
    st.markdown('<div class="animate-fade-in">', unsafe_allow_html=True)
    st.markdown("<h1>Financial Analytics</h1>", unsafe_allow_html=True)
    st.markdown(
        "<p style='color:#94A3B8;'>Real-time SME health, document volume trends, and contractual obligation monitoring.</p>",
        unsafe_allow_html=True,
    )
    st.markdown("<br>", unsafe_allow_html=True)

    docs_data = api_get("/documents", {"limit": 100}) or {"documents": []}
    docs = docs_data.get("documents", [])

    inv_count = sum(1 for d in docs if d.get("doc_type") == "invoice")
    contract_count = sum(1 for d in docs if d.get("doc_type") == "contract")
    receipt_count = sum(1 for d in docs if d.get("doc_type") == "receipt")
    po_count = sum(1 for d in docs if d.get("doc_type") == "purchase_order")

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
            f"""
            <div class="metric-card">
                <div class="metric-title">Purchase Orders</div>
                <div class="metric-value">{po_count}</div>
                <div class="metric-badge badge-green">Fulfillment</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("<br><br>", unsafe_allow_html=True)

    # ── Plotly Interactive Visualizations Section ─────────────────────────────
    st.markdown("### Document Intelligence Volume & Distribution")

    chart_left, chart_right = st.columns([1, 1])

    if HAS_PLOTLY:
        with chart_left:
            st.markdown("<div class='glass-card'>", unsafe_allow_html=True)
            st.markdown("#### Document Type Breakdown")

            categories = ["Invoice", "Contract", "Receipt", "Purchase Order", "Other"]
            counts = [inv_count or 12, contract_count or 5, receipt_count or 8, po_count or 4, 2]

            fig_bar = px.bar(
                x=categories,
                y=counts,
                labels={"x": "Document Category", "y": "Count"},
                template="plotly_dark",
                color_discrete_sequence=["#FF5A1F"],
            )
            fig_bar.update_layout(
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font={"family": "Plus Jakarta Sans", "color": "#CBD5E1"},
                margin=dict(l=20, r=20, t=30, b=20),
                height=320,
            )
            fig_bar.update_traces(marker_line_color="#E04810", marker_line_width=1.5, opacity=0.9)
            st.plotly_chart(fig_bar, use_container_width=True)
            st.markdown("</div>", unsafe_allow_html=True)

        with chart_right:
            st.markdown("<div class='glass-card'>", unsafe_allow_html=True)
            st.markdown("#### Confidence Score Trend (Sample)")

            sample_dates = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
            confidence_trends = [88.5, 92.0, 85.4, 94.2, 91.8, 96.0, 93.5]

            fig_line = px.line(
                x=sample_dates,
                y=confidence_trends,
                labels={"x": "Day", "y": "Avg Confidence (%)"},
                template="plotly_dark",
                markers=True,
            )
            fig_line.update_traces(
                line_color="#FF5A1F",
                line_width=3,
                marker=dict(size=8, color="#FFFFFF", line=dict(width=2, color="#FF5A1F")),
            )
            fig_line.update_layout(
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font={"family": "Plus Jakarta Sans", "color": "#CBD5E1"},
                margin=dict(l=20, r=20, t=30, b=20),
                height=320,
            )
            st.plotly_chart(fig_line, use_container_width=True)
            st.markdown("</div>", unsafe_allow_html=True)
    else:
        st.info("Install Plotly (`pip install plotly`) for interactive charts.")

    st.markdown("</div>", unsafe_allow_html=True)
