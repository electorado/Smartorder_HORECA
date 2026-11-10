from datetime import datetime
from typing import List, Dict, Any, Optional
from .database import get_database, get_gridfs


def load_raw_products(
    provider_id: str,
    products: List[Dict[str, Any]],
    supplier_name: Optional[str] = None,
    is_annex: bool = False
) -> int:
    """Carga o actualiza los productos procesados en la colección de MongoDB.
    Si is_annex es False (modo sustitución por defecto), purga los productos anteriores
    del proveedor para que no queden ítems descatalogados o que ya no se pueden pedir.
    Si is_annex es True (modo anexo), mantiene el catálogo base y solo añade/actualiza."""
    if not products:
        print("⚠️ No hay productos para cargar.")
        return 0

    db = get_database()
    collection = db["productos_brutos"]

    # En modo sustitución, purgar productos antiguos del proveedor
    if not is_annex:
        deleted = collection.delete_many({"supplier_id": provider_id})
        print(f"🗑️ Reemplazo de catálogo: eliminados {deleted.deleted_count} productos anteriores del proveedor {provider_id}.")

    # Obtener nombre del proveedor si no se indicó
    if not supplier_name:
        supp = db["proveedores"].find_one({"id": provider_id})
        supplier_name = supp.get("name", provider_id) if supp else provider_id

    count = 0
    now = datetime.utcnow()

    for prod in products:
        raw_name = prod.get("raw_name")
        clean_name = prod.get("clean_name", "")
        master_id = prod.get("master_ingredient_id")

        # Auto-crear ingrediente maestro si no existía previa coincidencia
        if not master_id and raw_name and len(raw_name) >= 2:
            import re
            clean_slug = re.sub(r'[^a-z0-9]', '_', clean_name).strip('_')
            master_id = f"ing_{clean_slug}"
            db["ingredientes_maestros"].update_one(
                {"id": master_id},
                {
                    "$setOnInsert": {
                        "id": master_id,
                        "name": raw_name.title(),
                        "category": "Catálogo Proveedores",
                        "standard_unit": prod.get("canonical_unit") or prod.get("unit", "ud"),
                        "description": f"Ingrediente registrado dinámicamente desde el catálogo de {supplier_name}"
                    }
                },
                upsert=True
            )

        doc = {
            "supplier_id": provider_id,
            "supplier_name": supplier_name,
            "supplier_product_code": prod.get("supplier_product_code"),
            "raw_name": raw_name,
            "clean_name": clean_name,
            "price": float(prod.get("price", 0.0)),
            "unit": prod.get("unit", "ud"),
            "format": prod.get("format"),
            "canonical_unit": prod.get("canonical_unit", prod.get("unit", "ud")),
            "canonical_quantity": prod.get("canonical_quantity", 1.0),
            "canonical_price": prod.get("canonical_price", float(prod.get("price", 0.0))),
            "master_ingredient_id": master_id,
            "similarity_score": prod.get("similarity_score", 100.0) if prod.get("master_ingredient_id") else 100.0,
            "stock_available": True,
            "updated_at": now
        }

        # Reemplazar o insertar si coincide proveedor y código/nombre
        filter_query = {
            "supplier_id": provider_id,
            "clean_name": doc["clean_name"]
        }
        
        collection.update_one(filter_query, {"$set": doc}, upsert=True)
        count += 1

    print(f"💾 Guardados/actualizados {count} productos para el proveedor {provider_id} ({supplier_name}) en MongoDB.")
    return count



def save_catalog_file(filename: str, file_bytes: bytes, supplier_id: str) -> str:
    """Guarda el archivo original (PDF/XLSX) en GridFS para auditoría visual."""
    fs = get_gridfs()
    file_id = fs.put(
        file_bytes,
        filename=filename,
        supplier_id=supplier_id,
        upload_date=datetime.utcnow()
    )
    print(f"📂 Archivo original '{filename}' respaldado en GridFS con ID: {file_id}")
    return str(file_id)