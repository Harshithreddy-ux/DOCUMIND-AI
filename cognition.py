"""
cognition.py — DocuMind AI  |  Pillar 3: Cognition Core
=========================================================
The AI brain: Few-Shot Schema Synthesis + Causal Validation + Confidence Scoring.

Optimised for 4-bit quantised models running on Ollama (≤ 4 GB VRAM).
Prompts are kept deliberately concise (< 400 tokens) to work well with
small models like gemma2:2b-instruct-q4_K_M or nemotron-mini.

Pipeline steps:
  1. classify_document  — identify doc type from OCR text
  2. synthesize_schema  — infer extraction schema (few-shot if needed)
  3. extract_fields     — run LLM extraction → structured JSON
  4. validate_causally  — math consistency checks (Subtotal+Tax==Total etc.)
  5. score_confidence   — compute per-field confidence waterfall
"""

from __future__ import annotations

import json
import logging
import math
import os
import re
from typing import Any, Dict, List, Optional, Tuple

import ollama  # pip install ollama

from state import CausalValidationResult, FieldConfidence

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "gemma2:2b-instruct-q4_K_M")  # ≤ 1.5 GB VRAM
OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
CONFIDENCE_THRESHOLD = 0.80   # Below this → needs_hitl = True

# ---------------------------------------------------------------------------
# Pre-defined extraction schemas for known document types
# ---------------------------------------------------------------------------
KNOWN_SCHEMAS: Dict[str, Dict[str, str]] = {
    "invoice": {
        "vendor_name": "string",
        "invoice_number": "string",
        "invoice_date": "date (YYYY-MM-DD)",
        "due_date": "date (YYYY-MM-DD)",
        "line_items": "array of {description, quantity, unit_price, line_total}",
        "subtotal": "number",
        "tax": "number",
        "discount": "number",
        "total": "number",
        "currency": "string (3-letter ISO code)",
        "payment_terms": "string",
        "po_reference": "string or null",
    },
    "contract": {
        "parties": "array of strings",
        "effective_date": "date (YYYY-MM-DD)",
        "expiry_date": "date (YYYY-MM-DD) or null",
        "auto_renewal": "boolean",
        "payment_terms": "string or null",
        "governing_law": "string",
        "liability_cap": "number or null",
        "key_obligations": "array of strings",
    },
    "receipt": {
        "merchant_name": "string",
        "date": "date (YYYY-MM-DD)",
        "items": "array of {description, amount}",
        "subtotal": "number",
        "tax": "number",
        "total": "number",
        "payment_method": "string",
    },
}


# ---------------------------------------------------------------------------
# Step 1: Classify document type
# ---------------------------------------------------------------------------

def classify_document(ocr_text: str) -> str:
    """
    Use the local LLM to classify the document into one of the known types
    or return 'unknown'.  Prompt is minimal for small-model compatibility.
    """
    # Fast heuristic pass before calling LLM (saves ~1-2 s per doc)
    text_lower = ocr_text.lower()
    if any(kw in text_lower for kw in ["invoice", "bill to", "amount due", "invoice #"]):
        return "invoice"
    if any(kw in text_lower for kw in ["agreement", "whereas", "hereinafter", "contract"]):
        return "contract"
    if any(kw in text_lower for kw in ["receipt", "thank you for your purchase", "transaction id"]):
        return "receipt"

    # LLM fallback
    prompt = (
        "Classify the document. Reply with exactly one word from: "
        "invoice, contract, receipt, purchase_order, unknown.\n\n"
        f"TEXT (first 400 chars):\n{ocr_text[:400]}"
    )
    try:
        response = _call_ollama(prompt, max_tokens=10)
        doc_type = response.strip().lower().split()[0]
        if doc_type not in KNOWN_SCHEMAS:
            doc_type = "unknown"
        logger.info(f"Document classified as: {doc_type}")
        return doc_type
    except Exception as exc:
        logger.warning(f"Classification LLM call failed ({exc}); defaulting to 'unknown'")
        return "unknown"


# ---------------------------------------------------------------------------
# Step 2: Few-Shot Schema Synthesis (Innovation #1)
# ---------------------------------------------------------------------------

