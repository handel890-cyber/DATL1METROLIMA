import streamlit as st
import pandas as pd
import re

st.set_page_config(page_title="Identificador de Archivos SCADA", layout="wide")

st.title("🔍 Identificador de Contenido de Archivos .dat")
st.write("Carga tus archivos `.dat` para leer sus **cabeceras e identificadores** y saber a qué variable corresponden.")

uploaded_files = st.file_uploader("Sube uno o varios archivos .dat", type=["dat", "raw", "his"], accept_multiple_files=True)

if uploaded_files:
    summary_data = []

    for uploaded_file in uploaded_files:
        raw_bytes = uploaded_file.read()
        
        # 1. Extraer secuencias de texto ASCII (nombres de variables, Tags, subestaciones)
        # Esto busca palabras legibles ocultas en la cabecera binaria del archivo
        ascii_strings = re.findall(b'[a-zA-Z0-9_\\-\\.:]{4,}', raw_bytes[:1024])
        readable_tags = [s.decode('ascii', errors='ignore') for s in ascii_strings]
        
        # 2. Identificar posibles textos clave
        header_text = " | ".join(readable_tags[:10]) if readable_tags else "Sin texto identificable en cabecera"
        
        summary_data.append({
            "Nombre del Archivo": uploaded_file.name,
            "Tamaño (MB)": round(len(raw_bytes) / (1024 * 1024), 2),
            "Identificadores / Tags Encontrados": header_text
        })

    # Mostrar la tabla comparativa de todos los .dat subidos
    st.subheader("📋 Resumen de Identificación de Archivos")
    df_summary = pd.DataFrame(summary_data)
    st.dataframe(df_summary, use_container_width=True)
    
    st.info("💡 **Consejo:** Compara los 'Tags Encontrados' con las etiquetas que ves en las pantallas del unifilar VICOS para saber cuál archivo procesar.")