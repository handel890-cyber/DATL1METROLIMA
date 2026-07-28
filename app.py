import streamlit as st
import pandas as pd
import numpy as np
import string
import re

# Configuración de página
st.set_page_config(
    page_title="Extractor SCADA Ultra-Rápido",
    page_icon="⚡",
    layout="wide"
)

st.title("⚡ Extractor SCADA VICOS Ultra-Rápido")
st.caption("Procesamiento optimizado con NumPy para archivos binarios pesados (.dat y .~at)")

# --- PANEL LATERAL DE CARGA ---
st.sidebar.header("📂 Carga de Archivos")

# type=None permite subir .~at, .at~, .dat, etc. sin bloqueos de Streamlit
uploaded_at = st.sidebar.file_uploader(
    "1. Sube archivos de atributos (.~at / .at):",
    type=None,
    accept_multiple_files=True
)

uploaded_dat = st.sidebar.file_uploader(
    "2. Sube archivos históricos (.dat):",
    type=None,
    accept_multiple_files=True
)

st.sidebar.markdown("---")
st.sidebar.header("⚙️ Ajustes de Rendimiento")
frecuencia_muestreo = st.sidebar.number_input("Intervalo entre lecturas (Segundos)", min_value=1, value=1)

# --- FUNCIONES OPTIMIZADAS ---

def limpiar_id(nombre_archivo):
    """Limpia la extensión e identificadores temporales (~at, .dat) para cruzar nombres."""
    nombre_sin_ext = re.sub(r'[\.\~](at|dat|raw|his|xml).*$', '', nombre_archivo, flags=re.IGNORECASE)
    return nombre_sin_ext.strip().upper()

def extraer_metadata_at(file_at):
    """Extrae palabras clave y unidades del archivo de atributos .~at"""
    bytes_at = file_at.read()
    try:
        texto = bytes_at.decode('latin-1', errors='ignore')
    except Exception:
        texto = str(bytes_at)
    
    # Filtrar caracteres no imprimibles
    caracteres_ok = set(string.ascii_letters + string.digits + " _-.:/@")
    texto_limpio = "".join([c if c in caracteres_ok else " " for c in texto])
    palabras = [p.strip() for p in texto_limpio.split() if len(p.strip()) >= 2 and not p.strip().isdigit()]
    
    # Detectar unidad de medida eléctrica
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
    """
    DECODIFICACIÓN ULTRA-RÁPIDA USANDO NUMPY.
    Lee todo el array de bytes de golpe en lugar de usar bucles for.
    """
    # Convertir el buffer de bytes directamente a Float32 (Little-endian '<f4')
    data = np.frombuffer(content_bytes, dtype='<f4')
    
    # Filtrar mediante máscaras vectoriales (100x más rápido que Python puro)
    mask = ~np.isnan(data) & ~np.isinf(data) & (data != 0.0) & (np.abs(data) < 500000.0)
    valores_validos = data[mask]
    
    return np.round(valores_validos, 3)

# --- PROCESAMIENTO PRINCIPAL ---

if uploaded_dat:
    # 1. Indexar Metadatos .~at
    diccionario_metadata = {}
    if uploaded_at:
        for f_at in uploaded_at:
            key_id = limpiar_id(f_at.name)
            diccionario_metadata[key_id] = extraer_metadata_at(f_at)
            
    archivos_procesados = {}
    
    # 2. Procesar datos .dat con NumPy
    with st.spinner("Procesando datos a alta velocidad con NumPy..."):
        for f_dat in uploaded_dat:
            bytes_dat = f_dat.read()
            key_dat = limpiar_id(f_dat.name)
            
            # Decodificar usando la función vectorizada
            valores = decodificar_dat_vectorizado(bytes_dat)
            
            # Emparejamiento Automático
            if key_dat in diccionario_metadata:
                tag = diccionario_metadata[key_dat]["Tag"]
                unidad = diccionario_metadata[key_dat]["Unidad"]
                estado = "✅ Emparejado Automático"
            elif len(diccionario_metadata) == 1:
                unica_key = list(diccionario_metadata.keys())[0]
                tag = diccionario_metadata[unica_key]["Tag"]
                unidad = diccionario_metadata[unica_key]["Unidad"]
                estado = "⚠️ Usando .~at único disponible"
            else:
                tag = f"TAG_{key_dat}"
                unidad = "Lectura"
                estado = "❌ Sin .~at (Usando Nombre de Archivo)"
                
            archivos_procesados[f_dat.name] = {
                "Tag": tag,
                "Unidad": unidad,
                "Estado": estado,
                "Datos": valores
            }

    # 3. Resumen en Tabla
    st.subheader("📊 Mapeo y Cruce de Archivos Realizado")
    resumen_data = []
    for nombre_archivo, info in archivos_procesados.items():
        resumen_data.append({
            "Archivo .dat": nombre_archivo,
            "Tag Identificado": info["Tag"],
            "Unidad": info["Unidad"],
            "Total de Muestras": len(info["Datos"]),
            "Estado del Mapeo": info["Estado"]
        })
    st.dataframe(pd.DataFrame(resumen_data), use_container_width=True)
    
    st.markdown("---")
    
    # 4. Visualización y Descarga
    st.subheader("📈 Inspección y Exportación de Datos")
    
    archivo_seleccionado = st.selectbox("Selecciona un archivo para exportar:", list(archivos_procesados.keys()))
    info_sel = archivos_procesados[archivo_seleccionado]
    
    col_graf, col_export = st.columns([2, 1])
    
    # Crear DataFrame rápido
    df_export = pd.DataFrame({
        "Muestra": np.arange(1, len(info_sel["Datos"]) + 1),
        f"{info_sel['Tag']} ({info_sel['Unidad']})": info_sel["Datos"]
    })
    
    with col_graf:
        # Muestra gráfica optimizada (máximo 5,000 puntos para evitar saturar el navegador)
        if len(df_export) > 5000:
            st.caption("ℹ️ Mostrando vista previa reducida para mantener la fluidez del navegador.")
            st.line_chart(df_export.iloc[::len(df_export)//5000].set_index("Muestra"))
        else:
            st.line_chart(df_export.set_index("Muestra"))
            
    with col_export:
        st.write(f"**Tag:** `{info_sel['Tag']}`")
        st.write(f"**Unidad:** `{info_sel['Unidad']}`")
        st.write(f"**Muestras totales:** `{len(info_sel['Datos'])}`")
        
        # Exportación ultrarrápida a TXT
        txt_bytes = df_export.to_csv(index=False, sep='\t').encode('utf-8')
        st.download_button(
            label="💾 Descargar TXT Limpio",
            data=txt_bytes,
            file_name=f"{info_sel['Tag']}_extraido.txt",
            mime="text/plain"
        )
else:
    st.info("👈 Por favor, sube los archivos .dat y .~at en el panel lateral para iniciar el procesamiento.")