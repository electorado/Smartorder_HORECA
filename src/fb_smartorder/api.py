from fastapi import FastAPI, File, UploadFile, Form, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional
import tempfile
import os
from datetime import datetime
from bson import ObjectId

from .database import get_database, init_db, get_db_client
from .models import Order, OrderItem, SupplierSubOrder, Supplier
from .extract import extract_excel, extract_pdf
from .transform import resolve_entities
from .load import load_raw_products, save_catalog_file

app = FastAPI(
    title="F&B SmartOrder API",
    description="Backend API asíncrono para el procesamiento de catálogos y automatización de pedidos en Hostelería.",
    version="0.1.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def startup_db_check():
    """Inicializa la base de datos al arrancar la API."""
    try:
        init_db()
    except Exception as e:
        print(f"Advertencia al iniciar DB en startup: {e}")

@app.get("/")
def read_root():
    db_online = False
    try:
        client = get_db_client()
        client.server_info()
        db_online = True
    except Exception:
        db_online = False

    return {
        "app": "F&B SmartOrder API",
        "status": "online",
        "mongodb_connected": db_online,
        "version": "0.1.0"
    }

@app.get("/api/v1/suppliers")
def get_suppliers():
    """Devuelve la lista de proveedores activos."""
    try:
        db = get_database()
        suppliers = list(db["proveedores"].find({}, {"_id": 0}))
        return {"suppliers": suppliers}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/ingredients")
def get_ingredients(query: Optional[str] = None):
    """Devuelve el catálogo de ingredientes maestros enriquecido con las mejores ofertas de proveedores."""
    try:
        db = get_database()
        filter_query = {}
        if query:
            filter_query["$or"] = [
                {"name": {"$regex": query, "$options": "i"}},
                {"category": {"$regex": query, "$options": "i"}}
            ]

        masters = list(db["ingredientes_maestros"].find(filter_query, {"_id": 0}))

        # Para cada ingrediente maestro, buscar las ofertas de proveedores asociadas
        result = []
        for master in masters:
            m_id = master["id"]
            offers = list(db["productos_brutos"].find({"master_ingredient_id": m_id}, {"_id": 0}))
            
            # Ordenar ofertas por precio ascendente
            offers.sort(key=lambda x: x.get("price", 999999.0))
            best_offer = offers[0] if offers else None

            master["best_offer"] = best_offer
            master["available_offers_count"] = len(offers)
            master["all_offers"] = offers
            result.append(master)

        return {"ingredients": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/products")
def get_products(
    query: Optional[str] = Query(None, description="Filtro opcional por nombre o categoría"),
    supplier_id: Optional[str] = Query(None, description="Filtro opcional por proveedor")
):
    """Devuelve el catálogo de productos unificados con su mejor oferta para la app móvil."""
    try:
        db = get_database()
        filter_query = {}
        if query:
            filter_query["$or"] = [
                {"name": {"$regex": query, "$options": "i"}},
                {"category": {"$regex": query, "$options": "i"}}
            ]

        masters = list(db["ingredientes_maestros"].find(filter_query, {"_id": 0}))

        products = []
        for m in masters:
            offer_query = {"master_ingredient_id": m["id"]}
            if supplier_id:
                offer_query["supplier_id"] = supplier_id

            offers = list(db["productos_brutos"].find(offer_query, {"_id": 0}))
            offers.sort(key=lambda x: x.get("price", 999999.0))
            best_offer = offers[0] if offers else None

            products.append({
                "id": m["id"],
                "name": m["name"],
                "category": m.get("category", "General"),
                "standard_unit": m.get("standard_unit", "kg"),
                "best_price": best_offer.get("price") if best_offer else None,
                "best_supplier_id": best_offer.get("supplier_id") if best_offer else None,
                "best_supplier_name": best_offer.get("supplier_name") if best_offer else None,
                "available_offers": len(offers)
            })

        return {"products": products}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/v1/catalogs/upload")
async def upload_catalog(
    supplier_id: str = Form(...),
    file: UploadFile = File(...)
):
    """Sube un archivo de catálogo (PDF o Excel), lo almacena en GridFS y ejecuta el pipeline ETL."""
    try:
        db = get_database()
        supplier = db["proveedores"].find_one({"id": supplier_id})
        if not supplier:
            raise HTTPException(status_code=404, detail=f"Proveedor '{supplier_id}' no encontrado.")

        supplier_name = supplier.get("name", supplier_id)

        file_bytes = await file.read()
        filename = file.filename or "catalogo"
        ext = os.path.splitext(filename)[1].lower()

        # 1. Guardar en GridFS
        gridfs_id = save_catalog_file(filename, file_bytes, supplier_id)

        # 2. Guardar temporalmente para la extracción
        with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
            tmp.write(file_bytes)
            tmp_path = tmp.name

        try:
            # 3. Fase de Extracción
            if ext in [".xlsx", ".xls"]:
                raw_extracted = extract_excel(tmp_path)
            elif ext == ".pdf":
                raw_extracted = extract_pdf(tmp_path, save_output=False)
            else:
                raise HTTPException(status_code=400, detail="Formato no soportado. Debe ser .pdf, .xlsx o .xls.")
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

        # 4. Fase de Transformación (Entity Resolution con Ingredientes Maestros)
        master_ingredients = list(db["ingredientes_maestros"].find({}, {"_id": 0}))
        transformed_products = resolve_entities(raw_extracted, master_ingredients)

        # 5. Fase de Carga a MongoDB
        loaded_count = load_raw_products(supplier_id, transformed_products, supplier_name)

        return {
            "message": f"Catálogo procesado y cargado con éxito.",
            "supplier_id": supplier_id,
            "supplier_name": supplier_name,
            "gridfs_file_id": gridfs_id,
            "products_extracted": len(raw_extracted),
            "products_loaded": loaded_count
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error procesando catálogo: {str(e)}")

@app.post("/api/v1/orders")
def create_order(order_data: Order):
    """Crea y consolida un nuevo pedido en el sistema, dividiéndolo automáticamente por proveedores."""
    try:
        db = get_database()

        # Agrupar ítems por proveedor
        grouped = {}
        for item in order_data.items:
            s_id = item.supplier_id
            if s_id not in grouped:
                supp = db["proveedores"].find_one({"id": s_id})
                s_name = item.supplier_name or (supp.get("name") if supp else s_id)
                s_email = supp.get("email", "pedidos@proveedor.com") if supp else "pedidos@proveedor.com"
                grouped[s_id] = {
                    "supplier_id": s_id,
                    "supplier_name": s_name,
                    "supplier_email": s_email,
                    "items": [],
                    "subtotal": 0.0
                }
            grouped[s_id]["items"].append(item)
            grouped[s_id]["subtotal"] += item.total_price

        suborders = [SupplierSubOrder(**v) for v in grouped.values()]
        order_data.supplier_suborders = suborders
        order_data.total_amount = sum(so.subtotal for so in suborders)
        order_data.created_at = datetime.utcnow()
        order_data.status = "pending"

        order_dict = order_data.dict()
        res = db["pedidos"].insert_one(order_dict)
        order_id = str(res.inserted_id)
        order_dict["id"] = order_id
        order_dict["_id"] = order_id

        return {
            "message": "Pedido consolidado creado con éxito.",
            "order_id": order_id,
            "order": order_dict
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creando pedido: {str(e)}")

@app.get("/api/v1/orders")
def list_orders():
    """Obtiene el historial de pedidos."""
    try:
        db = get_database()
        orders = list(db["pedidos"].find().sort("created_at", -1))
        for o in orders:
            o["id"] = str(o["_id"])
            del o["_id"]
        return {"orders": orders}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/v1/orders/{order_id}/send")
def send_order(order_id: str):
    """Simula/dispara el envío de las órdenes de pedido por correo a cada proveedor."""
    try:
        db = get_database()
        try:
            query = {"_id": ObjectId(order_id)}
        except Exception:
            query = {"id": order_id}

        order = db["pedidos"].find_one(query)
        if not order:
            raise HTTPException(status_code=404, detail="Pedido no encontrado.")

        # Simular envío a cada sub-orden de proveedor
        sent_summaries = []
        for sub in order.get("supplier_suborders", []):
            sent_summaries.append({
                "supplier_name": sub.get("supplier_name"),
                "supplier_email": sub.get("supplier_email"),
                "items_count": len(sub.get("items", [])),
                "subtotal": sub.get("subtotal"),
                "sent_status": "SUCCESS (Email simulado a " + sub.get("supplier_email", "") + ")"
            })

        db["pedidos"].update_one(query, {"$set": {"status": "sent", "sent_at": datetime.utcnow()}})

        return {
            "message": f"Pedido #{order_id} enviado a los proveedores.",
            "status": "sent",
            "sent_details": sent_summaries
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/v1/ocr/fridge-list")
async def scan_fridge_photo(file: UploadFile = File(...)):
    """Recibe una foto de la lista de la nevera/pizarra, extrae los ítems y los mapea con el catálogo maestro."""
    try:
        from .ocr import process_fridge_photo
        file_bytes = await file.read()
        
        # 1. Extraer ítems de la foto
        raw_items = process_fridge_photo(file_bytes)
        
        # 2. Mapear con ingredientes maestros
        db = get_database()
        master_ingredients = list(db["ingredientes_maestros"].find({}, {"_id": 0}))
        mapped_items = resolve_entities(raw_items, master_ingredients)
        
        # 3. Asignar mejor oferta disponible para cada ingrediente
        suggested_order_items = []
        for item in mapped_items:
            m_id = item.get("master_ingredient_id")
            best_offer = None
            if m_id:
                offers = list(db["productos_brutos"].find({"master_ingredient_id": m_id}, {"_id": 0}))
                offers.sort(key=lambda x: x.get("price", 99999.0))
                best_offer = offers[0] if offers else None
            
            suggested_order_items.append({
                "raw_text": item.get("raw_name"),
                "clean_name": item.get("clean_name"),
                "quantity": item.get("quantity", 1.0),
                "unit": item.get("unit", "kg"),
                "master_ingredient_id": m_id,
                "similarity_score": item.get("similarity_score", 0.0),
                "best_offer": best_offer
            })

        return {
            "message": f"Se procesó la foto de la nevera exitosamente.",
            "items_found_count": len(suggested_order_items),
            "items": suggested_order_items
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al procesar foto de la nevera: {str(e)}")

