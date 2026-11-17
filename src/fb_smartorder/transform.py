import re
import unicodedata
from typing import List, Dict, Any
from rapidfuzz import process, fuzz


STOPWORDS_ES = {
    "de", "del", "con", "el", "la", "los", "las", "un", "una",
    "en", "y", "a", "al", "para", "por", "sin", "sobre", "s", "c", "pa",
    "kg", "ud", "uds", "gr", "kilos", "kilo", "pieza", "piezas", "extra", "super", "brik"
}

# Mapa ontológico / taxonómico de familias de alimentos (Hostelería)
TAXONOMY_MAP = {
    # Vacuno (bovino)
    "vaca": "vacuno",
    "ternera": "vacuno",
    "buey": "vacuno",
    "anojo": "vacuno",
    "novillo": "vacuno",
    "angus": "vacuno",
    # Porcino
    "cerdo": "porcino",
    "puerco": "porcino",
    "cochinillo": "porcino",
    "iberico": "porcino",
    # Aves
    "pollo": "ave",
    "pavo": "ave",
    "gallina": "ave",
    # Cortes
    "chuleton": "chuleta",
    # Pescados / Cefalópodos
    "chopo": "sepia",
    "pota": "calamar",
    # Aceites
    "aove": "oliva"
}

# Cortes y formatos de carne / pescado reconocidos para evitar mezclar partes incompatibles
KNOWN_CUTS = {
    "solomillo", "chuletero", "chuleton", "chuleta", "chuletas", "lomo",
    "entrecot", "falda", "aguja", "carrillada", "churrasco",
    "secreto", "lagarto", "codillo", "cabecero", "picana",
    "pechuga", "filete", "filetes", "tartar", "hamburguesa", "hamburguesas",
    "costilla", "costillas", "alita", "alitas", "muslito", "muslitos", "jamoncito", "jamoncitos"
}


def clean_tokens(text: str) -> list[str]:
    """Extrae tokens normalizados semántica y fonéticamente."""
    text_norm = unicodedata.normalize("NFKD", text)
    text_clean = "".join(c for c in text_norm if unicodedata.category(c) != "Mn").lower()
    text_clean = re.sub(r'\(?c[.:]?\s*\d+\)?', '', text_clean)
    text_clean = re.sub(r'\b\d+[.,\'’]\d{1,2}\s*€(?:/\w+)?\b', '', text_clean)
    text_clean = re.sub(r'[*!¡?¿#%]', '', text_clean)
    text_clean = re.sub(r'[^\w\s]', ' ', text_clean)
    
    tokens = []
    for t in text_clean.split():
        if t in STOPWORDS_ES or len(t) < 3 or t.isdigit():
            continue
        tokens.append(TAXONOMY_MAP.get(t, t))
    return tokens


def parse_product_structure(text: str):
    """Separa el producto principal (head) de notas accesorias ('con...', 'c/...', notas entre paréntesis)."""
    clean_txt = re.sub(r'\(.*?\)', '', text)
    parts = re.split(r'\b(?:con|c/)\b', clean_txt, flags=re.IGNORECASE)
    head_txt = parts[0].strip()
    head_tokens = clean_tokens(head_txt)
    all_tokens = clean_tokens(text)
    raw_cut = next((t for t in head_tokens if t in KNOWN_CUTS), None)
    if raw_cut:
        head_cut = raw_cut[:-1] if raw_cut.endswith("s") and len(raw_cut) > 4 else raw_cut
    else:
        head_cut = None
    return {
        "head_tokens": set(head_tokens),
        "all_tokens": set(all_tokens),
        "head_cut": head_cut
    }


def clean_product_text(text: str) -> str:
    """Limpia ruido del texto (acentos, mayúsculas, códigos, precios y palabras promocionales)."""
    if not text:
        return ""
    
    text_normalized = unicodedata.normalize('NFKD', text)
    text_without_accents = ''.join(c for c in text_normalized if unicodedata.category(c) != 'Mn')
    text_clean = text_without_accents.lower().strip()
    
    noise_patterns = [
        r'\b1[aa]\s+calidad\b',
        r'\boferta\b',
        r'\bpromocion\b',
        r'\bsuper\b',
        r'\bprecio\s+especial\b',
        r'\(?c[.:]?\s*\d+\)?',
        r'\b\d+[.,\'’]\d{1,2}\s*€(?:/\w+)?\b',
        r'[*!¡?¿#%]'
    ]
    for pattern in noise_patterns:
        text_clean = re.sub(pattern, '', text_clean)
        
    text_clean = re.sub(r'\s+', ' ', text_clean).strip()
    return text_clean


