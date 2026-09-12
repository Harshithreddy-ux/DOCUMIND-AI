"""
app.py — DocuMind AI
====================
Next.js-Style Glassmorphism SaaS Platform Frontend for DocuMind AI.
Streamlit Cloud Deployment Ready with Standalone Interactive Demo Engine.

Navigation:
  1. Omni-Ingestion Hub (Default Landing Page)
  2. HITL Verification
  3. Knowledge Graph
  4. RAG Intelligence
  5. Financial Analytics

Run locally:
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
    page_title="DocuMind AI Platform",
    page_icon=None,
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Configuration Constants ───────────────────────────────────────────────────
API_BASE = "http://localhost:8000"

# ── Hyper-Premium Animated Dark Gradient & Glassmorphism CSS ────────────────
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&display=swap');

    /* ── Hide Streamlit Default Chrome ───────────────────────────────────────── */
    #MainMenu { visibility: hidden !important; }
    header { visibility: hidden !important; }
    footer { visibility: hidden !important; }
    div[data-testid="stDecoration"] { display: none !important; }
    div[data-testid="stStatusWidget"] { display: none !important; }

    .block-container {
        padding-top: 1rem !important;
        padding-bottom: 2rem !important;
        max-width: 95% !important;
    }

    /* ── Animated Living Dark Gradient Background ────────────────────────────── */
    @keyframes gradientBG {
        0% { background-position: 0% 50%; }
        50% { background-position: 100% 50%; }
        100% { background-position: 0% 50%; }
    }

    html, body, [class*="css"] {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif !important;
    }

    .stApp {
        background: linear-gradient(-45deg, #07090e, #111827, #1a0f2e, #0c0a1d) !important;
        background-size: 400% 400% !important;
        animation: gradientBG 15s ease infinite !important;
        background-attachment: fixed !important;
        color: #F8FAFC !important;
    }

    /* ── Entry Slide-Up Animations ───────────────────────────────────────────── */
    @keyframes fadeSlideUp {
        0% {
            opacity: 0;
            transform: translateY(20px);
        }
        100% {
            opacity: 1;
            transform: translateY(0);
        }
    }

    .stMarkdown, .stDataFrame, .glass-card, .metric-card, .stForm {
        animation: fadeSlideUp 0.4s ease-out forwards;
    }

    /* ── Heavy Glassmorphism Cards ───────────────────────────────────────────── */
    .glass-card, .metric-card {
        background: rgba(255, 255, 255, 0.02) !important;
        backdrop-filter: blur(16px) !important;
        -webkit-backdrop-filter: blur(16px) !important;
        border: 1px solid rgba(255, 255, 255, 0.08) !important;
        border-radius: 16px !important;
        padding: 1.5rem !important;
        margin-bottom: 1.5rem !important;
        transition: all 0.3s cubic-bezier(0.16, 1, 0.3, 1) !important;
    }

    .glass-card:hover, .metric-card:hover {
        border-color: rgba(255, 90, 31, 0.4) !important;
        transform: translateY(-3px) !important;
        box-shadow: 0 8px 32px rgba(255, 90, 31, 0.25), 0 0 0 1px rgba(255, 90, 31, 0.2) !important;
    }

    /* ── Bold Headers ───────────────────────────────────────────────────────── */
    h1 {
        font-size: 2.25rem !important;
        font-weight: 800 !important;
        letter-spacing: -1px !important;
        color: #FFFFFF !important;
        margin-bottom: 0.25rem !important;
    }

    h2, h3, h4 {
        color: #F8FAFC !important;
        font-weight: 700 !important;
        letter-spacing: -0.5px !important;
    }

    p, span, label { color: #CBD5E1; }
    hr { border-color: rgba(255, 255, 255, 0.08) !important; }

    /* ── Sidebar Styling (Dark Glass Shell) ─────────────────────────────────── */
    [data-testid="stSidebar"] {
        background: rgba(9, 11, 18, 0.8) !important;
        backdrop-filter: blur(20px) !important;
        -webkit-backdrop-filter: blur(20px) !important;
        border-right: 1px solid rgba(255, 255, 255, 0.08) !important;
    }

    .sidebar-brand {
        padding: 1.5rem 0.5rem 1.5rem 0.5rem;
        margin-bottom: 1.5rem;
        border-bottom: 1px solid rgba(255, 255, 255, 0.08);
    }

    .sidebar-brand-name {
        font-size: 1.4rem;
        font-weight: 900;
        letter-spacing: -1px;
        color: #FFFFFF;
    }

    .sidebar-brand-name span {
        color: #FF5A1F;
        text-shadow: 0 0 12px rgba(255, 90, 31, 0.6);
    }

    .sidebar-brand-sub {
        font-size: 0.7rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.1em;
        color: #64748B;
        margin-top: 0.25rem;
    }

    /* ── Neon Action Buttons ────────────────────────────────────────────────── */
    .stButton > button {
        background: rgba(255, 255, 255, 0.04);
        color: #F8FAFC;
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 10px;
        font-weight: 600;
        font-size: 0.875rem;
        padding: 0.6rem 1.1rem;
        transition: all 0.25s cubic-bezier(0.16, 1, 0.3, 1);
    }

    .stButton > button:hover {
        background: rgba(255, 255, 255, 0.08);
        border-color: rgba(255, 255, 255, 0.25);
        transform: translateY(-2px);
        box-shadow: 0 4px 16px rgba(0, 0, 0, 0.3);
    }

    button[kind="primary"] {
        background: #FF5A1F !important;
        color: #FFFFFF !important;
        border: 1px solid #E04810 !important;
        border-radius: 10px !important;
        font-weight: 700 !important;
        box-shadow: 0 0 16px rgba(255, 90, 31, 0.45) !important;
        transition: all 0.25s cubic-bezier(0.16, 1, 0.3, 1) !important;
    }

    button[kind="primary"]:hover {
        background: #E04810 !important;
        box-shadow: 0 0 24px rgba(255, 90, 31, 0.7) !important;
        transform: translateY(-2px) scale(1.02) !important;
    }

    /* ── Custom Metric Card Styling ─────────────────────────────────────────── */
    .metric-title {
        font-size: 0.75rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        color: #94A3B8;
        margin-bottom: 0.4rem;
    }

    .metric-value {
        font-size: 2.25rem;
        font-weight: 900;
        color: #F8FAFC;
        letter-spacing: -0.04em;
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

    /* ── Status Pills ───────────────────────────────────────────────────────── */
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

    /* ── Chat Messaging Box Styling ─────────────────────────────────────────── */
    .chat-user-box {
        background: #2563EB;
        color: #FFFFFF;
        border-radius: 14px 14px 2px 14px;
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
        border-radius: 14px 14px 14px 2px;
        padding: 0.875rem 1.125rem;
        margin: 0.5rem 0;
        max-width: 82%;
        float: left;
        clear: both;
        font-size: 0.9rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# ── Standalone Interactive Fallback Data (For Streamlit Cloud Deployment) ───
def _get_mock_jobs() -> List[Dict[str, Any]]:
    return [
        {
            "job_id": "job-8821-inv",
            "file_name": "Invoice_AcmeCorp_2026_0042.pdf",
            "source_channel": "web_upload",
            "status": "complete",
            "created_at": "2026-09-12T19:20:00Z",
        },
        {
            "job_id": "job-8822-cnt",
            "file_name": "Consulting_Agreement_Master.pdf",
            "source_channel": "email",
            "status": "awaiting_hitl",
            "created_at": "2026-09-12T19:22:00Z",
        },
        {
            "job_id": "job-8823-po",
            "file_name": "PurchaseOrder_Hardware_901.pdf",
            "source_channel": "slack",
            "status": "complete",
            "created_at": "2026-09-12T19:25:00Z",
        },
        {
            "job_id": "job-8824-rcp",
            "file_name": "Receipt_Travel_Expense.pdf",
            "source_channel": "web_upload",
            "status": "complete",
            "created_at": "2026-09-12T19:28:00Z",
        },
    ]


def _get_mock_documents() -> List[Dict[str, Any]]:
    return [
        {"id": "doc-1", "file_name": "Invoice_AcmeCorp_2026_0042.pdf", "doc_type": "invoice", "overall_conf": 0.94, "source_channel": "web_upload"},
        {"id": "doc-2", "file_name": "Consulting_Agreement_Master.pdf", "doc_type": "contract", "overall_conf": 0.72, "source_channel": "email"},
        {"id": "doc-3", "file_name": "PurchaseOrder_Hardware_901.pdf", "doc_type": "purchase_order", "overall_conf": 0.98, "source_channel": "slack"},
        {"id": "doc-4", "file_name": "Receipt_Travel_Expense.pdf", "doc_type": "receipt", "overall_conf": 0.91, "source_channel": "web_upload"},
    ]


def _get_mock_graph() -> Dict[str, List[Dict[str, Any]]]:
    return {
        "nodes": [
            {"id": "inv-0042", "label": "Invoice #0042\n(invoice)", "color": "#FF5A1F"},
            {"id": "vendor-acme", "label": "Acme Corp", "color": "#60A5FA"},
            {"id": "po-901", "label": "PO #901\n(purchase_order)", "color": "#4ADE80"},
            {"id": "contract-master", "label": "Master Agreement\n(contract)", "color": "#A78BFA"},
        ],
        "edges": [
            {"source": "inv-0042", "target": "vendor-acme", "label": "ISSUED_BY"},
            {"source": "inv-0042", "target": "po-901", "label": "REFERENCES"},
            {"source": "contract-master", "target": "vendor-acme", "label": "GOVERNS"},
        ],
    }


# ── Session State Initialization ──────────────────────────────────────────────
def _init_session() -> None:
    defaults: Dict[str, Any] = {
        "page": "Upload",  # Default page: Omni-Ingestion Hub
        "jobs": [],
        "selected_job": None,
        "chat_history": [],
        "graph_data": None,
        "upload_queue": [],
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


_init_session()


# ── Graceful API Wrappers (Local backend or Standalone Cloud Mode) ───────────
def api_get(path: str, params: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
    try:
        r = requests.get(f"{API_BASE}{path}", params=params, timeout=3)
        r.raise_for_status()
        return r.json()
    except Exception:
        # Fallbacks for Cloud / Standalone Deployment
        if path == "/jobs":
            return {"jobs": _get_mock_jobs()}
        if path.startswith("/documents"):
            return {"documents": _get_mock_documents(), "count": len(_get_mock_documents())}
        if path == "/graph":
            return _get_mock_graph()
        if path.startswith("/status/"):
            return {
                "job_id": "job-8822-cnt",
                "file_name": "Consulting_Agreement_Master.pdf",
                "document_type": "contract",
                "overall_confidence": 0.72,
                "status": "awaiting_hitl",
                "action_log": ["CAUSAL FAILURE: Expiry date precedes effective date"],
                "anomaly_alerts": ["Liability cap missing standard indemnification clause"],
            }
        return None


def api_post(
    path: str, json_data: Optional[Dict[str, Any]] = None, files: Any = None
) -> Optional[Dict[str, Any]]:
    try:
        if files:
            r = requests.post(f"{API_BASE}{path}", files=files, timeout=30)
        else:
            r = requests.post(f"{API_BASE}{path}", json=json_data, timeout=15)
        r.raise_for_status()
        return r.json()
    except Exception:
        # Standalone mock response for Cloud deployment
        return {"job_id": f"job-{int(time.time())}", "status": "queued"}


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
            <div class="sidebar-brand-sub">Enterprise Document Intelligence</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    nav_labels = [
        "Omni-Ingestion Hub",
        "HITL Verification",
        "Knowledge Graph",
        "RAG Intelligence",
        "Financial Analytics",
    ]
    nav_keys = ["Upload", "HITL", "Graph", "Chat", "Dashboard"]

    if HAS_OPTION_MENU:
        selected_nav = option_menu(
            menu_title=None,
            options=nav_labels,
            icons=["cloud-upload", "check-circle", "diagram-3", "chat-dots", "graph-up"],
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
                    "padding": "0.7rem 0.85rem",
                    "font-weight": "600",
                    "color": "#94A3B8",
                    "--hover-color": "rgba(255, 255, 255, 0.05)",
                    "border-radius": "10px",
                },
                "nav-link-selected": {
                    "background-color": "#FF5A1F",
                    "color": "#FFFFFF",
                    "font-weight": "700",
                    "box-shadow": "0 0 16px rgba(255, 90, 31, 0.45)",
                },
            },
        )
        st.session_state.page = nav_keys[nav_labels.index(selected_nav)]
    else:
        for label, key in zip(nav_labels, nav_keys):
            if st.button(label, use_container_width=True, key=f"nav_{key}"):
                st.session_state.page = key

    st.markdown(
        """
        <div style="padding-top: 3rem; color: #475569; font-size: 0.75rem;">
            Engine v1.0.0<br>
            Multi-Modal Fabric
        </div>
        """,
        unsafe_allow_html=True,
    )


# ── Page Router ───────────────────────────────────────────────────────────────
page = st.session_state.page

# ==============================================================================
# PAGE 1: OMNI-INGESTION HUB (DEFAULT LANDING PAGE)
# ==============================================================================
if page == "Upload":
    st.markdown("<h1>Omni-Ingestion Hub</h1>", unsafe_allow_html=True)
    st.markdown(
        "<p style='color:#94A3B8;'>Multi-channel document capture with priority scheduling & multi-modal processing.</p>",
        unsafe_allow_html=True,
    )
    st.markdown("<br>", unsafe_allow_html=True)

    col_up, col_q = st.columns([1, 1])

    with col_up:
        st.markdown("<div class='glass-card'>", unsafe_allow_html=True)
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
                        st.session_state.upload_queue.append({
                            "name": uf.name,
                            "size_kb": round(len(raw) / 1024, 1),
                            "priority": priority,
                            "job_id": res.get("job_id", f"job-{int(time.time())}") if res else f"job-{int(time.time())}",
                            "status": "queued",
                        })
                    time.sleep(0.5)

                st.toast(
                    f"Successfully queued {len(uploaded_files)} document(s)!", icon="🚀"
                )
        st.markdown("</div>", unsafe_allow_html=True)

    with col_q:
        st.markdown("<div class='glass-card'>", unsafe_allow_html=True)
        st.markdown("### Queue Monitor")
        if st.button("Refresh Queue", use_container_width=True):
            jobs_resp = api_get("/jobs")
            if jobs_resp:
                j_map = {j["job_id"]: j["status"] for j in jobs_resp.get("jobs", [])}
                for q_item in st.session_state.upload_queue:
                    if q_item["job_id"] in j_map:
                        q_item["status"] = j_map[q_item["job_id"]]

        queue = st.session_state.upload_queue or [
            {"name": "Invoice_AcmeCorp_2026_0042.pdf", "size_kb": 240.5, "priority": 1, "status": "complete"},
            {"name": "Consulting_Agreement_Master.pdf", "size_kb": 512.0, "priority": 2, "status": "awaiting_hitl"},
            {"name": "PurchaseOrder_Hardware_901.pdf", "size_kb": 180.2, "priority": 2, "status": "complete"},
        ]

        for item in sorted(queue, key=lambda x: x.get("priority", 2)):
            c1, c2 = st.columns([3, 1])
            c1.markdown(f"**{item['name']}** ({item['size_kb']} KB)")
            c2.markdown(render_status_pill(item["status"]), unsafe_allow_html=True)
            st.markdown("<hr style='margin:0.5rem 0;'>", unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)


# ==============================================================================
# PAGE 2: HITL VERIFICATION
# ==============================================================================
elif page == "HITL":
    st.markdown("<h1>Human-in-the-Loop Verification</h1>", unsafe_allow_html=True)
    st.markdown(
        "<p style='color:#94A3B8;'>Review extractions flagged for low confidence or causal discrepancies.</p>",
        unsafe_allow_html=True,
    )
    st.markdown("<br>", unsafe_allow_html=True)

    jobs_resp = api_get("/jobs") or {"jobs": _get_mock_jobs()}
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
            conf = job_state.get("overall_confidence", 0.0) or 0.72
            st.markdown(
                f"""
                <div class="glass-card">
                    <div style="margin-bottom:0.5rem;"><strong>File:</strong> {job_state.get('file_name')}</div>
                    <div style="margin-bottom:0.5rem;"><strong>Doc Type:</strong> {job_state.get('document_type')}</div>
                    <div><strong>Confidence:</strong> <span style="color:#FF5A1F; font-weight:800;">{conf:.0%}</span></div>
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
                        api_post(
                            f"/hitl/{job_state.get('job_id')}",
                            json_data={"corrections": corrections, "reviewed_by": reviewer},
                        )
                        time.sleep(0.5)

                    st.toast("Pipeline Resumed Successfully!", icon="⚡")
                    time.sleep(1)
                    st.rerun()


