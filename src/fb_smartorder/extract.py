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


def detect_supplier_from_pdf(reader: PdfReader, path: Path) -> Dict[str, Any]:
    """Extrae metadatos de proveedor examinando portada y contraportada con filtros anti-producto."""
    num_pages = len(reader.pages)
    sample_pages = []
    sample_pages.extend(reader.pages[:min(3, num_pages)])
    if num_pages > 3:
        sample_pages.extend(reader.pages[max(3, num_pages - 2):])
    full_text = "\n".join(p.extract_text() or "" for p in sample_pages)
    stem_lower = path.stem.lower()
    supp_name = None

    # 1. Identificación por marca conocida HORECA
    if "dialva" in stem_lower or "dialva" in full_text.lower():
        supp_name = "DIALVA Hostelería S.L."
    elif "abordo" in stem_lower or "abordo" in full_text.lower() or "servifrio" in full_text.lower():
        supp_name = "Abordo Hostelería / Servifrío"
    elif "ferjusanz" in stem_lower or "ferjusanz" in full_text.lower():
        supp_name = "VERDURA FERJUSANZ C.B"
    elif "morego" in stem_lower or "morego" in full_text.lower():
        supp_name = "MOREGO INDUSTRIAS CÁRNICAS, S.L"
    elif "ahumados" in stem_lower or "dominguez" in full_text.lower() or "domínguez" in full_text.lower():
        supp_name = "Ahumados Domínguez"

    # 2. Si no es marca conocida, buscar razón social con forma jurídica
    if not supp_name:
        comp_m = re.search(r"([A-Za-zÁÉÍÓÚÑáéíóúñ\s,.-]{4,40}(?:S\.L\.|S\.A\.|C\.B\.|S\.L\.U\.))", full_text)
        if comp_m:
            cand = comp_m.group(1).strip()
            words = cand.split()
            cleaned_words = []
            for w in words:
                n = len(w)
                if n >= 4 and n % 2 == 0 and w[:n//2].lower() == w[n//2:].lower():
                    cleaned_words.append(w[:n//2])
                else:
                    cleaned_words.append(w)
            cand_clean = " ".join(cleaned_words).strip()
            if not any(cand_clean.lower().startswith(p) for p in ["kg ", "lote ", "pack ", "caja ", "bandeja ", "pieza "]):
                supp_name = cand_clean

    # 3. Fallback a nombre de archivo limpio
    if not supp_name:
        clean_stem = re.sub(r"(?i)(?:catalogo|tarifa|lista|precios|noviembre|diciembre|enero|febrero|marzo|\d{4})", "", path.stem)
        clean_stem = re.sub(r"[-_]+", " ", clean_stem).strip().title()
        supp_name = clean_stem if len(clean_stem) >= 3 else "Proveedor HORECA"

    # 4. Teléfono (fijos y móviles)
    phone_m = re.search(r"(?:tel[ée]fonos?|whatsapp|tfno|pedidos|telf)[^\d\n]*((?:\+?34\s*)?[6789]\d[\d\s\-/y]{7,35})", full_text, re.I)
    phone_raw = phone_m.group(1).strip() if phone_m else None
    phone = None
    if phone_raw:
        parts = re.split(r'[/,;\n|y\-]', phone_raw)
        cands = []
        for p in parts:
            d = re.sub(r'[^\d]', '', p)
            if d.startswith("34") and len(d) == 11:
                d = d[2:]
            if len(d) == 9:
                cands.append(d)
        if cands:
            mobile = next((c for c in cands if c.startswith(('6', '7'))), None)
            phone = mobile if mobile else cands[0]
        else:
            phone = re.sub(r"\s+", " ", phone_raw).strip(" .,;:-")

    # 5. CIF / NIF
    cif_m = re.search(r"\b(?:CIF|NIF|N\.I\.F\.|C\.I\.F\.)?[:\s]*([A-HJ-NP-SUVW]\-?\d{7,8}[0-9A-J])\b", full_text, re.I)
    cif = cif_m.group(1).strip() if cif_m else None

    # 6. Email (real)
    email_m = re.search(r"\b([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})\b", full_text)
    email = None
    if email_m:
        cand_email = email_m.group(1).lower().strip()
        if not any(d in cand_email for d in ["adobe.com", "google.com", "example.com", "pedidos@proveedor"]):
            email = cand_email

    return {"name": supp_name, "cif": cif, "phone": phone, "email": email}


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
        anchor_regex: str = r'[C|c][:.-]?\s*(\d{3,5})',
        ignored_section_headers: Optional[Set[str]] = None,
        noise_phrases: Optional[List[str]] = None,
        x_tolerance: float = 190.0,
        y_above: float = 85.0,
        y_below: float = 80.0,
        header_y_limit: float = 950.0,
        save_output: bool = False
    ):
        super().__init__()
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
        s = text.strip(' ·-,')
        if s.startswith('(') and s.endswith(')'):
            s = s[1:-1].strip(' ·-,')
        if s.count('(') > s.count(')'):
            s = s.rstrip('(')
        elif s.count(')') > s.count('('):
            s = s.rstrip(')')
        return s.strip()

    def extract(self, file_path: Union[str, Path]) -> List[Dict[str, Any]]:
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Archivo PDF no encontrado: {file_path}")

        print(f"📑 [SpatialCardPdfExtractor] Analizando maquetación por tarjetas: {file_path}")
        reader = PdfReader(path)
        products: List[Dict[str, Any]] = []

        # Detección de proveedor
        if self.detected_supplier is None and len(reader.pages) > 0:
            self.detected_supplier = detect_supplier_from_pdf(reader, path)

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
                elif e['text'].isdigit() and len(e['text']) in [3, 4, 5] and i > 0 and ('C:' in filtered_elements[i-1]['text'] or re.search(r'[C|c][:.-]\s*$', filtered_elements[i-1]['text'])):
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
                name_candidates = [
                    e for e in card_elems
                    if cy - 6.0 <= e['y'] <= cy + self.y_above
                    and not any(k in e['text'].lower() for k in ['caja:', 'antes:', 'le sale'])
                ]
                name_candidates = sorted(name_candidates, key=lambda x: -x['y'])

                name_tokens = []
                for nc in name_candidates:
                    clean_t = self._clean_product_name(nc['text'])
                    clean_t = re.sub(r'\b[C|c][:.-]?\s*\d+\b', '', clean_t, flags=re.IGNORECASE).strip(' ·-,')
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
                    fm3 = re.search(r'(caja:?\s*[\d.,]+\s*k?g|[\d.,]+\s*pzas?\.?/kg)', e['text'], re.I)
                    if fm3:
                        format_str = fm3.group(1)
                        break

                # Precio y unidad de medida (agrupación de líneas de precio por coordenada Y)
                price_elems = [e for e in card_elems if e['y'] <= cy]
                lines_by_y = {}
                for pe in price_elems:
                    found_y = None
                    for yb in lines_by_y:
                        if abs(pe['y'] - yb) <= 3.5:
                            found_y = yb
                            break
                    if found_y is None:
                        found_y = pe['y']
                        lines_by_y[found_y] = []
                    lines_by_y[found_y].append(pe)

                price_val = 0.0
                unit_val = 'kg'

                # Prioridad 1: Precio explícito con unidad (€/kg, €/ud, €/caja, €/tarta, €/estuche)
                for yb in sorted(lines_by_y.keys(), key=lambda y: -y):
                    row_elems = sorted(lines_by_y[yb], key=lambda e: e['x'])
                    line_str = ' '.join(e['text'] for e in row_elems)
                    if any(np in line_str.lower() for np in ['antes', 'le sale']):
                        continue
                    pm = re.search(r'([\d]+[.,\'’]\d{1,2})\s*€\s*/\s*([a-záéíóú]+)', line_str, re.IGNORECASE)
                    if pm:
                        val = float(pm.group(1).replace(',', '.').replace('\'', '.').replace('’', '.'))
                        if 0.5 <= val <= 500.0:
                            price_val = val
                            unit_val = pm.group(2).lower()
                            break

                # Prioridad 2: Número con símbolo € directo en la línea
                if price_val == 0.0:
                    for yb in sorted(lines_by_y.keys(), key=lambda y: -y):
                        row_elems = sorted(lines_by_y[yb], key=lambda e: e['x'])
                        line_str = ' '.join(e['text'] for e in row_elems)
                        if any(np in line_str.lower() for np in ['antes', 'le sale']):
                            continue
                        pm = re.search(r'([\d]+[.,\'’]\d{1,2})\s*€', line_str, re.IGNORECASE)
                        if pm:
                            val = float(pm.group(1).replace(',', '.').replace('\'', '.').replace('’', '.'))
                            if 0.5 <= val <= 500.0:
                                price_val = val
                                break

                # Prioridad 3: Número suelto en la tarjeta si tiene precio numérico estándar
                if price_val == 0.0:
                    for pe in price_elems:
                        tu = pe['text'].lower()
                        if any(np in tu for np in ['antes', 'le sale']):
                            continue
                        num_m = re.match(r'^([\d]+[.,\'’]\d{1,2})$', pe['text'])
                        if num_m:
                            val = float(num_m.group(1).replace(',', '.').replace('\'', '.').replace('’', '.'))
                            if 0.5 <= val <= 500.0:
                                price_val = val
                                break

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
                'EMBUTIDOS', 'VACUNO', 'OFERTAS', 'DIALVA', 'PÁGINA', 'SEPTIEMBRE', '2026', 'CATALOGO'
            },
            noise_phrases=[
                'POLÍGONO VIRGEN', 'DIALVA@', 'WWW.COMERCIALDIALVA', 'TELF.', '46950 XIRIVELLA',
                'LES MORERES', '@COMERCIALDIALVA', 'FAX 96 359', 'POTENCIA EL SABOR',
                'UNA VEZ DILUIDO', 'SE DILUYE', 'PREPARADO ES DE', 'UNA SELECCIÓN CON CARÁCTER',
                'SABOR Y JUGOSIDAD', 'DE CALDO DE PESCADO', 'ARROCES, PAELLAS', 'FIDEUÁS, SOPAS',
                'OBTIENES APROXIMADAMENTE', 'COSTE REAL DEL CALDO'
            ],
            x_tolerance=190.0,
            y_above=85.0,
            y_below=80.0,
            header_y_limit=950.0,
            save_output=save_output
        )


