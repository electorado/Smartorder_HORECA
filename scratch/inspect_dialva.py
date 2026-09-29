from fb_smartorder.extract import extract_pdf
from pypdf import PdfReader
from pathlib import Path

pdf_path = Path("data/raw/DIALVA - Catalogo Mensual de Ofertas.pdf")

print("=== INSPECCIONANDO PDF DE DIALVA ===")
reader = PdfReader(pdf_path)
print(f"Total de páginas en PDF: {len(reader.pages)}")

# Extraer primeras 3 páginas de texto bruto
for i in range(min(5, len(reader.pages))):
    text = reader.pages[i].extract_text()
    print(f"\n--- PÁGINA {i+1} ---")
    print(text[:800] if text else "[Página vacía o imagen sin capa de texto]")

# Probar extract_pdf
extracted = extract_pdf(pdf_path)
print(f"\n✅ Total de ítems extraídos con extract_pdf: {len(extracted)}")
for item in extracted[:15]:
    print(" ->", item)
