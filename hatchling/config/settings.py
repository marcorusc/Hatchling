import os
import logging
from pathlib import Path
from hatchling.core.logging.logging_manager import logging_manager

class ChatSettings:
    """Manages chat configuration settings."""
    
    def __init__(self, 
                 ollama_api_url: str = os.environ.get("OLLAMA_HOST_API", "http://localhost:11434/api"),
                 ollama_model: str = os.environ.get("OLLAMA_MODEL", "mistral-small3.1"),
                 hatch_envs_dir: str = os.environ.get("HATCH_ENVS_DIR", Path.home() / ".hatch" / "envs"),
                 max_tool_call_iteration: int = 5,
                 max_working_time: float = 30.0):
        """Initialize chat settings with configurable parameters.
        
        Args:
            ollama_api_url (str, optional): URL for the Ollama API. Defaults to environment variable or localhost.
            ollama_model (str, optional): Ollama LLM to use. Defaults to environment variable or mistral-small3.1.
            hatch_envs_dir (str, optional): Directory for Hatch environments. Defaults to environment variable or ~/.hatch/envs.
            max_tool_call_iteration (int, optional): Maximum number of tool call iterations. Defaults to 5.
            max_working_time (float, optional): Maximum time in seconds for tool operations. Defaults to 30.0.
        """
        self.logger = logging_manager.get_session("ChatSettings",
                                                  logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))


        self.ollama_api_url = ollama_api_url
        self.ollama_model = ollama_model

        # If hatch_envs_dir is:
        # - an absolute path, it is used as is
        # - a relative path, it is resolved against the user's home directory
        if os.path.isabs(hatch_envs_dir):
            self.hatch_envs_dir = hatch_envs_dir
        else:
            self.hatch_envs_dir = Path.home() / hatch_envs_dir
        
        # New settings for tool calling control
        self.max_tool_call_iteration = max_tool_call_iteration  # Maximum number of tool call iterations
        self.max_working_time = max_working_time  # Maximum time in seconds for tool operations

        self.logger.info(f"ChatSettings initialized with model: {self.ollama_model}, API URL: {self.ollama_api_url}")
        self.logger.info(f"Max tool call iterations: {self.max_tool_call_iteration}, Max working time: {self.max_working_time} seconds")
        self.logger.info(f"Hatch environments directory: {self.hatch_envs_dir}")