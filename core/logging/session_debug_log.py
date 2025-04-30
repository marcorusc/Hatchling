import logging
import io
from datetime import datetime
from typing import Optional


class SessionDebugLog:
    """Class for managing session-specific logging with in-memory storage for viewing logs during a chat session."""
    
    def __init__(self, name: Optional[str] = "SessionDebugLog", formatter: Optional[logging.Formatter] = None):
        """Initialize a session-specific logger.
        
        Args:
            name (str, optional): Name of the logger. Defaults to "SessionDebugLog".
            formatter (logging.Formatter, optional): Custom formatter for log messages. 
        """
        # Create a unique logger for this session
        self.logger = logging.getLogger(name)
        
        # Keep propagate=True so logs go to root logger
        # which handles console output properly with just one instance
        self.logger.propagate = True
        
        # Create a StringIO buffer just for in-memory storage
        # but don't add a second handler that would cause duplicate console output
        self.log_buffer = io.StringIO()
        
        # Store the session name
        self.name = name
        
        # Keep track of log entries for easy access by index
        self.log_entries = []
    
    def debug(self, message: str):
        """Log a debug message.
        
        Args:
            message (str): The message to log.
        """
        self.logger.debug(message)
        self.log_entries.append((datetime.now().strftime("%Y-%m-%d %H:%M:%S:%f"), "DEBUG", message))
    
    def info(self, message: str):
        """Log an info message.
        
        Args:
            message (str): The message to log.
        """
        self.logger.info(message)
        self.log_entries.append((datetime.now().strftime("%Y-%m-%d %H:%M:%S:%f"), "INFO", message))
    
    def warning(self, message: str):
        """Log a warning message.
        
        Args:
            message (str): The message to log.
        """
        self.logger.warning(message)
        self.log_entries.append((datetime.now().strftime("%Y-%m-%d %H:%M:%S:%f"), "WARNING", message))
    
    def error(self, message: str):
        """Log an error message.
        
        Args:
            message (str): The message to log.
        """
        self.logger.error(message)
        self.log_entries.append((datetime.now().strftime("%Y-%m-%d %H:%M:%S:%f"), "ERROR", message))
    
    def critical(self, message: str):
        """Log a critical message.
        
        Args:
            message (str): The message to log.
        """
        self.logger.critical(message)
        self.log_entries.append((datetime.now().strftime("%Y-%m-%d %H:%M:%S:%f"), "CRITICAL", message))
    
    def get_logs(self, last_n: Optional[int] = None) -> str:
        """Get formatted log entries, optionally limited to the last N entries.
        
        Args:
            last_n (int, optional): If provided, only return the last N log entries.
            
        Returns:
            str: A formatted string with the log entries.
        """
        if not self.log_entries:
            return "No logs recorded in this session."
        
        entries = self.log_entries
        if last_n is not None and last_n > 0:
            entries = self.log_entries[-last_n:]
        
        result = f"=== SESSION DEBUG LOG: {self.name} ===\n"
        for time, level, message in entries:
            result += f"[{time}] {level}: {message}\n"
        result += "======================\n"
        return result
    
    def clear_logs(self):
        """Clear all logs."""
        self.log_entries = []
        # Reset the string buffer
        self.log_buffer.truncate(0)
        self.log_buffer.seek(0)