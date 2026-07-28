import streamlit as st
import pandas as pd
import struct

st.set_page_config(page_title="Extractor Binario SCADA", layout="wide")

st.title("⚡ Extractor de Archivos Binarios SCADA (.dat)")
st.write("Esta aplicación desempaqueta los bytes numéricos (`float32`) de archivos `.dat` cerrados o binarios.")

uploaded_file = st.file_uploader("Sube tu archivo .dat binario", type=["dat", "raw", "his"])

if uploaded_file is not None:
    # Leer el archivo como bytes puros (sin intentar convertir a texto)
    raw_bytes = uploaded_file.read()
    total_bytes = len(raw_bytes)
    st.info(f"Tamaño del archivo: {total_bytes / (1024*1024):.2f} MB ({total_bytes} bytes)")
    
    # Cada número flotante (float) en arquitectura de 32 bits ocupa 4 bytes
    record_size = 4 
    num_records = total_bytes // record_size
    
    values = []
    
    # Recorremos el archivo byte por byte extractando valores flotantes (IEEE 754)
    # '<f' indica un número flotante de 32 bits (Little-Endian standard en Windows)
    for i in range(0, total_bytes - (total_bytes % record_size), record_size):
        chunk = raw_bytes[i:i+record_size]
        try:
            val = struct.unpack('<f', chunk)[0]
            # Filtramos valores absurdos/infinitos propios del relleno de cabecera
            if -100000.0 < val < 100000.0 and val != 0.0:
                values.append(val)
        except Exception:
            pass

    if values:
        st.success(f"¡Éxito! Se desempaquetaron {len(values)} valores numéricos reales del archivo binario.")
        
        # Crear DataFrame con los valores extraídos
        df = pd.DataFrame({'Índice_Muestra': range(1, len(values) + 1), 'Valor_Sensado': values})
        
        col1, col2 = st.columns([1, 2])
        
        with col1:
            st.subheader("📋 Tabla de Valores Extraídos")
            st.dataframe(df.head(200), use_container_width=True)
            
            # Exportar a .txt / .csv
            txt_data = df.to_csv(index=False, sep='\t').encode('utf-8')
            st.download_button(
                label="📥 Descargar como archivo .txt",
                data=txt_data,
                file_name="datos_scada_desempaquetados.txt",
                mime="text/plain"
            )

        with col2:
            st.subheader("📈 Gráfico de la Curva")
            st.line_chart(df['Valor_Sensado'])
    else:
        st.error("No se pudieron extraer valores numéricos válidos. La estructura de bytes requiere una máscara específica.")