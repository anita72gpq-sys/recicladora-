from datetime import datetime, timedelta
import io
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

st.markdown(
    """
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
""",
    unsafe_allow_html=True,
)


# ---------------------------------------------------------
# BASE DE DATOS
# ---------------------------------------------------------
def obtener_conexion():
  return sqlite3.connect("recicladora.db", check_same_thread=False)


def inicializar_bd():
  conexion = obtener_conexion()
  cursor = conexion.cursor()

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
            total_pagado REAL NOT NULL,
            turno TEXT DEFAULT 'Turno 1'
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
            total_cobrado REAL NOT NULL,
            turno TEXT DEFAULT 'Turno 1'
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
            monto REAL NOT NULL,
            turno TEXT DEFAULT 'Turno 1'
        )
    """)
  cursor.execute("""
        CREATE TABLE IF NOT EXISTS movimientos_caja (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha TEXT NOT NULL,
            tipo TEXT NOT NULL,
            monto REAL NOT NULL,
            motivo TEXT,
            turno TEXT DEFAULT 'Turno 1'
        )
    """)

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
st.markdown(
    f"""
    <div class="header-box">
        <h1>♻️ {emp_nombre}</h1>
        <p>📍 {emp_direccion} | 📞 Cel: {emp_telefono}</p>
    </div>
    """,
    unsafe_allow_html=True,
)

# MENÚ PRINCIPAL
menu = st.sidebar.selectbox(
    "📋 Menú Principal",
    [
        "📝 Registrar Compra (Báscula)",
        "📦 Ver Inventario y Precios",
        "📤 Registrar Venta (Salida)",
        "💵 Control de Caja (Fondo / Entradas)",
        "✂️ Corte de Caja por Turno y Día",
        "💸 Registrar y Administrar Gastos",
        "📊 Reportes (Diario, Semanal, Mensual, Anual)",
        "⚙️ Configuración / Datos Empresa",
    ],
)


# EXPORTAR A EXCEL
def convertir_df_a_excel(df):
  output = io.BytesIO()
  with pd.ExcelWriter(output, engine="openpyxl") as writer:
    df.to_excel(writer, index=False, sheet_name="Reporte")
  return output.getvalue()


# ---------------------------------------------------------
# OPCIÓN 1: BÁSCULA DE COMPRA
# ---------------------------------------------------------
if menu == "📝 Registrar Compra (Báscula)":
  st.subheader("🛒 Registro Rápido de Compra")

  col_t1, col_t2 = st.columns([2, 2])
  with col_t1:
    turno_actual = st.selectbox(
        "⏱️ Turno Actual:",
        ["Turno 1 (Mañana)", "Turno 2 (Tarde)", "Turno Completo"],
    )

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
            cursor.execute(
                "INSERT INTO clientes (nombre, telefono) VALUES (?, ?)",
                (cli_nom, cli_tel),
            )
            conexion.commit()
            st.success("¡Cliente guardado!")
            st.rerun()
          except Exception:
            st.error("El cliente ya existe.")

  st.markdown("---")
  st.write("### ➕ Agregar Material")

  cursor.execute(
      "SELECT id, nombre, precio_compra FROM materiales ORDER BY nombre ASC"
  )
  mats_db = cursor.fetchall()

  if mats_db:
    dict_mats = {m[1]: (m[0], m[2]) for m in mats_db}
    col_m1, col_m2, col_m3 = st.columns([3, 2, 2])
    with col_m1:
      mat_nom = st.selectbox("Material:", list(dict_mats.keys()))
      mat_id, mat_p = dict_mats[mat_nom]
    with col_m2:
      kilos = st.number_input(
          "Kilos (Kg):", min_value=0.0, step=0.5, format="%.2f"
      )
    with col_m3:
      precio = st.number_input(
          "Precio $/Kg:", value=float(mat_p), step=0.5, format="%.2f"
      )

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
              "subtotal": subtotal,
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
    st.dataframe(
        df_car[["material", "kilos", "precio", "subtotal"]].rename(
            columns={
                "material": "Material",
                "kilos": "Kilos (Kg)",
                "precio": "Precio $/Kg",
                "subtotal": "Subtotal ($)",
            }
        ),
        use_container_width=True,
    )

    tot_ticket = sum(i["subtotal"] for i in st.session_state.carrito_compras)

    st.markdown(
        f"""
        <div class="total-card">
            <p style="margin:0; font-weight:bold;">TOTAL A PAGAR</p>
            <h2>${tot_ticket:,.2f} MXN</h2>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.write("")
    if st.button(
        "✅ FINALIZAR Y GENERAR TICKET",
        type="primary",
        use_container_width=True,
    ):
      f_act = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
      cursor.execute(
          "INSERT INTO compras (fecha, cliente, total_pagado, turno) VALUES (?,"
          " ?, ?, ?)",
          (f_act, cliente_sel, tot_ticket, turno_actual),
      )
      c_id = cursor.lastrowid

      for item in st.session_state.carrito_compras:
        cursor.execute(
            "INSERT INTO detalle_compra (compra_id, material_id, kilos,"
            " subtotal) VALUES (?, ?, ?, ?)",
            (c_id, item["material_id"], item["kilos"], item["subtotal"]),
        )
        cursor.execute(
            "UPDATE materiales SET stock_kilos = stock_kilos + ? WHERE id = ?",
            (item["kilos"], item["material_id"]),
        )

      conexion.commit()

      txt_t = f"========================================\n"
      txt_t += f"       {emp_nombre.upper()}             \n"
      txt_t += f"  {emp_direccion}  \n"
      txt_t += f"  Tel: {emp_telefono} \n"
      txt_t += f"========================================\n"
      txt_t += f"Folio: #{c_id} | Fecha: {f_act}\n"
      txt_t += f"Turno: {turno_actual}\n"
      txt_t += f"Cliente: {cliente_sel}\n"
      txt_t += f"----------------------------------------\n"
      for i in st.session_state.carrito_compras:
        txt_t += f"{i['material']:<15} {i['kilos']:<6.1f}kg  ${i['subtotal']:<7.2f}\n"
      txt_t += f"----------------------------------------\n"
      txt_t += f"TOTAL: ${tot_ticket:,.2f}\n"
      txt_t += f"========================================\n"

      st.success(f"¡Compra #{c_id} registrada con éxito!")
      st.text(txt_t)

      st.session_state.carrito_compras = []

      st.download_button(
          label="📄 Descargar Ticket (.TXT)",
          data=txt_t,
          file_name=f"Ticket_{c_id}.txt",
          mime="text/plain",
      )

