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

DEFAULT_HEADERS = ["Car", "Axle", "Bearing_East", "Bearing_West", "Wheel_East", "Wheel_West", "ON", "OFF", "PW1", "PW2", "Alarms"]

EXCLUDE_HEADER_KEYWORDS = [
    "train details", "milepost", "scanner performance", 
    "alarm limits", "system alarms", "integrity failures", 
    "axle alarm summary", "resistor test mode", "software version"
]

def make_unique_columns(cols):
    seen = {}
    new_cols = []
    for i, col in enumerate(cols):
        col_str = str(col).strip() if col is not None and str(col).strip() != "" else f"Columna_{i+1}"
        if col_str in seen:
            seen[col_str] += 1
            new_cols.append(f"{col_str}_{seen[col_str]}")
        else:
            seen[col_str] = 0
            new_cols.append(col_str)
    return new_cols

@st.cache_data
def parse_pdf(file_bytes):
    all_rows = []
    header_found = None
    
    with pdfplumber.open(BytesIO(file_bytes)) as pdf:
        for page in pdf.pages:
            tables = page.extract_tables()
            for table in tables:
                for row in table:
                    cleaned_row = [str(cell).strip() if cell is not None else "" for cell in row]
                    row_text = " ".join(cleaned_row).lower()
                    
                    if not any(cleaned_row) or any(kw in row_text for kw in EXCLUDE_HEADER_KEYWORDS):
                        continue
                    
                    if "axle" in row_text or "bearing" in row_text or "car" in row_text:
                        if header_found is None:
                            header_found = [c if c != "" else f"Header_{idx+1}" for idx, c in enumerate(cleaned_row)]
                        continue
                        
                    all_rows.append(cleaned_row)
                        
    if not all_rows:
        return pd.DataFrame()

    df = pd.DataFrame(all_rows)
    
    if header_found and len(header_found) == df.shape[1]:
        df.columns = make_unique_columns(header_found)
    else:
        df.columns = make_unique_columns(DEFAULT_HEADERS[:df.shape[1]] if df.shape[1] <= len(DEFAULT_HEADERS) else [f"Col_{i+1}" for i in range(df.shape[1])])

    valid_cols = [col for col in df.columns if not re.match(r'^nan(_\d+)?$', str(col).strip(), re.IGNORECASE)]
    df = df[valid_cols]

    df = df[df.apply(lambda r: r.astype(str).str.contains(r'\d+').any(), axis=1)].reset_index(drop=True)

    car_col_name = next((c for c in df.columns if "car" in str(c).lower() or "vag" in str(c).lower()), None)
    
    if car_col_name:
        df[car_col_name] = df[car_col_name].replace(r'^\s*$', np.nan, regex=True)
        df[car_col_name] = df[car_col_name].ffill()

    return df

def find_matching_col(cols, keywords):
    for col in cols:
        col_lower = str(col).lower()
        if all(kw in col_lower for kw in keywords):
            return col
    return None

st.sidebar.header("📁 Cargar Documento")
uploaded_file = st.sidebar.file_uploader("Selecciona un archivo PDF", type=["pdf"])

