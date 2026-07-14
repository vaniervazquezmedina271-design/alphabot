@echo off
REM ============================================================
REM  AlphaBot - Bot local (tiempo real)
REM  Arranca el bot que revisa Telegram y busca noticias.
REM  Se lanza solo al iniciar Windows (acceso directo en Inicio).
REM  Para detenerlo: cierra esta ventana o pulsa Ctrl+C.
REM ============================================================
title AlphaBot - Bot Local
cd /d "C:\VANIER\AGENTE DE BUSQUEDA"
"venv\Scripts\python.exe" bot_local.py
REM Si el bot se cierra por un error, deja la ventana abierta para ver el motivo
echo.
echo El bot se detuvo. Pulsa una tecla para cerrar.
pause >nul
