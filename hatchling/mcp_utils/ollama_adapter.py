import json
import asyncio
import logging
from typing import Dict, List, Any
from hatchling.core.logging.logging_manager import logging_manager

class OllamaMCPAdapter:
    """Adapter to integrate Ollama's tool calling format with MCP tools."""
    
    def __init__(self):
        """Initialize the adapter."""
        # Schema caching for better performance and parameter name consistency
        self._mcp_to_ollama_schemas = {}  # Cache for MCP schemas converted to Ollama format
        
        # Get a debug log session from the logging_manager
        self.logger = logging_manager.get_session(self.__class__.__name__,
                                                    formatter=logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    
    async def build_schema_cache(self, mcp_tools: Dict[str, Any]) -> None:
        """Build cache of Ollama tool schemas based on the schemas of MCP tools.
        
        Args:
            mcp_tools (Dict[str, Any]): Dictionary of MCP tools to convert.
        """
        try:
            # Clear existing caches
            self._mcp_to_ollama_schemas = {}
            
            # Build the schema cache
            for tool_name, tool in mcp_tools.items():
                # Extract the schema from the tool
                tool_schema = self._extract_MCPTool_schema_in_Ollama(tool)
                    
                # Convert MCP schema to Ollama format
                ollama_schema = {
                    "type": "function",
                    "function": tool_schema
                }
 
                # Cache the Ollama schema
                self._mcp_to_ollama_schemas[tool_name] = ollama_schema

            self.logger.debug(f"Built schema cache for {len(self._mcp_to_ollama_schemas)} tools")
            
        except Exception as e:
            self.logger.error(f"Error building tool schema cache: {e}")
            # Don't re-raise, as this is a non-critical error that shouldn't halt execution
    
    def _extract_MCPTool_schema_in_Ollama(self, tool) -> Dict[str, Any]:
        """Extract schema from an MCP tool object.
        
        Args:
            tool: The MCP tool object to extract schema from.
            
        Returns:
            Dict[str, Any]: Schema in Ollama format.
        """
        if hasattr(tool, "name") and hasattr(tool, "description") and hasattr(tool, "inputSchema"):
            # Build a schema dictionary from the tool's attributes
            schema = {
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.inputSchema
            }
            return schema
        else:
            self.logger.error(f"Provided tool object does not have the expected attributes")
            return {}
    
    def get_all_tools(self) -> List[Dict[str, Any]]:
        """Get all available tools in Ollama's expected format.
        
        Returns:
            List[Dict[str, Any]]: List of tools in Ollama format.
        """
        if not self._mcp_to_ollama_schemas:
            self.logger.warning("No tools available in schema cache")
            return []
            
        self.logger.debug(f"Returning {len(self._mcp_to_ollama_schemas)} tools from schema cache")
        return list(self._mcp_to_ollama_schemas.values())

    async def process_tool_calls(self, tool_calls: List[Dict[str, Any]], manager) -> List[Dict[str, Any]]:
        """Process Ollama tool calls and execute them using MCP.
        
        Args:
            tool_calls (List[Dict[str, Any]]): List of tool calls from Ollama.
            manager: Reference to the MCPManager that will execute the tools.
            
        Returns:
            List[Dict[str, Any]]: List of tool responses in Ollama format.
        """
        tool_responses = []
        processing_tasks = []
        
        # Process each tool call
        for tool_call in tool_calls:
            processing_tasks.append(self._process_single_tool_call(tool_call, manager))
            
        # Wait for all tool calls to be processed
        tool_responses = await asyncio.gather(*processing_tasks)
        
        return tool_responses
    
    async def _process_single_tool_call(self, tool_call: Dict[str, Any], manager) -> Dict[str, Any]:
        """Process a single tool call and return the response in Ollama's expected format.
        
        Args:
            tool_call (Dict[str, Any]): The tool call to process.
            manager: Reference to the MCPManager that will execute the tool.
            
        Returns:
            Dict[str, Any]: Tool response in Ollama format.
        """
        function_call = tool_call.get("function", {})
        function_name = function_call.get("name", "")
        
        self.logger.debug(f"Processing tool call: {function_name}")
        
        # Parse arguments (safely)
        try:
            # Handle both string and dict arguments formats
            if isinstance(function_call.get("arguments"), str):
                arguments = json.loads(function_call.get("arguments", "{}"))
            else:
                arguments = function_call.get("arguments", {})
        except json.JSONDecodeError as e:
            self.logger.error(f"Invalid JSON in tool call arguments: {function_call.get('arguments')}: {e}")
            arguments = {}
        
        # Execute the tool
        result = None
        error = None
        
        try:
            # Execute the tool using the manager
            self.logger.debug(f"Executing tool {function_name} with arguments: {arguments}")
            result = await manager.execute_tool(function_name, arguments)
            
        except ValueError as param_error:
            # Parameter validation error
            error = f"Parameter error executing tool {function_name}: {param_error}"
            self.logger.error(error)
        except ConnectionError as e:
            error = f"Connection error executing tool {function_name}: {e}"
            self.logger.error(error)
        except TimeoutError as e:
            error = f"Timeout error executing tool {function_name}: {e}"
            self.logger.error(error)
        except Exception as e:
            error = f"Error executing tool {function_name}: {e}"
            self.logger.error(error)

        # Create the tool response in Ollama's expected format
        tool_response = {
            "role": "tool",
            "name": function_name
        }
        
        if result is not None:
            tool_response["content"] = result
        else:
            # Return a structured error with useful information to help the LLM retry
            tool_response["content"] = json.dumps({"error": error})
        
        return tool_response