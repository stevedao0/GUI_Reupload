"""
YouTube Reupload Detector - Compact UI Entry Point
Compact main window + separate log/results windows
"""

import sys
from pathlib import Path
from PyQt6.QtWidgets import QApplication

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.utils import setup_logger, get_config
from src.pipeline import ProcessingPipeline
from src.gui import AppController

logger = setup_logger(__name__)


def main():
    """Main entry point for compact UI"""
    try:
        logger.info("=" * 80)
        logger.info("YouTube Reupload Detector - Compact UI - Starting...")
        logger.info("=" * 80)
        
        # Load configuration
        config = get_config('config.yaml')
        logger.info(f"Configuration loaded from: config.yaml")
        
        # Initialize pipeline
        logger.info("Initializing processing pipeline...")
        pipeline = ProcessingPipeline(config)
        
        # Create Qt application
        app = QApplication(sys.argv)
        app.setApplicationName("YouTube Reupload Detector")
        app.setOrganizationName("SteveDao")
        
        # Create app controller
        controller = AppController(config, pipeline)
        controller.setup_main_window()
        
        logger.info("Application started successfully")
        logger.info("=" * 80)
        
        # Run application
        sys.exit(app.exec())
        
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()