# ==============================================================================
# 4.1. ESTRATEGIA ESPECÍFICA ABORDO / SERVIFRÍO (Extractor Espacial de Tarjetas)
# ==============================================================================

class AbordoPdfExtractor(BaseCatalogExtractor):
    """Estrategia especializada con delimitación geométrica de tarjetas y lógica de precios
    para el catálogo de Abordo Hostelería / Servifrío.
    
    Resuelve específicamente:
    1. Delimitación vertical de tarjetas consecutivas para evitar que precios o textos de una tarjeta
       se mezclen con el título o datos de la tarjeta adyacente.
    2. Identificación precisa del título en la línea del anclaje C-XXXX y su posible continuación (subline).
    3. Captura del precio real de oferta (destacado/rojo), descartando los ganchos de precio por ración
       ("La ración de ... le sale a X,XX €") y los precios antiguos ("antes: XX,XX €").
    4. Detección de unidad correcta ('ud' para 'La unidad le sale a: XX,XX €' o 'XX,XX €/u', 'kg' para 'XX,XX €/kg').
    """

    def __init__(self, save_output: bool = False):
        super().__init__()
        self.save_output = save_output

    def extract(self, file_path: Union[str, Path]) -> List[Dict[str, Any]]:
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Archivo PDF no encontrado: {file_path}")

        print(f"📑 [AbordoPdfExtractor] Procesando catálogo Abordo con motor espacial: {file_path}")
        reader = PdfReader(path)
        products: List[Dict[str, Any]] = []

        if self.detected_supplier is None and len(reader.pages) > 0:
            self.detected_supplier = detect_supplier_from_pdf(reader, path)

        UNIT_MAP = {
            'kilo': 'kg', 'kilos': 'kg', 'uds': 'ud', 'unidad': 'ud', 'unidades': 'ud',
            'cajas': 'caja', 'bolsas': 'bolsa', 'estuches': 'estuche', 'tarrinas': 'tarrina', 'u': 'ud'
        }

        for page_idx, page in enumerate(reader.pages, start=1):
            page_width = float(page.mediabox.width) if hasattr(page, 'mediabox') and page.mediabox else 595.0
            midpoint = page_width / 2.0
            elements = []

            def visitor(text, cm, tm, font_dict, font_size):
                t = text.strip()
                if t:
                    elements.append({
                        'x': round(tm[4], 1),
                        'y': round(tm[5], 1),
                        'text': t,
                        'size': font_size
                    })

            page.extract_text(visitor_text=visitor)

            filtered = [e for e in elements if 25.0 < e['y'] < 800.0]

            anchors = []
            for e in filtered:
                m = re.search(r'\b(C-\d{3,5})\b', e['text'])
                if m:
                    anchors.append({'code': m.group(1), 'x': e['x'], 'y': e['y']})

            left_anchors = sorted([a for a in anchors if a['x'] < midpoint], key=lambda a: -a['y'])
            right_anchors = sorted([a for a in anchors if a['x'] >= midpoint], key=lambda a: -a['y'])

            for col_anchors, is_left in [(left_anchors, True), (right_anchors, False)]:
                for i, a in enumerate(col_anchors):
                    cy = a['y']
                    # Delimitación superior e inferior de la tarjeta
                    top_y = cy + 8.0
                    bottom_y = (col_anchors[i+1]['y'] + 6.0) if (i + 1 < len(col_anchors)) else max(25.0, cy - 140.0)

                    card_elems = [
                        e for e in filtered
                        if (e['x'] < midpoint if is_left else e['x'] >= midpoint)
                        and bottom_y <= e['y'] <= top_y
                    ]

                    # 1. Título del producto: línea del código anclaje
                    title_elems = sorted([e for e in card_elems if abs(e['y'] - cy) <= 4.0 and e['x'] >= a['x']], key=lambda e: e['x'])
                    title_1 = ' '.join(e['text'] for e in title_elems)
                    title_1 = re.sub(r'\bC-\d{3,5}\b', '', title_1).strip(' ·-,')

                    # Posible continuación del título en la línea inmediatamente inferior (subline)
                    sub_elems = sorted(
                        [e for e in card_elems if (cy - 16.0) <= e['y'] <= (cy - 8.0) and abs(e['x'] - a['x']) < 180.0],
                        key=lambda e: e['x']
                    )
                    sub_text = ' '.join(e['text'] for e in sub_elems)
                    sub_title = re.sub(r'\([^)]+\)', '', sub_text).strip(' ·-,')

                    if sub_title and not any(k in sub_title.lower() for k in ['caja', 'el kg', 'le sale', 'antes', 'bolsa', 'estuche', 'pata', 'kg/pza']):
                        full_title = f"{title_1} {sub_title}".strip()
                    else:
                        full_title = title_1

                    # 2. Formato de presentación
                    fmt = ''
                    for e in card_elems:
                        m_caja = re.search(r'(Caja:\s*[^/\n]+)', e['text'], re.I)
                        if m_caja:
                            fmt = m_caja.group(1).strip()
                            break
                        m_est = re.search(r'(Estuche\s*[^/\n]+|Bolsa\s*[^/\n]+|Tarrina\s*[^/\n]+)', e['text'], re.I)
                        if m_est:
                            fmt = m_est.group(1).strip()
                            break
                    if fmt:
                        fmt = fmt.rstrip(')')

                    # 3. Precio y Unidad
                    card_sorted = sorted(card_elems, key=lambda e: (-e['y'], e['x']))
                    full_card_text = ' '.join(e['text'] for e in card_sorted)

                    price = 0.0
                    unit = 'kg'

                    # Caso A: Precio unitario ("La unidad le sale a: XX,XX €")
                    m_unit = re.search(r'(\d+[.,]\d{2})\s*€?\s*(?:La\s+)?unidad\s+le\s+sale\s+a', full_card_text, re.I) or \
                             re.search(r'(?:La\s+)?unidad\s+le\s+sale\s+a:?\s*(\d+[.,]\d{2})', full_card_text, re.I)
                    if m_unit:
                        price = float(m_unit.group(1).replace(',', '.'))
                        unit = 'ud'
                    else:
                        # Limpiar precios antiguos ("antes: XX,XX") y ganchos de ración ("le sale a XX,XX")
                        cleaned = re.sub(r'antes:\s*[\d.,]+\s*€?(?:/[a-z]+)?', '', full_card_text, flags=re.I)
                        cleaned = re.sub(r'(?:ración|pata|pieza|kg|bolsa|estuche)\s+de[^\n€]*le\s+sale\s+a\s*[\d.,]+\s*€?', '', cleaned, flags=re.I)
                        cleaned = re.sub(r'le\s+sale\s+a\s*[\d.,]+\s*€?', '', cleaned, flags=re.I)

                        # Buscar precio de oferta con unidad explícita
                        m_price = re.search(r'(\d+[.,]\d{2})\s*€\s*/?\s*(kg|kilo|kilos|u|ud|uds|unidad|unidades|caja|cajas|bolsa|bolsas|estuche|estuches|tarrina|tarrinas|bandeja|bandejas|sobre|sobres|lote|lotes|pack|packs)\b', cleaned, re.I)
                        if m_price:
                            price = float(m_price.group(1).replace(',', '.'))
                            raw_u = m_price.group(2).lower()
                            unit = UNIT_MAP.get(raw_u, raw_u)
                        else:
                            m_eur = re.search(r'(\d+[.,]\d{2})\s*€', cleaned, re.I)
                            if m_eur:
                                price = float(m_eur.group(1).replace(',', '.'))
                                unit = 'kg'

                    if full_title and price > 0:
                        products.append({
                            'page': page_idx,
                            'supplier_product_code': a['code'],
                            'raw_name': full_title,
                            'format': fmt,
                            'price': price,
                            'unit': unit
                        })

        if self.save_output:
            output_dir = Path("data/processed")
            output_dir.mkdir(parents=True, exist_ok=True)
            output_file = output_dir / f"{path.stem}_extracted.json"
            output_file.write_text(json.dumps(products, ensure_ascii=False, indent=2))
            print(f"💾 Respaldo JSON guardado en: {output_file}")

        print(f"✅ [AbordoPdfExtractor] Se extrajeron {len(products)} productos estructurados.")
        return products


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

        # Detección de proveedor
        if self.detected_supplier is None and len(reader.pages) > 0:
            self.detected_supplier = detect_supplier_from_pdf(reader, path)

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
# 5.1. ESTRATEGIA TABULAR POR COORDENADAS (Tablas con precios en columna separada)
# ==============================================================================

