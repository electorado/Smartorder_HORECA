import io
from PIL import Image, ImageDraw, ImageFont
from fastapi.testclient import TestClient
from fb_smartorder.api import app
from fb_smartorder.extract import extract_image_list

# 1. Crear una imagen de muestra representando la foto de la pizarra de la nevera
img = Image.new('RGB', (600, 400), color=(240, 240, 240))
draw = ImageDraw.Draw(img)
draw.text((20, 30), "LISTA DE COMPRA NEVERA", fill=(0, 0, 0))
draw.text((20, 80), "- 5 kg Tomate rama", fill=(0, 0, 0))
draw.text((20, 130), "- 2 kg Pechuga de pollo", fill=(0, 0, 0))
draw.text((20, 180), "- 1 ud Aceite Oliva 5L", fill=(0, 0, 0))

buf = io.BytesIO()
img.save(buf, format='JPEG')
img_bytes = buf.getvalue()

def test_fridge_photo():
    print("=== PROBANDO ESCÁNER DE LISTA DE NEVERA ===")
    
    # Pruebas directas de función
    items = extract_image_list(img_bytes)
    print(f"Extraídos {len(items)} ítems de la foto:")
    for it in items:
        print(" ->", it)

    assert len(items) > 0

    # Prueba de Endpoint FastAPI
    client = TestClient(app)
    response = client.post(
        "/api/v1/ocr/fridge-list",
        files={"file": ("foto_nevera.jpg", img_bytes, "image/jpeg")}
    )
    print("\nRespuesta de API POST /api/v1/ocr/fridge-list:")
    print("Status:", response.status_code)
    print("Items mapeados:", response.json().get("items_found_count"))
    assert response.status_code == 200

    print("\n✅ PRUEBA DEL ESCÁNER DE FOTO DE NEVERA COMPLETADA CON ÉXITO.")

if __name__ == "__main__":
    test_fridge_photo()