def synthesize_schema(
    ocr_text: str,
    doc_type: str,
    few_shot_examples: Optional[List[Dict[str, Any]]] = None,
) -> Tuple[str, Dict[str, str]]:
    """
    Return (schema_name, schema_dict).

    If doc_type is known → return the pre-defined schema from KNOWN_SCHEMAS.
    If doc_type is 'unknown' AND few_shot_examples are provided (2-3 labelled
    samples), ask the LLM to infer a schema from those examples.
    If no examples → ask the LLM to infer schema from the OCR text alone.

    Prompt is engineered to elicit a concise JSON schema from small models.
    """
    if doc_type in KNOWN_SCHEMAS:
        return doc_type, KNOWN_SCHEMAS[doc_type]

    # Build few-shot block
    examples_block = ""
    if few_shot_examples:
        for i, ex in enumerate(few_shot_examples[:3], 1):
            examples_block += f"\nExample {i}:\n{json.dumps(ex, indent=2)}\n"

    prompt = (
        "You are a document schema expert. "
        "Given the document text below"
        + (" and example extractions", "")[not examples_block]
        + ", output ONLY a JSON object whose keys are field names "
        "and values are type descriptions (string, number, date, boolean, array).\n"
        + (f"\nExamples:\n{examples_block}" if examples_block else "")
        + f"\nDocument text (first 600 chars):\n{ocr_text[:600]}\n\nSchema JSON:"
    )

    try:
        raw = _call_ollama(prompt, max_tokens=300)
        schema = _parse_json_from_response(raw)
        if not isinstance(schema, dict) or len(schema) < 2:
            raise ValueError("Schema has fewer than 2 fields — likely parse failure")
        logger.info(f"Few-shot schema synthesised with {len(schema)} fields")
        return "synthesized", schema
    except Exception as exc:
        logger.warning(f"Schema synthesis failed ({exc}); using fallback")
        # Bare-minimum fallback schema
        return "fallback", {"raw_text": "string", "date": "date", "amount": "number"}


# ---------------------------------------------------------------------------
# Step 3: LLM Field Extraction
# ---------------------------------------------------------------------------

def extract_fields(
    ocr_text: str,
    schema: Dict[str, str],
    doc_type: str,
) -> Dict[str, Any]:
    """
    Use the local LLM to extract structured fields from OCR text according
    to the provided schema.  Returns a plain Python dict.

    Prompt engineering tips for 4-bit quantised models:
      - Be explicit: "output ONLY valid JSON, no prose"
      - Include the schema inline as a concise reference
      - Keep the OCR text window short (≤ 1 200 chars) to avoid hallucination
    """
    schema_str = ", ".join(f'"{k}": {v}' for k, v in list(schema.items())[:12])

    prompt = (
        f"Extract fields from this {doc_type} document.\n"
        f"Output ONLY valid JSON with these keys: {{{schema_str}}}.\n"
        "Use null for missing fields. No explanations.\n\n"
        f"DOCUMENT TEXT:\n{ocr_text[:1200]}\n\nJSON:"
    )

    try:
        raw = _call_ollama(prompt, max_tokens=600)
        extracted = _parse_json_from_response(raw)
        logger.info(f"Extracted {len(extracted)} fields from {doc_type}")
        return extracted
    except Exception as exc:
        logger.error(f"Field extraction failed: {exc}")
        return {}


def _num(val: Any, default: float = 0.0) -> float:
    try:
        return float(val) if val is not None else default
    except (TypeError, ValueError):
        return default


def _close(a: float, b: float, tol: float = 0.02) -> bool:
    """True if |a - b| <= tol (handles small floating-point rounding)."""
    return math.isclose(a, b, rel_tol=0.001, abs_tol=tol)


# ---------------------------------------------------------------------------
# Step 4: Causal Validator (Innovation #2 component)
# ---------------------------------------------------------------------------

