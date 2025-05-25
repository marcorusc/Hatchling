import os
import logging
from hatchling.core.logging.logging_manager import logging_manager

logger = logging_manager.get_session("Chat Settings", logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))

class ChatSettings:
    """Manages chat configuration settings."""
    
    def __init__(self, 
                 ollama_api_url: str = os.environ.get("OLLAMA_HOST_API", "http://localhost:11434/api"),
                 default_model: str = os.environ.get("DEFAULT_MODEL", "mistral-small3.1"),
                 mcp_server_urls: list = None,
                 max_tool_call_iteration: int = 5,
                 max_working_time: float = 30.0):
        """Initialize chat settings with configurable parameters.
        
        Args:
            ollama_api_url (str, optional): URL for the Ollama API. Defaults to environment variable or localhost.
            default_model (str, optional): Default LLM model to use. Defaults to environment variable or mistral-small3.1.
            mcp_server_urls (list, optional): List of MCP server URLs. Defaults to empty list.
            max_tool_call_iteration (int, optional): Maximum number of tool call iterations. Defaults to 5.
            max_working_time (float, optional): Maximum time in seconds for tool operations. Defaults to 30.0.
        """
        self.ollama_api_url = ollama_api_url
        self.default_model = default_model
        self.mcp_server_urls = mcp_server_urls or []
        
        # New settings for tool calling control
        self.max_tool_call_iteration = max_tool_call_iteration  # Maximum number of tool call iterations
        self.max_working_time = max_working_time  # Maximum time in seconds for tool operations

        logger.info(f"ChatSettings initialized with model: {self.default_model}, API URL: {self.ollama_api_url}")
        logger.info(f"Max tool call iterations: {self.max_tool_call_iteration}, Max working time: {self.max_working_time} seconds")
        logger.info(f"MCP server URLs: {self.mcp_server_urls}")