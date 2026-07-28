import streamlit as st
import pandas as pd
import numpy as np
import struct
import string
import re
import io

# Configuración de la aplicación
st.set_page_config(
    page_title="Extractor Binario SCADA VICOS",
    page_icon="⚡",
    layout="wide"
)

st.title("⚡ Extractor y Decodificador de Archivos SCADA (.dat)")
st.markdown("""
Esta herramienta limpia los caracteres binarios de control no imprimibles para:
1. **Identificar la variable / Tag** que contiene el archivo en su cabecera.
2. **Extraer los valores numéricos reales** (voltajes, corrientes, potencias) sin que aparezcan símbolos extraños.
3. **Graficar las curvas** y exportar un archivo `.txt` o `.csv` limpio.
""")

# Cargador de archivos
uploaded_files = st.file_uploader(
    "Carga uno o varios archivos .dat de tu carpeta SCADA:",
    type=["dat", "raw", "his", "txt"],
    accept_multiple_files=True
)

def extraer_metadata_limpia(raw_bytes, max_bytes=2048):
    """
    Filtra los bytes de control no imprimibles (como , \x00, ꑒ) y extrae únicamente
    cadenas de texto ASCII legibles (nombres de subestaciones, Tags o variables).
    """
    bytes_cabecera = raw_bytes[:max_bytes]
    
    # 1. Convertir a caracteres filtrando símbolos de control no imprimibles
    caracteres_validos = set(string.ascii_letters + string.digits + " _-.:/@")
    texto_filtrado = "".join([chr(b) if chr(b) in caracteres_validos else " " for b in bytes_cabecera])
    
    # 2. Extraer palabras estructuradas de al menos 3 caracteres
    palabras = [p.strip() for p in texto_filtrado.split() if len(p.strip()) >= 3 and not p.strip().isdigit()]
    
    return palabras

def decodificar_valores_numericos(raw_bytes):
    """
    Desempaqueta bloques binarios directamente a flotantes de 32 bits (IEEE 754),
    evitando traducir números a símbolos de texto.
    """
    total_bytes = len(raw_bytes)
    record_size = 4  # 4 bytes por número flotante
    valores = []
    
    # Recorrer el archivo de 4 en 4 bytes
    for i in range(0, total_bytes - (total_bytes % record_size), record_size):
        chunk = raw_bytes[i:i + record_size]
        try:
            # Little-endian float (<f) es la estructura estándar de Windows/Siemens
            val = struct.unpack('<f', chunk)[0]
            
            # Filtrar valores infinitos, NaN y fuera de rango eléctrico coherente
            if not np.isnan(val) and not np.isinf(val):
                if -500000.0 < val < 500000.0 and val != 0.0:
                    valores.append(val)
        except Exception:
            continue
            
    return valores

def procesar_texto_plano(raw_bytes):
    """Si el archivo resulta ser texto delimitado por comas/tabulaciones, lo extrae."""
    try:
        texto = raw_bytes.decode('utf-8', errors='ignore')
        lineas = [l.strip() for l in texto.splitlines() if len(l.strip()) > 0 and not l.startswith('\x00')]
        if len(lineas) > 5 and (',' in lineas[0] or '\t' in lineas[0] or ';' in lineas[0]):
            return lineas
    except Exception:
        pass
    return None

