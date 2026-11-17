import json
import re
from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Dict, Any, Union, Optional, Set
import pandas as pd
from pypdf import PdfReader


# ==============================================================================
# 1. CONTRATO BASE (Patrón Estrategia - GoF)
# ==============================================================================

class BaseCatalogExtractor(ABC):
    """Interfaz abstracta que define el contrato común para cualquier extractor de catálogo.
    
    Permite desacoplar el origen de datos (Excel, PDF espacial, PDF tabular, OCR)
    del resto del pipeline ETL (transformación y carga).
    """

    def __init__(self):
        self.detected_supplier: Optional[Dict[str, Any]] = None

    @abstractmethod
    def extract(self, file_path: Union[str, Path]) -> List[Dict[str, Any]]:
        """Extrae y normaliza los productos crudos a una lista de diccionarios.
        
        Cada elemento devuelto debe contener como mínimo:
            - 'raw_name': Nombre del producto en bruto.
            - 'price': Precio numérico (float).
            - 'unit': Unidad de medida ('kg', 'ud', 'sobre', etc.).
            - 'supplier_product_code': Código de referencia del proveedor (opcional).
            - 'format': Formato o presentación del empaque (opcional).
        """
        pass


# ==============================================================================
# 2. ESTRATEGIA EXCEL (Genérica para hojas de cálculo)
# ==============================================================================

class GenericExcelExtractor(BaseCatalogExtractor):
    """Extractor para hojas de cálculo Excel (.xlsx, .xls).
    
    Analiza inteligentemente las cabeceras de columnas para identificar automáticamente
    las columnas correspondientes a nombre, precio, unidad y código.
    """

    def extract(self, file_path: Union[str, Path]) -> List[Dict[str, Any]]:
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Archivo Excel no encontrado: {file_path}")

        print(f"📄 [ExcelExtractor] Procesando: {file_path}")
        df = pd.read_excel(path, sheet_name=0).dropna(how="all")
        
        products: List[Dict[str, Any]] = []
        cols = [str(c).lower().strip() for c in df.columns]

        name_col = None
        price_col = None
        unit_col = None
        code_col = None

        for idx, col_name in enumerate(cols):
            if any(k in col_name for k in ["producto", "articulo", "descripc", "ingrediente", "nombre"]):
                name_col = df.columns[idx]
            elif any(k in col_name for k in ["precio", "pvp", "coste", "eur", "importe"]):
                price_col = df.columns[idx]
            elif any(k in col_name for k in ["unidad", "formato", "medida", "ud"]):
                unit_col = df.columns[idx]
            elif any(k in col_name for k in ["codigo", "cod", "ref", "id"]):
                code_col = df.columns[idx]

        for _, row in df.iterrows():
            raw_name = ""
            price = 0.0
            unit = "ud"
            code = None

            if name_col and pd.notna(row[name_col]):
                raw_name = str(row[name_col]).strip()
            elif len(df.columns) > 0 and pd.notna(row[df.columns[0]]):
                raw_name = str(row[df.columns[0]]).strip()

            if not raw_name or len(raw_name) < 2:
                continue

            if price_col and pd.notna(row[price_col]):
                try:
                    val_str = str(row[price_col]).replace("€", "").replace(",", ".").strip()
                    price = float(val_str)
                except ValueError:
                    price = 0.0
            else:
                for col in df.columns:
                    val = str(row[col])
                    if re.search(r'\d+[.,]\d{2}', val):
                        try:
                            price = float(re.sub(r'[^\d.]', '', val.replace(',', '.')))
                            break
                        except ValueError:
                            pass

            if unit_col and pd.notna(row[unit_col]):
                unit = str(row[unit_col]).strip().lower()

            if code_col and pd.notna(row[code_col]):
                code = str(row[code_col]).strip()

            products.append({
                "supplier_product_code": code,
                "raw_name": raw_name,
                "price": price,
                "unit": unit
            })

        print(f"✅ [ExcelExtractor] Se extrajeron {len(products)} productos.")
        return products


# ==============================================================================
# 3. ESTRATEGIA PDF ESPACIAL (Parametrizable para catálogos publicitarios tipo revista)
# ==============================================================================

