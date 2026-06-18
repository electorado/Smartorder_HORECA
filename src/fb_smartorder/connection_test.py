import os
from pymongo import MongoClient

USER = "admin"
PASSWORD = "supplypassword"
HOST = "localhost"
PORT = "27017"

CONNECTION_STRING = f"mongodb://{USER}:{PASSWORD}@{HOST}:{PORT}/"

try:
    print("⏳ Conectando a MongoDB en Docker...")
    client = MongoClient(CONNECTION_STRING, serverSelectionTimeoutMS=5000)
    
    # La forma más simple e infalible de forzar una conexión y ver si responde:
    # Simplemente pedimos la lista de nombres de bases de datos
    dbs = client.list_database_names()
    
    print("Python se ha conectado correctamente a MongoDB.")
    print("🗄️  Bases de datos disponibles:")
    for db in dbs:
        print(f" - {db}")

except Exception as e:
    print("Error al conectar a la base de datos:")
    print(e)
