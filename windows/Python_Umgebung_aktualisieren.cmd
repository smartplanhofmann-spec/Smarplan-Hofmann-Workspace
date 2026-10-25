@echo off
setlocal
chcp 65001 >nul
title Smartplan Office - Python-Abhaengigkeiten offline aktualisieren
set "smartplanPython=%LOCALAPPDATA%\SmartplanOffice\.venv\Scripts\python.exe"
if not exist "%smartplanPython%" (
  echo Die bestehende Smartplan-Python-3.12-Umgebung fehlt.
  echo Dieses Update installiert Python nicht neu und legt keine Datenbank an.
  if not "%~1"=="--no-pause" pause
  exit /b 1
)
echo Bitte Smartplan-App und lokalen Server vor diesem Update schliessen.
echo Aktualisiert werden nur Python-Abhaengigkeiten aus diesem entpackten Paket.
"%smartplanPython%" -I -X utf8 "%~dp0Python_Umgebung_aktualisieren.py"
set "smartplanUpdateExit=%errorlevel%"
if not "%smartplanUpdateExit%"=="0" echo Update nicht vollstaendig. Bitte Meldung oben beachten und Starten.cmd noch nicht oeffnen.
if not "%~1"=="--no-pause" pause
exit /b %smartplanUpdateExit%
