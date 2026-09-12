"""
state.py — DocuMind AI
======================
Defines the canonical LangGraph StateGraph TypedDict.
Every pipeline node (ingest → perceive → understand → connect → act)
reads from and writes into this single shared state object.

Design principle: immutable-by-convention. Each node returns a *partial*
dict with only the keys it owns. LangGraph merges them automatically.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, TypedDict


# ---------------------------------------------------------------------------
# Bounding-box structure returned by LayoutParser / PaddleOCR
# ---------------------------------------------------------------------------
class BoundingBox(TypedDict):
    """Spatial region of a detected text or layout element."""
    text: str           # OCR'd text inside this region
    x1: float           # Top-left X  (normalised 0-1 or pixels)
    y1: float           # Top-left Y
    x2: float           # Bottom-right X
    y2: float           # Bottom-right Y
    label: str          # LayoutParser label e.g. "Table", "Title", "Text"
    ocr_conf: float     # PaddleOCR character-level confidence (0-1)


# ---------------------------------------------------------------------------
# Per-field confidence breakdown (the "confidence waterfall")
# ---------------------------------------------------------------------------
class FieldConfidence(TypedDict):
    """Multiplicative confidence model: OCR × Layout × LLM × Cross-validation."""
    field_name: str
    raw_value: str
    ocr_confidence: float       # Character-level certainty from PaddleOCR
    layout_confidence: float    # How well the field maps to expected layout region
    llm_confidence: float       # Model self-reported logit confidence
    cross_val_confidence: float # Causal / rule-based validation score
    final_score: float          # Product of all four dimensions (0-1)
    needs_review: bool          # True if final_score < CONFIDENCE_THRESHOLD


# ---------------------------------------------------------------------------
# Causal validation result
# ---------------------------------------------------------------------------
class CausalValidationResult(TypedDict):
    """Output of the math consistency checker in cognition.py."""
    passed: bool
    checks_run: List[str]       # e.g. ["subtotal+tax==total", "qty*price==line_total"]
    failures: List[str]         # Human-readable descriptions of failed checks
    corrected_values: Dict[str, Any]  # Suggested fixes keyed by field name


# ---------------------------------------------------------------------------
# The Central LangGraph State
# ---------------------------------------------------------------------------
class DocuMindState(TypedDict):
    """
    Master state object that flows through every node of the LangGraph.

    Lifecycle of key fields:
      raw_bytes       → set by ingest node
      ocr_text        → set by perceive node
      bounding_boxes  → set by perceive node
      extracted_json  → set by understand node
      confidence_map  → set by understand node
      validation      → set by understand node
      needs_hitl      → set by understand node (triggers conditional edge)
      graph_node_ids  → set by connect node
      action_log      → appended by act node
    """

    # ── Ingest ──────────────────────────────────────────────────────────────
    file_name: str                      # Original file name
    file_type: str                      # "pdf" | "png" | "jpg" | "email" | "slack"
    source_channel: str                 # "web_upload" | "email" | "slack" | "voice"
    raw_bytes: bytes                    # Raw file contents
    priority: int                       # 1=urgent, 2=normal, 3=low
    ingested_at: str                    # ISO-8601 timestamp

    # ── Perceive ─────────────────────────────────────────────────────────────
    ocr_text: str                       # Full concatenated OCR text
    bounding_boxes: List[BoundingBox]   # Per-region spatial + text data
    page_count: int                     # Number of pages detected
    forensics_flags: List[str]          # e.g. ["font_mismatch", "entropy_anomaly"]
    layout_summary: str                 # High-level layout description

    # ── Understand (Cognition) ───────────────────────────────────────────────
    document_type: str                  # "invoice" | "contract" | "receipt" | "unknown"
    extracted_json: Dict[str, Any]      # LLM-extracted structured fields
    schema_used: str                    # Schema name that was applied
    confidence_map: List[FieldConfidence]  # Per-field confidence waterfall
    overall_confidence: float           # Mean final_score across all fields (0-1)
    validation: CausalValidationResult  # Math/logic consistency check output

    # ── HITL Gate ────────────────────────────────────────────────────────────
    needs_hitl: bool                    # True → route to human_review node
    hitl_corrections: Dict[str, Any]    # Human-provided field overrides
    hitl_reviewed_by: Optional[str]     # Username of reviewer
    hitl_reviewed_at: Optional[str]     # ISO-8601 timestamp

    # ── Connect (Knowledge Fabric) ───────────────────────────────────────────
    embedding_id: Optional[str]         # pgvector row UUID
    graph_node_ids: List[str]           # Neo4j node element IDs
    linked_documents: List[str]         # IDs of related documents found during linking
    anomaly_alerts: List[str]           # e.g. ["amount_3x_vendor_avg"]

    # ── Act (Automation Mesh) ────────────────────────────────────────────────
    action_log: List[str]               # Human-readable log of actions taken
    routed_to: Optional[str]            # e.g. "CFO", "AP_clerk"
    calendar_events_created: List[str]  # Calendar event IDs
    erp_push_status: Optional[str]      # "success" | "failed" | "skipped"

    # ── Meta ─────────────────────────────────────────────────────────────────
    error: Optional[str]                # Non-null if any node raised an exception
    pipeline_stage: str                 # Current stage name for UI progress indicator


# ---------------------------------------------------------------------------
# Default / empty state factory
# ---------------------------------------------------------------------------
def empty_state() -> DocuMindState:
    """
    Returns a zeroed-out DocuMindState suitable as a starting point.
    Nodes only need to fill in the keys they own.
    """
    return DocuMindState(
        # Ingest
        file_name="",
        file_type="",
        source_channel="web_upload",
        raw_bytes=b"",
        priority=2,
        ingested_at="",
        # Perceive
        ocr_text="",
        bounding_boxes=[],
        page_count=0,
        forensics_flags=[],
        layout_summary="",
        # Understand
        document_type="unknown",
        extracted_json={},
        schema_used="",
        confidence_map=[],
        overall_confidence=0.0,
        validation=CausalValidationResult(
            passed=False, checks_run=[], failures=[], corrected_values={}
        ),
        # HITL
        needs_hitl=False,
        hitl_corrections={},
        hitl_reviewed_by=None,
        hitl_reviewed_at=None,
        # Connect
        embedding_id=None,
        graph_node_ids=[],
        linked_documents=[],
        anomaly_alerts=[],
        # Act
        action_log=[],
        routed_to=None,
        calendar_events_created=[],
        erp_push_status=None,
        # Meta
        error=None,
        pipeline_stage="idle",
    )