def normalize_metric_dimension(
    price: float,
    unit: str,
    format_str: str = ""
) -> Dict[str, Any]:
    """Normaliza formatos y unidades heterogéneas a unidades canónicas estándar (kg, L, ud).
    
    Calcula la métrica base y el precio unitario comparable (precio/kg, precio/L o precio/ud)
    para permitir comparativas homogéneas entre ofertas de diferentes proveedores y empaques.
    
    Ejemplos:
        - 12.50 €/caja con formato '1ud X 3.6kg' -> 3.47 €/kg (canonical_unit='kg')
        - 4.50 €/sobre con formato '5uds X 0.1kg' -> 45.00 €/kg (canonical_unit='kg')
        - 7.98 €/ud con formato '16uds X 0.2kg' -> 39.90 €/kg (canonical_unit='kg')
        - 28.80 €/kg -> 28.80 €/kg (canonical_unit='kg')
    """
    unit_clean = (unit or "").lower().strip()
    fmt = (format_str or "").lower().strip()

    # 1. Caso base: la unidad ya está en kilos
    if unit_clean in ["kg", "kilo", "kilos", "kilogramo"]:
        return {
            "canonical_unit": "kg",
            "canonical_quantity": 1.0,
            "canonical_price": round(price, 2)
        }

    # 2. Caso base: la unidad ya está en litros
    if unit_clean in ["l", "litro", "litros", "l."]:
        return {
            "canonical_unit": "L",
            "canonical_quantity": 1.0,
            "canonical_price": round(price, 2)
        }

    # 3. Empaques compuestos: Nuds X M kg/gr/L/ml (ej. 14uds X 1kg, 12ud X 0,25kg)
    mult_match = re.search(r'(\d+)\s*uds?\s*[xX]\s*([\d.,]+)\s*(k?g|m?l|l)\b', fmt)
    if mult_match:
        count = float(mult_match.group(1))
        unit_weight = float(mult_match.group(2).replace(',', '.'))
        measure_unit = mult_match.group(3).lower()

        if measure_unit in ["g", "gr"]:
            unit_weight /= 1000.0
            measure_unit = "kg"
        elif measure_unit == "ml":
            unit_weight /= 1000.0
            measure_unit = "l"

        canonical_unit = "kg" if measure_unit == "kg" else "L" if measure_unit == "l" else "ud"

        # Si el precio es de la caja/estuche completo, dividimos entre el peso total del lote
        if unit_clean in ["caja", "estuche", "pack", "lote"]:
            total_qty = count * unit_weight
            canonical_price = price / total_qty if total_qty > 0 else price
        # Si el precio es por sobre/pieza/ud/pizza individual, dividimos entre el peso de una unidad
        elif unit_clean in ["sobre", "pieza", "pizza", "ud", "unidad"]:
            total_qty = unit_weight
            canonical_price = price / total_qty if total_qty > 0 else price
        else:
            total_qty = count * unit_weight
            canonical_price = price / total_qty if total_qty > 0 else price

        return {
            "canonical_unit": canonical_unit,
            "canonical_quantity": round(total_qty, 3),
            "canonical_price": round(canonical_price, 2)
        }

    # 4. Formato simple: '5kg', '500g', '2.5L', '750ml'
    single_match = re.search(r'([\d.,]+)\s*(k?g|m?l|l)\b', fmt or unit_clean)
    if single_match:
        qty = float(single_match.group(1).replace(',', '.'))
        measure_unit = single_match.group(2).lower()
        if measure_unit in ["g", "gr"]:
            qty /= 1000.0
            measure_unit = "kg"
        elif measure_unit == "ml":
            qty /= 1000.0
            measure_unit = "l"

        canonical_unit = "kg" if measure_unit == "kg" else "L" if measure_unit == "l" else "ud"
        canonical_price = price / qty if qty > 0 else price
        return {
            "canonical_unit": canonical_unit,
            "canonical_quantity": round(qty, 3),
            "canonical_price": round(canonical_price, 2)
        }

    # 5. Formato por docenas o unidades discretas
    if "docena" in unit_clean or "docena" in fmt:
        return {
            "canonical_unit": "ud",
            "canonical_quantity": 12.0,
            "canonical_price": round(price / 12.0, 2)
        }

    # Por defecto: unidad discreta (ud)
    return {
        "canonical_unit": "ud",
        "canonical_quantity": 1.0,
        "canonical_price": round(price, 2)
    }


