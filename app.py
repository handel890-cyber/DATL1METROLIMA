import streamlit as st
import pandas as pd
import numpy as np
import struct
import re
import io

# Configuración de la página
st.set_page_config(
    page_title="Analizador y Extractor de Archivos SCADA (.dat)",
    page_icon="⚡",
    layout="wide"
)

st.title("⚡ Analizador e Identificador Integral de Archivos .dat")
st.markdown("""
Esta aplicación te permite **inspeccionar múltiples archivos `.dat`** para:
1. **Identificar qué variable/Tag contiene cada archivo** (leyendo marcas e identificadores en la cabecera).
2. **Extraer los valores numéricos** (voltajes, corrientes, potencias).
3. **Graficar las curvas** y exportar todo a un archivo `.txt` o `.csv` limpio.
""")

# Cargador de archivos múltiples
uploaded_files = st.file_uploader(
    "Carga uno o varios archivos .dat de tu carpeta SCADA:",
    type=["dat", "raw", "his", "txt"],
    accept_multiple_files=True
)

def extraer_texto_cabecera(raw_bytes, max_bytes=2048):
    """Extrae secuencias de texto ASCII visibles en los primeros bytes del archivo (Metadata/Tags)."""
    bytes_cabecera = raw_bytes[:max_bytes]
    # Buscar patrones de texto ASCII de al menos 3 caracteres (nombres de subestaciones, tags, unidades)
    coincidencias = re.findall(b'[a-zA-Z0-9_\\-\\.:/]{3,}', bytes_cabecera)
    textos = [c.decode('ascii', errors='ignore') for c in coincidencias]
    # Filtrar palabras comunes o muy cortas
    textos_filtrados = [t for t in textos if not t.isdigit()]
    return textos_filtrados

def decodificar_floats_binarios(raw_bytes):
    """Desempaqueta números flotantes de 32 bits (float32) contenidos en los bytes binarios."""
    total_bytes = len(raw_bytes)
    record_size = 4  # 4 bytes por flotante
    valores = []
    
    # Recorrer bloque a bloque los bytes
    for i in range(0, total_bytes - (total_bytes % record_size), record_size):
        chunk = raw_bytes[i:i + record_size]
        try:
            val = struct.unpack('<f', chunk)[0] # Little-endian float
            # Filtrar valores NaN, Infinitos o fuera de rangos razonables de mediciones eléctricas
            if not np.isnan(val) and not np.isinf(val):
                if -500000.0 < val < 500000.0 and val != 0.0:
                    valores.append(val)
        except Exception:
            continue
            
    return valores

def decodificar_texto_plano(raw_bytes):
    """Intenta decodificar el archivo si contiene texto plano separado por comas, tabulaciones o punto y coma."""
    try:
        texto = raw_bytes.decode('utf-8', errors='ignore')
        lineas = [l.strip() for l in texto.splitlines() if len(l.strip()) > 0 and not l.startswith('\x00')]
        if len(lineas) > 5:
            return lineas
    except Exception:
        pass
    return None

