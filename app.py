from datetime import datetime, timedelta
import os
import sqlite3
import pandas as pd
import streamlit as st

# Configuración de la página
st.set_page_config(
    page_title="ERP Recicladora de Metales", page_icon="♻️", layout="wide"
)


# Ruta de la base de datos local
def obtener_conexion():
  ruta_bd = os.path.expanduser("~/recicladora.db")
  return sqlite3.connect(ruta_bd)


# Inicializar base de datos si no existe
def inicializar_bd():
  conexion = obtener_conexion()
  cursor = conexion.cursor()
  cursor.execute(
      """
        CREATE TABLE IF NOT EXISTS materiales (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            precio_compra REAL NOT NULL,
            precio_venta REAL DEFAULT 0.0,
            stock_kilos REAL DEFAULT 0.0
        )
    """
  )
  cursor.execute(
      """
        CREATE TABLE IF NOT EXISTS compras (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha TEXT NOT NULL,
            cliente TEXT NOT NULL,
            total_pagado REAL NOT NULL
        )
    """
  )
  cursor.execute(
      """
        CREATE TABLE IF NOT EXISTS detalle_compra (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            compra_id INTEGER,
            material_id INTEGER,
            kilos REAL NOT NULL,
            subtotal REAL NOT NULL
        )
    """
  )
  cursor.execute(
      """
        CREATE TABLE IF NOT EXISTS ventas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha TEXT NOT NULL,
            comprador TEXT NOT NULL,
            total_cobrado REAL NOT NULL
        )
    """
  )
  cursor.execute(
      """
        CREATE TABLE IF NOT EXISTS detalle_venta (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            venta_id INTEGER,
            material_id INTEGER,
            kilos REAL NOT NULL,
            subtotal REAL NOT NULL
        )
    """
  )
  cursor.execute(
      """
        CREATE TABLE IF NOT EXISTS gastos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha TEXT NOT NULL,
            categoria TEXT NOT NULL,
            descripcion TEXT,
            monto REAL NOT NULL
        )
    """
  )
  # Nueva tabla para la caja y entradas de dinero (Fondo inicial / Inyecciones)
  cursor.execute(
      """
        CREATE TABLE IF NOT EXISTS movimientos_caja (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha TEXT NOT NULL,
            tipo TEXT NOT NULL,
            monto REAL NOT NULL,
            motivo TEXT
        )
    """
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

# --- INTERFAZ GRÁFICA CON STREAMLIT ---
st.title("♻️ Sistema ERP - Recicladora de Metales")

# Menú lateral ampliado con la opción de Caja y Corte
menu = st.sidebar.selectbox(
    "Menú Principal",
    [
        "Ver Inventario y Precios",
        "Registrar Nueva Compra",
        "Registrar Venta (Salida)",
        "Control de Caja (Fondo y Entradas)",
        "Corte de Caja Diario",
        "Registrar y Administrar Gastos",
        "Reportes de Compras y Utilidad",
        "Ajustar Precios y Materiales",
    ],
)

conexion = obtener_conexion()
cursor = conexion.cursor()

# ---------------------------------------------------------
# OPCIÓN 1: VER INVENTARIO
# ---------------------------------------------------------
if menu == "Ver Inventario y Precios":
  st.subheader("📦 Inventario Actual y Precios en Bodega")
  cursor.execute(
      "SELECT id, nombre, precio_compra, precio_venta, stock_kilos FROM"
      " materiales"
  )
  materiales = cursor.fetchall()

  df = pd.DataFrame(
      materiales,
      columns=[
          "ID",
          "Material",
          "Precio Compra ($)",
          "Precio Venta ($)",
          "Stock en Bodega (Kg)",
      ],
  )
  st.dataframe(df, use_container_width=True)

# ---------------------------------------------------------
# OPCIÓN 2: REGISTRAR COMPRA
# ---------------------------------------------------------
elif menu == "Registrar Nueva Compra":
  st.subheader("📝 Registrar Nueva Compra de Material")

  cursor.execute("SELECT id, nombre, precio_compra, stock_kilos FROM materiales")
  materiales = cursor.fetchall()

  cliente = st.text_input("Nombre del Proveedor / Cliente:")

  st.markdown("---")
  st.write("### Seleccione los materiales y kilos a comprar:")

  compras_usuario = {}
  for m in materiales:
    col1, col2, col3 = st.columns([2, 2, 2])
    with col1:
      st.write(f"**{m[1]}** (Compra: ${m[2]:.2f}/kg)")
    with col2:
      kilos = st.number_input(
          f"Kilos de {m[1]}", min_value=0.0, step=0.5, key=f"mat_c_{m[0]}"
      )
    with col3:
      subtotal = kilos * m[2]
      st.write(f"Subtotal: **${subtotal:.2f}**")

    if kilos > 0:
      compras_usuario[m[0]] = (m[1], kilos, m[2], subtotal)

  if st.button("Finalizar y Generar Ticket de Compra", type="primary"):
    if not cliente:
      st.error("⚠️ Por favor ingrese el nombre del proveedor.")
    elif not compras_usuario:
      st.error("⚠️ Debe agregar al menos un material con cantidad mayor a 0 kilos.")
    else:
      fecha_actual = datetime.now().strftime("%Y-%m-%d %H:%M")
      total_general = sum(item[3] for item in compras_usuario.values())

      cursor.execute(
          "INSERT INTO compras (fecha, cliente, total_pagado) VALUES (?, ?, ?)",
          (fecha_actual, cliente, total_general),
      )
      compra_id = cursor.lastrowid

      for mat_id, data in compras_usuario.items():
        nombre_mat, kilos, precio, subtotal = data
        cursor.execute(
            "INSERT INTO detalle_compra (compra_id, material_id, kilos,"
            " subtotal) VALUES (?, ?, ?, ?)",
            (compra_id, mat_id, kilos, subtotal),
        )
        cursor.execute(
            "UPDATE materiales SET stock_kilos = stock_kilos + ? WHERE id = ?",
            (kilos, mat_id),
        )

      conexion.commit()

      texto_ticket = "=" * 40 + "\n"
      texto_ticket += " TICKET DE COMPRA - RECICLADORA \n"
      texto_ticket += "=" * 40 + "\n"
      texto_ticket += f"Folio: #{compra_id} | Fecha: {fecha_actual}\n"
      texto_ticket += f"Proveedor: {cliente}\n"
      texto_ticket += "-" * 40 + "\n"
      for data in compras_usuario.values():
        texto_ticket += (
            f"{data[0]:<15} {data[1]:<6.1f}kg  ${data[3]:<7.2f}\n"
        )
      texto_ticket += "-" * 40 + "\n"
      texto_ticket += f"TOTAL A PAGAR: ${total_general:.2f}\n"
      texto_ticket += "=" * 40 + "\n"

      try:
        carpeta_tickets = os.path.expanduser("~/Desktop/Tickets_Recicladora")
        os.makedirs(carpeta_tickets, exist_ok=True)
        nombre_archivo = os.path.join(
            carpeta_tickets, f"Ticket_Compra_{compra_id}.txt"
        )
        with open(nombre_archivo, "w", encoding="utf-8") as f:
          f.write(texto_ticket)
      except Exception:
        pass

      st.success(f"¡Compra registrada con éxito! Folio #{compra_id}")
      st.text(texto_ticket)

      st.download_button(
          label="📄 Descargar / Imprimir Ticket de Compra",
          data=texto_ticket,
          file_name=f"Ticket_Compra_{compra_id}.txt",
          mime="text/plain",
      )

# ---------------------------------------------------------
# OPCIÓN 3: REGISTRAR VENTA (SALIDA DE MATERIAL)
# ---------------------------------------------------------
elif menu == "Registrar Venta (Salida)":
  st.subheader("📤 Registrar Venta / Salida de Material de Bodega")

  cursor.execute("SELECT id, nombre, precio_venta, stock_kilos FROM materiales")
  materiales = cursor.fetchall()

  comprador = st.text_input("Nombre de la Fundidora / Comprador Final:")

  st.markdown("---")
  st.write("### Seleccione los kilos a vender / descontar del inventario:")

  ventas_usuario = {}
  for m in materiales:
    stock_actual = m[3]
    col1, col2, col3 = st.columns([2, 2, 2])
    with col1:
      st.write(
          f"**{m[1]}**\n\n*(Disponibles:"
          f" {stock_actual:.1f} kg)*\n\n*(P. Venta: ${m[2]:.2f}/kg)*"
      )
    with col2:
      kilos_venta = st.number_input(
          f"Kilos a vender de {m[1]}",
          min_value=0.0,
          max_value=float(stock_actual),
          step=0.5,
          key=f"mat_v_{m[0]}",
      )
    with col3:
      subtotal_venta = kilos_venta * m[2]
      st.write(f"Subtotal Venta: **${subtotal_venta:.2f}**")

    if kilos_venta > 0:
      ventas_usuario[m[0]] = (m[1], kilos_venta, m[2], subtotal_venta)

  if st.button("Finalizar Venta y Actualizar Inventario", type="primary"):
    if not comprador:
      st.error("⚠️ Por favor ingrese el nombre del comprador o fundidora.")
    elif not ventas_usuario:
      st.error(
          "⚠️ Debe seleccionar al menos un material con cantidad mayor a 0"
          " kilos."
      )
    else:
      fecha_actual = datetime.now().strftime("%Y-%m-%d %H:%M")
      total_general_venta = sum(item[3] for item in ventas_usuario.values())

      cursor.execute(
          "INSERT INTO ventas (fecha, comprador, total_cobrado) VALUES (?, ?,"
          " ?)",
          (fecha_actual, comprador, total_general_venta),
      )
      venta_id = cursor.lastrowid

      for mat_id, data in ventas_usuario.items():
        nombre_mat, kilos, precio, subtotal = data
        cursor.execute(
            "INSERT INTO detalle_venta (venta_id, material_id, kilos,"
            " subtotal) VALUES (?, ?, ?, ?)",
            (venta_id, mat_id, kilos, subtotal),
        )
        cursor.execute(
            "UPDATE materiales SET stock_kilos = stock_kilos - ? WHERE id = ?",
            (kilos, mat_id),
        )

      conexion.commit()

      texto_salida = "=" * 40 + "\n"
      texto_salida += " TICKET DE SALIDA / VENTA DE MATERIAL\n"
      texto_salida += "=" * 40 + "\n"
      texto_salida += f"Folio Venta: #{venta_id} | Fecha: {fecha_actual}\n"
      texto_salida += f"Comprador: {comprador}\n"
      texto_salida += "-" * 40 + "\n"
      for data in ventas_usuario.values():
        texto_salida += (
            f"{data[0]:<15} {data[1]:<6.1f}kg  ${data[3]:<7.2f}\n"
        )
      texto_salida += "-" * 40 + "\n"
      texto_salida += f"TOTAL COBRADO: ${total_general_venta:.2f}\n"
      texto_salida += "=" * 40 + "\n"

      try:
        carpeta_tickets = os.path.expanduser("~/Desktop/Tickets_Recicladora")
        os.makedirs(carpeta_tickets, exist_ok=True)
        nombre_archivo = os.path.join(
            carpeta_tickets, f"Ticket_Venta_{venta_id}.txt"
        )
        with open(nombre_archivo, "w", encoding="utf-8") as f:
          f.write(texto_salida)
      except Exception:
        pass

      st.success(
          f"¡Venta registrada con éxito y stock descontado! Folio #{venta_id}"
      )
      st.text(texto_salida)

      st.download_button(
          label="📄 Descargar / Imprimir Ticket de Venta",
          data=texto_salida,
          file_name=f"Ticket_Venta_{venta_id}.txt",
          mime="text/plain",
      )

# ---------------------------------------------------------
# OPCIÓN 4: CONTROL DE CAJA (FONDO INICIAL E INYECCIONES)
# ---------------------------------------------------------
elif menu == "Control de Caja (Fondo y Entradas)":
  st.subheader("💵 Control de Fondo y Entradas de Dinero a Caja")
  st.write(
      "Registra aquí el dinero base con el que arranca la caja o las"
      " inyecciones adicionales si se necesita más efectivo durante el día."
  )

  with st.form("form_caja"):
    tipo_movimiento = st.selectbox(
        "Tipo de Movimiento de Efectivo:",
        ["Fondo Inicial de Caja", "Inyección Extra de Dinero"],
    )
    monto_caja = st.number_input(
        "Monto ($):", min_value=0.0, step=100.0, format="%.2f"
    )
    motivo_caja = st.text_input(
        "Motivo o Descripción (Ej. Cambio inicial, Relleno de efectivo de"
        " emergencia):"
    )

    btn_caja = st.form_submit_button("Registrar Movimiento de Caja")
    if btn_caja:
      if monto_caja <= 0:
        st.error("⚠️ El monto debe ser mayor a 0.")
      else:
        fecha_actual = datetime.now().strftime("%Y-%m-%d %H:%M")
        cursor.execute(
            "INSERT INTO movimientos_caja (fecha, tipo, monto, motivo) VALUES"
            " (?, ?, ?, ?)",
            (fecha_actual, tipo_movimiento, monto_caja, motivo_caja),
        )
        conexion.commit()
        st.success(
            f"¡Se registró correctamente el movimiento de ${monto_caja:,.2f}!"
        )
        st.rerun()

  st.markdown("---")
  st.write("### Historial de Movimientos de Caja Registrados")
  cursor.execute(
      "SELECT id, fecha, tipo, monto, motivo FROM movimientos_caja ORDER BY id"
      " DESC"
  )
  movimientos = cursor.fetchall()

  if movimientos:
    for mov in movimientos:
      col_m1, col_m2, col_m3, col_m4, col_m5 = st.columns(
          [1, 2, 2, 2, 1]
      )
      with col_m1:
        st.write(f"#{mov[0]}")
      with col_m2:
        st.write(f"📅 {mov[1]}")
      with col_m3:
        st.write(f"📌 **{mov[2]}**")
      with col_m4:
        st.write(f"💰 **${mov[3]:,.2f}** ({mov[4] if mov[4] else 'Sin detalle'})")
      with col_m5:
        if st.button("🗑️ Borrar", key=f"del_mov_{mov[0]}"):
          cursor.execute(
              "DELETE FROM movimientos_caja WHERE id = ?", (mov[0],)
          )
          conexion.commit()
          st.success("Movimiento eliminado.")
          st.rerun()
  else:
    st.info(
        "No hay registros de fondo inicial o inyecciones de caja todavía."
    )

# ---------------------------------------------------------
# OPCIÓN 5: CORTE DE CAJA DIARIO (EFECTIVO DISPONIBLE)
# ---------------------------------------------------------
elif menu == "Corte de Caja Diario":
  st.subheader("✂️ Corte de Caja Diario (Dinero en Efectivo Actual)")
  st.write(
      "Aquí puedes hacer el corte para saber exactamente cuánto dinero te"
      " queda en la caja restando las compras y gastos al dinero ingresado."
  )

  # Selector de fecha para el corte (Por defecto hoy)
  fecha_corte = st.date_input("Selecciona la fecha para el corte:", datetime.now())
  f_inicio = fecha_corte.strftime("%Y-%m-%d 00:00")
  f_fin = fecha_corte.strftime("%Y-%m-%d 23:59")

  # 1. Sumar Fondo Inicial e Inyecciones del día
  cursor.execute(
      "SELECT SUM(monto) FROM movimientos_caja WHERE fecha BETWEEN ? AND ?",
      (f_inicio, f_fin),
  )
  res_caja = cursor.fetchone()
  total_ingresado_caja = res_caja[0] if res_caja[0] else 0.0

  # 2. Sumar Ventas cobradas (si las hay, por si entra dinero por venta)
  cursor.execute(
      "SELECT SUM(total_cobrado) FROM ventas WHERE fecha BETWEEN ? AND ?",
      (f_inicio, f_fin),
  )
  res_ventas = cursor.fetchone()
  total_ventas_dia = res_ventas[0] if res_ventas[0] else 0.0

  # Dinero Total Disponible en Efectivo (Fondo + Inyecciones + Ventas)
  efectivo_total_disponible = total_ingresado_caja + total_ventas_dia

  # 3. Sumar Compras realizadas (Efectivo gastado comprando material)
  cursor.execute(
      "SELECT SUM(total_pagado), COUNT(*) FROM compras WHERE fecha BETWEEN ? AND"
      " ?",
      (f_inicio, f_fin),
  )
  res_compras_dia = cursor.fetchone()
  total_comprado_dia = res_compras_dia[0] if res_compras_dia[0] else 0.0
  cant_tickets_compra = res_compras_dia[1] if res_compras_dia[1] else 0

  # 4. Sumar Gastos operativos del día
  cursor.execute(
      "SELECT SUM(monto) FROM gastos WHERE fecha BETWEEN ? AND ?",
      (f_inicio, f_fin),
  )
  res_gastos_dia = cursor.fetchone()
  total_gastos_dia = res_gastos_dia[0] if res_gastos_dia[0] else 0.0

  # Dinero que queda en caja: (Disponible) - (Compras de material) - (Gastos)
  efectivo_restante_en_caja = (
      efectivo_total_disponible - total_comprado_dia - total_gastos_dia
  )

  st.markdown("---")
  col_c1, col_c2, col_c3 = st.columns(3)
  col_c1.metric(
      "💵 Dinero Ingresado (Fondo + Inyecciones)",
      f"${total_ingresado_caja:,.2f}",
  )
  col_c2.metric("📦 Total Pagado en Compras", f"${total_comprado_dia:,.2f}")
  col_c3.metric("💸 Total en Gastos", f"${total_gastos_dia:,.2f}")

  st.markdown("---")
  # Tarjeta grande destacando el dinero restante en caja
  st.markdown(
      f"""
    <div style="padding: 20px; border-radius: 10px; background-color: #1E293B; text-align: center; border: 2px solid #38BDF8;">
        <h3 style="color: #38BDF8; margin: 0;">Efectivo que Debe Haber en Caja</h3>
        <h1 style="color: #F8FAFC; font-size: 45px; margin: 10px 0;">${efectivo_restante_en_caja:,.2f}</h1>
        <p style="color: #94A3B8; margin: 0;">Calculado: (Fondo/Inyecciones + Ventas) - (Compras + Gastos)</p>
    </div>
    """,
      unsafe_allow_html=True,
  )

  st.markdown("---")
  st.write("### Detalle de Movimientos del Día")
  st.write(f"- **Tickets de compra realizados:** {cant_tickets_compra}")
  st.write(f"- **Total invertido en material:** ${total_comprado_dia:,.2f}")

  # Botón para descargar reporte de corte
  texto_corte = "=" * 45 + "\n"
  texto_corte += f"           CORTE DE CAJA ({fecha_corte})          \n"
  texto_corte += "=" * 45 + "\n"
  texto_corte += f"Fondo / Inyecciones Caja:  ${total_ingresado_caja:,.2f}\n"
  texto_corte += f"Ventas Cobradas:           ${total_ventas_dia:,.2f}\n"
  texto_corte += f"Total Compras (Material):  ${total_comprado_dia:,.2f}\n"
  texto_corte += f"Total Gastos Operativos:   ${total_gastos_dia:,.2f}\n"
  texto_corte += "-" * 45 + "\n"
  texto_corte += (
      f"EFECTIVO RESTANTE EN CAJA: ${efectivo_restante_en_caja:,.2f}\n"
  )
  texto_corte += "=" * 45 + "\n"

  st.download_button(
      label="📄 Descargar / Imprimir Corte de Caja",
      data=texto_corte,
      file_name=f"Corte_Caja_{fecha_corte}.txt",
      mime="text/plain",
  )

# ---------------------------------------------------------
# OPCIÓN 6: REGISTRAR Y ADMINISTRAR GASTOS
# ---------------------------------------------------------
elif menu == "Registrar y Administrar Gastos":
  st.subheader("💸 Registro y Administración de Gastos")

  categorias = [
      "Sueldo",
      "Gasolina",
      "Mantenimiento",
      "Luz",
      "Agua",
      "Arrendamiento",
      "Comida",
      "Extraordinario",
  ]

  with st.form("form_gastos"):
    col1, col2 = st.columns(2)
    with col1:
      categoria_gasto = st.selectbox("Categoría de Gasto:", categorias)
      monto_gasto = st.number_input("Monto del Gasto ($):", min_value=0.0, step=10.0)
    with col2:
      descripcion_gasto = st.text_input("Descripción o Detalle (Opcional):")

    submitted = st.form_submit_button("Guardar Gasto", type="primary")
    if submitted:
      if monto_gasto <= 0:
        st.error("⚠️ El monto del gasto debe ser mayor a 0.")
      else:
        fecha_actual = datetime.now().strftime("%Y-%m-%d %H:%M")
        cursor.execute(
            "INSERT INTO gastos (fecha, categoria, descripcion, monto) VALUES"
            " (?, ?, ?, ?)",
            (fecha_actual, categoria_gasto, descripcion_gasto, monto_gasto),
        )
        conexion.commit()
        st.success(
            f"¡Gasto de ${monto_gasto:,.2f} en [{categoria_gasto}] registrado"
            " correctamente!"
        )
        st.rerun()

  st.markdown("---")
  st.write("### Historial de Gastos y Eliminación de Errores")
  cursor.execute(
      "SELECT id, fecha, categoria, descripcion, monto FROM gastos ORDER BY id"
      " DESC"
  )
  gastos_todos = cursor.fetchall()

  if gastos_todos:
    st.write("Selecciona el gasto que deseas eliminar si hubo algún error:")
    for g in gastos_todos:
      col_info1, col_info2, col_info3, col_info4, col_btn = st.columns(
          [1, 2, 2, 2, 1]
      )
      with col_info1:
        st.write(f"#{g[0]}")
      with col_info2:
        st.write(f"📅 {g[1]}")
      with col_info3:
        st.write(f"🏷️ **{g[2]}** (${g[4]:,.2f})")
      with col_info4:
        st.write(f"💬 {g[3] if g[3] else 'Sin descripción'}")
      with col_btn:
        if st.button("🗑️ Borrar", key=f"del_gasto_{g[0]}"):
          cursor.execute("DELETE FROM gastos WHERE id = ?", (g[0],))
          conexion.commit()
          st.success(f"¡Gasto #{g[0]} eliminado con éxito!")
          st.rerun()
  else:
    st.info("Aún no hay gastos registrados.")

# ---------------------------------------------------------
# OPCIÓN 7: REPORTES DE COMPRAS Y UTILIDAD
# ---------------------------------------------------------
elif menu == "Reportes de Compras y Utilidad":
  st.subheader("📊 Reportes Financieros y Utilidad Neta por Período")

  filtro_periodo = st.radio(
      "Seleccione el período a consultar:",
      ["Hoy", "Esta Semana", "Este Mes", "Este Año"],
      horizontal=True,
  )

  ahora = datetime.now()
  if filtro_periodo == "Hoy":
    fecha_inicio = ahora.strftime("%Y-%m-%d 00:00")
  elif filtro_periodo == "Esta Semana":
    inicio_semana = ahora - timedelta(days=7)
    fecha_inicio = inicio_semana.strftime("%Y-%m-%d 00:00")
  elif filtro_periodo == "Este Mes":
    fecha_inicio = ahora.strftime("%Y-%m-01 00:00")
  elif filtro_periodo == "Este Año":
    fecha_inicio = ahora.strftime("%Y-01-01 00:00")

  fecha_fin = ahora.strftime("%Y-%m-%d 23:59")

  cursor.execute(
      "SELECT COUNT(*), SUM(total_pagado) FROM compras WHERE fecha BETWEEN ? AND"
      " ?",
      (fecha_inicio, fecha_fin),
  )
  res_compras = cursor.fetchone()
  total_tickets = res_compras[0] if res_compras[0] else 0
  total_efectivo = res_compras[1] if res_compras[1] else 0.0

  cursor.execute(
      """
        SELECT m.nombre, SUM(d.kilos), SUM(d.subtotal), 
               SUM(d.kilos * m.precio_venta) as total_venta_est,
               SUM((m.precio_venta - m.precio_compra) * d.kilos) as utilidad_est
        FROM detalle_compra d
        JOIN compras c ON d.compra_id = c.id
        JOIN materiales m ON d.material_id = m.id
        WHERE c.fecha BETWEEN ? AND ?
        GROUP BY m.nombre
    """,
      (fecha_inicio, fecha_fin),
  )
  resultados = cursor.fetchall()
  utilidad_bruta = sum(r[4] for r in resultados) if resultados else 0.0

  cursor.execute(
      "SELECT SUM(monto) FROM gastos WHERE fecha BETWEEN ? AND ?",
      (fecha_inicio, fecha_fin),
  )
  res_gastos = cursor.fetchone()
  total_gastos = res_gastos[0] if res_gastos[0] else 0.0

  utilidad_neta = utilidad_bruta - total_gastos

  st.markdown("---")
  col1, col2, col3, col4, col5 = st.columns(5)
  col1.metric("Tickets Compra", total_tickets)
  col2.metric("Inversión", f"${total_efectivo:,.2f}")
  col3.metric("Utilidad Bruta", f"${utilidad_bruta:,.2f}")
  col4.metric("Total Gastos", f"${total_gastos:,.2f}")
  col5.metric(
      "Utilidad Neta Real", f"${utilidad_neta:,.2f}", delta_color="normal"
  )

  st.markdown("---")
  st.write(f"### Desglose de Compras y Balance ({filtro_periodo})")
  if resultados:
    df_rep = pd.DataFrame(
        resultados,
        columns=[
            "Material",
            "Kilos Comprados",
            "Inversión ($)",
            "Venta Est. ($)",
            "Utilidad Bruta ($)",
        ],
    )
    st.dataframe(df_rep, use_container_width=True)

    cursor.execute(
        "SELECT categoria, descripcion, monto, fecha FROM gastos WHERE fecha"
        " BETWEEN ? AND ?",
        (fecha_inicio, fecha_fin),
    )
    gastos_periodo = cursor.fetchall()
    if gastos_periodo:
      st.write(f"### Gastos Registrados en el Período")
      df_gp = pd.DataFrame(
          gastos_periodo, columns=["Categoría", "Descripción", "Monto ($)", "Fecha"]
      )
      st.dataframe(df_gp, use_container_width=True)

    texto_reporte = "=" * 45 + "\n"
    texto_reporte += f"     REPORTE FINANCIERO ({filtro_periodo.upper()})     \n"
    texto_reporte += f"Generado: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
    texto_reporte += "=" * 45 + "\n"
    texto_reporte += f"Tickets de Compra:    {total_tickets}\n"
    texto_reporte += f"Efectivo Invertido:   ${total_efectivo:,.2f}\n"
    texto_reporte += f"Utilidad Bruta:       ${utilidad_bruta:,.2f}\n"
    texto_reporte += f"Total Gastos:         ${total_gastos:,.2f}\n"
    texto_reporte += f"UTILIDAD NETA REAL:   ${utilidad_neta:,.2f}\n"
    texto_reporte += "-" * 45 + "\n"
    texto_reporte += "DESGLOSE DE COMPRAS:\n"
    texto_reporte += "-" * 45 + "\n"
    for r in resultados:
      texto_reporte += (
          f"{r[0]:<15} | Kg: {r[1]:<6.1f} | Ut: ${r[4]:<7.2f}\n"
      )
    texto_reporte += "=" * 45 + "\n"

    st.download_button(
        label=f"📄 Descargar / Imprimir Reporte ({filtro_periodo})",
        data=texto_reporte,
        file_name=(
            f"Reporte_Financiero_{filtro_periodo}_{datetime.now().strftime('%Y-%m-%d')}.txt"
        ),
        mime="text/plain",
    )
  else:
    st.info(
        f"No hay compras registradas en el período seleccionado"
        f" ({filtro_periodo}), pero los gastos del período suman:"
        f" ${total_gastos:,.2f}."
    )

# ---------------------------------------------------------
# OPCIÓN 8: AJUSTAR PRECIOS, MODIFICAR O ELIMINAR MATERIALES
# ---------------------------------------------------------
elif menu == "Ajustar Precios y Materiales":
  st.subheader(
      "⚙️ Configuración, Modificación y Eliminación de Materiales y Precios"
  )

  st.write("### Actualizar Precios Existentes")
  cursor.execute("SELECT id, nombre, precio_compra, precio_venta FROM materiales")
  materiales_edit = cursor.fetchall()

  for mat in materiales_edit:
    col1, col2, col3, col4 = st.columns([2, 2, 2, 2])
    with col1:
      st.write(f"**{mat[1]}** (ID: {mat[0]})")
    with col2:
      nuevo_p_compra = st.number_input(
          f"P. Compra", value=float(mat[2]), step=1.0, key=f"pc_{mat[0]}"
      )
    with col3:
      nuevo_p_venta = st.number_input(
          f"P. Venta", value=float(mat[3]), step=1.0, key=f"pv_{mat[0]}"
      )
    with col4:
      if st.button("Guardar", key=f"btn_{mat[0]}"):
        cursor.execute(
            "UPDATE materiales SET precio_compra = ?, precio_venta = ? WHERE id"
            " = ?",
            (nuevo_p_compra, nuevo_p_venta, mat[0]),
        )
        conexion.commit()
        st.success(f"¡Precios de {mat[1]} actualizados!")
        st.rerun()

  st.markdown("---")
  st.write("### 🗑️ Eliminar Material Agregado por Error")
  if materiales_edit:
    mat_a_borrar = st.selectbox(
        "Selecciona el material que deseas eliminar por completo de la"
        " base de datos:",
        [m[1] for m in materiales_edit],
    )
    if st.button("Eliminar Material Seleccionado", type="secondary"):
      cursor.execute(
          "DELETE FROM materiales WHERE nombre = ?", (mat_a_borrar,)
      )
      conexion.commit()
      st.error(f"El material '{mat_a_borrar}' ha sido borrado.")
      st.rerun()

  st.markdown("---")
  st.write("### ➕ Agregar Nuevo Material")
  col_n1, col_n2, col_n3 = st.columns(3)
  with col_n1:
    nuevo_nombre = st.text_input("Nombre del Material:")
  with col_n2:
    nuevo_compra_add = st.number_input(
        "Precio Compra ($/kg):", min_value=0.0, step=1.0
    )
  with col_n3:
    nuevo_venta_add = st.number_input(
        "Precio Venta ($/kg):", min_value=0.0, step=1.0
    )

  if st.button("Añadir Material", type="primary"):
    if nuevo_nombre:
      cursor.execute(
          "INSERT INTO materiales (nombre, precio_compra, precio_venta,"
          " stock_kilos) VALUES (?, ?, ?, 0.0)",
          (nuevo_nombre, nuevo_compra_add, nuevo_venta_add),
      )
      conexion.commit()
      st.success(f"¡Material '{nuevo_nombre}' agregado con éxito!")
      st.rerun()
    else:
      st.error("Por favor escribe el nombre del material.")

conexion.close()
