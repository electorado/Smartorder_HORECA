from pathlib import Path
from typing import List, Dict, Any, Union
import re
import pandas as pd
from .base import BaseCatalogExtractor


class GenericExcelExtractor(BaseCatalogExtractor):
    """Extractor para hojas de cálculo Excel (.xlsx, .xls).
    
    Identifica las columnas de nombre, precio, unidad y código según las cabeceras.
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

