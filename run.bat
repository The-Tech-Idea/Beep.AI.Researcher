@echo off
REM Beep.AI.Researcher - Windows Launcher
REM This script automatically downloads embedded Python if needed and runs the app

cd /d "%~dp0"

REM Usage: run.bat [port]  e.g. run.bat 5006

echo.
echo ============================================================
echo   Beep.AI.Researcher - Windows Launcher
echo ============================================================
echo.

REM Check if embedded Python exists and is functional
if exist "python-embedded\python.exe" (
    echo [INFO] Embedded Python found, verifying installation...
    python-embedded\python.exe --version >nul 2>&1
    if errorlevel 1 (
        echo [WARN] Embedded Python found but not functional. Reinstalling...
        goto :download_python
    )
    REM Verify python311._pth is configured correctly (critical for venv module)
    findstr /C:"import site" "python-embedded\python311._pth" >nul 2>&1
    if errorlevel 1 (
        echo [WARN] python311._pth not configured correctly. Reconfiguring...
        powershell -NoProfile -ExecutionPolicy Bypass -Command "(Get-Content 'python-embedded\python311._pth') -replace '#import site', 'import site' | Set-Content 'python-embedded\python311._pth'"
    )
    python-embedded\python.exe -m pip --version >nul 2>&1
    if errorlevel 1 (
        echo [WARN] Pip not found in embedded Python. Installing pip...
        goto :install_pip
    )
    echo [INFO] Embedded Python is ready
    goto :run_launcher
)

:download_python

REM Embedded Python not found - download it automatically
echo [INFO] Embedded Python not found. Downloading automatically...
echo.

REM Create directory
if not exist "python-embedded" mkdir python-embedded

REM Download embedded Python using PowerShell
echo [INFO] Downloading Python 3.11.7 Embedded (64-bit)...
echo        This may take a few minutes...
powershell -NoProfile -ExecutionPolicy Bypass -Command "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; $ProgressPreference = 'SilentlyContinue'; Invoke-WebRequest -Uri 'https://www.python.org/ftp/python/3.11.7/python-3.11.7-embed-amd64.zip' -OutFile 'python-embedded.zip'"

if not exist "python-embedded.zip" (
    echo [ERROR] Failed to download Python!
    echo Please check your internet connection and try again.
    pause
    exit /b 1
)

REM Extract using PowerShell
echo [INFO] Extracting Python...
powershell -NoProfile -ExecutionPolicy Bypass -Command "Expand-Archive -Path 'python-embedded.zip' -DestinationPath 'python-embedded' -Force"

REM Clean up zip file
del python-embedded.zip

REM Configure embedded Python
echo [INFO] Configuring embedded Python...
powershell -NoProfile -ExecutionPolicy Bypass -Command "(Get-Content 'python-embedded\python311._pth') -replace '#import site', 'import site' | Set-Content 'python-embedded\python311._pth'"

:install_pip
REM Download and install pip
echo [INFO] Installing pip...
powershell -NoProfile -ExecutionPolicy Bypass -Command "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; $ProgressPreference = 'SilentlyContinue'; Invoke-WebRequest -Uri 'https://bootstrap.pypa.io/get-pip.py' -OutFile 'python-embedded\get-pip.py'"
if errorlevel 1 (
    echo [ERROR] Failed to download get-pip.py!
    echo Please check your internet connection.
    pause
    exit /b 1
)

python-embedded\python.exe python-embedded\get-pip.py
if errorlevel 1 (
    echo [ERROR] Failed to install pip!
    pause
    exit /b 1
)
del python-embedded\get-pip.py

REM Verify installation
if not exist "python-embedded\python.exe" (
    echo [ERROR] Embedded Python installation failed!
    pause
    exit /b 1
)

echo [INFO] Embedded Python installed successfully!
echo.

:run_launcher
REM Install/upgrade pip and install requirements
echo [INFO] Installing required packages...
python-embedded\python.exe -m pip install --upgrade pip --quiet --no-warn-script-location
if errorlevel 1 (
    echo [ERROR] Failed to upgrade pip!
    pause
    exit /b 1
)

REM Install virtualenv package by default (for reliable venv creation)
python-embedded\python.exe -m pip install virtualenv --quiet --no-warn-script-location

python-embedded\python.exe -m pip install -r requirements.txt --quiet --no-warn-script-location
if errorlevel 1 (
    echo [ERROR] Failed to install required packages!
    echo Please check your internet connection and requirements.txt file.
    pause
    exit /b 1
)

REM Run the launcher with embedded Python
python-embedded\python.exe run_hostadmin.py %*

if errorlevel 1 (
    echo.
    echo [ERROR] Failed to start Beep.AI.Researcher
    pause
    exit /b 1
)

pause
