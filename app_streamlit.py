import os
import base64
from io import BytesIO
from datetime import datetime
import uuid
import re

import pandas as pd
import requests
import streamlit as st
import streamlit.components.v1 as components

from agentes import ejecutar_equipo_riesgo
from ratios import calcular_ratios

ruta_base = os.path.dirname(__file__)
ruta_datos = os.path.join(ruta_base, "datos")

API_URL = os.getenv("API_URL", "http://localhost:8000")

df_pd_validacion = pd.read_csv(os.path.join(ruta_datos, "pd_validacion.csv"))
df_estados_validacion = pd.read_csv(
    os.path.join(ruta_datos, "estados_financieros_validacion.csv")
)

ids_empresas_validacion = sorted(df_pd_validacion["id_empresa"].unique())


def analizar_estados_financieros(id_empresa: int) -> dict:
    df = df_estados_validacion[
        df_estados_validacion["id_empresa"] == id_empresa
    ]
    if df.empty:
        raise ValueError(f"id_empresa {id_empresa} no encontrado en estados financieros.")
    return calcular_ratios(df)


def generar_informe_pdf(
    id_empresa: int,
    resultado_pd: dict,
    analisis_financiero: dict,
    resumen_ejecutivo: str | None = None,
) -> bytes:
    """Genera un PDF usando la plantilla HTML con WeasyPrint"""

    # Cargar la plantilla HTML
    ruta_plantilla = os.path.join(ruta_base, "plantillas", "plantilla_informe.html")
    with open(ruta_plantilla, "r", encoding="utf-8") as f:
        plantilla_html = f.read()

    # Preparar los datos para rellenar la plantilla
    datos = preparar_datos_para_plantilla(
        id_empresa, resultado_pd, analisis_financiero, resumen_ejecutivo
    )

    # Rellenar la plantilla
    html_final = plantilla_html
    for clave, valor in datos.items():
        html_final = html_final.replace(f"{{{{{clave}}}}}", str(valor))

    # Generar PDF desde HTML (importación diferida para tolerar faltantes nativos en Windows)
    from weasyprint import HTML

    pdf_bytes = HTML(string=html_final).write_pdf()
    return pdf_bytes


def generar_informe_html(
    id_empresa: int,
    resultado_pd: dict,
    analisis_financiero: dict,
    resumen_ejecutivo: str | None = None,
) -> str:
    """Genera un informe HTML usando la plantilla"""

    ruta_plantilla = os.path.join(ruta_base, "plantillas", "plantilla_informe.html")
    with open(ruta_plantilla, "r", encoding="utf-8") as f:
        plantilla_html = f.read()

    datos = preparar_datos_para_plantilla(
        id_empresa, resultado_pd, analisis_financiero, resumen_ejecutivo
    )

    html_final = plantilla_html
    for clave, valor in datos.items():
        html_final = html_final.replace(f"{{{{{clave}}}}}", str(valor))

    return html_final