# ---------------------------------------------------------
# OPCIÓN 2: VER INVENTARIO Y PRECIOS
# ---------------------------------------------------------
elif menu == "📦 Ver Inventario y Precios":
  st.subheader("📦 Inventario Actual")
  cursor.execute(
      "SELECT id, nombre, precio_compra, precio_venta, stock_kilos FROM"
      " materiales"
  )
  mats = cursor.fetchall()
  df_inv = pd.DataFrame(
      mats,
      columns=[
          "ID",
          "Material",
          "Precio Compra ($)",
          "Precio Venta ($)",
          "Stock (Kg)",
      ],
  )
  st.dataframe(df_inv, use_container_width=True)

  excel_data = convertir_df_a_excel(df_inv)
  st.download_button(
      label="🟢 Descargar Inventario en Excel (.xlsx)",
      data=excel_data,
      file_name=f"Inventario_{datetime.now().strftime('%Y%m%d')}.xlsx",
      mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
  )

# ---------------------------------------------------------
# OPCIÓN 3: REGISTRAR VENTA
# ---------------------------------------------------------
elif menu == "📤 Registrar Venta (Salida)":
  st.subheader("📤 Registrar Venta de Material")

  turno_v = st.selectbox(
      "⏱️ Turno:", ["Turno 1 (Mañana)", "Turno 2 (Tarde)", "Turno Completo"]
  )
  comprador = st.text_input("Fundidora / Comprador Final:")

  cursor.execute("SELECT id, nombre, precio_venta, stock_kilos FROM materiales")
  mats_v = cursor.fetchall()

  dict_v = {}
  for m in mats_v:
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
      dict_v[m[0]] = (m[1], kv, m[2], kv * m[2])

  if st.button("Finalizar Venta", type="primary"):
    if not comprador:
      st.error("Ingrese el comprador.")
    elif not dict_v:
      st.error("Seleccione al menos un producto.")
    else:
      f_act = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
      tot_v = sum(x[3] for x in dict_v.values())
      cursor.execute(
          "INSERT INTO ventas (fecha, comprador, total_cobrado, turno) VALUES"
          " (?, ?, ?, ?)",
          (f_act, comprador, tot_v, turno_v),
      )
      v_id = cursor.lastrowid

      for mid, data in dict_v.items():
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
      st.success(f"¡Venta #{v_id} registrada por ${tot_v:,.2f}!")

