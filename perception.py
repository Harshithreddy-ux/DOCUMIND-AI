"""
perception.py — DocuMind AI  |  Pillar 2: Perception Engine
=============================================================
Transforms raw document bytes (PDF or image) into structured, spatial-aware
text using PaddleOCR and LayoutParser.

Key responsibilities:
  1. Convert PDF pages → PIL Images
  2. Run LayoutParser to segment regions (Table, Title, Text, Figure…)
  3. Run PaddleOCR inside each detected region for character-level confidence
  4. Run lightweight forensics (visual entropy anomaly detection)
  5. Return a list of BoundingBox dicts + full OCR text + forensics flags

VRAM budget: PaddleOCR PP-OCRv4 (server) fits in ~1.2 GB at fp16.
            LayoutParser PaddleDetection uses ~0.6 GB. Total ≈ 1.8 GB.
"""

from __future__ import annotations

import io
import logging
import os
from typing import Any, Dict, List, Tuple

import numpy as np
from PIL import Image

# ---------------------------------------------------------------------------
# Lazy imports — heavy models are loaded once and cached at module level
# ---------------------------------------------------------------------------
_PADDLE_OCR = None   # PaddleOCR instance (lazy)
_LAYOUT_MODEL = None  # LayoutParser model (lazy)

logger = logging.getLogger(__name__)

# Confidence threshold below which we flag a character as low-quality
OCR_LOW_CONF_THRESHOLD = 0.70

# ---------------------------------------------------------------------------
# Helper: lazy model loaders (keeps startup fast; first call pays the cost)
# ---------------------------------------------------------------------------

def _get_ocr():
    """Lazily initialise PaddleOCR (English + angle classification)."""
    global _PADDLE_OCR
    if _PADDLE_OCR is None:
        from paddleocr import PaddleOCR  # type: ignore
        logger.info("Loading PaddleOCR model (first call)…")
        _PADDLE_OCR = PaddleOCR(
            use_angle_cls=True,   # auto-rotate skewed scans
            lang="en",
            use_gpu=True,         # falls back to CPU if no CUDA
            show_log=False,
        )
    return _PADDLE_OCR


def _get_layout_model():
    """Lazily initialise LayoutParser with a lightweight PaddleDetection model."""
    global _LAYOUT_MODEL
    if _LAYOUT_MODEL is None:
        import layoutparser as lp  # type: ignore
        logger.info("Loading LayoutParser model (first call)…")
        # PaddleDetection model — low VRAM footprint (~600 MB)
        _LAYOUT_MODEL = lp.PaddleDetectionLayoutModel(
            config_path="lp://PaddleDetection/ppyolov2_r50vd_dcn_365e_publaynet/config",
            threshold=0.5,
            label_map={
                0: "Text",
                1: "Title",
                2: "List",
                3: "Table",
                4: "Figure",
            },
            enforce_cpu=False,
            enable_mkldnn=True,
        )
    return _LAYOUT_MODEL


# ---------------------------------------------------------------------------
# PDF → PIL Images conversion
# ---------------------------------------------------------------------------

def pdf_to_images(raw_bytes: bytes, dpi: int = 200) -> List[Image.Image]:
    """
    Convert each page of a PDF to a PIL Image at the given DPI.
    Falls back gracefully if pdf2image / poppler is not installed.
    """
    try:
        from pdf2image import convert_from_bytes  # type: ignore
        images = convert_from_bytes(raw_bytes, dpi=dpi)
        logger.info(f"Converted PDF → {len(images)} page image(s) at {dpi} DPI")
        return images
    except Exception as exc:
        logger.warning(f"pdf2image failed ({exc}); treating as single-page image.")
        return [Image.open(io.BytesIO(raw_bytes)).convert("RGB")]


# ---------------------------------------------------------------------------
# Forensics: visual entropy anomaly detection
# ---------------------------------------------------------------------------

def _compute_entropy(image_array: np.ndarray) -> float:
    """
    Compute Shannon entropy of the grayscale histogram.
    Tampered/copy-pasted regions often have anomalously low or high entropy.
    """
    gray = np.mean(image_array, axis=2).astype(np.uint8)
    hist, _ = np.histogram(gray.flatten(), bins=256, range=(0, 256))
    hist = hist / hist.sum()
    # Avoid log(0)
    hist = hist[hist > 0]
    return float(-np.sum(hist * np.log2(hist)))


def run_forensics(images: List[Image.Image]) -> List[str]:
    """
    Lightweight forensics pass:
      - Flag pages whose entropy deviates significantly from the median
        (potential copy-paste or pixel-level tampering).
    Returns a list of human-readable flag strings.
    """
    flags: List[str] = []
    entropies = []
    for i, img in enumerate(images):
        arr = np.array(img)
        ent = _compute_entropy(arr)
        entropies.append(ent)
        logger.debug(f"Page {i+1} entropy = {ent:.3f}")

    if len(entropies) > 1:
        median_ent = float(np.median(entropies))
        for i, ent in enumerate(entropies):
            deviation = abs(ent - median_ent) / (median_ent + 1e-9)
            if deviation > 0.25:   # >25% deviation from median
                flags.append(
                    f"entropy_anomaly_page_{i+1}: entropy={ent:.2f}, "
                    f"median={median_ent:.2f}, deviation={deviation:.1%}"
                )
    return flags


