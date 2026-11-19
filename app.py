import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime
import os
from database import init_db

# Configuración inicial de Streamlit
st.set_page_config(page_title="Control General de Turno - EOSR", layout="wide")

# Inicialización de la base de datos
init_db()

def get_connection():
    return sqlite3.connect('operaciones_terminal.db')

def exportar_y_guardar_excel():
    """Lee las tablas de SQLite y las guarda en un libro consolidado de Excel."""
    conn = get_connection()
    try:
        df_cabecera = pd.read_sql_query("SELECT * FROM cabecera_turno", conn)
        df_equipos = pd.read_sql_query("SELECT * FROM control_equipos", conn)
        df_trenes = pd.read_sql_query("SELECT * FROM registro_trenes", conn)
        df_lineas = pd.read_sql_query("SELECT * FROM control_lineas", conn)
        df_tractores = pd.read_sql_query("SELECT * FROM tractores_radios", conn)
        
        with pd.ExcelWriter('Consolidado_Operaciones_EOSR.xlsx', engine='openpyxl') as writer:
            df_cabecera.to_excel(writer, sheet_name='Cabecera_Turnos', index=False)
            df_equipos.to_excel(writer, sheet_name='Control_Equipos', index=False)
            df_trenes.to_excel(writer, sheet_name='Registro_Trenes', index=False)
            df_lineas.to_excel(writer, sheet_name='Control_Lineas', index=False)
            df_tractores.to_excel(writer, sheet_name='Tractores_Radios', index=False)
            
        return True
    except Exception as e:
        st.error(f"Error al exportar a Excel: {e}")
        return False
    finally:
        conn.close()

st.title("🚆 Control Operativo de Turno (EOSR)")

# Pestañas principales
tab_nuevo, tab_kpi, tab_registros = st.tabs(["📝 Llenar Reporte de Turno", "📊 KPIs y Rendimiento", "📂 Histórico y Descargas"])

