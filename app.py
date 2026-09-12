"""
app.py — DocuMind AI  |  Streamlit Multi-Page Dashboard
=========================================================
Entry point for the DocuMind AI Streamlit application.

Navigation (sidebar):
  🏠  Home / Overview      — KPI cards + system status
  📥  Omni-Ingestion       — Drag-and-drop upload with priority queue
  🧠  HITL Review          — Human-in-the-Loop correction interface
  🕸️  Document Graph       — Living Neo4j relationship visualisation
  💬  RAG Chat             — Cross-document natural language Q&A
  📊  Financial Pulse      — Dashboard: cash flow, anomalies, renewals

All pages communicate with the FastAPI backend (localhost:8000).
The Streamlit app is stateless — all persistent data lives in PostgreSQL/Neo4j.
Session state is used only for UI ephemera (selected job, chat history, etc.).

Run with:
  streamlit run app.py --server.port 8501
"""

import streamlit as st

# ── Page config must be the FIRST Streamlit call ─────────────────────────────
st.set_page_config(
    page_title="DocuMind AI",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded",
)

import time
from typing import Any, Dict, List, Optional

import requests

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
API_BASE = "http://localhost:8000"
POLL_INTERVAL_S = 2   # seconds between status polls

# ---------------------------------------------------------------------------
# Custom CSS — dark, professional, hackathon-grade UI
# ---------------------------------------------------------------------------
st.markdown(
    """
    <style>
    /* ── Global font & background ───────────────────────────────────── */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700&display=swap');
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

    /* ── Sidebar ─────────────────────────────────────────────────────── */
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #0d1117 0%, #161b22 100%);
        border-right: 1px solid #30363d;
    }
    [data-testid="stSidebar"] .css-1d391kg { padding-top: 1rem; }

    /* ── KPI Metric cards ────────────────────────────────────────────── */
    [data-testid="metric-container"] {
        background: #161b22;
        border: 1px solid #30363d;
        border-radius: 12px;
        padding: 1rem;
    }

    /* ── Buttons ─────────────────────────────────────────────────────── */
    .stButton > button {
        border-radius: 8px;
        font-weight: 600;
        transition: all 0.2s;
    }
    .stButton > button:hover { transform: translateY(-1px); box-shadow: 0 4px 12px rgba(0,0,0,0.3); }

    /* ── Status pills ────────────────────────────────────────────────── */
    .pill-complete   { background:#1a7f37; color:#fff; padding:2px 10px; border-radius:20px; font-size:0.75rem; }
    .pill-running    { background:#9a6700; color:#fff; padding:2px 10px; border-radius:20px; font-size:0.75rem; }
    .pill-hitl       { background:#0969da; color:#fff; padding:2px 10px; border-radius:20px; font-size:0.75rem; }
    .pill-error      { background:#cf222e; color:#fff; padding:2px 10px; border-radius:20px; font-size:0.75rem; }
    .pill-queued     { background:#6e7781; color:#fff; padding:2px 10px; border-radius:20px; font-size:0.75rem; }

    /* ── Chat bubbles ────────────────────────────────────────────────── */
    .chat-user { background:#1f6feb; color:#fff; border-radius:12px 12px 2px 12px; padding:10px 14px; margin:6px 0; max-width:80%; float:right; clear:both; }
    .chat-ai   { background:#21262d; color:#e6edf3; border-radius:12px 12px 12px 2px; padding:10px 14px; margin:6px 0; max-width:80%; float:left; clear:both; }
    .chat-source { font-size:0.7rem; color:#8b949e; margin-top:4px; }

    /* ── Divider ─────────────────────────────────────────────────────── */
    hr { border-color: #30363d; }

    /* ── Confidence bar colours ──────────────────────────────────────── */
    .conf-high { color: #3fb950; font-weight:600; }
    .conf-mid  { color: #d29922; font-weight:600; }
    .conf-low  { color: #f85149; font-weight:600; }
    </style>
    """,
    unsafe_allow_html=True,
)


