import asyncio
import logging
import os
import subprocess
from typing import Dict, List, Any, Optional

from hatchling.mcp_utils.client import MCPClient
from hatchling.mcp_utils.ollama_adapter import OllamaMCPAdapter
from hatchling.core.logging.logging_manager import logging_manager

class MCPManager:
    """Centralized manager for everything MCP-related: servers, clients, and adapters."""
    
    _instance = None
    
    def __new__(cls):
        """Ensure singleton pattern implementation."""
        if cls._instance is None:
            cls._instance = super(MCPManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        """Initialize the MCP manager if not already initialized."""
        if self._initialized:
            return
            
        # Initialize only once
        self._initialized = True
        
        # Connection tracking
        self.mcp_clients: Dict[str, MCPClient] = {}
        self.server_processes: Dict[str, subprocess.Popen] = {}
        self._connection_lock = asyncio.Lock()
        self.connected = False
        
        # Tool tracking
        self._tool_client_map = {}  # Map of tool names to clients that provide them

        # Hatch server usage
        self._used_servers_in_session = set()
        
        # Adapter for Ollama format
        self._adapter = None
        
        # Get a debug log session
        self.debug_log = logging_manager.get_session(self.__class__.__name__,
                                  formatter=logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    
    def validate_server_paths(self, server_paths: List[str]) -> List[str]:
        """Validate server paths and return the list of valid absolute paths.
        
        Args:
            server_paths (List[str]): List of server paths to validate.
            
        Returns:
            List[str]: List of valid absolute paths.
        """
        valid_paths = []
        for path in server_paths:
            # Convert to absolute path if relative
            abs_path = os.path.abspath(path)
            
            # Check if file exists
            if not os.path.isfile(abs_path):
                self.debug_log.error(f"MCP server script not found: {abs_path}")
                continue
                
            valid_paths.append(abs_path)
            
        return valid_paths
    
    async def start_server(self, server_path: str) -> Optional[subprocess.Popen]:
        """Start an MCP server in a subprocess.
        
        Args:
            server_path (str): Path to the MCP server script.
            
        Returns:
            Optional[subprocess.Popen]: Process object if server started successfully, None otherwise.
        """
        if not os.path.isfile(server_path):
            self.debug_log.error(f"MCP server script not found: {server_path}")
            return None
        
        # Get the directory containing the script to use as the working directory
        working_dir = os.path.dirname(os.path.abspath(server_path))
        server_filename = os.path.basename(server_path)
        
        try:
            process = subprocess.Popen(
                ['python', server_filename],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                cwd=working_dir  # Set the working directory
            )
            
            self.debug_log.info(f"MCP server started: {server_path}")
            
            # Store the process
            self.server_processes[server_path] = process
            
            # Give the MCP server a moment to start
            await asyncio.sleep(2)
            
            return process
        except Exception as e:
            self.debug_log.error(f"Error starting MCP server: {str(e)}")
            return None
    
    async def initialize(self, server_paths: List[str], auto_start: bool = False) -> bool:
        """Initialize the MCP system with the given server paths.
        
        Args:
            server_paths (List[str]): List of paths to MCP server scripts.
            auto_start (bool, optional): Whether to start servers if they aren't running. Defaults to False.
            
        Returns:
            bool: True if initialization was successful.
        """
        connected = await self.connect_to_servers(server_paths, auto_start)
        
        if connected and not self._adapter:            
            self._adapter = OllamaMCPAdapter()
            await self._adapter.build_schema_cache(self.get_tools_by_name())
            
        return connected

    async def connect_to_servers(self, server_paths: List[str], auto_start: bool = False) -> bool:
        """Connect to all configured MCP servers.
        
        Args:
            server_paths (List[str]): List of paths to MCP server scripts.
            auto_start (bool, optional): Whether to start servers if they aren't running. Defaults to False.

        Returns:
            bool: True if connected to at least one server successfully.
        """
        if self.connected and self.mcp_clients:
            return True
            
        async with self._connection_lock:
            # Validate server paths
            valid_paths = self.validate_server_paths(server_paths)
            if not valid_paths:
                self.debug_log.error("No valid MCP server scripts found")
                return False
            
            # Connect to each valid server path
            for path in valid_paths:
                # Start the server if requested
                if auto_start and path not in self.server_processes:
                    await self.start_server(path)
                
                # Connect to the server
                client = MCPClient()
                is_connected = await client.connect(path)
                if is_connected:
                    self.mcp_clients[path] = client
                    
                    # Cache tool mappings
                    for tool_name in client.tools:
                        self._tool_client_map[tool_name] = client
            
            # Update connection status
            self.connected = len(self.mcp_clients) > 0
            
            if self.connected:
                # Log the available tools across all clients
                total_tools = sum(len(client.tools) for client in self.mcp_clients.values())
                self.debug_log.info(f"Connected to {len(self.mcp_clients)} MCP servers with {total_tools} total tools")
                
                # Update adapter schema cache if adapter exists
                if self._adapter:
                    await self._adapter.build_schema_cache(self.get_tools_by_name())
            else:
                self.debug_log.warning("Failed to connect to any MCP server")
                
            return self.connected
    
    async def disconnect_all(self) -> None:
        """Disconnect from all MCP servers."""
        if not self.connected:
            return
            
        async with self._connection_lock:
            # Disconnect each client individually with error handling
            for path, client in list(self.mcp_clients.items()):
                try:
                    await client.disconnect()
                except Exception as e:
                    self.debug_log.error(f"Error disconnecting client for {path}: {e}")
                
            # Clear all client tracking
            self.mcp_clients = {}
            self._tool_client_map = {}
            self.connected = False
            
            self.debug_log.info("Disconnected from all MCP servers")
    
    def get_tools_by_name(self) -> Dict[str, Any]:
        """Get a dictionary of tool name to tool object mappings.
        
        Returns:
            Dict[str, Any]: Dictionary mapping tool names to tool objects.
        """
        tools = {}
        for client in self.mcp_clients.values():
            tools.update(client.tools)
        return tools
    
    def get_ollama_tools(self) -> List[Dict[str, Any]]:
        """Get all available tools in Ollama format.
        
        Returns:
            List[Dict[str, Any]]: List of tools in Ollama format.
        """
        if not self.connected or not self._adapter:
            return []
        return self._adapter.get_all_tools()
    
    async def execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """Execute a tool by name with the given arguments.
        
        Args:
            tool_name (str): Name of the tool to execute.
            arguments (Dict[str, Any]): Arguments to pass to the tool.
            
        Returns:
            Any: Result of the tool execution.
            
        Raises:
            ConnectionError: If not connected to any MCP server.
            ValueError: If the tool is not found in any connected MCP server.
        """
        if not self.connected or not self.mcp_clients:
            raise ConnectionError("Not connected to any MCP server")
            
        if tool_name not in self._tool_client_map:
            raise ValueError(f"Tool '{tool_name}' not found in any connected MCP server")
            
        client = self._tool_client_map[tool_name]
        self._used_servers_in_session.add(client.server_path)
        
        try:
            return await client.execute_tool(tool_name, arguments)
        except ConnectionError:
            # Handle client disconnection
            for path, c in list(self.mcp_clients.items()):
                if c == client:
                    # Remove the disconnected client
                    del self.mcp_clients[path]
                    # Clean up tool mappings
                    self._tool_client_map = {
                        name: c for name, c in self._tool_client_map.items() 
                        if c != client
                    }
                    break
            
            # Re-raise the exception
            raise
    
    async def get_citations_for_session(self) -> Dict[str, Dict[str, str]]:
        """Get citations for all servers used in the current session.

        Returns:
            response (Dict[str, Dict[str, str]]]: Dictionary of citations for each server.
        """
        citations = {}
        
        for path in self._used_servers_in_session:
            if path in self.mcp_clients:
                client = self.mcp_clients[path]
                try:
                    server_citations = await client.get_citations()
                    citations[path] = server_citations
                except Exception as e:
                    self.debug_log.error(f"Error getting citations for {path}: {e}")
        
        return citations

    def reset_session_tracking(self):
        """Reset the tracking of which servers were used."""
        self._used_servers_in_session.clear()
    
    async def process_tool_calls(self, tool_calls: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Process tool calls in Ollama format.
        
        Args:
            tool_calls (List[Dict[str, Any]]): List of tool calls in Ollama format.
            
        Returns:
            List[Dict[str, Any]]: List of tool responses in Ollama format.
            
        Raises:
            ConnectionError: If MCP system is not properly initialized.
        """
        if not self.connected or not self._adapter:
            raise ConnectionError("MCP system not properly initialized")
        return await self._adapter.process_tool_calls(tool_calls, self)
    
    def stop_all_servers(self) -> None:
        """Stop all running MCP server processes."""
        for path, process in list(self.server_processes.items()):
            if process.poll() is None:  # Process is still running
                try:
                    process.terminate()
                    self.debug_log.info(f"Terminated MCP server: {path}")
                except Exception as e:
                    self.debug_log.error(f"Error terminating MCP server {path}: {e}")
            
            # Remove from tracking
            del self.server_processes[path]

# Create a singleton instance
mcp_manager = MCPManager()