import os
import hashlib
from datetime import datetime
from dotenv import load_dotenv
from pymongo import MongoClient
import gridfs

load_dotenv(override=True)

def hash_password(password: str) -> str:
    """Genera el hash SHA-256 de una contraseña."""
    return hashlib.sha256(password.encode("utf-8")).hexdigest()

def get_db_client():
    """Crea la conexión con MongoDB usando Atlas (MONGO_URI) o credenciales locales."""
    mongo_uri = os.getenv("MONGO_URI")
    if mongo_uri:
        return MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)

    user = os.getenv("MONGO_ROOT_USER", "admin")
    password = os.getenv("MONGO_ROOT_PASSWORD", "supplypassword")
    host = os.getenv("MONGO_HOST", "localhost")
    port = os.getenv("MONGO_PORT", "27017")
    connection_string = f"mongodb://{user}:{password}@{host}:{port}/"

    return MongoClient(connection_string, serverSelectionTimeoutMS=5000)

def get_database(db_name="fb_smartorder"):
    """Obtiene la base de datos principal."""
    client = get_db_client()
    try:
        default_db = client.get_default_database()
        if default_db is not None:
            return default_db
    except Exception:
        pass
    return client[db_name]

def get_gridfs(db_name="fb_smartorder"):
    """Acceso a GridFS para guardar ficheros (PDFs y Excel)."""
    db = get_database(db_name)
    return gridfs.GridFS(db)

