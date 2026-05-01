"""Logging configuration for the hiring agent."""

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

import structlog

LOG_DIR = Path("logs")


def setup_logging(log_level: str = "INFO") -> None:
    """
    Configure structlog with JSON output to stdout and file rotation.
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    """
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    
    # Convert string log level to logging constant
    level = getattr(logging, log_level.upper(), logging.INFO)
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    
    # Clear existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Stdout handler
    stdout_handler = logging.StreamHandler()
    stdout_handler.setLevel(level)
    
    # File handler with rotation
    file_handler = RotatingFileHandler(
        LOG_DIR / "hiring_agent.log",
        maxBytes=10_000_000,  # 10MB
        backupCount=5,
    )
    file_handler.setLevel(level)
    
    # Structlog processor formatter
    formatter = structlog.stdlib.ProcessorFormatter(
        processor=structlog.processors.JSONRenderer(),
        foreign_pre_chain=[
            structlog.stdlib.ProcessorFormatter.remove_log_record_nanny,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
        ],
    )
    
    stdout_handler.setFormatter(formatter)
    file_handler.setFormatter(formatter)
    
    root_logger.addHandler(stdout_handler)
    root_logger.addHandler(file_handler)
    
    # Configure structlog
    structlog.configure(
        processors=[
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """
    Get a configured logger instance.
    
    Args:
        name: Logger name (typically __name__)
    
    Returns:
        Configured structlog bound logger
    """
    return structlog.get_logger(name)
