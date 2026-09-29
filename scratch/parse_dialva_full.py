import re
from pypdf import PdfReader
from pathlib import Path

pdf_path = Path("data/raw/DIALVA - Catalogo Mensual de Ofertas.pdf")
reader = PdfReader(pdf_path)

products = []

price_pattern = re.compile(r'([\d]+[.,]\d{1,2})\s*€\s*/?\s*(kg|ud|estuche|bandeja|botella|garrafa)?', re.IGNORECASE)
code_pattern = re.compile(r'[C|c][:.]?\s*(\d{4})', re.IGNORECASE)

for page_idx, page in enumerate(reader.pages):
    text = page.extract_text()
    if not text:
        continue

    lines = [l.strip() for l in text.split("\n") if l.strip()]
    
    current_name = []
    current_code = None
    
    for l in lines:
        # Si es un encabezado grande de catálogo, omitir
        if any(h in l.upper() for h in ["OFERTAS", "SABOR DE IT", "AUTÉNTICO", "Y SUS QUESOS", "DIALVA", "CATALOGO", "PÁGINA"]):
            continue

        # Si contiene código C: 1234
        match_code = code_pattern.search(l)
        if match_code:
            current_code = match_code.group(1)

        # Si contiene un precio (ej. 9,20 €/kg o 8,75€/kg)
        match_price = price_pattern.search(l)
        if match_price:
            try:
                price_val = float(match_price.group(1).replace(",", "."))
                unit_val = match_price.group(2).lower() if match_price.group(2) else "ud"
                
                name_str = " ".join(current_name).strip()
                # Limpiar ruidos del nombre (formatos, cantidades como "16uds X 0,2kg")
                name_clean = re.sub(r'\b\d+\s*uds?\s*x\b.*', '', name_str, flags=re.IGNORECASE).strip()
                name_clean = re.sub(r'\(?\d+\s*[X|x]\s*[\d.,]+\s*k?g\)?', '', name_clean, flags=re.IGNORECASE).strip()
                
                if len(name_clean) >= 3 and price_val > 0:
                    products.append({
                        "supplier_product_code": current_code,
                        "raw_name": name_clean,
                        "price": price_val,
                        "unit": unit_val,
                        "page": page_idx + 1
                    })
                current_name = []
                current_code = None
            except ValueError:
                pass
        else:
            # Si no es un código ni un precio, es parte del nombre del producto
            if not l.startswith("C:") and not re.search(r'^\d+uds?\s*X', l, re.IGNORECASE):
                current_name.append(l)

print(f"✅ Se extrajeron {len(products)} productos estructurados del PDF de DIALVA:")
for p in products[:20]:
    print(f" -> [{p.get('supplier_product_code')}] '{p['raw_name']}' - {p['price']} € / {p['unit']} (Pág {p['page']})")