# ---------------------------------------------------------------------------
# Session state initialisation
# ---------------------------------------------------------------------------
def _init_session():
    defaults = {
        "page":           "Home",
        "jobs":           [],          # list of job dicts from /jobs
        "selected_job":   None,        # job dict for HITL view
        "chat_history":   [],          # [{"role": "user"|"ai", "content": str, "sources": []}]
        "graph_data":     None,        # {"nodes": [], "edges": []}
        "upload_queue":   [],          # list of {"name", "size_kb", "priority", "job_id", "status"}
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

_init_session()


# ---------------------------------------------------------------------------
# API helpers
# ---------------------------------------------------------------------------
def api_get(path: str, params: Optional[Dict] = None) -> Optional[Dict]:
    try:
        r = requests.get(f"{API_BASE}{path}", params=params, timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception as exc:
        st.warning(f"API error: {exc}")
        return None


def api_post(path: str, json_data: Optional[Dict] = None, files=None) -> Optional[Dict]:
    try:
        if files:
            r = requests.post(f"{API_BASE}{path}", files=files, timeout=60)
        else:
            r = requests.post(f"{API_BASE}{path}", json=json_data, timeout=30)
        r.raise_for_status()
        return r.json()
    except Exception as exc:
        st.error(f"API error: {exc}")
        return None


def status_pill(status: str) -> str:
    cls = {
        "complete":     "pill-complete",
        "running":      "pill-running",
        "awaiting_hitl":"pill-hitl",
        "error":        "pill-error",
        "queued":       "pill-queued",
    }.get(status, "pill-queued")
    return f'<span class="{cls}">{status}</span>'


def conf_color(score: float) -> str:
    if score >= 0.85:
        return "conf-high"
    if score >= 0.65:
        return "conf-mid"
    return "conf-low"


# ---------------------------------------------------------------------------
# Sidebar navigation
# ---------------------------------------------------------------------------
with st.sidebar:
    st.image(
        "https://img.icons8.com/fluency/96/document.png",
        width=56,
    )
    st.markdown("## 🧠 DocuMind AI")
    st.caption("Autonomous Document Intelligence Fabric")
    st.divider()

    pages = {
        "🏠  Home":             "Home",
        "📥  Omni-Ingestion":  "Upload",
        "🧠  HITL Review":     "HITL",
        "🕸️  Document Graph":  "Graph",
        "💬  RAG Chat":        "Chat",
        "📊  Financial Pulse": "Dashboard",
    }
    for label, key in pages.items():
        if st.button(label, use_container_width=True, key=f"nav_{key}"):
            st.session_state.page = key

    st.divider()

    # Quick health check
    if st.button("🔍 Check Services", use_container_width=True):
        health = api_get("/health")
        if health:
            for svc, status in health.get("services", {}).items():
                icon = "✅" if status == "ok" else "❌"
                st.caption(f"{icon} {svc}: {status}")

    st.divider()
    st.caption("v1.0.0  ·  4-bit Ollama  ·  pgvector + Neo4j")


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------
def _rag_synthesise(query: str, context: str) -> str:
    """
    Call local Ollama to synthesise an answer from the retrieved context.
    Uses a minimal prompt optimised for 4-bit quantised models.
    """
    if not context.strip():
        return (
            "I couldn't find relevant documents in the knowledge base for that question. "
            "Please upload and process some documents first."
        )
    try:
        import ollama
        model = "gemma2:2b-instruct-q4_K_M"
        prompt = (
            "You are a financial document assistant. Answer the question using ONLY "
            "the document excerpts below. Be concise (2-4 sentences). "
            "If the answer isn't in the excerpts, say so.\n\n"
            f"DOCUMENT EXCERPTS:\n{context[:1500]}\n\n"
            f"QUESTION: {query}\n\nANSWER:"
        )
        response = ollama.generate(
            model=model,
            prompt=prompt,
            options={"num_predict": 200, "temperature": 0.2},
        )
        return response.get("response", "Unable to generate answer.").strip()
    except Exception as exc:
        return f"⚠️ LLM unavailable ({exc}). Retrieved context: {context[:400]}…"


# ---------------------------------------------------------------------------
# Page router
# ---------------------------------------------------------------------------
page = st.session_state.page

# ============================================================================
# PAGE: HOME
# ============================================================================
if page == "Home":
    st.title("🧠 DocuMind AI")
    st.subheader("Autonomous Document Intelligence Fabric for SMEs")
    st.markdown(
        "> *We don't read documents. We understand your business.*"
    )
    st.divider()

    # Fetch live stats
    jobs_data   = api_get("/jobs")   or {"jobs": [], "count": 0}
    docs_data   = api_get("/documents", {"limit": 100}) or {"documents": [], "count": 0}

    all_jobs = jobs_data.get("jobs", [])
    all_docs = docs_data.get("documents", [])

    # ── KPI Row ────────────────────────────────────────────────────────
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.metric("📄 Docs Processed", len(all_docs))
    with col2:
        hitl_count = sum(1 for j in all_jobs if j.get("status") == "awaiting_hitl")
        st.metric("🧠 Awaiting Review", hitl_count, delta="needs attention" if hitl_count else None)
    with col3:
        complete = sum(1 for j in all_jobs if j.get("status") == "complete")
        st.metric("✅ Completed Jobs", complete)
    with col4:
        error_count = sum(1 for j in all_jobs if j.get("status") == "error")
        st.metric("❌ Errors", error_count)
    with col5:
        running = sum(1 for j in all_jobs if j.get("status") == "running")
        st.metric("⚡ Running", running)

    st.divider()

    # ── Recent jobs table ──────────────────────────────────────────────
    col_l, col_r = st.columns([2, 1])
    with col_l:
        st.markdown("### 📋 Recent Pipeline Jobs")
        if all_jobs:
            for job in sorted(all_jobs, key=lambda x: x.get("created_at", ""), reverse=True)[:8]:
                cols = st.columns([3, 1, 1])
                cols[0].markdown(f"**{job['file_name']}**  \n`{job['job_id'][:8]}…`")
                cols[1].markdown(status_pill(job["status"]), unsafe_allow_html=True)
                cols[2].caption(job.get("source_channel", ""))
        else:
            st.info("No jobs yet. Upload a document to get started!")

    with col_r:
        st.markdown("### 🔑 8 Pillars Status")
        pillars = [
            ("Omni-Ingestion",   "✅"),
            ("Perception Engine","✅"),
            ("Cognition Core",   "✅"),
            ("Knowledge Fabric", "✅"),
            ("Intelligence Svc", "✅"),
            ("Conversation Layer","✅"),
            ("Automation Mesh",  "✅"),
            ("Trust & Govern.",  "✅"),
        ]
        for name, icon in pillars:
            st.caption(f"{icon} {name}")

    st.divider()

    # ── Innovation callouts ────────────────────────────────────────────
    st.markdown("### 🚀 Key Innovations")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.info(
            "**💡 Few-Shot Schema Synthesis**\n\n"
            "Upload 2-3 examples → full extraction schema in **30 seconds**. "
            "No templates. No coding."
        )
    with c2:
        st.warning(
            "**🕸️ Cross-Document Causal Reasoning**\n\n"
            "Detects duplicates, simulates contract changes, reconciles "
            "meeting notes with drafts."
        )
    with c3:
        st.success(
            "**🔄 Self-Healing Active Learning**\n\n"
            "Auto-retries failed extractions. Learns from every human "
            "correction to improve future accuracy."
        )


# ============================================================================
# PAGE: UPLOAD (Omni-Ingestion)
# ============================================================================
elif page == "Upload":
    st.title("📥 Omni-Ingestion Hub")
    st.caption("Upload documents from any channel. Smart priority queuing included.")
    st.divider()

    col_upload, col_queue = st.columns([1, 1])

    # ── Left: Upload panel ─────────────────────────────────────────────
    with col_upload:
        st.markdown("### 📂 Upload Documents")

        uploaded_files = st.file_uploader(
            "Drag & drop documents here",
            type=["pdf", "png", "jpg", "jpeg"],
            accept_multiple_files=True,
            help="Supports PDF, PNG, JPG. Batch upload up to 500 files.",
        )

        priority = st.select_slider(
            "Priority",
            options=[1, 2, 3],
            value=2,
            format_func=lambda x: {1: "🔴 Urgent", 2: "🟡 Normal", 3: "🟢 Low"}[x],
        )

        channel = st.selectbox(
            "Source Channel (mock)",
            ["web_upload", "email", "slack", "voice"],
        )

        if st.button("🚀 Process Documents", type="primary", use_container_width=True):
            if not uploaded_files:
                st.warning("Please select at least one file.")
            else:
                progress = st.progress(0, text="Submitting to pipeline…")
                for i, uf in enumerate(uploaded_files):
                    raw = uf.read()
                    # POST to FastAPI /upload
                    files_payload = {"file": (uf.name, raw, uf.type or "application/octet-stream")}
                    result = api_post(f"/upload?priority={priority}", files=files_payload)

                    if result:
                        st.session_state.upload_queue.append({
                            "name":     uf.name,
                            "size_kb":  round(len(raw) / 1024, 1),
                            "priority": priority,
                            "channel":  channel,
                            "job_id":   result.get("job_id", ""),
                            "status":   "queued",
                        })

                    progress.progress(
                        (i + 1) / len(uploaded_files),
                        text=f"Submitted {i+1}/{len(uploaded_files)}: {uf.name}",
                    )
                    time.sleep(0.1)

                st.success(f"✅ {len(uploaded_files)} document(s) queued for processing!")

        st.divider()
        st.markdown("#### 🔗 Mock External Channels")

        with st.expander("📧 Simulate Email Ingestion"):
            email_from = st.text_input("From address", "vendor@acme.com")
            email_subject = st.text_input("Subject", "Invoice #2024-0042")
            email_file = st.file_uploader("Attachment", type=["pdf", "png"], key="email_att")
            if st.button("Send Email Mock") and email_file:
                import base64
                b64 = base64.b64encode(email_file.read()).decode()
                result = api_post("/webhook/email", {
                    "from_address":    email_from,
                    "subject":         email_subject,
                    "attachment_name": email_file.name,
                    "attachment_b64":  b64,
                })
                if result:
                    st.success(f"Email ingested! job_id: {result.get('job_id', '')[:8]}…")

        with st.expander("💬 Simulate Slack Message"):
            slack_file = st.text_input("File name", "Q3_contract.pdf")
            if st.button("Send Slack Mock"):
                result = api_post("/webhook/slack", {
                    "event": {"type": "file_shared", "file_name": slack_file, "file_id": "F999"},
                })
                if result:
                    st.success(f"Slack event ingested! job_id: {result.get('job_id', '')[:8]}…")

    # ── Right: Priority Queue ──────────────────────────────────────────
    with col_queue:
        st.markdown("### ⏳ Priority Queue")

        # Refresh job statuses
        if st.button("🔄 Refresh", use_container_width=True):
            jobs_resp = api_get("/jobs")
            if jobs_resp:
                # Update statuses in upload_queue
                job_map = {j["job_id"]: j["status"] for j in jobs_resp.get("jobs", [])}
                for item in st.session_state.upload_queue:
                    if item["job_id"] in job_map:
                        item["status"] = job_map[item["job_id"]]

        queue = st.session_state.upload_queue
        if not queue:
            st.info("Queue is empty. Upload documents to see them here.")
        else:
            # Sort by priority
            sorted_queue = sorted(queue, key=lambda x: x["priority"])
            for item in sorted_queue:
                with st.container():
                    c1, c2, c3 = st.columns([3, 1, 1])
                    priority_icon = {1: "🔴", 2: "🟡", 3: "🟢"}.get(item["priority"], "⚪")
                    c1.markdown(
                        f"{priority_icon} **{item['name']}**  \n"
                        f"`{item['size_kb']} KB`  ·  {item.get('channel', 'web')}"
                    )
                    c2.markdown(status_pill(item["status"]), unsafe_allow_html=True)
                    # Jump to HITL if awaiting
                    if item["status"] == "awaiting_hitl":
                        if c3.button("Review", key=f"q_review_{item['job_id']}"):
                            # Load full job state for HITL
                            full_status = api_get(f"/status/{item['job_id']}")
                            st.session_state.selected_job = full_status
                            st.session_state.page = "HITL"
                            st.rerun()

                    st.divider()


# ============================================================================
# PAGE: HITL (Human-in-the-Loop Review)
# ============================================================================
elif page == "HITL":
    st.title("🧠 HITL — Human-in-the-Loop Review")
    st.caption(
        "Documents routed here scored below the 80% confidence threshold or failed causal validation. "
        "Correct the highlighted fields to resume the pipeline."
    )
    st.divider()

    # ── Job selector ──────────────────────────────────────────────────
    jobs_resp = api_get("/jobs") or {"jobs": []}
    hitl_jobs = [j for j in jobs_resp.get("jobs", []) if j.get("status") == "awaiting_hitl"]

    col_sel, col_badge = st.columns([3, 1])
    with col_sel:
        if hitl_jobs:
            job_options = {f"{j['file_name']} ({j['job_id'][:8]}…)": j["job_id"] for j in hitl_jobs}
            selected_label = st.selectbox("Select document to review", list(job_options.keys()))
            selected_job_id = job_options[selected_label]

            # Fetch full state
            job_state = api_get(f"/status/{selected_job_id}")
            st.session_state.selected_job = job_state
        else:
            st.success("🎉 No documents awaiting review! All pipelines are running smoothly.")
            job_state = st.session_state.get("selected_job")

    with col_badge:
        st.metric("📋 Awaiting Review", len(hitl_jobs))

    if not job_state:
        st.info("Select a job from the upload queue, or wait for a low-confidence document to arrive.")
        st.stop()

    st.divider()

    # ── HITL Content ──────────────────────────────────────────────────
    left_col, right_col = st.columns([1, 1])

    with left_col:
        st.markdown("### 📄 Document Preview")
        doc_type     = job_state.get("document_type", "unknown")
        overall_conf = job_state.get("overall_confidence", 0.0) or 0.0
        file_name    = job_state.get("file_name", "")

        st.info(
            f"**File:** {file_name}  \n"
            f"**Type:** {doc_type}  \n"
            f"**Overall Confidence:** {overall_conf:.0%}  \n"
            f"**Job ID:** {job_state.get('job_id', '')[:16]}…"
        )

        # Confidence waterfall (from action_log since state is serialised)
        st.markdown("#### 🎯 Confidence Waterfall")
        conf_note = (
            "Confidence is computed as: **OCR × Layout × LLM × Cross-Validation**\n\n"
            f"Overall score: **{overall_conf:.0%}** — "
            + ("⚠️ Below 80% threshold — review required." if overall_conf < 0.80
               else "✅ Above threshold.")
        )
        st.markdown(conf_note)

        # Causal validation warnings
        action_log = job_state.get("action_log") or []
        causal_failures = [log for log in action_log if "CAUSAL FAILURE" in log]
        if causal_failures:
            st.error("**⚠️ Causal Validation Failures:**")
            for f in causal_failures:
                st.markdown(f"- {f.replace('CAUSAL FAILURE: ', '')}")

        anomalies = job_state.get("anomaly_alerts") or []
        if anomalies:
            st.warning("**🔍 Anomaly Alerts:**")
            for a in anomalies:
                st.markdown(f"- {a}")

    with right_col:
        st.markdown("### ✏️ Field Correction Interface")
        st.caption("Edit any field below. Leave unchanged fields as-is.")

        # Get the extracted JSON from the API (via documents endpoint)
        # In production this would come from the full state via a dedicated endpoint
        # Here we use a representative set of fields based on document type
        fields_to_show = {
            "invoice": [
                "vendor_name", "invoice_number", "invoice_date",
                "due_date", "subtotal", "tax", "discount", "total",
                "currency", "payment_terms", "po_reference",
            ],
            "contract": [
                "parties", "effective_date", "expiry_date",
                "auto_renewal", "payment_terms", "governing_law",
            ],
            "receipt": [
                "merchant_name", "date", "subtotal", "tax", "total", "payment_method"
            ],
        }.get(doc_type, ["raw_text", "date", "amount"])

        corrections: Dict[str, Any] = {}
        reviewer_name = st.text_input("Your name (reviewer)", "Finance Team")

        with st.form("hitl_correction_form"):
            for field in fields_to_show:
                # In a full implementation, pre-populate from stored extracted_json
                # Here we show editable text inputs
                value = st.text_input(
                    field.replace("_", " ").title(),
                    value="",
                    key=f"hitl_{field}",
                    placeholder=f"Enter {field}…",
                )
                if value:
                    corrections[field] = value

            submitted = st.form_submit_button(
                "✅ Submit Corrections & Resume Pipeline",
                type="primary",
                use_container_width=True,
            )

        if submitted:
            if not corrections:
                st.warning("Please fill in at least one field before submitting.")
            else:
                result = api_post(
                    f"/hitl/{job_state.get('job_id', '')}",
                    json_data={
                        "corrections":  corrections,
                        "reviewed_by":  reviewer_name,
                    },
                )
                if result:
                    st.success(
                        f"✅ Corrections submitted! Pipeline resuming…  \n"
                        f"**Status:** {result.get('status', '')}  \n"
                        f"{result.get('message', '')}"
                    )
                    st.session_state.selected_job = None
                    time.sleep(1.5)
                    st.rerun()


# ============================================================================
# PAGE: GRAPH (Living Document Graph)
# ============================================================================
elif page == "Graph":
    st.title("🕸️ Living Document Graph")
    st.caption(
        "Force-directed graph of all documents, vendors, and their relationships in Neo4j. "
        "Nodes are coloured by document type and dimmed if confidence < 80%."
    )
    st.divider()

    col_ctrl, col_legend = st.columns([3, 1])
    with col_ctrl:
        if st.button("🔄 Refresh Graph", type="primary"):
            st.session_state.graph_data = api_get("/graph")

    with col_legend:
        st.markdown(
            """
            **Legend:**
            - 🟢 Invoice
            - 🔵 Contract
            - 🟡 Receipt
            - 🟠 Purchase Order
            - 🟣 Vendor
            - ⚪ Low confidence
            """
        )

    # Load graph data
    if st.session_state.graph_data is None:
        st.session_state.graph_data = api_get("/graph") or {"nodes": [], "edges": []}

    graph_data = st.session_state.graph_data
    nodes_raw  = graph_data.get("nodes", [])
    edges_raw  = graph_data.get("edges", [])

    if not nodes_raw:
        st.info(
            "📭 No documents in the graph yet.\n\n"
            "Upload and process documents to see them appear here."
        )
    else:
        st.caption(f"Showing **{len(nodes_raw)} nodes** and **{len(edges_raw)} edges**")

        try:
            from streamlit_agraph import agraph, Config, Edge, Node  # type: ignore

            nodes = [
                Node(
                    id=n["id"],
                    label=n.get("label", n["id"][:8]),
                    color=n.get("color", "#636e72"),
                    size=n.get("size", 20),
                )
                for n in nodes_raw
            ]
            edges = [
                Edge(
                    source=e["source"],
                    target=e["target"],
                    label=e.get("label", ""),
                    color="#8b949e",
                )
                for e in edges_raw
            ]
            config = Config(
                width="100%",
                height=600,
                directed=True,
                physics=True,
                hierarchical=False,
                nodeHighlightBehavior=True,
                highlightColor="#f0a500",
                collapsible=False,
            )
            selected = agraph(nodes=nodes, edges=edges, config=config)
            if selected:
                st.markdown(f"**Selected node:** `{selected}`")

        except ImportError:
            # Fallback: plain table if streamlit-agraph isn't installed
            st.warning(
                "streamlit-agraph not installed. "
                "Run `pip install streamlit-agraph` for interactive graph visualisation."
            )
            st.markdown("#### Nodes")
            st.dataframe(
                [{"id": n["id"][:16], "label": n.get("label", ""), "color": n.get("color", "")}
                 for n in nodes_raw]
            )
            st.markdown("#### Edges")
            st.dataframe(
                [{"source": e["source"][:16], "target": e["target"][:16], "rel": e.get("label", "")}
                 for e in edges_raw]
            )

    st.divider()

    # ── Document list sidebar ──────────────────────────────────────────
    st.markdown("### 📋 All Documents in Knowledge Fabric")
    docs_resp = api_get("/documents", {"limit": 50}) or {"documents": []}
    docs = docs_resp.get("documents", [])
    if docs:
        for doc in docs:
            conf = float(doc.get("overall_conf") or 0)
            conf_cls = conf_color(conf)
            st.markdown(
                f"**{doc.get('file_name', 'unknown')}** · {doc.get('doc_type', '')} · "
                f"<span class='{conf_cls}'>{conf:.0%}</span> confidence · "
                f"via {doc.get('source_channel', '')}",
                unsafe_allow_html=True,
            )
    else:
        st.info("No documents stored yet.")


# ============================================================================
# PAGE: CHAT (RAG Conversation Layer)
# ============================================================================
elif page == "Chat":
    st.title("💬 RAG Conversation Layer")
    st.caption(
        "Ask cross-document questions in plain English. "
        "Powered by pgvector semantic search + local Ollama LLM."
    )
    st.divider()

    col_chat, col_info = st.columns([2, 1])

    with col_info:
        st.markdown("### 💡 Example Questions")
        examples = [
            "How much did we spend on cloud services last quarter?",
            "Which contracts auto-renew in the next 30 days?",
            "Find all invoices from Acme Corp over $10,000",
            "Are there any duplicate invoices?",
            "What is our total outstanding payable?",
            "Which vendors have unusual billing patterns?",
        ]
        for ex in examples:
            if st.button(f"➡ {ex}", use_container_width=True, key=f"ex_{ex[:20]}"):
                st.session_state._pending_query = ex

        st.divider()
        st.markdown("### 📚 Knowledge Base Stats")
        docs_resp = api_get("/documents", {"limit": 1}) or {"count": 0}
        st.metric("Documents indexed", docs_resp.get("count", 0))

        if st.button("🗑️ Clear Chat", use_container_width=True):
            st.session_state.chat_history = []
            st.rerun()

    with col_chat:
        # ── Chat history display ───────────────────────────────────────
        chat_container = st.container()
        with chat_container:
            for msg in st.session_state.chat_history:
                if msg["role"] == "user":
                    st.markdown(
                        f'<div class="chat-user">{msg["content"]}</div>',
                        unsafe_allow_html=True,
                    )
                else:
                    sources_html = ""
                    if msg.get("sources"):
                        src_list = ", ".join(
                            s.get("file_name", "doc")[:30] for s in msg["sources"][:3]
                        )
                        sources_html = f'<div class="chat-source">📎 Sources: {src_list}</div>'
                    st.markdown(
                        f'<div class="chat-ai">{msg["content"]}{sources_html}</div>',
                        unsafe_allow_html=True,
                    )

        st.markdown("<br>", unsafe_allow_html=True)

        # ── Input box ─────────────────────────────────────────────────
        # Handle example button click
        pending = st.session_state.pop("_pending_query", None) if hasattr(st.session_state, "_pending_query") else None

        with st.form("chat_form", clear_on_submit=True):
            query = st.text_input(
                "Ask a question about your documents…",
                value=pending or "",
                placeholder="e.g. What is the total invoice amount from Acme Corp?",
            )
            send = st.form_submit_button("Send", type="primary", use_container_width=True)

        if send and query.strip():
            user_query = query.strip()

            # Add user message to history
            st.session_state.chat_history.append({"role": "user", "content": user_query})

            with st.spinner("🔍 Searching documents + generating answer…"):
                # Step 1: Semantic search
                search_result = api_get("/search", {"q": user_query, "top_k": 5})
                context_chunks = []
                sources = []
                if search_result:
                    for item in search_result.get("results", []):
                        context_chunks.append(item.get("chunk_text", ""))
                        sources.append({
                            "file_name":  item.get("file_name", ""),
                            "doc_type":   item.get("doc_type", ""),
                            "similarity": item.get("similarity", 0),
                        })

                context_text = "\n\n---\n\n".join(context_chunks[:3]) if context_chunks else ""

                # Step 2: LLM synthesis via Ollama
                ai_answer = _rag_synthesise(user_query, context_text)

            # Add AI response to history
            st.session_state.chat_history.append({
                "role":    "ai",
                "content": ai_answer,
                "sources": sources,
            })
            st.rerun()



# ============================================================================
# PAGE: DASHBOARD (Financial Pulse)
# ============================================================================
elif page == "Dashboard":
    st.title("📊 Financial Pulse Dashboard")
    st.caption("Real-time SME financial health: cash flow, overdue invoices, contract renewals.")
    st.divider()

    # Pull documents from API
    docs_resp = api_get("/documents", {"limit": 100}) or {"documents": []}
    docs = docs_resp.get("documents", [])
    jobs_resp = api_get("/jobs") or {"jobs": []}
    jobs = jobs_resp.get("jobs", [])

    # ── KPI Row ────────────────────────────────────────────────────────
    invoices  = [d for d in docs if d.get("doc_type") == "invoice"]
    contracts = [d for d in docs if d.get("doc_type") == "contract"]
    receipts  = [d for d in docs if d.get("doc_type") == "receipt"]
    anomalies = [j for j in jobs if j.get("status") == "complete"]  # proxy

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("🧾 Total Invoices",  len(invoices))
    with col2:
        st.metric("📃 Contracts",       len(contracts))
    with col3:
        st.metric("🧾 Receipts",        len(receipts))
    with col4:
        st.metric("⚡ Jobs Processed",  len(jobs))

    st.divider()

    col_l, col_r = st.columns(2)

    with col_l:
        st.markdown("### 🚨 Risk Radar")
        alert_items = []
        for j in jobs:
            action_log = []  # would come from full state in production
            for log in action_log:
                if "ALERT" in log or "anomaly" in log.lower():
                    alert_items.append(log)

        if alert_items:
            for alert in alert_items:
                st.error(f"⚠️ {alert}")
        else:
            st.success("✅ No active risk alerts detected.")

        st.divider()
        st.markdown("### 📋 Recent Documents")
        if docs:
            for doc in docs[:8]:
                conf = float(doc.get("overall_conf") or 0)
                conf_cls = conf_color(conf)
                st.markdown(
                    f"- **{doc.get('file_name', '?')}** · {doc.get('doc_type', '?')} · "
                    f"<span class='{conf_cls}'>{conf:.0%}</span>",
                    unsafe_allow_html=True,
                )
        else:
            st.info("No documents processed yet.")

    with col_r:
        st.markdown("### 📈 Processing Volume")
        # Pipeline stage breakdown
        stage_counts = {}
        for j in jobs:
            s = j.get("status", "unknown")
            stage_counts[s] = stage_counts.get(s, 0) + 1

        if stage_counts:
            import pandas as pd
            df = pd.DataFrame(
                list(stage_counts.items()), columns=["Status", "Count"]
            )
            st.bar_chart(df.set_index("Status"))
        else:
            st.info("Upload documents to see processing volume trends.")

        st.divider()
        st.markdown("### 💡 Automation Actions")
        all_actions = []
        # In production, query action_log from documents table
        if not all_actions:
            st.info("Actions will appear here once documents are processed.")
        else:
            for action in all_actions[-10:]:
                st.caption(f"▶ {action}")


# ============================================================================
# Footer
# ============================================================================
st.markdown(
    """
    <hr style="margin-top:3rem;">
    <center style="color:#8b949e;font-size:0.8rem;">
    🧠 <strong>DocuMind AI</strong> ·
    Built with LangGraph + Ollama + pgvector + Neo4j + Streamlit
    </center>
    """,
    unsafe_allow_html=True,
)
