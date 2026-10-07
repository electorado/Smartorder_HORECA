# [F&B SmartOrder]

An Intelligent Data Pipeline and Order Automation System for the Food & Beverage Sector.

---

## 🚀 El Proyecto

Este proyecto nace como mi **Trabajo de Fin de Ciclo (TFC)** para el Grado Superior en Desarrollo de Aplicaciones Multiplataforma (DAM). Es una solución pensada desde la experiencia en hostelería para resolver un problema cotidiano de los restaurantes.

### El Problema Real
En el día a día de una cocina, la gestión de compras suele ser caótica. Cada proveedor envía sus catálogos, ofertas y precios en formatos distintos (hojas de Excel, PDFs a varias columnas, notas o mensajes). Quien gestiona los pedidos pierde mucho tiempo comparando precios a mano y contactando a cada proveedor por separado.

### La Solución
**[F&B SmartOrder]** unifica y agiliza este proceso:
1. **Pipeline de datos y backend:** Ingesta y normaliza los catálogos en MongoDB, unifica productos equivalentes bajo un mismo ingrediente maestro y expone los datos mediante una API en FastAPI.
2. **Interfaz de usuario:** Un panel web en Streamlit para validar datos, buscar ingredientes y comparar precios, y una app móvil nativa en Android (Kotlin) para hacer los pedidos desde la cocina o el almacén.

---

## 🛠️ Arquitectura y Tecnologías

El sistema sigue una arquitectura desacoplada por capas:

### 🗄️ 1. Almacenamiento e Ingesta
* **MongoDB y GridFS**: Almacena los catálogos en colecciones documentales y guarda los archivos originales (PDFs, Excels) para auditoría visual si surgen dudas.

### 🧠 2. Pipeline ETL y Normalización
* **Python (Pandas, OpenPyXL, PyPDF, RapidFuzz)**: Extrae los datos, limpia el texto y empareja los productos de distintos proveedores con el ingrediente maestro correspondiente.

### ⚙️ 3. Backend y API
* **FastAPI**: Servidor asíncrono con endpoints REST para búsquedas, comparativas de precios y generación de pedidos.

### 📱 4. Interfaz de Usuario
* **Streamlit**: Panel web para probar el sistema, buscar ingredientes y comparar ofertas de proveedores.
* **Android Nativo (Kotlin)**: Aplicación móvil para gestionar el inventario y tramitar pedidos desde el teléfono.

---

## ⚡ Guía de Ejecución Rápida

### 1. Iniciar Base de Datos (MongoDB + GridFS)
```bash
docker compose up -d
```

### 2. Sincronizar Dependencias
```bash
uv sync
```

### 3. Ejecutar Pipeline ETL
```bash
uv run python3 src/main.py
```

### 4. Iniciar Backend FastAPI
```bash
uv run uvicorn fb_smartorder.api:app --reload --port 8000
```
*Documentación Swagger en: `http://localhost:8000/docs`*

### 5. Iniciar Interfaz Web (Streamlit)
```bash
uv run streamlit run src/fb_smartorder/app_ui.py
```
*Panel web accesible en: `http://localhost:8501`*
