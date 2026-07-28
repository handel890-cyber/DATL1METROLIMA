import streamlit as st
import pandas as pd
import numpy as np
import struct
import string
import re
import io

# Configuración inicial de la página
st.set_page_config(
    page_title="Sistema Integrado SCADA (.AT + .dat)",
    page_icon="⚡",
    layout="wide"
)

st.title("⚡ Extractor e Interpretador Integrado SCADA (VICOS)")
st.markdown("""
Esta aplicación realiza la **vinculación automática** entre:
* **El Archivo .AT (Metadatos / Diccionario):** Extrae nombres de Tags, unidades, rangos y descripciones del unifilar.
* **El Archivo .dat (Datos Históricos Binarios):** Desempaqueta las series temporales de voltajes, corrientes y potencias.
""")

st.sidebar.header("📂 Cargar Archivos del Servidor SCADA")

# Carga de archivos .AT y .dat
uploaded_at = st.sidebar.file_uploader(
    "1. Sube el/los archivo(s) .AT (Diccionario)",
    type=["at", "AT", "xml", "dbf"],
    accept_multiple_files=True
)

uploaded_dat = st.sidebar.file_uploader(
    "2. Sube el/los archivo(s) .dat (Históricos)",
    type=None,
    accept_multiple_files=True
)

st.sidebar.markdown("---")
st.sidebar.header("⚙️ Ajustes de Lectura Binaria")
bytes_per_row = st.sidebar.number_input("Tamaño de registro (Bytes/Fila)", min_value=4, max_value=128, value=32, step=4)

def extraer_metadatos_at(file_at):
    """Lee el archivo .AT y busca los nombres de Tags, unidades de medida y descripciones."""
    bytes_at = file_at.read()
    try:
        texto = bytes_at.decode('latin-1', errors='ignore')
    except Exception:
        texto = str(bytes_at)
    
    # Buscar patrones comunes de Tags SCADA (ej. SUB_01_V, BARRA_KV, L1_AMP, etc.)
    caracteres_legibles = set(string.ascii_letters + string.digits + " _-.:/@")
    texto_limpio = "".join([c if c in caracteres_legibles else " " for c in texto])
    
    palabras = [p.strip() for p in texto_limpio.split() if len(p.strip()) >= 3 and not p.strip().isdigit()]
    
    # Identificar posibles unidades eléctricas
    unidades_posibles = ["KV", "V", "A", "KA", "MW", "MVAR", "HZ", "AMP"]
    unidades_encontradas = [p for p in palabras if p.upper() in unidades_posibles]
    unidad = unidades_encontradas[0] if unidades_encontradas else "Valor"
    
    nombre_tag = palabras[0] if palabras else file_at.name.replace(".AT", "").replace(".at", "")
    
    return {
        "Nombre_Tag": nombre_tag,
        "Unidad": unidad,
        "Texto_Completo_AT": texto,
        "Palabras_Clave": palabras[:10]
    }

def decodificar_dat_binario(file_dat, row_size):
    """Desempaqueta el archivo .dat binario en lecturas flotantes estructuradas."""
    raw_bytes = file_dat.read()
    total_bytes = len(raw_bytes)
    valores = []
    
    # Desempaquetado de bloques de 4 bytes (IEEE 754 Float32)
    for i in range(0, total_bytes - 3, 4):
        chunk = raw_bytes[i:i+4]
        try:
            val = struct.unpack('<f', chunk)[0]
            # Filtrar NaN, infinitos o rangos absurdos
            if not np.isnan(val) and not np.isinf(val):
                if -500000.0 < val < 500000.0 and val != 0.0:
                    valores.append(round(val, 3))
        except Exception:
            continue
            
    return valores

