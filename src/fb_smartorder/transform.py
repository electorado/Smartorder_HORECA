import re
import unicodedata
from typing import List, Dict, Any
from rapidfuzz import process, fuzz


def clean_product_text(text: str) -> str:
    """Limpia ruido del texto (acentos, mayúsculas, caracteres raros, palabras promocionales)."""
    if not text:
        return ""
    
    # Convertir NFD y eliminar diacríticos (acentos)
    text_normalized = unicodedata.normalize('NFD', text)
    text_without_accents = ''.join(c for c in text_normalized if unicodedata.category(c) != 'Mn')
    
    # Convertir a minúsculas
    text_clean = text_without_accents.lower().strip()
    
    # Eliminar palabras con ruido común en hostelería (1ª calidad, oferta, especial, super, etc.)
    noise_patterns = [
        r'\b1[aa]\s+calidad\b',
        r'\boferta\b',
        r'\bpromocion\b',
        r'\bsuper\b',
        r'\bprecio\s+especial\b',
        r'[*!¡?¿#%]'
    ]
    for pattern in noise_patterns:
        text_clean = re.sub(pattern, '', text_clean)
        
    # Reemplazar múltiples espacios por uno solo
    text_clean = re.sub(r'\s+', ' ', text_clean).strip()
    return text_clean


def resolve_entities(
    raw_products: List[Dict[str, Any]],
    master_ingredients: List[Dict[str, Any]],
    threshold: float = 60.0
) -> List[Dict[str, Any]]:
    """Algoritmo de Entity Resolution para emparejar productos del proveedor con el catálogo maestro.
    
    Args:
        raw_products: Lista de diccionarios de productos brutos (con 'raw_name').
        master_ingredients: Lista de ingredientes maestros (con 'id' y 'name').
        threshold: Puntuación mínima de similitud de 0 a 100 para considerar coincidencia.
    
    Returns:
        Lista de productos brutos enriquecidos con 'clean_name', 'master_ingredient_id' y 'similarity_score'.
    """
    print(f"🧠 Ejecutando Entity Resolution para {len(raw_products)} productos...")
    
    if not master_ingredients:
        # Devolver productos limpios sin mapear si no hay catálogo maestro
        for p in raw_products:
            p["clean_name"] = clean_product_text(p.get("raw_name", ""))
            p["master_ingredient_id"] = None
            p["similarity_score"] = 0.0
        return raw_products

    # Preparamos nombres limpios de la lista maestra
    master_names_map = {}
    master_names_list = []
    for ing in master_ingredients:
        c_name = clean_product_text(ing["name"])
        master_names_map[c_name] = ing["id"]
        master_names_list.append(c_name)

    results = []
    for prod in raw_products:
        raw_name = prod.get("raw_name", "")
        c_name = clean_product_text(raw_name)
        prod["clean_name"] = c_name

        if not c_name or not master_names_list:
            prod["master_ingredient_id"] = None
            prod["similarity_score"] = 0.0
            results.append(prod)
            continue

        # Usar rapidfuzz con WRatio para maxima tolerancia a erratas tipográficas y OCR
        match = process.extractOne(
            c_name,
            master_names_list,
            scorer=fuzz.WRatio
        )

        if match and match[1] >= threshold:
            best_matched_cname = match[0]
            score = float(match[1])
            master_id = master_names_map.get(best_matched_cname)
            prod["master_ingredient_id"] = master_id
            prod["similarity_score"] = round(score, 2)
        else:
            prod["master_ingredient_id"] = None
            prod["similarity_score"] = round(float(match[1]), 2) if match else 0.0

        results.append(prod)


    matched_count = sum(1 for r in results if r["master_ingredient_id"] is not None)
    print(f"✅ Entity Resolution finalizado: {matched_count}/{len(raw_products)} emparejados.")
    return results