@echo off
echo ========================================
echo YouTube Reupload Detector - Installation
echo ========================================
echo.

REM Check Python
python --version > nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found!
    echo Please install Python 3.10 or newer from https://www.python.org/
    pause
    exit /b 1
)

echo [1/5] Creating virtual environment...
python -m venv venv
if errorlevel 1 (
    echo ERROR: Failed to create virtual environment
    pause
    exit /b 1
)

echo [2/5] Activating virtual environment...
call venv\Scripts\activate.bat

echo [3/5] Upgrading pip...
python -m pip install --upgrade pip

echo [4/5] Installing PyTorch (CUDA)...
echo.
echo Select GPU type:
echo 1. NVIDIA (CUDA)
echo 2. AMD (ROCm)
echo 3. CPU only
echo.
set /p gpu_choice="Enter choice (1-3): "

if "%gpu_choice%"=="1" (
    echo Installing PyTorch with CUDA support...
    pip install torch torchvision --index-url https://download.pytorch.org/whl/cu118
) else (
    if "%gpu_choice%"=="2" (
        echo Installing PyTorch with ROCm support...
        pip install torch torchvision --index-url https://download.pytorch.org/whl/rocm5.4.2
    ) else (
        echo Installing PyTorch ^(CPU only^)...
        pip install torch torchvision
    )
)

echo [5/5] Installing other dependencies...
pip install -r requirements.txt

echo.
echo ========================================
echo Installation complete!
echo ========================================
echo.
echo To run the application:
echo   run.bat
echo.
echo Or manually:
echo   venv\Scripts\activate
echo   python main.py
echo.
pause

