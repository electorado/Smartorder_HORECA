from fb_smartorder.database import get_database

db = get_database()

print("=== REVISANDO REPOSITORIO MONGO DE RICOTTA Y DIALVA ===")

# Buscar Ricotta en ingredientes maestros
masters = list(db["ingredientes_maestros"].find({"name": {"$regex": "ricotta", "$options": "i"}}))
print(f"Ingredientes maestros de Ricotta ({len(masters)}):", masters)

# Buscar Ricotta en productos brutos
raw_ricotta = list(db["productos_brutos"].find({"raw_name": {"$regex": "ricotta", "$options": "i"}}))
print(f"Productos brutos de Ricotta ({len(raw_ricotta)}):", raw_ricotta)

# Ver todos los ingredientes maestros registrados actualmente
all_masters = list(db["ingredientes_maestros"].find({}, {"_id": 0, "id": 1, "name": 1, "category": 1}))
print(f"\nTotal ingredientes maestros ({len(all_masters)}):")
for m in all_masters:
    print(" ->", m)

# Ver cuántos productos brutos hay cargados por proveedor
pipeline = [
    {"$group": {"_id": "$supplier_name", "count": {"$sum": 1}, "mapped_count": {"$sum": {"$cond": [{"$ifNull": ["$master_ingredient_id", False]}, 1, 0]}}}}
]
stats = list(db["productos_brutos"].aggregate(pipeline))
print("\nEstadísticas de productos brutos por proveedor:")
for s in stats:
    print(f" -> Proveedor: {s['_id']} | Total productos: {s['count']} | Mapeados a maestro: {s['mapped_count']}")