def validate_causally(extracted: Dict[str, Any]) -> CausalValidationResult:
    """
    Run deterministic math-consistency checks on numeric fields.

    Checks performed (skipped gracefully if fields are missing / null):
      1. subtotal + tax - discount == total
      2. sum(line_item.line_total) == subtotal
      3. quantity * unit_price == line_total  (per line item)

    Returns a CausalValidationResult with per-check pass/fail details.
    """
    checks_run: List[str] = []
    failures: List[str] = []
    corrected: Dict[str, Any] = {}

    # ── Check 1: subtotal + tax - discount == total ─────────────────────
    subtotal = _num(extracted.get("subtotal"))
    tax      = _num(extracted.get("tax"))
    discount = _num(extracted.get("discount"))
    total    = _num(extracted.get("total"))

    if any(extracted.get(k) is not None for k in ("subtotal", "tax", "total")):
        checks_run.append("subtotal + tax - discount == total")
        computed_total = subtotal + tax - discount
        if not _close(computed_total, total):
            failures.append(
                f"Total mismatch: {subtotal} + {tax} - {discount} = "
                f"{computed_total:.2f} ≠ stated {total:.2f}"
            )
            corrected["total"] = round(computed_total, 2)

    # ── Check 2: sum(line_totals) == subtotal ───────────────────────────
    line_items = extracted.get("line_items") or extracted.get("items") or []
    if isinstance(line_items, list) and line_items and subtotal > 0:
        checks_run.append("sum(line_item.line_total) == subtotal")
        line_sum = sum(_num(item.get("line_total", item.get("amount"))) for item in line_items)
        if not _close(line_sum, subtotal):
            failures.append(
                f"Line-item sum mismatch: Σ line_totals = {line_sum:.2f} ≠ subtotal {subtotal:.2f}"
            )
            corrected["subtotal"] = round(line_sum, 2)

    # ── Check 3: qty × unit_price == line_total (per item) ──────────────
    for i, item in enumerate(line_items):
        if isinstance(item, dict):
            qty = _num(item.get("quantity"))
            price = _num(item.get("unit_price"))
            lt = _num(item.get("line_total"))
            if qty > 0 and price > 0 and lt > 0:
                checks_run.append(f"line_items[{i}]: qty*price == line_total")
                if not _close(qty * price, lt):
                    failures.append(
                        f"Line item {i} qty*price: {qty}×{price}={qty*price:.2f} ≠ {lt:.2f}"
                    )

    passed = len(failures) == 0
    logger.info(
        f"Causal validation: {len(checks_run)} checks, "
        f"{len(failures)} failures, passed={passed}"
    )

    return CausalValidationResult(
        passed=passed,
        checks_run=checks_run,
        failures=failures,
        corrected_values=corrected,
    )


# ---------------------------------------------------------------------------
# Step 5: Hierarchical Confidence Scoring
# ---------------------------------------------------------------------------

def score_confidence(
    extracted: Dict[str, Any],
    bounding_boxes: List[Any],   # List[BoundingBox] from state
    schema: Dict[str, str],
    validation: CausalValidationResult,
) -> Tuple[List[FieldConfidence], float]:
    """
    For each extracted field, compute a multiplicative confidence score:
        final = OCR_conf × layout_conf × llm_conf × cross_val_conf

    Returns (List[FieldConfidence], overall_mean_confidence).
    """
    # Pre-index bounding boxes by normalised text for fast lookup
    bbox_index: Dict[str, float] = {}
    for bb in bounding_boxes:
        key = (bb["text"] or "").strip().lower()[:30]
        if key:
            # Keep the max confidence if the same text appears multiple times
            bbox_index[key] = max(bbox_index.get(key, 0.0), bb["ocr_conf"])

    conf_list: List[FieldConfidence] = []

    for field_name, raw_value in extracted.items():
        if raw_value is None:
            continue

        value_str = str(raw_value).strip()

        # OCR confidence — look up the field value in the bbox index
        ocr_conf = _lookup_ocr_conf(value_str, bbox_index)

        # Layout confidence — numeric fields in known positions get a bonus
        layout_conf = _layout_conf_heuristic(field_name, value_str, schema)

        # LLM confidence — proxy: how well-defined the field type is
        llm_conf = _llm_conf_heuristic(field_name, raw_value, schema)

        # Cross-validation confidence — penalise fields that failed causal checks
        cross_val_conf = _cross_val_conf(field_name, validation)

        final = ocr_conf * layout_conf * llm_conf * cross_val_conf

        fc: FieldConfidence = FieldConfidence(
            field_name=field_name,
            raw_value=value_str,
            ocr_confidence=round(ocr_conf, 4),
            layout_confidence=round(layout_conf, 4),
            llm_confidence=round(llm_conf, 4),
            cross_val_confidence=round(cross_val_conf, 4),
            final_score=round(final, 4),
            needs_review=final < CONFIDENCE_THRESHOLD,
        )
        conf_list.append(fc)

    overall = (
        float(sum(f["final_score"] for f in conf_list) / len(conf_list))
        if conf_list
        else 0.0
    )
    return conf_list, round(overall, 4)


