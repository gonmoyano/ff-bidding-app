"""Shared logging configuration for FF Package Manager."""

import logging
from pathlib import Path
from datetime import datetime

# Global logger instance
_logger = None


def get_logger():
    """Get or create the logger instance."""
    global _logger

    if _logger is not None:
        return _logger

    try:
        # Create logs directory in the addon root
        # Path structure: client/ff_bidding_app/logger.py -> go up to root
        addon_root = Path(__file__).parent.parent.parent
        log_dir = addon_root / "logs"
        log_dir.mkdir(exist_ok=True)

        # Create log file with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = log_dir / f"ff_package_manager_{timestamp}.log"

        # Setup logging
        logging.basicConfig(
            level=logging.WARNING,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file, encoding='utf-8'),
                logging.StreamHandler()  # Also print to console
            ],
            force=True  # Override any existing configuration
        )

        _logger = logging.getLogger("FFPackageManager")
        _logger.setLevel(logging.WARNING)

        return _logger

    except Exception as e:
        print(f"Failed to setup logging: {e}")
        import traceback
        traceback.print_exc()

        # Return a basic logger if setup fails
        _logger = logging.getLogger("FFPackageManager")
        return _logger


# Initialize logger on import
logger = get_logger()