class CoordinateTablePdfExtractor(BaseCatalogExtractor):
    """Extractor para PDFs tabulares estructurados con columnas separadas geométricamente (ej. Morego).
    
    Asocia el código y nombre del producto o lote en el lado izquierdo con su precio
    ubicado exactamente a la misma altura vertical (Y) en la columna de importes.
    Agrupa los cortes o sub-ítems pertenecientes a cada lote.
    """
    def extract(self, file_path: Union[str, Path]) -> List[Dict[str, Any]]:
        path = Path(file_path)
        reader = PdfReader(path)
        products: List[Dict[str, Any]] = []

        # Extraer metadatos de proveedor
        self.detected_supplier = detect_supplier_from_pdf(reader, path)

        for page_idx, page in enumerate(reader.pages, start=1):
            elements = []
            def visitor(text, cm, tm, font_dict, font_size):
                t = text.strip()
                if t: elements.append({'x': round(tm[4], 1), 'y': round(tm[5], 1), 'text': t})
            page.extract_text(visitor_text=visitor)

            # Buscar anclajes de Lotes o productos principales
            anchors = [e for e in elements if 'LOTE' in e['text'].upper() or re.match(r'^\d{4}\s+[A-Z]', e['text'])]
            anchors = sorted(anchors, key=lambda a: -a['y'])

            for i, a in enumerate(anchors):
                ay = a['y']
                next_y = anchors[i+1]['y'] if i + 1 < len(anchors) else 50.0

                # Buscar precio a la misma altura Y (+/- 4 pt) en la columna derecha (X > 280)
                price = None
                for pe in elements:
                    if abs(pe['y'] - ay) <= 4.0 and pe['x'] > 280.0:
                        m = re.search(r'(\d+[.,]\d{2})', pe['text'])
                        if m:
                            price = float(m.group(1).replace(',', '.'))
                            break

                # Sub-cortes incluidos en el lote
                subitems = []
                for se in elements:
                    if next_y < se['y'] < (ay - 4.0) and se['x'] < 300.0:
                        clean_s = re.sub(r'\s+\d+\s*kg$', '', se['text'], flags=re.I).strip()
                        if clean_s and len(clean_s) > 2 and 'pedido' not in clean_s.lower() and 'domicilio' not in clean_s.lower():
                            subitems.append(clean_s)

                if price and price > 0:
                    clean_name = a['text'].strip()
                    code_m = re.match(r'^(\d{3,5})\s+(.*)$', clean_name)
                    code = code_m.group(1) if code_m else None
                    name = code_m.group(2) if code_m else clean_name

                    sub_desc = f" ({', '.join(s.title() for s in subitems[:8])})" if subitems else ""
                    products.append({
                        'supplier_product_code': code,
                        'raw_name': f"{name.title()}{sub_desc}",
                        'price': price,
                        'unit': 'ud',
                        'format': f"Lote surtido ({len(subitems)} cortes)" if subitems else "Pack cárnico",
                        '_subitems': subitems
                    })

        print(f"✅ [CoordinateTablePdfExtractor] Se extrajeron {len(products)} lotes estructurados.")
        return products


# ==============================================================================
# 5.2. ESTRATEGIA FLYER PUBLICITARIO 2D (Ofertas gráficas y multicolumna)
# ==============================================================================

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
        ("pdf", "prov_abordo_02"): AbordoPdfExtractor,
        ("pdf", "abordo"): AbordoPdfExtractor,
        ("pdf", "gemini"): GeminiMultimodalPdfExtractor,
        ("pdf", "auto"): UniversalPdfExtractor,
        ("pdf", "nuevo"): UniversalPdfExtractor,
        ("pdf", None): UniversalPdfExtractor,  # Por defecto extractor universal adaptativo
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

        # 2.1. Si el proveedor contiene 'abordo' o 'servifrio' o el archivo es de Abordo
        if any(k in path.stem.lower() for k in ["abordo", "servifrio", "servifrío"]) or (
            provider_id and any(k in provider_id.lower() for k in ["abordo", "servifrio", "servifrío"])
        ):
            return AbordoPdfExtractor()

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
