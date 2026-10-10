import streamlit as st
import pdfplumber
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import re
from io import BytesIO

# Configuración inicial de la página
st.set_page_config(
    page_title="PDF Extractor - Tren de Carga (Rodamientos y Ruedas)",
    page_icon="🚆",
    layout="wide"
)

st.title("🚆 Extractor de Datos PDF - Análisis Separado de Rodamientos y Ruedas")
st.markdown("Visualización segregada para **Bearing East/West** (Rodamientos) y **Wheel East/West** (Ruedas) por eje de tren.")

# Nombres estándar de las columnas del reporte SmartScan
STANDARD_COLUMNS = ["Car", "Axle", "Bearing_East", "Bearing_West", "Wheel_East", "Wheel_West", "ON", "OFF", "PW1", "PW2", "Alarms"]

# Función para convertir DataFrame a un archivo Excel (.xlsx) en memoria
def convert_df_to_excel(df, sheet_name="Datos_Extraidos"):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name=sheet_name)
    processed_data = output.getvalue()
    return processed_data

@st.cache_data
def parse_pdf(file_bytes):
    parsed_data = []
    current_car = None

    with pdfplumber.open(BytesIO(file_bytes)) as pdf:
        for page in pdf.pages:
            text = page.extract_text(layout=False)
            if not text:
                continue

            lines = text.split("\n")
            for line in lines:
                line_str = line.strip()
                if not line_str:
                    continue

                tokens = line_str.split()

                # Ignorar encabezados y metadatos del reporte
                if any(kw in line_str.lower() for kw in ["train details", "milepost", "scanner performance", "alarm limits", "system alarms", "integrity failures", "axle alarm summary", "resistor", "software version", "bearing", "wheel"]):
                    continue

                numeric_tokens = [t for t in tokens if re.match(r'^-?\d+(\.\d+)?$', t)]
                
                if len(numeric_tokens) >= 8:
                    if len(tokens) >= 10 and tokens[0].isdigit() and int(tokens[0]) < 100 and tokens[1].isdigit():
                        current_car = tokens[0]
                        axle = tokens[1]
                        rest = tokens[2:]
                    elif tokens[0].isdigit():
                        axle = tokens[0]
                        rest = tokens[1:]
                    else:
                        continue

                    row = [current_car, axle] + rest
                    
                    if len(row) < len(STANDARD_COLUMNS):
                        row += [""] * (len(STANDARD_COLUMNS) - len(row))
                    elif len(row) > len(STANDARD_COLUMNS):
                        alarms_text = " ".join(row[10:])
                        row = row[:10] + [alarms_text]

                    parsed_data.append(row)

    if not parsed_data:
        return pd.DataFrame()

    df = pd.DataFrame(parsed_data, columns=STANDARD_COLUMNS)
    df["Car"] = df["Car"].replace(r'^\s*$', np.nan, regex=True).ffill()
    
    return df

st.sidebar.header("📁 Cargar Documento")
uploaded_file = st.sidebar.file_uploader("Selecciona un archivo PDF", type=["pdf"])

