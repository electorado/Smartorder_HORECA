import sys
import os
from pathlib import Path

# Aseguramos que Python encuentre el paquete local si ejecutamos desde la raíz
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from fb_smartorder.database import get_db_client, get_database, init_db, get_gridfs
from fb_smartorder.extract import extract_excel
from fb_smartorder.transform import clean_product_text, resolve_entities
from fb_smartorder.load import load_raw_products, save_catalog_file

def run_pipeline():
    print("==================================================")
    print("🚀 INICIANDO PIPELINE DE DATOS F&B SMARTORDER")
    print("==================================================")
    
    # 0. Verificar e inicializar la infraestructura de MongoDB
    db_available = False
    try:
        client = get_db_client()
        client.server_info()
        print("✅ Infraestructura de MongoDB: ONLINE")
        init_db()
        db_available = True
    except Exception as e:
        print("⚠️ Advertencia: La base de datos MongoDB no responde. ¿Está levantado el contenedor Docker?")
        print(f"Detalles: {e}")

    # 1. Definir lista de catálogos a procesar en data/raw
    catalogs_to_process = [
        {"file": Path("data/raw/catalogo_frutas_paco.xlsx"), "provider_id": "prov_paco_01", "type": "excel"},
        {"file": Path("data/raw/DIALVA - Catalogo Mensual de Ofertas.pdf"), "provider_id": "prov_dialva_04", "type": "pdf"}
    ]

    master_ingredients = []
    if db_available:
        db = get_database()
        master_ingredients = list(db["ingredientes_maestros"].find({}, {"_id": 0}))
    print(f"🧠 Catálogo Maestro cargado: {len(master_ingredients)} ingredientes.")

    for item in catalogs_to_process:
        archivo_path = item["file"]
        provider_id = item["provider_id"]
        
        if not archivo_path.exists():
            print(f"⚠️ Archivo no encontrado: {archivo_path}")
            continue

        print(f"\n--------------------------------------------------")
        print(f"📄 Procesando Catálogo: {archivo_path.name} (Proveedor: {provider_id})")
        
        if item["type"] == "excel":
            datos_brutos = extract_excel(archivo_path)
        else:
            from fb_smartorder.extract import extract_pdf
            datos_brutos = extract_pdf(archivo_path)

        print(f"📥 Extraídos {len(datos_brutos)} ítems del documento.")

        # 2. Respaldo visual en GridFS
        if db_available:
            with open(archivo_path, "rb") as f:
                file_bytes = f.read()
            gridfs_id = save_catalog_file(archivo_path.name, file_bytes, provider_id)

        # 3. Transformación y Mapeo
        productos_mapeados = resolve_entities(datos_brutos, master_ingredients)

        # 4. Carga en MongoDB
        if db_available:
            count = load_raw_products(provider_id=provider_id, products=productos_mapeados)
            print(f"💾 Carga finalizada: {count} productos actualizados en 'productos_brutos' para {provider_id}.")

    print("\n==================================================")
    print("🎉 PIPELINE FINALIZADO CON ÉXITO")
    print("==================================================")


if __name__ == "__main__":
    run_pipeline()