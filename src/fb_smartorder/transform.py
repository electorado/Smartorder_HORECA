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
    "solomillo", "chuletero", "chuleton", "chuleta", "lomo",
    "entrecot", "falda", "aguja", "carrillada", "churrasco",
    "secreto", "lagarto", "codillo", "cabecero", "picana",
    "pechuga", "filete", "tartar", "hamburguesa"
}


def clean_tokens(text: str) -> list[str]:
    """Extrae tokens normalizados semántica y fonéticamente."""
    text_norm = unicodedata.normalize("NFD", text)
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
    head_cut = next((t for t in head_tokens if t in KNOWN_CUTS), None)
    return {
        "head_tokens": set(head_tokens),
        "all_tokens": set(all_tokens),
        "head_cut": head_cut
    }


def clean_product_text(text: str) -> str:
    """Limpia ruido del texto (acentos, mayúsculas, códigos, precios y palabras promocionales)."""
    if not text:
        return ""
    
    text_normalized = unicodedata.normalize('NFD', text)
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


def resolve_entities(
    raw_products: List[Dict[str, Any]],
    master_ingredients: List[Dict[str, Any]],
    threshold: float = 65.0
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
            if m["root"] not in prod_struct["head_tokens"]:
                continue

            # 4. Cálculo de coincidencia conceptual
            overlap = prod_struct["all_tokens"] & m["tokens"]
            coverage = len(overlap) / len(m["tokens"])
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
    def resolve_entities(
        raw_products: List[Dict[str, Any]], 
        master_catalog: List[Dict[str, Any]], 
        threshold: float = 65.0
    ) -> List[Dict[str, Any]]:
        """Mapea productos brutos heterogéneos con el catálogo maestro de ingredientes."""
        return resolve_entities(raw_products, master_catalog, threshold=threshold)