def init_db(db_name="fb_smartorder"):
    """Crea índices y carga datos iniciales si la base de datos está vacía."""
    try:
        db = get_database(db_name)
        
        # Índices principales
        db["productos_brutos"].create_index([("clean_name", "text")])
        db["productos_brutos"].create_index([("supplier_id", 1)])
        db["productos_brutos"].create_index([("master_ingredient_id", 1)])
        db["ingredientes_maestros"].create_index([("name", 1)], unique=True)
        db["proveedores"].create_index([("user_email", 1), ("id", 1)], unique=True)

        # Proveedores por defecto si no hay datos
        suppliers_count = db["proveedores"].count_documents({})
        if suppliers_count < 4:
            suppliers = [
                {
                    "id": "prov_paco_01",
                    "name": "Frutas Paco S.L.",
                    "email": "pedidos@frutaspaco.es",
                    "phone": "+34600111222",
                    "preferred_channel": "whatsapp",
                    "delivery_days": ["Lunes", "Miércoles", "Viernes"],
                    "minimum_order_euro": 50.0,
                    "active": True
                },
                {
                    "id": "prov_carnes_gomez_02",
                    "name": "Carnes Gómez & Hijos",
                    "email": "ventas@carnesgomez.com",
                    "phone": "+34611333444",
                    "preferred_channel": "whatsapp",
                    "delivery_days": ["Martes", "Jueves", "Sábado"],
                    "minimum_order_euro": 100.0,
                    "active": True
                },
                {
                    "id": "prov_mariscos_sur_03",
                    "name": "Mariscos del Sur",
                    "email": "pedidos@mariscosdelsur.es",
                    "phone": "+34622555666",
                    "preferred_channel": "whatsapp",
                    "delivery_days": ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes"],
                    "minimum_order_euro": 80.0,
                    "active": True
                },
                {
                    "id": "prov_dialva_04",
                    "name": "DIALVA Hostelería S.L.",
                    "email": "pedidos@dialva.es",
                    "phone": "+34900888999",
                    "preferred_channel": "whatsapp",
                    "delivery_days": ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes"],
                    "minimum_order_euro": 60.0,
                    "active": True
                }
            ]
            for s in suppliers:
                db["proveedores"].update_one({"id": s["id"]}, {"$set": s}, upsert=True)

        # Ingredientes maestros iniciales
        master_seeds = [
            {"id": "ing_tomate_rama", "name": "Tomate Rama", "category": "Frutas y Verduras", "standard_unit": "kg", "description": "Tomate de rama para ensaladas y guisos"},
            {"id": "ing_cebolla_recogida", "name": "Cebolla Recogida", "category": "Frutas y Verduras", "standard_unit": "kg", "description": "Cebolla común o grano"},
            {"id": "ing_solomillo_ternera", "name": "Solomillo de Ternera", "category": "Carnes", "standard_unit": "kg", "description": "Solomillo limpio de ternera de año"},
            {"id": "ing_pechuga_pollo", "name": "Pechuga de Pollo", "category": "Carnes", "standard_unit": "kg", "description": "Pechuga fresca limpia de pollo"},
            {"id": "ing_aceite_oliva_virgen_extra", "name": "Aceite de Oliva Virgen Extra 5L", "category": "Secos y Aceites", "standard_unit": "ud", "description": "Garrafa de 5 litros AOVE"},
            {"id": "ing_leche_entera", "name": "Leche Entera 1L", "category": "Lácteos", "standard_unit": "L", "description": "Brik de 1 litro leche entera"},
            {"id": "ing_lubina_fresca", "name": "Lubina Fresca Ración", "category": "Pescados y Mariscos", "standard_unit": "kg", "description": "Lubina de estero / ración 400-600g"},
            {"id": "ing_dorada_fresca", "name": "Dorada", "category": "Pescados y Mariscos", "standard_unit": "kg", "description": "Dorada fresca ración"},
            {"id": "ing_ajo_malla", "name": "Ajo", "category": "Frutas y Verduras", "standard_unit": "kg", "description": "Ajo morado malla 1kg"},
            {"id": "ing_ternera_guisar", "name": "Ternera pa guisar", "category": "Carnes", "standard_unit": "kg", "description": "Carne de ternera troceada para guisos"},
            {"id": "ing_ajoarriero", "name": "AJOARRIERO", "category": "Quinta Gama", "standard_unit": "kg", "description": "Ajoarriero tradicional con bacalao"},
            {"id": "ing_burrata", "name": "Burrata Fresca", "category": "Lácteos", "standard_unit": "kg", "description": "Queso italiano Burrata fresca"},
            {"id": "ing_mascarpone", "name": "Mascarpone", "category": "Lácteos", "standard_unit": "kg", "description": "Queso Mascarpone tarrina"},
            {"id": "ing_canelon_carne", "name": "Canelón de Carne", "category": "Quinta Gama", "standard_unit": "kg", "description": "Canelones rellenos de carne sin bechamel"},
            {"id": "ing_bacalao_filete", "name": "Filete de Bacalao", "category": "Pescados y Mariscos", "standard_unit": "kg", "description": "Filete de bacalao desmigado / Gadus Morhua"},
            {"id": "ing_lenguado", "name": "Lenguado Tigre", "category": "Pescados y Mariscos", "standard_unit": "kg", "description": "Lenguado ración 200-300g"}
        ]
        for ing in master_seeds:
            db["ingredientes_maestros"].update_one({"id": ing["id"]}, {"$set": ing}, upsert=True)

        # Índices y usuarios por defecto
        db["usuarios"].create_index([("email", 1)], unique=True)
        db["productos_brutos"].create_index([("user_email", 1)])
        db["proveedores"].create_index([("user_email", 1)])
        db["pedidos"].create_index([("user_email", 1)])
        for default_user in [
            {"email": "cuisto@horeca.com", "name": "Chef Cuisto", "restaurant_name": "Restaurante El Faro"},
            {"email": "pablo@horeca.com", "name": "Pablo Moncayo", "restaurant_name": "Restaurante El Faro"}
        ]:
            if db["usuarios"].count_documents({"email": default_user["email"]}) == 0:
                db["usuarios"].insert_one({
                    "name": default_user["name"],
                    "email": default_user["email"],
                    "password_hash": hash_password("password123"),
                    "restaurant_name": default_user["restaurant_name"],
                    "created_at": datetime.utcnow()
                })

        # Sincronizar catálogo y proveedores demo para cuisto@horeca.com
        if db["proveedores"].count_documents({"user_email": "cuisto@horeca.com"}) == 0:
            for p in db["proveedores"].find({"user_email": "pablo@horeca.com"}):
                p_copy = dict(p)
                p_copy.pop("_id", None)
                p_copy["user_email"] = "cuisto@horeca.com"
                db["proveedores"].insert_one(p_copy)

        if db["productos_brutos"].count_documents({"user_email": "cuisto@horeca.com"}) == 0:
            for pr in db["productos_brutos"].find({"user_email": "pablo@horeca.com"}):
                pr_copy = dict(pr)
                pr_copy.pop("_id", None)
                pr_copy["user_email"] = "cuisto@horeca.com"
                db["productos_brutos"].insert_one(pr_copy)

        if db["pedidos"].count_documents({"user_email": "cuisto@horeca.com"}) == 0:
            for o in db["pedidos"].find({"user_email": "pablo@horeca.com"}):
                o_copy = dict(o)
                o_copy.pop("_id", None)
                o_copy["user_email"] = "cuisto@horeca.com"
                db["pedidos"].insert_one(o_copy)

        return True

    except Exception as e:
        print(f"Error inicializando base de datos: {e}")
        return False


class DatabaseManager:
    """Clase helper para agrupar accesos a base de datos y GridFS."""

    @staticmethod
    def get_client():
        return get_db_client()

    @staticmethod
    def get_database(db_name="fb_smartorder"):
        return get_database(db_name)

    @staticmethod
    def get_gridfs(db_name="fb_smartorder"):
        return get_gridfs(db_name)

    @staticmethod
    def init_db(db_name="fb_smartorder"):
        return init_db(db_name)

    @staticmethod
    def save_catalog_file(filename: str, file_bytes: bytes, supplier_id: str) -> str:
        from .load import save_catalog_file as _save
        return _save(filename, file_bytes, supplier_id)

    @staticmethod
    def load_raw_products(provider_id: str, products: list, provider_name: str = None) -> int:
        from .load import load_raw_products as _load
        return _load(provider_id, products, provider_name)
