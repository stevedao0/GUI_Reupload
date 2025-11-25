"""
YouTube Reupload Detector - Main Entry Point
Hệ thống phát hiện video YouTube reupload sử dụng AI
Compact UI: Small input window + separate log/results windows
"""

import sys
from pathlib import Path
from PyQt6.QtWidgets import QApplication

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.utils import setup_logger, get_config
from src.gui import AppController

logger = setup_logger(__name__)


def main():
    """Main entry point - Compact UI"""
    try:
        logger.info("=" * 80)
        logger.info("YouTube Reupload Detector - Starting...")
        logger.info("=" * 80)
        
        # Load configuration
        config = get_config('config.yaml')
        logger.info(f"Configuration loaded from: config.yaml")
        
        # Create Qt application (pipeline will be lazy-loaded on first start)
        app = QApplication(sys.argv)
        app.setApplicationName("YouTube Reupload Detector")
        app.setOrganizationName("SteveDao")
        
        # Create app controller (manages compact UI windows)
        controller = AppController(config)
        controller.setup_main_window()
        
        logger.info("Application started successfully (pipeline will be initialized on first run)")
        logger.info("=" * 80)
        
        # Run application
        sys.exit(app.exec())
        
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()

