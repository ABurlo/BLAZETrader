import logging
import os
from colorlog import ColoredFormatter
from typing import Optional

class TradingLogger:
    def __init__(self, log_dir: str = "logs", log_level: str = "INFO"):
        """
        Initialize the TradingLogger with colored logging to files and console.

        Args:
            log_dir: Directory to store log files (default: "logs").
            log_level: Logging level (e.g., "DEBUG", "INFO", "WARNING", "ERROR", default: "INFO").
        """
        # Ensure the log directory exists, with error handling
        try:
            os.makedirs(log_dir, exist_ok=True)
        except PermissionError as e:
            raise RuntimeError(f"Cannot create log directory {log_dir}: {str(e)}")

        # Set the logging level
        self.log_level = getattr(logging, log_level.upper(), logging.INFO)
        
        # Initialize loggers
        self.global_logger = self._setup_logger("global", os.path.join(log_dir, "global.log"), "green")
        self.error_logger = self._setup_logger("error", os.path.join(log_dir, "errors.log"), "red")
        self.trade_logger = self._setup_logger("trade", os.path.join(log_dir, "trades.log"), "blue")

    def _setup_logger(self, name: str, filename: str, color: str) -> logging.Logger:
        """
        Set up a logger with colored output to both file and console.

        Args:
            name: Logger name.
            filename: Path to the log file.
            color: Color for console output (e.g., "green", "red", "blue").

        Returns:
            logging.Logger: Configured logger instance.
        """
        # Get or create logger
        logger = logging.getLogger(name)      
        # Remove any existing handlers to prevent duplicates
        if logger.hasHandlers():
            logger.handlers.clear()
        
        # Set logging level
        logger.setLevel(self.log_level)

        # Create formatter with colored output
        formatter = ColoredFormatter(
            "%(log_color)s%(asctime)s | %(name)s | %(levelname)s | %(message)s%(reset)s",
            datefmt="%Y-%m-%d %H:%M:%S",
            log_colors={
                'DEBUG': 'cyan',
                'INFO': color,
                'WARNING': 'yellow',
                'ERROR': 'red',
                'CRITICAL': 'bold_red'
            }
        )

        # File handler
        try:
            fh = logging.FileHandler(filename)
            fh.setFormatter(formatter)
            logger.addHandler(fh)
        except (IOError, PermissionError) as e:
            print(f"Warning: Cannot write to log file {filename}: {str(e)}")

        # Console handler
        ch = logging.StreamHandler()
        ch.setFormatter(formatter)
        logger.addHandler(ch)

        return logger

    def log(self, level: str, message: str, logger_type: str = "global") -> None:
        """
        Log a message with the specified level and logger type.

        Args:
            level: Logging level (e.g., "DEBUG", "INFO", "ERROR").
            message: Message to log.
            logger_type: Type of logger to use ("global", "error", "trade").
        """
        level = level.upper()
        log_func = getattr(self._get_logger(logger_type), level.lower(), None)
        if log_func and callable(log_func):
            log_func(message)
        else:
            self.global_logger.error(f"Invalid logging level or logger type: {level}, {logger_type}")

    def _get_logger(self, logger_type: str) -> logging.Logger:
        """
        Get the appropriate logger based on type.

        Args:
            logger_type: Type of logger ("global", "error", "trade").

        Returns:
            logging.Logger: The requested logger instance.
        """
        logger_map = {
            "global": self.global_logger,
            "error": self.error_logger,
            "trade": self.trade_logger
        }
        return logger_map.get(logger_type, self.global_logger)

    def set_log_level(self, level: str) -> None:
        """
        Set the logging level for all loggers.

        Args:
            level: Logging level (e.g., "DEBUG", "INFO", "WARNING", "ERROR").
        """
        self.log_level = getattr(logging, level.upper(), logging.INFO)
        for logger in [self.global_logger, self.error_logger, self.trade_logger]:
            logger.setLevel(self.log_level)