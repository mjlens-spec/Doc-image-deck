@echo off
rem Doc-image-deck launcher for Windows. usage: deck.cmd ^<command^> [args]   (deck.cmd help)
rem Runs deck.py with the runtime Python when it exists, otherwise with the py launcher or python.
setlocal
set "S=%~dp0"
set "R=%LOCALAPPDATA%\doc-image-deck"
if defined DOC_IMAGE_DECK_HOME set "R=%DOC_IMAGE_DECK_HOME%"
set "PYTHONUTF8=1"
set "PYTHONDONTWRITEBYTECODE=1"
if not exist "%R%\venv\Scripts\python.exe" goto nopy
"%R%\venv\Scripts\python.exe" -X utf8 "%S%deck.py" %*
exit /b %ERRORLEVEL%
:nopy
where py >nul 2>nul
if errorlevel 1 goto nolauncher
py -3 -X utf8 "%S%deck.py" %*
exit /b %ERRORLEVEL%
:nolauncher
python -X utf8 "%S%deck.py" %*
exit /b %ERRORLEVEL%
