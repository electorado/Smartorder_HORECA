import json
import re
from pathlib import Path
from typing import List, Dict, Any, Union
import pandas as pd
from pypdf import PdfReader


def extract_excel(file_path: Union[str, Path]) -> List[Dict[str, Any]]:
    """Extrae datos estructurados desde un archivo Excel (xlsx/xls).
    
    Busca inteligentemente las columnas de producto, precio, unidad y código.
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Archivo Excel no encontrado: {file_path}")

    print(f"📄 Extrayendo datos desde el Excel: {file_path}")
    
    # Leer el excel en un dataframe
    df = pd.read_excel(path, sheet_name=0)
    
    # Limpiar columnas vacías
    df = df.dropna(how="all")
    
    products: List[Dict[str, Any]] = []
    
    # Intentar identificar nombres de columnas automáticamente
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

    # Si no se detectaron encabezados explícitos, asumir orden habitual (col 0: código/nombre, col 1: nombre/precio, col 2: precio)
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
            # Buscar número en las demás celdas
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

    print(f"✅ Se extrajeron {len(products)} productos del Excel.")
    return products


def extract_pdf(
    file_path: Union[str, Path], save_output: bool = False
) -> List[Dict[str, Any]]:
    """Extrae texto y parsea líneas de productos/precios desde un PDF.
    
    Args:
        file_path: Ruta del archivo PDF.
        save_output: Booleano para guardar respaldo crudo en JSON.

    Returns:
        Lista de diccionarios con la información extraída de los productos.
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Archivo no encontrado: {file_path}")

    print(f"📑 Extrayendo texto desde el PDF: {file_path}")
    reader = PdfReader(path)
    products: List[Dict[str, Any]] = []

    price_pattern = re.compile(r'([\d]+[.,\'’]\d{1,2})\s*€\s*/?\s*([a-záéíóú]+)?', re.IGNORECASE)
    code_pattern = re.compile(r'[C|c][:.]?\s*(\d{4})', re.IGNORECASE)
    single_line_pattern = re.compile(r'(.+?)\s+([\d]+[.,\'’]\d{1,2})\s*€?\s*(?:/\s*(\w+))?', re.IGNORECASE)

    for index, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        raw_lines = [l.strip() for l in text.split("\n") if l.strip()]

        # Preprocesar líneas: separar texto concatenado por OCR y precios que preceden al siguiente producto
        lines = []
        for l in raw_lines:
            # Separar palabras pegadas (ej. raciónTarta -> ración Tarta)
            l_spaced = re.sub(r'([a-zñáéíóú])([A-ZÁÉÍÓÚ])', r'\1 \2', l)
            # Si una línea empieza por precio/ración y le sigue texto (ej. "1,98€/ración Tarta de Lotus")
            m_lead = re.match(r'^([\d]+[.,\'’]\d{1,2}\s*€(?:\s*/\s*[a-záéíóú]+)?)\s+(.+)', l_spaced, re.IGNORECASE)
            if m_lead:
                lines.append(m_lead.group(1))
                lines.append(m_lead.group(2))
            else:
                lines.append(l_spaced)

        current_name_acc = []
        current_code = None

        for line in lines:
            # Omitir títulos / ruidos genéricos
            if any(h in line.upper() for h in ["OFERTAS", "SABOR DE IT", "AUTÉNTICO", "Y SUS QUESOS", "DIALVA", "PÁGINA"]):
                continue

            match_code = code_pattern.search(line)
            if match_code:
                current_code = match_code.group(1)

            match_price = price_pattern.search(line)
            if match_price:
                try:
                    price_val = float(match_price.group(1).replace(",", ".").replace("'", ".").replace("’", "."))
                    unit_val = match_price.group(2).lower() if match_price.group(2) else "ud"

                    # Si acumulamos líneas arriba, usar como nombre
                    if current_name_acc:
                        name_str = " ".join(current_name_acc).strip()
                    else:
                        # Si no hay acumulado, probar regex monolínea
                        m_single = single_line_pattern.search(line)
                        name_str = m_single.group(1).strip() if m_single else ""

                    # Limpiar ruidos de formato (ej. 16uds X 0,2kg) y precios residuales
                    name_clean = re.sub(r'\b\d+\s*uds?\s*x\b.*', '', name_str, flags=re.IGNORECASE).strip()
                    name_clean = re.sub(r'\(?\d+\s*[X|x]\s*[\d.,]+\s*k?g\)?', '', name_clean, flags=re.IGNORECASE).strip()
                    name_clean = re.sub(r'\b\d+[.,\']\d{1,2}\s*€(?:/\w+)?\b', '', name_clean).strip()

                    # Descartar si el nombre resultante no tiene letras o es solo residuo numérico
                    has_letters = bool(re.search(r'[a-záéíóúñ]{3,}', name_clean, re.IGNORECASE))

                    if has_letters and price_val > 0:
                        products.append({
                            "page": index,
                            "supplier_product_code": current_code,
                            "raw_name": name_clean,
                            "price": price_val,
                            "unit": unit_val
                        })

                    current_name_acc = []
                    current_code = None
                except ValueError:
                    pass
            else:
                # Si la línea no es precio ni código, acumular como parte del nombre del producto
                if not line.startswith("C:") and not re.search(r'^\d+uds?\s*X', line, re.IGNORECASE):
                    current_name_acc.append(line)

    if save_output:
        output_dir = Path("data/processed")
        output_dir.mkdir(parents=True, exist_ok=True)
        output_file = output_dir / f"{path.stem}_extracted.json"
        output_file.write_text(json.dumps(products, ensure_ascii=False, indent=2))
        print(f"💾 Datos extraídos guardados en: {output_file}")

    print(f"✅ Se extrajeron {len(products)} productos estructurados del PDF.")
    return products



def extract_image_list(image_bytes: bytes) -> List[Dict[str, Any]]:
    """Extrae productos y cantidades desde la imagen de una lista manuscrita en la nunca o pizarra."""
    from .ocr import process_fridge_photo
    return process_fridge_photo(image_bytes)


class CatalogExtractor:
    """Clase de servicio del pipeline ETL encargada de la ingesta y extracción multimodal."""

    @staticmethod
    def extract_excel(file_path: Union[str, Path]) -> List[Dict[str, Any]]:
        """Extrae productos y precios desde hojas de cálculo Excel."""
        return extract_excel(file_path)

    @staticmethod
    def extract_pdf(file_path: Union[str, Path], save_output: bool = True) -> List[Dict[str, Any]]:
        """Extrae productos y precios desde catálogos y tarifas en formato PDF."""
        return extract_pdf(file_path, save_output=save_output)

    @staticmethod
    def extract_ocr(image_bytes: bytes) -> List[Dict[str, Any]]:
        """Extrae líneas manuscritas mediante reconocimiento óptico de caracteres (OCR)."""
        return extract_image_list(image_bytes)