# ---------------------------------------------------------
# OPCIÓN 4: CONTROL DE CAJA
# ---------------------------------------------------------
elif menu == "💵 Control de Caja (Fondo / Entradas)":
  st.subheader("💵 Fondo e Inyecciones de Caja")

  with st.form("form_caja_in"):
    turno_c = st.selectbox(
        "Turno:", ["Turno 1 (Mañana)", "Turno 2 (Tarde)", "Turno Completo"]
    )
    tipo_m = st.selectbox(
        "Tipo:", ["Fondo Inicial de Caja", "Inyección Extra de Efectivo"]
    )
    monto_m = st.number_input("Monto ($):", min_value=0.0, step=100.0)
    motivo_m = st.text_input("Motivo:")

    if st.form_submit_button("Guardar en Caja"):
      if monto_m > 0:
        f_act = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute(
            "INSERT INTO movimientos_caja (fecha, tipo, monto, motivo, turno)"
            " VALUES (?, ?, ?, ?, ?)",
            (f_act, tipo_m, monto_m, motivo_m, turno_c),
        )
        conexion.commit()
        st.success(f"Se ingresaron ${monto_m:,.2f} a caja en [{turno_c}].")
        st.rerun()

  cursor.execute(
      "SELECT id, fecha, turno, tipo, monto, motivo FROM movimientos_caja ORDER"
      " BY id DESC"
  )
  df_caja_movs = pd.DataFrame(
      cursor.fetchall(),
      columns=["ID", "Fecha", "Turno", "Tipo", "Monto", "Motivo"],
  )
  st.dataframe(df_caja_movs, use_container_width=True)

