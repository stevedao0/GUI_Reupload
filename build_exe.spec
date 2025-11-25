# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for YouTube Reupload Detector
Build: pyinstaller build_exe.spec
"""

from PyInstaller.utils.hooks import collect_data_files, collect_submodules
import sys
from pathlib import Path

block_cipher = None

# Collect all submodules
hidden_imports = [
    # PyQt6
    'PyQt6.QtCore',
    'PyQt6.QtGui',
    'PyQt6.QtWidgets',
    'PyQt6.sip',

    # Deep Learning
    'torch',
    'torchvision',
    'transformers',
    'transformers.models',
    'transformers.models.clip',

    # Audio
    'librosa',
    'librosa.core',
    'librosa.feature',
    'soundfile',
    'pydub',
    'audioread',

    # OCR
    'easyocr',
    'easyocr.easyocr',
    'paddleocr',

    # Video
    'cv2',
    'scenedetect',

    # Data processing
    'numpy',
    'pandas',
    'openpyxl',

    # Utils
    'yaml',
    'tqdm',
    'colorama',
    'PIL',
    'PIL.Image',
    'requests',
    'urllib3',

    # yt-dlp
    'yt_dlp',
    'yt_dlp.utils',
    'yt_dlp.extractor',

    # Additional dependencies
    'sklearn',
    'scipy',
    'matplotlib',
    'regex',
    'ftfy',
]

# Collect data files
datas = [
    ('config.yaml', '.'),
]

# Try to collect transformers data
try:
    datas += collect_data_files('transformers')
except:
    pass

# Try to collect easyocr data
try:
    datas += collect_data_files('easyocr')
except:
    pass

# Try to collect paddleocr data
try:
    datas += collect_data_files('paddleocr')
except:
    pass

# Binaries to exclude (reduce size)
excludes = [
    'tkinter',
    'matplotlib',
    'IPython',
    'jupyter',
    'notebook',
    'pytest',
    'sphinx',
]

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(
    a.pure,
    a.zipped_data,
    cipher=block_cipher
)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='YouTubeReuploadDetector',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,  # Set to False to hide console window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,  # Add your icon file here if you have one
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='YouTubeReuploadDetector',
)
