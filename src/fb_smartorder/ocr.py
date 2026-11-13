"""
ocr.py - Módulo mantenido por retrocompatibilidad arquitectónica (R01F03 / R01F04).

El motor OCR clásico (EasyOCR / Tesseract) arrojaba un 38.2% de precisión en caligrafía
de hostelería, por lo que fue sustituido por Visión Multimodal con Google Gemini Flash Lite.
Toda la lógica activa se encuentra en `vision_ai.py`.
"""

from .vision_ai import (
    process_fridge_photo,
    scan_kitchen_notes,
    get_ocr_reader,
    _call_gemini_vision,
)

__all__ = [
    "process_fridge_photo",
    "scan_kitchen_notes",
    "get_ocr_reader",
    "_call_gemini_vision",
]