# ---------------------------------------------------------
# OPCIÓN 5: CORTE DE CAJA POR TURNO Y DÍA
# ---------------------------------------------------------
elif menu == "✂️ Corte de Caja por Turno y Día":
  st.subheader("✂️ Arqueo y Corte de Caja")

  col_f1, col_f2 = st.columns(2)
  with col_f1:
    f_corte = st.date_input("Fecha del Corte:", datetime.now())
  with col_f2:
    filtro_turno = st.selectbox(
        "Filtrar por Turno:",
        [
            "Todos los Turnos (Día Completo)",
            "Turno 1 (Mañana)",
            "Turno 2 (Tarde)",
        ],
    )

  f_i = f_corte.strftime("%Y-%m-%d 00:00:00")
  f_f = f_corte.strftime("%Y-%m-%d 23:59:59")

  # Construir condición SQL según el turno elegido
  cond_turno = ""
  params_t = [f_i, f_f]
  if filtro_turno != "Todos los Turnos (Día Completo)":
    cond_turno = " AND turno = ?"
    params_t.append(filtro_turno)

  cursor.execute(
      f"SELECT SUM(monto) FROM movimientos_caja WHERE fecha >= ? AND fecha <="
      f" ?{cond_turno}",
      params_t,
  )
  tot_ingresado = cursor.fetchone()[0] or 0.0

  cursor.execute(
      f"SELECT SUM(total_cobrado) FROM ventas WHERE fecha >= ? AND fecha <="
      f" ?{cond_turno}",
      params_t,
  )
  tot_ventas = cursor.fetchone()[0] or 0.0

  cursor.execute(
      f"SELECT SUM(total_pagado) FROM compras WHERE fecha >= ? AND fecha <="
      f" ?{cond_turno}",
      params_t,
  )
  tot_compras = cursor.fetchone()[0] or 0.0

  cursor.execute(
      f"SELECT SUM(monto) FROM gastos WHERE fecha >= ? AND fecha <="
      f" ?{cond_turno}",
      params_t,
  )
  tot_gastos = cursor.fetchone()[0] or 0.0

  efectivo_restante = (tot_ingresado + tot_ventas) - (tot_compras + tot_gastos)

  st.markdown(
      f"""
    <div class="total-card">
        <p style="margin:0; font-weight:bold;">EFECTIVO RESTANTE EN CAJA ({filtro_turno.upper()})</p>
        <h2>${efectivo_restante:,.2f} MXN</h2>
    </div>
    """,
      unsafe_allow_html=True,
  )

  st.write("")
  col1, col2, col3, col4 = st.columns(4)
  col1.metric("Fondo/Inyecciones", f"${tot_ingresado:,.2f}")
  col2.metric("Ventas Cobradas", f"${tot_ventas:,.2f}")
  col3.metric("Comprado en Material", f"${tot_compras:,.2f}")
  col4.metric("Gastos Generales", f"${tot_gastos:,.2f}")

  txt_corte = f"========================================\n"
  txt_corte += f"       CORTE DE CAJA ({f_corte})       \n"
  txt_corte += f"       Filtro: {filtro_turno}          \n"
  txt_corte += f"========================================\n"
  txt_corte += f"Fondo / Inyecciones:  ${tot_ingresado:,.2f}\n"
  txt_corte += f"Ventas del Día:       ${tot_ventas:,.2f}\n"
  txt_corte += f"(-) Compras Material: ${tot_compras:,.2f}\n"
  txt_corte += f"(-) Gastos Varios:    ${tot_gastos:,.2f}\n"
  txt_corte += f"----------------------------------------\n"
  txt_corte += f"EFECTIVO EN CAJA:     ${efectivo_restante:,.2f}\n"
  txt_corte += f"========================================\n"

  st.text(txt_corte)
  st.download_button(
      label="📄 Descargar Corte de Caja (.TXT)",
      data=txt_corte,
      file_name=f"Corte_Caja_{f_corte}_{filtro_turno}.txt",
      mime="text/plain",
  )

# ---------------------------------------------------------
# OPCIÓN 6: GASTOS
# ---------------------------------------------------------
elif menu == "💸 Registrar y Administrar Gastos":
  st.subheader("💸 Registro de Gastos")
  with st.form("fgastos"):
    turno_g = st.selectbox(
        "Turno:", ["Turno 1 (Mañana)", "Turno 2 (Tarde)", "Turno Completo"]
    )
    cat = st.selectbox(
        "Categoría:",
        ["Sueldo", "Gasolina", "Mantenimiento", "Luz", "Agua", "Otros"],
    )
    mon = st.number_input("Monto ($):", min_value=0.0)
    des = st.text_input("Descripción:")

    if st.form_submit_button("Guardar Gasto"):
      if mon > 0:
        cursor.execute(
            "INSERT INTO gastos (fecha, categoria, descripcion, monto, turno)"
            " VALUES (?, ?, ?, ?, ?)",
            (
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                cat,
                des,
                mon,
                turno_g,
            ),
        )
        conexion.commit()
        st.success("Gasto registrado.")
        st.rerun()

  cursor.execute(
      "SELECT id, fecha, turno, categoria, descripcion, monto FROM gastos ORDER"
      " BY id DESC"
  )
  df_g = pd.DataFrame(
      cursor.fetchall(),
      columns=["ID", "Fecha", "Turno", "Categoría", "Descripción", "Monto"],
  )
  st.dataframe(df_g, use_container_width=True)