class SpatialCardPdfExtractor(BaseCatalogExtractor):
    """Extractor parametrizable para PDFs publicitarios con maquetación de tarjetas/grid.
    
    Utiliza coordenadas espaciales y fuentes para agrupar elementos en cajas de producto
    independientes, permitiendo configurar los patrones de código, cabeceras a descartar
    y frases publicitarias sin acoplar la lógica general a un único proveedor.
    """

    def __init__(
        self,
        anchor_regex: str = r'[C|c][:.]?\s*(\d{3,5})',
        ignored_section_headers: Optional[Set[str]] = None,
        noise_phrases: Optional[List[str]] = None,
        x_tolerance: float = 190.0,
        y_above: float = 75.0,
        y_below: float = 65.0,
        header_y_limit: float = 780.0,
        save_output: bool = False
    ):
        self.anchor_regex = anchor_regex
        self.ignored_section_headers = ignored_section_headers or set()
        self.noise_phrases = noise_phrases or []
        self.x_tolerance = x_tolerance
        self.y_above = y_above
        self.y_below = y_below
        self.header_y_limit = header_y_limit
        self.save_output = save_output

    def _clean_product_name(self, text: str) -> str:
        text = re.sub(r'\(?\d+\s*uds?\s*[Xx]\s*[\d.,\'’]+\s*k?g\)?', '', text, flags=re.IGNORECASE)
        text = re.sub(r'\b\d+\s*uds?\s*x\b.*', '', text, flags=re.IGNORECASE)
        text = re.sub(r'\(?c[.:]?\s*\d+\)?', '', text, flags=re.IGNORECASE)
        text = re.sub(r'\bC:\s*$', '', text, flags=re.IGNORECASE)
        text = re.sub(r'\b\d+[.,\'’]\d{1,2}\s*€(?:/\w+)?\b', '', text)
        text = re.sub(r'\b\d+\s*raciones\b', '', text, flags=re.IGNORECASE)
        text = re.sub(r'\b\d+X\d+[A-Za-z]*\b', '', text)
        text = re.sub(r'\s+', ' ', text)
        return text.strip(' ·-(),')

    def extract(self, file_path: Union[str, Path]) -> List[Dict[str, Any]]:
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Archivo PDF no encontrado: {file_path}")

        print(f"📑 [SpatialCardPdfExtractor] Analizando maquetación por tarjetas: {file_path}")
        reader = PdfReader(path)
        products: List[Dict[str, Any]] = []

        for page_idx, page in enumerate(reader.pages, start=1):
            elements = []
            page_width = float(page.mediabox.width) if hasattr(page, 'mediabox') and page.mediabox else 595.0
            midpoint = page_width / 2.0

            def visitor(text, cm, tm, font_dict, font_size):
                t = text.strip()
                if t:
                    font_name = font_dict.get('/BaseFont', '') if font_dict else ''
                    elements.append({
                        'x': tm[4],
                        'y': tm[5],
                        'bold': 'Bold' in font_name,
                        'text': t,
                        'size': font_size
                    })

            page.extract_text(visitor_text=visitor)

            # Filtrar textos institucionales, cabeceras y anuncios publicitarios
            filtered_elements = []
            for e in elements:
                tu = e['text'].upper()
                if tu in self.ignored_section_headers:
                    continue
                if any(np in tu for np in self.noise_phrases):
                    continue
                if e['y'] > self.header_y_limit:
                    continue
                filtered_elements.append(e)

            # 1. Identificar los anclajes de producto (códigos de proveedor)
            code_anchors = []
            for i, e in enumerate(filtered_elements):
                m = re.search(self.anchor_regex, e['text'])
                if m:
                    code_anchors.append({'code': m.group(1), 'x': e['x'], 'y': e['y'], 'idx': i})
                elif e['text'].isdigit() and len(e['text']) in [3, 4, 5] and i > 0 and 'C:' in filtered_elements[i-1]['text']:
                    code_anchors.append({'code': e['text'], 'x': e['x'], 'y': e['y'], 'idx': i})

            # 2. Delimitar la tarjeta espacial de cada anclaje
            for ca in code_anchors:
                cx, cy = ca['x'], ca['y']
                is_left = cx < midpoint
                card_elems = [
                    e for e in filtered_elements
                    if (e['x'] < midpoint if is_left else e['x'] >= midpoint)
                    and abs(e['x'] - cx) < self.x_tolerance
                    and (cy - self.y_below) <= e['y'] <= (cy + self.y_above)
                ]

                # Nombre del producto y variedad: elementos situados por encima o alineados con el código
                name_candidates = [e for e in card_elems if cy - 4.0 <= e['y'] <= cy + self.y_above]
                name_candidates = sorted(name_candidates, key=lambda x: -x['y'])

                name_tokens = []
                for nc in name_candidates:
                    clean_t = self._clean_product_name(nc['text'])
                    clean_t = re.sub(r'C[:.]?\s*\d+', '', clean_t, flags=re.IGNORECASE).strip(' ·-(),')
                    if clean_t and not clean_t.isdigit() and '€' not in clean_t and len(clean_t) > 1:
                        name_tokens.append(clean_t)

                raw_name = ' '.join(name_tokens).strip()

                # Formato de empaque
                format_str = ''
                for e in card_elems:
                    fm = re.search(r'(\d+\s*uds?\s*[Xx]\s*[\d.,\'’]+\s*[A-Za-z]+)', e['text'], re.IGNORECASE)
                    if fm:
                        format_str = fm.group(1)
                        break
                    fm2 = re.search(r'(\d+\s*ud\s*[Xx]\s*[\d.,\'’]+\s*k?g)', e['text'], re.IGNORECASE)
                    if fm2:
                        format_str = fm2.group(1)
                        break

                # Precio y unidad de medida (y < cy)
                price_elems = [e for e in card_elems if e['y'] < cy]
                price_elems = sorted(price_elems, key=lambda x: -x['y'])

                price_val = 0.0
                unit_val = 'kg'

                for pe in price_elems:
                    pm = re.search(r'([\d]+[.,\'’]\d{1,2})\s*€(?:\s*/\s*([a-záéíóú]+))?', pe['text'], re.IGNORECASE)
                    if pm:
                        price_val = float(pm.group(1).replace(',', '.').replace('\'', '.').replace('’', '.'))
                        if pm.group(2):
                            unit_val = pm.group(2).lower()
                        break
                    else:
                        num_m = re.search(r'^([\d]+[.,\'’]\d{1,2})$', pe['text'])
                        if num_m and price_val == 0.0:
                            price_val = float(num_m.group(1).replace(',', '.').replace('\'', '.').replace('’', '.'))
                        um = re.search(r'€\s*/\s*([a-záéíóú]+)', pe['text'], re.IGNORECASE)
                        if um:
                            unit_val = um.group(1).lower()

                if raw_name and ca['code'] and price_val > 0:
                    products.append({
                        'page': page_idx,
                        'supplier_product_code': ca['code'],
                        'raw_name': raw_name,
                        'format': format_str,
                        'price': price_val,
                        'unit': unit_val
                    })

        if self.save_output:
            output_dir = Path("data/processed")
            output_dir.mkdir(parents=True, exist_ok=True)
            output_file = output_dir / f"{path.stem}_extracted.json"
            output_file.write_text(json.dumps(products, ensure_ascii=False, indent=2))
            print(f"💾 Respaldo JSON guardado en: {output_file}")

        print(f"✅ [SpatialCardPdfExtractor] Se extrajeron {len(products)} productos estructurados.")
        return products


