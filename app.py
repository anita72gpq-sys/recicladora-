from datetime import datetime, timedelta
import os
import sqlite3
import base64
import pandas as pd

try:
  from reportlab.lib.pagesizes import letter
  from reportlab.pdfgen import canvas
  PDF_DISPONIBLE = True
except ImportError:
  PDF_DISPONIBLE = False

import streamlit as st

# ---------------------------------------------------------
# CONFIGURACIÓN DE PÁGINA Y TEMA VISUAL (VERDE ECOLÓGICO)
# ---------------------------------------------------------
st.set_page_config(
    page_title="Chatarrería Don Kilo - ERP",
    page_icon="♻️",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
    <style>
    .stApp { background-color: #F4F8F5; }
    .header-box {
        background: linear-gradient(135deg, #1E4D2B 0%, #2E7D32 100%);
        color: white; padding: 20px; border-radius: 12px;
        text-align: center; margin-bottom: 25px;
        box-shadow: 0px 4px 10px rgba(0, 0, 0, 0.15);
    }
    .header-box h1 { color: #FFFFFF !important; margin: 0; font-weight: 800; }
    .header-box p { color: #E8F5E9 !important; margin: 5px 0 0 0; font-size: 15px; }

    div.stButton > button:first-child {
        background-color: #2E7D32 !important; color: white !important;
        font-weight: bold !important; border-radius: 8px !important;
        border: none !important; padding: 8px 16px !important;
    }
    div.stButton > button:first-child:hover { background-color: #1B5E20 !important; }

    .total-card {
        background-color: #E8F5E9; border-left: 6px solid #2E7D32;
        padding: 15px; border-radius: 8px; text-align: center; margin-top: 10px;
    }
    .total-card h2 { color: #1B5E20; margin: 0; font-size: 32px; }
    </style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------
# BASE DE DATOS Y CONEXIÓN ROBUSTA
# ---------------------------------------------------------
def obtener_conexion():
    return sqlite3.connect("recicladora.db", check_same_thread=False)

def inicializar_bd():
    conexion = obtener_conexion()
    cursor = conexion.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS config_empresa (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT,
            direccion TEXT,
            telefono TEXT
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS clientes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT UNIQUE NOT NULL,
            telefono TEXT,
            tipo TEXT DEFAULT 'Proveedor'
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS materiales (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            precio_compra REAL NOT NULL,
            precio_venta REAL DEFAULT 0.0,
            stock_kilos REAL DEFAULT 0.0
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS compras (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha TEXT NOT NULL,
            cliente TEXT NOT NULL,
            total_pagado REAL NOT NULL,
            turno TEXT DEFAULT 'Turno 1'
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS detalle_compra (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            compra_id INTEGER,
            material_id INTEGER,
            kilos REAL NOT NULL,
            subtotal REAL NOT NULL
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS ventas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha TEXT NOT NULL,
            comprador TEXT NOT NULL,
            total_cobrado REAL NOT NULL,
            turno TEXT DEFAULT 'Turno 1'
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS detalle_venta (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            venta_id INTEGER,
            material_id INTEGER,
            kilos REAL NOT NULL,
            subtotal REAL NOT NULL
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS gastos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha TEXT NOT NULL,
            categoria TEXT NOT NULL,
            descripcion TEXT,
            monto REAL NOT NULL,
            turno TEXT DEFAULT 'Turno 1'
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS movimientos_caja (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha TEXT NOT NULL,
            tipo TEXT NOT NULL,
            monto REAL NOT NULL,
            motivo TEXT,
            turno TEXT DEFAULT 'Turno 1'
        )
    ''')
    
    cursor.execute("SELECT COUNT(*) FROM config_empresa")
    if cursor.fetchone()[0] == 0:
        cursor.execute("INSERT INTO config_empresa (nombre, direccion, telefono) VALUES (?, ?, ?)",
                       ("Chatarrería Don Kilo", "Calle 31 lote 772 casa 182 fracc. Villa Jardin, Mérida, Yucatán", "984-533-8681"))
        
    cursor.execute("SELECT COUNT(*) FROM materiales")
    if cursor.fetchone()[0] == 0:
        materiales_iniciales = [
            ('Chatarra', 4.50, 6.00, 0.0),
            ('Cobre', 140.00, 160.00, 0.0),
            ('Bronce', 90.00, 105.00, 0.0),
            ('Aluminio Latas', 28.00, 33.00, 0.0),
            ('Aluminio General', 22.00, 27.00, 0.0)
        ]
        cursor.executemany("INSERT INTO materiales (nombre, precio_compra, precio_venta, stock_kilos) VALUES (?, ?, ?, ?)", materiales_iniciales)
        
    conexion.commit()
    conexion.close()

inicializar_bd()

if "carrito_compras" not in st.session_state:
    st.session_state.carrito_compras = []

conexion = obtener_conexion()
cursor = conexion.cursor()

cursor.execute("SELECT nombre, direccion, telefono FROM config_empresa LIMIT 1")
empresa_info = cursor.fetchone()
emp_nombre = empresa_info[0] if empresa_info else "Chatarrería Don Kilo"
emp_direccion = empresa_info[1] if empresa_info else "Mérida, Yucatán"
emp_telefono = empresa_info[2] if empresa_info else "984-533-8681"

st.markdown(f"""
    <div class="header-box">
        <h1>♻️ {emp_nombre}</h1>
        <p>📍 {emp_direccion} | 📞 Cel: {emp_telefono}</p>
    </div>
""", unsafe_allow_html=True)

menu = st.sidebar.selectbox("📋 Menú Principal", [
    "📝 Registrar Compra (Báscula)",
    "📦 Ver Inventario y Precios",
    "📤 Registrar Venta (Salida)",
    "💵 Control de Caja (Fondo / Entradas)",
    "✂️ Corte de Caja por Turno y Día",
    "💸 Registrar y Administrar Gastos",
    "📊 Reportes (Diario, Semanal, Mensual, Anual)",
    "⚙️ Configuración / Precios / Empresa"
])

def obtener_ruta_carpeta_tickets():
    carpeta = os.path.abspath("Tickets_Recicladora")
    os.makedirs(carpeta, exist_ok=True)
    return carpeta

def mostrar_visor_pdf(bytes_pdf, titulo_btn="📥 DESCARGAR / IMPRIMIR PDF"):
    if bytes_pdf:
        base64_pdf = base64.b64encode(bytes_pdf).decode('utf-8')
        pdf_display = f'<iframe src="data:application/pdf;base64,{base64_pdf}" width="100%" height="500px" type="application/pdf"></iframe>'
        st.markdown("---")
        st.subheader("👀 Vista Previa en Pantalla")
        st.markdown(pdf_display, unsafe_allow_html=True)
        st.write("")
        st.download_button(
            label=f"🖨️ {titulo_btn}",
            data=bytes_pdf,
            file_name=f"Documento_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
            mime="application/pdf",
            type="primary"
        )

def generar_pdf_ticket(nombre_emp, dir_emp, tel_emp, folio, fecha, turno, cliente, carrito, total):
    if not PDF_DISPONIBLE:
        return None
    from io import BytesIO
    buffer = BytesIO()
    p = canvas.Canvas(buffer, pagesize=letter)
    p.setFont("Helvetica-Bold", 14)
    p.drawString(50, 750, f"♻️ {nombre_emp}")
    p.setFont("Helvetica", 9)
    p.drawString(50, 735, f"{dir_emp} | Cel: {tel_emp}")
    p.line(50, 725, 500, 725)
    
    p.setFont("Helvetica-Bold", 11)
    p.drawString(50, 705, f"TICKET DE COMPRA #{folio}")
    p.setFont("Helvetica", 10)
    p.drawString(50, 685, f"Fecha: {fecha} | Turno: {turno}")
    p.drawString(50, 665, f"Proveedor / Cliente: {cliente}")
    p.line(50, 655, 500, 655)
    
    y = 635
    p.setFont("Helvetica-Bold", 9)
    p.drawString(50, y, "MATERIAL")
    p.drawString(220, y, "KILOS (KG)")
    p.drawString(320, y, "PRECIO/KG")
    p.drawString(420, y, "SUBTOTAL")
    y -= 15
    
    p.setFont("Helvetica", 9)
    for item in carrito:
        p.drawString(50, y, str(item['material']))
        p.drawString(220, y, f"{item['kilos']:.2f} kg")
        p.drawString(320, y, f"${item['precio']:,.2f}")
        p.drawString(420, y, f"${item['subtotal']:,.2f}")
        y -= 18
        if y < 100:
            p.showPage()
            y = 750
            
    p.line(50, y - 5, 500, y - 5)
    y -= 25
    p.setFont("Helvetica-Bold", 12)
    p.drawString(50, y, f"TOTAL A PAGAR: ${total:,.2f} MXN")
    
    p.showPage()
    p.save()
    buffer.seek(0)
    return buffer.getvalue()

def generar_pdf_corte_caja(nombre_emp, dir_emp, tel_emp, fecha_str, turno_str, efectivo, ingresos, ventas, compras, gastos):
    if not PDF_DISPONIBLE:
        return None
    from io import BytesIO
    buffer = BytesIO()
    p = canvas.Canvas(buffer, pagesize=letter)
    p.setFont("Helvetica-Bold", 16)
    p.drawString(50, 750, f"♻️ {nombre_emp}")
    p.setFont("Helvetica", 10)
    p.drawString(50, 735, f"{dir_emp} | Tel: {tel_emp}")
    p.line(50, 725, 550, 725)
    
    p.setFont("Helvetica-Bold", 14)
    p.drawString(50, 695, f"CORTE DE CAJA - {fecha_str}")
    p.setFont("Helvetica", 11)
    p.drawString(50, 675, f"Filtro Turno: {turno_str}")
    
    p.drawString(50, 640, f"Fondo e Inyecciones a Caja: ${ingresos:,.2f} MXN")
    p.drawString(50, 620, f"Ventas Realizadas:           ${ventas:,.2f} MXN")
    p.drawString(50, 600, f"(-) Compras en Material:     ${compras:,.2f} MXN")
    p.drawString(50, 580, f"(-) Gastos Operativos:        ${gastos:,.2f} MXN")
    
    p.line(50, 565, 550, 565)
    p.setFont("Helvetica-Bold", 14)
    p.drawString(50, 540, f"EFECTIVO RESTANTE EN CAJA: ${efectivo:,.2f} MXN")
    p.line(50, 525, 550, 525)
    
    p.showPage()
    p.save()
    buffer.seek(0)
    return buffer.getvalue()

# ---------------------------------------------------------
# OPCIÓN 1: BÁSCULA DE COMPRA
# ---------------------------------------------------------
if menu == "📝 Registrar Compra (Báscula)":
    st.subheader("🛒 Registro Rápido de Compra con Atajos y Cambio de Precio")
    
    col_t1, col_t2 = st.columns([2, 2])
    with col_t1:
        turno_actual = st.selectbox("⏱️ Turno Actual:", ["Turno 1 (Mañana)", "Turno 2 (Tarde)", "Turno Completo"])
        
    cursor.execute("SELECT nombre FROM clientes ORDER BY nombre ASC")
    lista_clientes = [c[0] for c in cursor.fetchall()]
    if "Público General" not in lista_clientes:
        lista_clientes.insert(0, "Público General")
        
    col_cli1, col_cli2 = st.columns([3, 1])
    with col_cli1:
        cliente_sel = st.selectbox("👤 Proveedor / Cliente:", lista_clientes)
    with col_cli2:
        with st.popover("➕ Agregar Cliente"):
            cli_nom = st.text_input("Nombre Completo:")
            cli_tel = st.text_input("Teléfono Celular:")
            if st.button("Guardar Cliente"):
                if cli_nom:
                    try:
                        cursor.execute("INSERT INTO clientes (nombre, telefono) VALUES (?, ?)", (cli_nom, cli_tel))
                        conexion.commit()
                        st.success("¡Cliente guardado!")
                        st.rerun()
                    except Exception:
                        st.error("El cliente ya existe.")

    st.markdown("---")
    st.write("### ⚡ Atajos de Compras Rápidas (Clic para rellenar)")
    
    cursor.execute("SELECT id, nombre, precio_compra FROM materiales ORDER BY nombre ASC")
    mats_db = cursor.fetchall()
    dict_mats = {m[1]: (m[0], m[2]) for m in mats_db}
    
    cols_atajos = st.columns(len(dict_mats) if len(dict_mats) > 0 else 1)
    i = 0
    for mat_n, (m_id, m_p) in dict_mats.items():
        with cols_atajos[i % len(cols_atajos)]:
            if st.button(f"📦 {mat_n}\n(${m_p:,.2f})", key=f"atajo_{m_id}"):
                st.session_state.atj_mat = mat_n
                st.session_state.atj_precio = float(m_p)
        i += 1

    st.markdown("---")
    st.write("### ➕ Agregar Material a la Báscula")
    
    mat_def_sel = st.session_state.get("atj_mat", list(dict_mats.keys())[0] if dict_mats else "")
    mat_nom = st.selectbox("Material:", list(dict_mats.keys()), index=list(dict_mats.keys()).index(mat_def_sel) if mat_def_sel in dict_mats else 0)
    mat_id, mat_p_db = dict_mats[mat_nom]
    
    precio_inicial_sugerido = st.session_state.get("atj_precio", float(mat_p_db))
    
    col_m2, col_m3 = st.columns(2)
    with col_m2:
        kilos = st.number_input("Kilos (Kg):", min_value=0.0, step=0.5, format="%.2f")
    with col_m3:
        # Permite cambiar el precio en pantalla y actualizarlo también de inmediato en el inventario
        precio = st.number_input("Precio $/Kg (Modificable):", value=float(precio_inicial_sugerido), step=0.5, format="%.2f")
        
    subtotal = kilos * precio
    st.info(f"Subtotal calculado: **${subtotal:,.2f} MXN**")
    
    col_b1, col_b2 = st.columns([3, 1])
    with col_b1:
        if st.button("📥 Agregar a la Lista del Ticket", type="primary"):
            if kilos <= 0:
                st.warning("Ingrese una cantidad de kilos mayor a 0.")
            else:
                # Actualiza automáticamente el precio en el inventario si el usuario lo modificó en pantalla
                cursor.execute("UPDATE materiales SET precio_compra = ? WHERE id = ?", (precio, mat_id))
                conexion.commit()

                st.session_state.carrito_compras.append({
                    "material_id": mat_id,
                    "material": mat_nom,
                    "kilos": kilos,
                    "precio": precio,
                    "subtotal": subtotal
                })
                if "atj_mat" in st.session_state:
                    del st.session_state.atj_mat
                st.success(f"Agregado {kilos} kg de {mat_nom} a ${precio}/kg (Precio actualizado en inventario)")
                st.rerun()
    with col_b2:
        if st.button("🔄 Limpiar Ticket"):
            st.session_state.carrito_compras = []
            if "atj_mat" in st.session_state:
                del st.session_state.atj_mat
            st.rerun()

    st.markdown("---")
    st.write("### 📄 Contenido Actual del Ticket:")
    
    if st.session_state.carrito_compras:
        df_car = pd.DataFrame(st.session_state.carrito_compras)
        st.dataframe(df_car[["material", "kilos", "precio", "subtotal"]].rename(columns={
            "material": "Material", "kilos": "Kilos (Kg)", "precio": "Precio $/Kg", "subtotal": "Subtotal ($)"
        }), use_container_width=True)
        
        tot_ticket = sum(i["subtotal"] for i in st.session_state.carrito_compras)
        
        st.markdown(f"""
        <div class="total-card">
            <p style="margin:0; font-weight:bold;">TOTAL A PAGAR</p>
            <h2>${tot_ticket:,.2f} MXN</h2>
        </div>
        """, unsafe_allow_html=True)
        
        st.write("")
        if st.button("✅ FINALIZAR Y GUARDAR TICKET EN PDF", type="primary", use_container_width=True):
            f_act = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            cursor.execute("INSERT INTO compras (fecha, cliente, total_pagado, turno) VALUES (?, ?, ?, ?)",
                           (f_act, cliente_sel, tot_ticket, turno_actual))
            c_id = cursor.lastrowid
            
            for item in st.session_state.carrito_compras:
                cursor.execute("INSERT INTO detalle_compra (compra_id, material_id, kilos, subtotal) VALUES (?, ?, ?, ?)",
                               (c_id, item['material_id'], item['kilos'], item['subtotal']))
                cursor.execute("UPDATE materiales SET stock_kilos = stock_kilos + ? WHERE id = ?",
                               (item['kilos'], item['material_id']))
            
            conexion.commit()
            
            bytes_pdf = generar_pdf_ticket(emp_nombre, emp_direccion, emp_telefono, c_id, f_act, turno_actual, cliente_sel, st.session_state.carrito_compras, tot_ticket)
            
            if bytes_pdf:
                carpeta_tk = obtener_ruta_carpeta_tickets()
                nombre_archivo = os.path.join(carpeta_tk, f"Ticket_Compra_{c_id}.pdf")
                with open(nombre_archivo, "wb") as f_pdf:
                    f_pdf.write(bytes_pdf)
                st.success(f"¡Compra #{c_id} registrada con éxito! Guardado en la carpeta 'Tickets_Recicladora'.")
                
                st.session_state.ultimo_pdf_compra = bytes_pdf
            
            st.session_state.carrito_compras = []
            st.rerun()

    if "ultimo_pdf_compra" in st.session_state and st.session_state.ultimo_pdf_compra:
        mostrar_visor_pdf(st.session_state.ultimo_pdf_compra, "DESCARGAR / IMPRIMIR TICKET DE COMPRA")

# ---------------------------------------------------------
# OPCIÓN 2: VER INVENTARIO Y PRECIOS
# ---------------------------------------------------------
elif menu == "📦 Ver Inventario y Precios":
    st.subheader("📦 Inventario Actual y Precios de Compra")
    cursor.execute("SELECT id, nombre, precio_compra, precio_venta, stock_kilos FROM materiales")
    mats = cursor.fetchall()
    df_inv = pd.DataFrame(mats, columns=["ID", "Material", "Precio Compra ($)", "Precio Venta ($)", "Stock (Kg)"])
    st.dataframe(df_inv, use_container_width=True)

# ---------------------------------------------------------
# OPCIÓN 3: REGISTRAR VENTA
# ---------------------------------------------------------
elif menu == "📤 Registrar Venta (Salida)":
    st.subheader("📤 Registrar Venta de Material")
    turno_v = st.selectbox("⏱️ Turno:", ["Turno 1 (Mañana)", "Turno 2 (Tarde)", "Turno Completo"])
    comprador = st.text_input("Fundidora / Comprador Final:")
    
    cursor.execute("SELECT id, nombre, precio_venta, stock_kilos FROM materiales")
    mats_v = cursor.fetchall()
    
    dict_v = {}
    for m in mats_v:
        col1, col2, col3 = st.columns(3)
        with col1:
            st.write(f"**{m[1]}** (Disp: {m[3]:.1f} kg)")
        with col2:
            kv = st.number_input(f"Kg a vender de {m[1]}", min_value=0.0, max_value=float(m[3]), key=f"v_{m[0]}")
        with col3:
            st.write(f"Subtotal: **${kv * m[2]:,.2f}**")
        if kv > 0:
            dict_v[m[0]] = (m[1], kv, m[2], kv * m[2])
            
    if st.button("Finalizar Venta", type="primary"):
        if not comprador:
            st.error("Ingrese el comprador.")
        elif not dict_v:
            st.error("Seleccione al menos un producto.")
        else:
            f_act = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            tot_v = sum(x[3] for x in dict_v.values())
            cursor.execute("INSERT INTO ventas (fecha, comprador, total_cobrado, turno) VALUES (?, ?, ?, ?)",
                           (f_act, comprador, tot_v, turno_v))
            v_id = cursor.lastrowid
            
            for mid, data in dict_v.items():
                cursor.execute("INSERT INTO detalle_venta (venta_id, material_id, kilos, subtotal) VALUES (?, ?, ?, ?)",
                               (v_id, mid, data[1], data[3]))
                cursor.execute("UPDATE materiales SET stock_kilos = stock_kilos - ? WHERE id = ?",
                               (data[1], mid))
            
            conexion.commit()
            st.success(f"¡Venta #{v_id} registrada por ${tot_v:,.2f}!")

# ---------------------------------------------------------
# OPCIÓN 4: CONTROL DE CAJA
# ---------------------------------------------------------
elif menu == "💵 Control de Caja (Fondo / Entradas)":
    st.subheader("💵 Fondo e Inyecciones de Caja")
    
    with st.form("form_caja_in"):
        turno_c = st.selectbox("Turno:", ["Turno 1 (Mañana)", "Turno 2 (Tarde)", "Turno Completo"])
        tipo_m = st.selectbox("Tipo:", ["Fondo Inicial de Caja", "Inyección Extra de Efectivo"])
        monto_m = st.number_input("Monto ($):", min_value=0.0, step=100.0)
        motivo_m = st.text_input("Motivo:")
        
        if st.form_submit_button("Guardar en Caja"):
            if monto_m > 0:
                f_act = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                cursor.execute("INSERT INTO movimientos_caja (fecha, tipo, monto, motivo, turno) VALUES (?, ?, ?, ?, ?)",
                               (f_act, tipo_m, monto_m, motivo_m, turno_c))
                conexion.commit()
                st.success(f"Se ingresaron ${monto_m:,.2f} a caja en [{turno_c}].")
                st.rerun()

    cursor.execute("SELECT id, fecha, turno, tipo, monto, motivo FROM movimientos_caja ORDER BY id DESC")
    df_caja_movs = pd.DataFrame(cursor.fetchall(), columns=["ID", "Fecha", "Turno", "Tipo", "Monto", "Motivo"])
    st.dataframe(df_caja_movs, use_container_width=True)

# ---------------------------------------------------------
# OPCIÓN 5: CORTE DE CAJA POR TURNO Y DÍA
# ---------------------------------------------------------
elif menu == "✂️ Corte de Caja por Turno y Día":
    st.subheader("✂️ Arqueo y Corte de Caja en PDF")
    
    col_f1, col_f2 = st.columns(2)
    with col_f1:
        f_corte = st.date_input("Fecha del Corte:", datetime.now())
    with col_f2:
        filtro_turno = st.selectbox("Filtrar por Turno:", ["Todos los Turnos (Día Completo)", "Turno 1 (Mañana)", "Turno 2 (Tarde)"])
        
    f_i = f_corte.strftime("%Y-%m-%d 00:00:00")
    f_f = f_corte.strftime("%Y-%m-%d 23:59:59")
    
    cond_turno = ""
    params_t = [f_i, f_f]
    if filtro_turno != "Todos los Turnos (Día Completo)":
        cond_turno = " AND turno = ?"
        params_t.append(filtro_turno)
        
    cursor.execute(f"SELECT SUM(monto) FROM movimientos_caja WHERE fecha >= ? AND fecha <= ?{cond_turno}", params_t)
    tot_ingresado = cursor.fetchone()[0] or 0.0
    
    cursor.execute(f"SELECT SUM(total_cobrado) FROM ventas WHERE fecha >= ? AND fecha <= ?{cond_turno}", params_t)
    tot_ventas = cursor.fetchone()[0] or 0.0
    
    cursor.execute(f"SELECT SUM(total_pagado) FROM compras WHERE fecha >= ? AND fecha <= ?{cond_turno}", params_t)
    tot_compras = cursor.fetchone()[0] or 0.0
    
    cursor.execute(f"SELECT SUM(monto) FROM gastos WHERE fecha >= ? AND fecha <= ?{cond_turno}", params_t)
    tot_gastos = cursor.fetchone()[0] or 0.0
    
    efectivo_restante = (tot_ingresado + tot_ventas) - (tot_compras + tot_gastos)
    
    st.markdown(f"""
    <div class="total-card">
        <p style="margin:0; font-weight:bold;">EFECTIVO RESTANTE EN CAJA ({filtro_turno.upper()})</p>
        <h2>${efectivo_restante:,.2f} MXN</h2>
    </div>
    """, unsafe_allow_html=True)
    
    st.write("")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Fondo/Inyecciones", f"${tot_ingresado:,.2f}")
    col2.metric("Ventas Cobradas", f"${tot_ventas:,.2f}")
    col3.metric("Comprado en Material", f"${tot_compras:,.2f}")
    col4.metric("Gastos Generales", f"${tot_gastos:,.2f}")
    
    if PDF_DISPONIBLE:
        bytes_pdf_corte = generar_pdf_corte_caja(emp_nombre, emp_direccion, emp_telefono, str(f_corte), filtro_turno, efectivo_restante, tot_ingresado, tot_ventas, tot_compras, tot_gastos)
        if bytes_pdf_corte:
            carpeta_tk = obtener_ruta_carpeta_tickets()
            nombre_archivo_corte = os.path.join(carpeta_tk, f"Corte_Caja_{f_corte}_{filtro_turno}.pdf")
            with open(nombre_archivo_corte, "wb") as f_pdf:
                f_pdf.write(bytes_pdf_corte)
                
            mostrar_visor_pdf(bytes_pdf_corte, "DESCARGAR / IMPRIMIR CORTE DE CAJA")

# ---------------------------------------------------------
# OPCIÓN 6: GASTOS
# ---------------------------------------------------------
elif menu == "💸 Registrar y Administrar Gastos":
    st.subheader("💸 Registro de Gastos")
    with st.form("fgastos"):
        turno_g = st.selectbox("Turno:", ["Turno 1 (Mañana)", "Turno 2 (Tarde)", "Turno Completo"])
        cat = st.selectbox("Categoría:", ["Sueldo", "Gasolina", "Mantenimiento", "Luz", "Agua", "Otros"])
        mon = st.number_input("Monto ($):", min_value=0.0)
        des = st.text_input("Descripción:")
        
        if st.form_submit_button("Guardar Gasto"):
            if mon > 0:
                cursor.execute("INSERT INTO gastos (fecha, categoria, descripcion, monto, turno) VALUES (?, ?, ?, ?, ?)",
                               (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), cat, des, mon, turno_g))
                conexion.commit()
                st.success("Gasto registrado.")
                st.rerun()

    cursor.execute("SELECT id, fecha, turno, categoria, descripcion, monto FROM gastos ORDER BY id DESC")
    df_g = pd.DataFrame(cursor.fetchall(), columns=["ID", "Fecha", "Turno", "Categoría", "Descripción", "Monto"])
    st.dataframe(df_g, use_container_width=True)

# ---------------------------------------------------------
# OPCIÓN 7: REPORTES
# ---------------------------------------------------------
elif menu == "📊 Reportes (Diario, Semanal, Mensual, Anual)":
    st.subheader("📊 Reportes Financieros en PDF")
    
    periodo = st.radio("Seleccione el período de consulta:", ["Diario (Hoy)", "Semanal", "Mensual", "Anual", "Personalizado"], horizontal=True)
    
    ahora = datetime.now()
    if periodo == "Diario (Hoy)":
        f_inicio = ahora.strftime("%Y-%m-%d 00:00:00")
        f_fin = ahora.strftime("%Y-%m-%d 23:59:59")
    elif periodo == "Semanal":
        f_inicio = (ahora - timedelta(days=7)).strftime("%Y-%m-%d 00:00:00")
        f_fin = ahora.strftime("%Y-%m-%d 23:59:59")
    elif periodo == "Mensual":
        f_inicio = ahora.strftime("%Y-%m-01 00:00:00")
        f_fin = ahora.strftime("%Y-%m-%d 23:59:59")
    elif periodo == "Anual":
        f_inicio = ahora.strftime("%Y-01-01 00:00:00")
        f_fin = ahora.strftime("%Y-%m-%d 23:59:59")
    else:
        col_p1, col_p2 = st.columns(2)
        with col_p1:
            d_i = st.date_input("Fecha Inicio:", ahora - timedelta(days=30))
        with col_p2:
            d_f = st.date_input("Fecha Fin:", ahora)
        f_inicio = d_i.strftime("%Y-%m-%d 00:00:00")
        f_fin = d_f.strftime("%Y-%m-%d 23:59:59")
        
    cursor.execute("SELECT COUNT(*), SUM(total
