import streamlit as st
import pandas as pd
import re
import io

st.set_page_config(page_title="Extractor de Curvas SCADA", layout="wide")

st.title("⚡ Extractor y Visualizador de Curvas SCADA (.dat)")
st.write("Sube tu archivo `.dat` del sistema VICOS/SCADA para procesarlo y visualizar las lecturas de voltaje y corriente.")

# Cargador de archivos en Streamlit
uploaded_file = st.file_uploader("Selecciona el archivo .dat", type=["dat", "txt", "raw"])

if uploaded_file is not None:
    st.success("Archivo cargado con éxito. Procesando contenido...")
    
    # Lectura del contenido en bytes
    content_bytes = uploaded_file.read()
    
    # Intento de extracción de texto plano/limpieza de bytes
    try:
        # Decodificar ignorando caracteres binarios no imprimibles
        text_content = content_bytes.decode('utf-8', errors='ignore')
        lines = text_content.splitlines()
        
        # Filtrar líneas válidas que contengan datos numéricos o marcas de tiempo
        clean_lines = [line.strip() for line in lines if len(line.strip()) > 0 and not line.startswith('\x00')]
        
        if len(clean_lines) > 0:
            st.subheader("📋 Vista previa de datos extraídos")
            
            # Intento de parseo automático como CSV/TSV
            try:
                df = pd.read_csv(io.StringIO("\n".join(clean_lines)), sep=r'[\t;,|]', engine='python')
                st.dataframe(df.head(100), use_container_width=True)
                
                # Botón para descargar en formato .txt / .csv limpio
                csv_bytes = df.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="📥 Descargar datos limpios (.txt / .csv)",
                    data=csv_bytes,
                    file_name="curvas_scada_limpias.txt",
                    mime="text/plain"
                )
                
                # Gráfico si hay columnas numéricas
                numeric_cols = df.select_dtypes(include=['float64', 'int64']).columns
                if len(numeric_cols) > 0:
                    st.subheader("📈 Gráfico de Curvas")
                    col_selected = st.selectbox("Selecciona la variable a graficar:", numeric_cols)
                    st.line_chart(df[col_selected])
                    
            except Exception as e:
                st.warning("No se pudo estructurar automáticamente en tabla. Mostrando texto extraído:")
                st.text_area("Contenido extraído", "\n".join(clean_lines[:200]), height=300)
        else:
            st.error("El archivo no contiene texto legible directamente. Es un binario cerrado del SCADA.")
            
    except Exception as ex:
        st.error(f"Error al procesar el archivo: {ex}")