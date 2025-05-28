"""Logging management for the Hatchling application.

This module provides centralized logging configuration, management of logging sessions,
and consistent logging across the application.
"""

import logging
import io
import os
from pathlib import Path
from typing import Dict, Optional, List, Union
from logging.handlers import RotatingFileHandler
from hatchling.core.logging.session_debug_log import SessionDebugLog


class LoggingManager:
    """Singleton manager for handling all logging sessions in the application."""
    
    _instance = None
    
    def __new__(cls):
        """Ensure singleton pattern implementation.
        
        Returns:
            LoggingManager: The singleton instance of LoggingManager.
        """
        if cls._instance is None:
            cls._instance = super(LoggingManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        """Initialize the logging manager if not already initialized."""
        if self._initialized:
            return
            
        # Initialize only once
        self._initialized = True
        
        # Load log settings from environment variables
        self._load_log_settings()
        
        # Default formatter for root logger
        self.default_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        
        # Store all session loggers by name
        self.sessions: Dict[str, SessionDebugLog] = {}
        
        # Configure root logger for CLI output
        self.configure_root_logger()
    
    def _load_log_settings(self):
        """Load logging settings from environment variables."""
        # Get log level from environment (default to INFO)
        log_level_str = os.environ.get('LOG_LEVEL', 'INFO').upper()
        log_levels = {
            'DEBUG': logging.DEBUG,
            'INFO': logging.INFO,
            'WARNING': logging.WARNING,
            'ERROR': logging.ERROR,
            'CRITICAL': logging.CRITICAL
        }
        self.log_level = log_levels.get(log_level_str, logging.INFO)
        
        # Get log file path from environment
        log_dir = Path(os.environ.get('LOG_DIR', Path.home() / '.hatch' / 'logs'))
        log_dir.mkdir(exist_ok=True, parents=True)
        self.log_file = log_dir / 'hatchling.log'

    def configure_root_logger(self):
        """Configure the root logger with CLI handler and file handler if configured."""
        # Get the root logger
        root_logger = logging.getLogger()
        
        # Remove existing handlers to avoid duplicates if reconfigured
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)
            
        # Create console handler
        console = logging.StreamHandler()
        console.setFormatter(self.default_formatter)
        root_logger.addHandler(console)
        
        # Add file handler if log file is specified
        if self.log_file:
            try:
                # Use rotating file handler to prevent huge log files
                file_handler = RotatingFileHandler(
                    str(self.log_file), 
                    maxBytes=10*1024*1024,  # 10 MB
                    backupCount=5
                )
                file_handler.setFormatter(self.default_formatter)
                root_logger.addHandler(file_handler)
                
                logging.info(f"Logging to file: {self.log_file}")
            except Exception as e:
                logging.error(f"Failed to set up file logging: {str(e)}")
        
        self.set_log_level(self.log_level)
    
    def set_log_level(self, level: int) -> None:
        """Set the log level for all loggers and handlers.
        
        Args:
            level (int): The log level (e.g., logging.DEBUG, logging.INFO).
        """
        self.log_level = level
        
        # Set level for all existing loggers
        for logger_name in logging.root.manager.loggerDict:
            logger = logging.getLogger(logger_name)
            logger.setLevel(self.log_level)
            
            # Also update handlers
            for handler in logger.handlers:
                handler.setLevel(self.log_level)

    def get_session(self, name: str, 
                   formatter: Optional[logging.Formatter] = None) -> SessionDebugLog:
        """Get a session debug log by name, creating it if it doesn't exist.
        
        Args:
            name (str): The name of the session debug log.
            formatter (logging.Formatter, optional): Custom formatter for this session. Defaults to None.
            
        Returns:
            SessionDebugLog: The session debug log instance.
        """
        if name not in self.sessions:
            # Create a new session if it doesn't exist
            if formatter is None:
                self.sessions[name] = SessionDebugLog(name, self.default_formatter)
            else:
                self.sessions[name] = SessionDebugLog(name, formatter)
                
            # Keep session loggers non-propagating to avoid duplicate logs
            # Their propagate flag is already set to False in the SessionDebugLog class
                
        return self.sessions[name]
    
    def get_all_sessions(self) -> List[str]:
        """Get a list of all session names.
        
        Returns:
            List[str]: List of session names.
        """
        return list(self.sessions.keys())
    
    def clear_session(self, name: str) -> bool:
        """Clear a specific session log.
        
        Args:
            name (str): The name of the session to clear.
            
        Returns:
            bool: True if the session was cleared, False if it doesn't exist.
        """
        if name in self.sessions:
            self.sessions[name].clear_logs()
            return True
        return False
    
    def clear_all_sessions(self) -> None:
        """Clear all session logs."""
        for session in self.sessions.values():
            session.clear_logs()
    
    def create_console_handler(self, formatter: Optional[logging.Formatter] = None) -> logging.StreamHandler:
        """Create a console handler with the current CLI log level.
        
        Args:
            formatter (logging.Formatter, optional): Formatter to use, falls back to default formatter. Defaults to None.
            
        Returns:
            logging.StreamHandler: A configured console handler.
        """
        console = logging.StreamHandler()
        console.setLevel(self.log_level)
        console.setFormatter(formatter or self.default_formatter)
        return console

# Create a global instance that can be imported elsewhere
logging_manager = LoggingManager()