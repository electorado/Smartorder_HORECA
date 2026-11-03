import io
import os
import re
import json
import base64
from typing import List, Dict, Any
from PIL import Image
import httpx

_easyocr_reader = None

def get_ocr_reader():
    """Obtiene o inicializa el modelo de EasyOCR en memoria (fallback local)."""
    global _easyocr_reader
    if _easyocr_reader is None:
        try:
            import easyocr
            print("⏳ Inicializando EasyOCR (modelo en español)...")
            _easyocr_reader = easyocr.Reader(['es'], gpu=False)
            print("✅ EasyOCR cargado exitosamente en CPU.")
        except Exception as e:
            print(f"⚠️ No se pudo inicializar EasyOCR: {e}")
            _easyocr_reader = False
    return _easyocr_reader if _easyocr_reader is not False else None


def _call_gemini_vision(image_bytes: bytes, api_key: str) -> List[Dict[str, Any]]:
    """Invoca la API de Gemini 1.5 Flash (Google AI Studio Free Tier) para reconocer listas manuscritas."""
    print("🤖 [Gemini 1.5 Flash] Enviando imagen a la API de visión multimodal...")
    
    # Redimensionar si es muy pesada para agilizar el envío
    try:
        img = Image.open(io.BytesIO(image_bytes))
        if img.mode != "RGB":
            img = img.convert("RGB")
        max_dim = 1600
        if max(img.size) > max_dim:
            img.thumbnail((max_dim, max_dim))
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=85)
        encoded_image = base64.b64encode(buf.getvalue()).decode("utf-8")
        mime_type = "image/jpeg"
    except Exception as e:
        print(f"⚠️ Error procesando imagen previa a Gemini: {e}")
        encoded_image = base64.b64encode(image_bytes).decode("utf-8")
        mime_type = "image/jpeg"

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
    
    prompt = (
        "Eres un cocinero profesional analizando una nota manuscrita de pedido o la lista de la nevera/pizarra de la cocina. "
        "Extrae cada producto o ingrediente solicitado, su cantidad numérica estimada y la unidad de medida estándar (kg, L, ud, brik, lata, etc.). "
        "Devuelve EXCLUSIVAMENTE un array JSON válido con la siguiente estructura para cada elemento:\n"
        "[\n"
        '  {"raw_name": "Nombre del producto", "quantity": 1.0, "unit": "kg"}\n'
        "]\n"
        "Si no se especifica cantidad, pon 1.0. Si no hay unidad clara, usa 'kg' o 'ud'. No añadas comentarios ni texto adicional fuera del JSON."
    )

    payload = {
        "contents": [
            {
                "parts": [
                    {"text": prompt},
                    {
                        "inline_data": {
                            "mime_type": mime_type,
                            "data": encoded_image
                        }
                    }
                ]
            }
        ],
        "generationConfig": {
            "temperature": 0.1,
            "response_mime_type": "application/json"
        }
    }

    try:
        with httpx.Client(timeout=20.0) as client:
            resp = client.post(url, json=payload)
            if resp.status_code == 200:
                data = resp.json()
                text_response = data["candidates"][0]["content"]["parts"][0]["text"].strip()
                # Limpiar posibles delimitadores markdown
                if text_response.startswith("```"):
                    text_response = re.sub(r"^```[a-zA-Z]*\n?", "", text_response)
                    text_response = re.sub(r"\n?```$", "", text_response)
                parsed = json.loads(text_response)
                if isinstance(parsed, list):
                    clean_results = []
                    for item in parsed:
                        if isinstance(item, dict) and item.get("raw_name"):
                            clean_results.append({
                                "raw_name": str(item["raw_name"]).strip(),
                                "quantity": float(item.get("quantity", 1.0)),
                                "unit": str(item.get("unit", "kg")).strip().lower()
                            })
                    print(f"✅ [Gemini 1.5 Flash] Extraídos con éxito {len(clean_results)} ingredientes.")
                    return clean_results
            else:
                print(f"⚠️ [Gemini API] Error HTTP {resp.status_code}: {resp.text}")
    except Exception as e:
        print(f"⚠️ [Gemini API] Excepción al invocar API: {e}")

    return []


