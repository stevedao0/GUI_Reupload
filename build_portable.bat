@echo off
REM =====================================================================
REM YouTube Reupload Detector - Portable Build Script
REM Builds standalone executable with bundled ffmpeg
REM =====================================================================

echo =====================================================================
echo YouTube Reupload Detector - Portable Build
echo =====================================================================
echo.

REM Step 1: Clean previous builds
echo [1/5] Cleaning previous builds...
if exist "build" rmdir /s /q build
if exist "dist" rmdir /s /q dist
if exist "YouTubeReuploadDetector.spec" del YouTubeReuploadDetector.spec
echo    Done!
echo.

REM Step 2: Build with PyInstaller
echo [2/5] Building executable with PyInstaller...
echo    This may take 5-10 minutes...
pyinstaller build_exe.spec --clean
if %errorlevel% neq 0 (
    echo    ERROR: Build failed!
    pause
    exit /b 1
)
echo    Done!
echo.

REM Step 3: Copy config file
echo [3/5] Copying configuration files...
copy config.yaml "dist\YouTubeReuploadDetector\config.yaml" >nul
echo    Done!
echo.

REM Step 4: Bundle ffmpeg (if available)
echo [4/5] Bundling ffmpeg...
where ffmpeg >nul 2>&1
if %errorlevel% equ 0 (
    echo    Found ffmpeg in PATH, bundling...
    for /f "delims=" %%i in ('where ffmpeg') do set FFMPEG_PATH=%%i
    for %%i in ("%FFMPEG_PATH%") do set FFMPEG_DIR=%%~dpi

    copy "%FFMPEG_DIR%ffmpeg.exe" "dist\YouTubeReuploadDetector\ffmpeg.exe" >nul 2>&1
    if %errorlevel% equ 0 (
        echo    - ffmpeg.exe bundled successfully
    ) else (
        echo    WARNING: Could not copy ffmpeg.exe
    )

    copy "%FFMPEG_DIR%ffprobe.exe" "dist\YouTubeReuploadDetector\ffprobe.exe" >nul 2>&1
    if %errorlevel% equ 0 (
        echo    - ffprobe.exe bundled successfully
    ) else (
        echo    WARNING: Could not copy ffprobe.exe
    )
) else (
    echo    WARNING: ffmpeg not found in PATH!
    echo    Please manually copy ffmpeg.exe and ffprobe.exe to dist\YouTubeReuploadDetector\
)
echo.

REM Step 5: Create README
echo [5/5] Creating README...
(
echo ===================================================================
echo   YOUTUBE REUPLOAD DETECTOR - PORTABLE VERSION
echo ===================================================================
echo.
echo CACH SU DUNG:
echo --------------
echo.
echo 1. KHOI DONG UNG DUNG
echo    - Chay file: YouTubeReuploadDetector.exe
echo    - Giao dien GUI se hien ra
echo.
echo 2. YEU CAU HE THONG
echo    - Windows 10/11 ^(64-bit^)
echo    - RAM: Toi thieu 8GB, khuyen nghi 16GB+
echo    - GPU: NVIDIA/AMD ^(tuy chon, de tang toc^)
echo    - Ket noi Internet ^(de download video^)
echo.
echo 3. CAU HINH
echo    - Chinh sua file 'config.yaml' trong cung thu muc
echo    - Cau hinh GPU, chat luong video, so luong download,...
echo.
echo 4. FFMPEG
echo    - Da duoc bundle san ^(ffmpeg.exe, ffprobe.exe^)
echo    - Khong can cai dat them!
echo.
echo 5. SU DUNG
echo    a. Import file Excel chua danh sach YouTube URLs
echo    b. Dieu chinh settings neu can
echo    c. Click "START PROCESSING"
echo    d. Doi xu ly hoan tat
echo    e. Xem ket qua va Export ra Excel
echo.
echo LUU Y QUAN TRONG:
echo -----------------
echo.
echo - Lan dau chay, ung dung se download cac AI models ^(~2-5GB^)
echo - Models duoc luu tai: %%USERPROFILE%%\.cache\
echo - Can du dung luong o cung cho temporary downloads
echo - Khuyen nghi su dung GPU de tang toc xu ly
echo.
echo TROUBLESHOOTING:
echo ----------------
echo.
echo 1. Loi GPU:
echo    - Kiem tra NVIDIA/AMD drivers
echo    - Set gpu.enabled: false trong config.yaml de dung CPU
echo.
echo 2. Out of Memory:
echo    - Giam gpu.batch_size trong config.yaml
echo    - Giam video_quality xuong 360p hoac 480p
echo    - Dong cac ung dung khac
echo.
echo 3. Download cham:
echo    - Giam download.max_parallel
echo    - Kiem tra ket noi Internet
echo.
echo ===================================================================
echo Phien ban: v1.3.0
echo Build date: %date% %time%
echo ===================================================================
) > "dist\YouTubeReuploadDetector\README.txt"
echo    Done!
echo.

REM Summary
echo =====================================================================
echo BUILD COMPLETED SUCCESSFULLY!
echo =====================================================================
echo.
echo Output location: dist\YouTubeReuploadDetector\
echo.
echo Package contents:
dir /b "dist\YouTubeReuploadDetector" | findstr /v "_internal"
echo.
echo To distribute: Copy entire "dist\YouTubeReuploadDetector" folder
echo =====================================================================
echo.
pause