def preparar_datos_para_plantilla(
    id_empresa: int,
    resultado_pd: dict,
    analisis_financiero: dict,
    resumen_ejecutivo: str | None = None,
) -> dict:
    """Prepara el diccionario de datos para rellenar la plantilla HTML"""

    r = analisis_financiero["ratios"]
    pd_12m = resultado_pd["pd_12m"]
    banda_score = resultado_pd["banda_score"]

    # Determinar clases CSS según el riesgo (basado en banda de score y PD)
    if banda_score in ["CCC", "C"] or pd_12m > 0.07:
        risk_bg_class = "bg-danger-light"
        risk_text_class = "text-danger"
    elif banda_score in ["B", "BB"] or pd_12m > 0.03:
        risk_bg_class = "bg-warning-light"
        risk_text_class = "text-warning"
    else:
        risk_bg_class = "bg-success-light"
        risk_text_class = "text-success"

    # Calcular posición en el medidor de riesgo (0-100%)
    # PD de 0% = posición 0, PD de 20%+ = posición 100
    risk_meter_percentage = min(pd_12m * 500, 100)  # Escalar para que 20% PD = 100%

    # Evaluar ratios individuales
    # Liquidez
    ratio_liquidez = r["ratio_liquidez"]
    if ratio_liquidez >= 2.0:
        liquidity_badge = "badge-green"
        liquidity_text = "Excelente"
    elif ratio_liquidez >= 1.2:
        liquidity_badge = "badge-green"
        liquidity_text = "Bueno"
    elif ratio_liquidez >= 0.8:
        liquidity_badge = "badge-amber"
        liquidity_text = "Atención"
    else:
        liquidity_badge = "badge-red"
        liquidity_text = "Crítico"

    # Apalancamiento
    ratio_apal = r["ratio_apalancamiento"]
    if ratio_apal <= 1.5:
        leverage_badge = "badge-green"
        leverage_text = "Moderado"
    elif ratio_apal <= 3.0:
        leverage_badge = "badge-amber"
        leverage_text = "Alto"
    else:
        leverage_badge = "badge-red"
        leverage_text = "Excesivo"

    # Margen EBITDA
    margen_ebitda = r["margen_ebitda"]
    if margen_ebitda >= 0.15:
        ebitda_badge = "badge-green"
        ebitda_text = "Saludable"
    elif margen_ebitda >= 0.08:
        ebitda_badge = "badge-amber"
        ebitda_text = "Moderado"
    else:
        ebitda_badge = "badge-red"
        ebitda_text = "Débil"

    # Cobertura de intereses
    cobertura = r["cobertura_intereses"]
    if cobertura >= 3.0:
        coverage_badge = "badge-green"
        coverage_text = "Fuerte"
    elif cobertura >= 1.5:
        coverage_badge = "badge-amber"
        coverage_text = "Ajustado"
    else:
        coverage_badge = "badge-red"
        coverage_text = "Débil"

    # Crecimiento
    crecimiento = r.get("crecimiento_ingresos_ultimo", 0)
    if crecimiento is None:
        crecimiento = 0

    if crecimiento > 0.05:
        growth_color = "#388e3c"  # Verde
    elif crecimiento > -0.05:
        growth_color = "#f57f17"  # Amarillo oscuro
    else:
        growth_color = "#d32f2f"  # Rojo

    # Tendencia operativa
    tendencia = analisis_financiero.get("tendencia_margen", "Estable")
    if "mejor" in tendencia.lower() or "crec" in tendencia.lower():
        operational_trend = "Mejorando"
    elif "peor" in tendencia.lower() or "decr" in tendencia.lower():
        operational_trend = "Empeorando"
    else:
        operational_trend = "Estable"

    # Generar listas HTML de fortalezas y debilidades
    strengths_html = ""
    if analisis_financiero.get("fortalezas"):
        for fortaleza in analisis_financiero["fortalezas"]:
            strengths_html += f"<li class='li-good'>{fortaleza}</li>"
    else:
        strengths_html = (
            "<li class='li-good'>No se identificaron fortalezas significativas.</li>"
        )

    weaknesses_html = ""
    if analisis_financiero.get("debilidades"):
        for debilidad in analisis_financiero["debilidades"]:
            # Determinar si es crítico o solo atención
            if any(
                word in debilidad.lower()
                for word in ["alto", "crítico", "grave", "excesivo", "débil"]
            ):
                weaknesses_html += f"<li class='li-bad'>{debilidad}</li>"
            else:
                weaknesses_html += f"<li class='li-warn'>{debilidad}</li>"
    else:
        weaknesses_html = (
            "<li class='li-good'>No se detectaron debilidades relevantes.</li>"
        )

    # Resumen ejecutivo (convertir markdown básico a HTML si existe)
    if resumen_ejecutivo:
        executive_summary_html = markdown_basico_a_html(resumen_ejecutivo)
    else:
        executive_summary_html = "<p>La empresa presenta características financieras que requieren análisis detallado por parte del equipo de riesgos.</p>"

    # Nota para el analista
    analyst_note = (
        "Este informe combina la PD estimada por el modelo cuantitativo con un análisis de ratios financieros. "
        "El analista debe revisar la coherencia con información cualitativa (sector, equipo gestor, garantías) "
        "y decidir sobre la aprobación, límites o información adicional necesaria."
    )

    # Construir diccionario de datos
    datos = {
        "company_name": f"Empresa ID {id_empresa}",
        "company_id": str(id_empresa),
        "report_date": datetime.now().strftime("%d/%m/%Y"),
        "executive_summary_html": executive_summary_html,
        "risk_score": banda_score,
        "risk_bg_class": risk_bg_class,
        "risk_text_class": risk_text_class,
        "pd_value": f"{pd_12m * 100:.2f}",
        "risk_meter_percentage": f"{risk_meter_percentage:.1f}",
        "ratio_liquidity_value": f"{ratio_liquidez:.2f}x",
        "ratio_liquidity_badge_class": liquidity_badge,
        "ratio_liquidity_text": liquidity_text,
        "ratio_leverage_value": f"{ratio_apal:.2f}x",
        "ratio_leverage_badge_class": leverage_badge,
        "ratio_leverage_text": leverage_text,
        "ratio_ebitda_value": f"{margen_ebitda * 100:.1f}%",
        "ratio_ebitda_badge_class": ebitda_badge,
        "ratio_ebitda_text": ebitda_text,
        "ratio_coverage_value": f"{cobertura:.2f}x",
        "ratio_coverage_badge_class": coverage_badge,
        "ratio_coverage_text": coverage_text,
        "growth_value": f"{crecimiento * 100:+.2f}",
        "growth_color": growth_color,
        "operational_trend_text": operational_trend,
        "strengths_list_html": strengths_html,
        "weaknesses_list_html": weaknesses_html,
        "analyst_note": analyst_note,
        "transaction_id": str(uuid.uuid4())[:8].upper(),
    }

    return datos


