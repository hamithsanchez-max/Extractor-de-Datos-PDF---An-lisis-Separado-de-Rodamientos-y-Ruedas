import streamlit as st
import pdfplumber
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import re
from io import BytesIO

st.set_page_config(
    page_title="PDF Extractor - Tren de Carga (Rodamientos y Ruedas)",
    page_icon="🚆",
    layout="wide"
)

st.title("🚆 Extractor de Datos PDF - Análisis Separado de Rodamientos y Ruedas")
st.markdown("Visualización segregada para **Bearing East/West** (Rodamientos) y **Wheel East/West** (Ruedas) por eje de tren.")

STANDARD_COLUMNS = [
    "Car", "Axle", "Bearing_East", "Bearing_West",
    "Wheel_East", "Wheel_West", "ON", "OFF", "PW1", "PW2", "Alarms"
]


def convert_df_to_excel(df, sheet_name="Datos_Extraidos"):
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name=sheet_name)
    return output.getvalue()


@st.cache_data
def parse_pdf(file_bytes):
    parsed_data = []
    summary_alarms = []
    current_car = None
    in_alarm_summary = False

    ignore_keywords = [
        "train details", "milepost", "scanner performance", "alarm limits",
        "system alarms", "integrity failures",
        "resistor", "software version", "bearing", "wheel"
    ]

    with pdfplumber.open(BytesIO(file_bytes)) as pdf:
        for page in pdf.pages:
            text = page.extract_text(layout=False)
            if not text:
                continue

            for line in text.split("\n"):
                line_str = line.strip()
                if not line_str:
                    continue

                low_line = line_str.lower()

                # Detectar sección de resumen de alarmas del reporte SmartScan
                if "axle alarm summary" in low_line:
                    in_alarm_summary = True
                    continue

                if in_alarm_summary:
                    if any(kw in low_line for kw in ["system alarms", "integrity failures", "scanner performance", "software version", "end of report"]):
                        in_alarm_summary = False
                    else:
                        # Capturar líneas de alarma del resumen (ej. "36 Hot Wheel East..." o "Axle 36 ...")
                        m_alarm = re.match(r"^(?:axle\s*)?(\d{1,3})\s+(.+)$", line_str, re.IGNORECASE)
                        if m_alarm:
                            eje_al = int(m_alarm.group(1))
                            desc_al = m_alarm.group(2).strip()
                            if eje_al <= 160 and not desc_al.isdigit():
                                summary_alarms.append((eje_al, desc_al))
                        continue

                tokens = line_str.split()

                if any(kw in low_line for kw in ignore_keywords):
                    continue

                numeric_tokens = [
                    t for t in tokens
                    if re.match(r"^(-?\d+(\.\d+)?[*a-zA-Z]*|-{2,})$", t)
                ]

                if len(numeric_tokens) >= 8:
                    t0_clean = re.sub(r"[^0-9]", "", tokens[0])
                    t1_clean = re.sub(r"[^0-9]", "", tokens[1]) if len(tokens) > 1 else ""

                    if len(tokens) >= 10 and t0_clean.isdigit() and int(t0_clean) < 100 and t1_clean.isdigit():
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
        return pd.DataFrame(), summary_alarms

    df = pd.DataFrame(parsed_data, columns=STANDARD_COLUMNS)
    df["Car"] = df["Car"].replace(r"^\s*$", np.nan, regex=True).ffill()
    return df, summary_alarms


st.sidebar.header("📁 Cargar Documento")
uploaded_file = st.sidebar.file_uploader("Selecciona un archivo PDF", type=["pdf"])

