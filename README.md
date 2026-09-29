# [F&B SmartOrder]

An Intelligent Data Pipeline and Order Automation System for the Food & Beverage Sector.

---

## 🚀 El Proyecto

Este proyecto nace como mi **Trabajo de Fin de Ciclo (TFC)** para el Grado Superior en Desarrollo de Aplicaciones Multiplataforma (DAM). Sin embargo, no es solo un proyecto académico; es una solución de software diseñada desde la experiencia directa en la gestión del sector de la hostelería (Food & Beverage).

### El Problema Real
En el día a día de una cocina profesional, la gestión de compras puede convertirse en una tarea ineficiente y caótica. Cada proveedor envía sus catálogos, ofertas y actualizaciones de precios en formatos completamente dispares y no estructurados (Excel caóticos, PDFs densos, imágenes de albaranes o mensajes de texto). Un jefe de cocina pierde horas comparando precios manualmente o gestionando pedidos por canales fragmentados en mitad del servicio, incluso teniendo que enviar varios emails o mensajes a los diferentes proveedores.

### La Solución
**[F&B SmartOrder]** automatiza y unifica este proceso de principio a fin a través de dos componentes principales:
1. **Un Pipeline de Ingeniería de Datos (Backend):** Que ingiere, limpia y normaliza de forma flexible los catálogos caóticos de los proveedores empleando bases de datos NoSQL.
2. **Una Interfaz Móvil Ágil (Frontend):** Diseñada para "fricción cero", que permite al chef buscar ingredientes de forma unificada, resolver conflictos de existencias, añadir notas o productos fuera de catálogo y disparar pedidos automáticos consolidados con un solo clic.

---

## 🛠️ Arquitectura y Tecnologías

Para resolver la flexibilidad que requieren los datos y la robustez que necesita la automatización, se ha diseñado una arquitectura desacoplada basada en servicios:
Para resolver la flexibilidad que requieren los datos y la robustez que necesita la automatización, se ha diseñado una arquitectura desacoplada basada en servicios:

### 🗄️ 1. Capa de Almacenamiento e Ingesta (El Caos Estructurado)
*   **Tecnología Principal:** **MongoDB (BSON / GridFS)**
*   **Justificación:** Debido a la naturaleza dispar de los catálogos de los proveedores (XLSX, PDF, imágenes), las bases de datos relacionales tradicionales fallarían por rigidez de esquema. MongoDB aporta la flexibilidad necesaria para almacenar los documentos en su estado nativo. Además, se utiliza GridFS para almacenar y respaldar los archivos físicos originales (como fotos de ofertas o PDFs), permitiendo una auditoría visual en caso de discrepancias.

### 🧠 2. Capa del Pipeline y Lógica de Datos (El Cerebro ETL)
*   **Tecnología Principal:** **Python (Pandas, OpenPyXL, PyPDF2)**
*   **Justificación:** Python es el estándar de la industria en Ingeniería de Datos. Esta capa ejecuta el proceso de Extracción, Transformación y Carga (ETL). Se encarga de limpiar el texto procedente de MongoDB (eliminación de ruidos, estandarización de formatos) y ejecuta algoritmos de coincidencia (*Entity Resolution*) para emparejar el producto bruto del proveedor con el ingrediente maestro unificado del sistema.

### ⚙️ 3. Capa del Servidor y API (El Conector)
*   **Tecnología Principal:** **FastAPI (Python)**
*   **Justificación:** Proporciona un backend asíncrono de alto rendimiento que expone los endpoints necesarios para alimentar la interfaz de usuario. Gestiona la lógica de las peticiones en tiempo real (autocompletado, resolución de conflictos de proveedores) y orquesta la automatización de salida (generación de hojas de pedido y envío asíncrono de emails/notificaciones a los proveedores).

### 📱 4. Capa de Interfaz de Usuario (Fricción Cero)
*   **Tecnología Principal:** **Streamlit / Web Responsive**
*   **Justificación:** Con el objetivo de optimizar los tiempos de desarrollo y evitar la sobreingeniería de un entorno móvil nativo complejo (como React Native o Flutter), se ha optado por un enfoque web ágil y adaptativo. Esto permite poner el foco del proyecto donde realmente aporta valor de negocio: la arquitectura del dato, el procesamiento del backend y un flujo de experiencia de usuario (UX) diseñado específicamente para el ritmo de una cocina.

---

## ⚡ Guía de Ejecución Rápida

### 1. Iniciar Infraestructura de Base de Datos (MongoDB + GridFS)
```bash
docker compose up -d
```

### 2. Sincronizar Dependencias del Entorno
```bash
uv sync
```

### 3. Ejecutar Pipeline ETL de Ingesta y Entity Resolution
```bash
uv run python3 src/main.py
```

### 4. Iniciar Servidor Backend FastAPI
```bash
uv run uvicorn fb_smartorder.api:app --reload --port 8000
```
*Documentación interactiva Swagger disponible en: `http://localhost:8000/docs`*

### 5. Iniciar Interfaz de Usuario (Streamlit)
```bash
uv run streamlit run src/fb_smartorder/app_ui.py
```
*Panel Web del Chef accesible en: `http://localhost:8501`*

