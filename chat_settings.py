class ChatSettings:
    """Manages chat configuration settings."""
    
    def __init__(self, ollama_api_url: str = "http://localhost:11434/api",
                 default_model :str = "mistral-small3.1",
                 mcp_server_urls: list = []):
        self.ollama_api_url = ollama_api_url
        self.default_model = default_model
        self.mcp_server_urls = mcp_server_urls