# ==============================================================================
# PAGE 3: KNOWLEDGE GRAPH
# ==============================================================================
elif page == "Graph":
    st.markdown("<h1>Living Knowledge Graph</h1>", unsafe_allow_html=True)
    st.markdown(
        "<p style='color:#94A3B8;'>Entity relationship topology powered by Neo4j graph store.</p>",
        unsafe_allow_html=True,
    )
    st.markdown("<br>", unsafe_allow_html=True)

    if st.button("Refresh Graph View", type="primary"):
        st.session_state.graph_data = api_get("/graph")

    if st.session_state.graph_data is None:
        st.session_state.graph_data = api_get("/graph") or _get_mock_graph()

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


# ==============================================================================
# PAGE 4: RAG INTELLIGENCE (CHAT)
# ==============================================================================
elif page == "Chat":
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
                if s_res and "results" in s_res:
                    for item in s_res.get("results", []):
                        chunks.append(item.get("chunk_text", ""))

                if not chunks:
                    # Standalone intelligent response
                    answer = (
                        f"Based on the indexed document corpus:\n\n"
                        f"- Total Outstanding Payable: **$14,250.00** across Acme Corp and Hardware Direct.\n"
                        f"- Duplicate Risk: Invoice #0042 matches PO #901 with 98% similarity.\n"
                        f"- Contract Term: Master Consulting Agreement auto-renews on **2026-10-15**."
                    )
                else:
                    ctx = "\n".join(chunks)
                    answer = f"Synthesized Insights (Retrieved from {len(chunks)} chunks):\n\n{ctx[:400]}..."

                st.session_state.chat_history.append({"role": "ai", "content": answer})
                st.rerun()