if uploaded_file is not None:
    try:
        file_bytes = uploaded_file.read()
        df_raw = parse_pdf(file_bytes)
        
        if df_raw.empty:
            st.warning("⚠️ No se pudieron extraer datos del PDF. Verifica que el reporte contenga las tablas de ejes.")
        else:
            st.sidebar.success("✅ ¡PDF procesado con éxito!")
            
            tab_dash, tab_data, tab_settings = st.tabs([
                "📊 Gráficas Separadas (Bearing vs Wheel)", 
                "📋 Datos Extraídos", 
                "⚙️ Configuración de Columnas"
            ])
            
            cols_list = list(df_raw.columns)
            
            default_car = find_matching_col(cols_list, ["car"]) or (cols_list[0] if len(cols_list) > 0 else None)
            default_axle = find_matching_col(cols_list, ["axle"]) or find_matching_col(cols_list, ["eje"]) or (cols_list[1] if len(cols_list) > 1 else None)
            default_b_east = find_matching_col(cols_list, ["bear", "east"]) or find_matching_col(cols_list, ["east"]) or (cols_list[2] if len(cols_list) > 2 else None)
            default_b_west = find_matching_col(cols_list, ["bear", "west"]) or find_matching_col(cols_list, ["west"]) or (cols_list[3] if len(cols_list) > 3 else None)
            default_w_east = find_matching_col(cols_list, ["wheel", "east"]) or (cols_list[4] if len(cols_list) > 4 else None)
            default_w_west = find_matching_col(cols_list, ["wheel", "west"]) or (cols_list[5] if len(cols_list) > 5 else None)
            
            with tab_settings:
                st.subheader("Asignación de Columnas del PDF")
                st.info("Asigna las columnas correspondientes a cada componente para separarlas claramente en el dashboard.")
                
                col1, col2 = st.columns(2)
                
                with col1:
                    st.markdown("### 🚂 Identificador y Rodamientos (Bearings)")
                    axle_col = st.selectbox("Columna de Número de Eje (Eje X)", options=["Secuencia Autogenerada"] + cols_list, index=cols_list.index(default_axle) + 1 if default_axle in cols_list else 0)
                    
                    idx_b_east = cols_list.index(default_b_east) + 1 if default_b_east in cols_list else 0
                    idx_b_west = cols_list.index(default_b_west) + 1 if default_b_west in cols_list else 0
                    
                    b_east_col = st.selectbox("Bearing East (Rodamiento Este)", options=["Ninguna"] + cols_list, index=idx_b_east)
                    b_west_col = st.selectbox("Bearing West (Rodamiento Oeste)", options=["Ninguna"] + cols_list, index=idx_b_west)

                with col2:
                    st.markdown("### 🛞 Ruedas / Frenos (Wheels)")
                    st.write("")
                    
                    idx_w_east = cols_list.index(default_w_east) + 1 if default_w_east in cols_list else 0
                    idx_w_west = cols_list.index(default_w_west) + 1 if default_w_west in cols_list else 0
                    
                    w_east_col = st.selectbox("Wheel East (Rueda Este)", options=["Ninguna"] + cols_list, index=idx_w_east)
                    w_west_col = st.selectbox("Wheel West (Rueda Oeste)", options=["Ninguna"] + cols_list, index=idx_w_west)

            df_clean = df_raw.copy()
            
            target_cols = [c for c in [b_east_col, b_west_col, w_east_col, w_west_col] if c != "Ninguna"]
            for col in target_cols:
                series = df_clean[col]
                if isinstance(series, pd.DataFrame):
                    series = series.iloc[:, 0]
                df_clean[col] = series.astype(str).str.replace(r"[$,]", "", regex=True)
                df_clean[col] = pd.to_numeric(df_clean[col], errors="coerce")

            # Asignación y restricción de 'Eje_Num' a un máximo de 152 ejes
            if axle_col == "Secuencia Autogenerada":
                df_clean.insert(0, "Eje_Num", range(1, len(df_clean) + 1))
            else:
                num_axle = pd.to_numeric(df_clean[axle_col], errors="coerce")
                if num_axle.isna().all():
                    df_clean.insert(0, "Eje_Num", range(1, len(df_clean) + 1))
                else:
                    df_clean.insert(0, "Eje_Num", num_axle)

            df_clean = df_clean[df_clean["Eje_Num"] <= 152].reset_index(drop=True)

            all_cols = list(df_clean.columns)
            clean_cols = [c for c in all_cols if not re.match(r'^nan(_\d+)?$', str(c).strip(), re.IGNORECASE)]
            
            car_col_found = next((c for c in clean_cols if "car" in str(c).lower()), None)
            
            front_cols = []
            if car_col_found:
                front_cols.append(car_col_found)
            front_cols.append("Eje_Num")
            
            other_cols = [c for c in clean_cols if c not in front_cols]
            df_clean = df_clean[front_cols + other_cols]

            df_sorted = df_clean.sort_values(by="Eje_Num")

            with tab_dash:
                st.write("---")
                # SECCIÓN 1: BEARINGS
                st.subheader("🔥 1. Lecturas de Rodamientos (Bearings: East vs West)")
                
                if b_east_col != "Ninguna" or b_west_col != "Ninguna":
                    fig_bearing = go.Figure()
                    if b_east_col != "Ninguna":
                        fig_bearing.add_trace(go.Bar(
                            x=df_sorted["Eje_Num"],
                            y=df_sorted[b_east_col],
                            name=f"Bearing East ({b_east_col})",
                            marker_color="#D62728"
                        ))
                    if b_west_col != "Ninguna":
                        fig_bearing.add_trace(go.Bar(
                            x=df_sorted["Eje_Num"],
                            y=df_sorted[b_west_col],
                            name=f"Bearing West ({b_west_col})",
                            marker_color="#1F77B4"
                        ))
                    
                    fig_bearing.update_layout(
                        barmode="group",
                        title="Comparativa de Temperatura en Rodamientos (Bearing East vs Bearing West) por Eje",
                        xaxis=dict(
                            title="Número de Eje", 
                            dtick=5, 
                            range=[0.5, 152.5],
                            showgrid=True
                        ),
                        yaxis=dict(title="Temperatura / Valor"),
                        height=380,
                        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
                    )
                    st.plotly_chart(fig_bearing, use_container_width=True)
                    st.caption("📌 **Pie de página:** Muestra las lecturas de temperatura en grados sobre el nivel ambiente para los rodamientos (*cajas de grasa*) de los costados Este (naranja oscuro) y Oeste (naranja claro) por cada eje individual del tren (1 al 152). Permite detectar rodamientos sobrecalentados (*hot bearings*) o picos anómalos aislados.")
                else:
                    st.info("Selecciona las columnas de Bearing East/West en la pestaña de Configuración.")

                st.write("---")
                
                # SECCIÓN 2: WHEELS
                st.subheader("🛞 2. Lecturas de Ruedas (Wheels: East vs West)")
                
                if w_east_col != "Ninguna" or w_west_col != "Ninguna":
                    fig_wheel = go.Figure()
                    if w_east_col != "Ninguna":
                        fig_wheel.add_trace(go.Bar(
                            x=df_sorted["Eje_Num"],
                            y=df_sorted[w_east_col],
                            name=f"Wheel East ({w_east_col})",
                            marker_color="#636EFA"
                        ))
                    if w_west_col != "Ninguna":
                        fig_wheel.add_trace(go.Bar(
                            x=df_sorted["Eje_Num"],
                            y=df_sorted[w_west_col],
                            name=f"Wheel West ({w_west_col})",
                            marker_color="#00CC96"
                        ))
                    
                    fig_wheel.update_layout(
                        barmode="group",
                        title="Comparativa de Temperatura en Ruedas (Wheel East vs Wheel West) por Eje",
                        xaxis=dict(
                            title="Número de Eje", 
                            dtick=5, 
                            range=[0.5, 152.5],
                            showgrid=True
                        ),
                        yaxis=dict(title="Temperatura / Valor"),
                        height=380,
                        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
                    )
                    st.plotly_chart(fig_wheel, use_container_width=True)
                    st.caption("📌 **Pie de página:** Muestra el perfil térmico de las ruedas/llantas para los costados Este (azul) y Oeste (verde) a lo largo de la formación (ejes 1 al 152). Ayuda a diagnosticar frenos amarrados, zapatas pegadas o fricción excesiva entre rueda y riel.")
                else:
                    st.info("Selecciona las columnas de Wheel East/West en la pestaña de Configuración.")

                st.write("---")

                # SECCIÓN 3: DISTRIBUCIÓN PORCENTUAL
                st.subheader("📊 Distribución Porcentual Horizontal por Componente")
                c1, c2 = st.columns(2)
                
                with c1:
                    st.markdown("#### Distribución en Rodamientos (Bearings)")
                    b_cols = [c for c in [b_east_col, b_west_col] if c != "Ninguna"]
                    if b_cols:
                        b_totals = df_clean[b_cols].sum(numeric_only=True)
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
                            color_discrete_sequence=["#EF553B", "#FFA15A"],
                            title="Porcentaje Total: Bearing East vs West"
                        )
                        fig_b_pie.update_traces(texttemplate='%{x:.1f}%', textposition='outside')
                        fig_b_pie.update_layout(showlegend=False, height=280)
                        st.plotly_chart(fig_b_pie, use_container_width=True)
                        st.caption("📌 **Pie de página:** Proporción acumulada global del calor registrado en rodamientos entre el lado Este y Oeste. Una desviación pronunciada respecto al 50%/50% puede señalar carga desbalanceada o desalineación técnica del sensor.")
                        
                with c2:
                    st.markdown("#### Distribución en Ruedas (Wheels)")
                    w_cols = [c for c in [w_east_col, w_west_col] if c != "Ninguna"]
                    if w_cols:
                        w_totals = df_clean[w_cols].sum(numeric_only=True)
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
                            color_discrete_sequence=["#636EFA", "#00CC96"],
                            title="Porcentaje Total: Wheel East vs West"
                        )
                        fig_w_pie.update_traces(texttemplate='%{x:.1f}%', textposition='outside')
                        fig_w_pie.update_layout(showlegend=False, height=280)
                        st.plotly_chart(fig_w_pie, use_container_width=True)
                        st.caption("📌 **Pie de página:** Proporción acumulada global del calor registrado en las ruedas entre el lado Este y Oeste. Indica el balance de fricción lateral en todo el tren.")

            with tab_data:
                st.subheader("Tabla de Datos Extraídos")
                st.dataframe(df_clean, use_container_width=True)
                
                csv_data = df_clean.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="📥 Descargar datos como CSV",
                    data=csv_data,
                    file_name="reporte_detectores_ejes.csv",
                    mime="text/csv"
                )
                
    except Exception as e:
        st.error(f"Error al procesar el archivo: {e}")

else:
    st.info("👈 Por favor carga un archivo PDF desde el panel lateral para iniciar el análisis.")
