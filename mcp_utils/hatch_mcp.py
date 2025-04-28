import inspect
import logging
from typing import Optional
from mcp.server.fastmcp import FastMCP
from core.logging.logging_manager import logging_manager

class HatchMCP():
    """Base wrapper for MCP servers with citation capabilities."""
    
    def __init__(self, 
                 name: str, 
                 origin_citation: Optional[str] = None, 
                 mcp_citation: Optional[str] = None):
        """Initialize the HatchMCP wrapper.
        
        Args:
            name: The name of the MCP server.
            origin_citation: Citation information for the original tools/algorithms.
            mcp_citation: Citation information for the MCP server implementation.
        """
        # Initialize the logger
        self.logger = logging_manager.get_session(
            f"HatchMCP_{name}",
            formatter=logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        )

        # Create the underlying FastMCP server
        self.server = FastMCP(name)
        self.name = name
        self.module_name = "" #the file name of the calling module
        
        # Store citation information
        self._origin_citation = origin_citation or "No origin citation provided."
        self._mcp_citation = mcp_citation or "No MCP citation provided."

        # Determine the filename of the calling module for citation URIs
        try:
            frame = inspect.stack()[1]
            module = inspect.getmodule(frame[0])
            if module and module.__file__:
                self.module_name = module.__file__[1:]
                self.logger.info(f"Module name for citation URIs: {self.module_name}")
        except Exception:
            raise RuntimeError("Unable to determine module name for citation URIs.")
        
        # Register a resource to discover the server name
        # This allows clients to query server_name://hatch to get the correct name for citation URIs
        @self.server.resource(
            uri=f"name://{self.module_name}",
            name="Server Name",
            description="The name of this MCP server for use in other resource URIs",
            mime_type="text/plain"
        )
        def get_server_name() -> str:
            """Return the name of this MCP server."""
            return self.name

        # Register citation resources using standard URIs and the resource decorator
        @self.server.resource(
            uri=f"citation://origin/{name}",
            name="Origin Citation",
            description="Citation information for the original tools/algorithms",
            mime_type="text/plain"
        )
        def get_origin_citation() -> str:
            """Return citation information for the wrapped tools."""
            return self._origin_citation
        
        @self.server.resource(
            uri=f"citation://mcp/{name}",
            name="MCP Implementation Citation",
            description="Citation information for the MCP server implementation",
            mime_type="text/plain"
        )
        def get_mcp_citation() -> str:
            """Return citation information for the MCP server developers."""
            return self._mcp_citation