# ==============================================================================
# PAGE 5: FINANCIAL ANALYTICS (DASHBOARD WITH PLOTLY)
# ==============================================================================
elif page == "Dashboard":
    st.markdown("<h1>Financial Analytics</h1>", unsafe_allow_html=True)
    st.markdown(
        "<p style='color:#94A3B8;'>Real-time SME health, document volume trends, and contractual obligation monitoring.</p>",
        unsafe_allow_html=True,
    )
    st.markdown("<br>", unsafe_allow_html=True)

    docs_data = api_get("/documents", {"limit": 100}) or {"documents": _get_mock_documents()}
    docs = docs_data.get("documents", [])

    inv_count = sum(1 for d in docs if d.get("doc_type") == "invoice") or 14
    contract_count = sum(1 for d in docs if d.get("doc_type") == "contract") or 6
    receipt_count = sum(1 for d in docs if d.get("doc_type") == "receipt") or 9
    po_count = sum(1 for d in docs if d.get("doc_type") == "purchase_order") or 5

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
            counts = [inv_count, contract_count, receipt_count, po_count, 2]

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
                font={"family": "Inter", "color": "#CBD5E1"},
                margin=dict(l=20, r=20, t=30, b=20),
                height=320,
            )
            fig_bar.update_traces(marker_line_color="#E04810", marker_line_width=1.5, opacity=0.9)
            st.plotly_chart(fig_bar, use_container_width=True)
            st.markdown("</div>", unsafe_allow_html=True)

        with chart_right:
            st.markdown("<div class='glass-card'>", unsafe_allow_html=True)
            st.markdown("#### Confidence Score Trend")

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
                font={"family": "Inter", "color": "#CBD5E1"},
                margin=dict(l=20, r=20, t=30, b=20),
                height=320,
            )
            st.plotly_chart(fig_line, use_container_width=True)
            st.markdown("</div>", unsafe_allow_html=True)
    else:
        st.info("Install Plotly (`pip install plotly`) for interactive charts.")
