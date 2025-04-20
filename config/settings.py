import os

class ChatSettings:
    """Manages chat configuration settings."""
    
    def __init__(self, 
                 ollama_api_url: str = os.environ.get("OLLAMA_API_URL", "http://localhost:11434/api"),
                 default_model: str = os.environ.get("DEFAULT_MODEL", "mistral-small3.1"),
                 mcp_server_urls: list = None,
                 max_tool_call_iteration: int = 5,
                 max_working_time: float = 30.0):
        self.ollama_api_url = ollama_api_url
        self.default_model = default_model
        self.mcp_server_urls = mcp_server_urls or []
        
        # New settings for tool calling control
        self.max_tool_call_iteration = max_tool_call_iteration  # Maximum number of tool call iterations
        self.max_working_time = max_working_time  # Maximum time in seconds for tool operations