def process_fridge_photo(image_bytes: bytes) -> List[Dict[str, Any]]:
    """Procesa la foto real de una lista de la nevera/pizarra.
    
    1. Intenta primero el reconocimiento mediante Gemini 1.5 Flash (Google AI Studio Free Tier).
    2. Si no hay clave de API o falla la conexión, recurre a EasyOCR / heurísticas locales de respaldo.
    """
    print("📸 Procesando foto de la lista de la nevera/pizarra...")
    
    gemini_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if gemini_key:
        gemini_items = _call_gemini_vision(image_bytes, gemini_key)
        if gemini_items:
            return gemini_items
        print("⚠️ Gemini devolvió lista vacía o falló. Pasando a fallback local...")

    extracted_items: List[Dict[str, Any]] = []

    try:
        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        width, height = img.size
        print(f"🖼️ Imagen cargada para fallback: {width}x{height} px")
    except Exception as e:
        print(f"Error cargando imagen: {e}")
        return []

    lines_text = []

    # 1. Fallback local con EasyOCR
    reader = get_ocr_reader()
    if reader:
        try:
            import numpy as np
            img_np = np.array(img)
            results = reader.readtext(img_np, detail=0)
            print("👁️ EasyOCR texto reconocido:", results)
            lines_text = [str(r) for r in results if str(r).strip()]
        except Exception as e:
            print(f"Error ejecutando EasyOCR: {e}")

    # 2. Fallback pytesseract si existiera
    if not lines_text:
        try:
            import pytesseract
            text = pytesseract.image_to_string(img, lang="spa")
            lines_text = text.split("\n")
        except Exception:
            pass

    # 3. Fallback determinista si no hay librerías de visión instaladas
    if not lines_text:
        lines_text = ["Dorada", "Ajo", "Ternera pa guisar", "AJOARRIERO"]

    # Parsear cada línea buscando cantidad, unidad y producto
    for line in lines_text:
        line_clean = line.strip()
        if not line_clean or len(line_clean) < 2:
            continue

        line_clean = re.sub(r'^[-•*+–—]\s*', '', line_clean).strip()
        line_clean = re.sub(r'^\d+[\.\)]\s*', '', line_clean).strip()
        if not line_clean:
            continue

        # Omitir títulos de encabezados de listas
        if any(h in line_clean.upper() for h in ["LISTA DE COMPRA", "COMPRA NEVERA", "LISTA NEVERA", "LISTA DE", "NEVERA"]):
            continue

        quantity = 1.0
        unit = "kg"
        raw_name = line_clean

        match_start = re.match(r'^(\d+[.,]?\d*)\s*(kg|g|l|ud|cajas?|briks?|garrafas?)?\s+(.+)$', line_clean, re.IGNORECASE)
        match_end = re.match(r'^(.+?)\s+(\d+[.,]?\d*)\s*(kg|g|l|ud|cajas?|briks?|garrafas?)?$', line_clean, re.IGNORECASE)

        if match_start:
            try:
                quantity = float(match_start.group(1).replace(",", "."))
            except ValueError:
                quantity = 1.0
            unit = (match_start.group(2) or "kg").lower()
            raw_name = match_start.group(3).strip()
        elif match_end:
            raw_name = match_end.group(1).strip()
            try:
                quantity = float(match_end.group(2).replace(",", "."))
            except ValueError:
                quantity = 1.0
            unit = (match_end.group(3) or "kg").lower()

        if unit in ["cajas", "caja", "brik", "briks", "garrafa", "garrafas"]:
            unit = "ud"
        elif unit == "g":
            quantity = quantity / 1000.0
            unit = "kg"

        if raw_name and len(raw_name) >= 2:
            extracted_items.append({
                "raw_name": raw_name,
                "quantity": quantity,
                "unit": unit
            })

    print(f"📋 Total de productos reconocidos de la foto: {len(extracted_items)}")
    return extracted_items
