import os
import asyncio
import logging
from typing import Dict, Any, Optional
import uuid
from contextlib import AsyncExitStack

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from core.logging.logging_manager import logging_manager


class MCPClient:
    """Client for MCP servers that manages connections and tool execution."""
    
    def __init__(self):
        """Initialize the MCP client."""
        self.client_id = str(uuid.uuid4())
        self.session: Optional[ClientSession] = None
        self.exit_stack = AsyncExitStack()
        self.connected = False
        self.tools = {}
        self.server_path = None
        self.read = None
        self.write = None
        
        # Add connection monitoring
        self._heartbeat_task = None
        self._reconnection_attempts = 0
        self.MAX_RECONNECTION_ATTEMPTS = 3
        self.RECONNECTION_DELAY = 2  # seconds
        
        # Get a debug log session from the LoggingManager
        self.debug_log = logging_manager.get_session(self.__class__.__name__,
                                  formatter=logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    
    async def connect(self, server_path: str) -> bool:
        """Connect to an MCP server via stdio.
        
        Args:
            server_path (str): Path to the server script (.py file).
            
        Returns:
            bool: True if connection was successful, False otherwise.
        """
        try:
            self.server_path = server_path
            
            # Create server parameters for stdio connection
            server_params = StdioServerParameters(
                command="python",  # Use Python to execute the script
                args=[server_path],  # Path to the server script
                env=os.environ.copy(),  # Use default environment variables
            )
            
            self.debug_log.info(f"Connecting to MCP server: {server_path}")
            
            # Create the stdio client connection with a simpler approach
            try:
                # Use the stdlib timeout instead of anyio for better compatibility
                stdio_transport = await asyncio.wait_for(
                    self.exit_stack.enter_async_context(stdio_client(server_params)),
                    timeout=10  # 10 second timeout
                )
                self.read, self.write = stdio_transport
            except asyncio.TimeoutError:
                self.debug_log.error(f"Connection to MCP server timed out: {server_path}")
                return False
                
            # Create the client session
            self.session = await self.exit_stack.enter_async_context(
                ClientSession(self.read, self.write)
            )
            
            # Initialize the session
            await self.session.initialize()
            self.connected = True
            
            # List available tools
            response = await self.session.list_tools()
            tools = response.tools
            
            # Store tools in a dictionary for easy access
            for tool in tools:
                self.tools[tool.name] = tool
            
            self.debug_log.info(f"Connected to MCP server: {server_path}")
            self.debug_log.info(f"Discovered {len(self.tools)} tools: {', '.join(self.tools.keys())}")

            # List available citations
            citations = await self.get_citations()
            self.debug_log.info("Tool Origin Citation: " + citations["origin"])
            self.debug_log.info("MCP Implementation Citation: " + citations["mcp"])
            
            # Start heartbeat task to monitor connection
            self._start_heartbeat()
            
            return True
            
        except asyncio.CancelledError:
            self.debug_log.warning("Connection attempt cancelled")
            raise
        except Exception as e:
            self.debug_log.error(f"Failed to connect to MCP server at {server_path}: {str(e)}")
            self.connected = False
            return False
    
    def _start_heartbeat(self):
        """Start a background task to periodically check connection health."""
        if self._heartbeat_task is None:
            self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
    
    async def _heartbeat_loop(self):
        """Periodically check if the connection is still alive."""
        try:
            while self.connected:
                await asyncio.sleep(30)  # Check every 30 seconds
                if not self.connected:
                    break
                    
                try:
                    # Try a lightweight operation to check connection
                    await self.session.list_tools()
                    self.debug_log.debug("Connection heartbeat: OK")
                except Exception as e:
                    self.debug_log.warning(f"Connection heartbeat failed: {e}")
                    # Try to reconnect
                    if self._reconnection_attempts < self.MAX_RECONNECTION_ATTEMPTS:
                        self._reconnection_attempts += 1
                        self.debug_log.info(f"Attempting to reconnect ({self._reconnection_attempts}/{self.MAX_RECONNECTION_ATTEMPTS})")
                        await asyncio.sleep(self.RECONNECTION_DELAY)
                        
                        # Close existing session before reconnecting
                        await self._cleanup_connection()
                        
                        # Reconnect
                        success = await self.connect(self.server_path)
                        if success:
                            self._reconnection_attempts = 0
                            self.debug_log.info("Successfully reconnected")
                        else:
                            self.debug_log.error("Failed to reconnect")
                    else:
                        self.debug_log.error(f"Maximum reconnection attempts reached ({self.MAX_RECONNECTION_ATTEMPTS})")
                        self.connected = False
                        break
                    
        except asyncio.CancelledError:
            self.debug_log.debug("Heartbeat task cancelled")
        except Exception as e:
            self.debug_log.error(f"Error in heartbeat task: {e}")
        finally:
            self.debug_log.debug("Heartbeat task stopped")
            self._heartbeat_task = None
    
    async def _cleanup_connection(self):
        """Clean up the connection resources."""
        if self.session:
            # Session will be cleaned by exit_stack later
            self.session = None
            
        self.read = None
        self.write = None
            
    async def disconnect(self):
        """Disconnect from the MCP server and clean up resources."""
        if self.connected:
            try:
                self.debug_log.info(f"Disconnecting from MCP server: {self.server_path}")
                
                # Cancel heartbeat task
                if self._heartbeat_task:
                    self._heartbeat_task.cancel()
                    try:
                        await self._heartbeat_task
                    except asyncio.CancelledError:
                        pass
                    finally:
                        self._heartbeat_task = None
                
                # Close resources individually
                try:
                    # Close the exit stack with a timeout
                    await asyncio.wait_for(self.exit_stack.aclose(), timeout=5)
                except asyncio.TimeoutError:
                    self.debug_log.warning("Timeout while closing resources")
                except Exception as e:
                    self.debug_log.error(f"Error closing resources: {e}")
                    
                self.debug_log.info(f"Disconnected from MCP server: {self.server_path}")
                
            except Exception as e:
                self.debug_log.error(f"Error disconnecting from MCP server: {str(e)}")
            finally:
                self.connected = False
                self.tools = {}
                self.session = None
                self.read = None
                self.write = None
                self._reconnection_attempts = 0
    
    async def get_citations(self) -> Dict[str, str]:
        """Get citations from the MCP server.
        
        Returns:
            Dict[str, str]: Dictionary with origin and MCP citations.
        """
        if not self.connected or not self.session:
            raise ConnectionError("Not connected to MCP server")
            
        citations = {
            "server_name": "None",
            "origin": "Citation not available",
            "mcp": "Citation not available"
        }

        try:
            # Extract server name from the path server uri
            try:
                server_name_uri = f"name://{self.server_path[1:]}"
                server_name_response = await self.session.read_resource(uri=server_name_uri)
                if server_name_response and server_name_response.contents:
                    citations["server_name"] = server_name_response.contents[0].text
                    self.debug_log.debug(f"Retrieved server name from {server_name_uri}: {citations["server_name"]}")
            except Exception as e:
                self.debug_log.error(f"Failed to get server name: {e}")
                
            # Try to read origin citation
            try:
                origin_uri = f"citation://origin/{citations["server_name"]}"
                origin_response = await self.session.read_resource(uri=origin_uri)
                if origin_response and origin_response.contents:
                    citations["origin"] = origin_response.contents[0].text
                    self.debug_log.debug(f"Retrieved origin citation from {origin_uri}")
            except Exception as e:
                self.debug_log.error(f"Failed to get origin citation: {e}")
            
            # Try to read MCP citation
            try:
                mcp_uri = f"citation://mcp/{citations["server_name"]}"
                mcp_response = await self.session.read_resource(uri=mcp_uri)
                if mcp_response and mcp_response.contents:
                    citations["mcp"] = mcp_response.contents[0].text
                    self.debug_log.debug(f"Retrieved MCP citation from {mcp_uri}")
            except Exception as e:
                self.debug_log.error(f"Failed to get MCP citation: {e}")
                
        except Exception as e:
            self.debug_log.error(f"Error retrieving citations: {e}")
            
        return citations
    
    async def execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """Execute an MCP tool by name with given arguments.
        
        Args:
            tool_name (str): Name of the tool to execute.
            arguments (Dict[str, Any]): Arguments to pass to the tool.
            
        Returns:
            Any: Result of the tool execution.
            
        Raises:
            ConnectionError: If not connected to MCP server.
            ValueError: If the tool is not found.
            TimeoutError: If the tool execution times out.
            Exception: For any other errors during execution.
        """
        if not self.connected or not self.session:
            raise ConnectionError("Not connected to MCP server")
            
        if tool_name not in self.tools:
            raise ValueError(f"Tool '{tool_name}' not found")
        
        try:            
            # Execute the tool with timeout
            try:
                # Use asyncio timeout instead of anyio
                result = await asyncio.wait_for(
                    self.session.call_tool(name=tool_name, arguments=arguments),
                    timeout=30  # 30 second timeout
                )
                
                # Extract the result value from the response object if needed
                if hasattr(result, 'result'):
                    return result.result
                else:
                    return result
                    
            except asyncio.TimeoutError:
                self.debug_log.error(f"Tool execution timed out: {tool_name}")
                raise TimeoutError(f"Execution of tool {tool_name} timed out after 30 seconds")
                
        except Exception as e:
            self.debug_log.error(f"Error executing tool {tool_name}: {str(e)}")
            raise