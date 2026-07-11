@echo off
REM ============================================================
REM  Instala las tareas programadas del Agente Financiero
REM  - Reporte diario a las 8:00 AM
REM  - Alertas en tiempo real cada 30 minutos
REM
REM  Ejecutar como Administrador (click derecho > Ejecutar como admin)
REM ============================================================

set PROJECT_DIR=C:\VANIER\AGENTE DE BUSQUEDA
set PYTHON=%PROJECT_DIR%\venv\Scripts\python.exe

echo ============================================================
echo  Instalando tareas programadas del Agente Financiero
echo ============================================================
echo  Carpeta: %PROJECT_DIR%
echo  Python:  %PYTHON%
echo.

REM --- Tarea 1: Reporte diario a las 8:00 AM ---
echo [1/2] Creando tarea: Reporte diario 8AM...
schtasks /create /tn "MarketDaily_Reporte_8AM" ^
    /tr "\"%PYTHON%\" \"%PROJECT_DIR%\run_report.py\" --daily" ^
    /sc daily /st 08:00 ^
    /rl HIGHEST /f
if %errorlevel% equ 0 (
    echo     OK - Reporte diario a las 8:00 AM
) else (
    echo     ERROR - No se pudo crear la tarea. Ejecuta como admin.
)
echo.

REM --- Tarea 2: Alertas cada 30 minutos (9:00 AM - 5:00 PM, horas de mercado) ---
echo [2/2] Creando tarea: Alertas cada 30 min...
schtasks /create /tn "MarketDaily_Alertas_30min" ^
    /tr "\"%PYTHON%\" \"%PROJECT_DIR%\run_report.py\" --breaking --no-reasoning" ^
    /sc daily /st 09:00 /et 17:00 /ri 30 ^
    /rl HIGHEST /f
if %errorlevel% equ 0 (
    echo     OK - Alertas cada 30 min (9AM-5PM)
) else (
    echo     ERROR - No se pudo crear la tarea. Ejecuta como admin.
)
echo.

echo ============================================================
echo  Listo! Las tareas estan instaladas.
echo.
echo  - Reporte diario:   8:00 AM cada dia
echo  - Alertas tiempo real: cada 30 min (9AM-5PM)
echo.
echo  Para verlas: abre "Programador de tareas" y busca "MarketDaily"
echo  Para eliminarlas: schtasks /delete /tn "MarketDaily_Reporte_8AM" /f
echo                     schtasks /delete /tn "MarketDaily_Alertas_30min" /f
echo ============================================================
pause
