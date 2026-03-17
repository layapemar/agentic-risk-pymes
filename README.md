# Agentic Data Science

Aplicación de evaluación de riesgo para PYMEs con:
- API en FastAPI para cálculo de probabilidad de default (PD)
- Interfaz en Streamlit
- Orquestación de análisis con agentes

## Requisitos
- Python 3.11
- Conda (recomendado)

## Configuración rápida
1. Crear entorno:
   - `conda create -n agentic-ds python=3.11 -y`
2. Instalar dependencias:
   - `conda run -n agentic-ds python -m pip install -r requirements.txt`
3. Configurar variables de entorno:
   - Copiar `.env.example` a `.env`
   - Completar `OPENAI_API_KEY`

## Ejecución
- Opción recomendada (Windows): ejecutar `lanzar_app.bat`
- Manual:
  - API: `conda run -n agentic-ds python api_pd.py`
  - App: `conda run -n agentic-ds streamlit run app_streamlit.py --server.port 8501`

## Estructura
- `api_pd.py`: servicio FastAPI del modelo PD
- `app_streamlit.py`: interfaz principal
- `agentes.py`: coordinación y lógica de agentes
- `datos/`: datasets de entrenamiento/validación
- `plantillas/`: plantilla HTML para informe

## Notas
- En Windows, la generación PDF con WeasyPrint puede requerir librerías nativas adicionales.
- La app tiene fallback a informe HTML cuando el PDF no puede generarse.
