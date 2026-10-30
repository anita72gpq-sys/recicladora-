from datetime import datetime, timedelta
import os
import sqlite3
import pandas as pd
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

# Estilos CSS personalizados para mejorar botones, tarjetas y colores verdes
st.markdown(
    """
    <style>
    /* Fondo y colores principales */
    .stApp {
        background-color: #F4F8F5;
    }
    
    /* Encabezado Principal */
    .header-box {
        background: linear-gradient(135deg, #1E4D2B 0%, #2E7D32 100%);
        color: white;
        padding: 20px;
        border-radius: 12px;
        text-align: center;
        margin-bottom: 25px;
        box-shadow: 0px 4px 10px rgba(0, 0, 0, 0.15);
    }
    .header-box h1 {
        color: #FFFFFF !important;
        margin: 0;
        font-weight: 800;
    }
    .header-box p {
        color: #E8F5E9 !important;
        margin: 5px 0 0 0;
        font-size: 15px;
    }

    /* Botones primarios en verde destacado */
    div.stButton > button:first-child {
        background-color: #2E7D32 !important;
        color: white !important;
        font-weight: bold !important;
        border-radius: 8px !important;
        border: none !important;
        padding: 8px 16px !important;
    }
    div.stButton > button:first-child:hover {
        background-color: #1B5E20 !important;
        box-shadow: 0 4px 8px rgba(0,0,0,0.2);
    }

    /* Métrica / Total destacado */
    .total-card {
        background-color: #E8F5E9;
        border-left: 6px solid #2E7D32;
        padding: 15px;
        border-radius: 8px;
        text-align: center;
        margin-top: 10px;
    }
    .total-card h2 {
        color: #1B5E20;
        margin: 0;
        font-size: 32px;
    }
    </style>
""",
    unsafe_allow_html=True,
)


# ---------------------------------------------------------
# BASE DE DATOS Y CONEXIÓN
# ---------------------------------------------------------
def obtener_conexion():
  ruta_bd = os.path.expanduser("~/recicladora.db")
  return sqlite3.connect(ruta_bd)


def inicializar_bd():
  conexion = obtener_conexion()
  cursor = conexion.cursor()

  # Tablas
  cursor.execute("""
        CREATE TABLE IF NOT EXISTS config_empresa (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT,
            direccion TEXT,
            telefono TEXT
        )
    """)
  cursor.execute("""
        CREATE TABLE IF NOT EXISTS clientes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT UNIQUE NOT NULL,
            telefono TEXT,
            tipo TEXT DEFAULT 'Proveedor'
        )
    """)
  cursor.execute("""
        CREATE TABLE IF NOT EXISTS materiales (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            precio_compra REAL NOT NULL,
            precio_venta REAL DEFAULT 0.0,
            stock_kilos REAL DEFAULT 0.0
        )
    """)
  cursor.execute("""
        CREATE TABLE IF NOT EXISTS compras (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha TEXT NOT NULL,
            cliente TEXT NOT NULL,
            total_pagado REAL NOT NULL
        )
    """)
  cursor.execute("""
        CREATE TABLE IF NOT EXISTS detalle_compra (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            compra_id INTEGER,
            material_id INTEGER,
            kilos REAL NOT NULL,
            subtotal REAL NOT NULL
        )
    """)
  cursor.execute("""
        CREATE TABLE IF NOT EXISTS ventas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha TEXT NOT NULL,
            comprador TEXT NOT NULL,
            total_cobrado REAL NOT NULL
        )
    """)
  cursor.execute("""
        CREATE TABLE IF NOT EXISTS detalle_venta (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            venta_id INTEGER,
            material_id INTEGER,
            kilos REAL NOT NULL,
            subtotal REAL NOT NULL
        )
    """)
  cursor.execute("""
        CREATE TABLE IF NOT EXISTS gastos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha TEXT NOT NULL,
            categoria TEXT NOT NULL,
            descripcion TEXT,
            monto REAL NOT NULL
        )
    """)
  cursor.execute("""
        CREATE TABLE IF NOT EXISTS movimientos_caja (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha TEXT NOT NULL,
            tipo TEXT NOT NULL,
            monto REAL NOT NULL,
            motivo TEXT
        )
    """)

  # Datos por defecto de la empresa
  cursor.execute("SELECT COUNT(*) FROM config_empresa")
  if cursor.fetchone()[0] == 0:
    cursor.execute(
        "INSERT INTO config_empresa (nombre, direccion, telefono) VALUES (?,"
        " ?, ?)",
        (
            "Chatarrería Don Kilo",
            "Calle Principal #123, Mérida, Yucatán",
            "999-000-0000",
        ),
    )

  # Materiales iniciales
  cursor.execute("SELECT COUNT(*) FROM materiales")
  if cursor.fetchone()[0] == 0:
    materiales_iniciales = [
        ("Chatarra", 4.50, 6.00, 0.0),
        ("Cobre", 140.00, 160.00, 0.0),
        ("Bronce", 90.00, 105.00, 0.0),
        ("Aluminio Latas", 28.00, 33.00, 0.0),
        ("Aluminio General", 22.00, 27.00, 0.0),
    ]
    cursor.executemany(
        "INSERT INTO materiales (nombre, precio_compra, precio_venta,"
        " stock_kilos) VALUES (?, ?, ?, ?)",
        materiales_iniciales,
    )

  conexion.commit()
  conexion.close()