# ==========================================
# --- TAB 1: FORMULARIO COMPLETO DE TURNO ---
# ==========================================
with tab_nuevo:
    st.subheader("1. Información General del Turno")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        terminal = st.selectbox("Terminal", ["PACIFICO", "ATLANTICO"])
        fecha = st.date_input("Día", datetime.now())
    with col2:
        horario = st.selectbox("Horario/Turno", ["16:00 a 23:59", "00:00 a 08:00", "08:00 a 16:00"])
    with col3:
        hora_desde = st.time_input("Desde", datetime.strptime("16:00", "%H:%M"))
        hora_hasta = st.time_input("Hasta", datetime.strptime("23:59", "%H:%M"))
    with col4:
        supervisor = st.text_input("Supervisor en Turno", placeholder="Ej: J.L.G")

    st.markdown("---")

    # SECCIÓN EQUIPOS DINÁMICOS CON SELECTOR SI/NO COMPACTO
    st.subheader(f"2. Equipos del Terminal ({terminal})")
    
    equipos_pit = [
        ("R1 MJ 850P", "PIT"), ("R2 MJ 900P", "PIT"), ("R3 MJ 900P", "PIT"), 
        ("R7 MJ 900P", "PIT"), ("FANTUZY 1", "PIT"), ("T3 - TAYLOR 974BIG", "PIT"), 
        ("T4 - TAYLOR 974BIG", "PIT"), ("T7 - TAYLOR 974BIG", "PIT"), ("T9 - TAYLOR 974 BIG", "PIT")
    ]
    
    equipos_ait = [
        ("R5 MJ 900P", "AIT"), ("R6 MJ 900P", "AIT"), ("R8 MJ 900P", "AIT"), 
        ("M - 1", "AIT"), ("T5 - TAYLOR 974BIG", "AIT"), ("T6 - TAYLOR 974BIG", "AIT"), 
        ("T8 - TAYLOR 974BIG", "AIT")
    ]
    
    equipos_veh = [("VEH 1", "VEH"), ("VEH 2", "VEH"), ("VEH 3", "VEH"), ("VEH 4", "VEH")]

    if terminal == "PACIFICO":
        lista_equipos_activa = equipos_pit + equipos_veh
    else:
        lista_equipos_activa = equipos_ait + equipos_veh

    equipos_data = []
    conteo_disponibles = 0

    with st.expander(f"Ver y Modificar Estado de Equipos - {terminal}", expanded=True):
        st.write("##### Registro de Disponibilidad, Tiempos de Falla/Reparación y Gaseo")
        
        for eq_key, eq_codigo in lista_equipos_activa:
            if eq_codigo == "VEH":
                col_title1, col_title2, col_disp_v = st.columns([1, 2, 1])
                col_title1.markdown(f"**{eq_codigo}**")
                eq_nombre = col_title2.text_input("Número/ID de Vehículo", placeholder="Ej: 336", key=f"name_{eq_key}")
                disp = col_disp_v.selectbox("Disponible", ["SI", "NO"], key=f"disp_{eq_key}")
            else:
                st.markdown(f"**{eq_codigo} - {eq_key}**")
                eq_nombre = eq_key
                
                # Se coloca el selector de disponibilidad en una columna compacta (ancho 1/4)
                col_d, col_v = st.columns([1, 3])
                disp = col_d.selectbox(f"Disponibilidad", ["SI", "NO"], key=f"disp_{eq_key}")

            if disp == "SI":
                conteo_disponibles += 1

            # Alineación horizontal pareja para los tiempos de falla y reparación
            col_f1, col_f2, col_f3, col_f4 = st.columns(4)
            f_operador = col_f1.text_input("Falla Operador (Hora)", key=f"fop_{eq_key}", placeholder="HH:MM")
            f_mecanico = col_f2.text_input("Falla Mecánico (Hora)", key=f"fmec_{eq_key}", placeholder="HH:MM")
            f_desp = col_f3.text_input("Falla Despachador (Hora)", key=f"fdesp_{eq_key}", placeholder="HH:MM")
            h_rep = col_f4.text_input("Reparación (Hora)", key=f"hrep_{eq_key}", placeholder="HH:MM")

            col_g1, col_g2, col_g3 = st.columns([2, 1, 1])
            operador = col_g1.text_input("Nombre del Operador", key=f"op_{eq_key}")
            gaseo = col_g2.number_input("Gaseo (Galones)", min_value=0.0, step=10.0, key=f"gas_{eq_key}")
            h_gaseo = col_g3.text_input("Horario Gaseo", key=f"hgas_{eq_key}")
            
            st.markdown("---")
            equipos_data.append((eq_codigo, eq_nombre, disp, f_operador, f_mecanico, f_desp, h_rep, operador, gaseo, h_gaseo))

        # Indicador de suma total de disponibilidad
        st.metric("Disponibilidad Total de Equipos en Servicio", f"{conteo_disponibles} / {len(lista_equipos_activa)}")

    st.markdown("---")

    # SECCIÓN TRENES NORTE Y SUR
    st.subheader("3. Operación de Trenes (Ruta Norte y Ruta Sur)")
    col_norte, col_sur = st.columns(2)
    
    with col_norte:
        st.markdown("### 🟢 Trenes Ruta Norte")
        with st.form("form_norte", clear_on_submit=False):
            t_num = st.text_input("Tren # / Set #", placeholder="Ej: 508 / 1")
            enc_480v = st.text_input("Encendido 480V", placeholder="Ej: 17:44:00 o XXX")
            peso = st.number_input("Peso Total", min_value=0.0)
            ini_carga = st.text_input("Inicio de Carga", placeholder="Ej: T.A ó 16:30:00")
            fin_carga = st.text_input("Fin de Carga", placeholder="Ej: 19:40:00")
            partida = st.text_input("Hora de Partida", placeholder="Ej: 19:42:00")
            contenedores = st.text_input("Total Contenedores", placeholder="Ej: 106 (0)")
            locom_cuad = st.text_input("Locomotoras / Cuadrilla")
            track = st.text_input("Track / Comentarios", placeholder="Ej: TRACK 1W")
            add_norte = st.form_submit_button("Añadir Tren Norte")
            if add_norte:
                st.session_state.setdefault('temp_trenes', []).append(('Norte', t_num, enc_480v, peso, ini_carga, fin_carga, partida, contenedores, locom_cuad, track))
                st.success("Tren Norte agregado a la lista temporal del turno")

    with col_sur:
        st.markdown("### 🔴 Trenes Ruta Sur")
        with st.form("form_sur", clear_on_submit=False):
            t_num_s = st.text_input("Tren # / Set #", key="s1", placeholder="Ej: 505 / 5")
            apag_480v = st.text_input("Apagado 480V / Hora Llegada", key="s2", placeholder="Ej: T.A ó 19:00:00")
            peso_s = st.number_input("Peso Total", min_value=0.0, key="s3")
            ini_desc = st.text_input("Inicio Descarga", key="s4", placeholder="Ej: T.A ó 17:40:00")
            fin_carga_s = st.text_input("Fin de Carga", key="s5", placeholder="Ej: 21:25:00")
            partida_s = st.text_input("Hora de Partida", key="s6")
            contenedores_s = st.text_input("Total Contenedores", key="s7")
            locom_cuad_s = st.text_input("Locomotoras / Cuadrilla", key="s8")
            track_s = st.text_input("Track / Comentarios", key="s9", placeholder="Ej: TRACK 2W")
            add_sur = st.form_submit_button("Añadir Tren Sur")
            if add_sur:
                st.session_state.setdefault('temp_trenes', []).append(('Sur', t_num_s, apag_480v, peso_s, ini_desc, fin_carga_s, partida_s, contenedores_s, locom_cuad_s, track_s))
                st.success("Tren Sur agregado a la lista temporal del turno")

    # Tabla temporal de trenes agregados
    if 'temp_trenes' in st.session_state and st.session_state['temp_trenes']:
        st.write("#### Trenes ingresados para este turno:")
        df_temp = pd.DataFrame(st.session_state['temp_trenes'], columns=["Ruta", "Tren/Set", "480V/Llegada", "Peso", "Inicio", "Fin", "Partida", "Contenedores", "Locom/Cuadrilla", "Track"])
        st.dataframe(df_temp, use_container_width=True)

    st.markdown("---")

    # SECCIÓN LÍNEAS Y LOCOMOTORAS
    st.subheader("4. Locomotoras y Estado de Líneas")
    lineas_list = ["Línea 1 Este", "Línea 1 Oeste", "Línea 2 Este", "Línea 2 Centro", "Línea 2 Oeste", "Línea 3", "Línea 4", "Sección I Límite"]
    
    lineas_data = []
    with st.expander("Ver Estado de Líneas", expanded=False):
        for lin in lineas_list:
            cL1, cL2, cL3, cL4 = st.columns(4)
            loc = cL1.text_input(f"{lin} - Locomotora", key=f"loc_{lin}")
            set_n = cL2.text_input("Set #", key=f"set_{lin}")
            tren_n = cL3.text_input("Tren #", key=f"trn_{lin}")
            cond = cL4.selectbox("Condición", ["-", "NORTE", "SUR", "TREN VACIO", "MANTENIMIENTO", "TREN DE TRABAJO"], key=f"cond_{lin}")
            lineas_data.append((lin, loc, set_n, tren_n, cond))

    st.markdown("---")

    # SECCIÓN NOVEDADES, REUNIONES, TRACTORES Y RADIOS
    st.subheader("5. Reuniones, Demoras, Tractores y Radios")
    colA, colB = st.columns(2)
    with colA:
        demoras = st.text_area("Demoras en turno / Banderas en patio")
        reuniones = st.text_area("Reunión con el personal / Otras situaciones")
    with colB:
        cant_tractores = st.number_input("Cantidad de Tractores en turno", min_value=0, step=1)
        radio_patio = st.selectbox("Radio Portátil de Patio #", ["SI", "NO"])
        radio_asignado = st.text_input("Radio Asignado A:")
        radio_hora = st.text_input("Hora Radio")

    st.markdown("---")

    # BOTÓN FINAL DE GUARDADO
    if st.button("💾 GUARDAR Y ACTUALIZAR ARCHIVO DE EXCEL", type="primary", use_container_width=True):
        conn = get_connection()
        c = conn.cursor()
        
        # 1. Cabecera
        c.execute("""INSERT INTO cabecera_turno 
            (terminal, fecha, turno, hora_desde, hora_hasta, supervisor, demoras, reuniones) 
            VALUES (?,?,?,?,?,?,?,?)""",
            (terminal, str(fecha), horario, str(hora_desde), str(hora_hasta), supervisor, demoras, reuniones))
        id_turno = c.lastrowid
        
        # 2. Equipos
        for eq_code, eq_name, disp, f_op, f_mec, f_desp, h_rep, op, gas, hgas in equipos_data:
            c.execute("""INSERT INTO control_equipos 
                (id_turno, codigo_terminal, equipo, disponible, falla_operador, falla_mecanico, falla_despachador, hora_reparacion, operador, gaseo_galones, hora_gaseo) 
                VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (id_turno, eq_code, eq_name, disp, f_op, f_mec, f_desp, h_rep, op, gas, hgas))
            
        # 3. Trenes
        if 'temp_trenes' in st.session_state:
            for ruta, t_num, v480, peso, ini, fin, part, cont, loc_cuad, trk in st.session_state['temp_trenes']:
                c.execute("""INSERT INTO registro_trenes 
                    (id_turno, ruta, numero_tren, estado_480v, peso_total, inicio_operacion, fin_operacion, hora_partida, contenedores, locomotoras_cuadrilla, track_comentarios) 
                    VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                    (id_turno, ruta, t_num, v480, peso, ini, fin, part, cont, loc_cuad, trk))
            st.session_state['temp_trenes'] = []
            
        # 4. Líneas
        for lin, loc, set_n, tren_n, cond in lineas_data:
            c.execute("""INSERT INTO control_lineas 
                (id_turno, linea, locomotora, set_num, tren_num, condicion) 
                VALUES (?,?,?,?,?,?)""",
                (id_turno, lin, loc, set_n, tren_n, cond))
            
        # 5. Tractores y Radios
        c.execute("""INSERT INTO tractores_radios 
            (id_turno, hora_revision, cantidad_tractores, radio_patio, asignado_a, hora_radio) 
            VALUES (?,?,?,?,?,?)""",
            (id_turno, str(datetime.now().strftime("%H:%M:%S")), cant_tractores, radio_patio, radio_asignado, radio_hora))
        
        conn.commit()
        conn.close()
        
        if exportar_y_guardar_excel():
            st.balloons()
            st.success(f"✅ Reporte de Turno #{id_turno} guardado. Equipos en servicio: {conteo_disponibles}.")