if uploaded_files:
    st.markdown("---")
    st.header("1. Resumen e Identificación de Archivos Subidos")
    
    resumen_list = []
    detalles_archivos = {}

    for file in uploaded_files:
        contenido = file.read()
        tamano_mb = len(contenido) / (1024 * 1024)
        
        # 1. Extraer palabras/tags limpias
        tags_encontrados = extraer_metadata_limpia(contenido)
        identificador_str = " | ".join(tags_encontrados[:6]) if tags_encontrados else "Binario Puro (Sin Metadatos)"
        
        # 2. Decodificar números
        valores_num = decodificar_valores_numericos(contenido)
        lineas_texto = procesar_texto_plano(contenido)
        
        es_texto = lineas_texto is not None
        tipo_formato = "Texto CSV/TSV" if es_texto else f"Binario SCADA ({len(valores_num)} lecturas)"
        
        resumen_list.append({
            "Nombre del Archivo": file.name,
            "Tamaño (MB)": round(tamano_mb, 2),
            "Formato Detectado": tipo_formato,
            "Tags y Palabras Legibles Encontradas": identificador_str
        })
        
        detalles_archivos[file.name] = {
            "bytes": contenido,
            "tags": tags_encontrados,
            "valores_num": valores_num,
            "lineas_texto": lineas_texto
        }

    # Mostrar la tabla comparativa
    df_resumen = pd.DataFrame(resumen_list)
    st.dataframe(df_resumen, use_container_width=True)
    
    st.markdown("---")
    st.header("2. Extractor y Graficador de Curva")
    
    archivo_seleccionado = st.selectbox(
        "Selecciona el archivo que deseas inspeccionar:",
        options=list(detalles_archivos.keys())
    )
    
    if archivo_seleccionado:
        info = detalles_archivos[archivo_seleccionado]
        
        tab_tags, tab_curva, tab_export = st.tabs([
            "🏷️ Identificación / Tags", 
            "📈 Tabla y Curva Numérica", 
            "💾 Exportar a .TXT"
        ])
        
        with tab_tags:
            st.subheader("Información extraída de la cabecera")
            if info["tags"]:
                st.write("Palabras y códigos legibles encontrados (útil para identificar a qué variable corresponde en el SCADA):")
                df_tags = pd.DataFrame({"Texto / Tag Limpio": info["tags"]})
                st.dataframe(df_tags, use_container_width=True)
            else:
                st.warning("No se encontraron etiquetas ASCII legibles. El archivo es un bloque binario directo de mediciones.")

        with tab_curva:
            st.subheader("Datos Numéricos Desempaquetados")
            
            if info["lineas_texto"]:
                st.info("Formato de texto plano detectado.")
                try:
                    df_csv = pd.read_csv(io.StringIO("\n".join(info["lineas_texto"])), sep=r'[\t;,|]', engine='python')
                    st.dataframe(df_csv.head(500), use_container_width=True)
                    num_cols = df_csv.select_dtypes(include=[np.number]).columns
                    if len(num_cols) > 0:
                        col_var = st.selectbox("Selecciona columna a graficar:", num_cols)
                        st.line_chart(df_csv[col_var])
                except Exception:
                    st.text_area("Contenido extraído", "\n".join(info["lineas_texto"][:200]), height=300)
            
            elif info["valores_num"]:
                st.success(f"Se extrajeron correctamente **{len(info['valores_num'])} mediciones numéricas**.")
                
                df_bin = pd.DataFrame({
                    "Muestra": range(1, len(info["valores_num"]) + 1),
                    "Valor_Medido": info["valores_num"]
                })
                
                col_tabla, col_graf = st.columns([1, 2])
                with col_tabla:
                    st.dataframe(df_bin.head(500), use_container_width=True)
                with col_graf:
                    st.line_chart(df_bin.set_index("Muestra"))
            else:
                st.error("No se encontraron lecturas flotantes estándar en este archivo.")

        with tab_export:
            st.subheader("Generar archivo .TXT legible")
            
            if info["valores_num"]:
                df_export = pd.DataFrame({
                    "Muestra": range(1, len(info["valores_num"]) + 1),
                    "Valor_Medido": info["valores_num"]
                })
                txt_data = df_export.to_csv(index=False, sep='\t')
                
                st.download_button(
                    label=f"📥 Descargar `{archivo_seleccionado}.txt`",
                    data=txt_data,
                    file_name=f"{archivo_seleccionado}_limpio.txt",
                    mime="text/plain"
                )
                st.markdown("**Vista previa del archivo .TXT a descargar:**")
                st.code(txt_data[:400], language="text")
                
            elif info["lineas_texto"]:
                txt_content = "\n".join(info["lineas_texto"])
                st.download_button(
                    label=f"📥 Descargar `{archivo_seleccionado}.txt`",
                    data=txt_content,
                    file_name=f"{archivo_seleccionado}_limpio.txt",
                    mime="text/plain"
                )