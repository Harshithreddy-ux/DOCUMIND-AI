"""
graph.py — DocuMind AI  |  LangGraph State Machine
====================================================
Assembles the full LangGraph pipeline:

  ingest ──► perceive ──► understand ──► [conditional] ──► connect ──► act
                                                │
                                         (conf < 80%)
                                                │
                                         human_review ──► connect ──► act

Nodes are pure Python functions that receive the full DocuMindState and
return a PARTIAL dict (only the keys they mutate).  LangGraph merges them.

The conditional edge is the key innovation: it routes low-confidence
extractions to a human_review staging area (Streamlit HITL screen)
instead of blindly storing bad data in the knowledge fabric.
"""

from __future__ import annotations

import datetime
import logging
from typing import Annotated, Any, Dict, Literal

from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages  # noqa: F401 (may be used later)

from cognition import (
    classify_document,
    extract_fields,
    score_confidence,
    synthesize_schema,
    validate_causally,
    CONFIDENCE_THRESHOLD,
)
from perception import run_perception
from state import DocuMindState, empty_state

logger = logging.getLogger(__name__)


# ============================================================================
# NODE DEFINITIONS
# Each node receives the FULL state and returns a PARTIAL update dict.
# ============================================================================

# ---------------------------------------------------------------------------
# Node 1: ingest
# ---------------------------------------------------------------------------
def node_ingest(state: DocuMindState) -> Dict[str, Any]:
    """
    Normalise and stamp the incoming document.
    In a real system this would also de-duplicate (hash check) against
    the document store.  Here we set the timestamp and priority.
    """
    logger.info(f"[ingest] Processing: {state['file_name']} from {state['source_channel']}")

    # Derive file type from extension if not already set
    file_type = state.get("file_type", "")
    if not file_type and state.get("file_name"):
        ext = state["file_name"].rsplit(".", 1)[-1].lower()
        file_type = ext if ext in {"pdf", "png", "jpg", "jpeg"} else "pdf"

    # Smart priority scoring: PDFs > 500 KB get higher priority
    size_kb = len(state.get("raw_bytes", b"")) / 1024
    priority = state.get("priority", 2)
    if size_kb > 500 and priority == 2:
        priority = 1   # bump up large files

    return {
        "file_type": file_type,
        "priority": priority,
        "ingested_at": datetime.datetime.utcnow().isoformat() + "Z",
        "pipeline_stage": "ingested",
        "action_log": [f"Ingested '{state['file_name']}' ({size_kb:.1f} KB) via {state['source_channel']}"],
    }


# ---------------------------------------------------------------------------
# Node 2: perceive
# ---------------------------------------------------------------------------
def node_perceive(state: DocuMindState) -> Dict[str, Any]:
    """
    Run the full Perception Engine (OCR + Layout + Forensics).
    Delegates to perception.run_perception().
    """
    logger.info(f"[perceive] Running OCR + Layout on {state['file_name']}")
    try:
        result = run_perception(
            raw_bytes=state["raw_bytes"],
            file_type=state["file_type"],
        )
        result["action_log"] = state.get("action_log", []) + [
            f"Perceived: {result['page_count']} page(s), "
            f"{len(result['bounding_boxes'])} text blocks, "
            f"{len(result['forensics_flags'])} forensics flags."
        ]
        return result
    except Exception as exc:
        logger.error(f"[perceive] Failed: {exc}", exc_info=True)
        return {
            "error": f"Perception failed: {exc}",
            "pipeline_stage": "error",
        }


# ---------------------------------------------------------------------------
# Node 3: understand  (Cognition Core)
# ---------------------------------------------------------------------------
def node_understand(state: DocuMindState) -> Dict[str, Any]:
    """
    Run the full Cognition Core:
      classify → synthesize schema → extract fields →
      causal validation → confidence scoring → HITL flag
    """
    logger.info(f"[understand] Running Cognition Core on {state['file_name']}")
    ocr_text = state.get("ocr_text", "")

    if not ocr_text.strip():
        return {
            "error": "OCR text is empty — cannot run cognition",
            "pipeline_stage": "error",
        }

    try:
        # 1. Classify
        doc_type = classify_document(ocr_text)

        # 2. Synthesize schema (few-shot examples can be injected via state later)
        schema_name, schema = synthesize_schema(ocr_text, doc_type)

        # 3. Extract fields
        extracted = extract_fields(ocr_text, schema, doc_type)

        # 4. Causal validation
        validation = validate_causally(extracted)

        # Apply causal corrections (do not overwrite if human already reviewed)
        if validation["corrected_values"] and not state.get("hitl_corrections"):
            extracted.update(validation["corrected_values"])

        # 5. Confidence scoring
        confidence_map, overall_conf = score_confidence(
            extracted=extracted,
            bounding_boxes=state.get("bounding_boxes", []),
            schema=schema,
            validation=validation,
        )

        # 6. Determine if HITL is needed
        needs_hitl = overall_conf < CONFIDENCE_THRESHOLD or not validation["passed"]

        logger.info(
            f"[understand] doc_type={doc_type}, overall_conf={overall_conf:.2%}, "
            f"needs_hitl={needs_hitl}"
        )

        return {
            "document_type": doc_type,
            "schema_used": schema_name,
            "extracted_json": extracted,
            "confidence_map": confidence_map,
            "overall_confidence": overall_conf,
            "validation": validation,
            "needs_hitl": needs_hitl,
            "pipeline_stage": "understood",
            "action_log": state.get("action_log", []) + [
                f"Extracted {len(extracted)} fields ({doc_type}), "
                f"confidence={overall_conf:.0%}, hitl_needed={needs_hitl}"
            ],
        }

    except Exception as exc:
        logger.error(f"[understand] Failed: {exc}", exc_info=True)
        return {
            "error": f"Cognition failed: {exc}",
            "pipeline_stage": "error",
        }