# ==========================================
# --- TAB 2: KPIS Y DASHBOARD ---
# ==========================================
with tab_kpi:
    st.header("Indicadores de Rendimiento y Operación")
    try:
        conn = get_connection()
        df_trenes = pd.read_sql_query("SELECT * FROM registro_trenes", conn)
        df_equipos_kpi = pd.read_sql_query("SELECT * FROM control_equipos", conn)
        conn.close()
    except Exception:
        df_trenes = pd.DataFrame()
        df_equipos_kpi = pd.DataFrame()

    if not df_trenes.empty:
        colK1, colK2, colK3 = st.columns(3)
        colK1.metric("Total Trenes Procesados", len(df_trenes))
        colK2.metric("Trenes Ruta Norte", len(df_trenes[df_trenes['ruta'] == 'Norte']))
        colK3.metric("Trenes Ruta Sur", len(df_trenes[df_trenes['ruta'] == 'Sur']))
        
        st.subheader("Detalle de Registros de Trenes")
        st.dataframe(df_trenes, use_container_width=True)
    else:
        st.info("Aún no hay datos de trenes registrados para calcular KPIs.")

# ==========================================
# --- TAB 3: HISTÓRICO Y DESCARGA EXCEL ---
# ==========================================
with tab_registros:
    st.header("Consultar Base de Datos y Descargar Excel Consolidado")
    
    if os.path.exists('Consolidado_Operaciones_EOSR.xlsx'):
        with open('Consolidado_Operaciones_EOSR.xlsx', 'rb') as f:
            st.download_button(
                label="📥 DESCARGAR CONSOLIDADO EXCEL (.XLSX) PARA ANÁLISIS",
                data=f,
                file_name='Consolidado_Operaciones_EOSR.xlsx',
                mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                type="primary"
            )
    else:
        st.warning("El archivo Excel consolidado se creará al guardar el primer registro de turno.")

    st.markdown("---")
    
    try:
        conn = get_connection()
        df_cabecera = pd.read_sql_query("SELECT * FROM cabecera_turno", conn)
        df_equipos_all = pd.read_sql_query("SELECT * FROM control_equipos", conn)
        conn.close()
    except Exception:
        df_cabecera = pd.DataFrame()
        df_equipos_all = pd.DataFrame()

    if not df_cabecera.empty:
        st.subheader("Histórico de Turnos Guardados")
        st.dataframe(df_cabecera, use_container_width=True)
        st.subheader("Histórico de Equipos Registrados")
        st.dataframe(df_equipos_all, use_container_width=True)
    else:
        st.info("La base de datos se encuentra vacía actualmente.")