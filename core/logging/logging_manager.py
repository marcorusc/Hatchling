import logging
import io
from typing import Dict, Optional, List, Union
from core.logging.session_debug_log import SessionDebugLog


class LoggingManager:
    """Singleton manager for handling all logging sessions in the application."""
    
    _instance = None
    
    def __new__(cls):
        """Ensure singleton pattern implementation."""
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
        
        # Default CLI log level (for stdout)
        self.cli_log_level = logging.INFO
        
        # Default formatter for root logger
        self.default_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        
        # Store all session loggers by name
        self.sessions: Dict[str, SessionDebugLog] = {}
        
        # Configure root logger for CLI output
        self.configure_root_logger()
    
    def configure_root_logger(self):
        """Configure the root logger with CLI handler."""
        # Get the root logger
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.DEBUG)  # Capture everything at root level
        
        # Remove existing handlers to avoid duplicates if reconfigured
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)
            
        # Create console handler
        console = logging.StreamHandler()
        console.setLevel(self.cli_log_level)
        console.setFormatter(self.default_formatter)
        root_logger.addHandler(console)
    
    def set_cli_log_level(self, level: int) -> None:
        """Set the log level for CLI output.
        
        Args:
            level (int): The log level (e.g., logging.DEBUG, logging.INFO).
        """
        self.cli_log_level = level
        
        # Update console handlers on root logger
        root_logger = logging.getLogger()
        for handler in root_logger.handlers:
            if isinstance(handler, logging.StreamHandler) and not isinstance(handler.stream, io.StringIO):
                handler.setLevel(level)
    
    def get_session(self, name: str, 
                   formatter: Optional[logging.Formatter] = None) -> SessionDebugLog:
        """Get a session debug log by name, creating it if it doesn't exist.
        
        Args:
            name (str): The name of the session debug log.
            formatter (logging.Formatter, optional): Custom formatter for this session.
            
        Returns:
            SessionDebugLog: The session debug log.
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
            formatter (Optional[logging.Formatter], optional): Formatter to use, falls back to default formatter.
            
        Returns:
            logging.StreamHandler: A configured console handler.
        """
        console = logging.StreamHandler()
        console.setLevel(self.cli_log_level)
        console.setFormatter(formatter or self.default_formatter)
        return console

# Create a global instance that can be imported elsewhere
logging_manager = LoggingManager()