# ==============================================================================
# 4. ESTRATEGIA ESPECÍFICA DIALVA (Especialización del Extractor Espacial)
# ==============================================================================

class DialvaPdfExtractor(SpatialCardPdfExtractor):
    """Estrategia especializada con el perfil de reglas y filtros del catálogo de DIALVA Hostelería."""

    def __init__(self, save_output: bool = False):
        super().__init__(
            anchor_regex=r'[C|c][:.]?\s*(\d{3,5})',
            ignored_section_headers={
                'V GAMA', 'EL AUTÉNTICO', 'SABOR DE IT ALIA', 'SABOR DE ITALIA',
                'Y SUS QUESOS', 'PESCADOS', 'MARISCOS', 'CEFALÓPODOS',
                'EMBUTIDOS', 'CERDO', 'CERDO IBÉRICO DE', 'B E L LOTA', 'BELLOTA',
                'VACUNO', 'OFERTAS', 'DIALVA', 'PÁGINA', 'SEPTIEMBRE', '2026', 'CATALOGO',
                'FUMET DE', 'PESCADO', 'DE ROCA'
            },
            noise_phrases=[
                'POLÍGONO VIRGEN', 'DIALVA@', 'WWW.COMERCIALDIALVA', 'TELF.', '46950 XIRIVELLA',
                'LES MORERES', '@COMERCIALDIALVA', 'FAX 96 359', 'POTENCIA EL SABOR',
                'UNA VEZ DILUIDO', 'SE DILUYE', 'PREPARADO ES DE', 'UNA SELECCIÓN CON CARÁCTER',
                'SABOR Y JUGOSIDAD', 'DE CALDO DE PESCADO', 'ARROCES, PAELLAS', 'FIDEUÁS, SOPAS',
                'OBTIENES APROXIMADAMENTE', 'COSTE REAL DEL CALDO'
            ],
            x_tolerance=190.0,
            y_above=75.0,
            y_below=65.0,
            header_y_limit=780.0,
            save_output=save_output
        )