def markdown_basico_a_html(texto: str) -> str:
    """Convierte markdown básico a HTML"""
    # Reemplazar negritas
    html = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", texto)
    # Reemplazar títulos ###
    html = re.sub(r"###\s*(.+?)\n", r"<h3>\1</h3>", html)
    # Reemplazar párrafos
    html = html.replace("\n\n", "</p><p>")
    # Envolver en párrafo inicial
    if not html.startswith("<"):
        html = f"<p>{html}</p>"
    return html


def mostrar_pdf_en_streamlit(pdf_bytes: bytes):
    b64 = base64.b64encode(pdf_bytes).decode("utf-8")
    iframe = f'<iframe src="data:application/pdf;base64,{b64}" width="100%" height="600" type="application/pdf"></iframe>'
    st.markdown(iframe, unsafe_allow_html=True)


def markdown_a_html(texto_markdown: str) -> str:
    """Convierte markdown básico a HTML para mostrar en cajas con scroll"""
    # Reemplazar saltos de línea
    html = texto_markdown.replace("\n\n", "<br><br>").replace("\n", "<br>")
    # Reemplazar negritas
    import re

    html = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", html)
    # Reemplazar títulos ###
    html = re.sub(r"###\s*(.+?)<br>", r"<h3>\1</h3>", html)
    # Reemplazar líneas horizontales
    html = html.replace("---<br>", "<hr>")
    html = html.replace("---", "<hr>")
    return html


# Estilos inline para las cajas (garantiza que se apliquen)
ESTILO_CAJA = "border: 3px solid #FF6B35; border-radius: 10px; padding: 20px; background-color: #FFFBF5; margin-bottom: 20px; height: 400px; max-height: 400px; overflow-y: auto; overflow-x: hidden;"
ESTILO_CAJA_PDF = "border: 3px solid #FF6B35; border-radius: 10px; padding: 20px; background-color: #FFFBF5; height: 850px; max-height: 850px; overflow-y: auto; overflow-x: hidden;"
ESTILO_TITULO = "color: #FF6B35; font-size: 18px; font-weight: bold; margin-top: 0; margin-bottom: 15px;"