# Proceso Principal
if uploaded_dat:
    diccionario_at = {}
    
    # 1. Mapear archivos .AT si se subieron
    if uploaded_at:
        st.success(f" Se cargaron {len(uploaded_at)} archivo(s) de atributos (.AT). Procesando diccionarios...")
        for f_at in uploaded_at:
            # Asociar por nombre base (ej. 'HIST_01.AT' se mapea a 'HIST_01')
            base_name = re.sub(r'\.(at|AT|xml|dbf)$', '', f_at.name)
            diccionario_at[base_name.upper()] = extraer_metadatos_at(f_at)
            
    # 2. Procesar archivos .dat
    mats_procesados = []
    
    for f_dat in uploaded_dat:
        base_name_dat = re.sub(r'\.(dat|RAW|raw|his)$', '', f_dat.name).upper()
        valores_num = decodificar_dat_binario(f_dat, bytes_per_row)
        
        # Buscar si hay un .AT equivalente para este .dat
        if base_name_dat in diccionario_at:
            info_tag = diccionario_at[base_name_dat]["Nombre_Tag"]
            unidad_tag = diccionario_at[base_name_dat]["Unidad"]
            origen_tag = f"Mapeado desde {f_dat.name.replace('.dat', '.AT')}"
        elif len(diccionario_at) == 1:
            # Si solo subió un .AT, asumimos que aplica al .dat cargado
            primer_key = list(diccionario_at.keys())[0]
            info_tag = diccionario_at[primer_key]["Nombre_Tag"]
            unidad_tag = diccionario_at[primer_key]["Unidad"]
            origen_tag = "Mapeado desde .AT único"
        else:
            info_tag = f"Tag_{base_name_dat}"
            unidad_tag = "Unidad_Desconocida"
            origen_tag = "Sin .AT asociado (Nombre genérico)"
            
        mats_procesados.append({
            "Archivo_DAT": f_dat.name,
            "Tag_Identificado": info_tag,
            "Unidad": unidad_tag,
            "Total_Lecturas": len(valores_num),
            "Origen_Metadata": origen_tag,
            "Lecturas_Num": valores_num
        })
        
    # Mostrar resumen de cruzamiento de datos
    st.subheader("📋 Mapa de Variables e Históricos Vinculados")
    df_resumen = pd.DataFrame([{
        "Archivo .DAT": m["Archivo_DAT"],
        "Tag / Variable Asignada": m["Tag_Identificado"],
        "Unidad": m["Unidad"],
        "Total de Muestras": m["Total_Lecturas"],
        "Estado del Mapeo": m["Origen_Metadata"]
    } for m in mats_procesados])
    
    st.dataframe(df_resumen, use_container_width=True)
    
    st.markdown("---")
    
    # Visualizador de Curvas por Archivo Seleccionado
    opciones_archivos = [m["Archivo_DAT"] for m in mats_procesados]
    archivo_sel = st.selectbox("Selecciona la variable a graficar y exportar:", opciones_archivos)
    
    datos_m = next(m for m in mats_procesados if m["Archivo_DAT"] == archivo_sel)
    
    col_graf, col_tabla = st.columns([2, 1])
    
    nombre_columna_final = f"{datos_m['Tag_Identificado']} ({datos_m['Unidad']})"
    df_curva = pd.DataFrame({
        "Muestra": range(1, len(datos_m["Lecturas_Num"]) + 1),
        nombre_columna_final: datos_m["Lecturas_Num"]
    })
    
    with col_graf:
        st.subheader(f"📈 Curva: {nombre_columna_final}")
        st.line_chart(df_curva.set_index("Muestra"))
        
    with col_tabla:
        st.subheader("📋 Muestras Extraídas")
        st.dataframe(df_curva.head(300), use_container_width=True)
        
        # Generar descarga en .txt
        txt_buffer = df_curva.to_csv(index=False, sep='\t')
        st.download_button(
            label=f"💾 Descargar `{datos_m['Archivo_DAT']}.txt`",
            data=txt_buffer,
            file_name=f"{datos_m['Tag_Identificado']}_extraido.txt",
            mime="text/plain"
        )

else:
    st.info("👈 Por favor, usa el panel lateral para subir los archivos `.AT` y `.dat` desde tu laptop.")