# ==============================================================================
# 5. ESTRATEGIA PDF TABULAR (Para listas de precios y albaranes convencionales en PDF)
# ==============================================================================

class TabularPdfExtractor(BaseCatalogExtractor):
    """Extractor para PDFs administrativos convencionales organizados por líneas/tablas de texto.
    
    A diferencia de catálogos publicitarios en cuadrícula, estos PDFs presentan
    una estructura lineal: [CÓDIGO/REF] [DESCRIPCIÓN] [FORMATO] [PRECIO] [UNIDAD].
    """

    def extract(self, file_path: Union[str, Path]) -> List[Dict[str, Any]]:
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Archivo PDF no encontrado: {file_path}")

        print(f"📑 [TabularPdfExtractor] Procesando PDF por líneas tabulares: {file_path}")
        reader = PdfReader(path)
        products: List[Dict[str, Any]] = []

        # Detección heurística de metadatos de proveedor en todas las páginas del PDF
        if len(reader.pages) > 0 and self.detected_supplier is None:
            full_text = "\n".join(page.extract_text() or "" for page in reader.pages)
            
            # 1. CIF / NIF
            cif_m = re.search(r'\b(?:CIF|NIF|N\.I\.F\.|C\.I\.F\.)?[:\s]*([A-HJ-NP-SUVW]\-?\d{7,8}[0-9A-J])\b', full_text, re.IGNORECASE)
            cif = cif_m.group(1).strip() if cif_m else None
            
            # 2. Teléfonos (fijo y móvil, incluyendo dobles separados por - o /)
            phone_m = re.search(
                r'(?:(?:tel[ée]fono|whatsapp|tlf|pedidos|contacto)[^\d\n]*)((?:\+?34\s*)?(?:[6789]\d(?:\s*\d){7})(?:\s*[-/y]\s*(?:\+?34\s*)?(?:[6789]\d(?:\s*\d){7}))?)',
                full_text,
                re.IGNORECASE
            )
            phone = phone_m.group(1).strip() if phone_m else None
            
            # 3. Email
            email_m = re.search(r'([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})', full_text)
            email = email_m.group(1).strip() if email_m else None
            
            # 4. Razón Social o Nombre de Empresa
            # Buscar primero líneas formales con forma societaria (S.L., S.A., C.B., etc.)
            supp_name = None
            company_m = re.search(r'([A-Za-zÁÉÍÓÚÑáéíóúñ\s,.-]{4,}(?:S\.L\.|S\.A\.|C\.B\.|S\.L\.U\.|S\.C\.|S\.A\.U\.))', full_text)
            if company_m:
                supp_name = re.sub(r'[\r\n]+', ' ', company_m.group(1)).strip()
                supp_name = re.sub(r'\s+', ' ', supp_name).strip()
                supp_name = re.sub(r'^[\s.,;:-]+|[\s.,;:-]+$', '', supp_name)
            
            if not supp_name:
                first_text = reader.pages[0].extract_text() or ""
                lines = [l.strip() for l in first_text.split('\n') if l.strip() and not any(k in l.lower() for k in ['pág', 'fecha', 'cif', 'tarifa', 'listado', 'nombre', 'precio', 'lote', 'kg', 'iva'])]
                supp_name = lines[0] if lines else path.stem.replace('-', ' ').replace('_', ' ').title()
            
            self.detected_supplier = {
                "name": supp_name,
                "cif": cif,
                "phone": phone,
                "email": email
            }

        # Patrones de ruido a descartar en PDFs administrativos
        noise_patterns = [
            re.compile(r'^(?:nombre|precio|medida|código|articulo|producto|tarifa|total|subtotal|pág|fecha)', re.I),
            re.compile(r'(?:c\.b\.|s\.l\.|s\.a\.|tel[ée]fono|whatsapp|reparto|contacto|@|domicilio|horario)', re.I),
            re.compile(r'^(?:lista de precios|verdura|fruta)', re.I)
        ]

        # Patrón flexible que captura líneas que terminan en precio y unidad opcional
        # Soporta: 'ACELGAS MANOJO 1,25€ KILO', 'CALABAZA 2,80 KILO', 'PATATA FREIR 1€ KILO', 'SOLOMILLO 24,50 €/KG', etc.
        line_pattern = re.compile(
            r'^(?P<content>.+?)\s+'
            r'(?P<price>\d+(?:[.,]\d{1,2})?)\s*'
            r'€?\s*(?:/\s*)?'
            r'(?P<unit>[a-záéíóúA-Z]+)?\s*$',
            re.I
        )
        subitem_pattern = re.compile(
            r'^\s*([A-Za-zÁÉÍÓÚáéíóúÑñ0-9\s/.,\-+ªº()]+?)\s+(\d+(?:[.,]\d+)?\s*(?:kg|ud|k))\s*$',
            re.I
        )

        for page in reader.pages:
            try:
                text = page.extract_text(extraction_mode="layout") or page.extract_text() or ""
            except Exception:
                text = page.extract_text() or ""

            current_bundle = None
            for line in text.split("\n"):
                line = line.strip()
                if not line or len(line) < 3:
                    continue
                if any(p.search(line) for p in noise_patterns):
                    continue

                m = line_pattern.match(line)
                if m:
                    content = m.group("content").strip()
                    price_str = m.group("price").replace(",", ".")
                    unit = (m.group("unit") or "ud").lower()
                    try:
                        price = float(price_str)
                    except ValueError:
                        continue

                    if price > 1000.0 or price <= 0.0:
                        continue

                    # Extraer código si el primer término es claramente un código (ej. REF01, 10023, C-12)
                    tokens = content.split()
                    first = tokens[0]
                    code = None
                    name = content
                    if len(tokens) > 1 and (re.search(r'\d', first) or (len(first) <= 5 and first.isupper() and first.isalnum() and not any(v in first.lower() for v in ['ajo', 'sol', 'pan', 'uvas', 'lomo', 'pera', 'atun']))):
                        code = first
                        name = " ".join(tokens[1:])

                    prod_dict = {
                        "supplier_product_code": code,
                        "raw_name": name.strip(),
                        "price": price,
                        "unit": unit,
                        "_subitems": []
                    }
                    products.append(prod_dict)
                    current_bundle = prod_dict
                elif current_bundle is not None:
                    sub_m = subitem_pattern.match(line)
                    if sub_m:
                        sub_name = sub_m.group(1).strip()
                        current_bundle["_subitems"].append(sub_name)

        # Enriquecer lotes y packs con el desglose de cortes que incluyen
        for prod in products:
            subitems = prod.pop("_subitems", [])
            if subitems:
                preview = ", ".join(s.title() for s in subitems)
                prod["format"] = f"Pack ({preview})"
                prod["raw_name"] = f"{prod['raw_name']} ({preview})"

        print(f"✅ [TabularPdfExtractor] Se extrajeron {len(products)} productos.")
        return products


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

        print("🔄 [GeminiMultimodalPdfExtractor] Activando fallback TabularPdfExtractor...")
        fallback = TabularPdfExtractor()
        items = fallback.extract(file_path)
        self.detected_supplier = fallback.detected_supplier
        return items