st.set_page_config(page_title="Demo Riesgo PYMEs con agentes IA", layout="wide")

st.title("Demo de evaluación de riesgo para PYMEs con agentes de IA")

# CSS personalizado para las cajas con bordes naranjas y scroll vertical
st.markdown(
    """
<style>
    /* Cajas con scroll - usando !important para sobrescribir Streamlit */
    div[data-testid="stMarkdownContainer"] .caja-contenido,
    .caja-contenido {
        border: 3px solid #FF6B35 !important;
        border-radius: 10px !important;
        padding: 20px !important;
        background-color: #FFFBF5 !important;
        margin-bottom: 20px !important;
        height: 400px !important;
        max-height: 400px !important;
        overflow-y: auto !important;
        overflow-x: hidden !important;
        display: block !important;
    }
    
    div[data-testid="stMarkdownContainer"] .caja-pdf,
    .caja-pdf {
        border: 3px solid #FF6B35 !important;
        border-radius: 10px !important;
        padding: 20px !important;
        background-color: #FFFBF5 !important;
        height: 850px !important;
        max-height: 850px !important;
        overflow-y: auto !important;
        overflow-x: hidden !important;
        display: block !important;
    }
    
    /* Scroll bar personalizado */
    .caja-contenido::-webkit-scrollbar, .caja-pdf::-webkit-scrollbar {
        width: 10px;
    }
    
    .caja-contenido::-webkit-scrollbar-track, .caja-pdf::-webkit-scrollbar-track {
        background: #f1f1f1;
        border-radius: 10px;
    }
    
    .caja-contenido::-webkit-scrollbar-thumb, .caja-pdf::-webkit-scrollbar-thumb {
        background: #FF6B35;
        border-radius: 10px;
    }
    
    .caja-contenido::-webkit-scrollbar-thumb:hover, .caja-pdf::-webkit-scrollbar-thumb:hover {
        background: #E85A2A;
    }
    
    /* Títulos de las cajas */
    .titulo-caja {
        color: #FF6B35;
        font-size: 18px;
        font-weight: bold;
        margin-top: 0;
        margin-bottom: 15px;
    }
    
    /* Contenido interno de las cajas */
    .caja-contenido * , .caja-pdf * {
        max-width: 100%;
        word-wrap: break-word;
    }
</style>
""",
    unsafe_allow_html=True,
)

# Sección de selección
st.subheader("Selección de empresa")
id_seleccionada = st.selectbox(
    "Empresa (id_empresa en validación):", ids_empresas_validacion
)

