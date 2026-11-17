import os
import hashlib
from datetime import datetime
from dotenv import load_dotenv
from pymongo import MongoClient
import gridfs

load_dotenv(override=True)

def hash_password(password: str) -> str:
    """Calcula el hash SHA-256 de una contraseña."""
    return hashlib.sha256(password.encode("utf-8")).hexdigest()

def get_db_client():
    """Inicializa y devuelve el cliente utilizando MONGO_URI (Atlas) o variables locales (Docker)."""
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
    """Devuelve la instancia de la base de datos específica del proyecto."""
    client = get_db_client()
    try:
        default_db = client.get_default_database()
        if default_db is not None:
            return default_db
    except Exception:
        pass
    return client[db_name]

def get_gridfs(db_name="fb_smartorder"):
    """Devuelve la instancia de GridFS para almacenar archivos binarios (PDFs, Excel nativos)."""
    db = get_database(db_name)
    return gridfs.GridFS(db)

def init_db(db_name="fb_smartorder"):
    """Inicializa colecciones e índices esenciales en MongoDB y siembra datos iniciales de prueba."""
    try:
        db = get_database(db_name)
        
        # Índices
        db["productos_brutos"].create_index([("clean_name", "text")])
        db["productos_brutos"].create_index([("supplier_id", 1)])
        db["productos_brutos"].create_index([("master_ingredient_id", 1)])
        db["ingredientes_maestros"].create_index([("name", 1)], unique=True)
        db["proveedores"].create_index([("user_email", 1), ("id", 1)], unique=True)

        # Semilla de proveedores si la colección está vacía o incompleta
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

        # Semilla de ingredientes maestros si está vacía o incompleta
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

        # Semilla e índices de usuarios y multi-tenancy por cocinero
        db["usuarios"].create_index([("email", 1)], unique=True)
        db["productos_brutos"].create_index([("user_email", 1)])
        db["proveedores"].create_index([("user_email", 1)])
        db["pedidos"].create_index([("user_email", 1)])
        if db["usuarios"].count_documents({"email": "pablo@horeca.com"}) == 0:
            db["usuarios"].insert_one({
                "name": "Pablo Moncayo",
                "email": "pablo@horeca.com",
                "password_hash": hash_password("password123"),
                "restaurant_name": "Restaurante El Faro",
                "created_at": datetime.utcnow()
            })

        return True

    except Exception as e:
        print(f"Error inicializando base de datos: {e}")
        return False


class DatabaseManager:
    """Clase de infraestructura y persistencia que gestiona MongoDB y GridFS."""

    @staticmethod
    def get_client():
        """Devuelve el cliente activo de MongoClient."""
        return get_db_client()

    @staticmethod
    def get_database(db_name="fb_smartorder"):
        """Devuelve la base de datos de MongoDB configurada."""
        return get_database(db_name)

    @staticmethod
    def get_gridfs(db_name="fb_smartorder"):
        """Devuelve el bucket de GridFS para almacenamiento de archivos binarios."""
        return get_gridfs(db_name)

    @staticmethod
    def init_db(db_name="fb_smartorder"):
        """Inicializa colecciones, índices y semillas maestras."""
        return init_db(db_name)

    @staticmethod
    def save_catalog_file(filename: str, file_bytes: bytes, supplier_id: str) -> str:
        """Guarda un fichero original de catálogo en GridFS."""
        from .load import save_catalog_file as _save
        return _save(filename, file_bytes, supplier_id)

    @staticmethod
    def load_raw_products(provider_id: str, products: list, provider_name: str = None) -> int:
        """Carga e indexa los productos procesados en MongoDB."""
        from .load import load_raw_products as _load
        return _load(provider_id, products, provider_name)