# ==============================================================================
# 6. FACTORÍA DE EXTRACTORES (Patrón Factoría - GoF)
# ==============================================================================

class ExtractorFactory:
    """Factoría responsable de instanciar y devolver la estrategia de extracción adecuada.
    
    Satisface el principio Open/Closed: para agregar soporte a nuevos formatos o
    proveedores, basta con registrar una nueva clase en el catálogo sin modificar
    el cliente ni el pipeline ETL.
    """

    _REGISTRY: Dict[tuple, Any] = {
        ("excel", None): GenericExcelExtractor,
        ("excel", "prov_paco_01"): GenericExcelExtractor,
        ("pdf", "prov_dialva_04"): DialvaPdfExtractor,
        ("pdf", "dialva"): DialvaPdfExtractor,
        ("pdf", "gemini"): GeminiMultimodalPdfExtractor,
        ("pdf", "auto"): GeminiMultimodalPdfExtractor,
        ("pdf", "nuevo"): GeminiMultimodalPdfExtractor,
        ("pdf", None): GeminiMultimodalPdfExtractor,  # Por defecto IA multimodal para PDFs nuevos
    }

    @classmethod
    def register(cls, file_type: str, provider_id: Optional[str], extractor_class: type):
        """Permite registrar dinámicamente nuevas estrategias en tiempo de ejecución."""
        cls._REGISTRY[(file_type.lower(), provider_id)] = extractor_class

    @classmethod
    def get_extractor(
        cls,
        file_path: Union[str, Path],
        provider_id: Optional[str] = None
    ) -> BaseCatalogExtractor:
        """Determina y crea la instancia del extractor adecuado según extensión y proveedor."""
        path = Path(file_path)
        ext = path.suffix.lower().strip('.')

        file_type = "excel" if ext in ["xlsx", "xls"] else "pdf" if ext == "pdf" else ext

        # 1. Búsqueda por par exacto (tipo, proveedor)
        if provider_id and (file_type, provider_id.lower()) in cls._REGISTRY:
            return cls._REGISTRY[(file_type, provider_id.lower())]()

        # 2. Si el proveedor contiene 'dialva' o el archivo es el catálogo de Dialva
        if "dialva" in path.stem.lower() or (provider_id and "dialva" in provider_id.lower()):
            return DialvaPdfExtractor()

        # 3. Fallback genérico por tipo de archivo
        if (file_type, None) in cls._REGISTRY:
            return cls._REGISTRY[(file_type, None)]()

        raise ValueError(f"No hay una estrategia de extracción registrada para tipo='{file_type}', proveedor='{provider_id}'")


