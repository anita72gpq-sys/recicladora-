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

def mostrar
