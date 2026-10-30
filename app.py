from datetime import datetime, timedelta
import os
import sqlite3
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
# BASE DE DATOS
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
                       ("Chatarrería Don Kilo", "Calle Principal #123, Mérida, Yucatán", "999-000-0000"))
        
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

# Cargar Info Empresa
cursor.execute("SELECT nombre, direccion, telefono FROM config_empresa LIMIT 1")
empresa_info = cursor.fetchone()
emp_nombre = empresa_info[0] if empresa_info else "Chatarrería Don Kilo"
emp_direccion = empresa_info[1] if empresa_info else "Mérida, Yucatán"
emp_telefono = empresa_info[2] if empresa_info else "999-000-0000"

# ENCABEZADO
st.markdown(f"""
    <div class="header-box">
        <h1>♻️ {emp_nombre}</h1>
        <p>📍 {emp_direccion} | 📞 Cel: {emp_telefono}</p>
    </div>
""", unsafe_allow_html=True)

# MENÚ PRINCIPAL
menu = st.sidebar.selectbox("📋 Menú Principal", [
    "📝 Registrar Compra (Báscula)",
    "📦 Ver Inventario y Precios",
    "📤 Registrar Venta (Salida)",
    "💵 Control de Caja (Fondo / Entradas)",
    "✂️ Corte de Caja por Turno y Día",
    "💸 Registrar y Administrar Gastos",
    "📊 Reportes (Diario, Semanal, Mensual, Anual)",
    "⚙️ Configuración / Datos Empresa"
])

# ---------------------------------------------------------
# FUNCIONES DE CARPETA Y PDF
# ---------------------------------------------------------
def obtener_ruta_carpeta_tickets():
    carpeta = os.path.abspath("Tickets_Recicladora")
    os.makedirs(carpeta, exist_ok=True)
    return carpeta

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
    p.line(50, 725, 450, 725)
    
    p.setFont("Helvetica-Bold", 11)
    p.drawString(50, 705, f"TICKET DE COMPRA #{folio}")
    p.setFont("Helvetica", 10)
    p.drawString(50, 685, f"Fecha: {fecha} | Turno: {turno}")
    p.drawString(50, 665, f"Proveedor / Cliente: {cliente}")
    p.line(50, 655, 450, 655)
    
    y = 635
    p.setFont("Helvetica-Bold", 9)
    p.drawString(50, y, "MATERIAL")
    p.drawString(220, y, "KG")
    p.drawString(320, y, "SUBTOTAL")
    y -= 15
    
    p.setFont("Helvetica", 9)
    for item in carrito:
        p.drawString(50, y, str(item['material']))
        p.drawString(220, y, f"{item['kilos']:.1f} kg")
        p.drawString(320, y, f"${item['subtotal']:,.2f}")
        y -= 15
        
    p.line(50, y - 5, 450, y - 5)
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
    st.subheader("🛒 Registro Rápido de Compra")
    
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
    st.write("### ➕ Agregar Material")
    
    cursor.execute("SELECT id, nombre, precio_compra FROM materiales ORDER BY nombre ASC")
    mats_db = cursor.fetchall()
    
    if mats_db:
        dict_mats = {m[1]: (m[0], m[2]) for m in mats_db}
        col_m1, col_m2, col_m3 = st.columns([3, 2, 2])
        with col_m1:
            mat_nom = st.selectbox("Material:", list(dict_mats.keys()))
            mat_id, mat_p = dict_mats[mat_nom]
        with col_m2:
            kilos = st.number_input("Kilos (Kg):", min_value=0.0, step=0.5, format="%.2f")
        with col_m3:
            precio = st.number_input("Precio $/Kg:", value=float(mat_p), step=0.5, format="%.2f")
            
        subtotal = kilos * precio
        
        col_b1, col_b2 = st.columns([3, 1])
        with col_b1:
            if st.button("📥 Agregar a la Lista", type="primary"):
                if kilos <= 0:
                    st.warning("Ingrese cantidad de kilos mayor a 0.")
                else:
                    st.session_state.carrito_compras.append({
                        "material_id": mat_id,
                        "material": mat_nom,
                        "kilos": kilos,
                        "precio": precio,
                        "subtotal": subtotal
                    })
                    st.success(f"Agregado {kilos} kg de {mat_nom}")
                    st.rerun()
        with col_b2:
            if st.button("🔄 Limpiar Ticket"):
                st.session_state.carrito_compras = []
                st.rerun()

    st.markdown("---")
    st.write("### 📄 Ticket Actual:")
    
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
        if st.button("✅ FINALIZAR Y GENERAR TICKET PDF", type="primary", use_container_width=True):
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
                carpeta_tk = obtener
