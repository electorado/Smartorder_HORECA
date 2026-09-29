import pandas as pd
from pathlib import Path

# Crear directorio data/raw si no existe
raw_dir = Path("data/raw")
raw_dir.mkdir(parents=True, exist_ok=True)

data = [
    {"Codigo": "FP-001", "Producto": "TOMATE RAMA 1ª CALIDAD !!", "Precio": "1,85 €", "Unidad": "kg"},
    {"Codigo": "FP-002", "Producto": "Cebolla Recogida Grano (Saco 10kg)", "Precio": "0,95 €", "Unidad": "kg"},
    {"Codigo": "FP-003", "Producto": "Pechuga de Pollo Fresca Limpia", "Precio": "6,20 €", "Unidad": "kg"},
    {"Codigo": "FP-004", "Producto": "Aceite Oliva Virgen Extra Garrafa 5L", "Precio": "31,50 €", "Unidad": "ud"},
    {"Codigo": "FP-005", "Producto": "Leche Entera Brik 1L (OFERTA SUPER)", "Precio": "0,89 €", "Unidad": "L"},
    {"Codigo": "FP-006", "Producto": "Lubina Fresca de Estero (400-600g)", "Precio": "9,80 €", "Unidad": "kg"}
]

df = pd.DataFrame(data)
file_path = raw_dir / "catalogo_frutas_paco.xlsx"
df.to_excel(file_path, index=False)
print(f"Excel de muestra creado exitosamente en {file_path}")
