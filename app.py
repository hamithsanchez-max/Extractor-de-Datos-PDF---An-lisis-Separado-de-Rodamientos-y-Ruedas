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

                # Extraer tokens numéricos incluso si tienen indicadores de alarma pegados (ej. 450*, 512H)
                numeric_tokens = [t for t in tokens if re.match(r'^-?\d+(\.\d+)?[*a-zA-Z]*$', t)]
                
                if len(numeric_tokens) >= 8:
                    # Limpiar posibles asteriscos o letras en los primeros tokens identificadores
                    t0_clean = re.sub(r'[^0-9]', '', tokens[0])
                    t1_clean = re.sub(r'[^0-9]', '', tokens[1]) if len(tokens) > 1 else ""

                    if len(tokens) >= 10 and t0_clean.isdigit() and int(t0_clean) < 200 and t1_clean.isdigit():
                        current_car = t0_clean
                        axle = t1_clean
                        rest = tokens[2:]
                    elif t0_clean.isdigit():
                        axle = t0_clean
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
            
            # Limpiar símbolos o letras (ej. *, H, W) adjuntos a temperaturas altas antes de convertir a número
            numeric_cols = [b_east_col, b_west_col, w_east_col, w_west_col]
            for col in numeric_cols:
                df_clean[col] = (
                    df_clean[col]
                    .astype(str)
                    .str.replace(r"[^0-9.-]", "", regex=True)
                )
                df_clean[col] = pd.to_numeric(df_clean[col], errors="coerce")

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
                    alarm_list_str = ", ".join([f"**Eje {row['Eje_Num']}**: {row['Alarm_Text