@echo off
setlocal
chcp 65001 >nul
title Smartplan Office - Start und Sicherung
set "smartplanPython=%LOCALAPPDATA%\SmartplanOffice\.venv\Scripts\python.exe"
if not exist "%smartplanPython%" (
  echo Die eingerichtete Python-Umgebung fehlt.
  echo Bitte zuerst das vorhandene Smartplan-Python-Offlinepaket installieren.
  pause
  exit /b 1
)
set "smartplanBackend=%~dp0backend"
if not exist "%smartplanBackend%\windows_office.py" set "smartplanBackend=%~dp0..\backend"
if not exist "%smartplanBackend%\windows_office.py" (
  echo Das Startpaket ist unvollstaendig. Bitte das gesamte ZIP entpacken.
  pause
  exit /b 1
)
"%smartplanPython%" -X utf8 "%smartplanBackend%\windows_office.py" "%~1"
if errorlevel 1 (
  echo Smartplan konnte den Vorgang nicht abschliessen. Bitte die Meldung oben beachten.
  pause
  exit /b 1
)
exit /b 0