def resolve_entities(
    raw_products: List[Dict[str, Any]],
    master_ingredients: List[Dict[str, Any]],
    threshold: float = 60.0
) -> List[Dict[str, Any]]:
    """Algoritmo de Entity Resolution ontológico para F&B.
    
    Principios de resolución:
    1. Distinción de producto principal vs. accesorios ('Chuletero con Solomillo' no es Solomillo).
    2. Compatibilidad taxonómica (Vaca / Ternera / Añojo pertenecen a 'Vacuno').
    3. Coherencia de corte: un producto con corte noble explícito no se asigna a otro corte ni a recortes/guiso.
    4. Cobertura conceptual ponderada sin sesgo por conectores comunes.
    """
    print(f"🧠 Ejecutando Entity Resolution ontológico para {len(raw_products)} productos...")
    
    if not master_ingredients:
        for p in raw_products:
            p["clean_name"] = clean_product_text(p.get("raw_name", ""))
            metric_info = normalize_metric_dimension(
                price=p.get("price", 0.0),
                unit=p.get("unit", ""),
                format_str=p.get("format", "")
            )
            p.update(metric_info)
            p["master_ingredient_id"] = None
            p["similarity_score"] = 0.0
        return raw_products

    # Estructurar ingredientes maestros
    master_prepared = []
    for ing in master_ingredients:
        m_struct = parse_product_structure(ing["name"])
        m_tokens = clean_tokens(ing["name"])
        m_root = m_tokens[0] if m_tokens else ""
        master_prepared.append({
            "id": ing["id"],
            "name": ing["name"],
            "root": m_root,
            "tokens": set(m_tokens),
            "cut": m_struct["head_cut"]
        })

    results = []
    for prod in raw_products:
        raw_name = prod.get("raw_name", "")
        c_name = clean_product_text(raw_name)
        prod["clean_name"] = c_name
        
        # Normalización métrica y dimensional del formato y precio unitario
        metric_info = normalize_metric_dimension(
            price=prod.get("price", 0.0),
            unit=prod.get("unit", ""),
            format_str=prod.get("format", "")
        )
        prod.update(metric_info)
        
        prod_struct = parse_product_structure(raw_name)

        if not prod_struct["all_tokens"]:
            prod["master_ingredient_id"] = None
            prod["similarity_score"] = 0.0
            results.append(prod)
            continue

        best_master_id = None
        best_score = 0.0

        for m in master_prepared:
            # 1. Incompatibilidad de corte explícito (ej. chuletero vs solomillo)
            if m["cut"] and prod_struct["head_cut"] and m["cut"] != prod_struct["head_cut"]:
                continue
            
            # 2. Protección de recortes: si el maestro es para 'guisar' y el producto es un corte noble
            if "guisar" in m["tokens"] and prod_struct["head_cut"]:
                continue

            # 3. El núcleo del producto maestro debe residir en el producto principal del proveedor
            def _tokens_affinity(t1, t2):
                if t1 == t2:
                    return True
                if (t1.startswith(t2) or t2.startswith(t1)) and len(min(t1, t2, key=len)) >= 4:
                    return True
                if fuzz.ratio(t1, t2) >= 80:
                    return True
                return False

            has_root_match = any(_tokens_affinity(t, m["root"]) for t in prod_struct["head_tokens"]) or \
                             any(_tokens_affinity(t, mt) for t in prod_struct["head_tokens"] for mt in m["tokens"]) or \
                             any(_tokens_affinity(t, mt) for t in prod_struct["all_tokens"] for mt in m["tokens"])

            if not has_root_match:
                continue

            # 4. Cálculo de coincidencia conceptual
            overlap_count = sum(1 for mt in m["tokens"] if any(_tokens_affinity(pt, mt) for pt in prod_struct["all_tokens"]))
            coverage = overlap_count / max(len(m["tokens"]), 1)
            str_sim = fuzz.token_set_ratio(" ".join(prod_struct["all_tokens"]), " ".join(m["tokens"])) / 100.0
            
            # Ponderación: Presencia de raíz (40%) + Cobertura de conceptos (35%) + Similitud léxica (25%)
            score = (0.4 + coverage * 0.35 + str_sim * 0.25) * 100.0

            if score > best_score:
                best_score = score
                best_master_id = m["id"]

        if best_master_id and best_score >= threshold:
            prod["master_ingredient_id"] = best_master_id
            prod["similarity_score"] = round(best_score, 2)
        else:
            prod["master_ingredient_id"] = None
            prod["similarity_score"] = round(best_score, 2)

        results.append(prod)

    matched_count = sum(1 for r in results if r["master_ingredient_id"] is not None)
    print(f"✅ Entity Resolution finalizado: {matched_count}/{len(raw_products)} emparejados.")
    return results


class OntologicalEntityResolver:
    """Motor de resolución de entidades basado en taxonomía ontológica y similitud híbrida."""

    TAXONOMY_MAP = TAXONOMY_MAP
    KNOWN_CUTS = KNOWN_CUTS
    STOPWORDS_ES = STOPWORDS_ES

    @staticmethod
    def clean_product_text(text: str) -> str:
        """Normaliza y limpia caracteres especiales y puntuación de nombres de producto."""
        return clean_product_text(text)

    @staticmethod
    def clean_tokens(text: str) -> List[str]:
        """Obtiene tokens léxicos limpios eliminando stopwords y palabras vacías."""
        return clean_tokens(text)

    @staticmethod
    def parse_product_structure(text: str) -> Dict[str, Any]:
        """Descompone el producto en corte principal/raíz y accesorios secundarios."""
        return parse_product_structure(text)

    @staticmethod
    def normalize_metric_dimension(price: float, unit: str, format_str: str = "") -> Dict[str, Any]:
        """Normaliza formatos y calcula el precio por unidad canónica (kg, L, ud)."""
        return normalize_metric_dimension(price, unit, format_str)

    @staticmethod
    def resolve_entities(
        raw_products: List[Dict[str, Any]], 
        master_catalog: List[Dict[str, Any]], 
        threshold: float = 65.0
    ) -> List[Dict[str, Any]]:
        """Mapea productos brutos heterogéneos con el catálogo maestro de ingredientes."""
        return resolve_entities(raw_products, master_catalog, threshold=threshold)