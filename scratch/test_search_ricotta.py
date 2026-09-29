from fb_smartorder.database import get_database

db = get_database()

search_query = "Ricotta"

print(f"=== PROBANDO BÚSQUEDA DE '{search_query}' ===")

# Simular consulta de app_ui.py
query_master = {"$or": [
    {"name": {"$regex": search_query, "$options": "i"}},
    {"id": {"$regex": search_query, "$options": "i"}},
    {"category": {"$regex": search_query, "$options": "i"}}
]}

masters = list(db["ingredientes_maestros"].find(query_master, {"_id": 0}))

raw_matches = list(db["productos_brutos"].find(
    {"$or": [
        {"raw_name": {"$regex": search_query, "$options": "i"}},
        {"clean_name": {"$regex": search_query, "$options": "i"}}
    ]},
    {"_id": 0}
))

print(f"Ingredientes maestros coincidentes: {len(masters)}")
for m in masters:
    offers = list(db["productos_brutos"].find({"master_ingredient_id": m["id"]}, {"_id": 0}))
    print(f" -> Maestro: '{m['name']}' (ID: {m['id']}) | Ofertas encontradas: {len(offers)}")
    for o in offers:
        print(f"    - Proveedor: {o['supplier_name']} | Precio: {o['price']} €/{o['unit']}")

print(f"\nProductos brutos coincidentes: {len(raw_matches)}")
for rm in raw_matches:
    print(f" -> Bruto: '{rm['raw_name']}' | Proveedor: {rm['supplier_name']} | Precio: {rm['price']} €/{rm['unit']}")

assert len(masters) > 0 or len(raw_matches) > 0
print("\n✅ PRUEBA DE BÚSQUEDA DE RICOTTA EXITOSA.")
