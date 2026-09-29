from pypdf import PdfReader
from pathlib import Path

pdf_path = Path("data/raw/DIALVA - Catalogo Mensual de Ofertas.pdf")
reader = PdfReader(pdf_path)

print("=== LINEAS DE TEXTO EN DIALVA PDF ===")
for page_num in range(1, 6):
    text = reader.pages[page_num].extract_text()
    lines = text.split("\n")
    print(f"\n--- PAGINA {page_num+1} ({len(lines)} líneas) ---")
    for l in lines[:20]:
        if l.strip():
            print("  L:", l.strip())
