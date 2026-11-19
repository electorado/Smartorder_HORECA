import json
import os
import re
import tempfile
from pathlib import Path
from typing import List, Dict, Any, Union, Optional, Set
from pypdf import PdfReader

from .base import BaseCatalogExtractor, detect_supplier_from_pdf
from .pdf_spatial import SpatialCardPdfExtractor
from .pdf_tabular import TabularPdfExtractor, CoordinateTablePdfExtractor


class VisualFlyerPdfExtractor(BaseCatalogExtractor):
    """Extractor para folletos publicitarios multicolumna y de ofertas especiales (ej. Ahumados Domínguez / Campañas).
    
    Gestiona textos con doble impresión de sombreado y asocia los nombres de productos
    con sus precios situados inmediatamente debajo usando proximidad geométrica 2D.
    """
    def extract(self, file_path: Union[str, Path]) -> List[Dict[str, Any]]:
        path = Path(file_path)
        reader = PdfReader(path)
        products: List[Dict[str, Any]] = []

        # Detección de proveedor
        self.detected_supplier = detect_supplier_from_pdf(reader, path)

        for page_idx, page in enumerate(reader.pages, start=1):
            raw_elements = []
            def visitor(text, cm, tm, font_dict, font_size):
                t = text.strip()
                if t:
                    # Limpiar duplicaciones de sombreado
                    n = len(t)
                    if n >= 4 and n % 2 == 0 and t[:n//2] == t[n//2:]:
                        t = t[:n//2]
                    raw_elements.append({
                        'x': round(tm[4], 1),
                        'y': round(tm[5], 1),
                        'text': t,
                        'size': font_size
                    })
            page.extract_text(visitor_text=visitor)

            # Descartar elementos idénticos en la misma coordenada
            seen = set()
            elements = []
            for e in raw_elements:
                key = (e['x'], e['y'], e['text'])
                if key not in seen:
                    seen.add(key)
                    elements.append(e)

            # 1. Encontrar números de precio
            price_anchors = []
            for e in elements:
                m = re.match(r'^(\d+(?:[.,]\d{1,2})?)$', e['text'])
                if m:
                    val = float(m.group(1).replace(',', '.'))
                    if 0.5 <= val <= 500.0:
                        unit = 'kg'
                        has_currency = False
                        for u in elements:
                            if abs(u['y'] - e['y']) <= 5.0 and 0 < (u['x'] - e['x']) < 120.0:
                                if '€' in u['text'] or any(k in u['text'].lower() for k in ['kg', 'ud', 'lote', 'caja', 'pieza']):
                                    has_currency = True
                                    um = re.search(r'(?:€\s*/?\s*)?([a-zA-Z]+)', u['text'])
                                    if um and um.group(1).lower() in ['kg', 'ud', 'lote', 'caja', 'pieza']:
                                        unit = um.group(1).lower()
                                    break
                        if has_currency:
                            price_anchors.append({'price': val, 'unit': unit, 'x': e['x'], 'y': e['y']})

            # 2. Asociar nombre del producto encima del precio
            for pa in price_anchors:
                px, py = pa['x'], pa['y']
                name_candidates = [
                    e for e in elements
                    if 10.0 <= (e['y'] - py) <= 75.0
                    and abs(e['x'] - px) < 130.0
                    and not re.search(r'^\d+[.,]?\d*$', e['text'])
                    and '€' not in e['text']
                    and e['text'].upper() not in ['ESPECIALIDADES', 'CARNICERÍA', 'OFERTAS', 'NOVIEMBRE', 'PRECIOS', 'TUS CONGELADOS']
                ]
                name_candidates = sorted(name_candidates, key=lambda c: -c['y'])
                name = ' '.join(c['text'] for c in name_candidates).strip()
                if name and len(name) >= 3:
                    products.append({
                        'page': page_idx,
                        'supplier_product_code': None,
                        'raw_name': name,
                        'price': pa['price'],
                        'unit': pa['unit'],
                        'format': ''
                    })

        print(f"✅ [VisualFlyerPdfExtractor] Se extrajeron {len(products)} productos de folleto.")
        return products


# ==============================================================================
# 5.3. ESTRATEGIA UNIVERSAL ADAPTATIVA (Detección automática de maquetación)
# ==============================================================================

class UniversalPdfExtractor(BaseCatalogExtractor):
    """Estrategia Universal que analiza la geometría interna del documento PDF
    y delega dinámicamente en el motor óptimo:
    - SpatialCardPdfExtractor para folletos con códigos C-XXXX (Abordo, Dialva).
    - CoordinateTablePdfExtractor para tablas con columna de precios alineada por Y (Morego).
    - VisualFlyerPdfExtractor para folletos publicitarios y ofertas multicolumna (Ahumados).
    - TabularPdfExtractor para listas administrativas convencionales línea a línea (Ferjusanz).
    """
    def extract(self, file_path: Union[str, Path]) -> List[Dict[str, Any]]:
        path = Path(file_path)
        reader = PdfReader(path)
        num_pages = len(reader.pages)
        sample_pages = []
        sample_pages.extend(reader.pages[:min(3, num_pages)])
        if num_pages > 3:
            sample_pages.extend(reader.pages[max(3, num_pages - 2):])
        
        code_count = 0
        c_hyphen_count = 0
        has_coord_table = 0
        multi_price_lines = 0
        duplicate_coords = 0
        seen_coords = set()
        is_dialva = False
        is_abordo = False

        for p in sample_pages:
            txt = p.extract_text() or ""
            txt_lower = txt.lower()
            if "dialva" in txt_lower:
                is_dialva = True
            if "abordo" in txt_lower or "servifrio" in txt_lower or "servifrío" in txt_lower:
                is_abordo = True
            # Contar anclajes de código tanto en el texto extraído como en tokens
            code_count += len(re.findall(r'[C|c][:.-]?\s*\d{3,5}', txt))
            c_hyphen_count += len(re.findall(r'\bC-\d{3,5}\b', txt))

            for l in txt.split("\n"):
                l = l.strip()
                if not l: continue
                if len(re.findall(r'€', l)) >= 2:
                    multi_price_lines += 1

            def visitor(text, cm, tm, font_dict, font_size):
                t = text.strip()
                if not t: return
                nonlocal duplicate_coords
                key = (round(tm[4], 1), round(tm[5], 1), t)
                if key in seen_coords:
                    duplicate_coords += 1
                else:
                    seen_coords.add(key)
            p.extract_text(visitor_text=visitor)

        for p in sample_pages:
            elements = []
            def v2(text, cm, tm, font_dict, font_size):
                t = text.strip()
                if t: elements.append({'x': round(tm[4], 1), 'y': round(tm[5], 1), 'text': t})
            p.extract_text(visitor_text=v2)
            for e in elements:
                if 'lote' in e['text'].lower() or re.match(r'^\d{4}\s+[A-Z]', e['text']):
                    matches = [pe for pe in elements if abs(pe['y'] - e['y']) <= 4.0 and pe['x'] > 280.0 and re.search(r'\d+[.,]\d{2}', pe['text'])]
                    if matches:
                        has_coord_table += 1

        # Selección de estrategia según huella espacial
        stem_lower = path.stem.lower()
        if is_dialva or "dialva" in stem_lower:
            print("🎯 [UniversalPdfExtractor] Detectado catálogo de DIALVA Hostelería. Usando DialvaPdfExtractor...")
            engine = DialvaPdfExtractor()
        elif is_abordo or any(k in stem_lower for k in ["abordo", "servifrio", "servifrío"]) or c_hyphen_count >= 3:
            print("🎯 [UniversalPdfExtractor] Detectado catálogo de Abordo Hostelería / Servifrío. Usando AbordoPdfExtractor...")
            engine = AbordoPdfExtractor()
        elif code_count >= 3:
            print(f"🎯 [UniversalPdfExtractor] Detectado catálogo de tarjetas por código ({code_count} anclajes C-XXXX). Usando SpatialCardPdfExtractor...")
            engine = SpatialCardPdfExtractor(
                anchor_regex=r'[C|c][:.-]?\s*(\d{3,5})',
                header_y_limit=950.0,
                y_above=85.0,
                y_below=80.0,
                x_tolerance=190.0
            )
        elif has_coord_table >= 2:
            print(f"🎯 [UniversalPdfExtractor] Detectada tabla por coordenadas verticales Y ({has_coord_table} lotes). Usando CoordinateTablePdfExtractor...")
            engine = CoordinateTablePdfExtractor()
        elif multi_price_lines >= 2 or duplicate_coords >= 5:
            print("🎯 [UniversalPdfExtractor] Detectado folleto publicitario/flyer. Usando VisualFlyerPdfExtractor...")
            engine = VisualFlyerPdfExtractor()
        else:
            print("🎯 [UniversalPdfExtractor] Detectada lista tabular convencional. Usando TabularPdfExtractor...")
            engine = TabularPdfExtractor()

        items = engine.extract(file_path)
        self.detected_supplier = engine.detected_supplier
        return items


# ==============================================================================
# 5. ESTRATEGIA MULTIMODAL CON GEMINI 1.5 FLASH (Google AI Studio Free Tier)
# ==============================================================================

class GeminiMultimodalPdfExtractor(BaseCatalogExtractor):
    """Extractor asistido por IA multimodal (Gemini 1.5 Flash) para catálogos PDF
    complejos o no estructurados (folletos gráficos, diseños de revista, etc.).
    """

    def extract(self, file_path: Union[str, Path]) -> List[Dict[str, Any]]:
        import os
        import base64
        import httpx

        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Archivo PDF no encontrado: {file_path}")

        api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if not api_key:
            print("⚠️ [GeminiMultimodalPdfExtractor] No hay GEMINI_API_KEY configurada. Usando fallback tabular.")
            return TabularPdfExtractor().extract(file_path)

        # Para catálogos voluminosos (> 3MB) como Abordo (7MB), priorizar extracción tabular local instantánea
        if path.stat().st_size > 3 * 1024 * 1024:
            print(f"⚡ [GeminiMultimodalPdfExtractor] Catálogo voluminoso ({path.stat().st_size / (1024*1024):.1f} MB). Usando extractor tabular local ultrarrápido...")
            fallback = TabularPdfExtractor()
            items = fallback.extract(file_path)
            if len(items) > 0:
                self.detected_supplier = fallback.detected_supplier
                return items

        print(f"🤖 [GeminiMultimodalPdfExtractor] Procesando {path.name} mediante Gemini 1.5 Flash...")
        try:
            with open(path, "rb") as f:
                pdf_bytes = f.read()

            encoded_pdf = base64.b64encode(pdf_bytes).decode("utf-8")

            prompt = (
                "Eres un extractor de datos para hostelería. Analiza las páginas de este catálogo comercial de proveedor.\n"
                "1. Extrae los datos del PROVEEDOR o empresa identificada en el documento (nombre o razón social, teléfono/WhatsApp, email y CIF si aparecen).\n"
                "2. Extrae todos los PRODUCTOS listados con su nombre exacto ('raw_name'), precio unitario numérico ('price'), "
                "unidad ('unit': kg, L, ud, caja, sobre), formato ('format') y código del proveedor ('supplier_product_code').\n\n"
                "Devuelve EXCLUSIVAMENTE un JSON con esta estructura exacta:\n"
                "{\n"
                '  "supplier": {"name": "Nombre Proveedor", "phone": "+34...", "email": "pedidos@...", "cif": "B12345678"},\n'
                '  "products": [\n'
                '    {"raw_name": "Nombre", "price": 10.50, "unit": "kg", "supplier_product_code": "REF01", "format": "Caja 5kg"}\n'
                "  ]\n"
                "}\n"
                "Si no logras identificar el nombre de empresa, pon en 'supplier' el título del catálogo.\n"
                "Sin bloques markdown ni explicaciones adicionales."
            )

            payload = {
                "contents": [
                    {
                        "parts": [
                            {"text": prompt},
                            {
                                "inline_data": {
                                    "mime_type": "application/pdf",
                                    "data": encoded_pdf
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

            candidate_models = ["gemini-2.5-flash", "gemini-flash-latest"]

            for model_name in candidate_models:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
                print(f"🤖 [GeminiMultimodalPdfExtractor] Probando modelo '{model_name}'...")

                try:
                    with httpx.Client(timeout=10.0) as client:
                        resp = client.post(url, json=payload)
                        if resp.status_code == 200:
                            data = resp.json()
                            text_response = data["candidates"][0]["content"]["parts"][0]["text"].strip()
                            if text_response.startswith("```"):
                                text_response = re.sub(r"^```[a-zA-Z]*\n?", "", text_response)
                                text_response = re.sub(r"\n?```$", "", text_response)
                            parsed_json = json.loads(text_response)
                            items = []
                            if isinstance(parsed_json, dict):
                                supp_data = parsed_json.get("supplier")
                                if isinstance(supp_data, dict) and supp_data.get("name"):
                                    self.detected_supplier = {
                                        "name": str(supp_data.get("name")).strip(),
                                        "phone": str(supp_data.get("phone")).strip() if supp_data.get("phone") else None,
                                        "email": str(supp_data.get("email")).strip() if supp_data.get("email") else None,
                                        "cif": str(supp_data.get("cif")).strip() if supp_data.get("cif") else None
                                    }
                                items = parsed_json.get("products", [])
                            elif isinstance(parsed_json, list):
                                items = parsed_json

                            if isinstance(items, list):
                                valid_items = []
                                for it in items:
                                    if isinstance(it, dict) and it.get("raw_name"):
                                        try:
                                            price = float(it.get("price", 0.0))
                                        except (ValueError, TypeError):
                                            price = 0.0
                                        valid_items.append({
                                            "raw_name": str(it["raw_name"]).strip(),
                                            "price": price,
                                            "unit": str(it.get("unit", "ud")).strip().lower(),
                                            "supplier_product_code": str(it.get("supplier_product_code")) if it.get("supplier_product_code") else None,
                                            "format": str(it.get("format")) if it.get("format") else None
                                        })
                                print(f"✅ [GeminiMultimodalPdfExtractor - {model_name}] Extraídos {len(valid_items)} productos con éxito.")
                                return valid_items
                        elif resp.status_code in [401, 402, 429]:
                            print(f"⚠️ [GeminiMultimodalPdfExtractor] Cuota o autenticación no disponible ({resp.status_code}). Saltando a fallback local...")
                            break
                        elif resp.status_code in [404, 503]:
                            print(f"ℹ️ [GeminiMultimodalPdfExtractor] Modelo '{model_name}' no disponible ({resp.status_code}). Probando siguiente...")
                            continue
                        else:
                            print(f"⚠️ [GeminiMultimodalPdfExtractor] Error HTTP {resp.status_code}: {resp.text}")
                except Exception as e:
                    print(f"⚠️ [GeminiMultimodalPdfExtractor] Excepción llamando a {model_name}: {e}")
                    continue
        except Exception as e:
            print(f"⚠️ [GeminiMultimodalPdfExtractor] Excepción global: {e}")

        print("🔄 [GeminiMultimodalPdfExtractor] Activando fallback UniversalPdfExtractor...")
        fallback = UniversalPdfExtractor()
        items = fallback.extract(file_path)
        self.detected_supplier = fallback.detected_supplier
        return items


# ==============================================================================
# 6. FACTORÍA DE EXTRACTORES (Patrón Factoría - GoF)
# ==============================================================================