# ---------------------------------------------------------------------------
# Node 4: human_review  (HITL staging area)
# ---------------------------------------------------------------------------
def node_human_review(state: DocuMindState) -> Dict[str, Any]:
    """
    Pauses the graph and signals the Streamlit UI to display the HITL screen.

    In production this would use LangGraph's interrupt() mechanism (v0.2+).
    Here we set a flag that the Streamlit app polls.  The app then:
      1. Shows the PDF alongside the low-confidence JSON.
      2. Lets the user correct fields.
      3. Writes hitl_corrections into the state and resumes the graph.

    This node itself is a no-op — it just updates the stage label.
    The actual wait/resume is handled by the Streamlit runner in main.py.
    """
    logger.info(f"[human_review] Document halted for HITL: {state['file_name']}")

    # If the human has already reviewed (hitl_corrections is populated),
    # merge the corrections into extracted_json and clear the flag.
    corrections = state.get("hitl_corrections") or {}
    if corrections:
        merged = {**state.get("extracted_json", {}), **corrections}
        # Re-score confidence after human corrections (all corrected fields → 1.0)
        for fc in state.get("confidence_map", []):
            if fc["field_name"] in corrections:
                fc["final_score"] = 1.0
                fc["needs_review"] = False

        logger.info(f"[human_review] Merged {len(corrections)} human corrections")
        return {
            "extracted_json": merged,
            "needs_hitl": False,
            "pipeline_stage": "hitl_complete",
            "action_log": state.get("action_log", []) + [
                f"Human reviewed: {len(corrections)} field(s) corrected by "
                f"{state.get('hitl_reviewed_by', 'user')}"
            ],
        }

    # No corrections yet — remain in HITL staging
    return {
        "pipeline_stage": "awaiting_hitl",
        "action_log": state.get("action_log", []) + [
            "Routed to HITL: overall confidence below threshold or causal check failed."
        ],
    }


# ---------------------------------------------------------------------------
# Node 5: connect  (Knowledge Fabric)
# ---------------------------------------------------------------------------
def node_connect(state: DocuMindState) -> Dict[str, Any]:
    """
    Persist the validated extraction into pgvector and Neo4j.
    Full implementation is in knowledge.py — this node is the LangGraph
    wrapper that calls those functions and updates state.
    """
    logger.info(f"[connect] Persisting to Knowledge Fabric: {state['file_name']}")
    try:
        # knowledge.py is imported here to avoid circular deps at module load
        from knowledge import store_in_knowledge_fabric

        embedding_id, graph_node_ids, linked_docs, anomaly_alerts = (
            store_in_knowledge_fabric(state)
        )

        return {
            "embedding_id": embedding_id,
            "graph_node_ids": graph_node_ids,
            "linked_documents": linked_docs,
            "anomaly_alerts": anomaly_alerts,
            "pipeline_stage": "connected",
            "action_log": state.get("action_log", []) + [
                f"Stored in pgvector (id={embedding_id}), "
                f"Neo4j ({len(graph_node_ids)} nodes), "
                f"{len(linked_docs)} linked docs, "
                f"{len(anomaly_alerts)} anomaly alerts."
            ],
        }
    except Exception as exc:
        logger.error(f"[connect] Failed: {exc}", exc_info=True)
        return {
            "error": f"Knowledge Fabric persistence failed: {exc}",
            "pipeline_stage": "error",
        }


# ---------------------------------------------------------------------------
# Node 6: act  (Automation Mesh — stub, Phase 4 will expand this)
# ---------------------------------------------------------------------------
def node_act(state: DocuMindState) -> Dict[str, Any]:
    """
    Automation Mesh entry point.
    Dispatches: smart routing, alert generation, calendar sync stubs.
    Full implementation in Phase 4; here we just log the decision.
    """
    logger.info(f"[act] Executing automation for {state['file_name']}")
    actions_taken: list[str] = []

    # Smart routing by document type and amount
    extracted = state.get("extracted_json", {})
    total = extracted.get("total")
    doc_type = state.get("document_type", "unknown")

    if doc_type == "invoice" and total:
        try:
            routed_to = "CFO" if float(total) >= 50000 else "AP_clerk"
        except (TypeError, ValueError):
            routed_to = "AP_clerk"
        actions_taken.append(f"Routed {doc_type} (total={total}) to {routed_to}")
    else:
        routed_to = "AP_clerk"

    # Anomaly alerts
    for alert in state.get("anomaly_alerts", []):
        actions_taken.append(f"ALERT: {alert}")

    # Causal failures
    for failure in (state.get("validation") or {}).get("failures", []):
        actions_taken.append(f"CAUSAL FAILURE: {failure}")

    return {
        "routed_to": routed_to,
        "pipeline_stage": "complete",
        "action_log": state.get("action_log", []) + actions_taken,
    }


