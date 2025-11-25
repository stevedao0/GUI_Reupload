"""
FFmpeg Helper - Auto-detect bundled ffmpeg or system ffmpeg
"""

import os
import sys
from pathlib import Path


def get_ffmpeg_path():
    """Get path to ffmpeg executable.

    Priority:
    1. Explicit environment override via FFMPEG_PATH
    2. Bundled ffmpeg next to the app (PyInstaller) or project root
    3. Bundled ffmpeg inside an `ffmpeg/bin` subfolder
    4. System PATH ffmpeg (by returning plain 'ffmpeg')

    Returns:
        str: Path to ffmpeg executable or 'ffmpeg' (system default).
    """
    # 1) Allow explicit override via environment variable
    env_path = os.environ.get("FFMPEG_PATH")
    if env_path and Path(env_path).exists():
        return env_path

    # 2) Determine application directory
    if getattr(sys, 'frozen', False):
        # Running as compiled executable
        app_dir = Path(sys.executable).parent
    else:
        # Running as script (project layout)
        app_dir = Path(__file__).parent.parent.parent

    # 3) Check for bundled ffmpeg in common locations
    candidates = [
        app_dir / "ffmpeg.exe",                      # e.g. Reupload/ffmpeg.exe
        app_dir / "ffmpeg" / "ffmpeg.exe",         # e.g. Reupload/ffmpeg/ffmpeg.exe
        app_dir / "ffmpeg" / "bin" / "ffmpeg.exe" # e.g. Reupload/ffmpeg/bin/ffmpeg.exe
    ]
    for cand in candidates:
        if cand.exists():
            return str(cand)

    # 4) Fall back to system PATH
    return "ffmpeg"


def get_ffprobe_path():
    """Get path to ffprobe executable.

    Priority:
    1. Explicit environment override via FFPROBE_PATH
    2. Bundled ffprobe next to the app or project root
    3. Bundled ffprobe inside an `ffmpeg/bin` subfolder
    4. System PATH ffprobe (by returning plain 'ffprobe').
    """
    env_path = os.environ.get("FFPROBE_PATH")
    if env_path and Path(env_path).exists():
        return env_path

    if getattr(sys, 'frozen', False):
        app_dir = Path(sys.executable).parent
    else:
        app_dir = Path(__file__).parent.parent.parent

    candidates = [
        app_dir / "ffprobe.exe",
        app_dir / "ffmpeg" / "ffprobe.exe",
        app_dir / "ffmpeg" / "bin" / "ffprobe.exe",
    ]
    for cand in candidates:
        if cand.exists():
            return str(cand)

    return "ffprobe"


# Set environment variables for yt-dlp and other tools
FFMPEG_LOCATION = get_ffmpeg_path()
FFPROBE_LOCATION = get_ffprobe_path()

# Export for easy import
__all__ = ['get_ffmpeg_path', 'get_ffprobe_path', 'FFMPEG_LOCATION', 'FFPROBE_LOCATION']