if st.button("Lanzar evaluación de riesgo", type="primary"):
    # Fila superior: Orquestador y PDF
    col_top1, col_top2 = st.columns([1, 1])

    with col_top1:
        contenedor_orquestador = st.empty()

    with col_top2:
        contenedor_pdf = st.empty()

    # Fila inferior: Data Scientist y Analista
    col_bottom1, col_bottom2 = st.columns([1, 1])

    with col_bottom1:
        contenedor_data_scientist = st.empty()

    with col_bottom2:
        contenedor_analista = st.empty()

    # Inicializar variables para ir acumulando el texto
    import time

    # PASO 1: Agente Data Scientist trabaja con el modelo
    contenedor_data_scientist.markdown(
        f"""
<div style="{ESTILO_CAJA}">
<p style="{ESTILO_TITULO}">🤖 Agente Data Scientist (Modelo PD)</p>
<hr>
<h3>🔍 Iniciando análisis...</h3>
<p>Conectándome a la API del modelo de probabilidad de default...</p>
</div>
    """,
        unsafe_allow_html=True,
    )
    time.sleep(0.5)

    contenedor_orquestador.markdown(
        f"""
<div style="{ESTILO_CAJA}">
<p style="{ESTILO_TITULO}">🎯 Orquestador de Evaluación</p>
<hr>
<p><strong>Paso 1/4:</strong> Solicitando análisis del modelo de PD al agente especialista...</p>
</div>
    """,
        unsafe_allow_html=True,
    )

    try:
        resp = requests.post(
            f"{API_URL}/calcular_pd", json={"id_empresa": int(id_seleccionada)}
        )
        resp.raise_for_status()
        resultado_pd = resp.json()

        # El agente data scientist va explicando sus hallazgos
        texto_data_scientist = f"""
**🤖 Agente Data Scientist (Modelo PD)**

---

### ✅ Modelo de PD ejecutado

**Empresa ID:** {id_seleccionada}

🎯 **Resultado principal:**
- **Probabilidad de Default (12 meses):** {resultado_pd['pd_12m']:.4f} ({resultado_pd['pd_12m']*100:.2f}%)
- **Banda de Score:** {resultado_pd['banda_score']}

📊 **Mi interpretación como Data Scientist:**

"""
        # Interpretación según la PD
        if resultado_pd["pd_12m"] < 0.02:
            texto_data_scientist += """
✅ Esta empresa muestra una **muy baja probabilidad de default**. El modelo la clasifica en la zona más segura.

**Factores clave que identifiqué:**
- Los ratios financieros alimentados al modelo son sólidos
- La combinación de variables sugiere una situación financiera estable
- El score está en banda AAA o AA, indicando riesgo mínimo
"""
        elif resultado_pd["pd_12m"] < 0.05:
            texto_data_scientist += """
✅ La empresa tiene una **baja probabilidad de default**. Es un perfil de riesgo aceptable.

**Factores clave que identifiqué:**
- Los indicadores financieros son generalmente positivos
- Algunas variables pueden mostrar áreas de atención menor
- Score en banda A o BBB, considerado investment grade
"""
        elif resultado_pd["pd_12m"] < 0.10:
            texto_data_scientist += """
⚠️ La empresa presenta una **probabilidad moderada de default**. Requiere análisis adicional.

**Factores clave que identifiqué:**
- Algunos ratios financieros muestran debilidades
- Combinación de señales mixtas en el modelo
- Score en banda BB o B, zona especulativa
"""
            texto_data_scientist += """
🚨 La empresa tiene una **alta probabilidad de default**. Riesgo crediticio significativo.

**Factores clave que identifiqué:**
- Múltiples indicadores financieros están en zona de riesgo
- Las variables del modelo señalan vulnerabilidad financiera
- Score en banda C o inferior, alto riesgo
"""
        else:
            texto_data_scientist += """
🚨 La empresa tiene una **alta probabilidad de default**. Riesgo crediticio significativo.

**Factores clave que identifiqué:**
- Múltiples indicadores financieros están en zona de riesgo
- Las variables del modelo señalan vulnerabilidad financiera
- Score en banda C o inferior, alto riesgo
"""

        texto_data_scientist += f"""

📈 **Detalles técnicos:**
- Modelo: Regresión Logística calibrada
- Features analizadas: 18 variables financieras
- Banda de score: {resultado_pd['banda_score']}

🔄 **Mi recomendación:** Proceder con el análisis de ratios financieros para validar y profundizar estos hallazgos.
"""

        # Convertir a HTML y mostrar en la caja
        html_content = markdown_a_html(texto_data_scientist)
        contenedor_data_scientist.markdown(
            f"""
<div style="{ESTILO_CAJA}">
<p style="{ESTILO_TITULO}">🤖 Agente Data Scientist (Modelo PD)</p>
<hr>
{html_content}
</div>
            """,
            unsafe_allow_html=True,
        )

    except Exception as e:
        st.error(f"❌ Error en el agente Data Scientist: {e}")
        st.stop()

    time.sleep(0.3)

    # PASO 2: Agente Analista Financiero trabaja con los ratios
    contenedor_orquestador.markdown(
        f"""
<div style="{ESTILO_CAJA}">
<p style="{ESTILO_TITULO}">🎯 Orquestador de Evaluación</p>
<hr>
<p><strong>Paso 2/4:</strong> El modelo ha completado su análisis. Ahora el analista financiero revisa los estados financieros...</p>
</div>
    """,
        unsafe_allow_html=True,
    )

    contenedor_analista.markdown(
        f"""
<div style="{ESTILO_CAJA}">
<p style="{ESTILO_TITULO}">📊 Agente Analista Financiero</p>
<hr>
<h3>🔍 Analizando estados financieros...</h3>
<p>Cargando datos históricos de la empresa...<br>
Calculando ratios clave...</p>
</div>
    """,
        unsafe_allow_html=True,
    )
    time.sleep(0.5)

    try:
        analisis_financiero = analizar_estados_financieros(int(id_seleccionada))
        r = analisis_financiero["ratios"]

        # El analista va explicando sus hallazgos
        texto_analista = f"""
**📊 Agente Analista Financiero**

---

### 📊 Análisis Financiero Completado

**Empresa ID:** {id_seleccionada}  
**Años analizados:** {', '.join(map(str, analisis_financiero['anos_disponibles']))}

---

### 🔢 Ratios Clave (Último año)

**Liquidez:**
- Current Ratio: **{r['ratio_liquidez']:.2f}**
"""
        if r["ratio_liquidez"] >= 1.5:
            texto_analista += "  ✅ Excelente capacidad de pago a corto plazo\n"
        elif r["ratio_liquidez"] >= 1.2:
            texto_analista += "  ✅ Buena liquidez\n"
        else:
            texto_analista += "  ⚠️ Liquidez ajustada, requiere monitoreo\n"

        texto_analista += f"""
**Solvencia:**
- Apalancamiento (Pasivos/Patrimonio): **{r['ratio_apalancamiento']:.2f}**
"""
        if r["ratio_apalancamiento"] <= 2:
            texto_analista += "  ✅ Nivel de endeudamiento conservador\n"
        elif r["ratio_apalancamiento"] <= 3:
            texto_analista += "  ✅ Apalancamiento razonable\n"
        else:
            texto_analista += "  ⚠️ Endeudamiento elevado, puede limitar flexibilidad\n"

        texto_analista += f"""
**Rentabilidad:**
- Margen EBITDA: **{r['margen_ebitda']:.2%}**
- Tendencia: **{analisis_financiero['tendencia_margen']}**
"""
        if r["margen_ebitda"] >= 0.15:
            texto_analista += "  ✅ Excelente rentabilidad operativa\n"
        elif r["margen_ebitda"] >= 0.10:
            texto_analista += "  ✅ Margen saludable\n"
        else:
            texto_analista += "  ⚠️ Margen reducido, presión en rentabilidad\n"

        texto_analista += f"""
**Cobertura de Deuda:**
- Cobertura EBITDA/Intereses: **{r['cobertura_intereses']:.2f}x**
"""
        if r["cobertura_intereses"] >= 5:
            texto_analista += "  ✅ Excelente capacidad de servicio de deuda\n"
        elif r["cobertura_intereses"] >= 3:
            texto_analista += "  ✅ Buena cobertura\n"
        else:
            texto_analista += (
                "  ⚠️ Cobertura limitada, vulnerabilidad ante fluctuaciones\n"
            )

        if r["crecimiento_ingresos_ultimo"] is not None:
            texto_analista += f"""
**Crecimiento:**
- Ingresos (var. interanual): **{r['crecimiento_ingresos_ultimo']:.2%}**
"""
            if r["crecimiento_ingresos_ultimo"] > 0.10:
                texto_analista += "  ✅ Fuerte crecimiento\n"
            elif r["crecimiento_ingresos_ultimo"] > 0:
                texto_analista += "  ✅ Ingresos en expansión\n"
            else:
                texto_analista += "  ⚠️ Contracción de ingresos\n"

        texto_analista += """

---

### 💪 Fortalezas Identificadas:
"""
        if analisis_financiero["fortalezas"]:
            for f in analisis_financiero["fortalezas"]:
                texto_analista += f"\n✅ {f}"
        else:
            texto_analista += "\n- Sin fortalezas especialmente destacadas"

        texto_analista += """

### ⚠️ Debilidades y Puntos de Atención:
"""
        if analisis_financiero["debilidades"]:
            for d in analisis_financiero["debilidades"]:
                texto_analista += f"\n⚠️ {d}"
        else:
            texto_analista += "\n- No se detectan debilidades significativas"

        texto_analista += """

---

### 📝 Mi Conclusión como Analista:

"""
        # Conclusión según el análisis
        num_fortalezas = len(analisis_financiero["fortalezas"])
        num_debilidades = len(analisis_financiero["debilidades"])

        if num_fortalezas > num_debilidades + 1:
            texto_analista += "La empresa muestra una posición financiera **sólida** con múltiples fortalezas. Los ratios sugieren capacidad de hacer frente a sus obligaciones."
        elif num_fortalezas > num_debilidades:
            texto_analista += "La situación financiera es **favorable**, aunque existen algunos puntos que requieren monitoreo."
        elif num_fortalezas == num_debilidades:
            texto_analista += "Situación **mixta** con fortalezas y debilidades equilibradas. Se requiere análisis cualitativo adicional."
        else:
            texto_analista += "La empresa presenta **varios puntos de atención** que sugieren vulnerabilidad financiera. Recomiendo cautela."

        # Convertir a HTML y mostrar en la caja
        html_content = markdown_a_html(texto_analista)
        contenedor_analista.markdown(
            f"""
<div style="{ESTILO_CAJA}">
<p style="{ESTILO_TITULO}">📊 Agente Analista Financiero</p>
<hr>
{html_content}
</div>
            """,
            unsafe_allow_html=True,
        )

    except Exception as e:
        st.error(f"❌ Error en el agente Analista Financiero: {e}")
        st.stop()

    time.sleep(0.3)

    # PASO 3: Orquestador sintetiza y llama a CrewAI
    contenedor_orquestador.markdown(
        f"""
<div style="{ESTILO_CAJA}">
<p style="{ESTILO_TITULO}">🎯 Orquestador de Evaluación</p>
<hr>
<p><strong>Paso 3/4:</strong> Ambos agentes han completado su trabajo. Sintetizando información y generando resumen ejecutivo con IA...</p>
<p>⏳ Esto puede tardar unos segundos mientras los agentes de CrewAI procesan la información...</p>
</div>
    """,
        unsafe_allow_html=True,
    )

    try:
        openai_api_key = os.getenv("OPENAI_API_KEY", "").strip()
        if not openai_api_key.startswith("sk-"):
            raise ValueError(
                "OPENAI_API_KEY no configurada correctamente. Debe iniciar con 'sk-'."
            )

        resumen_ejecutivo = ejecutar_equipo_riesgo(int(id_seleccionada))

        html_resumen = markdown_a_html(
            f"""
**Paso 3/4:** ✅ Resumen ejecutivo generado

---

### 📋 Resumen Ejecutivo de IA:

{resumen_ejecutivo}
"""
        )
        contenedor_orquestador.markdown(
            f"""
<div style="{ESTILO_CAJA}">
<p style="{ESTILO_TITULO}">🎯 Orquestador de Evaluación</p>
<hr>
{html_resumen}
</div>
            """,
            unsafe_allow_html=True,
        )
    except Exception as e:
        contenedor_orquestador.markdown(
            f"""
<div style="{ESTILO_CAJA}">
<p style="{ESTILO_TITULO}">🎯 Orquestador de Evaluación</p>
<hr>
<p><strong>Paso 3/4:</strong> ⚠️ No se pudo generar resumen con CrewAI</p>
<p>Error: {str(e)}</p>
<p>Continuando con generación de informe PDF...</p>
</div>
            """,
            unsafe_allow_html=True,
        )
        resumen_ejecutivo = "No disponible - configurar OPENAI_API_KEY en .env"

    time.sleep(0.3)

    # PASO 4: Generar PDF
    contenedor_orquestador.markdown(
        f"""
<div style="{ESTILO_CAJA}">
<p style="{ESTILO_TITULO}">🎯 Orquestador de Evaluación</p>
<hr>
<p><strong>Paso 4/4:</strong> Generando informe PDF completo...</p>
</div>
    """,
        unsafe_allow_html=True,
    )

    pdf_bytes = None
    html_fallback = None
    error_pdf = None

    try:
        pdf_bytes = generar_informe_pdf(
            int(id_seleccionada), resultado_pd, analisis_financiero, resumen_ejecutivo
        )
    except Exception as e:
        error_pdf = str(e)
        html_fallback = generar_informe_html(
            int(id_seleccionada), resultado_pd, analisis_financiero, resumen_ejecutivo
        )

    estado_paso_4 = "✅ Informe PDF generado"
    if error_pdf:
        estado_paso_4 = (
            "⚠️ No fue posible generar PDF en este entorno. Se habilitó informe HTML."
        )

    contenedor_orquestador.markdown(
        f"""
<div style="{ESTILO_CAJA}">
<p style="{ESTILO_TITULO}">🎯 Orquestador de Evaluación</p>
<hr>
<p><strong>Paso 4/4:</strong> {estado_paso_4}</p>
<hr>
<h3>✅ Evaluación Completa</h3>
<p>Todos los agentes han finalizado su trabajo. El informe ejecutivo está listo para revisión.</p>
</div>
    """,
        unsafe_allow_html=True,
    )

    # Mostrar PDF o fallback HTML
    if pdf_bytes is not None:
        contenedor_pdf.markdown(
            f"""
<div style="{ESTILO_CAJA_PDF}">
<p style="{ESTILO_TITULO}">📄 Informe Ejecutivo PDF</p>
<hr>
<div style="text-align: center; margin-bottom: 15px;">
    <a href="data:application/pdf;base64,{base64.b64encode(pdf_bytes).decode('utf-8')}" 
       download="informe_riesgo_empresa_{id_seleccionada}.pdf"
       style="background-color: #FF6B35; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; display: inline-block;">
       📥 Descargar Informe PDF
    </a>
</div>
<hr>
<iframe src="data:application/pdf;base64,{base64.b64encode(pdf_bytes).decode('utf-8')}" 
        width="100%" height="700" type="application/pdf" style="border: none;"></iframe>
</div>
        """,
            unsafe_allow_html=True,
        )
    else:
        contenedor_pdf.markdown(
            f"""
<div style="{ESTILO_CAJA_PDF}">
<p style="{ESTILO_TITULO}">📄 Informe Ejecutivo (HTML)</p>
<hr>
<p>No fue posible generar el PDF por dependencias nativas de WeasyPrint en Windows.</p>
<p style="font-size: 12px; color: #666;">Detalle técnico: {error_pdf}</p>
</div>
        """,
            unsafe_allow_html=True,
        )
        components.html(html_fallback, height=700, scrolling=True)
        st.download_button(
            label="📥 Descargar Informe HTML",
            data=html_fallback.encode("utf-8"),
            file_name=f"informe_riesgo_empresa_{id_seleccionada}.html",
            mime="text/html",
        )

else:
    st.info(
        "👆 Selecciona una empresa y pulsa 'Lanzar evaluación de riesgo' para iniciar el análisis."
    )