# ============================================================================
# CONDITIONAL ROUTING EDGE
# ============================================================================

def route_after_understand(
    state: DocuMindState,
) -> Literal["human_review", "connect"]:
    """
    The key branching decision:
      - If overall_confidence < CONFIDENCE_THRESHOLD OR causal checks failed
        → route to human_review (HITL)
      - Otherwise → route directly to connect (Knowledge Fabric)

    This is the heart of DocuMind's Self-Healing / HITL Innovation (#3).
    """
    if state.get("needs_hitl", False):
        logger.info(
            f"Routing to HITL: conf={state.get('overall_confidence', 0):.0%} "
            f"< threshold={CONFIDENCE_THRESHOLD:.0%}"
        )
        return "human_review"

    logger.info(
        f"Routing to connect: conf={state.get('overall_confidence', 0):.0%} "
        f"≥ threshold={CONFIDENCE_THRESHOLD:.0%}"
    )
    return "connect"


def route_after_human_review(
    state: DocuMindState,
) -> Literal["connect", "awaiting_hitl"]:
    """
    After the human_review node runs:
      - If corrections have been applied (needs_hitl is now False) → connect
      - If still waiting (no corrections yet) → END (Streamlit will re-trigger)
    """
    if not state.get("needs_hitl", True):
        return "connect"
    # Remain pending — the Streamlit app will re-invoke the graph
    return "awaiting_hitl"


# ============================================================================
# GRAPH ASSEMBLY
# ============================================================================

def build_graph() -> StateGraph:
    """
    Construct and compile the DocuMind LangGraph StateGraph.

    Graph topology:
        __start__ → ingest → perceive → understand →
          [conditional: needs_hitl?]
            YES → human_review → [conditional: corrections ready?]
                    YES → connect → act → __end__
                    NO  → __end__  (Streamlit re-triggers when ready)
            NO  → connect → act → __end__
    """
    graph = StateGraph(DocuMindState)

    # ── Add all nodes ────────────────────────────────────────────────────
    graph.add_node("ingest",        node_ingest)
    graph.add_node("perceive",      node_perceive)
    graph.add_node("understand",    node_understand)
    graph.add_node("human_review",  node_human_review)
    graph.add_node("connect",       node_connect)
    graph.add_node("act",           node_act)

    # ── Linear edges ────────────────────────────────────────────────────
    graph.add_edge("ingest",   "perceive")
    graph.add_edge("perceive", "understand")
    graph.add_edge("connect",  "act")
    graph.add_edge("act",      END)

    # ── Conditional edge: after understand ──────────────────────────────
    graph.add_conditional_edges(
        "understand",
        route_after_understand,
        {
            "human_review": "human_review",
            "connect":      "connect",
        },
    )

    # ── Conditional edge: after human_review ────────────────────────────
    graph.add_conditional_edges(
        "human_review",
        route_after_human_review,
        {
            "connect":       "connect",
            "awaiting_hitl": END,   # graph halts; Streamlit re-triggers with corrections
        },
    )

    # ── Entry point ──────────────────────────────────────────────────────
    graph.set_entry_point("ingest")

    compiled = graph.compile()
    logger.info("DocuMind LangGraph compiled successfully.")
    return compiled


# ── Module-level singleton (import once, reuse) ──────────────────────────────
DOCUMIND_GRAPH = build_graph()


# ============================================================================
# Convenience runner (used by FastAPI and Streamlit)
# ============================================================================

def run_pipeline(
    file_name: str,
    raw_bytes: bytes,
    file_type: str = "pdf",
    source_channel: str = "web_upload",
    priority: int = 2,
) -> DocuMindState:
    """
    Initialise an empty state, populate the ingest fields, and run the graph.
    Returns the final state dict.
    """
    initial_state = empty_state()
    initial_state.update({
        "file_name":      file_name,
        "raw_bytes":      raw_bytes,
        "file_type":      file_type,
        "source_channel": source_channel,
        "priority":       priority,
    })

    final_state = DOCUMIND_GRAPH.invoke(initial_state)
    return final_state


def resume_after_hitl(
    state: DocuMindState,
    corrections: Dict[str, Any],
    reviewed_by: str = "user",
) -> DocuMindState:
    """
    Resume a graph that halted at the HITL node by injecting human corrections
    and re-running from the human_review node forward.
    """
    import datetime

    state.update({
        "hitl_corrections":  corrections,
        "hitl_reviewed_by":  reviewed_by,
        "hitl_reviewed_at":  datetime.datetime.utcnow().isoformat() + "Z",
        "needs_hitl":        True,   # node_human_review will flip this to False
    })

    # Re-run from human_review node
    final_state = DOCUMIND_GRAPH.invoke(state)
    return final_state
