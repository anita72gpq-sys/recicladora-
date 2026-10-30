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
import streamlit.components.v1 as components

# ---------------------------------------------------------
# CONFIGURACIÓN DE PÁGINA Y TEMA VISUAL (ESTILO VENTANA PRINCIPAL)
# ---------------------------------------------------------
st.set_page_config(
    page_title="Chatarrería Don Kilo - ERP",
    page_icon="♻️",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
    <style>
    .stApp { background-color: #E8F0EC; }
    
    .main-window-box {
        background-color: #FFFFFF;
        border: 2px solid #2E7D32;
        border-radius: 12px;
        padding: 25px;
        box-shadow: 0px 6px 15px rgba(46, 125, 50, 0.15);
        margin-bottom: 20px;
    }

    .win-frame {
        border: 1px solid #C8E6C9;
        background-color: #F9FBF9;
        padding: 15px;
        border-radius: 8px;
        margin-bottom: 15px;
    }
    .win-frame-title {
        font-weight: bold;
        color: #1B5E20;
        font-size: 14px;
        margin-bottom: 10px;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        border-bottom: 2px solid #A5D6A7;
        padding-bottom: 5px;
    }

    .header-box {
        background: linear-gradient(135deg, #1E4D2B 0%, #2E7D32 100%);
        color: white; padding: 18px; border-radius: 8px;
        text-align: center; margin-bottom: 20px;
        box-shadow: 0px 4px 8px rgba(0, 0, 0, 0.15);
    }
    .header-box h1 { color: #FFFFFF !important; margin: 0; font-size: 24px; font-weight: bold; }
    .header-box p { color: #E8F5E9 !important; margin: 5px 0 0 0; font-size: 13px; }

    div.stButton > button:first-child {
        background-color: #2E7D32 !important; 
        color: #FFFFFF !important;
        font-weight: bold !important; 
        border-radius: 6px !important;
        border: none !important; 
        padding: 8px 16px !important;
    }
    div.stButton > button:first-child:hover { 
        background-color: #1B5E20 !important; 
    }
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

if "texto_ticket_pantalla" not in st.session_state:
    st.session_state.texto_ticket_pantalla = ""

if "input_kilos_key" not in st.session_state:
    st.session_state.input_kilos_key = 0

if "reset_form_trigger" not in st.session_state:
    st.session_state.reset_form_trigger = 0

conexion = obtener_conexion()
cursor = conexion.cursor()

cursor.execute("SELECT nombre, direccion, telefono FROM config_empresa LIMIT 1")
empresa_info = cursor.fetchone()
emp_nombre = empresa_info[0] if empresa_info else "Chatarrería Don Kilo"
emp_direccion = empresa_info[1] if empresa_info else "Mérida, Yucatán"
emp_telefono = empresa_info[2] if empresa_info else "984-533-8681"

st.markdown(f"""
    <div class="header-box">
        <h1>🖥️ SISTEMA DE CONTROL - {emp_nombre}</h1>
        <p>📍 {emp_direccion} | 📞 Cel: {emp_telefono}</p>
    </div>
""", unsafe_allow_html=True)

menu = st.sidebar.selectbox("📋 Menú Principal", [
    "📝 Registro de Compra (Báscula)",
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

def mostrar_boton_imprimir_termico(texto_ticket):
    html_code = f"""
    <div style="text-align: left; margin: 10px 0;">
        <button onclick="
            var ventana = window.open('', '_print', 'height=600,width=400');
            ventana.document.write('<html><head><title>Imprimir Ticket</title>');
            ventana.document.write('<style>body {{ font-family: monospace; white-space: pre; font-size: 14px; font-weight: bold; margin: 10px; }}</style>');
            ventana.document.write('</head><body>');
            ventana.document.write(`{texto_ticket}`);
            ventana.document.write('</body></html>');
            ventana.document.close();
            ventana.focus();
            setTimeout(function() {{ ventana.print(); ventana.close(); }}, 250);
        " style="
            background-color: #2E7D32;
            color: #FFFFFF;
            padding: 10px 20px;
            font-size: 15px;
            font-weight: bold;
            border: none;
            border-radius: 6px;
            cursor: pointer;
        ">🖨️ Mandar a Imprimir Ticket</button>
    </div>
    """
    components.html(html_code, height=60)

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

def generar_pdf_reporte_general(nombre_emp, dir_emp, tel_emp, titulo_rep, df_datos):
    if not PDF_DISPONIBLE or df_datos.empty:
        return None
    from io import BytesIO
    buffer = BytesIO()
    p = canvas.Canvas(buffer, pagesize=letter)
    p.setFont("Helvetica-Bold", 14)
    p.drawString(50, 750, f"♻️ {nombre_emp}")
    p.setFont("Helvetica", 9)
    p.drawString(50, 735, f"{dir_emp} | Cel: {tel_emp}")
    p.line(50, 725, 550, 725)
    
    p.setFont("Helvetica-Bold", 12)
    p.drawString(50, 700, f"REPORTE: {titulo_rep}")
    p.setFont("Helvetica", 9)
    p.drawString(50, 685, f"Fecha de emision: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    p.line(50, 675, 550, 675)
    
    y = 650
    cols = list(df_datos.columns)
    
    p.setFont("Helvetica-Bold", 9)
    x_pos = 50
    for col in cols:
        p.drawString(x_pos, y, str(col)[:15])
        x_pos += 100
    y -= 15
    p.line(50, y, 550, y)
    y -= 15
    
    p.setFont("Helvetica", 8)
    for index, row in df_datos.iterrows():
        x_pos = 50
        for col in cols:
            val = str(row[col])
            p.drawString(x_pos, y, val[:18])
            x_pos += 100
        y -= 15
        if y < 80:
            p.showPage()
            y = 750
            p.setFont("Helvetica", 8)
            
    p.save()
    buffer.seek(0)
    return buffer.getvalue()

# ---------------------------------------------------------
# OPCIÓN 1: BÁSCULA DE COMPRA (DENTRO DE CUADRO PRINCIPAL)
# ---------------------------------------------------------
if menu == "📝 Registro de Compra (Báscula)":
    
    st.markdown('<div class="main-window-box">', unsafe_allow_html=True)
    
    col_head1, col_head2 = st.columns([3, 1])
    with col_head1:
        st.markdown("### 📝 REGISTRO DE COMPRA (BÁSCULA)")
    with col_head2:
        if st.button("🔄 Nueva Compra", use_container_width=True):
            st.session_state.carrito_compras = []
            st.session_state.texto_ticket_pantalla = ""
            st.session_state.input_kilos_key += 1
            st.session_state.reset_form_trigger += 1
            if "atj_mat" in st.session_state:
                del st.session_state.atj_mat
            st.rerun()

    # Marco 1: Datos Personales / Proveedor
    st.markdown('<div class="win-frame">', unsafe_allow_html=True)
    st.markdown('<div class="win-frame-title">👤 Datos Personales / Proveedor</div>', unsafe_allow_html=True)
    
    col_t1, col_t2 = st.columns([2, 2])
    with col_t1:
        turno_actual = st.selectbox("Turno Operativo:", ["Turno 1 (Mañana)", "Turno 2 (Tarde)", "Turno Completo"], key=f"turno_sel_{st.session_state.reset_form_trigger}")
    with col_t2:
        cliente_sel = st.text_input("Cliente / Proveedor (Escribir nombre):", value="Público General", key=f"cliente_input_{st.session_state.reset_form_trigger}")
    st.markdown('</div>', unsafe_allow_html=True)

    # Marco 2: Atajos rápidos de selección
    st.markdown('<div class="win-frame">', unsafe_allow_html=True)
    st.markdown('<div class="win-frame-title">⚡ Atajos de Selección Rápida</div>', unsafe_allow_html=True)
    
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
    st.markdown('</div>', unsafe_allow_html=True)

    # Marco 3: Detalle de Producto / Báscula
    st.markdown('<div class="win-frame">', unsafe_allow_html=True)
    st.markdown('<div class="win-frame-title">⚖️ Producto y Pesaje</div>', unsafe_allow_html=True)
    
    lista_nombres_mats = list(dict_mats.keys())
    mat_def_sel = st.session_state.get("atj_mat", None)
    
    if mat_def_sel and mat_def_sel in dict_mats:
        idx_default = lista_nombres_mats.index(mat_def_sel)
        mat_nom = st.selectbox("Material Seleccionado:", lista_nombres_mats, index=idx_default, key=f"mat_sel_box_{st.session_state.reset_form_trigger}")
    else:
        opciones_select = ["-- Ingrese o seleccione un producto --"] + lista_nombres_mats
        mat_nom_elegido = st.selectbox("Material Seleccionado:", opciones_select, key=f"mat_sel_box_{st.session_state.reset_form_trigger}")
        mat_nom = None if mat_nom_elegido == "-- Ingrese o seleccione un producto --" else mat_nom_elegido

    if mat_nom and mat_nom in dict_mats:
        mat_id, mat_p_db = dict_mats[mat_nom]
        precio_inicial_sugerido = st.session_state.get("atj_precio", float(mat_p_db))
    else:
        mat_id = None
        precio_inicial_sugerido = 0.0

    col_m2, col_m3 = st.columns(2)
    with col_m2:
        kilos = st.number_input("Cantidad (Kilos / Kg):", min_value=0.0, value=0.0, step=0.5, format="%.2f", key=f"kilos_input_{st.session_state.input_kilos_key}")
    with col_m3:
        precio = st.number_input("Precio Unitario ($/Kg):", value=float(precio_inicial_sugerido), step=0.5, format="%.2f", key=f"precio_input_{st.session_state.reset_form_trigger}")
        
    subtotal = kilos * precio
    st.info(f"Subtotal de Línea: **${subtotal:,.2f} MXN**")
    
    col_b1, col_b2 = st.columns([3, 1])
    with col_b1:
        if st.button("➕ Agregar al Comprobante", type="primary"):
            if not mat_nom:
                st.warning("⚠️ Por favor seleccione o ingrese un producto válido.")
            elif kilos <= 0:
                st.warning("⚠️ Ingrese una cantidad de kilos mayor a 0.")
            else:
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
                
                st.session_state.input_kilos_key += 1
                st.session_state.reset_form_trigger += 1
                st.success(f"¡Agregado {kilos} kg de {mat_nom}!")
                st.rerun()
    with col_b2:
        if st.button("🔄 Limpiar Partida"):
            st.session_state.input_kilos_key += 1
            st.session_state.reset_form_trigger += 1
            if "atj_mat" in st.session_state:
                del st.session_state.atj_mat
            st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

    # Marco 4: Datos de Comprobante / Total a Pagar
    st.markdown('<div class="win-frame">', unsafe_allow_html=True)
    st.markdown('<div class="win-frame-title">📄 Datos de Comprobante</div>', unsafe_allow_html=True)
    
    if st.session_state.carrito_compras:
        df_car = pd.DataFrame(st.session_state.carrito_compras)
        
        st.markdown("""
            <style>
            [data-testid="stTable"] td, [data-testid="stDataFrame"] td {
                font-size: 16px !important;
                font-weight: bold !important;
                color: #000000 !important;
            }
            </style>
        """, unsafe_allow_html=True)

        st.dataframe(df_car[["material", "kilos", "precio", "subtotal"]].rename(columns={
            "material": "Material", "kilos": "Kilos (Kg)", "precio": "Precio $/Kg", "subtotal": "Subtotal ($)"
        }), use_container_width=True)
        
        tot_ticket = sum(i["subtotal"] for i in st.session_state.carrito_compras)
        
        st.markdown(f"""
        <div style="background-color: #E8F5E9; border: 2px solid #2E7D32; padding: 12px; border-radius: 6px; text-align: right; font-weight: bold; font-size: 20px; color: #1B5E20;">
            IMPORTE TOTAL A PAGAR: ${tot_ticket:,.2f} MXN
        </div>
        """, unsafe_allow_html=True)
        
        st.write("")
        if st.button("💾 REGISTRAR E IMPRIMIR TICKET", type="primary", use_container_width=True):
            f_act = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            if cliente_sel and cliente_sel != "Público General":
                try:
                    cursor.execute("INSERT OR IGNORE INTO clientes (nombre, tipo) VALUES (?, 'Proveedor')", (cliente_sel,))
                except Exception:
                    pass

            cursor.execute("INSERT INTO compras (fecha, cliente, total_pagado, turno) VALUES (?, ?, ?, ?)",
                           (f_act, cliente_sel, tot_ticket, turno_actual))
            c_id = cursor.lastrowid
            
            for item in st.session_state.carrito_compras:
                cursor.execute("INSERT INTO detalle_compra (compra_id, material_id, kilos, subtotal) VALUES (?, ?, ?, ?)",
                               (c_id, item['material_id'], item['kilos'], item['subtotal']))
                cursor.execute("UPDATE materiales SET stock_kilos = stock_kilos + ? WHERE id = ?",
                               (item['kilos'], item['material_id']))
            
            conexion.commit()
            
            lineas_ticket = []
            lineas_ticket.append("==================================================")
            lineas_ticket.append("TICKET DE COMPRA - RECICLADORA DON KILO")
            lineas_ticket.append("==================================================")
            lineas_ticket.append(f"Folio: #{c_id}  |  Fecha: {f_act}")
            lineas_ticket.append(f"Proveedor: {cliente_sel}")
            lineas_ticket.append("--------------------------------------------------")
            for item in st.session_state.carrito_compras:
                mat_str = f"{item['material']:<18}"
                kg_str = f"{item['kilos']:>5.1f} kg"
                sub_str = f"${item['subtotal']:>8.2f}"
                lineas_ticket.append(f"{mat_str} {kg_str}   {sub_str}")
            lineas_ticket.append("--------------------------------------------------")
            lineas_ticket.append(f"TOTAL A PAGAR: ${tot_ticket:,.2f}")
            lineas_ticket.append("==================================================")
            
            st.session_state.texto_ticket_pantalla = "\n".join(lineas_ticket)
            
            bytes_pdf = generar_pdf_ticket(emp_nombre, emp_direccion, emp_telefono, c_id, f_act, turno_actual, cliente_sel, st.session_state.carrito_compras, tot_ticket)
            
            if bytes_pdf:
                carpeta_tk = obtener_ruta_carpeta_tickets()
                nombre_archivo = os.path.join(carpeta_tk, f"Ticket_Compra_{c_id}.pdf")
                with open(nombre_archivo, "wb") as f_pdf:
                    f_pdf.write(bytes_pdf)
                st.success(f"¡Transacción #{c_id} registrada con éxito!")
            
            st.session_state.carrito_compras = []
            st.session_state.input_kilos_key += 1
            st.session_state.reset_form_trigger += 1
            st.rerun()
    else:
        st.info("Aún no hay partidas agregadas al comprobante actual.")
    st.markdown('</div>', unsafe_allow_html=True)

    if "texto_ticket_pantalla" in st.session_state and st.session_state.texto_ticket_pantalla:
        st.markdown("### 🖨️ Vista Previa del Comprobante")
        st.markdown("""
            <style>
            code {
                font-size: 16px !important;
                font-weight: bold !important;
            }
            </style>
        """, unsafe_allow_html=True)
        st.code(st.session_state.texto_ticket_pantalla, language="")
        mostrar_boton_imprimir_termico(st.session_state.texto_ticket_pantalla)

    st.markdown('</div>', unsafe_allow_html=True)

# ---------------------------------------------------------
# OPCIÓN 2: VER INVENTARIO Y PRECIOS
# ---------------------------------------------------------
elif menu == "📦 Ver Inventario y Precios":
    st.markdown('<div class="main-window-box">', unsafe_allow_html=True)
    st.subheader("📦 Inventario Actual y Precios de Compra")
    cursor.execute("SELECT id, nombre, precio_compra, precio_venta, stock_kilos FROM materiales")
    mats = cursor.fetchall()
    df_inv = pd.DataFrame(mats, columns=["ID", "Material", "Precio Compra ($)", "Precio Venta ($)", "Stock (Kg)"])
    st.dataframe(df_inv, use_container_width=True)
    
    pdf_bytes = generar_pdf_reporte_general(emp_nombre, emp_direccion, emp_telefono, "Inventario Actual de Materiales", df_inv)
    if pdf_bytes:
        st.download_button("📥 Descargar Desglose en PDF", data=pdf_bytes, file_name="Reporte_Inventario.pdf", mime="application/pdf")
    st.markdown('</div>', unsafe_allow_html=True)

# ---------------------------------------------------------
# OPCIÓN 3: REGISTRAR VENTA
# ---------------------------------------------------------
elif menu == "📤 Registrar Venta (Salida)":
    st.markdown('<div class="main-window-box">', unsafe_allow_html=True)
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
    st.markdown('</div>', unsafe_allow_html=True)

# ---------------------------------------------------------
# OPCIÓN 4: CONTROL DE CAJA
# ---------------------------------------------------------
elif menu == "💵 Control de Caja (Fondo / Entradas)":
    st.markdown('<div class="main-window-box">', unsafe_allow_html=True)
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
    movs_data = cursor.fetchall()
    df_caja_movs = pd.DataFrame(movs_data, columns=["ID", "Fecha", "Turno", "Tipo", "Monto", "Motivo"])
    st.dataframe(df_caja_movs, use_container_width=True)
    
    pdf_bytes = generar_pdf_reporte_general(emp_nombre, emp_direccion, emp_telefono, "Movimientos y Fondo de Caja", df_caja_movs)
    if pdf_bytes:
        st.download_button("📥 Descargar Desglose de Caja en PDF", data=pdf_bytes, file_name="Reporte_Caja.pdf", mime="application/pdf")
    st.markdown('</div>', unsafe_allow_html=True)

# ---------------------------------------------------------
# OPCIÓN 5: CORTE DE CAJA POR TURNO Y DÍA
# ---------------------------------------------------------
elif menu == "✂️ Corte de Caja por Turno y Día":
    st.markdown('<div class="main-window-box">', unsafe_allow_html=True)
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
    <div style="background-color: #E8F5E9; border: 2px solid #2E7D32; padding: 15px; border-radius: 6px; text-align: center;">
        <p style="margin:0; font-weight:bold; color: #1B5E20;">EFECTIVO RESTANTE EN CAJA ({filtro_turno.upper()})</p>
        <h2 style="color: #2E7D32; margin: 5px 0 0 0;">${efectivo_restante:,.2f} MXN</h2>
    </div>
    """, unsafe_allow_html=True)
    
    st.write("")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Fondo/Inyecciones", f"${tot_ingresado:,.2f}")
    col2.metric("Ventas Cobradas", f"${tot_ventas:,.2f}")
    col3.metric("Comprado en Material", f"${tot_compras:,.2f}")
    col4.metric("Gastos Generales", f"${tot_gastos:,.2f}")
    
    df_corte_resumen = pd.DataFrame([
        {"Concepto": "Fondo / Inyecciones", "Monto ($)": tot_ingresado},
        {"Concepto": "Ventas Cobradas", "Monto ($)": tot_ventas},
        {"Concepto": "Compras de Material", "Monto ($)": tot_compras},
        {"Concepto": "Gastos Operativos", "Monto ($)": tot_gastos},
        {"Concepto": "Efectivo Restante en Caja", "Monto ($)": efectivo_restante}
    ])
    pdf_bytes = generar_pdf_reporte_general(emp_nombre, emp_direccion, emp_telefono, f"Corte de Caja - {f_corte.strftime('%Y-%m-%d')} ({filtro_turno})", df_corte_resumen)
    if pdf_bytes:
        st.download_button("📥 Descargar Corte de Caja en PDF", data=pdf_bytes, file_name=f"Corte_Caja_{f_corte}.pdf", mime="application/pdf")
    st.markdown('</div>', unsafe_allow_html=True)

# ---------------------------------------------------------
# OPCIÓN 6: GASTOS
# ---------------------------------------------------------
elif menu == "💸 Registrar y Administrar Gastos":
    st.markdown('<div class="main-window-box">', unsafe_allow_html=True)
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
    gastos_data = cursor.fetchall()
    df_g = pd.DataFrame(gastos_data, columns=["ID", "Fecha", "Turno", "Categoría", "Descripción", "Monto"])
    st.dataframe(df_g, use_container_width=True)
    
    pdf_bytes = generar_pdf_reporte_general(emp_nombre, emp_direccion, emp_telefono, "Reporte de Gastos Operativos", df_g)
    if pdf_bytes:
        st.download_button("📥 Descargar Desglose de Gastos en PDF", data=pdf_bytes, file_name="Reporte_Gastos.pdf", mime="application/pdf")
    st.markdown('</div>', unsafe_allow_html=True)

# ---------------------------------------------------------
# OPCIÓN 7: REPORTES
# ---------------------------------------------------------
elif menu == "📊 Reportes (Diario, Semanal, Mensual, Anual)":
    st.markdown('<div class="main-window-box">', unsafe_allow_html=True)
    st.subheader("📊 Reportes Financieros")
    
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
        
    cursor.execute("SELECT COUNT(*), SUM(total_pagado) FROM compras WHERE fecha >= ? AND fecha <= ?", (f_inicio, f_fin))
    res_c = cursor.fetchone()
    num_compras = res_c[0] or 0
    tot_compra_dinero = res_c[1] or 0.0
    
    cursor.execute("SELECT SUM(monto) FROM gastos WHERE fecha >= ? AND fecha <= ?", (f_inicio, f_fin))
    tot_gastos_per = cursor.fetchone()[0] or 0.0
    
    cursor.execute('''
        SELECT m.nombre, SUM(d.kilos), SUM(d.subtotal), 
               SUM((m.precio_venta - m.precio_compra) * d.kilos) as utilidad
        FROM detalle_compra d
        JOIN compras c ON d.compra_id = c.id
        JOIN materiales m ON d.material_id = m.id
        WHERE c.fecha >= ? AND c.fecha <= ?
        GROUP BY m.nombre
    ''', (f_inicio, f_fin))
    mats_rep = cursor.fetchall()
    
    util_bruta_per = sum(r[3] for r in mats_rep) if mats_rep else 0.0
    util_neta_per = util_bruta_per - tot_gastos_per
    
    st.write("---")
    col_r1, col_r2, col_r3, col_r4, col_r5 = st.columns(5)
    col_r1.metric("Tickets Compra", num_compras)
    col_r2.metric("Inversión en Material", f"${tot_compra_dinero:,.2f}")
    col_r3.metric("Utilidad Bruta Est.", f"${util_bruta_per:,.2f}")
    col_r4.metric("Gastos Totales", f"${tot_gastos_per:,.2f}")
    col_r5.metric("Utilidad Neta Real", f"${util_neta_per:,.2f}")
    
    st.write("---")
    st.write(f"### Desglose de Compras ({periodo})")
    if mats_rep:
        df_rep = pd.DataFrame(mats_rep, columns=["Material", "Kilos Comprados", "Inversión ($)", "Utilidad Est. ($)"])
        st.dataframe(df_rep, use_container_width=True)
        
        pdf_bytes = generar_pdf_reporte_general(emp_nombre, emp_direccion, emp_telefono, f"Reporte Financiero ({periodo})", df_rep)
        if pdf_bytes:
            st.download_button("📥 Descargar Reporte Financiero en PDF", data=pdf_bytes, file_name=f"Reporte_Financiero_{periodo}.pdf", mime="application/pdf")
    else:
        st.info("No hay registros de compras en el período seleccionado.")
    st.markdown('</div>', unsafe_allow_html=True)

# ---------------------------------------------------------
# OPCIÓN 8: CONFIGURACIÓN / PRECIOS / EMPRESA
# ---------------------------------------------------------
elif menu == "⚙️ Configuración / Precios / Empresa":
    st.markdown('<div class="main-window-box">', unsafe_allow_html=True)
    st.subheader("⚙️ Configuración General, Precios de Compra y Datos de Empresa")
    
    with st.form("form_config_emp"):
        nom_e = st.text_input("Nombre del Negocio:", value=emp_nombre)
        dir_e = st.text_input("Dirección:", value=emp_direccion)
        tel_e = st.text_input("Teléfono / Celular:", value=emp_telefono)
        if st.form_submit_button("Guardar Datos de Empresa"):
            cursor.execute("UPDATE config_empresa SET nombre = ?, direccion = ?, telefono = ? WHERE id = 1", (nom_e, dir_e, tel_e))
            conexion.commit()
            st.success("¡Datos de empresa actualizados!")
            st.rerun()

    st.markdown("---")
    st.write("### 💰 Configuración Oficial de Precios de Compra por Material")
    
    cursor.execute("SELECT id, nombre, precio_compra FROM materiales ORDER BY nombre ASC")
    todos_mats = cursor.fetchall()
    
    if todos_mats:
        with st.form("form_actualizar_precios"):
            nuevos_precios = {}
            for m_id, m_nom, m_pc in todos_mats:
                nuevos_precios[m_id] = st.number_input(f"Precio Oficial de Compra para '{m_nom}' ($/Kg):", value=float(m_pc), step=0.5, format="%.2f", key=f"precio_mat_{m_id}")
                
            if st.form_submit_button("💾 Guardar Precios en el Inventario"):
                for m_id, nuevo_val in nuevos_precios.items():
                    cursor.execute("UPDATE materiales SET precio_compra = ? WHERE id = ?", (nuevo_val, m_id))
                conexion.commit()
                st.success("¡Precios de compra actualizados correctamente en el inventario general!")
                st.rerun()

    st.markdown("---")
    st.write("### ⚠️ Reiniciar Datos de Prueba")
    st.warning("Esto borrará todos los registros de compras, ventas, gastos, movimientos de caja y restablecerá el stock a 0 para que puedas empezar de cero con tus operaciones reales.")
    if st.button("🗑️ Borrar Todas las Pruebas y Vaciar Base de Datos"):
        cursor.execute("DELETE FROM compras")
        cursor.execute("DELETE FROM detalle_compra")
        cursor.execute("DELETE FROM ventas")
        cursor.execute("DELETE FROM detalle_venta")
        cursor.execute("DELETE FROM gastos")
        cursor.execute("DELETE FROM movimientos_caja")
        cursor.execute("UPDATE materiales SET stock_kilos = 0.0")
        conexion.commit()
        st.success("¡Base de datos limpiada con éxito! Ya puedes iniciar con tus compras reales.")
        st.rerun()

    st.markdown("---")
    st.write("### 🗑️ Eliminar Materiales")
    if todos_mats:
        mat_del = st.selectbox("Seleccione material a eliminar:", [m[1] for m in todos_mats])
        if st.button("🗑️ Borrar Material Permanentemente"):
            cursor.execute("DELETE FROM materiales WHERE nombre = ?", (mat_del,))
            conexion.commit()
            st.error(f"Material '{mat_del}' eliminado.")
            st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

conexion.close()
