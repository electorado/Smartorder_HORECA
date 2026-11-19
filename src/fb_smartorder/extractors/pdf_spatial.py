import json
import re
from pathlib import Path
from typing import List, Dict, Any, Union, Optional, Set
from pypdf import PdfReader

from .base import BaseCatalogExtractor, detect_supplier_from_pdf


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

            # Los anclajes de columna izquierda tienen X < 220, y los de columna derecha X > 295.
            # Los elementos de texto/precio de columna izquierda se extienden hasta X ~ 280,
            # y los de columna derecha empiezan a partir de X ~ 285.
            left_anchors = sorted([a for a in anchors if a['x'] < 250.0], key=lambda a: -a['y'])
            right_anchors = sorted([a for a in anchors if a['x'] >= 250.0], key=lambda a: -a['y'])

            for col_anchors, is_left in [(left_anchors, True), (right_anchors, False)]:
                for i, a in enumerate(col_anchors):
                    cy = a['y']
                    # Delimitación superior e inferior de la tarjeta
                    top_y = cy + 8.0
                    bottom_y = (col_anchors[i+1]['y'] + 6.0) if (i + 1 < len(col_anchors)) else max(25.0, cy - 140.0)

                    card_elems = [
                        e for e in filtered
                        if (e['x'] < 285.0 if is_left else e['x'] >= 285.0)
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
                                combined_desc = f"{full_title} {fmt} {full_card_text}".lower()
                                if any(t in combined_desc for t in ['tarta', 'pastel', 'brazo', 'tiramisú', 'tiramisu', 'postre']):
                                    unit = 'ud'
                                elif 'bolsa' in combined_desc:
                                    unit = 'bolsa'
                                elif 'estuche' in combined_desc:
                                    unit = 'estuche'
                                elif 'tarrina' in combined_desc:
                                    unit = 'tarrina'
                                elif 'bandeja' in combined_desc:
                                    unit = 'bandeja'
                                elif '1 unidad' in combined_desc or 'unidades' in fmt.lower():
                                    unit = 'ud'
                                else:
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

