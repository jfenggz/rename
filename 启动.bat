@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"

rem --- find a Python that really has tkinter (skip broken / store stubs) ---
set "TARGET="
for /f "delims=" %%P in ('where python 2^>nul') do (
    if not defined TARGET (
        "%%~fP" -c "import tkinter" >nul 2>&1
        if not errorlevel 1 set "TARGET=%%~fP"
    )
)

if not defined TARGET (
    py -3 -c "import tkinter" >nul 2>&1
    if not errorlevel 1 set "TARGET=py -3"
)

if not defined TARGET goto :nopython

rem --- prefer pythonw.exe (same folder) so no console window stays open ---
set "LAUNCH=!TARGET!"
if /i not "!TARGET!"=="py -3" (
    for %%F in ("!TARGET!") do (
        if exist "%%~dpFpythonw.exe" set "LAUNCH=%%~dpFpythonw.exe"
    )
)

if /i "!TARGET!"=="py -3" (
    start "" pyw -3 main.py %*
) else (
    start "" "!LAUNCH!" main.py %*
)
exit /b 0

:nopython
echo.
echo   [X] 没有找到带 tkinter 的 Python
echo.
echo   请从 https://www.python.org/downloads/ 安装 Python 3.8 或更高版本，
echo   安装时勾选 "tcl/tk and IDLE"，并选择 "Add python.exe to PATH"。
echo.
pause
exit /b 1
