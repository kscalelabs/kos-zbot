import logging
import os
import sys
from datetime import datetime
from typing import Optional

class KOSLoggerSetup:
    _instance = None
    _initialized = False

    @classmethod
    def setup(cls, 
              log_dir: str = "logs",
              console_level: int = logging.INFO,
              file_level: int = logging.DEBUG) -> None:
        """
        Configure the root logger for KOS application.
        Should be called once at application startup.
        
        Args:
            log_dir: Directory where log files will be stored
            console_level: Logging level for console output
            file_level: Logging level for file output
        """
        if cls._initialized:
            return

        # Create logs directory if it doesn't exist
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
        
        # Generate log filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = os.path.join(log_dir, f"kos_{timestamp}.log")
        
        # Create formatters
        file_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        console_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        
        # Configure root logger
        root_logger = logging.getLogger()
        root_logger.setLevel(min(console_level, file_level))
        
        # Remove any existing handlers
        root_logger.handlers = []
        
        # Create and configure file handler
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(file_level)
        file_handler.setFormatter(file_formatter)
        root_logger.addHandler(file_handler)
        
        # Create and configure console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(console_level)
        console_handler.setFormatter(console_formatter)
        root_logger.addHandler(console_handler)
        
        cls._initialized = True

def get_logger(name: str) -> logging.Logger:
    """
    Get a logger with the specified name.
    
    Args:
        name: Name of the module/class (typically __name__ or f"{__name__}.{class_name}")
    
    Returns:
        logging.Logger: Logger instance
    """
    return logging.getLogger(name)

# Common log levels as constants for convenience
LOG_LEVELS = {
    'DEBUG': logging.DEBUG,
    'INFO': logging.INFO,
    'WARNING': logging.WARNING,
    'ERROR': logging.ERROR,
    'CRITICAL': logging.CRITICAL
}

def get_log_level(default_level: int = logging.INFO) -> int:
    """Get log level from environment variable or return default"""
    level_name = os.environ.get('KOS_LOG_LEVEL', '').upper()
    return LOG_LEVELS.get(level_name, default_level)