if uploaded_file is not None:
    try:
        pdf_title = uploaded_file.name
        file_bytes = uploaded_file.read()
        df_raw, summary_alarms = parse_pdf(file_bytes)

        if df_raw.empty:
            st.warning(f"⚠️ No se pudieron extraer datos del archivo **{pdf_title}**.")
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
                col1, col2 = st.columns(2)
                with col1:
                    st.markdown("### 🚂 Identificador y Rodamientos (Bearings)")
                    axle_col = st.selectbox("Columna de Número de Eje", options=cols_list, index=1)
                    b_east_col = st.selectbox("Bearing East", options=cols_list, index=2)
                    b_west_col = st.selectbox("Bearing West", options=cols_list, index=3)
                with col2:
                    st.markdown("### 🛞 Ruedas y Alarmas")
                    w_east_col = st.selectbox("Wheel East", options=cols_list, index=4)
                    w_west_col = st.selectbox("Wheel West", options=cols_list, index=5)
                    alarm_col = st.selectbox("Columna de Alarmas (Alarms)", options=["Ninguna"] + cols_list, index=len(cols_list))

            df_clean = df_raw.copy()

            for col in [b_east_col, b_west_col, w_east_col, w_west_col]:
                df_clean[col] = df_clean[col].astype(str).str.replace(r"[^0-9.-]", "", regex=True)
                df_clean[col] = pd.to_numeric(df_clean[col], errors="coerce")

            df_clean["Eje_Num"] = pd.to_numeric(df_clean[axle_col], errors="coerce")
            if df_clean["Eje_Num"].isna().all():
                df_clean["Eje_Num"] = range(1, len(df_clean) + 1)

            df_clean = df_clean.dropna(subset=["Eje_Num"])
            df_clean["Eje_Num"] = df_clean["Eje_Num"].astype(int)
            df_clean = df_clean.drop_duplicates(subset=["Eje_Num"], keep="first")
            df_clean = df_clean[df_clean["Eje_Num"] <= 160].reset_index(drop=True)

            cols_order = ["Car", "Eje_Num", b_east_col, b_west_col, w_east_col, w_west_col]
            remaining_cols = [c for c in df_clean.columns if c not in cols_order and c != axle_col]
            df_clean = df_clean[cols_order + remaining_cols]
            df_sorted = df_clean.sort_values(by="Eje_Num")

            # Consolidar alarmas tanto de la tabla de ejes como del resumen del reporte (ej. Eje 36)
            combined_alarms = {}
            if alarm_col != "Ninguna":
                df_sorted["Alarm_Text"] = df_sorted[alarm_col].astype(str).str.strip()
                for _, r in df_sorted.iterrows():
                    txt = r["Alarm_Text"]
                    if txt != "" and txt.lower() not in ["nan", "none", "0"]:
                        combined_alarms[int(r["Eje_Num"])] = txt

            for eje_al, desc_al in summary_alarms:
                if eje_al not in combined_alarms:
                    combined_alarms[eje_al] = desc_al
                elif desc_al not in combined_alarms[eje_al]:
                    combined_alarms[eje_al] += f" ({desc_al})"

            with tab_dash:
                st.write("---")
                if combined_alarms:
                    st.error(f"🚨 **Se registraron {len(combined_alarms)} alarma(s) en el reporte {pdf_title}:**")
                    alarm_items = [
                        f"**Eje {eje}**: {desc}"
                        for eje, desc in sorted(combined_alarms.items())
                    ]
                    st.markdown(", ".join(alarm_items))

                st.write("---")
                st.subheader(f"🔥 1. Lecturas de Rodamientos - {pdf_title}")

                fig_bearing = go.Figure()
                fig_bearing.add_trace(
                    go.Bar(
                        x=df_sorted["Eje_Num"],
                        y=df_sorted[b_east_col],
                        name=f"Bearing East ({b_east_col})",
                        marker_color="#D62728"
                    )
                )
                fig_bearing.add_trace(
                    go.Bar(
                        x=df_sorted["Eje_Num"],
                        y=df_sorted[b_west_col],
                        name=f"Bearing West ({b_west_col})",
                        marker_color="#1F77B4"
                    )
                )

                fig_bearing.update_layout(
                    barmode="group",
                    title=f"Comparativa de Temperatura en Rodamientos ({pdf_title})",
                    xaxis=dict(title="Número de Eje", dtick=5, range=[0.5, 160.5], showgrid=True),
                    yaxis=dict(title="Temperatura / Valor (°)", dtick=50, range=[0, 450], showgrid=True),
                    height=450,
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
                )
                st.plotly_chart(fig_bearing, use_container_width=True)
                st.caption("📌 **Pie de página:** Lecturas de temperatura para los rodamientos Este (rojo) y Oeste (azul).")

                st.write("---")
                st.subheader(f"🛞 2. Lecturas de Ruedas - {pdf_title}")

                fig_wheel = go.Figure()
                fig_wheel.add_trace(
                    go.Bar(
                        x=df_sorted["Eje_Num"],
                        y=df_sorted[w_east_col],
                        name=f"Wheel East ({w_east_col})",
                        marker_color="#9467BD"
                    )
                )
                fig_wheel.add_trace(
                    go.Bar(
                        x=df_sorted["Eje_Num"],
                        y=df_sorted[w_west_col],
                        name=f"Wheel West ({w_west_col})",
                        marker_color="#2CA02C"
                    )
                )

                fig_wheel.update_layout(
                    barmode="group",
                    title=f"Comparativa de Temperatura en Ruedas ({pdf_title})",
                    xaxis=dict(title="Número de Eje", dtick=5, range=[0.5, 160.5], showgrid=True),
                    yaxis=dict(title="Temperatura / Valor (°)", dtick=50, range=[0, 450], showgrid=True),
                    height=450,
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
                )
                st.plotly_chart(fig_wheel, use_container_width=True)
                st.caption("📌 **Pie de página:** Perfil térmico de las ruedas para los costados Este (púrpura) y Oeste (verde).")

                st.write("---")
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
                    fig_b_pie.update_traces(texttemplate="%{x:.1f}%", textposition="outside")
                    fig_b_pie.update_layout(showlegend=False, height=280)
                    st.plotly_chart(fig_b_pie, use_container_width=True)

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
                    fig_w_pie.update_traces(texttemplate="%{x:.1f}%", textposition="outside")
                    fig_w_pie.update_layout(showlegend=False, height=280)
                    st.plotly_chart(fig_w_pie, use_container_width=True)

            with tab_data:
                st.subheader(f"Tabla de Datos Extraídos - {pdf_title}")
                st.dataframe(df_clean, use_container_width=True)
                col_dl1, col_dl2 = st.columns(2)
                base_filename = pdf_title.replace(".pdf", "")

                with col_dl1:
                    st.download_button(
                        label="📊 Descargar Tabla de Datos en Excel (.xlsx)",
                        data=convert_df_to_excel(df_clean),
                        file_name=f"reporte_{base_filename}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
                with col_dl2:
                    st.download_button(
                        label="📥 Descargar Datos en CSV (.csv)",
                        data=df_clean.to_csv(index=False).encode("utf-8"),
                        file_name=f"reporte_{base_filename}.csv",
                        mime="text/csv"
                    )

    except Exception as e:
        st.error(f"Error al procesar el archivo: {e}")
else:
    st.info("👈 Por favor carga un archivo PDF desde el panel lateral para iniciar el análisis.")