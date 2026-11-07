@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"

rem ---------- 1. 找一个自带 tkinter 的 Python ----------
set "PY="
for /f "delims=" %%P in ('where python 2^>nul') do (
    if not defined PY (
        "%%~fP" -c "import tkinter" >nul 2>&1
        if not errorlevel 1 set "PY=%%~fP"
    )
)
if not defined PY (
    py -3 -c "import tkinter" >nul 2>&1
    if not errorlevel 1 set "PY=py -3"
)
if not defined PY goto :nopython

rem ---------- 2. 准备打包环境 ----------
if not exist ".buildenv\Scripts\python.exe" (
    echo [1/3] 创建打包环境...
    %PY% -m venv .buildenv || goto :fail
    ".buildenv\Scripts\python.exe" -m pip install -q --upgrade pip || goto :fail
)
".buildenv\Scripts\python.exe" -c "import PyInstaller" >nul 2>&1
if errorlevel 1 (
    echo       安装 PyInstaller...
    ".buildenv\Scripts\python.exe" -m pip install -q pyinstaller || goto :fail
)

rem ---------- 3. 生成图标 + 打包 ----------
echo [2/3] 生成图标...
".buildenv\Scripts\python.exe" build\make_icon.py || goto :fail

echo [3/3] 打包 exe...
".buildenv\Scripts\pyinstaller.exe" --noconfirm --clean --onefile --windowed ^
    --name "媒体文件重命名" --icon build\app.ico --paths vendor ^
    --collect-all tkinterdnd2 --add-data "build\app.ico;." ^
    --workpath .pyi-build --specpath . --distpath . main.py || goto :fail

echo.
echo 完成：媒体文件重命名.exe
pause
exit /b 0

:nopython
echo.
echo   [X] 没有找到带 tkinter 的 Python，无法打包。
echo       请安装 Python 3.8+ 并勾选 "tcl/tk and IDLE"。
echo.
pause
exit /b 1

:fail
echo.
echo   [X] 打包失败，请查看上方错误信息。
echo.
pause
exit /b 1