# ---------------------------------------------------------
# OPCIÓN 7: REPORTES (DIARIO, SEMANAL, MENSUAL, ANUAL)
# ---------------------------------------------------------
elif menu == "📊 Reportes (Diario, Semanal, Mensual, Anual)":
  st.subheader("📊 Reportes Financieros y de Utilidad Neta")

  periodo = st.radio(
      "Seleccione el período de consulta:",
      ["Diario (Hoy)", "Semanal", "Mensual", "Anual", "Personalizado"],
      horizontal=True,
  )

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
    f_fin = ahora.strftime("%Y-12-31 23:59:59")
  else:
    col_p1, col_p2 = st.columns(2)
    with col_p1:
      d_i = st.date_input("Fecha Inicio:", ahora - timedelta(days=30))
    with col_p2:
      d_f = st.date_input("Fecha Fin:", ahora)
    f_inicio = d_i.strftime("%Y-%m-%d 00:00:00")
    f_fin = d_f.strftime("%Y-%m-%d 23:59:59")

  cursor.execute(
      "SELECT COUNT(*), SUM(total_pagado) FROM compras WHERE fecha >= ? AND"
      " fecha <= ?",
      (f_inicio, f_fin),
  )
  res_c = cursor.fetchone()
  num_compras = res_c[0] or 0
  tot_compra_dinero = res_c[1] or 0.0

  cursor.execute(
      "SELECT SUM(monto) FROM gastos WHERE fecha >= ? AND fecha <= ?",
      (f_inicio, f_fin),
  )
  tot_gastos_per = cursor.fetchone()[0] or 0.0

  cursor.execute(
      """
        SELECT m.nombre, SUM(d.kilos), SUM(d.subtotal), 
               SUM((m.precio_venta - m.precio_compra) * d.kilos) as utilidad
        FROM detalle_compra d
        JOIN compras c ON d.compra_id = c.id
        JOIN materiales m ON d.material_id = m.id
        WHERE c.fecha >= ? AND c.fecha <= ?
        GROUP BY m.nombre
    """,
      (f_inicio, f_fin),
  )
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
    df_rep = pd.DataFrame(
        mats_rep,
        columns=[
            "Material",
            "Kilos Comprados",
            "Inversión ($)",
            "Utilidad Est. ($)",
        ],
    )
    st.dataframe(df_rep, use_container_width=True)

    excel_rep = convertir_df_a_excel(df_rep)
    st.download_button(
        label=f"🟢 Descargar Reporte ({periodo}) en Excel (.xlsx)",
        data=excel_rep,
        file_name=f"Reporte_{periodo}_{datetime.now().strftime('%Y%m%d')}.xlsx",
        mime=(
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        ),
    )
  else:
    st.info("No hay registros de compras en el período seleccionado.")

# ---------------------------------------------------------
# OPCIÓN 8: CONFIGURACIÓN Y DATOS DE LA EMPRESA
# ---------------------------------------------------------
elif menu == "⚙️ Configuración / Datos Empresa":
  st.subheader("⚙️ Configuración")

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
  st.write("### 🗑️ Eliminar Materiales")
  cursor.execute("SELECT id, nombre FROM materiales")
  mats_all = cursor.fetchall()
  if mats_all:
    mat_del = st.selectbox("Material:", [m[1] for m in mats_all])
    if st.button("🗑️ Borrar Material"):
      cursor.execute("DELETE FROM materiales WHERE nombre = ?", (mat_del,))
      conexion.commit()
      st.error(f"Material '{mat_del}' eliminado.")
      st.rerun()

conexion.close()
