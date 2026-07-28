import streamlit as st
import pandas as pd
import numpy as np
import string
import re

# Configuración de la página
st.set_page_config(
    page_title="Inspector Binario SCADA - Matriz Dinámica",
    page_icon="⚡",
    layout="wide"
)

st.title("⚡ Inspector SCADA: Reorganizador de Columnas Binarias")
st.caption("Juega con el número de canales/columnas para ajustar la estructura interna del archivo .dat")

# --- PANEL LATERAL DE CARGA Y CONTROLES ---
st.sidebar.header("📂 1. Cargar Archivos")

uploaded_at = st.sidebar.file_uploader(
    "Archivos de atributos (.~at / .at):",
    type=None,
    accept_multiple_files=True
)

uploaded_dat = st.sidebar.file_uploader(
    "Archivos históricos (.dat):",
    type=None,
    accept_multiple_files=True
)

st.sidebar.markdown("---")
st.sidebar.header("🎛️ 2. Estructura de la Matriz")

# Control dinámico para "jugar" con las columnas
num_columnas = st.sidebar.slider(
    "Número de Columnas / Canales (Variables):",
    min_value=1,
    max_value=12,
    value=1,
    step=1,
    help="Cambia este valor para ver cómo se redistribuye la tira plana de bytes en múltiples canales."
)

# --- FUNCIONES DE DECODIFICACIÓN ---

def limpiar_id(nombre_archivo):
    nombre_sin_ext = re.sub(r'[\.\~](at|dat|raw|his|xml).*$', '', nombre_archivo, flags=re.IGNORECASE)
    return nombre_sin_ext.strip().upper()

def extraer_metadata_at(file_at):
    bytes_at = file_at.read()
    try:
        texto = bytes_at.decode('latin-1', errors='ignore')
    except Exception:
        texto = str(bytes_at)
    
    caracteres_ok = set(string.ascii_letters + string.digits + " _-.:/@")
    texto_limpio = "".join([c if c in caracteres_ok else " " for c in texto])
    palabras = [p.strip() for p in texto_limpio.split() if len(p.strip()) >= 2 and not p.strip().isdigit()]
    
    unidades_conocidas = ["KV", "V", "A", "KA", "MW", "MVAR", "HZ", "AMP"]
    unidad_hallada = "Valor"
    for p in palabras:
        if p.upper() in unidades_conocidas:
            unidad_hallada = p
            break
            
    tag_hallado = palabras[0] if palabras else limpiar_id(file_at.name)
    return {"Tag": tag_hallado, "Unidad": unidad_hallada}

@st.cache_data
def decodificar_dat_vectorizado(content_bytes):
    data = np.frombuffer(content_bytes, dtype='<f4')
    mask = ~np.isnan(data) & ~np.isinf(data) & (data != 0.0) & (np.abs(data) < 500000.0)
    return data[mask]

# --- PROCESAMIENTO Y VISUALIZACIÓN ---

if uploaded_dat:
    diccionario_metadata = {}
    if uploaded_at:
        for f_at in uploaded_at:
            key_id = limpiar_id(f_at.name)
            diccionario_metadata[key_id] = extraer_metadata_at(f_at)
            
    archivo_sel = st.selectbox("Selecciona el archivo .dat a inspeccionar:", [f.name for f in uploaded_dat])
    f_dat = next(f for f in uploaded_dat if f.name == archivo_sel)
    
    bytes_dat = f_dat.read()
    key_dat = limpiar_id(f_dat.name)
    
    # 1. Obtener la tira plana de datos
    valores_planos = decodificar_dat_vectorizado(bytes_dat)
    total_muestras = len(valores_planos)
    
    # 2. Informar sobre el emparejamiento con el .~at
    if key_dat in diccionario_metadata:
        tag_base = diccionario_metadata[key_dat]["Tag"]
        unidad_base = diccionario_metadata[key_dat]["Unidad"]
        st.success(f" Metadatos vinculados desde `.~at`: **{tag_base}** ({unidad_base})")
    else:
        tag_base = f"CANAL_{key_dat}"
        unidad_base = "Lectura"
        st.warning("⚠️ Sin metadatos .~at asociados. Usando nombres de columna genéricos.")
        
    st.markdown("---")
    
    # 3. Lógica para reorganizar en N columnas usando reshape
    sobrantes = total_muestras % num_columnas
    muestras_utiles = total_muestras - sobrantes
    
    if sobrantes != 0:
        st.info(f"💡 **Aviso de Matriz:** Con {num_columnas} columna(s), se forman **{muestras_utiles // num_columnas:,} filas completas** y quedan {sobrantes} dato(s) sueltos al final que se omiten para mantener la tabla simétrica.")
    else:
        st.success(f" Matriz perfecta: {total_muestras:,} datos divididos exactamente en **{num_columnas} columna(s)** ({total_muestras // num_columnas:,} filas).")
        
    # Reorganizar la tira con NumPy
    valores_recortados = valores_planos[:muestras_utiles]
    matriz_reorganizada = valores_recortados.reshape(-1, num_columnas)
    
    # Crear nombres para las columnas
    nombres_cols = [f"{tag_base}_Ch{i+1} ({unidad_base})" for i in range(num_columnas)]
    
    df_matriz = pd.DataFrame(matriz_reorganizada, columns=nombres_cols)
    df_matriz.insert(0, "Fila / Instante", np.arange(1, len(df_matriz) + 1))
    
    # 4. Mostrar Resultados
    col_tabla, col_graf = st.columns([1, 1])
    
    with col_tabla:
        st.subheader(f"📋 Tabla Reorganizada ({num_columnas} Columna/s)")
        st.dataframe(df_matriz.head(500), use_container_width=True)
        
        # Descarga en TXT de la matriz armada
        txt_bytes = df_matriz.to_csv(index=False, sep='\t').encode('utf-8')
        st.download_button(
            label="💾 Descargar esta estructura en TXT",
            data=txt_bytes,
            file_name=f"{key_dat}_{num_columnas}col.txt",
            mime="text/plain"
        )
        
    with col_graf:
        st.subheader("📈 Comparativa Visual de Canales")
        # Graficar todas las columnas simultáneamente
        st.line_chart(df_matriz.set_index("Fila / Instante"))

else:
    st.info("👈 Sube un archivo `.dat` en el panel izquierdo para empezar a ajustar las columnas.")