# ==============================================================================
# 7. FUNCIONES PÚBLICAS Y DE COMPATIBILIDAD HACIA ATRÁS
# ==============================================================================

def extract_excel(file_path: Union[str, Path]) -> List[Dict[str, Any]]:
    """Función de compatibilidad: extrae datos desde Excel usando GenericExcelExtractor."""
    extractor = ExtractorFactory.get_extractor(file_path=file_path)
    return extractor.extract(file_path)


def extract_pdf(
    file_path: Union[str, Path],
    provider_id: Optional[str] = "prov_dialva_04",
    save_output: bool = False
) -> List[Dict[str, Any]]:
    """Función de compatibilidad: extrae datos desde PDF resolviendo la estrategia vía Factoría."""
    extractor = ExtractorFactory.get_extractor(file_path=file_path, provider_id=provider_id)
    if isinstance(extractor, SpatialCardPdfExtractor) and save_output:
        extractor.save_output = True
    return extractor.extract(file_path)


def extract_catalog(
    file_path: Union[str, Path],
    provider_id: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Punto de entrada universal: detecta el formato y proveedor y ejecuta el extractor adecuado."""
    extractor = ExtractorFactory.get_extractor(file_path=file_path, provider_id=provider_id)
    return extractor.extract(file_path)


def extract_catalog_with_supplier(
    file_path: Union[str, Path],
    provider_id: Optional[str] = None
) -> tuple[List[Dict[str, Any]], Optional[Dict[str, Any]]]:
    """Punto de entrada universal que devuelve tanto los productos extraídos como los metadatos del proveedor identificado."""
    extractor = ExtractorFactory.get_extractor(file_path=file_path, provider_id=provider_id)
    items = extractor.extract(file_path)
    return items, getattr(extractor, "detected_supplier", None)


def extract_image_list(image_bytes: bytes) -> List[Dict[str, Any]]:
    """Extrae productos manuscritos mediante OCR (lista de pizarra / nevera)."""
    from .vision_ai import process_fridge_photo
    return process_fridge_photo(image_bytes)


class CatalogExtractor:
    """Clase fachada (Facade) para exponer los extractores de forma unificada."""

    @staticmethod
    def extract_excel(file_path: Union[str, Path]) -> List[Dict[str, Any]]:
        return extract_excel(file_path)

    @staticmethod
    def extract_pdf(
        file_path: Union[str, Path],
        provider_id: Optional[str] = "prov_dialva_04",
        save_output: bool = True
    ) -> List[Dict[str, Any]]:
        return extract_pdf(file_path, provider_id=provider_id, save_output=save_output)

    @staticmethod
    def extract_ocr(image_bytes: bytes) -> List[Dict[str, Any]]:
        return extract_image_list(image_bytes)