inicializar_bd()

# Inicializar Carrito de Compras en Estado de Sesión
if "carrito_compras" not in st.session_state:
  st.session_state.carrito_compras = []

conexion = obtener_conexion()
cursor = conexion.cursor()

# Cargar datos de la empresa
cursor.execute("SELECT nombre, direccion, telefono FROM config_empresa LIMIT 1")
empresa_info = cursor.fetchone()
emp_nombre = empresa_info[0] if empresa_info else "Chatarrería Don Kilo"
emp_direccion = empresa_info[1] if empresa_info else "Dirección no registrada"
emp_telefono = empresa_info[2] if empresa_info else "Tel. S/N"

# ENCABEZADO DE LA APLICACIÓN
st.markdown(
    f"""
    <div class="header-box">
        <h1>♻️ {emp_nombre}</h1>
        <p>📍 {emp_direccion} | 📞 Cel: {emp_telefono}</p>
    </div>
    """,
    unsafe_allow_html=True,
)

# MENÚ LATERAL
menu = st.sidebar.selectbox(
    "📋 Menú Principal",
    [
        "📝 Registrar Nueva Compra (Báscula)",
        "📦 Ver Inventario y Precios",
        "📤 Registrar Venta (Salida)",
        "💵 Control de Caja (Fondo / Entradas)",
        "✂️ Corte de Caja Diario",
        "💸 Registrar y Administrar Gastos",
        "📊 Reportes de Compras y Utilidad",
        "⚙️ Configuración / Datos Empresa",
    ],
)

