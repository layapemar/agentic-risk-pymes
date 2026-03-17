@echo off
setlocal

cd /d "%~dp0"

set "ENV_NAME=agentic-ds"
set "API_PORT=8000"
set "APP_PORT=8501"

echo ================================================
echo  Agentic Data Science - Lanzador
echo ================================================
echo Entorno: %ENV_NAME%
echo Carpeta: %CD%
echo.

echo Verificando entorno conda...
conda run -n %ENV_NAME% python -V >nul 2>&1
if errorlevel 1 (
	echo [ERROR] No se encontro el entorno %ENV_NAME% o conda no esta disponible.
	echo Crea el entorno y dependencias antes de ejecutar este lanzador.
	pause
	exit /b 1
)

echo Iniciando API FastAPI en http://127.0.0.1:%API_PORT% ...
start "API FastAPI" cmd /k "cd /d %CD% && conda run -n %ENV_NAME% python api_pd.py"

echo Esperando arranque de API...
timeout /t 5 >nul

echo Iniciando Streamlit en http://localhost:%APP_PORT% ...
start "App Streamlit" cmd /k "cd /d %CD% && conda run -n %ENV_NAME% streamlit run app_streamlit.py --server.port %APP_PORT%"

echo.
echo Listo. Se abrieron dos ventanas:
echo  - API FastAPI
echo  - App Streamlit
echo.
echo Para detener cada servicio, cierra su ventana correspondiente.
endlocal