if uploaded_file is not None:
    try:
        pdf_title = uploaded_file.name
        
        file_bytes = uploaded_file.read()
        df_raw = parse_pdf(file_bytes)
        
        if df_raw.empty:
            st.warning(f"⚠️ No se pudieron extraer datos del archivo **{pdf_title}**. Verifica que el reporte sea un documento de detectores wayside.")
        else:
            st.sidebar.success("✅ ¡Procesado con éxito!")
            st.sidebar.info(f"📄 **Archivo activo:**\n`{pdf_title}`")
            
            st.info(f"📋 **Reporte Analizado:** `{pdf_title}`")
            
            tab_dash, tab_data, tab_settings = st.tabs([
                "📊 Gráficas Separadas (Bearing vs Wheel)", 
                "📋 Datos Extraídos", 
                "⚙️ Configuración de Columnas"
            ])
            
            cols_list = list(df_raw.columns)
            
            with tab_settings:
                st.subheader("Asignación de Columnas del PDF")
                st.info("Valida o ajusta las columnas asignadas automáticamente.")
                
                col1, col2 = st.columns(2)
                
                with col1:
                    st.markdown("### 🚂 Identificador y Rodamientos (Bearings)")
                    axle_col = st.selectbox("Columna de Número de Eje", options=cols_list, index=cols_list.index("Axle") if "Axle" in cols_list else 1)
                    b_east_col = st.selectbox("Bearing East", options=cols_list, index=cols_list.index("Bearing_East") if "Bearing_East" in cols_list else 2)
                    b_west_col = st.selectbox("Bearing West", options=cols_list, index=cols_list.index("Bearing_West") if "Bearing_West" in cols_list else 3)

                with col2:
                    st.markdown("### 🛞 Ruedas y Alarmas")
                    w_east_col = st.selectbox("Wheel East", options=cols_list, index=cols_list.index("Wheel_East") if "Wheel_East" in cols_list else 4)
                    w_west_col = st.selectbox("Wheel West", options=cols_list, index=cols_list.index("Wheel_West") if "Wheel_West" in cols_list else 5)
                    alarm_col = st.selectbox("Columna de Alarmas (Alarms)", options=["Ninguna"] + cols_list, index=cols_list.index("Alarms") + 1 if "Alarms" in cols_list else 0)

            df_clean = df_raw.copy()
            
            numeric_cols = [b_east_col, b_west_col, w_east_col, w_west_col]
            for col in numeric_cols:
                df_clean[col] = pd.to_numeric(df_clean[col].astype(str).str.replace(r"[$,]", "", regex=True), errors="coerce")

            df_clean["Eje_Num"] = pd.to_numeric(df_clean[axle_col], errors="coerce")
            
            if df_clean["Eje_Num"].isna().all():
                df_clean["Eje_Num"] = range(1, len(df_clean) + 1)

            # Restricción ampliada a 160 ejes máximo
            df_clean = df_clean[df_clean["Eje_Num"] <= 160].reset_index(drop=True)

            cols_order = ["Car", "Eje_Num", b_east_col, b_west_col, w_east_col, w_west_col]
            remaining_cols = [c for c in df_clean.columns if c not in cols_order and c != axle_col]
            df_clean = df_clean[cols_order + remaining_cols]

            df_sorted = df_clean.sort_values(by="Eje_Num")

            # Procesamiento de texto de alarmas
            if alarm_col != "Ninguna":
                df_sorted["Alarm_Text"] = df_sorted[alarm_col].astype(str).str.strip()
                df_sorted["Has_Alarm"] = df_sorted["Alarm_Text"].apply(lambda x: True if x != "" and x.lower() not in ["nan", "none", "0"] else False)
            else:
                df_sorted["Alarm_Text"] = ""
                df_sorted["Has_Alarm"] = False

            with tab_dash:
                st.write("---")
                
                # Resumen superior de alarmas
                alarms_df = df_sorted[df_sorted["Has_Alarm"]]
                if not alarms_df.empty:
                    st.error(f"🚨 **Se registraron {len(alarms_df)} alarma(s) en el reporte {pdf_title}:**")
                    alarm_list_str = ", ".join([f"**Eje {row['Eje_Num']}**: {row['Alarm_Text']}" for _, row in alarms_df.iterrows()])
                    st.markdown(alarm_list_str)

                st.write("---")

                # SECCIÓN 1: BEARINGS
                st.subheader(f"🔥 1. Lecturas de Rodamientos - {pdf_title}")
                
                fig_bearing = go.Figure()
                fig_bearing.add_trace(go.Bar(
                    x=df_sorted["Eje_Num"],
                    y=df_sorted[b_east_col],
                    name=f"Bearing East ({b_east_col})",
                    marker_color="#D62728",
                    hovertemplate="<b>Eje %{x}</b><br>Temp: %{y:.1f}<br>Bearing East<extra></extra>"
                ))
                fig_bearing.add_trace(go.Bar(
                    x=df_sorted["Eje_Num"],
                    y=df_sorted[b_west_col],
                    name=f"Bearing West ({b_west_col})",
                    marker_color="#1F77B4",
                    hovertemplate="<b>Eje %{x}</b><br>Temp: %{y:.1f}<br>Bearing West<extra></extra>"
                ))
                
                b_alarms = df_sorted[df_sorted["Has_Alarm"] & df_sorted["Alarm_Text"].str.lower().str.contains("bearing|box|diff", na=False)]
                if not b_alarms.empty:
                    max_y_b = df_sorted[[b_east_col, b_west_col]].max().max()
                    y_pos_b = max_y_b * 1.08 if not np.isnan(max_y_b) and max_y_b > 0 else 50
                    
                    fig_bearing.add_trace(go.Scatter(
                        x=b_alarms["Eje_Num"],
                        y=[y_pos_b] * len(b_alarms),
                        mode="markers+text",
                        name="🚨 ALARMA BEARING",
                        marker=dict(symbol="diamond", size=11, color="red", line=dict(width=1, color="black")),
                        text=["🚨"] * len(b_alarms),
                        textposition="top center",
                        hovertemplate="<b>Eje %{x}</b><br>Alarma: %{hovertext}<extra></extra>",
                        hovertext=b_alarms["Alarm_Text"]
                    ))

                fig_bearing.update_layout(
                    barmode="group",
                    title=f"Comparativa de Temperatura en Rodamientos ({pdf_title})",
                    xaxis=dict(title="Número de Eje", dtick=5, range=[0.5, 160.5], showgrid=True),
                    yaxis=dict(title="Temperatura / Valor"),
                    height=400,
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                    hoverlabel=dict(
                        font_size=14,
                        font_family="Arial, sans-serif"
                    )
                )
                st.plotly_chart(fig_bearing, use_container_width=True)
                st.caption("📌 **Pie de página:** Lecturas de temperatura para los rodamientos Este (rojo) y Oeste (azul). Los iconos **🚨** indican alarmas críticas de rodamientos/cajas.")

                st.write("---")
                
                # SECCIÓN 2: WHEELS
                st.subheader(f"🛞 2. Lecturas de Ruedas - {pdf_title}")
                
                fig_wheel = go.Figure()
                fig_wheel.add_trace(go.Bar(
                    x=df_sorted["Eje_Num"],
                    y=df_sorted[w_east_col],
                    name=f"Wheel East ({w_east_col})",
                    marker_color="#9467BD",
                    hovertemplate="<b>Eje %{x}</b><br>Temp: %{y:.1f}<br>Wheel East<extra></extra>"
                ))
                fig_wheel.add_trace(go.Bar(
                    x=df_sorted["Eje_Num"],
                    y=df_sorted[w_west_col],
                    name=f"Wheel West ({w_west_col})",
                    marker_color="#2CA02C",
                    hovertemplate="<b>Eje %{x}</b><br>Temp: %{y:.1f}<br>Wheel West<extra></extra>"
                ))
                
                w_alarms = df_sorted[df_sorted["Has_Alarm"] & df_sorted["Alarm_Text"].str.lower().str.contains("wheel|rueda|freno", na=False)]
                if not w_alarms.empty:
                    max_y_w = df_sorted[[w_east_col, w_west_col]].max().max()
                    y_pos_w = max_y_w * 1.08 if not np.isnan(max_y_w) and max_y_w > 0 else 50
                    
                    fig_wheel.add_trace(go.Scatter(
                        x=w_alarms["Eje_Num"],
                        y=[y_pos_w] * len(w_alarms),
                        mode="markers+text",
                        name="🚨 ALARMA WHEEL",
                        marker=dict(symbol="diamond", size=11, color="red", line=dict(width=1, color="black")),
                        text=["🚨"] * len(w_alarms),
                        textposition="top center",
                        hovertemplate="<b>Eje %{x}</b><br>Alarma Rueda: %{hovertext}<extra></extra>",
                        hovertext=w_alarms["Alarm_Text"]
                    ))

                fig_wheel.update_layout(
                    barmode="group",
                    title=f"Comparativa de Temperatura en Ruedas ({pdf_title})",
                    xaxis=dict(title="Número de Eje", dtick=5, range=[0.5, 160.5], showgrid=True),
                    yaxis=dict(title="Temperatura / Valor"),
                    height=400,
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                    hoverlabel=dict(
                        font_size=14,
                        font_family="Arial, sans-serif"
                    )
                )
                st.plotly_chart(fig_wheel, use_container_width=True)
                st.caption("📌 **Pie de página:** Perfil térmico de las ruedas para los costados Este (púrpura) y Oeste (verde). Los iconos **🚨** indican ejes con alarmas de ruedas (*Hot Wheel*).")

                st.write("---")

                # SECCIÓN 3: DISTRIBUCIÓN PORCENTUAL
                st.subheader("📊 Distribución Porcentual Horizontal por Componente")
                c1, c2 = st.columns(2)
                
                with c1:
                    st.markdown("#### Distribución en Rodamientos (Bearings)")
                    b_totals = df_clean[[b_east_col, b_west_col]].sum(numeric_only=True)
                    df_b_sum = pd.DataFrame({"Componente": b_totals.index, "Suma_Lecturas": b_totals.values})
                    total_b = df_b_sum["Suma_Lecturas"].sum()
                    df_b_sum["Porcentaje"] = (df_b_sum["Suma_Lecturas"] / total_b * 100) if total_b > 0 else 0
                    
                    fig_b_pie = px.bar(
                        df_b_sum,
                        x="Porcentaje",
                        y="Componente",
                        orientation="h",
                        text_auto=".1f",
                        color="Componente",
                        color_discrete_sequence=["#D62728", "#1F77B4"],
                        title="Porcentaje Total: Bearing East vs West"
                    )
                    fig_b_pie.update_traces(texttemplate='%{x:.1f}%', textposition='outside')
                    fig_b_pie.update_layout(
                        showlegend=False, 
                        height=280,
                        hoverlabel=dict(font_size=14, font_family="Arial, sans-serif")
                    )
                    st.plotly_chart(fig_b_pie, use_container_width=True)
                    st.caption("📌 **Pie de página:** Proporción acumulada global del calor en rodamientos entre el lado Este (rojo) y Oeste (azul).")
                        
                with c2:
                    st.markdown("#### Distribución en Ruedas (Wheels)")
                    w_totals = df_clean[[w_east_col, w_west_col]].sum(numeric_only=True)
                    df_w_sum = pd.DataFrame({"Componente": w_totals.index, "Suma_Lecturas": w_totals.values})
                    total_w = df_w_sum["Suma_Lecturas"].sum()
                    df_w_sum["Porcentaje"] = (df_w_sum["Suma_Lecturas"] / total_w * 100) if total_w > 0 else 0
                    
                    fig_w_pie = px.bar(
                        df_w_sum,
                        x="Porcentaje",
                        y="Componente",
                        orientation="h",
                        text_auto=".1f",
                        color="Componente",
                        color_discrete_sequence=["#9467BD", "#2CA02C"],
                        title="Porcentaje Total: Wheel East vs West"
                    )
                    fig_w_pie.update_traces(texttemplate='%{x:.1f}%', textposition='outside')
                    fig_w_pie.update_layout(
                        showlegend=False, 
                        height=280,
                        hoverlabel=dict(font_size=14, font_family="Arial, sans-serif")
                    )
                    st.plotly_chart(fig_w_pie, use_container_width=True)
                    st.caption("📌 **Pie de página:** Proporción acumulada global del calor en ruedas entre el lado Este (púrpura) y Oeste (verde).")

            with tab_data:
                st.subheader(f"Tabla de Datos Extraídos - {pdf_title}")
                st.dataframe(df_clean, use_container_width=True)
                
                # --- OPCIONES DE DESCARGA (EXCEL Y CSV) ---
                col_dl1, col_dl2 = st.columns(2)
                
                base_filename = pdf_title.replace('.pdf', '')
                
                with col_dl1:
                    # Descarga en formato Tabla Excel (.xlsx)
                    excel_data = convert_df_to_excel(df_clean)
                    st.download_button(
                        label="📊 Descargar Tabla de Datos en Excel (.xlsx)",
                        data=excel_data,
                        file_name=f"reporte_{base_filename}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
                    
                with col_dl2:
                    # Descarga en formato CSV (.csv)
                    csv_data = df_clean.to_csv(index=False).encode('utf-8')
                    st.download_button(
                        label="📥 Descargar Datos en CSV (.csv)",
                        data=csv_data,
                        file_name=f"reporte_{base_filename}.csv",
                        mime="text/csv"
                    )
                
    except Exception as e:
        st.error(f"Error al procesar el archivo: {e}")

else:
    st.info("👈 Por favor carga un archivo PDF desde el panel lateral para iniciar el análisis.")