import streamlit as st
import pandas as pd
from datetime import datetime
import json
import os

# Configuración de página con estética moderna y amplia
st.set_page_config(
    page_title="F&B SmartOrder | Chef Automation System",
    page_icon="🍳",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Estilos CSS personalizados para una interfaz de alta calidad (Glassmorphism, badges, tarjetas modernas)
st.markdown("""
<style>
    /* Estilos globales y paleta de colores premium */
    .stApp {
        background-color: #0f172a;
        color: #f8fafc;
        font-family: 'Inter', system-ui, -apple-system, sans-serif;
    }
    
    /* Header principal */
    .header-box {
        background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
        padding: 1.5rem 2rem;
        border-radius: 16px;
        border: 1px solid #334155;
        margin-bottom: 2rem;
        box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.3);
    }
    .header-title {
        font-size: 2.2rem;
        font-weight: 800;
        background: linear-gradient(90deg, #38bdf8 0%, #818cf8 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin: 0;
    }
    .header-subtitle {
        color: #94a3b8;
        font-size: 1rem;
        margin-top: 0.25rem;
    }

    /* Tarjetas de productos e ingredientes */
    .product-card {
        background: rgba(30, 41, 59, 0.7);
        backdrop-filter: blur(10px);
        border: 1px solid #334155;
        border-radius: 12px;
        padding: 1.25rem;
        margin-bottom: 1rem;
        transition: transform 0.2s, border-color 0.2s;
    }
    .product-card:hover {
        border-color: #38bdf8;
        transform: translateY(-2px);
    }
    .best-price-badge {
        background-color: #065f46;
        color: #34d399;
        font-size: 0.75rem;
        font-weight: 700;
        padding: 0.25rem 0.6rem;
        border-radius: 9999px;
        text-transform: uppercase;
    }
    .category-badge {
        background-color: #312e81;
        color: #a5b4fc;
        font-size: 0.75rem;
        font-weight: 600;
        padding: 0.25rem 0.6rem;
        border-radius: 9999px;
    }
    
    /* Resumen de pedido en el sidebar */
    .cart-box {
        background: #1e293b;
        border: 1px solid #334155;
        border-radius: 12px;
        padding: 1rem;
        margin-top: 1rem;
    }
    .cart-total {
        font-size: 1.5rem;
        font-weight: 800;
        color: #38bdf8;
    }

    /* Botón verde de acción rápida */
    div.stButton > button {
        border-radius: 10px;
        font-weight: 700;
    }
</style>
""", unsafe_allow_html=True)

# Inicializar estado de la sesión si no existe
if "cart" not in st.session_state:
    st.session_state.cart = [] # Lista de ítems en el carrito
if "orders_history" not in st.session_state:
    st.session_state.orders_history = []

# Conexión local a servicios de datos (MongoDB a través del módulo interno)
from fb_smartorder.database import get_database, init_db, get_db_client
from fb_smartorder.load import load_raw_products, save_catalog_file
from fb_smartorder.extract import extract_excel, extract_pdf
from fb_smartorder.transform import resolve_entities

@st.cache_resource
def setup_infrastructure():
    """Asegura la inicialización de la base de datos."""
    try:
        client = get_db_client()
        client.server_info()
        init_db()
        return True
    except Exception as e:
        return False

db_available = setup_infrastructure()

# Header de la App
st.markdown("""
<div class="header-box">
    <div style="display: flex; justify-content: space-between; align-items: center;">
        <div>
            <h1 class="header-title">F&B SmartOrder 🍳</h1>
            <p class="header-subtitle">Gestión Inteligente de Compras y Automatización de Pedidos para Cocina Profesional</p>
        </div>
        <div style="text-align: right;">
            <span style="background: #0284c7; color: white; padding: 0.4rem 0.8rem; border-radius: 8px; font-weight: 700; font-size: 0.85rem;">
                TFC DAM - Chef Edition
            </span>
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

# Banner de estado de la base de datos
if not db_available:
    st.warning("⚠️ MongoDB no está conectado o el contenedor Docker está detenido. La aplicación funcionará en modo simulación.")

# --- SIDEBAR: RESUMEN DE CARRITO Y PEDIDO ---
with st.sidebar:
    st.header("🛒 Tu Pedido Consolidador")
    
    if len(st.session_state.cart) == 0:
        st.info("El carrito está vacío. Busca productos y agrégalos con 1-clic.")
    else:
        total_acumulado = sum(item["total_price"] for item in st.session_state.cart)
        
        # Agrupar por proveedor
        grouped_suppliers = {}
        for item in st.session_state.cart:
            supp_name = item["supplier_name"]
            grouped_suppliers.setdefault(supp_name, []).append(item)

        st.markdown(f"<div class='cart-total'>Total: {total_acumulado:.2f} €</div>", unsafe_allow_html=True)
        st.caption(f"{len(st.session_state.cart)} productos para {len(grouped_suppliers)} proveedores")

        st.divider()

        # Detalle del carrito por proveedor
        for supp_name, items in grouped_suppliers.items():
            subtotal = sum(it["total_price"] for it in items)
            with st.expander(f"📦 **{supp_name}** ({subtotal:.2f} €)", expanded=True):
                for idx, it in enumerate(items):
                    col_a, col_b = st.columns([3, 1])
                    with col_a:
                        off_label = " 📝 (Fuera de Catálogo)" if it.get("is_off_catalog") else ""
                        st.write(f"• **{it['ingredient_name']}**{off_label}")
                        st.caption(f"{it['quantity']} {it['unit']} x {it['unit_price']:.2f}€")
                    with col_b:
                        if st.button("❌", key=f"del_{supp_name}_{idx}"):
                            st.session_state.cart.remove(it)
                            st.rerun()

        st.divider()

        chef_notes = st.text_area("📝 Notas globales para recepción / proveedores:", placeholder="Ej. Entregar antes de las 11:00 AM...")

        if st.button("🚀 Confirmar y Disparar Pedidos", type="primary", use_container_width=True):
            try:
                db = get_database()
                # Construir pedido
                supplier_suborders = []
                for s_name, items in grouped_suppliers.items():
                    s_id = items[0]["supplier_id"]
                    subtotal = sum(it["total_price"] for it in items)
                    supplier_suborders.append({
                        "supplier_id": s_id,
                        "supplier_name": s_name,
                        "supplier_email": f"pedidos@{s_id}.com",
                        "items": items,
                        "subtotal": subtotal
                    })

                new_order = {
                    "created_at": datetime.utcnow(),
                    "status": "sent",
                    "items": st.session_state.cart,
                    "total_amount": total_acumulado,
                    "supplier_suborders": supplier_suborders,
                    "chef_notes": chef_notes
                }

                if db_available:
                    db["pedidos"].insert_one(new_order)
                
                st.session_state.orders_history.insert(0, new_order)
                st.session_state.cart = []
                st.balloons()
                st.success("🎉 ¡Pedidos consolidados creados y enviados a los proveedores con éxito!")
                st.rerun()

            except Exception as e:
                st.error(f"Error procesando el pedido: {e}")

        if st.button("Vaciar Carrito", use_container_width=True):
            st.session_state.cart = []
            st.rerun()

# --- PESTAÑAS PRINCIPALES ---
tab_order, tab_catalog, tab_history, tab_comparison = st.tabs([
    "🛒 Pedido Rápido (Cocina)",
    "📦 Catálogos y Ingesta ETL",
    "📋 Historial de Pedidos",
    "📊 Comparador de Precios"
])

# --- TAB 1: PEDIDO RÁPIDO ---
with tab_order:
    # --- SECCIÓN DESTACADA: ESCÁNER DE LISTA DE NEVERA POR FOTO ---
    with st.expander("📷 Escanear Foto de la Nevera / Pizarra Manuscrita", expanded=False):
        st.markdown("Toma una foto con la cámara de la tableta o sube una imagen con la lista de necesidades escrita a mano por los cocineros.")
        
        col_cam, col_file = st.columns([1, 1])
        camera_photo = None
        uploaded_photo = None
        
        with col_cam:
            camera_photo = st.camera_input("📷 Cámara en directo (Tablet/Móvil)")
        with col_file:
            uploaded_photo = st.file_uploader("📁 O sube una foto de la lista", type=["jpg", "jpeg", "png"])
            
        target_photo = camera_photo or uploaded_photo
        
        if target_photo:
            image_bytes = target_photo.read()
            st.image(image_bytes, caption="Foto seleccionada", width=400)
            
            if st.button("🧠 Reconocer y Mapear Lista de la Foto", type="primary"):
                with st.spinner("Procesando imagen manuscrita y buscando mejores precios..."):
                    from fb_smartorder.extract import extract_image_list
                    raw_extracted = extract_image_list(image_bytes)
                    
                    master_ingredients = list(get_database()["ingredientes_maestros"].find({}, {"_id": 0})) if db_available else []
                    mapped = resolve_entities(raw_extracted, master_ingredients)
                    
                    st.session_state["scanned_fridge_items"] = mapped
                    st.success(f"✅ ¡Se identificaron {len(mapped)} productos en la foto de la nevera!")

        if "scanned_fridge_items" in st.session_state and st.session_state["scanned_fridge_items"]:
            st.markdown("#### 📋 Productos Detectados y Ofertas Sugeridas:")
            scanned_list = st.session_state["scanned_fridge_items"]
            
            items_to_add_batch = []
            for idx, item in enumerate(scanned_list):
                col1, col2, col3, col4 = st.columns([2, 1, 1, 1])
                m_id = item.get("master_ingredient_id")
                raw_name = item.get("raw_name")
                qty = item.get("quantity", 1.0)
                unit = item.get("unit", "kg")
                
                # Buscar mejor oferta para el ingrediente maestro
                best_offer = None
                if db_available and m_id:
                    offers = list(get_database()["productos_brutos"].find({"master_ingredient_id": m_id}, {"_id": 0}))
                    if offers:
                        offers.sort(key=lambda x: x.get("price", 99999.0))
                        best_offer = offers[0]
                
                with col1:
                    st.write(f"• **{raw_name}** (Cantidad: {qty} {unit})")
                    if m_id:
                        st.caption(f"🟢 Mapeado a: `{m_id}` ({item.get('similarity_score')}% similitud)")
                    else:
                        st.caption("🟡 No mapeado a catálogo (se añadirá fuera de catálogo)")
                        
                with col2:
                    supp_name = best_offer["supplier_name"] if best_offer else "Proveedor Genérico"
                    supp_id = best_offer["supplier_id"] if best_offer else "prov_manual"
                    price = best_offer["price"] if best_offer else 0.0
                    st.write(f"**{supp_name}**")
                    st.caption(f"{price:.2f} € / {unit}")
                    
                with col3:
                    total_p = round(qty * price, 2)
                    st.write(f"**{total_p:.2f} €**")
                    
                with col4:
                    items_to_add_batch.append({
                        "master_ingredient_id": m_id,
                        "ingredient_name": raw_name,
                        "quantity": qty,
                        "unit": unit,
                        "unit_price": price,
                        "total_price": total_p,
                        "supplier_id": supp_id,
                        "supplier_name": supp_name,
                        "is_off_catalog": m_id is None
                    })

            if st.button("➕ Añadir TODOS los productos detectados al carrito", type="primary"):
                st.session_state.cart.extend(items_to_add_batch)
                st.session_state["scanned_fridge_items"] = []
                st.toast("✅ ¡Productos de la nevera añadidos al carrito!", icon="🛒")
                st.rerun()

    st.markdown("---")
    st.subheader("🔍 Buscador Unificado de Ingredientes y Precios")

    
    col_search, col_cat = st.columns([3, 1])
    with col_search:
        search_query = st.text_input("Ingrediente o producto a buscar:", placeholder="Ej: Tomate, Solomillo, Aceite...", label_visibility="collapsed")
    with col_cat:
        category_filter = st.selectbox("Categoría:", ["Todas", "Frutas y Verduras", "Carnes", "Pescados y Mariscos", "Lácteos", "Secos y Aceites"], label_visibility="collapsed")

    # Obtener ingredientes maestros
    ingredients = []
    if db_available:
        db = get_database()
        query_master = {}
        if search_query:
            query_master["$or"] = [
                {"name": {"$regex": search_query, "$options": "i"}},
                {"id": {"$regex": search_query, "$options": "i"}},
                {"category": {"$regex": search_query, "$options": "i"}}
            ]
        if category_filter != "Todas":
            query_master["category"] = category_filter

        masters = list(db["ingredientes_maestros"].find(query_master, {"_id": 0}))

        # Si el usuario buscó un término específico (ej: Ricotta, Burrata), buscar también en productos brutos
        if search_query:
            raw_matches = list(db["productos_brutos"].find(
                {"$or": [
                    {"raw_name": {"$regex": search_query, "$options": "i"}},
                    {"clean_name": {"$regex": search_query, "$options": "i"}}
                ]},
                {"_id": 0}
            ))
            for rm in raw_matches:
                m_id = rm.get("master_ingredient_id")
                if m_id and not any(m["id"] == m_id for m in masters):
                    m_doc = db["ingredientes_maestros"].find_one({"id": m_id}, {"_id": 0})
                    if m_doc and (category_filter == "Todas" or m_doc.get("category") == category_filter):
                        masters.append(m_doc)
                elif not m_id:
                    # Crear elemento dinámico en interfaz
                    temp_item = {
                        "id": f"raw_{rm.get('clean_name', 'item')}",
                        "name": rm.get("raw_name", "Producto").title(),
                        "category": rm.get("supplier_name", "Catálogo Proveedores"),
                        "standard_unit": rm.get("unit", "ud"),
                        "offers": [rm]
                    }
                    if not any(x["name"].lower() == temp_item["name"].lower() for x in ingredients):
                        ingredients.append(temp_item)

        # Enriquecer cada ingrediente maestro con sus ofertas ordenadas por menor precio
        for m in masters:
            offers = list(db["productos_brutos"].find({"master_ingredient_id": m["id"]}, {"_id": 0}))
            offers.sort(key=lambda x: x.get("price", 99999.0))
            m["offers"] = offers
            if not any(x["id"] == m["id"] for x in ingredients):
                ingredients.append(m)

    else:
        # Datos simulados de fallback si Mongo no responde
        ingredients = [
            {"id": "ing_tomate_rama", "name": "Tomate Rama", "category": "Frutas y Verduras", "standard_unit": "kg", "offers": [{"supplier_id": "prov_paco_01", "supplier_name": "Frutas Paco S.L.", "price": 1.85, "unit": "kg"}]},
            {"id": "ing_solomillo_ternera", "name": "Solomillo de Ternera", "category": "Carnes", "standard_unit": "kg", "offers": [{"supplier_id": "prov_carnes_gomez_02", "supplier_name": "Carnes Gómez & Hijos", "price": 24.50, "unit": "kg"}]},
            {"id": "ing_aceite_oliva_virgen_extra", "name": "Aceite de Oliva Virgen Extra 5L", "category": "Secos y Aceites", "standard_unit": "ud", "offers": [{"supplier_id": "prov_paco_01", "supplier_name": "Frutas Paco S.L.", "price": 32.00, "unit": "ud"}]}
        ]

    st.markdown("---")

    # Grid de ingredientes
    if not ingredients:
        st.info("No se encontraron ingredientes con los criterios de búsqueda.")
    else:
        for ing in ingredients:
            offers = ing.get("offers", [])
            with st.container():
                st.markdown(f"""
                <div class="product-card">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <div>
                            <span style="font-size: 1.25rem; font-weight: 700;">{ing['name']}</span>
                            <span class="category-badge" style="margin-left: 10px;">{ing['category']}</span>
                        </div>
                        <div>
                            <span style="color: #94a3b8; font-size: 0.9rem;">Unidad estándar: <b>{ing.get('standard_unit', 'kg')}</b></span>
                        </div>
                    </div>
                </div>
                """, unsafe_allow_html=True)

                if not offers:
                    st.caption("⚠️ No hay ofertas cargadas de proveedores para este ingrediente.")
                else:
                    cols_offer = st.columns([2, 1, 1, 1])
                    best_offer = offers[0]
                    
                    with cols_offer[0]:
                        selected_supplier_name = st.selectbox(
                            "Proveedor:",
                            options=[f"{o['supplier_name']} - {o['price']:.2f} €/{o.get('unit','ud')}" for o in offers],
                            key=f"supp_select_{ing['id']}"
                        )
                        # Buscar el objeto de la oferta elegida
                        chosen_idx = [f"{o['supplier_name']} - {o['price']:.2f} €/{o.get('unit','ud')}" for o in offers].index(selected_supplier_name)
                        chosen_offer = offers[chosen_idx]

                    with cols_offer[1]:
                        qty = st.number_input(
                            f"Cantidad ({chosen_offer.get('unit','ud')}):",
                            min_value=0.5,
                            value=1.0,
                            step=0.5,
                            key=f"qty_{ing['id']}"
                        )

                    with cols_offer[2]:
                        st.metric(
                            "Subtotal",
                            f"{qty * chosen_offer['price']:.2f} €",
                            delta=f"{chosen_offer['price']:.2f} €/{chosen_offer.get('unit','ud')}",
                            delta_color="off"
                        )

                    with cols_offer[3]:
                        st.write("")
                        st.write("")
                        if st.button("➕ Añadir al Pedido", key=f"btn_add_{ing['id']}", use_container_width=True):
                            item_to_add = {
                                "master_ingredient_id": ing["id"],
                                "ingredient_name": ing["name"],
                                "quantity": qty,
                                "unit": chosen_offer.get("unit", "ud"),
                                "unit_price": chosen_offer["price"],
                                "total_price": round(qty * chosen_offer["price"], 2),
                                "supplier_id": chosen_offer["supplier_id"],
                                "supplier_name": chosen_offer["supplier_name"],
                                "is_off_catalog": False
                            }
                            st.session_state.cart.append(item_to_add)
                            st.toast(f"✅ ¡{ing['name']} añadido al carrito!", icon="🛒")
                            st.rerun()

                st.write("")

    # --- SECCIÓN: AÑADIR PRODUCTO FUERA DE CATÁLOGO ---
    with st.expander("➕ ¿No encuentras un ingrediente? Añadir producto fuera de catálogo (Fricción Cero)"):
        col_off1, col_off2, col_off3 = st.columns([2, 1, 1])
        with col_off1:
            off_name = st.text_input("Nombre o especificación del ingrediente:", placeholder="Ej. Solomillo de Ciervo / Calamar de Potera")
        with col_off2:
            off_qty = st.number_input("Cantidad estimada:", min_value=1.0, value=1.0)
            off_unit = st.selectbox("Unidad:", ["kg", "ud", "L", "caja", "brik"])
        with col_off3:
            db_suppliers = list(get_database()["proveedores"].find({}, {"_id": 0})) if db_available else []
            supp_options = {s["name"]: s["id"] for s in db_suppliers} if db_suppliers else {"Frutas Paco S.L.": "prov_paco_01"}
            off_supp_name = st.selectbox("Asignar Proveedor:", list(supp_options.keys()))
            off_price = st.number_input("Precio est. (€):", min_value=0.0, value=0.0)

        if st.button("➕ Añadir Nota / Fuera de Catálogo", type="secondary"):
            if off_name:
                item_to_add = {
                    "master_ingredient_id": None,
                    "ingredient_name": off_name,
                    "quantity": off_qty,
                    "unit": off_unit,
                    "unit_price": off_price,
                    "total_price": round(off_qty * off_price, 2),
                    "supplier_id": supp_options.get(off_supp_name, "prov_manual"),
                    "supplier_name": off_supp_name,
                    "is_off_catalog": True
                }
                st.session_state.cart.append(item_to_add)
                st.success(f"Añadido {off_name} fuera de catálogo.")
                st.rerun()

# --- TAB 2: CATÁLOGOS Y ETL INGESTA ---
with tab_catalog:
    st.subheader("📦 Ingesta y Limpieza ETL de Catálogos (PDF / Excel)")
    st.markdown("Sube catálogos desestructurados de proveedores. El pipeline extraerá el texto, limpiará el ruido y emparejará automáticamente los productos mediante **Entity Resolution**.")

    col_up1, col_up2 = st.columns([1, 1])
    
    with col_up1:
        st.markdown("#### 1. Seleccionar Proveedor y Subir Documento")
        db_suppliers = list(get_database()["proveedores"].find({}, {"_id": 0})) if db_available else [
            {"id": "prov_paco_01", "name": "Frutas Paco S.L."},
            {"id": "prov_carnes_gomez_02", "name": "Carnes Gómez & Hijos"},
            {"id": "prov_mariscos_sur_03", "name": "Mariscos del Sur"}
        ]
        
        selected_prov_id = st.selectbox(
            "Seleccionar Proveedor Emisor:",
            options=[s["id"] for s in db_suppliers],
            format_func=lambda x: next((s["name"] for s in db_suppliers if s["id"] == x), x)
        )
        
        uploaded_file = st.file_uploader("Arrastra aquí el catálogo (PDF o Excel .xlsx):", type=["pdf", "xlsx", "xls"])
        
        if uploaded_file and st.button("⚡ Ejecutar Pipeline ETL", type="primary"):
            with st.spinner("Procesando documento en MongoDB y ejecutando algoritmo de coincidencia..."):
                file_bytes = uploaded_file.read()
                filename = uploaded_file.name
                ext = os.path.splitext(filename)[1].lower()

                # Guardar en GridFS si la DB está disponible
                if db_available:
                    grid_id = save_catalog_file(filename, file_bytes, selected_prov_id)
                
                # Extracción
                import tempfile
                with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
                    tmp.write(file_bytes)
                    tmp_path = tmp.name

                try:
                    if ext in [".xlsx", ".xls"]:
                        raw_extracted = extract_excel(tmp_path)
                    else:
                        raw_extracted = extract_pdf(tmp_path)
                finally:
                    if os.path.exists(tmp_path):
                        os.remove(tmp_path)

                # Transformación
                master_ingredients = list(get_database()["ingredientes_maestros"].find({}, {"_id": 0})) if db_available else []
                transformed = resolve_entities(raw_extracted, master_ingredients)

                # Carga
                if db_available:
                    load_raw_products(selected_prov_id, transformed)

                st.success(f"✅ ¡Procesamiento finalizado! Se extrajeron {len(transformed)} productos.")
                st.session_state["last_extracted"] = transformed

    with col_up2:
        st.markdown("#### 2. Resultado de la Transformación y Mapeo")
        if "last_extracted" in st.session_state:
            df_last = pd.DataFrame(st.session_state["last_extracted"])
            st.dataframe(df_last[["raw_name", "clean_name", "price", "unit", "master_ingredient_id", "similarity_score"]], use_container_width=True)
        else:
            st.info("Suba un catálogo para ver la tabla de Entity Resolution en tiempo real.")

    st.divider()

    st.markdown("### 🏬 Proveedores Registrados en el Sistema")
    if db_available:
        suppliers_df = pd.DataFrame(list(get_database()["proveedores"].find({}, {"_id": 0})))
        st.dataframe(suppliers_df, use_container_width=True)

# --- TAB 3: HISTORIAL DE PEDIDOS ---
with tab_history:
    st.subheader("📋 Historial y Estado de Pedidos Enviados")
    
    orders = []
    if db_available:
        orders = list(get_database()["pedidos"].find().sort("created_at", -1))
    
    # Combinar con los creados en sesión
    all_orders = st.session_state.orders_history + orders
    
    if not all_orders:
        st.info("No hay pedidos registrados en el historial.")
    else:
        for idx, ord_item in enumerate(all_orders):
            date_str = ord_item.get("created_at")
            if isinstance(date_str, datetime):
                date_str = date_str.strftime("%Y-%m-%d %H:%M:%S")
            
            status = ord_item.get("status", "sent").upper()
            total = ord_item.get("total_amount", 0.0)

            with st.expander(f"📦 **Pedido #{idx+1}** - Fecha: {date_str} - Estado: **{status}** - Total: **{total:.2f} €**"):
                st.write(f"**Notas del Chef:** {ord_item.get('chef_notes') or 'Sin notas'}")
                st.markdown("#### Desglose por Proveedor:")
                
                for sub in ord_item.get("supplier_suborders", []):
                    st.markdown(f"**Proveedor:** {sub['supplier_name']} ({sub.get('supplier_email','')}) - **Subtotal:** {sub['subtotal']:.2f} €")
                    sub_items = pd.DataFrame(sub["items"])
                    if not sub_items.empty and "ingredient_name" in sub_items.columns:
                        st.dataframe(sub_items[["ingredient_name", "quantity", "unit", "unit_price", "total_price"]], use_container_width=True)

# --- TAB 4: COMPARADOR DE PRECIOS ---
with tab_comparison:
    st.subheader("📊 Comparativa en Tiempo Real de Ofertas por Proveedor")
    
    if db_available:
        raw_all = list(get_database()["productos_brutos"].find({}, {"_id": 0}))
        if raw_all:
            df_raw = pd.DataFrame(raw_all)
            st.markdown("#### Matriz de Productos Brutos vs Proveedores")
            st.dataframe(df_raw[["supplier_name", "raw_name", "clean_name", "price", "unit", "master_ingredient_id", "similarity_score"]], use_container_width=True)
            
            # Gráfico comparativo si hay suficientes productos
            if not df_raw.empty:
                st.markdown("#### Distribución de Precios por Ingrediente")
                st.bar_chart(df_raw, x="clean_name", y="price", color="supplier_name")
        else:
            st.info("No hay productos brutos registrados en MongoDB todavía. Suba catálogos en la pestaña 'Catálogos y Ingesta ETL'.")
    else:
        st.info("Conecte MongoDB para visualizar la analítica de precios.")
