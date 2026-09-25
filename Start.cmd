@echo off
setlocal EnableExtensions
title Staydesk - Hotelservice-Demo
cd /d "%~dp0"
if errorlevel 1 goto folder_error
echo.
echo  Staydesk - Lokale Hotelservice-Demo
echo  =================================
echo.
echo [1/5] Python und virtuelle Umgebung pruefen ...
if exist ".venv\Scripts\python.exe" goto environment_ready
py -3 -c "import sys; sys.exit(not ((3,11) <= sys.version_info[:2] < (3,15)))" >nul 2>&1
if errorlevel 1 goto try_python
py -3 -m venv .venv
if errorlevel 1 goto environment_error
goto environment_ready

:try_python
python -c "import sys; sys.exit(not ((3,11) <= sys.version_info[:2] < (3,15)))" >nul 2>&1
if errorlevel 1 goto python_error
python -m venv .venv
if errorlevel 1 goto environment_error

:environment_ready
".venv\Scripts\python.exe" -c "import sys; sys.exit(not ((3,11) <= sys.version_info[:2] < (3,15)))"
if errorlevel 1 goto environment_error
echo [2/5] Abhaengigkeiten installieren bzw. abgleichen ...
".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -r requirements-dev.txt
if errorlevel 1 goto install_error
echo [3/5] Paketabhaengigkeiten pruefen ...
".venv\Scripts\python.exe" -m pip check
if errorlevel 1 goto check_error
echo [4/5] Automatisierte Tests ausfuehren - isolierte Testdaten ...
".venv\Scripts\python.exe" -m pytest -q
if errorlevel 1 goto test_error
echo [5/5] Server starten und Browser oeffnen ...
echo Das Fenster bitte offen lassen. Beenden mit Strg+C.
".venv\Scripts\python.exe" run.py
if errorlevel 1 goto start_error
echo.
echo Anwendung beendet. Ihre Auftraege bleiben im Ordner data gespeichert.
pause
exit /b 0

:python_error
echo FEHLER: Python 3.11 bis 3.14 wird benoetigt; Python 3.12 wird empfohlen.
echo Installieren Sie Python von https://www.python.org/downloads/windows/
echo Aktivieren Sie "Add python.exe to PATH" und starten Sie diese Datei erneut.
goto failed
:environment_error
echo FEHLER: Die virtuelle Umgebung konnte nicht erstellt oder verwendet werden.
echo Pruefen Sie Python, Schreibrechte und den Ordner .venv.
echo Bei einer kopierten Umgebung: .venv umbenennen und Start.cmd erneut starten.
goto failed
:install_error
echo FEHLER: Installation fehlgeschlagen. Pruefen Sie Internetzugang und die Meldung oben.
echo Der erste Start benoetigt Internet. Es werden keine Adminrechte benoetigt.
goto failed
:check_error
echo FEHLER: Paketversionen passen nicht zusammen. Details stehen oben.
goto failed
:test_error
echo FEHLER: Mindestens ein Test ist fehlgeschlagen. Der Server wurde nicht gestartet.
goto failed
:start_error
echo FEHLER: Start fehlgeschlagen. Pruefen Sie Port und Schreibrechte; Details stehen oben.
goto failed
:folder_error
echo FEHLER: Projektordner nicht erreichbar. ZIP zuerst vollstaendig entpacken.
:failed
echo.
pause
exit /b 1
