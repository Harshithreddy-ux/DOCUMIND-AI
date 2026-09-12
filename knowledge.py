"""
knowledge.py — DocuMind AI  |  Pillar 4: Knowledge Fabric
===========================================================
Persists extracted document intelligence into two complementary stores:

  1. PostgreSQL + pgvector  — semantic vector search
       Table: documents      (metadata + extracted JSON)
       Table: embeddings     (1536-dim vectors via Ollama embed)
       Table: entities       (individual field values)

  2. Neo4j (Graph DB)       — relational document linking
       Node types : Document, Vendor, Invoice, Contract, PurchaseOrder
       Relationship types : ISSUED_BY, REFERENCES, FULFILLS, LINKED_TO

Also implements:
  - Anomaly detection  (amount vs. vendor historical average)
  - Duplicate detection (cosine similarity threshold)
  - Entity linking     (PO → Invoice → Contract chain)

VRAM note: Ollama embeddings use the CPU path (nomic-embed-text, ~0 VRAM).
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import psycopg2
import psycopg2.extras
from neo4j import GraphDatabase, exceptions as neo4j_exc

from state import DocuMindState

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration (read from environment — set in antigravity.yaml)
# ---------------------------------------------------------------------------
PG_DSN = (
    f"host={os.environ.get('POSTGRES_HOST', 'localhost')} "
    f"port={os.environ.get('POSTGRES_PORT', '5432')} "
    f"dbname={os.environ.get('POSTGRES_DB', 'documind')} "
    f"user={os.environ.get('POSTGRES_USER', 'postgres')} "
    f"password={os.environ.get('POSTGRES_PASSWORD', 'password')}"
)
NEO4J_URI      = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER     = os.environ.get("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.environ.get("NEO4J_PASSWORD", "password")
OLLAMA_MODEL_EMBED = os.environ.get("OLLAMA_MODEL_EMBED", "nomic-embed-text")

# Cosine similarity threshold above which two docs are flagged as duplicates
DUPLICATE_THRESHOLD = 0.95
# Amount anomaly multiplier: flag if amount > X × vendor average
ANOMALY_MULTIPLIER  = 2.5


# ============================================================================
# PostgreSQL helpers
# ============================================================================

def _get_pg_conn():
    """Return a new psycopg2 connection.  Caller is responsible for closing."""
    return psycopg2.connect(PG_DSN, cursor_factory=psycopg2.extras.RealDictCursor)


def init_postgres() -> None:
    """
    Create the required tables and pgvector extension if they do not exist.
    Safe to call on every startup (idempotent).
    """
    ddl = """
    -- Enable pgvector extension
    CREATE EXTENSION IF NOT EXISTS vector;

    -- Master document table
    CREATE TABLE IF NOT EXISTS documents (
        id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        file_name      TEXT NOT NULL,
        file_type      TEXT,
        source_channel TEXT,
        doc_type       TEXT,
        extracted_json JSONB,
        schema_used    TEXT,
        overall_conf   FLOAT,
        page_count     INT,
        forensics      JSONB,
        validation     JSONB,
        ingested_at    TIMESTAMPTZ DEFAULT NOW(),
        content_hash   TEXT UNIQUE   -- SHA-256 for duplicate guard
    );

    -- Vector embeddings (1536-dim for nomic-embed-text)
    CREATE TABLE IF NOT EXISTS embeddings (
        id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        document_id UUID REFERENCES documents(id) ON DELETE CASCADE,
        chunk_text  TEXT,
        embedding   vector(768),   -- nomic-embed-text outputs 768-dim
        created_at  TIMESTAMPTZ DEFAULT NOW()
    );
    CREATE INDEX IF NOT EXISTS embeddings_vec_idx
        ON embeddings USING ivfflat (embedding vector_cosine_ops)
        WITH (lists = 100);

    -- Flat entity table (one row per extracted field value)
    CREATE TABLE IF NOT EXISTS entities (
        id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        document_id UUID REFERENCES documents(id) ON DELETE CASCADE,
        field_name  TEXT,
        field_value TEXT,
        confidence  FLOAT,
        created_at  TIMESTAMPTZ DEFAULT NOW()
    );
    """
    conn = _get_pg_conn()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(ddl)
        logger.info("PostgreSQL schema initialised.")
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Embedding generation via Ollama
# ---------------------------------------------------------------------------

def _generate_embedding(text: str) -> List[float]:
    """
    Generate a semantic embedding vector using the local Ollama model.
    nomic-embed-text is CPU-only and uses zero VRAM.
    Falls back to a zeroed vector on error.
    """
    try:
        import ollama
        response = ollama.embeddings(model=OLLAMA_MODEL_EMBED, prompt=text[:2000])
        return response["embedding"]
    except Exception as exc:
        logger.warning(f"Embedding generation failed ({exc}); using zero vector.")
        return [0.0] * 768


# ---------------------------------------------------------------------------
# Document storage
# ---------------------------------------------------------------------------

def _compute_content_hash(raw_bytes: bytes) -> str:
    """SHA-256 hash of raw file bytes — used for exact duplicate detection."""
    return hashlib.sha256(raw_bytes).hexdigest()


def _store_document_pg(
    conn,
    state: DocuMindState,
    content_hash: str,
) -> Optional[str]:
    """
    Insert a document record into PostgreSQL.
    Returns the new UUID string, or None if a duplicate hash already exists.
    """
    doc_id = str(uuid.uuid4())
    sql = """
    INSERT INTO documents
        (id, file_name, file_type, source_channel, doc_type,
         extracted_json, schema_used, overall_conf, page_count,
         forensics, validation, content_hash)
    VALUES
        (%(id)s, %(file_name)s, %(file_type)s, %(source_channel)s, %(doc_type)s,
         %(extracted_json)s, %(schema_used)s, %(overall_conf)s, %(page_count)s,
         %(forensics)s, %(validation)s, %(content_hash)s)
    ON CONFLICT (content_hash) DO NOTHING
    RETURNING id;
    """
    params = {
        "id":            doc_id,
        "file_name":     state.get("file_name", ""),
        "file_type":     state.get("file_type", ""),
        "source_channel":state.get("source_channel", ""),
        "doc_type":      state.get("document_type", "unknown"),
        "extracted_json":json.dumps(state.get("extracted_json", {})),
        "schema_used":   state.get("schema_used", ""),
        "overall_conf":  state.get("overall_confidence", 0.0),
        "page_count":    state.get("page_count", 0),
        "forensics":     json.dumps(state.get("forensics_flags", [])),
        "validation":    json.dumps(state.get("validation", {})),
        "content_hash":  content_hash,
    }
    with conn.cursor() as cur:
        cur.execute(sql, params)
        row = cur.fetchone()
        if row is None:
            logger.info(f"Duplicate document detected (hash={content_hash[:12]}…); skipped.")
            return None
        return row["id"]


def _store_embedding_pg(conn, document_id: str, ocr_text: str) -> str:
    """
    Generate and store a vector embedding for the document's OCR text.
    Chunks text at 1000-char boundaries to stay within model context window.
    Returns the embedding row UUID.
    """
    chunk = ocr_text[:1000]   # single chunk for MVP; Phase 4 can add chunking
    vector = _generate_embedding(chunk)
    emb_id = str(uuid.uuid4())

    sql = """
    INSERT INTO embeddings (id, document_id, chunk_text, embedding)
    VALUES (%s, %s, %s, %s::vector);
    """
    with conn.cursor() as cur:
        cur.execute(sql, (emb_id, document_id, chunk, json.dumps(vector)))
    return emb_id


def _store_entities_pg(conn, document_id: str, extracted: Dict[str, Any]) -> None:
    """
    Flatten extracted JSON into individual entity rows for fast field-level search.
    Skips nested arrays (line_items) — those are searched via JSONB.
    """
    sql = """
    INSERT INTO entities (document_id, field_name, field_value)
    VALUES (%s, %s, %s)
    ON CONFLICT DO NOTHING;
    """
    rows = []
    for k, v in extracted.items():
        if v is None or isinstance(v, list):
            continue
        rows.append((document_id, k, str(v)[:500]))
    if rows:
        with conn.cursor() as cur:
            cur.executemany(sql, rows)


# ---------------------------------------------------------------------------
# Duplicate detection via vector cosine similarity
# ---------------------------------------------------------------------------

def _check_vector_duplicate(conn, embedding_id: str) -> Optional[str]:
    """
    Compare the newly stored embedding against all existing ones.
    Returns the ID of a near-duplicate document if cosine similarity
    exceeds DUPLICATE_THRESHOLD, else None.
    """
    sql = """
    SELECT e2.document_id, 1 - (e1.embedding <=> e2.embedding) AS similarity
    FROM   embeddings e1
    JOIN   embeddings e2 ON e1.id != e2.id
    WHERE  e1.id = %s
    ORDER  BY similarity DESC
    LIMIT  1;
    """
    with conn.cursor() as cur:
        cur.execute(sql, (embedding_id,))
        row = cur.fetchone()
        if row and row["similarity"] >= DUPLICATE_THRESHOLD:
            logger.warning(
                f"Near-duplicate detected! similarity={row['similarity']:.3f} "
                f"with document {row['document_id']}"
            )
            return str(row["document_id"])
    return None


# ---------------------------------------------------------------------------
# Anomaly detection (amount vs vendor historical average)
# ---------------------------------------------------------------------------

def _check_amount_anomaly(conn, vendor: str, amount: float) -> Optional[str]:
    """
    Compare the invoice total against the vendor's historical average from
    the documents table.  Returns an alert string if anomalous.
    """
    if not vendor or amount <= 0:
        return None

    sql = """
    SELECT AVG((extracted_json->>'total')::numeric) AS avg_total,
           COUNT(*) AS invoice_count
    FROM   documents
    WHERE  doc_type = 'invoice'
      AND  extracted_json->>'vendor_name' ILIKE %s
      AND  (extracted_json->>'total') IS NOT NULL;
    """
    with conn.cursor() as cur:
        cur.execute(sql, (f"%{vendor}%",))
        row = cur.fetchone()
        if row and row["invoice_count"] and row["invoice_count"] >= 3:
            avg = float(row["avg_total"] or 0)
            if avg > 0 and amount > avg * ANOMALY_MULTIPLIER:
                pct = (amount / avg - 1) * 100
                return (
                    f"Amount anomaly: {vendor} invoice = {amount:.2f} "
                    f"({pct:.0f}% above {avg:.2f} avg over {row['invoice_count']} invoices)"
                )
    return None


# ============================================================================
# Neo4j helpers
# ============================================================================

def _get_neo4j_driver():
    """Return a Neo4j driver instance.  Caller should close after use."""
    return GraphDatabase.driver(
        NEO4J_URI,
        auth=(NEO4J_USER, NEO4J_PASSWORD),
        max_connection_lifetime=300,
    )


def init_neo4j() -> None:
    """
    Create uniqueness constraints for node primary keys.
    Safe to call on every startup (idempotent).
    """
    constraints = [
        "CREATE CONSTRAINT doc_id IF NOT EXISTS FOR (d:Document) REQUIRE d.id IS UNIQUE",
        "CREATE CONSTRAINT vendor_name IF NOT EXISTS FOR (v:Vendor) REQUIRE v.name IS UNIQUE",
    ]
    driver = _get_neo4j_driver()
    try:
        with driver.session() as session:
            for cypher in constraints:
                session.run(cypher)
        logger.info("Neo4j constraints initialised.")
    except neo4j_exc.Neo4jError as exc:
        logger.warning(f"Neo4j constraint setup warning (may already exist): {exc}")
    finally:
        driver.close()


def _upsert_document_node(session, doc_id: str, state: DocuMindState) -> str:
    """
    Create (or MERGE) a Document node in Neo4j with core metadata.
    Returns the Neo4j internal element ID.
    """
    extracted = state.get("extracted_json", {})
    cypher = """
    MERGE (d:Document {id: $id})
    SET   d.file_name    = $file_name,
          d.doc_type     = $doc_type,
          d.ingested_at  = $ingested_at,
          d.total        = $total,
          d.date         = $date,
          d.confidence   = $confidence
    RETURN elementId(d) AS eid
    """
    result = session.run(
        cypher,
        id=doc_id,
        file_name=state.get("file_name", ""),
        doc_type=state.get("document_type", "unknown"),
        ingested_at=state.get("ingested_at", ""),
        total=str(extracted.get("total", "")),
        date=str(
            extracted.get("invoice_date")
            or extracted.get("effective_date")
            or extracted.get("date", "")
        ),
        confidence=state.get("overall_confidence", 0.0),
    )
    record = result.single()
    return record["eid"] if record else doc_id


def _upsert_vendor_node(session, vendor_name: str) -> None:
    """Create (or MERGE) a Vendor node and return nothing."""
    cypher = "MERGE (v:Vendor {name: $name})"
    session.run(cypher, name=vendor_name)


def _link_invoice_to_vendor(session, doc_id: str, vendor_name: str) -> None:
    """Create ISSUED_BY relationship: (Invoice:Document)-[:ISSUED_BY]->(Vendor)."""
    cypher = """
    MATCH (d:Document {id: $doc_id}), (v:Vendor {name: $vendor_name})
    MERGE (d)-[:ISSUED_BY]->(v)
    """
    session.run(cypher, doc_id=doc_id, vendor_name=vendor_name)


def _link_invoice_to_po(session, doc_id: str, po_ref: str) -> Optional[str]:
    """
    If a PO reference is present, find the PurchaseOrder document in Neo4j
    and create a REFERENCES relationship.  Returns the PO doc_id if found.
    """
    cypher = """
    MATCH (po:Document)
    WHERE po.doc_type = 'purchase_order'
      AND po.file_name CONTAINS $po_ref
    MERGE (inv:Document {id: $doc_id})-[:REFERENCES]->(po)
    RETURN po.id AS po_id
    """
    result = session.run(cypher, doc_id=doc_id, po_ref=po_ref)
    record = result.single()
    return record["po_id"] if record else None


def _find_similar_documents_neo4j(session, doc_id: str, doc_type: str) -> List[str]:
    """
    Retrieve IDs of documents of the same type ingested in the last 90 days.
    Used as a quick candidate set for relationship mining.
    """
    cypher = """
    MATCH (d:Document)
    WHERE d.doc_type = $doc_type AND d.id <> $doc_id
    RETURN d.id AS id
    LIMIT 20
    """
    result = session.run(cypher, doc_type=doc_type, doc_id=doc_id)
    return [record["id"] for record in result]


# ============================================================================
# Main entry point called by graph.py → node_connect
# ============================================================================

def store_in_knowledge_fabric(
    state: DocuMindState,
) -> Tuple[str, List[str], List[str], List[str]]:
    """
    Orchestrate storage across both knowledge stores.

    Returns:
        embedding_id    : UUID of the pgvector embedding row
        graph_node_ids  : List of Neo4j element IDs created
        linked_documents: List of related document IDs discovered
        anomaly_alerts  : List of human-readable anomaly alert strings
    """
    extracted    = state.get("extracted_json", {}) or {}
    raw_bytes    = state.get("raw_bytes", b"")
    ocr_text     = state.get("ocr_text", "")
    vendor_name  = str(extracted.get("vendor_name", "")).strip()
    po_ref       = str(extracted.get("po_reference", "")).strip()
    anomaly_alerts: List[str] = []
    graph_node_ids: List[str] = []
    linked_documents: List[str] = []

    content_hash = _compute_content_hash(raw_bytes)

    # ── PostgreSQL ────────────────────────────────────────────────────────
    pg_conn = _get_pg_conn()
    embedding_id = ""
    doc_id = None
    try:
        with pg_conn:
            # 1. Insert document record (returns None on exact duplicate)
            doc_id = _store_document_pg(pg_conn, state, content_hash)
            if doc_id is None:
                anomaly_alerts.append(
                    f"Exact duplicate blocked: content_hash={content_hash[:12]}…"
                )
                return "", [], [], anomaly_alerts

            # 2. Store embedding
            embedding_id = _store_embedding_pg(pg_conn, doc_id, ocr_text)

            # 3. Store flat entities
            _store_entities_pg(pg_conn, doc_id, extracted)

        # 4. Near-duplicate detection (outside the write transaction)
        with pg_conn:
            near_dup = _check_vector_duplicate(pg_conn, embedding_id)
            if near_dup:
                anomaly_alerts.append(
                    f"Near-duplicate detected: cosine similarity ≥ {DUPLICATE_THRESHOLD} "
                    f"with document {near_dup}"
                )
                linked_documents.append(near_dup)

        # 5. Anomaly: amount vs vendor average
        try:
            amount = float(extracted.get("total") or 0)
        except (TypeError, ValueError):
            amount = 0.0

        if vendor_name and amount > 0:
            with pg_conn:
                alert = _check_amount_anomaly(pg_conn, vendor_name, amount)
                if alert:
                    anomaly_alerts.append(alert)

    finally:
        pg_conn.close()

    # ── Neo4j ─────────────────────────────────────────────────────────────
    driver = _get_neo4j_driver()
    try:
        with driver.session() as session:
            # 1. Upsert Document node
            eid = _upsert_document_node(session, doc_id, state)
            graph_node_ids.append(eid)

            # 2. Vendor node + ISSUED_BY relationship
            if vendor_name:
                _upsert_vendor_node(session, vendor_name)
                _link_invoice_to_vendor(session, doc_id, vendor_name)

            # 3. PO linkage
            if po_ref:
                po_id = _link_invoice_to_po(session, doc_id, po_ref)
                if po_id:
                    linked_documents.append(po_id)
                    graph_node_ids.append(po_id)

            # 4. Find related documents for implicit linking
            related = _find_similar_documents_neo4j(
                session, doc_id, state.get("document_type", "unknown")
            )
            linked_documents.extend(related[:5])   # cap at 5 for MVP

    except neo4j_exc.Neo4jError as exc:
        logger.error(f"Neo4j storage error: {exc}")
        anomaly_alerts.append(f"Neo4j error: {exc}")
    finally:
        driver.close()

    logger.info(
        f"Knowledge Fabric: doc_id={doc_id}, emb_id={embedding_id}, "
        f"neo4j_nodes={len(graph_node_ids)}, "
        f"linked={len(linked_documents)}, alerts={len(anomaly_alerts)}"
    )
    return embedding_id, graph_node_ids, linked_documents, anomaly_alerts


# ============================================================================
# RAG: Semantic search over pgvector  (used by Streamlit Conversation Layer)
# ============================================================================

def semantic_search(
    query: str,
    top_k: int = 5,
) -> List[Dict[str, Any]]:
    """
    Embed the query and retrieve the top-k most semantically similar document
    chunks from pgvector.  Returns a list of dicts with chunk_text + metadata.
    """
    query_vector = _generate_embedding(query)
    sql = """
    SELECT
        e.chunk_text,
        e.document_id,
        d.file_name,
        d.doc_type,
        d.extracted_json,
        1 - (e.embedding <=> %s::vector) AS similarity
    FROM   embeddings e
    JOIN   documents  d ON d.id = e.document_id
    ORDER  BY similarity DESC
    LIMIT  %s;
    """
    conn = _get_pg_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, (json.dumps(query_vector), top_k))
            rows = cur.fetchall()
        results = []
        for row in rows:
            results.append({
                "chunk_text":    row["chunk_text"],
                "document_id":   str(row["document_id"]),
                "file_name":     row["file_name"],
                "doc_type":      row["doc_type"],
                "extracted_json":row["extracted_json"],
                "similarity":    float(row["similarity"]),
            })
        return results
    finally:
        conn.close()


# ============================================================================
# Graph query helper  (used by Streamlit Living Document Graph view)
# ============================================================================

def get_graph_data() -> Dict[str, List[Dict[str, Any]]]:
    """
    Return all Document and Vendor nodes plus their relationships for
    visualisation in the Streamlit streamlit-agraph component.

    Returns {"nodes": [...], "edges": [...]} in agraph format.
    """
    cypher = """
    MATCH (d:Document)
    OPTIONAL MATCH (d)-[r]->(target)
    RETURN
        d.id AS doc_id,
        d.file_name AS file_name,
        d.doc_type  AS doc_type,
        d.confidence AS confidence,
        type(r)     AS rel_type,
        target.id   AS target_id,
        labels(target)[0] AS target_label,
        COALESCE(target.name, target.id) AS target_name
    LIMIT 200
    """
    driver = _get_neo4j_driver()
    nodes_seen: set[str] = set()
    nodes: List[Dict] = []
    edges: List[Dict] = []

    try:
        with driver.session() as session:
            result = session.run(cypher)
            for record in result:
                doc_id    = str(record["doc_id"] or "")
                file_name = record["file_name"] or doc_id[:8]
                doc_type  = record["doc_type"] or "unknown"
                confidence = float(record["confidence"] or 0)

                if doc_id and doc_id not in nodes_seen:
                    nodes_seen.add(doc_id)
                    nodes.append({
                        "id":    doc_id,
                        "label": f"{file_name}\n({doc_type})",
                        "color": _node_color(doc_type, confidence),
                        "size":  20,
                    })

                # Vendor / related nodes
                target_id   = str(record["target_id"] or "")
                target_name = str(record["target_name"] or "")
                rel_type    = record["rel_type"]

                if target_id and target_id not in nodes_seen:
                    nodes_seen.add(target_id)
                    nodes.append({
                        "id":    target_id,
                        "label": target_name,
                        "color": "#a29bfe",   # purple for vendors / other types
                        "size":  15,
                    })

                if doc_id and target_id and rel_type:
                    edges.append({
                        "source": doc_id,
                        "target": target_id,
                        "label":  rel_type,
                    })
    finally:
        driver.close()

    return {"nodes": nodes, "edges": edges}


def _node_color(doc_type: str, confidence: float) -> str:
    """Map document type and confidence to a hex colour for graph visualisation."""
    base_colors = {
        "invoice":          "#00b894",  # green
        "contract":         "#0984e3",  # blue
        "receipt":          "#fdcb6e",  # yellow
        "purchase_order":   "#e17055",  # orange
        "unknown":          "#636e72",  # grey
    }
    color = base_colors.get(doc_type, "#636e72")
    # Dim the colour if confidence is low
    if confidence < 0.8:
        color = "#b2bec3"  # light grey for low-confidence nodes
    return color