# ---------------------------------------------------------------------------
# Core perception function
# ---------------------------------------------------------------------------

def run_perception(
    raw_bytes: bytes,
    file_type: str,
) -> Dict[str, Any]:
    """
    Entry point for the Perception Engine node.

    Args:
        raw_bytes:  Raw file contents (bytes).
        file_type:  One of "pdf", "png", "jpg", "jpeg".

    Returns:
        A dict with keys matching DocuMindState's perceive section:
          - ocr_text          : str
          - bounding_boxes    : List[BoundingBox]
          - page_count        : int
          - forensics_flags   : List[str]
          - layout_summary    : str
    """
    from state import BoundingBox  # local import to avoid circular deps

    ocr = _get_ocr()
    layout_model = _get_layout_model()

    # ── Step 1: Rasterise ─────────────────────────────────────────────────
    if file_type == "pdf":
        images = pdf_to_images(raw_bytes)
    else:
        images = [Image.open(io.BytesIO(raw_bytes)).convert("RGB")]

    page_count = len(images)

    # ── Step 2: Forensics pass (before any enhancement) ──────────────────
    forensics_flags = run_forensics(images)

    # ── Step 3: Layout detection + OCR per page ───────────────────────────
    all_bboxes: List[BoundingBox] = []
    full_text_parts: List[str] = []
    layout_labels: List[str] = []

    for page_idx, pil_img in enumerate(images):
        img_array = np.array(pil_img)
        h, w = img_array.shape[:2]

        # LayoutParser: detect structural regions
        try:
            import layoutparser as lp  # type: ignore
            layout = layout_model.detect(pil_img)
            regions = lp.Layout([b for b in layout if b.score > 0.5])
        except Exception as exc:
            logger.warning(f"LayoutParser failed on page {page_idx+1}: {exc}")
            regions = []

        # Collect unique layout labels for summary
        for block in regions:
            label = getattr(block, "type", "Text")
            if label not in layout_labels:
                layout_labels.append(label)

        # PaddleOCR on the full page image
        try:
            ocr_results = ocr.ocr(img_array, cls=True)
        except Exception as exc:
            logger.error(f"PaddleOCR failed on page {page_idx+1}: {exc}")
            ocr_results = [[]]

        page_text_parts: List[str] = []

        for line in (ocr_results or [[]])[0] or []:
            # line = [[[x1,y1],[x2,y1],[x2,y2],[x1,y2]], (text, confidence)]
            if not line or len(line) < 2:
                continue

            quad, (text, conf) = line[0], line[1]
            # Normalise bounding box to 0-1 range
            xs = [pt[0] for pt in quad]
            ys = [pt[1] for pt in quad]
            x1, y1 = min(xs) / w, min(ys) / h
            x2, y2 = max(xs) / w, max(ys) / h

            # Match to a LayoutParser region (if any overlap)
            matched_label = _match_region_label(regions, xs, ys)

            bbox: BoundingBox = BoundingBox(
                text=text,
                x1=round(x1, 4),
                y1=round(y1, 4),
                x2=round(x2, 4),
                y2=round(y2, 4),
                label=matched_label,
                ocr_conf=round(float(conf), 4),
            )
            all_bboxes.append(bbox)
            page_text_parts.append(text)

            # Low-confidence OCR flag
            if conf < OCR_LOW_CONF_THRESHOLD:
                forensics_flags.append(
                    f"low_ocr_conf_p{page_idx+1}: '{text[:30]}' conf={conf:.2f}"
                )

        full_text_parts.append(" ".join(page_text_parts))

    # ── Step 4: Build outputs ─────────────────────────────────────────────
    ocr_text = "\n\n--- PAGE BREAK ---\n\n".join(full_text_parts)
    layout_summary = (
        f"{page_count} page(s) detected. Layout regions: "
        + ", ".join(layout_labels or ["Text"])
        + f". Total text blocks: {len(all_bboxes)}."
    )

    logger.info(
        f"Perception complete: {page_count}p, "
        f"{len(all_bboxes)} blocks, "
        f"{len(forensics_flags)} forensics flags."
    )

    return {
        "ocr_text": ocr_text,
        "bounding_boxes": all_bboxes,
        "page_count": page_count,
        "forensics_flags": forensics_flags,
        "layout_summary": layout_summary,
        "pipeline_stage": "perceived",
    }


# ---------------------------------------------------------------------------
# Internal helper: spatial region matching
# ---------------------------------------------------------------------------

def _match_region_label(regions: Any, xs: List[float], ys: List[float]) -> str:
    """
    Given a list of LayoutParser blocks and raw pixel coordinates of an OCR
    line, return the label of the best-overlapping block, or 'Text' as default.
    """
    if not regions:
        return "Text"

    cx = (min(xs) + max(xs)) / 2
    cy = (min(ys) + max(ys)) / 2

    try:
        for block in regions:
            bx1, by1, bx2, by2 = (
                block.block.x_1,
                block.block.y_1,
                block.block.x_2,
                block.block.y_2,
            )
            if bx1 <= cx <= bx2 and by1 <= cy <= by2:
                return getattr(block, "type", "Text")
    except Exception:
        pass

    return "Text"
