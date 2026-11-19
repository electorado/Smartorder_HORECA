import re
from pathlib import Path
from typing import List, Dict, Any, Union, Optional, Set
from pypdf import PdfReader

from .base import BaseCatalogExtractor, detect_supplier_from_pdf


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

