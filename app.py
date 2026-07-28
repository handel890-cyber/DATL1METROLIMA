import streamlit as st
import pandas as pd
import numpy as np
import struct
import string
import io

st.set_page_config(page_title="Analizador Multi-Columna SCADA", layout="wide")

st.title("⚡ Decodificador de Estructura Multicolumna SCADA (.dat)")
st.write("Ajusta los parámetros del registro binario para desempaquetar correctamente todas las columnas de cada fila.")

uploaded_file = st.file_uploader("Sube tu archivo MESSAGES.dat u otro histórico", type=["dat", "raw", "his", "txt"])

if uploaded_file is not None:
    raw_bytes = uploaded_file.read()
    total_bytes = len(raw_bytes)
    st.info(f"Tamaño total del archivo: {total_bytes} bytes")

    st.sidebar.header("⚙️ Configuración del Registro Binario")
    
    # Permitir al usuario elegir cuántos bytes ocupa una FILA COMPLETA en el SCADA
    # Los registros de eventos/mensajes en Siemens suelen medir 16, 24, 32, 48 o 64 bytes por fila
    bytes_per_row = st.sidebar.number_input(
        "Tamaño de Fila/Registro (Bytes por fila):", 
        min_value=8, 
        max_value=128, 
        value=32, 
        step=4,
        help="Siemens VICOS suele usar registros de 24, 32 o 48 bytes para alojar fecha, TagID, valor y estado."
    )
    
    num_rows = total_bytes // bytes_per_row
    st.sidebar.write(f"Filas estimadas: **{num_rows}**")

    # Selección de formato para desempaquetar las columnas dentro de la fila
    # Un registro típico de 32 bytes puede tener 4 enteros (Int32) + 4 flotantes (Float32)
    st.sidebar.subheader("Estructura de Columnas por Fila")
    modo_desempaquetado = st.sidebar.radio(
        "Modo de interpretación:",
        ["Mixto (Texto + Números)", "Solo Flotantes (Float32)", "Solo Enteros (Int32)"]
    )

    filas_extraidas = []
    caracteres_validos = set(string.ascii_letters + string.digits + " _-.:/@")

    for i in range(0, total_bytes - (total_bytes % bytes_per_row), bytes_per_row):
        chunk = raw_bytes[i:i + bytes_per_row]
        fila = {}
        
        # Columna 0: Índice de Fila
        fila["Fila_ID"] = (i // bytes_per_row) + 1
        
        if modo_desempaquetado == "Solo Flotantes (Float32)":
            # Divide la fila en N columnas de 4 bytes como Float
            cols_count = bytes_per_row // 4
            for c in range(cols_count):
                sub_chunk = chunk[c*4 : (c+1)*4]
                try:
                    val = struct.unpack('<f', sub_chunk)[0]
                    fila[f"Col_Float_{c+1}"] = round(val, 4) if not np.isnan(val) and not np.isinf(val) else None
                except:
                    fila[f"Col_Float_{c+1}"] = None
                    
        elif modo_desempaquetado == "Solo Enteros (Int32)":
            # Divide la fila en N columnas de 4 bytes como Int
            cols_count = bytes_per_row // 4
            for c in range(cols_count):
                sub_chunk = chunk[c*4 : (c+1)*4]
                try:
                    val = struct.unpack('<i', sub_chunk)[0]
                    fila[f"Col_Int_{c+1}"] = val
                except:
                    fila[f"Col_Int_{c+1}"] = None
                    
        else: # Mixto
            # Extrae texto limpio de los primeros bytes de la fila (Tag/Estado)
            texto_raw = "".join([chr(b) if chr(b) in caracteres_validos else "" for b in chunk])
            fila["Texto_Identificador"] = texto_raw.strip() if texto_raw.strip() else "N/A"
            
            # Extrae posibles flotantes en los siguientes bloques de 4 bytes
            cols_count = bytes_per_row // 4
            for c in range(cols_count):
                sub_chunk = chunk[c*4 : (c+1)*4]
                try:
                    val = struct.unpack('<f', sub_chunk)[0]
                    if not np.isnan(val) and not np.isinf(val) and -500000.0 < val < 500000.0:
                        fila[f"Valor_Num_{c+1}"] = round(val, 2)
                    else:
                        fila[f"Valor_Num_{c+1}"] = None
                except:
                    fila[f"Valor_Num_{c+1}"] = None

        filas_extraidas.append(fila)

    if filas_extraidas:
        df = pd.DataFrame(filas_extraidas)
        
        st.subheader("📋 Tabla Multicolumna Desempaquetada")
        st.write("Prueba cambiar el **Tamaño de Fila (Bytes)** en el panel de la izquierda hasta que las columnas queden alineadas correctamente.")
        st.dataframe(df.head(500), use_container_width=True)
        
        # Opciones de Exportación
        st.markdown("---")
        st.subheader("📥 Exportar Tabla Estructurada")
        
        txt_buffer = df.to_csv(index=False, sep='\t')
        st.download_button(
            label="Descargar Tabla en formato .TXT (Separado por Tabuladores)",
            data=txt_buffer,
            file_name="scada_messages_multicolumna.txt",
            mime="text/plain"
        )