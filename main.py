"""
main.py — DocuMind AI  |  FastAPI Ingestion Gateway
=====================================================
Asynchronous HTTP API that acts as the front door for all document channels:

  POST /upload              — drag-and-drop file upload (web UI / Streamlit)
  POST /webhook/slack       — Slack event webhook mock (file_shared events)
  POST /webhook/email       — Email attachment ingestion mock (IMAP push)
  GET  /status/{job_id}     — Poll pipeline execution status
  GET  /documents           — List all processed documents from PostgreSQL
  GET  /graph               — Return Neo4j graph data for visualisation
  GET  /search              — Semantic RAG search over pgvector
  POST /hitl/{job_id}       — Submit human corrections to resume a halted graph
  GET  /health              — Health check for all services

Pipeline execution is fully asynchronous:
  - FastAPI receives the request and immediately returns a job_id
  - A background asyncio task runs the LangGraph pipeline
  - Results are stored in an in-memory job registry (Redis in production)

Cloudflare Quick Tunnel exposes this server to external webhooks:
  cloudflared tunnel --url http://localhost:8000
"""

from __future__ import annotations

import asyncio
import logging
import os
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import (
    BackgroundTasks,
    FastAPI,
    File,
    HTTPException,
    Query,
    UploadFile,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

# DocuMind modules
from knowledge import (
    get_graph_data,
    init_neo4j,
    init_postgres,
    semantic_search,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
)
logger = logging.getLogger("documind.api")


# ============================================================================
# Application bootstrap
# ============================================================================

app = FastAPI(
    title="DocuMind AI — Ingestion Gateway",
    version="1.0.0",
    description=(
        "Autonomous document intelligence fabric for SMEs and enterprises."
    ),
)

# Allow Streamlit (localhost:8501) to call FastAPI (localhost:8000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # tighten in production
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup_event():
    """Initialise database schemas on startup."""
    logger.info("DocuMind API starting up — initialising databases…")
    try:
        init_postgres()
        init_neo4j()
        logger.info("Database initialisation complete.")
    except Exception as exc:
        logger.warning(f"DB init warning (may already be configured): {exc}")


# ============================================================================
# In-memory job registry
# (Replace with Redis in production for multi-worker deployments)
# ============================================================================

# job_id → {"status", "state", "error", "created_at", "updated_at"}
JOB_REGISTRY: Dict[str, Dict[str, Any]] = {}


def _create_job(file_name: str, source_channel: str) -> str:
    """Register a new pipeline job and return its ID."""
    job_id = str(uuid.uuid4())
    JOB_REGISTRY[job_id] = {
        "job_id":        job_id,
        "file_name":     file_name,
        "source_channel":source_channel,
        "status":        "queued",    # queued | running | awaiting_hitl | complete | error
        "state":         None,        # final DocuMindState dict
        "error":         None,
        "created_at":    datetime.utcnow().isoformat() + "Z",
        "updated_at":    datetime.utcnow().isoformat() + "Z",
    }
    return job_id


def _update_job(job_id: str, **kwargs) -> None:
    if job_id in JOB_REGISTRY:
        JOB_REGISTRY[job_id].update(kwargs)
        JOB_REGISTRY[job_id]["updated_at"] = datetime.utcnow().isoformat() + "Z"


# ============================================================================
# Core pipeline runner (runs in asyncio background task)
# ============================================================================

async def _run_pipeline_async(
    job_id: str,
    file_name: str,
    raw_bytes: bytes,
    file_type: str,
    source_channel: str,
    priority: int,
) -> None:
    """
    Execute the LangGraph pipeline in a thread pool so we don't block the
    FastAPI event loop (LangGraph is synchronous).
    """
    _update_job(job_id, status="running")
    logger.info(f"[job={job_id}] Pipeline started for '{file_name}'")

    try:
        # Run the synchronous LangGraph pipeline in a thread
        loop = asyncio.get_event_loop()
        final_state = await loop.run_in_executor(
            None,   # default ThreadPoolExecutor
            _run_pipeline_sync,
            file_name, raw_bytes, file_type, source_channel, priority,
        )

        # Check if the graph halted at HITL
        if final_state.get("pipeline_stage") == "awaiting_hitl":
            _update_job(
                job_id,
                status="awaiting_hitl",
                state=_serialise_state(final_state),
            )
            logger.info(f"[job={job_id}] Halted at HITL — waiting for human review")
        else:
            _update_job(
                job_id,
                status="complete",
                state=_serialise_state(final_state),
            )
            logger.info(f"[job={job_id}] Pipeline complete")

    except Exception as exc:
        logger.error(f"[job={job_id}] Pipeline error: {exc}", exc_info=True)
        _update_job(job_id, status="error", error=str(exc))


def _run_pipeline_sync(
    file_name: str,
    raw_bytes: bytes,
    file_type: str,
    source_channel: str,
    priority: int,
) -> Dict[str, Any]:
    """Synchronous wrapper around graph.run_pipeline (called in thread pool)."""
    from graph import run_pipeline  # lazy import — avoids loading heavy models at startup
    return run_pipeline(
        file_name=file_name,
        raw_bytes=raw_bytes,
        file_type=file_type,
        source_channel=source_channel,
        priority=priority,
    )


def _serialise_state(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Make the DocuMindState JSON-serialisable:
    - Strip raw_bytes (too large for JSON, already persisted)
    - Convert any non-serialisable types to strings
    """
    safe = {k: v for k, v in state.items() if k != "raw_bytes"}
    # Ensure bytes values are removed recursively (shouldn't be any, but guard)
    for k, v in safe.items():
        if isinstance(v, bytes):
            safe[k] = f"<bytes:{len(v)}>"
    return safe


# ============================================================================
# Pydantic request/response models
# ============================================================================

class SlackWebhookPayload(BaseModel):
    """Simplified Slack Event API payload for file_shared events."""
    event: Dict[str, Any]
    team_id: Optional[str] = None
    api_app_id: Optional[str] = None


class EmailWebhookPayload(BaseModel):
    """Simplified inbound email payload (Mailgun / SendGrid format)."""
    from_address: str
    subject: str
    body: Optional[str] = ""
    # In production, attachments arrive as base64 strings
    attachment_name: Optional[str] = None
    attachment_b64: Optional[str] = None


class HitlCorrectionPayload(BaseModel):
    """Human corrections submitted from the Streamlit HITL interface."""
    corrections: Dict[str, Any]
    reviewed_by: str = "user"


class JobStatusResponse(BaseModel):
    job_id: str
    file_name: str
    source_channel: str
    status: str
    pipeline_stage: Optional[str] = None
    overall_confidence: Optional[float] = None
    document_type: Optional[str] = None
    anomaly_alerts: Optional[List[str]] = None
    action_log: Optional[List[str]] = None
    error: Optional[str] = None
    created_at: str
    updated_at: str


# ============================================================================
# Endpoints
# ============================================================================

# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------
@app.get("/health", tags=["Meta"])
async def health_check():
    """Check connectivity to PostgreSQL, Neo4j, and Ollama."""
    checks: Dict[str, str] = {}

    # PostgreSQL
    try:
        from knowledge import _get_pg_conn
        conn = _get_pg_conn()
        conn.close()
        checks["postgres"] = "ok"
    except Exception as exc:
        checks["postgres"] = f"error: {exc}"

    # Neo4j
    try:
        from knowledge import _get_neo4j_driver
        drv = _get_neo4j_driver()
        drv.verify_connectivity()
        drv.close()
        checks["neo4j"] = "ok"
    except Exception as exc:
        checks["neo4j"] = f"error: {exc}"

    # Ollama
    try:
        import ollama
        ollama.list()
        checks["ollama"] = "ok"
    except Exception as exc:
        checks["ollama"] = f"error: {exc}"

    overall = "healthy" if all(v == "ok" for v in checks.values()) else "degraded"
    return {"status": overall, "services": checks}


# ---------------------------------------------------------------------------
# POST /upload  — drag-and-drop web upload
# ---------------------------------------------------------------------------
@app.post("/upload", tags=["Ingestion"])
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    priority: int = Query(default=2, ge=1, le=3, description="1=urgent, 2=normal, 3=low"),
):
    """
    Accept a document file upload and immediately queue it for pipeline processing.
    Returns a job_id which the client can poll via GET /status/{job_id}.
    """
    # Validate file type
    allowed_types = {"pdf", "png", "jpg", "jpeg"}
    ext = (file.filename or "").rsplit(".", 1)[-1].lower()
    if ext not in allowed_types:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported file type: .{ext}. Allowed: {allowed_types}",
        )

    raw_bytes = await file.read()
    if len(raw_bytes) == 0:
        raise HTTPException(status_code=400, detail="Empty file received.")

    job_id = _create_job(file.filename or "upload", "web_upload")
    logger.info(
        f"Upload received: {file.filename} ({len(raw_bytes)/1024:.1f} KB), "
        f"priority={priority}, job_id={job_id}"
    )

    # Kick off pipeline in background — return immediately
    background_tasks.add_task(
        _run_pipeline_async,
        job_id=job_id,
        file_name=file.filename or "upload",
        raw_bytes=raw_bytes,
        file_type=ext,
        source_channel="web_upload",
        priority=priority,
    )

    return {
        "job_id":      job_id,
        "file_name":   file.filename,
        "status":      "queued",
        "message":     "Document queued for processing. Poll /status/{job_id} for updates.",
        "poll_url":    f"/status/{job_id}",
    }


# ---------------------------------------------------------------------------
# POST /webhook/slack  — Slack file_shared event mock
# ---------------------------------------------------------------------------
@app.post("/webhook/slack", tags=["Ingestion"])
async def slack_webhook(
    payload: SlackWebhookPayload,
    background_tasks: BackgroundTasks,
):
    """
    Handle Slack Event API callbacks for file_shared events.
    In production, this endpoint is exposed via Cloudflare Quick Tunnel.

    Expected event structure:
      {"event": {"type": "file_shared", "file_id": "F123", "file_name": "invoice.pdf"}}
    """
    event = payload.event
    if event.get("type") != "file_shared":
        return {"status": "ignored", "reason": f"event type '{event.get('type')}' not handled"}

    file_name = event.get("file_name", "slack_document.pdf")
    # In production, download the file from Slack API using the file_id
    # For the hackathon mock, we create a placeholder
    mock_bytes = b"%PDF-1.4 mock slack document"
    ext = file_name.rsplit(".", 1)[-1].lower() if "." in file_name else "pdf"

    job_id = _create_job(file_name, "slack")
    logger.info(f"Slack webhook: {file_name}, job_id={job_id}")

    background_tasks.add_task(
        _run_pipeline_async,
        job_id=job_id,
        file_name=file_name,
        raw_bytes=mock_bytes,
        file_type=ext,
        source_channel="slack",
        priority=1,   # Slack docs get high priority
    )

    return {"job_id": job_id, "status": "queued", "file_name": file_name}


# ---------------------------------------------------------------------------
# POST /webhook/email  — Email attachment ingestion mock
# ---------------------------------------------------------------------------
@app.post("/webhook/email", tags=["Ingestion"])
async def email_webhook(
    payload: EmailWebhookPayload,
    background_tasks: BackgroundTasks,
):
    """
    Handle inbound email webhooks (e.g. from Mailgun's inbound routing).
    Decodes base64-encoded attachment and queues it for processing.
    """
    import base64

    if not payload.attachment_name or not payload.attachment_b64:
        return {
            "status": "ignored",
            "reason": "No attachment found in email payload",
        }

    try:
        raw_bytes = base64.b64decode(payload.attachment_b64)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid base64 attachment data.")

    ext = payload.attachment_name.rsplit(".", 1)[-1].lower()
    job_id = _create_job(payload.attachment_name, "email")
    logger.info(
        f"Email webhook: from={payload.from_address}, "
        f"attachment={payload.attachment_name}, job_id={job_id}"
    )

    background_tasks.add_task(
        _run_pipeline_async,
        job_id=job_id,
        file_name=payload.attachment_name,
        raw_bytes=raw_bytes,
        file_type=ext,
        source_channel="email",
        priority=2,
    )

    return {
        "job_id":   job_id,
        "status":   "queued",
        "from":     payload.from_address,
        "file":     payload.attachment_name,
    }


# ---------------------------------------------------------------------------
# GET /status/{job_id}  — Poll pipeline status
# ---------------------------------------------------------------------------
@app.get("/status/{job_id}", tags=["Pipeline"], response_model=JobStatusResponse)
async def get_job_status(job_id: str):
    """
    Return the current execution status of a pipeline job.
    Used by the Streamlit UI for real-time progress updates.
    """
    job = JOB_REGISTRY.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found.")

    state: Dict[str, Any] = job.get("state") or {}
    return JobStatusResponse(
        job_id=job_id,
        file_name=job["file_name"],
        source_channel=job["source_channel"],
        status=job["status"],
        pipeline_stage=state.get("pipeline_stage"),
        overall_confidence=state.get("overall_confidence"),
        document_type=state.get("document_type"),
        anomaly_alerts=state.get("anomaly_alerts", []),
        action_log=state.get("action_log", []),
        error=job.get("error"),
        created_at=job["created_at"],
        updated_at=job["updated_at"],
    )


# ---------------------------------------------------------------------------
# POST /hitl/{job_id}  — Submit human corrections
# ---------------------------------------------------------------------------
@app.post("/hitl/{job_id}", tags=["HITL"])
async def submit_hitl_corrections(
    job_id: str,
    payload: HitlCorrectionPayload,
    background_tasks: BackgroundTasks,
):
    """
    Inject human corrections into a pipeline job that is halted at 'awaiting_hitl'.
    Resumes the LangGraph from the human_review node with the corrections applied.
    """
    job = JOB_REGISTRY.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found.")
    if job["status"] != "awaiting_hitl":
        raise HTTPException(
            status_code=409,
            detail=f"Job status is '{job['status']}', not 'awaiting_hitl'.",
        )

    stored_state = job.get("state")
    if not stored_state:
        raise HTTPException(status_code=500, detail="No stored state found for this job.")

    logger.info(
        f"[job={job_id}] HITL corrections received from '{payload.reviewed_by}': "
        f"{list(payload.corrections.keys())}"
    )
    _update_job(job_id, status="running")

    # Resume pipeline in background
    background_tasks.add_task(
        _resume_pipeline_async,
        job_id=job_id,
        state=stored_state,
        corrections=payload.corrections,
        reviewed_by=payload.reviewed_by,
    )

    return {
        "job_id":  job_id,
        "status":  "resuming",
        "message": "Corrections received. Pipeline resuming from HITL checkpoint.",
    }


async def _resume_pipeline_async(
    job_id: str,
    state: Dict[str, Any],
    corrections: Dict[str, Any],
    reviewed_by: str,
) -> None:
    """Resume a halted LangGraph pipeline after human corrections."""
    try:
        loop = asyncio.get_event_loop()
        final_state = await loop.run_in_executor(
            None,
            _resume_pipeline_sync,
            state, corrections, reviewed_by,
        )
        _update_job(
            job_id,
            status="complete",
            state=_serialise_state(final_state),
        )
        logger.info(f"[job={job_id}] HITL resume complete")
    except Exception as exc:
        logger.error(f"[job={job_id}] HITL resume error: {exc}", exc_info=True)
        _update_job(job_id, status="error", error=str(exc))


def _resume_pipeline_sync(
    state: Dict[str, Any],
    corrections: Dict[str, Any],
    reviewed_by: str,
) -> Dict[str, Any]:
    """Synchronous wrapper for graph.resume_after_hitl."""
    from graph import resume_after_hitl
    return resume_after_hitl(state, corrections, reviewed_by)


# ---------------------------------------------------------------------------
# GET /documents  — List processed documents
# ---------------------------------------------------------------------------
@app.get("/documents", tags=["Query"])
async def list_documents(limit: int = Query(default=20, le=100)):
    """Return the most recently processed documents from PostgreSQL."""
    try:
        from knowledge import _get_pg_conn
        conn = _get_pg_conn()
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, file_name, file_type, source_channel, doc_type,
                       overall_conf, page_count, ingested_at
                FROM   documents
                ORDER  BY ingested_at DESC
                LIMIT  %s
                """,
                (limit,),
            )
            rows = [dict(r) for r in cur.fetchall()]
        conn.close()
        return {"count": len(rows), "documents": rows}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# ---------------------------------------------------------------------------
# GET /graph  — Neo4j graph data for Streamlit visualisation
# ---------------------------------------------------------------------------
@app.get("/graph", tags=["Query"])
async def get_graph():
    """Return all document/vendor nodes and relationships for graph visualisation."""
    try:
        data = get_graph_data()
        return data
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# ---------------------------------------------------------------------------
# GET /search  — Semantic RAG search
# ---------------------------------------------------------------------------
@app.get("/search", tags=["Query"])
async def search_documents(
    q: str = Query(..., description="Natural language search query"),
    top_k: int = Query(default=5, ge=1, le=20),
):
    """
    Perform semantic vector search over the document corpus.
    Returns top-k most relevant document chunks with metadata.
    """
    try:
        results = semantic_search(query=q, top_k=top_k)
        return {"query": q, "results": results}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# ---------------------------------------------------------------------------
# GET /jobs  — List all in-memory jobs (debugging)
# ---------------------------------------------------------------------------
@app.get("/jobs", tags=["Meta"])
async def list_jobs():
    """List all jobs in the in-memory registry (for debugging / Streamlit polling)."""
    return {
        "count": len(JOB_REGISTRY),
        "jobs": [
            {
                "job_id":        j["job_id"],
                "file_name":     j["file_name"],
                "status":        j["status"],
                "source_channel":j["source_channel"],
                "created_at":    j["created_at"],
            }
            for j in JOB_REGISTRY.values()
        ],
    }


# ============================================================================
# Entry point (uvicorn)
# ============================================================================
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,       # auto-reload on code changes during development
        log_level="info",
    )
