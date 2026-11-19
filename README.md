# F&B SmartOrder 🍽️📦

> **Sistema Inteligente de Gestión de Catálogos, Normalización de Ingredientes y Automatización de Pedidos HORECA**  
> *Proyecto de Fin de Ciclo (TFC) · Desarrollo de Aplicaciones Multiplataforma (DAM)*

[![Python](https://img.shields.io/badge/Python-3.11%20%7C%203.13-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg)](https://fastapi.tiangolo.com/)
[![Android](https://img.shields.io/badge/Android-Kotlin-3DDC84.svg)](https://developer.android.com/kotlin)
[![MongoDB](https://img.shields.io/badge/MongoDB-Atlas%20%26%20GridFS-47A248.svg)](https://www.mongodb.com/)
[![Google Gemini](https://img.shields.io/badge/IA-Google%20Gemini%20Vision-8E75C2.svg)](https://ai.google.dev/)
[![Brevo](https://img.shields.io/badge/Email-Brevo%20SMTP-0092FF.svg)](https://www.brevo.com/)

---

## 📋 Tabla de Contenidos
1. [El Problema y la Solución](#-el-problema-y-la-solución)
2. [Características Principales](#-características-principales)
3. [Arquitectura del Sistema](#-arquitectura-del-sistema)
4. [Documentación Técnica: Descarte de OCR Clásico (R01F03T01P01)](#-documentación-técnica-criterio-r01f03t01p01)
5. [Estructura del Proyecto](#-estructura-del-proyecto)
6. [Guía de Instalación y Puesta en Marcha](#-guía-de-instalación-y-puesta-en-marcha)
7. [Credenciales Demo y Pruebas Rápidas](#-credenciales-demo-y-pruebas-rápidas)
8. [Tecnologías Utilizadas](#-tecnologías-utilizadas)

---

## 💡 El Problema y la Solución

### El Reto en Cocina Profesional
En la operativa diaria de un restaurante, el proceso de aprovisionamiento es fragmentado y consume horas de trabajo:
* Cada distribuidor envía sus ofertas en soportes y formatos heterogéneos: **PDFs a varias columnas** (ej. Dialva, Abordo), **hojas de cálculo Excel** con celdas combinadas, o mensajes de mensajería.
* El cocinero debe comparar manualmente precios por unidad estándar (€/kg, €/L) antes de confeccionar la comanda.
* La transmisión del pedido requiere contactar a cada comercial por canales distintos (WhatsApp, correo electrónico) revisando pedidos mínimos y días de entrega.

### La Solución F&B SmartOrder
Una plataforma integral que automatiza el ciclo completo:
1. **Pipeline ETL Inteligente:** Ingesta y normaliza catálogos comerciales heterogéneos, emparejando referencias con una taxonomía de **ingredientes maestros** mediante coincidencia difusa (*fuzzy matching* fonético y sintáctico con `RapidFuzz`).
2. **Backend API Asíncrono (FastAPI):** Centraliza la lógica de negocio, catálogo vivo, gestión de personalizaciones de precios y enrutamiento inteligente de comandas.
3. **Visión por Computador con IA Generativa (Google Gemini):** El chef fotografía la pizarra de mise en place o una lista de compras manuscrita y la IA infiere y cuantifica los ingredientes cotejándolos con el catálogo disponible.
4. **Despacho Multicanal Automatizado:** Agrupa el pedido global en subórdenes por distribuidor, generando enlaces formateados para **WhatsApp**, envíos automáticos por **Email (Brevo SMTP)** y albaranes **PDF nativos** con código alfanumérico.
5. **App Móvil Nativa (Android / Kotlin):** Diseñada específicamente para condiciones de cocina (alto contraste retro *diner*, controles táctiles generosos y capacidad de funcionamiento autónomo/offline).

---

## ✨ Características Principales

### 📦 1. Pipeline ETL y Catálogo Unificado
* **Extractores Modulares (Patrón Factory):** Detectores espaciales (`pdf_spatial.py`), tabulares (`pdf_tabular.py`) y de hojas de cálculo (`excel.py`) capaces de parsear promociones anidadas y códigos comerciales (`C-XXXX`).
* **Personalización del Chef:** Posibilidad de renombrar productos con el alias interno de la cocina, fijar precios pactados especiales, modificar unidades de medida o marcar ingredientes habituales como **Favoritos** / **Ocultos**.
* **Almacenamiento Dual en MongoDB & GridFS:** Respaldo completo de metadatos en colecciones documentales y conservación del archivo fuente (PDF/Excel) en GridFS para trazabilidad legal y auditoría.

### 📷 2. Escaneo Inteligente con Google Gemini Vision
* Captura de notas en pizarra, papel o estantes con la cámara del dispositivo móvil.
* Reconocimiento semántico con `gemini-2.5-flash` / `gemini-1.5-flash`, capaz de interpretar caligrafía de cocina, abreviaturas ("2kg tom rama", "3 brik leche") y asociarlas directamente al catálogo.

### 🚚 3. Generación y Despacho de Comandas
* **Cálculo de Pedidos Mínimos y Días de Entrega:** Alerta si el pedido no alcanza el umbral de envío gratuito del proveedor.
* **Envío a WhatsApp:** Mensajes preformateados con saludo corporativo, desglose detallado de ítems y observaciones especiales.
* **Envío por Email (Brevo SMTP):** Despacho desatendido mediante relay SMTP (`smtp-relay.brevo.com`) con firma personalizada del restaurante y chef.
* **Generador de Albaranes PDF:** Emisión nativa en el móvil del documento PDF oficial del pedido con visor integrado (`PdfRenderer`) y opción de reenvío.

### 🔐 4. Área Personal y Autenticación
* Registro e inicio de sesión de cocina con almacenamiento seguro de credenciales mediante *hashing* criptográfico.
* **Recuperación de Contraseña con Brevo:** Envío automático de credenciales provisionales generadas por el servidor directamente a la bandeja del cocinero.
* Edición de perfil de chef/restaurante y opción de **Eliminar Cuenta** conforme al derecho de supresión de datos.

---

## 🏛️ Arquitectura del Sistema

El ecosistema se distribuye en una arquitectura multicapa desacoplada:

```
[ App Android (Kotlin) ]              [ Dashboard Validación (Streamlit) ]
         │                                            │
         └───────────────┬────────────────────────────┘
                         │ REST API (JSON / Multipart)
                         ▼
             [ Backend FastAPI (Python) ]
             ├── Ingesta y Extractores Modulares (Factory)
             ├── Motor de Normalización (RapidFuzz)
             ├── Integración IA (Google Gemini Vision API)
             └── Pasarela de Correo (Brevo SMTP Relay)
                         │
         ┌───────────────┴───────────────┐
         ▼                               ▼
 [ MongoDB Atlas (Nube) ]     [ MongoDB Docker (Local) ]
 ├── Colecciones:             ├── Almacenamiento Documental
 │   ├── usuarios             └── GridFS (Archivos PDF / Excel)
 │   ├── proveedores
 │   ├── productos_brutos
 │   ├── ingredientes_maestros
 │   └── pedidos
```

---

## 📑 Documentación Técnica: Criterio R01F03T01P01

### Descarte del Módulo OCR Clásico Local en Favor de IA Multimodal
Durante la fase de diseño inicial (Fase 1), se planteó la utilización de motores OCR locales basados en `Tesseract OCR` o `EasyOCR` para la lectura de comandas manuscritas. 

Conforme al criterio técnico **R01F03T01P01**, este enfoque fue **oficialmente descartado** por las siguientes limitaciones determinantes:
1. **Sensibilidad al Ruido y Deformación:** En entornos hosteleros, las pizarras y hojas sufren brillos, manchas de grasa, baja iluminación y caligrafía rápida, donde los motores OCR tradicionales presentaban tasas de error superiores al 45%.
2. **Ausencia de Inferencia Semántica:** El OCR clásico únicamente extrae cadenas de texto aisladas sin comprensión del contexto (no asocia que *"1 saco ceb"* significa *"1 unidad / saco de Cebolla común"* ni infiere unidades de medida implícitas).
3. **Eficiencia en la Solución Adoptada:** Se sustituyó por la API Multimodal de **Google Gemini**, logrando una tasa de acierto superior al 95% al combinar transcripción caligráfica con comprensión semántica directa y mapeo inteligente contra la taxonomía de la cocina.

---

## 📂 Estructura del Proyecto

```text
.
├── android/                         # Proyecto Nativo Android (Kotlin)
│   ├── app/src/main/
│   │   ├── java/com/fb/smartorder/  # Código fuente Kotlin
│   │   │   ├── data/network/        # Interfaces Retrofit y Cliente HTTP
│   │   │   ├── model/               # Modelos de datos Gson
│   │   │   ├── ui/                  # Adaptadores RecyclerView y diálogos
│   │   │   └── util/                # Generador de PDF, SessionManager
│   │   └── res/                     # Layouts XML, temas diner, tipografías
│   └── build.gradle.kts
│
├── src/fb_smartorder/               # Backend y Pipeline ETL (Python)
│   ├── api.py                       # Servidor REST FastAPI y endpoints
│   ├── database.py                  # Conexión MongoDB Atlas/Docker y GridFS
│   ├── models.py                    # Esquemas de datos con Pydantic
│   ├── extract.py                   # Coordinador de extracción de catálogos
│   ├── extractors/                  # Módulos especializados de parseo
│   │   ├── factory.py               # Selector dinámico de extractor
│   │   ├── excel.py                 # Extractor de tarifas en hojas de cálculo
│   │   ├── pdf_spatial.py           # Extractor por límites espaciales (Abordo)
│   │   └── pdf_tabular.py           # Extractor de columnas dinámicas (Dialva)
│   ├── transform.py                 # Algoritmos de coincidencia fonética/fuzzy
│   ├── load.py                      # Persistencia y auditoría documental
│   └── app_ui.py                    # Herramienta de validación en Streamlit (Fase 1)
│
├── docker-compose.yml               # Entorno contenedorizado para MongoDB local
├── pyproject.toml                   # Dependencias de Python gestionadas con UV
├── FB_SmartOrder_v1.0.apk           # Paquete APK listo para instalación
└── AGENTS.md                        # Directrices de desarrollo y roles de agentes
```

---

## 🚀 Guía de Instalación y Puesta en Marcha

### Prerrequisitos
* **Python:** 3.11 o superior (recomendado gestor `uv`).
* **Android:** Android Studio Ladybug / Koala o dispositivo con Android 8.0+ (API 26+).
* **Docker:** (Opcional, para ejecución de MongoDB en local).

---

### 1. Configuración del Backend

1. **Clonar el repositorio:**
   ```bash
   git clone https://github.com/electorado/Smartorder_HORECA.git
   cd Smartorder_HORECA
   ```

2. **Configurar variables de entorno (`.env`):**
   Crea un archivo `.env` en la raíz con tus claves:
   ```env
   # Base de Datos (MongoDB Atlas o local)
   MONGO_URI=mongodb+srv://<usuario>:<password>@cluster0.qvy1bzz.mongodb.net/fb_smartorder?retryWrites=true&w=majority

   # Inteligencia Artificial
   GEMINI_API_KEY=tu_clave_de_gemini_api

   # Pasarela de Correo Transaccional (Brevo)
   SMTP_HOST=smtp-relay.brevo.com
   SMTP_PORT=587
   SMTP_USER=tu_usuario_smtp_brevo
   SMTP_PASSWORD=tu_password_smtp_brevo
   SMTP_FROM=tu_correo_verificado_en_brevo@gmail.com
   ```

3. **Instalar dependencias y sincronizar:**
   ```bash
   uv sync
   # o con virtualenv estándar:
   # python3 -m venv .venv && source .venv/bin/activate && pip install -e .
   ```

4. **Inicializar datos y lanzar el servidor:**
   ```bash
   uv run uvicorn fb_smartorder.api:app --reload --host 0.0.0.0 --port 8000
   ```
   * *Documentación interactiva Swagger:* `http://localhost:8000/docs`
   * *Panel de validación Streamlit (Fase 1):* `uv run streamlit run src/fb_smartorder/app_ui.py`

---

### 2. Aplicación Móvil Android

#### Opción A: Instalación directa del APK
El repositorio incluye el instalador debug compilado listo para usar en tu móvil o emulador:
* Descarga o transfiere el archivo [FB_SmartOrder_v1.0.apk](./FB_SmartOrder_v1.0.apk) a tu dispositivo e instálalo permitiendo orígenes desconocidos.

#### Opción B: Compilación desde código fuente
```bash
cd android
./gradlew assembleDebug
```
El APK resultante se genera en `android/app/build/outputs/apk/debug/app-debug.apk`.

---

## 🔑 Credenciales Demo y Pruebas Rápidas

Para facilitar la corrección y evaluación del tribunal, la base de datos de producción incluye un perfil de cocina preconfigurado:

| Campo | Valor Demo |
| :--- | :--- |
| **Usuario / Email** | `cuisto@horeca.com` |
| **Contraseña** | `password123` |
| **Chef Asignado** | Chef Cuisto |
| **Restaurante** | Restaurante El Faro |
| **Catálogo Precargado** | 365 ingredientes normalizados |
| **Distribuidores Asociados** | 8 proveedores con condiciones comerciales reales |

> *Nota:* La aplicación cuenta además con un **modo autónomo de rescate** que permite navegar y validar la interfaz incluso ante pérdidas temporales de conexión con el backend.

---

## 🛠️ Tecnologías Utilizadas

* **Móvil:** Android SDK, Kotlin, ViewBinding, Material Components, Retrofit 2, OkHttp 3, Coroutines, AndroidX CameraX, AndroidX PdfRenderer.
* **Backend:** Python 3, FastAPI, Pydantic v2, Uvicorn, Motor/PyMongo, GridFS, Requests.
* **ETL & Data Science:** Pandas, OpenPyXL, PyPDF, RapidFuzz (Levenshtein & Token Sort Ratio).
* **Inteligencia Artificial:** Google Generative AI (`gemini-2.5-flash`).
* **Comunicaciones:** Brevo SMTP Relay, WhatsApp Click-to-Chat API.
* **Bases de Datos:** MongoDB 7.0 (Docker) y MongoDB Atlas (Cloud Cluster).

---

## 👨‍🍳 Autor
* **Pablo Moncayo Vega** - *Desarrollo de Aplicaciones Multiplataforma (DAM)*