# ---------------------------------------------------------------------------
# Confidence sub-helpers
# ---------------------------------------------------------------------------

def _lookup_ocr_conf(value: str, bbox_index: Dict[str, float]) -> float:
    """Find the best OCR confidence for a given extracted value string."""
    key = value.lower()[:30]
    # Exact match
    if key in bbox_index:
        return bbox_index[key]
    # Partial match (first 10 chars)
    for k, v in bbox_index.items():
        if key[:10] and key[:10] in k:
            return v * 0.9   # slight penalty for partial match
    return 0.75  # default if value not traceable to OCR output


def _layout_conf_heuristic(field: str, value: str, schema: Dict[str, str]) -> float:
    """Heuristic: numeric fields like 'total', 'tax' are usually clearly placed."""
    field_type = schema.get(field, "string").lower()
    if "number" in field_type:
        # Try to verify the value looks numeric
        cleaned = re.sub(r"[,$€£ ]", "", value)
        try:
            float(cleaned)
            return 0.92
        except ValueError:
            return 0.55   # field says number but value isn't numeric
    if "date" in field_type:
        # Simple date pattern check
        if re.search(r"\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/\d{2,4}", value):
            return 0.90
        return 0.60
    return 0.85   # string/array fields — neutral


def _llm_conf_heuristic(field: str, value: Any, schema: Dict[str, str]) -> float:
    """Proxy for LLM confidence: check if value type matches schema expectation."""
    expected_type = schema.get(field, "string").lower()
    if value is None:
        return 0.5
    if "number" in expected_type:
        cleaned = re.sub(r"[,$€£ ]", "", str(value))
        try:
            float(cleaned)
            return 0.95
        except ValueError:
            return 0.45
    if "boolean" in expected_type:
        return 0.95 if isinstance(value, bool) else 0.6
    if "array" in expected_type:
        return 0.90 if isinstance(value, list) else 0.50
    return 0.88   # string — generally reliable


def _cross_val_conf(field: str, validation: CausalValidationResult) -> float:
    """
    Reduce confidence for fields that appear in the causal validation failures.
    Fields not involved in any check retain full confidence.
    """
    if not validation["failures"]:
        return 1.0
    for failure in validation["failures"]:
        # Check if the field name is mentioned in a failure description
        if field in failure.lower():
            return 0.50
    return 1.0


# ---------------------------------------------------------------------------
# Ollama wrapper
# ---------------------------------------------------------------------------

def _call_ollama(prompt: str, max_tokens: int = 512) -> str:
    """
    Call the local Ollama API and return the raw text response.
    Uses the ollama Python SDK which connects to http://localhost:11434.
    """
    response = ollama.generate(
        model=OLLAMA_MODEL,
        prompt=prompt,
        options={
            "num_predict": max_tokens,
            "temperature": 0.1,   # low temp → more deterministic for extraction
            "top_p": 0.9,
        },
    )
    return response["response"]


def _parse_json_from_response(raw: str) -> Any:
    """
    Extract the first valid JSON object or array from an LLM response,
    even if the model adds prose before/after the JSON block.
    """
    # Try direct parse first (model sometimes outputs clean JSON)
    try:
        return json.loads(raw.strip())
    except json.JSONDecodeError:
        pass

    # Find JSON block between ```json ... ``` or first { ... } or [ ... ]
    patterns = [
        r"```json\s*([\s\S]*?)```",   # markdown code block
        r"```\s*([\s\S]*?)```",        # any code block
        r"(\{[\s\S]*\})",              # first { } object
        r"(\[[\s\S]*\])",              # first [ ] array
    ]
    for pattern in patterns:
        match = re.search(pattern, raw, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1).strip())
            except json.JSONDecodeError:
                continue

    raise ValueError(f"No valid JSON found in LLM response: {raw[:200]!r}")
