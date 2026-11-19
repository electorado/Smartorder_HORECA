from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Dict, Any, Union, Optional, Set
import re
from pypdf import PdfReader


class BaseCatalogExtractor(ABC):
    """Clase base común para los extractores de catálogos (Excel, PDF o visión)."""

    def __init__(self):
        self.detected_supplier: Optional[Dict[str, Any]] = None

    @abstractmethod
    def extract(self, file_path: Union[str, Path]) -> List[Dict[str, Any]]:
        """Extrae productos del fichero y devuelve una lista de diccionarios normalizados."""
        pass


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
    elif "abordo" in stem_lower or "abordo" in full_text.lower() or "servifrio" in full_text.lower() or len(re.findall(r'\bC-\d{3,5}\b', full_text)) >= 2:
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

    if supp_name == "Abordo Hostelería / Servifrío":
        if not phone:
            phone = "961548112"
        if not email:
            email = "pedidos@abordo.es"
        if not cif:
            cif = "B-96452814"

    return {"name": supp_name, "cif": cif, "phone": phone, "email": email}


