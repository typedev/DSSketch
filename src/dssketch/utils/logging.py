"""
Logging configuration for DSSketch.

Provides centralized logging that outputs to files in a 'logs' subdirectory
of the conversion file's directory. The logs directory is created automatically
if it doesn't exist. Log filename format: dssketch_{dssketch_name}_{timestamp}.log

The logger automatically maintains only the 5 most recent log files with the
'dssketch_' prefix, removing older logs to prevent log directory bloat.
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Optional


class DSSketchLogger:
    """Centralized logger for DSSketch operations."""

    _logger: Optional[logging.Logger] = None
    _current_log_file: Optional[Path] = None

    @classmethod
    def _cleanup_old_logs(cls, logs_dir: Path, keep_count: int = 5) -> None:
        """
        Remove old log files, keeping only the most recent ones.

        Args:
            logs_dir: Directory containing log files
            keep_count: Number of most recent log files to keep (default: 5)
        """
        # Find all dssketch log files
        log_files = sorted(
            logs_dir.glob("dssketch_*.log"),
            key=lambda p: p.stat().st_mtime,
            reverse=True
        )

        # Remove old log files beyond keep_count
        for old_log in log_files[keep_count:]:
            try:
                old_log.unlink()
            except Exception:
                # Silently ignore deletion errors
                pass

    @classmethod
    def setup_logger(cls, file_path: str, log_level: int = logging.INFO) -> logging.Logger:
        """
        Setup logger for a conversion operation.

        Args:
            file_path: Path to the file being converted (DSSketch or DesignSpace)
            log_level: Logging level (default: INFO)

        Returns:
            Configured logger instance
        """
        # Get base filename without extension
        input_path = Path(file_path)
        base_name = input_path.stem
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:17]  # Include microseconds, trim to 2 digits

        # Create logs directory if it doesn't exist
        logs_dir = input_path.parent / "logs"
        logs_dir.mkdir(exist_ok=True)

        # Create log filename in logs directory with dssketch_ prefix
        log_filename = f"dssketch_{base_name}_{timestamp}.log"
        log_path = logs_dir / log_filename

        # Remove existing handlers if logger already exists
        if cls._logger:
            for handler in cls._logger.handlers[:]:
                cls._logger.removeHandler(handler)
                handler.close()

        # Create logger
        cls._logger = logging.getLogger('dssketch')
        cls._logger.setLevel(log_level)

        # Create file handler
        file_handler = logging.FileHandler(log_path, mode='w', encoding='utf-8')
        file_handler.setLevel(log_level)

        # Create console handler for important messages
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)

        # Create formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )

        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)

        # Add handlers
        cls._logger.addHandler(file_handler)
        cls._logger.addHandler(console_handler)

        cls._current_log_file = log_path

        # Log startup message
        cls._logger.info(f"DSSketch logging started for file: {file_path}")
        cls._logger.info(f"Log file: {log_path}")

        # Clean up old log files, keeping only the 5 most recent
        # (done after creating new log file so it's included in the count)
        cls._cleanup_old_logs(logs_dir, keep_count=5)

        return cls._logger

    @classmethod
    def get_logger(cls) -> Optional[logging.Logger]:
        """Get the current logger instance."""
        return cls._logger

    @classmethod
    def get_log_file_path(cls) -> Optional[Path]:
        """Get the current log file path."""
        return cls._current_log_file

    @classmethod
    def info(cls, message: str) -> None:
        """Log info message."""
        if cls._logger:
            cls._logger.info(message)

    @classmethod
    def warning(cls, message: str) -> None:
        """Log warning message."""
        if cls._logger:
            cls._logger.warning(message)

    @classmethod
    def error(cls, message: str) -> None:
        """Log error message."""
        if cls._logger:
            cls._logger.error(message)

    @classmethod
    def debug(cls, message: str) -> None:
        """Log debug message."""
        if cls._logger:
            cls._logger.debug(message)

    @classmethod
    def success(cls, message: str) -> None:
        """Log success message (using info level)."""
        if cls._logger:
            cls._logger.info(f"✅ {message}")

    @classmethod
    def cleanup(cls) -> None:
        """Clean up logger resources."""
        if cls._logger:
            for handler in cls._logger.handlers[:]:
                cls._logger.removeHandler(handler)
                handler.close()
            cls._logger = None
            cls._current_log_file = None
