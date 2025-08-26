@echo off
TITLE Control de Modelos Ollama

ECHO Ubicando el directorio del script...
cd /d "%~dp0"

ECHO Activando el entorno virtual...
call Scripts\activate.bat

ECHO Entorno activado. Ejecutando el programa de Python...
pythonw activacion_modelos_ollama.py

ECHO El programa ha finalizado.
pause