if uploaded_files:
    st.markdown("---")
    st.header("1. Resumen de Identificación de Archivos")
    
    resumen_list = []
    detalles_archivos = {}

    for file in uploaded_files:
        contenido = file.read()
        tamano_mb = len(contenido) / (1024 * 1024)
        
        # Intentar extraer identificadores de texto de la cabecera
        tags_encontrados = extraer_texto_cabecera(contenido)
        identificador_str = " | ".join(tags_encontrados[:8]) if tags_encontrados else "Sin texto ASCII (Binario Puro)"
        
        # Intentar extraer valores numéricos binarios
        valores_num = decodificar_floats_binarios(contenido)
        lineas_texto = decodificar_texto_plano(contenido)
        
        es_texto = lineas_texto is not None and len(lineas_texto) > 0
        tipo_formato = "Texto Plano / CSV" if es_texto else f"Binario ({len(valores_num)} puntos)"
        
        resumen_list.append({
            "Nombre del Archivo": file.name,
            "Tamaño (MB)": round(tamano_mb, 2),
            "Formato Detectado": tipo_formato,
            "Tags e Identificadores Encontrados en Cabecera": identificador_str
        })
        
        detalles_archivos[file.name] = {
            "bytes": contenido,
            "tags": tags_encontrados,
            "valores_num": valores_num,
            "lineas_texto": lineas_texto
        }

    # Mostrar tabla resumen
    df_resumen = pd.DataFrame(resumen_list)
    st.dataframe(df_resumen, use_container_width=True)
    
    st.markdown("---")
    st.header("2. Inspección y Extracción Detallada por Archivo")
    
    # Selector de archivo a inspeccionar
    archivo_seleccionado = st.selectbox(
        "Selecciona un archivo para ver su contenido completo, curva y exportar a .txt:",
        options=list(detalles_archivos.keys())
    )
    
    if archivo_seleccionado:
        info = detalles_archivos[archivo_seleccionado]
        st.subheader(f"📄 Analizando: `{archivo_seleccionado}`")
        
        # Pestañas de análisis
        tab1, tab2, tab3 = st.tabs(["🏷️ Identificadores / Tags", "📊 Curva y Tabla de Datos", "📥 Exportar a .TXT"])
        
        with tab1:
            st.markdown("### Cadenas de texto encontradas en la cabecera del archivo:")
            if info["tags"]:
                st.write("Estas palabras o combinaciones suelen indicar el **nombre del Tag**, la **subestación** o la **unidad de medida**:")
                df_tags = pd.DataFrame({"Texto / Tag Detectado": info["tags"]})
                st.dataframe(df_tags, use_container_width=True)
            else:
                st.warning("No se encontraron etiquetas de texto en los primeros bytes del archivo. Corresponde a una estructura binaria sin metadatos de cabecera.")

        with tab2:
            st.markdown("### Valores y Gráfico de Curva")
            if info["lineas_texto"]:
                st.info("El archivo se leyó como **texto estructurado**.")
                try:
                    df_txt = pd.read_csv(io.StringIO("\n".join(info["lineas_texto"])), sep=r'[\t;,|]', engine='python')
                    st.dataframe(df_txt.head(500), use_container_width=True)
                    
                    num_cols = df_txt.select_dtypes(include=[np.number]).columns
                    if len(num_cols) > 0:
                        col_var = st.selectbox("Selecciona columna a graficar:", num_cols)
                        st.line_chart(df_txt[col_var])
                except Exception as e:
                    st.text_area("Líneas de texto extraídas", "\n".join(info["lineas_texto"][:200]), height=300)
            
            elif info["valores_num"]:
                st.success(f"Se desempaquetaron **{len(info['valores_num'])} puntos numéricos** desde la estructura binaria.")
                
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
                st.error("No se pudieron extraer automáticamente muestras numéricas con el patrón estándar. Es necesario aplicar una máscara binaria específica.")

        with tab3:
            st.markdown("### Generar archivo .TXT listo para descargar")
            
            if info["valores_num"]:
                df_export = pd.DataFrame({
                    "Muestra": range(1, len(info["valores_num"]) + 1),
                    "Valor_Medido": info["valores_num"]
                })
                # Crear buffer de texto plano en formato separado por tabuladores
                txt_buffer = df_export.to_csv(index=False, sep='\t')
                
                st.download_button(
                    label=f"💾 Descargar `{archivo_seleccionado}.txt`",
                    data=txt_buffer,
                    file_name=f"{archivo_seleccionado}_extraido.txt",
                    mime="text/plain"
                )
                st.code(txt_buffer[:500], language="text")
            elif info["lineas_texto"]:
                txt_content = "\n".join(info["lineas_texto"])
                st.download_button(
                    label=f"💾 Descargar `{archivo_seleccionado}.txt`",
                    data=txt_content,
                    file_name=f"{archivo_seleccionado}_extraido.txt",
                    mime="text/plain"
                )
