@echo off
setlocal
cd /d "%~dp0.." || exit /b 1

if defined VIRTUAL_ENV (
    set "BUILD_PY=%VIRTUAL_ENV%\Scripts\python.exe"
) else (
    set "BUILD_PY=%CD%\.venv\Scripts\python.exe"
    if not exist "%CD%\.venv\Scripts\python.exe" (
        where py >nul 2>&1
        if errorlevel 1 (
            python -m venv .venv || exit /b 1
        ) else (
            py -3 -m venv .venv || exit /b 1
        )
    )
)

"%BUILD_PY%" -c "import sys; sys.exit(sys.version_info < (3, 11))" || exit /b 1
"%BUILD_PY%" -m pip install -r requirements.txt || exit /b 1
"%BUILD_PY%" -m unittest discover -s tests -v || exit /b 1
"%BUILD_PY%" -m PyInstaller --clean --noconfirm build.spec || exit /b 1
echo Built "%CD%\dist\CS2-Sensitivity-Generator.exe"
