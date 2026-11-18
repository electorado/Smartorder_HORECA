from fastapi import FastAPI, File, UploadFile, Form, HTTPException, Query, Header
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional
from contextlib import asynccontextmanager
import tempfile
import os
import re
import urllib.parse
from datetime import datetime
from bson import ObjectId

from .database import get_database, init_db, get_db_client, hash_password
from .models import (
    Order, OrderItem, SupplierSubOrder, Supplier,
    UserRegister, UserLogin, UserProfile, UserUpdate,
    ProductOverrideUpdate
)
from .extract import extract_excel, extract_pdf, extract_catalog, extract_catalog_with_supplier
from .transform import resolve_entities
from .load import load_raw_products, save_catalog_file

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gestión moderna del ciclo de vida de FastAPI (sustituye al deprecado on_event)."""
    try:
        init_db()
    except Exception as e:
        print(f"Advertencia al iniciar DB en startup: {e}")
    yield

app = FastAPI(
    title="F&B SmartOrder API",
    description="Backend API asíncrono para el procesamiento de catálogos y automatización de pedidos en Hostelería.",
    version="0.1.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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

# ==============================================================================
# Rutas de Autenticación y Perfil de Usuario
# ==============================================================================

@app.post("/api/v1/auth/register")
def register_user(user_data: UserRegister):
    """Registra un nuevo usuario/establecimiento en el sistema."""
    try:
        db = get_database()
        email_clean = user_data.email.lower().strip()
        
        existing = db["usuarios"].find_one({"email": email_clean})
        if existing:
            raise HTTPException(status_code=400, detail="El correo electrónico ya está registrado.")
        
        new_user = {
            "name": user_data.name.strip(),
            "email": email_clean,
            "password_hash": hash_password(user_data.password),
            "restaurant_name": user_data.restaurant_name.strip(),
            "created_at": datetime.utcnow()
        }
        res = db["usuarios"].insert_one(new_user)
        
        return {
            "message": "Usuario registrado exitosamente.",
            "user": {
                "id": str(res.inserted_id),
                "name": new_user["name"],
                "email": new_user["email"],
                "restaurant_name": new_user["restaurant_name"]
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/v1/auth/login")
def login_user(creds: UserLogin):
    """Autentica un usuario mediante email y contraseña."""
    try:
        db = get_database()
        email_clean = creds.email.lower().strip()
        pwd_hash = hash_password(creds.password)
        
        user = db["usuarios"].find_one({"email": email_clean})
        if not user or user.get("password_hash") != pwd_hash:
            raise HTTPException(status_code=401, detail="Credenciales incorrectas. Verifica el email y contraseña.")
        
        return {
            "message": "Inicio de sesión correcto.",
            "user": {
                "id": str(user.get("_id", "")),
                "name": user.get("name", "Chef"),
                "email": user.get("email", email_clean),
                "restaurant_name": user.get("restaurant_name", "Mi Restaurante")
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/auth/profile")
def get_user_profile(email: str = Query(...)):
    """Obtiene los datos del perfil activo."""
    try:
        db = get_database()
        user = db["usuarios"].find_one({"email": email.lower().strip()})
        if not user:
            raise HTTPException(status_code=404, detail="Usuario no encontrado.")
        
        return {
            "user": {
                "id": str(user.get("_id", "")),
                "name": user.get("name", ""),
                "email": user.get("email", ""),
                "restaurant_name": user.get("restaurant_name", "")
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/api/v1/auth/profile")
def update_user_profile(update_data: UserUpdate, email: str = Query(...)):
    """Actualiza los datos del perfil del cocinero o restaurante."""
    try:
        db = get_database()
        email_clean = email.lower().strip()
        
        updates = {}
        if update_data.name:
            updates["name"] = update_data.name.strip()
        if update_data.restaurant_name:
            updates["restaurant_name"] = update_data.restaurant_name.strip()
        if update_data.password and len(update_data.password) >= 4:
            updates["password_hash"] = hash_password(update_data.password)
            
        if not updates:
            return {"message": "Sin cambios que aplicar."}
            
        res = db["usuarios"].update_one({"email": email_clean}, {"$set": updates})
        if res.matched_count == 0:
            raise HTTPException(status_code=404, detail="Usuario no encontrado.")
            
        updated_user = db["usuarios"].find_one({"email": email_clean})
        return {
            "message": "Perfil actualizado correctamente.",
            "user": {
                "id": str(updated_user.get("_id", "")),
                "name": updated_user.get("name", ""),
                "email": updated_user.get("email", ""),
                "restaurant_name": updated_user.get("restaurant_name", "")
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/suppliers")
def get_suppliers(
    user_email: Optional[str] = Query(None),
    x_user_email: Optional[str] = Header(None, alias="X-User-Email")
):
    """Devuelve la lista de proveedores del cocinero."""
    try:
        db = get_database()
        u_email = (x_user_email or user_email or "").lower().strip()
        filter_query = {}
        if u_email:
            filter_query["user_email"] = u_email
        suppliers = list(db["proveedores"].find(filter_query, {"_id": 0}))
        return {"suppliers": suppliers}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

def resolve_user_email(*candidates, fallback: str = "pablo@horeca.com") -> str:
    """Extrae el email de usuario válido ignorando instancias de Query o Header de FastAPI."""
    for c in candidates:
        if isinstance(c, str) and c.strip():
            return c.strip().lower()
    return fallback.strip().lower()


def sanitize_whatsapp_phone(raw_phone: Optional[str]) -> str:
    """Extrae un único número de teléfono limpio apto para la URL de WhatsApp (preferente móvil español 6xx/7xx o formato internacional)."""
    if not raw_phone:
        return ""
    parts = re.split(r'[/,;\n|y\-]', str(raw_phone))
    cands = []
    for p in parts:
        digits = re.sub(r'[^\d]', '', p)
        if digits.startswith("0034"):
            digits = digits[4:]
        elif digits.startswith("34") and len(digits) == 11:
            digits = digits[2:]
        if len(digits) == 9:
            cands.append(digits)
        elif 9 < len(digits) <= 15:
            cands.append(digits)
    if not cands:
        m = re.findall(r'[6789]\d{8}', str(raw_phone))
        if m:
            cands = m
    if not cands:
        clean_all = re.sub(r'[^\d]', '', str(raw_phone))
        if len(clean_all) == 9:
            return f"34{clean_all}"
        return clean_all

    mobile = next((c for c in cands if c.startswith(('6', '7'))), None)
    selected = mobile if mobile else cands[0]
    if len(selected) == 9:
        return f"34{selected}"
    return selected


@app.post("/api/v1/suppliers")
def create_or_update_supplier(
    supplier: Supplier,
    user_email: Optional[str] = Query(None),
    x_user_email: Optional[str] = Header(None, alias="X-User-Email")
):
    """Crea o actualiza un proveedor asociado al cocinero."""
    try:
        db = get_database()
        u_email = resolve_user_email(x_user_email, user_email)
        supp_dict = supplier.model_dump()
        supp_dict["user_email"] = u_email
        
        # Si no tiene ID o es provisional, generar uno seguro
        if not supp_dict.get("id"):
            clean_id = re.sub(r'[^a-zA-Z0-9]', '_', supp_dict["name"].lower().strip())
            supp_dict["id"] = f"prov_{clean_id}"

        db["proveedores"].update_one(
            {"id": supp_dict["id"], "user_email": u_email},
            {"$set": supp_dict},
            upsert=True
        )

        # Sincronizar el nombre en productos del catálogo
        if supp_dict.get("name"):
            db["productos_brutos"].update_many(
                {"supplier_id": supp_dict["id"], "user_email": u_email},
                {"$set": {"supplier_name": supp_dict["name"]}}
            )

        return {
            "message": f"Proveedor '{supp_dict['name']}' guardado correctamente.",
            "supplier": supp_dict
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error guardando proveedor: {str(e)}")

@app.put("/api/v1/suppliers/{supplier_id}")
def update_supplier(
    supplier_id: str,
    supplier: Supplier,
    user_email: Optional[str] = Query(None),
    x_user_email: Optional[str] = Header(None, alias="X-User-Email")
):
    """Actualiza los datos de contacto de un proveedor existente y sincroniza su catálogo."""
    try:
        db = get_database()
        u_email = (x_user_email or user_email or "pablo@horeca.com").lower().strip()
        supp_dict = supplier.model_dump()
        supp_dict["id"] = supplier_id
        supp_dict["user_email"] = u_email
        db["proveedores"].update_one(
            {"id": supplier_id, "user_email": u_email},
            {"$set": supp_dict},
            upsert=True
        )
        if supp_dict.get("name"):
            db["productos_brutos"].update_many(
                {"supplier_id": supplier_id, "user_email": u_email},
                {"$set": {"supplier_name": supp_dict["name"]}}
            )
        return {
            "message": f"Proveedor '{supp_dict['name']}' actualizado correctamente.",
            "supplier": supp_dict
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error actualizando proveedor: {str(e)}")

@app.delete("/api/v1/suppliers/{supplier_id}")
def delete_supplier(
    supplier_id: str,
    user_email: Optional[str] = Query(None),
    x_user_email: Optional[str] = Header(None, alias="X-User-Email")
):
    """Elimina un proveedor y limpia automáticamente sus productos asociados del catálogo del cocinero."""
    try:
        db = get_database()
        u_email = (x_user_email or user_email or "").lower().strip()
        del_filter = {"id": supplier_id}
        if u_email:
            del_filter["user_email"] = u_email
        res = db["proveedores"].delete_one(del_filter)
        if u_email:
            prod_res = db["productos_brutos"].delete_many({"supplier_id": supplier_id, "user_email": u_email})
        else:
            prod_res = db["productos_brutos"].delete_many({"supplier_id": supplier_id})
        return {
            "message": f"Proveedor '{supplier_id}' eliminado correctamente. Se han retirado {prod_res.deleted_count} productos del catálogo.",
            "deleted_supplier": res.deleted_count > 0,
            "deleted_products": prod_res.deleted_count
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error eliminando proveedor: {str(e)}")

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
            
            # Ordenar ofertas por precio canónico comparable (ej. €/kg, €/L)
            offers.sort(key=lambda x: x.get("canonical_price") or x.get("price", 999999.0))
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
    supplier_id: Optional[str] = Query(None, description="Filtro opcional por proveedor"),
    filter_type: Optional[str] = Query(None, description="Filtro opcional: 'favorites', 'all', 'hidden'"),
    user_email: Optional[str] = Query(None),
    x_user_email: Optional[str] = Header(None, alias="X-User-Email")
):
    """Devuelve el catálogo de productos y ofertas del cocinero con soporte para favoritos, ocultos y personalizaciones."""
    try:
        db = get_database()
        u_email = (x_user_email if isinstance(x_user_email, str) else user_email if isinstance(user_email, str) else "").lower().strip()
        filter_query = {}
        if u_email:
            filter_query["user_email"] = u_email

        if supplier_id and isinstance(supplier_id, str):
            filter_query["supplier_id"] = supplier_id

        if query and isinstance(query, str):
            filter_query["$or"] = [
                {"raw_name": {"$regex": query, "$options": "i"}},
                {"clean_name": {"$regex": query, "$options": "i"}},
                {"supplier_name": {"$regex": query, "$options": "i"}}
            ]

        raw_items = list(db["productos_brutos"].find(filter_query))

        # Cargar personalizaciones y favoritos del usuario
        overrides_by_code = {}
        overrides_by_id = {}
        if u_email:
            for ov in db["product_overrides"].find({"user_email": u_email}):
                if ov.get("supplier_product_code"):
                    overrides_by_code[str(ov["supplier_product_code"])] = ov
                if ov.get("product_id"):
                    overrides_by_id[str(ov["product_id"])] = ov

        masters = {m["id"]: m for m in db["ingredientes_maestros"].find({}, {"_id": 0})}

        products = []
        for p in raw_items:
            p_id = str(p["_id"])
            p_code = str(p.get("supplier_product_code")) if p.get("supplier_product_code") else None
            m_id = p.get("master_ingredient_id")
            master = masters.get(m_id) if m_id else None

            # Aplicar override si existe
            ov = (overrides_by_code.get(p_code) if p_code else None) or overrides_by_id.get(p_id) or {}

            is_fav = bool(ov.get("is_favorite", p.get("is_favorite", False)))
            is_hid = bool(ov.get("is_hidden", p.get("is_hidden", False)))
            c_name = ov.get("custom_name") or p.get("custom_name")
            c_price = ov.get("custom_price") if ov.get("custom_price") is not None else p.get("custom_price")
            c_unit = ov.get("custom_unit") or p.get("custom_unit")

            # Filtrado por tipo (favorites, all, hidden)
            f_type = (filter_type or "").lower().strip()
            if f_type == "favorites" and (not is_fav or is_hid):
                continue
            elif f_type == "hidden" and not is_hid:
                continue
            elif f_type not in ["favorites", "hidden"] and is_hid:
                # En la vista normal 'all' o sin filtro, no mostrar los ocultos
                continue

            cat = p.get("category") or (master.get("category") if master else None) or "General"
            name = c_name or p.get("raw_name") or p.get("clean_name") or "Producto"
            unit = c_unit or p.get("unit") or p.get("canonical_unit") or "ud"
            price = c_price if c_price is not None else (p.get("price") if p.get("price") is not None else p.get("canonical_price"))

            products.append({
                "id": p_id,
                "supplier_product_code": p_code,
                "name": name,
                "original_name": p.get("raw_name") or p.get("clean_name"),
                "category": cat,
                "standard_unit": unit,
                "best_price": price,
                "best_supplier_id": p.get("supplier_id"),
                "best_supplier_name": p.get("supplier_name"),
                "available_offers": 1,
                "is_favorite": is_fav,
                "is_hidden": is_hid,
                "custom_name": c_name,
                "custom_price": c_price,
                "custom_unit": c_unit
            })

        return {"products": products}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.patch("/api/v1/products/{product_id}/override")
def update_product_override(
    product_id: str,
    override_data: ProductOverrideUpdate,
    user_email: Optional[str] = Query(None),
    x_user_email: Optional[str] = Header(None, alias="X-User-Email")
):
    """Permite al cocinero personalizar el nombre, precio, unidad, estado favorito u oculto de un producto."""
    try:
        db = get_database()
        u_email = (x_user_email or user_email or "").lower().strip()
        if not u_email:
            raise HTTPException(status_code=401, detail="Usuario no autenticado")

        try:
            prod = db["productos_brutos"].find_one({"_id": ObjectId(product_id)})
        except Exception:
            prod = db["productos_brutos"].find_one({"id": product_id})

        if not prod:
            raise HTTPException(status_code=404, detail="Producto no encontrado")

        p_code = prod.get("supplier_product_code")
        query_key = {"user_email": u_email}
        if p_code:
            query_key["supplier_product_code"] = str(p_code)
        else:
            query_key["product_id"] = product_id

        update_fields = {}
        for k, v in override_data.model_dump(exclude_unset=True).items():
            if v is not None:
                update_fields[k] = v

        if not update_fields:
            return {"message": "Sin cambios"}

        update_fields["updated_at"] = datetime.utcnow()
        if p_code:
            update_fields["supplier_product_code"] = str(p_code)
        update_fields["product_id"] = product_id

        db["product_overrides"].update_one(
            query_key,
            {"$set": update_fields},
            upsert=True
        )

        pb_update = {k: v for k, v in update_fields.items() if k in ["custom_name", "custom_price", "custom_unit", "is_favorite", "is_hidden"]}
        if pb_update:
            db["productos_brutos"].update_one(
                {"_id": prod["_id"]},
                {"$set": pb_update}
            )

        return {"status": "ok", "message": "Producto personalizado correctamente", "override": update_fields}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/v1/products/{product_id}/favorite")
def toggle_favorite(
    product_id: str,
    user_email: Optional[str] = Query(None),
    x_user_email: Optional[str] = Header(None, alias="X-User-Email")
):
    """Alterna el estado favorito / habitual de un producto."""
    try:
        db = get_database()
        u_email = (x_user_email or user_email or "").lower().strip()
        if not u_email:
            raise HTTPException(status_code=401, detail="Usuario no autenticado")

        try:
            prod = db["productos_brutos"].find_one({"_id": ObjectId(product_id)})
        except Exception:
            prod = db["productos_brutos"].find_one({"id": product_id})

        if not prod:
            raise HTTPException(status_code=404, detail="Producto no encontrado")

        p_code = prod.get("supplier_product_code")
        query_key = {"user_email": u_email}
        if p_code:
            query_key["supplier_product_code"] = str(p_code)
        else:
            query_key["product_id"] = product_id

        existing = db["product_overrides"].find_one(query_key)
        curr_fav = existing.get("is_favorite", prod.get("is_favorite", False)) if existing else prod.get("is_favorite", False)
        new_fav = not curr_fav

        db["product_overrides"].update_one(
            query_key,
            {"$set": {"is_favorite": new_fav, "updated_at": datetime.utcnow()}},
            upsert=True
        )
        db["productos_brutos"].update_one(
            {"_id": prod["_id"]},
            {"$set": {"is_favorite": new_fav}}
        )

        return {"status": "ok", "product_id": product_id, "is_favorite": new_fav}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/v1/products/{product_id}/hide")
def toggle_hide(
    product_id: str,
    user_email: Optional[str] = Query(None),
    x_user_email: Optional[str] = Header(None, alias="X-User-Email")
):
    """Alterna el estado oculto / archivado de un producto."""
    try:
        db = get_database()
        u_email = (x_user_email or user_email or "").lower().strip()
        if not u_email:
            raise HTTPException(status_code=401, detail="Usuario no autenticado")

        try:
            prod = db["productos_brutos"].find_one({"_id": ObjectId(product_id)})
        except Exception:
            prod = db["productos_brutos"].find_one({"id": product_id})

        if not prod:
            raise HTTPException(status_code=404, detail="Producto no encontrado")

        p_code = prod.get("supplier_product_code")
        query_key = {"user_email": u_email}
        if p_code:
            query_key["supplier_product_code"] = str(p_code)
        else:
            query_key["product_id"] = product_id

        existing = db["product_overrides"].find_one(query_key)
        curr_hid = existing.get("is_hidden", prod.get("is_hidden", False)) if existing else prod.get("is_hidden", False)
        new_hid = not curr_hid

        db["product_overrides"].update_one(
            query_key,
            {"$set": {"is_hidden": new_hid, "updated_at": datetime.utcnow()}},
            upsert=True
        )
        db["productos_brutos"].update_one(
            {"_id": prod["_id"]},
            {"$set": {"is_hidden": new_hid}}
        )

        return {"status": "ok", "product_id": product_id, "is_hidden": new_hid}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/v1/catalogs/upload")
async def upload_catalog(
    supplier_id: str = Form("auto"),
    is_annex: bool = Form(False),
    user_email: Optional[str] = Form(None),
    x_user_email: Optional[str] = Header(None, alias="X-User-Email"),
    file: UploadFile = File(...)
):
    """Sube un archivo de catálogo (PDF o Excel), auto-detecta el proveedor si es necesario, lo almacena en GridFS y ejecuta el pipeline ETL asociado al cocinero."""
    try:
        db = get_database()
        u_email = (x_user_email or user_email or "pablo@horeca.com").lower().strip()
        file_bytes = await file.read()
        filename = file.filename or "catalogo.pdf"
        ext = os.path.splitext(filename)[1].lower()

        if ext not in [".xlsx", ".xls", ".pdf"]:
            raise HTTPException(status_code=400, detail="Formato no soportado. Debe ser .pdf, .xlsx o .xls.")

        # 1. Guardar temporalmente para la extracción
        clean_prefix = re.sub(r'[^a-zA-Z0-9_\-]', '_', os.path.splitext(filename)[0])[:30]
        with tempfile.NamedTemporaryFile(delete=False, prefix=f"{clean_prefix}_", suffix=ext) as tmp:
            tmp.write(file_bytes)
            tmp_path = tmp.name

        try:
            # 2. Fase de Extracción universal con detección de metadatos de proveedor
            raw_extracted, detected_supplier = extract_catalog_with_supplier(tmp_path, provider_id=supplier_id)
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

        # 3. Resolución / Alta automática del Proveedor para este cocinero
        is_new_supplier = False
        is_auto_detect = not supplier_id or supplier_id.lower() in ["auto", "nuevo", "detect", "none"]

        if is_auto_detect:
            candidate_name = None
            if detected_supplier and detected_supplier.get("name"):
                candidate_name = str(detected_supplier["name"]).strip()

            if not candidate_name or len(candidate_name) < 3:
                base = os.path.splitext(filename)[0]
                base_clean = re.sub(r"(?i)(?:catalogo|tarifa|lista|precios|noviembre|diciembre|enero|\d{4})", "", base)
                candidate_name = re.sub(r"[-_]+", " ", base_clean).strip().title() or "Proveedor Nuevo"

            slug = re.sub(r"[^a-z0-9]", "_", candidate_name.lower())[:25].strip("_")
            candidate_id = f"prov_{slug}" if slug else f"prov_{int(datetime.utcnow().timestamp())}"

            # Buscar si ya existe para este usuario por ID o nombre
            existing = db["proveedores"].find_one({
                "user_email": u_email,
                "$or": [
                    {"id": candidate_id},
                    {"name": {"$regex": f"^{re.escape(candidate_name)}$", "$options": "i"}}
                ]
            })

            if existing:
                supplier = existing
                supplier_id = existing["id"]
                supplier_name = existing["name"]
                updates = {}
                if not existing.get("phone") and detected_supplier and detected_supplier.get("phone"):
                    updates["phone"] = detected_supplier["phone"]
                if not existing.get("email") and detected_supplier and detected_supplier.get("email"):
                    updates["email"] = detected_supplier["email"]
                if updates:
                    db["proveedores"].update_one({"id": supplier_id, "user_email": u_email}, {"$set": updates})
            else:
                s_phone = detected_supplier.get("phone") if detected_supplier else None
                s_email = detected_supplier.get("email") if detected_supplier else None
                # Preferir WhatsApp si hay teléfono (especialmente si incluye móviles 6xx / 7xx o se indica en el catálogo)
                s_channel = "whatsapp" if s_phone else ("email" if s_email else "whatsapp")
                new_doc = {
                    "user_email": u_email,
                    "id": candidate_id,
                    "name": candidate_name,
                    "email": s_email,
                    "phone": s_phone,
                    "cif": detected_supplier.get("cif") if detected_supplier else None,
                    "preferred_channel": s_channel,
                    "delivery_days": ["Lunes", "Miércoles", "Viernes"],
                    "minimum_order_euro": 0.0,
                    "active": True,
                    "created_at": datetime.utcnow()
                }
                db["proveedores"].insert_one(new_doc)
                supplier = new_doc
                supplier_id = candidate_id
                supplier_name = candidate_name
                is_new_supplier = True
        else:
            supplier = db["proveedores"].find_one({"id": supplier_id, "user_email": u_email})
            if not supplier:
                supplier_name = supplier_id.replace("prov_", "").replace("_", " ").title()
                supplier = {
                    "user_email": u_email,
                    "id": supplier_id,
                    "name": supplier_name,
                    "email": f"pedidos@{supplier_id}.com",
                    "phone": None,
                    "preferred_channel": "whatsapp",
                    "delivery_days": ["Lunes", "Miércoles", "Viernes"],
                    "minimum_order_euro": 0.0,
                    "active": True,
                    "created_at": datetime.utcnow()
                }
                db["proveedores"].insert_one(supplier)
                is_new_supplier = True
            else:
                supplier_name = supplier.get("name", supplier_id)

        # 4. Guardar archivo original en GridFS
        gridfs_id = save_catalog_file(filename, file_bytes, supplier_id)

        # 5. Fase de Transformación (Entity Resolution con Ingredientes Maestros)
        master_ingredients = list(db["ingredientes_maestros"].find({}, {"_id": 0}))
        transformed_products = resolve_entities(raw_extracted, master_ingredients)

        # 6. Fase de Carga a MongoDB (asociada al usuario)
        loaded_count = load_raw_products(supplier_id, transformed_products, supplier_name, is_annex=is_annex, user_email=u_email)

        mode_msg = "Anexo de ofertas incorporado con éxito" if is_annex else "Catálogo renovado con éxito (se han sustituido los productos anteriores para evitar descatalogados)"

        return {
            "message": f"{mode_msg}.",
            "mode": "annex" if is_annex else "replace",
            "supplier_id": supplier_id,
            "supplier_name": supplier_name,
            "is_new_supplier": is_new_supplier,
            "detected_phone": supplier.get("phone"),
            "detected_email": supplier.get("email"),
            "gridfs_file_id": gridfs_id,
            "products_extracted": len(raw_extracted),
            "products_loaded": loaded_count
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error procesando catálogo: {str(e)}")

@app.post("/api/v1/orders")
def create_order(
    order_data: Order,
    user_email: Optional[str] = Query(None),
    x_user_email: Optional[str] = Header(None, alias="X-User-Email")
):
    """Crea y consolida un nuevo pedido en el sistema, dividiéndolo automáticamente por proveedores y generando mensajes WhatsApp."""
    try:
        db = get_database()
        u_email = resolve_user_email(x_user_email, user_email, getattr(order_data, "user_email", None))

        # Agrupar ítems por proveedor
        grouped = {}
        for item in order_data.items:
            s_id = item.supplier_id
            if s_id not in grouped:
                # Priorizar proveedor perteneciente a este cocinero
                supp = db["proveedores"].find_one({"id": s_id, "user_email": u_email})
                if not supp and item.supplier_name:
                    supp = db["proveedores"].find_one({"name": item.supplier_name, "user_email": u_email})
                if not supp:
                    supp = db["proveedores"].find_one({"id": s_id})
                s_name = item.supplier_name or (supp.get("name") if supp else s_id)
                s_email = supp.get("email") if supp else None
                s_phone = supp.get("phone") if supp else None
                s_pref = supp.get("preferred_channel", "whatsapp") if supp else "whatsapp"
                grouped[s_id] = {
                    "supplier_id": s_id,
                    "supplier_name": s_name,
                    "supplier_email": s_email,
                    "supplier_phone": s_phone,
                    "preferred_channel": s_pref,
                    "items": [],
                    "subtotal": 0.0
                }
            grouped[s_id]["items"].append(item)
            grouped[s_id]["subtotal"] += item.total_price

        # Generar texto y enlaces para WhatsApp por cada proveedor
        suborders = []
        for v in grouped.values():
            s_name = v["supplier_name"]
            items_lines = []
            for it in v["items"]:
                is_note = getattr(it, "unit", "") == "nota" or (getattr(it, "notes", None) and "indicacion" in it.notes.lower())
                if is_note:
                    line_str = f"• 📝 *NOTA / INDICACIÓN:* {it.ingredient_name}"
                else:
                    line_str = f"• {it.quantity} {it.unit} {it.ingredient_name}"
                    if it.is_off_catalog:
                        line_str += " *(Adicional / Fuera de catálogo)*"
                    if it.notes:
                        line_str += f" [Nota: {it.notes}]"
                items_lines.append(line_str)

            items_block = "\n".join(items_lines)
            chef_note_block = f"\n\n*Notas del Cocinero:*\n{order_data.chef_notes}" if order_data.chef_notes else ""

            wa_text = (
                f"*PEDIDO HOSTELERÍA - F&B SMARTORDER*\n"
                f"*Proveedor:* {s_name}\n"
                f"*Fecha:* {datetime.now().strftime('%d/%m/%Y %H:%M')}\n\n"
                f"*Líneas del pedido:*\n"
                f"{items_block}"
                f"{chef_note_block}\n\n"
                f"*Subtotal estimado:* {round(v['subtotal'], 2):.2f} €"
            )

            v["whatsapp_text"] = wa_text
            phone_raw = v.get("supplier_phone") or ""
            phone_clean = sanitize_whatsapp_phone(phone_raw)
            if phone_clean:
                v["whatsapp_url"] = f"https://api.whatsapp.com/send?phone={phone_clean}&text={urllib.parse.quote(wa_text)}"
            else:
                v["whatsapp_url"] = f"https://api.whatsapp.com/send?text={urllib.parse.quote(wa_text)}"

            # Envío automático por Email desde servidor si el canal preferido es email (Opción C con Brevo SMTP)
            if v.get("preferred_channel", "").lower() == "email":
                try:
                    smtp_host = os.getenv("SMTP_HOST", "smtp-relay.brevo.com")
                    smtp_port = int(os.getenv("SMTP_PORT", 587))
                    smtp_user = os.getenv("SMTP_USER", "c3e19e001@smtp-brevo.com")
                    smtp_pwd = os.getenv("SMTP_PASSWORD", "xsmtpsib-6965a5e17ef4c854c9e1e2b137c506ffffaf43bf1870e770d7a9debcd55e2bcf-1dCRyMTa28bNE0d5")
                    smtp_from = os.getenv("SMTP_FROM", "pablomoncayovega@gmail.com")

                    user_doc = db["usuarios"].find_one({"email": u_email})
                    chef_name = (user_doc.get("name") if user_doc else None) or "Cocinero"
                    restaurant_name = (user_doc.get("restaurant_name") if user_doc else None) or "Hostelería"

                    import smtplib
                    from email.message import EmailMessage
                    msg = EmailMessage()
                    msg["Subject"] = f"📦 Pedido Hostelería: {restaurant_name} ({chef_name}) - {s_name} - {datetime.now().strftime('%d/%m/%Y')}"
                    msg["From"] = f"{restaurant_name} ({chef_name}) <{smtp_from}>"
                    msg["Reply-To"] = u_email
                    msg["To"] = v.get("supplier_email") or "pedidos@proveedor.com"
                    msg.set_content(wa_text)

                    with smtplib.SMTP(smtp_host, smtp_port, timeout=12) as server:
                        if os.getenv("SMTP_USE_TLS", "true").lower() == "true":
                            server.starttls()
                        server.login(smtp_user, smtp_pwd)
                        server.send_message(msg)
                    v["email_dispatched"] = True
                    v["email_status"] = "enviado_smtp"
                    print(f"✅ [EMAIL BREVO] Pedido para {s_name} enviado con éxito a {v.get('supplier_email')}")
                except Exception as mail_err:
                    print(f"⚠️ Error enviando email con Brevo: {mail_err}")
                    v["email_dispatched"] = False
                    v["email_status"] = f"error: {str(mail_err)}"
            else:
                v["email_dispatched"] = False
                v["email_status"] = None

            suborders.append(SupplierSubOrder(**v))

        order_data.supplier_suborders = suborders
        order_data.total_amount = sum(so.subtotal for so in suborders)
        order_data.created_at = datetime.utcnow()
        order_data.status = "pending"

        order_dict = order_data.model_dump() if hasattr(order_data, "model_dump") else order_data.dict()
        order_dict["user_email"] = u_email
        res = db["pedidos"].insert_one(order_dict)
        order_id = str(res.inserted_id)
        order_dict["id"] = order_id
        order_dict["_id"] = order_id

        # Smart Habitualization: Auto-marcar como habituales/favoritos los productos pedidos
        for item in order_data.items:
            try:
                p_match = None
                it_id = getattr(item, "ingredient_id", None)
                if it_id:
                    try:
                        p_match = db["productos_brutos"].find_one({"_id": ObjectId(it_id)})
                    except Exception:
                        p_match = db["productos_brutos"].find_one({"id": it_id, "user_email": u_email})
                if not p_match and getattr(item, "ingredient_name", None):
                    p_match = db["productos_brutos"].find_one({
                        "user_email": u_email,
                        "$or": [
                            {"raw_name": item.ingredient_name},
                            {"clean_name": item.ingredient_name.lower()}
                        ]
                    })
                if p_match:
                    p_code = p_match.get("supplier_product_code")
                    q_ov = {"user_email": u_email}
                    if p_code:
                        q_ov["supplier_product_code"] = str(p_code)
                    else:
                        q_ov["product_id"] = str(p_match["_id"])
                    db["product_overrides"].update_one(
                        q_ov,
                        {"$set": {"is_favorite": True, "updated_at": datetime.utcnow()}},
                        upsert=True
                    )
                    db["productos_brutos"].update_one(
                        {"_id": p_match["_id"]},
                        {"$set": {"is_favorite": True}}
                    )
            except Exception as fav_err:
                print(f"⚠️ Error auto-marcando favorito: {fav_err}")

        return {
            "message": "Pedido consolidado creado con éxito.",
            "order_id": order_id,
            "order": order_dict
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creando pedido: {str(e)}")

@app.get("/api/v1/orders")
def list_orders(
    user_email: Optional[str] = Query(None),
    x_user_email: Optional[str] = Header(None, alias="X-User-Email")
):
    """Obtiene el historial de pedidos del cocinero."""
    try:
        db = get_database()
        u_email = (x_user_email or user_email or "").lower().strip()
        filter_query = {"user_email": u_email} if u_email else {}
        orders = list(db["pedidos"].find(filter_query).sort("created_at", -1))
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
async def scan_fridge_photo(
    file: UploadFile = File(...),
    user_email: Optional[str] = Query(None),
    x_user_email: Optional[str] = Header(None, alias="X-User-Email")
):
    """Recibe una foto de la lista de la nevera/pizarra, extrae los ítems y los mapea con el catálogo del cocinero."""
    try:
        from .vision_ai import process_fridge_photo
        u_email = (x_user_email or user_email or "pablo@horeca.com").lower().strip()
        file_bytes = await file.read()
        
        # 1. Extraer ítems de la foto
        raw_items = process_fridge_photo(file_bytes)
        
        # 2. Mapear con ingredientes maestros
        db = get_database()
        master_ingredients = list(db["ingredientes_maestros"].find({}, {"_id": 0}))
        mapped_items = resolve_entities(raw_items, master_ingredients)
        
        # 3. Asignar mejor oferta disponible para cada ingrediente (solo en el catálogo del cocinero)
        suggested_order_items = []
        for item in mapped_items:
            m_id = item.get("master_ingredient_id")
            best_offer = None
            if m_id:
                raw_offers = list(db["productos_brutos"].find({"master_ingredient_id": m_id, "user_email": u_email}))
                raw_offers.sort(key=lambda x: x.get("canonical_price") or x.get("price", 99999.0))
                if raw_offers:
                    best = raw_offers[0]
                    p_id = str(best["_id"])
                    del best["_id"]
                    best["product_id"] = p_id
                    best_offer = best

            # Fallback a búsqueda directa por nombre en productos_brutos del cocinero
            if not best_offer and item.get("raw_name"):
                name_clean = re.sub(r'[^a-zA-ZáéíóúñÁÉÍÓÚÑ\s]', '', item.get("raw_name")).strip()
                if len(name_clean) >= 3:
                    name_query = {
                        "user_email": u_email,
                        "$or": [
                            {"raw_name": {"$regex": re.escape(name_clean), "$options": "i"}},
                            {"clean_name": {"$regex": re.escape(name_clean), "$options": "i"}}
                        ]
                    }
                    candidates = list(db["productos_brutos"].find(name_query))
                    if candidates:
                        candidates.sort(key=lambda x: x.get("canonical_price") or x.get("price", 99999.0))
                        best = candidates[0]
                        p_id = str(best["_id"])
                        del best["_id"]
                        best["product_id"] = p_id
                        best_offer = best
                        m_id = best.get("master_ingredient_id")

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

@app.post("/api/v1/scan-kitchen-notes")
async def scan_kitchen_notes(
    file: UploadFile = File(...),
    user_email: Optional[str] = Query(None),
    x_user_email: Optional[str] = Header(None, alias="X-User-Email")
):
    """Alias para escanear notas manuscritas o listas de cocina."""
    return await scan_fridge_photo(file, user_email=user_email, x_user_email=x_user_email)

