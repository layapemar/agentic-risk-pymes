import os
import requests
import pandas as pd
from dotenv import load_dotenv

from crewai import Agent, Task, Crew, Process
from crewai.tools import tool
from ratios import calcular_ratios

load_dotenv()

_base = os.getenv("API_URL", "http://localhost:8000")
API_URL = f"{_base}/calcular_pd"

ruta_base = os.path.dirname(__file__)
ruta_datos = os.path.join(ruta_base, "datos")
estados_financieros_validacion = pd.read_csv(
    os.path.join(ruta_datos, "estados_financieros_validacion.csv")
)


@tool("Modelo de PD para empresa")
def herramienta_modelo_pd(id_empresa: str) -> str:
    """
    Llama a la API del modelo de PD para una empresa concreta
    y devuelve un resumen en texto.
    """
    ident = int(id_empresa)
    respuesta = requests.post(API_URL, json={"id_empresa": ident})
    respuesta.raise_for_status()
    datos = respuesta.json()
    texto = (
        f"Resultado del modelo de PD para id_empresa={ident}: "
        f"PD_12m={datos['pd_12m']:.4f} (~{datos['pd_12m']*100:.2f}%), "
        f"banda de score={datos['banda_score']}."
    )
    return texto


@tool("Análisis financiero de empresa")
def herramienta_analisis_financiero(id_empresa: str) -> str:
    """
    Analiza los estados financieros de la empresa indicada
    y devuelve un resumen con ratios, fortalezas y debilidades.
    """
    ident = int(id_empresa)
    df = estados_financieros_validacion[
        estados_financieros_validacion["id_empresa"] == ident
    ]
    if df.empty:
        return f"No se encontraron estados financieros para id_empresa={ident}."

    resultado = calcular_ratios(df)
    r = resultado["ratios"]

    lineas = [
        f"Análisis financiero para id_empresa={ident}:",
        f"- Current ratio (liquidez) = {r['ratio_liquidez']:.2f}",
        f"- Apalancamiento (pasivos/patrimonio) = {r['ratio_apalancamiento']:.2f}",
        f"- Margen EBITDA = {r['margen_ebitda']:.2%}",
        f"- Cobertura EBITDA/intereses = {r['cobertura_intereses']:.2f}x",
    ]
    if r["crecimiento_ingresos_ultimo"] is not None:
        lineas.append(f"- Crecimiento de ingresos último año = {r['crecimiento_ingresos_ultimo']:.2%}")

    if resultado["fortalezas"]:
        lineas.append("Fortalezas:")
        lineas.extend(f"  * {f}" for f in resultado["fortalezas"])
    if resultado["debilidades"]:
        lineas.append("Puntos de atención:")
        lineas.extend(f"  * {d}" for d in resultado["debilidades"])

    return "\n".join(lineas)


def construir_equipo():
    agente_modelo_pd = Agent(
        role="Agente de modelo de PD",
        goal="Obtener la probabilidad de default y explicarla de forma clara.",
        backstory=(
            "Eres un especialista en modelos de riesgo que interpreta correctamente las salidas "
            "del modelo de probabilidad de default para pymes."
        ),
        tools=[herramienta_modelo_pd],
        verbose=True,
    )

    agente_ratios = Agent(
        role="Analista de ratios financieros",
        goal="Analizar los estados financieros y extraer las principales conclusiones de riesgo.",
        backstory=(
            "Eres un analista de riesgos que se enfoca en ratios financieros: liquidez, "
            "apalancamiento, rentabilidad y cobertura de intereses."
        ),
        tools=[herramienta_analisis_financiero],
        verbose=True,
    )

    agente_orquestador = Agent(
        role="Orquestador de evaluación de riesgo",
        goal=(
            "Combinar el resultado del modelo de PD con el análisis financiero para elaborar "
            "un resumen ejecutivo coherente y útil para un analista humano."
        ),
        backstory=(
            "Eres un responsable senior de riesgos bancarios que sintetiza información cuantitativa "
            "y cualitativa para apoyar decisiones de crédito a pymes."
        ),
        verbose=True,
    )

    tarea_pd = Task(
        description=(
            "Utiliza la herramienta del modelo de PD para obtener la probabilidad de default y la "
            "banda de score de la empresa con id_empresa={id_empresa}."
        ),
        agent=agente_modelo_pd,
        expected_output=(
            "Un párrafo que explique la PD a 12 meses y qué implica la banda de score para el riesgo de crédito."
        ),
    )

    tarea_fin = Task(
        description=(
            "Utiliza la herramienta de análisis financiero para revisar los estados financieros de la empresa "
            "con id_empresa={id_empresa} y resumir sus fortalezas y debilidades."
        ),
        agent=agente_ratios,
        expected_output=(
            "Un resumen claro de las principales fortalezas y debilidades financieras, citando los ratios clave."
        ),
    )

    tarea_orquestador = Task(
        description=(
            "Con la información del modelo de PD y del análisis financiero, redacta un resumen ejecutivo "
            "(2-3 párrafos) que explique:\n"
            "- El nivel de riesgo global de la pyme\n"
            "- Cómo se combinan las señales del modelo y de los ratios\n"
            "- Qué debería revisar el analista humano antes de decidir la concesión del crédito."
        ),
        agent=agente_orquestador,
        expected_output=(
            "Un texto conciso (2-3 párrafos) listo para incluir en un informe de riesgo."
        ),
    )

    equipo = Crew(
        agents=[agente_modelo_pd, agente_ratios, agente_orquestador],
        tasks=[tarea_pd, tarea_fin, tarea_orquestador],
        process=Process.sequential,
        verbose=True,
    )
    return equipo


def ejecutar_equipo_riesgo(id_empresa: int) -> str:
    """
    Lanza el equipo de agentes para una empresa concreta y devuelve
    el resumen ejecutivo generado por el orquestador.
    """
    equipo = construir_equipo()
    resultado = equipo.kickoff(inputs={"id_empresa": str(id_empresa)})
    resumen_ejecutivo = str(resultado)
    return resumen_ejecutivo
