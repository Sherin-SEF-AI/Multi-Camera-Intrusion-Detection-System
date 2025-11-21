"""
Logging Utility
Provides centralized logging with rotating file handlers and colored console output.
"""

import logging
import sys
from pathlib import Path
from logging.handlers import RotatingFileHandler
from typing import Optional
from datetime import datetime
import colorama
from colorama import Fore, Style

# Initialize colorama for cross-platform colored output
colorama.init(autoreset=True)


class ColoredFormatter(logging.Formatter):
    """
    Custom formatter that adds colors to console output based on log level.
    """

    COLORS = {
        'DEBUG': Fore.CYAN,
        'INFO': Fore.GREEN,
        'WARNING': Fore.YELLOW,
        'ERROR': Fore.RED,
        'CRITICAL': Fore.RED + Style.BRIGHT,
    }

    def format(self, record):
        """Format log record with colors."""
        levelname = record.levelname
        if levelname in self.COLORS:
            record.levelname = f"{self.COLORS[levelname]}{levelname}{Style.RESET_ALL}"
        return super().format(record)


class Logger:
    """
    Centralized logging system with file and console handlers.

    Features:
    - Rotating file handler to prevent unlimited log growth
    - Colored console output for better readability
    - Separate loggers for different modules
    - Configurable log levels and formats
    """

    _loggers = {}

    @staticmethod
    def setup_logger(
        name: str,
        log_file: Optional[str] = None,
        level: int = logging.INFO,
        log_to_console: bool = True,
        log_to_file: bool = True,
        max_file_size_mb: int = 10,
        backup_count: int = 5
    ) -> logging.Logger:
        """
        Set up and return a logger with specified configuration.

        Args:
            name: Logger name (typically module name)
            log_file: Path to log file. If None, uses default path
            level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
            log_to_console: Whether to output to console
            log_to_file: Whether to output to file
            max_file_size_mb: Maximum size of each log file in MB
            backup_count: Number of backup files to keep

        Returns:
            Configured logger instance
        """
        # Return existing logger if already set up
        if name in Logger._loggers:
            return Logger._loggers[name]

        # Create logger
        logger = logging.getLogger(name)
        logger.setLevel(level)
        logger.propagate = False

        # Clear existing handlers
        logger.handlers.clear()

        # Define log format
        file_format = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )

        console_format = ColoredFormatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%H:%M:%S'
        )

        # Add console handler
        if log_to_console:
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setLevel(level)
            console_handler.setFormatter(console_format)
            logger.addHandler(console_handler)

        # Add file handler
        if log_to_file:
            if log_file is None:
                # Default log file path
                project_root = Path(__file__).parent.parent.parent
                log_dir = project_root / "logs"
                log_dir.mkdir(parents=True, exist_ok=True)
                log_file = log_dir / f"{name}.log"

            # Create rotating file handler
            file_handler = RotatingFileHandler(
                log_file,
                maxBytes=max_file_size_mb * 1024 * 1024,
                backupCount=backup_count,
                encoding='utf-8'
            )
            file_handler.setLevel(level)
            file_handler.setFormatter(file_format)
            logger.addHandler(file_handler)

        # Store logger
        Logger._loggers[name] = logger

        return logger

    @staticmethod
    def get_logger(name: str) -> logging.Logger:
        """
        Get an existing logger or create a new one with default settings.

        Args:
            name: Logger name

        Returns:
            Logger instance
        """
        if name in Logger._loggers:
            return Logger._loggers[name]
        return Logger.setup_logger(name)

    @staticmethod
    def set_level(name: str, level: int) -> None:
        """
        Set logging level for a specific logger.

        Args:
            name: Logger name
            level: New logging level
        """
        if name in Logger._loggers:
            Logger._loggers[name].setLevel(level)
            for handler in Logger._loggers[name].handlers:
                handler.setLevel(level)

    @staticmethod
    def set_all_levels(level: int) -> None:
        """
        Set logging level for all loggers.

        Args:
            level: New logging level
        """
        for name in Logger._loggers:
            Logger.set_level(name, level)


def get_logger(name: str, **kwargs) -> logging.Logger:
    """
    Convenience function to get or create a logger.

    Args:
        name: Logger name
        **kwargs: Additional arguments for Logger.setup_logger()

    Returns:
        Logger instance

    Examples:
        >>> logger = get_logger(__name__)
        >>> logger.info("Application started")
        >>> logger.debug("Debug information")
        >>> logger.warning("Warning message")
        >>> logger.error("Error occurred")
        >>> logger.critical("Critical issue")
    """
    if kwargs:
        return Logger.setup_logger(name, **kwargs)
    return Logger.get_logger(name)


def setup_main_logger(config: Optional[dict] = None) -> logging.Logger:
    """
    Set up the main application logger with configuration from config dict.

    Args:
        config: Configuration dictionary. If None, uses defaults.

    Returns:
        Main logger instance
    """
    if config is None:
        config = {}

    # Extract logging configuration
    log_config = config.get('logging', {})

    level_str = log_config.get('level', 'INFO')
    level = getattr(logging, level_str.upper(), logging.INFO)

    log_to_file = log_config.get('log_to_file', True)
    log_to_console = log_config.get('log_to_console', True)
    log_file_path = log_config.get('log_file_path', None)
    max_file_size_mb = log_config.get('max_file_size_mb', 10)
    backup_count = log_config.get('backup_count', 5)

    # Set up main logger
    logger = Logger.setup_logger(
        name='IntrusionDetection',
        log_file=log_file_path,
        level=level,
        log_to_console=log_to_console,
        log_to_file=log_to_file,
        max_file_size_mb=max_file_size_mb,
        backup_count=backup_count
    )

    logger.info("=" * 80)
    logger.info("Multi-Camera Intrusion Detection System")
    logger.info(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 80)

    return logger


class LoggerContext:
    """
    Context manager for temporary logger configuration changes.

    Examples:
        >>> with LoggerContext('mylogger', level=logging.DEBUG):
        ...     logger.debug("This will be logged at DEBUG level")
    """

    def __init__(self, name: str, level: Optional[int] = None):
        """
        Initialize logger context.

        Args:
            name: Logger name
            level: Temporary logging level
        """
        self.name = name
        self.new_level = level
        self.old_level = None

    def __enter__(self):
        """Enter context - save current level and set new level."""
        logger = Logger.get_logger(self.name)
        self.old_level = logger.level
        if self.new_level is not None:
            Logger.set_level(self.name, self.new_level)
        return logger

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit context - restore original level."""
        if self.old_level is not None:
            Logger.set_level(self.name, self.old_level)


if __name__ == "__main__":
    # Test logger functionality
    logger = get_logger("test")

    logger.debug("This is a debug message")
    logger.info("This is an info message")
    logger.warning("This is a warning message")
    logger.error("This is an error message")
    logger.critical("This is a critical message")

    # Test context manager
    logger = get_logger("test_context", level=logging.WARNING)
    logger.debug("This won't be logged (level WARNING)")

    with LoggerContext("test_context", level=logging.DEBUG):
        logger.debug("This will be logged (temporary DEBUG)")

    logger.debug("This won't be logged again (back to WARNING)")
