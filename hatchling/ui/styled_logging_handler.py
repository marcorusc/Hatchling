"""Styled logging handler for prompt_toolkit integration.

This module provides a custom logging handler that formats log messages using
prompt_toolkit's styling capabilities, ensuring consistent appearance in the CLI.
"""

import logging
from typing import Dict, Optional, Tuple, Any
from datetime import datetime

from prompt_toolkit import print_formatted_text
from prompt_toolkit.formatted_text import FormattedText
from prompt_toolkit.patch_stdout import patch_stdout


class StyledLoggingHandler(logging.StreamHandler):
    """A logging handler that outputs styled logs using prompt_toolkit."""
    
    # Default style mapping for different log levels
    DEFAULT_STYLES = {
        logging.DEBUG: 'fg:cyan',
        logging.INFO: 'fg:white',
        logging.WARNING: 'fg:yellow',
        logging.ERROR: 'fg:red',
        logging.CRITICAL: 'bg:red fg:white bold',
    }
    
    def __init__(self, formatter: Optional[logging.Formatter] = None, styles: Optional[Dict[int, str]] = None):
        """Initialize the styled logging handler.
        
        Args:
            formatter (Optional[logging.Formatter], optional): Formatter to use for log messages.
                                                             Defaults to None.
            styles (Optional[Dict[int, str]], optional): Mapping of log levels to styles. 
                                                       Defaults to DEFAULT_STYLES.
        """
        super().__init__()
        self.styles = styles or self.DEFAULT_STYLES
        if formatter:
            self.setFormatter(formatter)
        else:
            # Default formatter that only includes the message
            self.setFormatter(logging.Formatter('%(message)s'))
    
    def emit(self, record: logging.LogRecord) -> None:
        """Format and emit a log record with styling.
        
        Args:
            record (logging.LogRecord): The log record to emit.
        """
        try:
            # Use the formatter to format the record
            msg = self.format(record)
            style = self.styles.get(record.levelno, 'fg:white')
            
            # Format the message with prompt_toolkit styling
            formatted_text = FormattedText([
                (style, msg)
            ])
            
            # Use patch_stdout to avoid interfering with input prompts
            with patch_stdout():
                print_formatted_text(formatted_text)
                
        except Exception:
            self.handleError(record)
    
    @staticmethod
    def setup_console_handler(logger_name: Optional[str] = None, 
                             formatter: Optional[logging.Formatter] = None) -> 'StyledLoggingHandler':
        """Set up a styled console handler for the specified logger.
        
        Args:
            logger_name (Optional[str], optional): Name of the logger to attach the handler to.
                                                If None, attaches to the root logger.
            formatter (Optional[logging.Formatter], optional): Formatter to use for log messages.
                                                             
        Returns:
            StyledLoggingHandler: The created handler instance.
        """
        logger = logging.getLogger(logger_name) if logger_name else logging.getLogger()
        
        # Create styled handler with specified formatter
        handler = StyledLoggingHandler(formatter=formatter)
        
        # Add the handler to the logger
        logger.addHandler(handler)
        
        return handler


class PromptToolkitLoggerAdapter:
    """Adapter that connects the LoggingManager to prompt_toolkit styled output."""
    
    def __init__(self, logger_instance):
        """Initialize the adapter with a logger instance.
        
        Args:
            logger_instance: The logger instance to adapt (SessionDebugLog in most cases)
        """
        self.logger = logger_instance
        self._styles = {
            'debug': 'fg:cyan',
            'info': 'fg:white',
            'warning': 'fg:yellow',
            'error': 'fg:red',
            'critical': 'bg:red fg:white bold'
        }
    
    def debug(self, message: str) -> None:
        """Log a debug message with styling.
        
        Args:
            message (str): The message to log.
        """
        self.logger.debug(message)
    
    def info(self, message: str) -> None:
        """Log an info message with styling.
        
        Args:
            message (str): The message to log.
        """
        self.logger.info(message)
    
    def warning(self, message: str) -> None:
        """Log a warning message with styling.
        
        Args:
            message (str): The message to log.
        """
        self.logger.warning(message)
    
    def error(self, message: str) -> None:
        """Log an error message with styling.
        
        Args:
            message (str): The message to log.
        """
        self.logger.error(message)
    
    def critical(self, message: str) -> None:
        """Log a critical message with styling.
        
        Args:
            message (str): The message to log.
        """
        self.logger.critical(message)
    
    @staticmethod
    def setup_logging(session_name: str, formatter: Optional[logging.Formatter] = None):
        """Set up a complete logging system with file logging and styled console output.
        
        This is a centralized method that sets up both the file logging and the styled
        console output with a single call.
        
        Args:
            session_name (str): Name for the log session
            formatter (Optional[logging.Formatter], optional): Custom formatter to use.
                If None, uses a standard formatter.
                
        Returns:
            tuple: A tuple containing (styled_handler, logger_adapter, raw_logger)
        """
        from hatchling.core.logging.logging_manager import logging_manager
        
        # Use provided formatter or create a standard one
        log_formatter = formatter or logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        
        # Set up the root console handler with styling
        styled_handler = StyledLoggingHandler.setup_console_handler(formatter=log_formatter)
        
        # Get a session logger from the logging manager
        raw_logger = logging_manager.get_session(session_name, formatter=log_formatter)
        
        # Create and return an adapter for the logger
        logger_adapter = PromptToolkitLoggerAdapter(raw_logger)
        
        return styled_handler, logger_adapter, raw_logger
