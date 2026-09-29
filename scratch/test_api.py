from fastapi.testclient import TestClient
from fb_smartorder.api import app

client = TestClient(app)

def test_api_flow():
    print("=== PROBANDO ENDPOINTS DE FASTAPI API ===")
    
    # 1. Root
    res_root = client.get("/")
    print("1. GET / status:", res_root.status_code, res_root.json())
    assert res_root.status_code == 200

    # 2. Suppliers
    res_supp = client.get("/api/v1/suppliers")
    print("2. GET /api/v1/suppliers status:", res_supp.status_code, f"Found {len(res_supp.json()['suppliers'])} suppliers")
    assert res_supp.status_code == 200

    # 3. Ingredients
    res_ing = client.get("/api/v1/ingredients")
    print("3. GET /api/v1/ingredients status:", res_ing.status_code, f"Found {len(res_ing.json()['ingredients'])} master ingredients")
    assert res_ing.status_code == 200

    # 4. Create Order
    sample_order = {
        "items": [
            {
                "master_ingredient_id": "ing_tomate_rama",
                "ingredient_name": "Tomate Rama",
                "quantity": 5.0,
                "unit": "kg",
                "unit_price": 1.85,
                "total_price": 9.25,
                "supplier_id": "prov_paco_01",
                "supplier_name": "Frutas Paco S.L.",
                "is_off_catalog": False
            }
        ],
        "total_amount": 9.25,
        "chef_notes": "Prueba de pedido automático desde TestClient"
    }

    res_ord = client.post("/api/v1/orders", json=sample_order)
    print("4. POST /api/v1/orders status:", res_ord.status_code, res_ord.json().get("message"))
    assert res_ord.status_code == 200
    order_id = res_ord.json()["order_id"]

    # 5. Send Order
    res_send = client.post(f"/api/v1/orders/{order_id}/send")
    print("5. POST /api/v1/orders/{id}/send status:", res_send.status_code, res_send.json().get("message"))
    assert res_send.status_code == 200

    # 6. List Orders
    res_list = client.get("/api/v1/orders")
    print("6. GET /api/v1/orders status:", res_list.status_code, f"Total orders: {len(res_list.json()['orders'])}")
    assert res_list.status_code == 200

    print("✅ TODAS LAS PRUEBAS DE LA API PASARON SATISFACTORIAMENTE.")

if __name__ == "__main__":
    test_api_flow()