# ---------------------------------------------------------
# OPCIÓN 1: REGISTRAR NUEVA COMPRA (BÁSCULA RÁPIDA)
# ---------------------------------------------------------
if menu == "📝 Registrar Nueva Compra (Báscula)":
  st.subheader("🛒 Registro Rápido de Compra de Materiales")

  # Obtener Clientes / Proveedores
  cursor.execute("SELECT nombre FROM clientes ORDER BY nombre ASC")
  lista_clientes = [c[0] for c in cursor.fetchall()]
  if "Público General" not in lista_clientes:
    lista_clientes.insert(0, "Público General")

  col_cli1, col_cli2 = st.columns([3, 1])
  with col_cli1:
    cliente_seleccionado = st.selectbox(
        "👤 Seleccione Proveedor / Cliente:", lista_clientes
    )
  with col_cli2:
    st.write("¿Nuevo Cliente?")
    with st.popover("➕ Agregar Cliente"):
      nuevo_cli_nombre = st.text_input("Nombre Completo:")
      nuevo_cli_tel = st.text_input("Teléfono Celular:")
      if st.button("Guardar Cliente"):
        if nuevo_cli_nombre:
          try:
            cursor.execute(
                "INSERT INTO clientes (nombre, telefono) VALUES (?, ?)",
                (nuevo_cli_nombre, nuevo_cli_tel),
            )
            conexion.commit()
            st.success(f"¡Cliente '{nuevo_cli_nombre}' guardado!")
            st.rerun()
          except Exception:
            st.error("El cliente ya está registrado.")

  st.markdown("---")
  st.write("### ➕ Agregar Material a la Compra Actual")

  cursor.execute(
      "SELECT id, nombre, precio_compra FROM materiales ORDER BY nombre ASC"
  )
  materiales_db = cursor.fetchall()

  if materiales_db:
    dict_mat = {m[1]: (m[0], m[2]) for m in materiales_db}

    col_m1, col_m2, col_m3 = st.columns([3, 2, 2])
    with col_m1:
      mat_nombre_sel = st.selectbox(
          "Seleccione Material:", list(dict_mat.keys())
      )
      mat_id, mat_precio = dict_mat[mat_nombre_sel]
    with col_m2:
      kilos_ingresados = st.number_input(
          "Kilos (Kg):", min_value=0.0, step=0.5, format="%.2f"
      )
    with col_m3:
      precio_aplicado = st.number_input(
          "Precio $/Kg:", value=float(mat_precio), step=0.5, format="%.2f"
      )

    subtotal_item = kilos_ingresados * precio_aplicado

    col_btn_add, col_btn_clr = st.columns([3, 1])
    with col_btn_add:
      if st.button("📥 Agregar Producto a la Lista", type="primary"):
        if kilos_ingresados <= 0:
          st.warning("⚠️ Ingrese una cantidad de kilos mayor a 0.")
        else:
          st.session_state.carrito_compras.append({
              "material_id": mat_id,
              "material": mat_nombre_sel,
              "kilos": kilos_ingresados,
              "precio": precio_aplicado,
              "subtotal": subtotal_item,
          })
          st.success(f"Added {kilos_ingresados} kg de {mat_nombre_sel}")
          st.rerun()

    with col_btn_clr:
      if st.button("🔄 Iniciar Nueva Compra"):
        st.session_state.carrito_compras = []
        st.rerun()

  # DETALLE DEL TICKET ACTUAL
  st.markdown("---")
  st.write("### 📄 Materiales en este Ticket:")

  if st.session_state.carrito_compras:
    df_carrito = pd.DataFrame(st.session_state.carrito_compras)
    st.dataframe(
        df_carrito[["material", "kilos", "precio", "subtotal"]].rename(
            columns={
                "material": "Material",
                "kilos": "Kilos (Kg)",
                "precio": "Precio $/Kg",
                "subtotal": "Subtotal ($)",
            }
        ),
        use_container_width=True,
    )

    total_ticket = sum(
        item["subtotal"] for item in st.session_state.carrito_compras
    )

    st.markdown(
        f"""
        <div class="total-card">
            <p style="margin:0; color:#2E7D32; font-weight:bold;">TOTAL A PAGAR AL CLIENTE</p>
            <h2>${total_ticket:,.2f} MXN</h2>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.write("")
    if st.button(
        "✅ FINALIZAR Y IMPRIMIR TICKET DE COMPRA",
        type="primary",
        use_container_width=True,
    ):
      fecha_actual = datetime.now().strftime("%Y-%m-%d %H:%M")
      cursor.execute(
          "INSERT INTO compras (fecha, cliente, total_pagado) VALUES (?, ?, ?)",
          (fecha_actual, cliente_seleccionado, total_ticket),
      )
      compra_id = cursor.lastrowid

      for item in st.session_state.carrito_compras:
        cursor.execute(
            "INSERT INTO detalle_compra (compra_id, material_id, kilos,"
            " subtotal) VALUES (?, ?, ?, ?)",
            (compra_id, item["material_id"], item["kilos"], item["subtotal"]),
        )
        cursor.execute(
            "UPDATE materiales SET stock_kilos = stock_kilos + ? WHERE id = ?",
            (item["kilos"], item["material_id"]),
        )

      conexion.commit()

      # Ticket de Texto Formateado
      texto_ticket = f"========================================\n"
      texto_ticket += f"       {emp_nombre.upper()}             \n"
      texto_ticket += f"  {emp_direccion}  \n"
      texto_ticket += f"  Tel/Cel: {emp_telefono} \n"
      texto_ticket += f"========================================\n"
      texto_ticket += f"Folio: #{compra_id} | Fecha: {fecha_actual}\n"
      texto_ticket += f"Cliente/Proveedor: {cliente_seleccionado}\n"
      texto_ticket += f"----------------------------------------\n"
      for item in st.session_state.carrito_compras:
        texto_ticket += f"{item['material']:<15} {item['kilos']:<6.1f}kg  ${item['subtotal']:<7.2f}\n"
      texto_ticket += f"----------------------------------------\n"
      texto_ticket += f"TOTAL PAGADO: ${total_ticket:,.2f}\n"
      texto_ticket += f"========================================\n"
      texto_ticket += f"      ¡Gracias por su confianza!       \n"

      st.success(f"¡Compra #{compra_id} registrada con éxito!")
      st.text(texto_ticket)

      # Reiniciar Carrito
      st.session_state.carrito_compras = []

      st.download_button(
          label="📄 Descargar Ticket de Compra (TXT)",
          data=texto_ticket,
          file_name=f"Ticket_{compra_id}.txt",
          mime="text/plain",
      )
  else:
    st.info(
        "El ticket está vacío. Seleccione un producto arriba y haga clic en"
        " 'Agregar Producto'."
    )

# ---------------------------------------------------------
# OPCIÓN 2: VER INVENTARIO Y PRECIOS
# ---------------------------------------------------------
elif menu == "📦 Ver Inventario y Precios":
  st.subheader("📦 Inventario Actual y Lista de Precios")
  cursor.execute(
      "SELECT id, nombre, precio_compra, precio_venta, stock_kilos FROM"
      " materiales"
  )
  mat_list = cursor.fetchall()
  df_mat = pd.DataFrame(
      mat_list,
      columns=[
          "ID",
          "Material",
          "Precio Compra ($)",
          "Precio Venta ($)",
          "Stock Bodega (Kg)",
      ],
  )
  st.dataframe(df_mat, use_container_width=True)

# ---------------------------------------------------------
# OPCIÓN 3: REGISTRAR VENTA (SALIDA DE MATERIAL)
# ---------------------------------------------------------
elif menu == "📤 Registrar Venta (Salida)":
  st.subheader("📤 Registrar Venta de Material a Fundidora")
  comprador = st.text_input("Nombre de la Fundidora / Comprador Final:")

  cursor.execute("SELECT id, nombre, precio_venta, stock_kilos FROM materiales")
  mats = cursor.fetchall()

  ventas_dict = {}
  for m in mats:
    col1, col2, col3 = st.columns(3)
    with col1:
      st.write(f"**{m[1]}** (Disp: {m[3]:.1f} kg)")
    with col2:
      kv = st.number_input(
          f"Kg a vender de {m[1]}",
          min_value=0.0,
          max_value=float(m[3]),
          key=f"v_{m[0]}",
      )
    with col3:
      st.write(f"Subtotal: **${kv * m[2]:,.2f}**")
    if kv > 0:
      ventas_dict[m[0]] = (m[1], kv, m[2], kv * m[2])

  if st.button("Finalizar Venta", type="primary"):
    if not comprador:
      st.error("Ingrese el comprador.")
    elif not ventas_dict:
      st.error("Seleccione al menos un producto.")
    else:
      f_act = datetime.now().strftime("%Y-%m-%d %H:%M")
      tot_v = sum(x[3] for x in ventas_dict.values())
      cursor.execute(
          "INSERT INTO ventas (fecha, comprador, total_cobrado) VALUES (?, ?,"
          " ?)",
          (f_act, comprador, tot_v),
      )
      v_id = cursor.lastrowid

      for mid, data in ventas_dict.items():
        cursor.execute(
            "INSERT INTO detalle_venta (venta_id, material_id, kilos, subtotal)"
            " VALUES (?, ?, ?, ?)",
            (v_id, mid, data[1], data[3]),
        )
        cursor.execute(
            "UPDATE materiales SET stock_kilos = stock_kilos - ? WHERE id = ?",
            (data[1], mid),
        )

      conexion.commit()
      st.success(f"¡Venta #{v_id} realizada por ${tot_v:,.2f}!")

# ---------------------------------------------------------
# OPCIÓN 4: CONTROL DE CAJA (FONDO / ENTRADAS)
# ---------------------------------------------------------
elif menu == "💵 Control de Caja (Fondo / Entradas)":
  st.subheader("💵 Fondo de Caja e Inyecciones de Efectivo")

  with st.form("form_caja_in"):
    tipo_m = st.selectbox(
        "Tipo:", ["Fondo Inicial de Caja", "Inyección Extra de Efectivo"]
    )
    monto_m = st.number_input("Monto ($):", min_value=0.0, step=100.0)
    motivo_m = st.text_input("Motivo:")
    if st.form_submit_button("Guardar en Caja"):
      if monto_m > 0:
        f_act = datetime.now().strftime("%Y-%m-%d %H:%M")
        cursor.execute(
            "INSERT INTO movimientos_caja (fecha, tipo, monto, motivo) VALUES"
            " (?, ?, ?, ?)",
            (f_act, tipo_m, monto_m, motivo_m),
        )
        conexion.commit()
        st.success(f"Se ingresaron ${monto_m:,.2f} a caja.")
        st.rerun()

  cursor.execute(
      "SELECT id, fecha, tipo, monto, motivo FROM movimientos_caja ORDER BY id"
      " DESC"
  )
  st.dataframe(
      pd.DataFrame(
          cursor.fetchall(),
          columns=["ID", "Fecha", "Tipo", "Monto", "Motivo"],
      ),
      use_container_width=True,
  )

# ---------------------------------------------------------
# OPCIÓN 5: CORTE DE CAJA DIARIO
# ---------------------------------------------------------
elif menu == "✂️ Corte de Caja Diario":
  st.subheader("✂️ Corte de Caja Diario")
  f_corte = st.date_input("Fecha del corte:", datetime.now())
  f_i = f_corte.strftime("%Y-%m-%d 00:00")
  f_f = f_corte.strftime("%Y-%m-%d 23:59")

  cursor.execute(
      "SELECT SUM(monto) FROM movimientos_caja WHERE fecha BETWEEN ? AND ?",
      (f_i, f_f),
  )
  tot_ingresado = cursor.fetchone()[0] or 0.0

  cursor.execute(
      "SELECT SUM(total_cobrado) FROM ventas WHERE fecha BETWEEN ? AND ?",
      (f_i, f_f),
  )
  tot_ventas = cursor.fetchone()[0] or 0.0

  cursor.execute(
      "SELECT SUM(total_pagado) FROM compras WHERE fecha BETWEEN ? AND ?",
      (f_i, f_f),
  )
  tot_compras = cursor.fetchone()[0] or 0.0

  cursor.execute(
      "SELECT SUM(monto) FROM gastos WHERE fecha BETWEEN ? AND ?", (f_i, f_f)
  )
  tot_gastos = cursor.fetchone()[0] or 0.0

  efectivo_en_caja = (tot_ingresado + tot_ventas) - (tot_compras + tot_gastos)

  st.markdown(
      f"""
    <div class="total-card">
        <p style="margin:0;">EFECTIVO FÍSICO QUE DEBE HABER EN CAJA</p>
        <h2>${efectivo_en_caja:,.2f} MXN</h2>
    </div>
    """,
      unsafe_allow_html=True,
  )

  col1, col2, col3 = st.columns(3)
  col1.metric("Ingresos a Caja", f"${tot_ingresado + tot_ventas:,.2f}")
  col2.metric("Pagado en Compras", f"${tot_compras:,.2f}")
  col3.metric("Gastos Operativos", f"${tot_gastos:,.2f}")

# ---------------------------------------------------------
# OPCIÓN 6: REGISTRAR Y ADMINISTRAR GASTOS
# ---------------------------------------------------------
elif menu == "💸 Registrar y Administrar Gastos":
  st.subheader("💸 Registro de Gastos")
  with st.form("fgastos"):
    cat = st.selectbox(
        "Categoría:",
        ["Sueldo", "Gasolina", "Mantenimiento", "Luz", "Agua", "Otros"],
    )
    mon = st.number_input("Monto ($):", min_value=0.0)
    des = st.text_input("Descripción:")
    if st.form_submit_button("Guardar Gasto"):
      if mon > 0:
        cursor.execute(
            "INSERT INTO gastos (fecha, categoria, descripcion, monto) VALUES"
            " (?, ?, ?, ?)",
            (datetime.now().strftime("%Y-%m-%d %H:%M"), cat, des, mon),
        )
        conexion.commit()
        st.success("Gasto registrado.")
        st.rerun()

# ---------------------------------------------------------
# OPCIÓN 7: REPORTES
# ---------------------------------------------------------
elif menu == "📊 Reportes de Compras y Utilidad":
  st.subheader("📊 Reportes Financieros")
  cursor.execute("SELECT SUM(total_pagado) FROM compras")
  tc = cursor.fetchone()[0] or 0.0
  cursor.execute("SELECT SUM(monto) FROM gastos")
  tg = cursor.fetchone()[0] or 0.0
  st.metric("Total Invertido en Compras", f"${tc:,.2f}")
  st.metric("Total Gastos acumulados", f"${tg:,.2f}")

# ---------------------------------------------------------
# OPCIÓN 8: CONFIGURACIÓN Y DATOS DE LA EMPRESA
# ---------------------------------------------------------
elif menu == "⚙️ Configuración / Datos Empresa":
  st.subheader("⚙️ Configuración de Empresa y Materiales")

  st.write("### 🏢 Datos de la Chatarrería")
  with st.form("form_config_emp"):
    nom_e = st.text_input("Nombre del Negocio:", value=emp_nombre)
    dir_e = st.text_input("Dirección:", value=emp_direccion)
    tel_e = st.text_input("Teléfono / Celular:", value=emp_telefono)
    if st.form_submit_button("Guardar Datos de Empresa"):
      cursor.execute(
          "UPDATE config_empresa SET nombre = ?, direccion = ?, telefono = ?"
          " WHERE id = 1",
          (nom_e, dir_e, tel_e),
      )
      conexion.commit()
      st.success("¡Datos actualizados!")
      st.rerun()

  st.markdown("---")
  st.write("### 🗑️ Eliminar o Modificar Materiales")
  cursor.execute("SELECT id, nombre, precio_compra, precio_venta FROM materiales")
  mats_all = cursor.fetchall()

  if mats_all:
    mat_del = st.selectbox(
        "Material a eliminar:", [m[1] for m in mats_all], key="del_mat_sel"
    )
    if st.button("🗑️ Borrar Material"):
      cursor.execute("DELETE FROM materiales WHERE nombre = ?", (mat_del,))
      conexion.commit()
      st.error(f"Material '{mat_del}' eliminado.")
      st.rerun()

conexion.close()
