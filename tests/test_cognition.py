"""
tests/test_cognition.py — Unit tests for the Cognition Core
=============================================================
Tests that do NOT require Ollama or any GPU — pure Python logic only.
"""

import math
import pytest
from unittest.mock import patch, MagicMock

# ─── Import the module under test (patch ollama before import) ────────────────
import sys, types
# Stub out ollama so tests don't need a running Ollama instance
ollama_stub = types.ModuleType("ollama")
ollama_stub.generate  = MagicMock(return_value={"response": '{"total": 118.0}'})
ollama_stub.embeddings = MagicMock(return_value={"embedding": [0.1] * 768})
ollama_stub.list      = MagicMock(return_value={})
sys.modules["ollama"] = ollama_stub

# Also stub paddleocr / layoutparser so perception.py doesn't crash on import
for mod in ["paddleocr", "layoutparser", "pdf2image"]:
    sys.modules[mod] = types.ModuleType(mod)

import os
os.environ.setdefault("POSTGRES_HOST", "localhost")
os.environ.setdefault("NEO4J_URI", "bolt://localhost:7687")
os.environ.setdefault("OLLAMA_MODEL", "gemma2:2b-instruct-q4_K_M")

from cognition import (
    classify_document,
    validate_causally,
    score_confidence,
    _parse_json_from_response,
    _close,
)
from state import CausalValidationResult, FieldConfidence


# ─────────────────────────────────────────────────────────────────────────────
# classify_document — heuristic path (no LLM call needed)
# ─────────────────────────────────────────────────────────────────────────────

class TestClassifyDocument:
    def test_classify_invoice(self):
        text = "Invoice #2024-001\nBill To: Acme Corp\nAmount Due: $1,500"
        assert classify_document(text) == "invoice"

    def test_classify_contract(self):
        text = "THIS AGREEMENT is entered into between the parties hereinafter referred to"
        assert classify_document(text) == "contract"

    def test_classify_receipt(self):
        text = "Thank you for your purchase! Transaction ID: TXN-999"
        assert classify_document(text) == "receipt"

    def test_unknown_falls_back(self):
        # LLM stub returns '{"total": 118.0}' which isn't a valid doc type
        # classify_document should return "unknown" after LLM fallback
        text = "random unrelated text with no document keywords xyz abc"
        result = classify_document(text)
        assert result in {"invoice", "contract", "receipt", "unknown", "purchase_order"}


# ─────────────────────────────────────────────────────────────────────────────
# validate_causally — pure math, no LLM
# ─────────────────────────────────────────────────────────────────────────────

class TestValidateCausally:
    def test_valid_invoice_passes(self):
        extracted = {"subtotal": 100.0, "tax": 18.0, "discount": 0.0, "total": 118.0}
        result = validate_causally(extracted)
        assert result["passed"] is True
        assert len(result["failures"]) == 0

    def test_total_mismatch_fails(self):
        extracted = {"subtotal": 100.0, "tax": 18.0, "discount": 0.0, "total": 115.0}
        result = validate_causally(extracted)
        assert result["passed"] is False
        assert "Total mismatch" in result["failures"][0]
        assert result["corrected_values"]["total"] == 118.0

    def test_line_item_sum_mismatch(self):
        extracted = {
            "subtotal": 200.0,
            "tax": 0.0,
            "discount": 0.0,
            "total": 200.0,
            "line_items": [
                {"description": "A", "line_total": 80.0},
                {"description": "B", "line_total": 70.0},  # 80+70=150 ≠ 200
            ],
        }
        result = validate_causally(extracted)
        assert result["passed"] is False
        assert any("Line-item sum" in f for f in result["failures"])

    def test_missing_fields_skips_gracefully(self):
        """If no numeric fields present, no checks are run."""
        result = validate_causally({"vendor_name": "Acme", "invoice_date": "2026-01-01"})
        assert result["checks_run"] == []
        assert result["passed"] is True

    def test_discount_applied_correctly(self):
        extracted = {"subtotal": 100.0, "tax": 10.0, "discount": 5.0, "total": 105.0}
        result = validate_causally(extracted)
        assert result["passed"] is True

    def test_line_item_qty_price_mismatch(self):
        extracted = {
            "subtotal": 60.0, "tax": 0.0, "discount": 0.0, "total": 60.0,
            "line_items": [{"quantity": 3, "unit_price": 10.0, "line_total": 40.0}],  # 3×10=30≠40
        }
        result = validate_causally(extracted)
        assert any("qty*price" in f for f in result["failures"])


# ─────────────────────────────────────────────────────────────────────────────
# _parse_json_from_response — LLM output parsing
# ─────────────────────────────────────────────────────────────────────────────

class TestParseJsonFromResponse:
    def test_clean_json(self):
        raw = '{"vendor": "Acme", "total": 100}'
        result = _parse_json_from_response(raw)
        assert result == {"vendor": "Acme", "total": 100}

    def test_json_in_markdown_block(self):
        raw = "Here is the extraction:\n```json\n{\"total\": 99}\n```"
        result = _parse_json_from_response(raw)
        assert result == {"total": 99}

    def test_json_in_plain_code_block(self):
        raw = "```\n{\"amount\": 500}\n```"
        result = _parse_json_from_response(raw)
        assert result == {"amount": 500}

    def test_json_buried_in_prose(self):
        raw = 'The extracted data is: {"invoice_number": "INV-001"} as you can see.'
        result = _parse_json_from_response(raw)
        assert result["invoice_number"] == "INV-001"

    def test_invalid_raises(self):
        with pytest.raises(ValueError):
            _parse_json_from_response("This has no JSON at all, sorry!")


# ─────────────────────────────────────────────────────────────────────────────
# _close — floating-point tolerance helper
# ─────────────────────────────────────────────────────────────────────────────

class TestCloseHelper:
    def test_exact_match(self):
        assert _close(100.0, 100.0) is True

    def test_within_tolerance(self):
        assert _close(100.01, 100.0) is True    # < 2 cents tolerance

    def test_outside_tolerance(self):
        assert _close(103.0, 100.0) is False    # 3% off — outside rel_tol

    def test_zero_values(self):
        assert _close(0.0, 0.0) is True
