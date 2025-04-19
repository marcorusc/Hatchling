import asyncio
import aiohttp
import logging
import json
from typing import List, Dict, Tuple, Any, Optional

# Updated import path for MCPManager
from mcp_utils.manager import mcp_manager
# Updated import paths for logging and settings
from core.logging.session_debug_log import SessionDebugLog
from core.logging.logging_manager import logging_manager
from config.settings import ChatSettings
from core.llm.model_manager import ModelManager

class ChatSession:
    def __init__(self, settings: ChatSettings):
        """Initialize a chat session with the specified settings."""
        self.settings = settings
        self.model_name = settings.default_model
        self.messages: List[Dict[str, str]] = []
        self.is_streaming = True
        # Get session-specific logger from the manager
        self.debug_log = logging_manager.get_session(f"ChatSession-{self.model_name}",
                                  formatter=logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
        
        # MCP-related property
        self.tools_enabled = False
    
    async def initialize_mcp(self, server_paths: List[str]) -> bool:
        """Initialize connection to MCP servers.
        
        Args:
            server_paths (List[str]): List of paths to MCP server scripts.
            
        Returns:
            bool: True if connection was successful, False otherwise.
        """
        # Use MCPManager to initialize everything
        self.tools_enabled = await mcp_manager.initialize(server_paths)
        
        if self.tools_enabled:
            self.debug_log.info(f"Connected to MCP servers")
        else:
            self.debug_log.warning("Failed to connect to any MCP server")
            
        return self.tools_enabled
    
    def add_user_message(self, content: str) -> None:
        """Add a user message to the chat history.
        
        Args:
            content (str): The message content.
        """
        self.messages.append({"role": "user", "content": content})
    
    def add_assistant_message(self, content: str) -> None:
        """Add an assistant message to the chat history.
        
        Args:
            content (str): The message content.
        """
        self.messages.append({"role": "assistant", "content": content})
    
    async def send_message(self, user_message: str, session: aiohttp.ClientSession) -> str:
        """Send the current message history to the Ollama API and stream the response.
        
        Args:
            user_message (str): The user's message.
            session (aiohttp.ClientSession): The session to use for the request.
            
        Returns:
            str: The assistant's response.
        """
        # Add user message
        self.add_user_message(user_message)

        # Prepare payload and send message to LLM
        payload = self._prepare_request_payload()
        
        if self.tools_enabled:
            payload = self._add_tools_to_payload(payload)
        
        # Send the request and process the response
        if not self.is_streaming:
            return await self._handle_non_streaming_response(session, payload)
        else:
            return await self._handle_streaming_response(session, payload)
    
    def _prepare_request_payload(self) -> Dict[str, Any]:
        """Prepare the request payload for the LLM API.
        
        Returns:
            Dict[str, Any]: The prepared payload.
        """
        payload = {
            "model": self.model_name,
            "messages": self.messages,
            "stream": self.is_streaming
        }
        self.debug_log.debug(f"Prepared payload: {json.dumps(payload)}")
        return payload
    
    def _add_tools_to_payload(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Add tools to the payload if MCP is enabled.
        
        Args:
            payload (Dict[str, Any]): The original payload.
            
        Returns:
            Dict[str, Any]: The payload with tools added.
        """
        # Add tools from the MCPManager if available
        tools = mcp_manager.get_ollama_tools()
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"
            self.debug_log.debug(f"Added {len(tools)} tools to payload")
        return payload
    
    async def _handle_non_streaming_response(self, session: aiohttp.ClientSession, payload: Dict[str, Any]) -> str:
        """Handle a non-streaming response from the LLM API.
        
        Args:
            session (aiohttp.ClientSession): The http session to use for the chat request.
            payload (Dict[str, Any]): The request payload, containing the message history, possibly tools calls.
            
        Returns:
            str: The assistant's response.
        """
        async with session.post(f"{self.settings.ollama_api_url}/chat", json=payload) as response:
            if response.status != 200:
                error_text = await response.text()
                self.debug_log.error(f"Error: {response.status}, {error_text}")
                raise Exception(f"Error: {response.status}, {error_text}")
            
            data = await response.json()
            content = data["message"]["content"]
            print(content)
            self.add_assistant_message(content)
            
            # Check for tool calls in the non-streaming response
            if "tool_calls" in data["message"] and data["message"]["tool_calls"]:
                await self._process_tool_calls(data["message"]["tool_calls"])
                
            return content
    
    async def _handle_streaming_response(self, session: aiohttp.ClientSession, payload: Dict[str, Any]) -> str:
        """Handle a streaming response from the LLM API.
        
        Args:
            session (aiohttp.ClientSession): The http session to use for the chat request.
            payload (Dict[str, Any]): The request payload, containing the message history, possibly tools calls.
            
        Returns:
            str: The assistant's response.
        """
        async with session.post(f"{self.settings.ollama_api_url}/chat", json=payload) as response:
            if response.status != 200:
                error_text = await response.text()
                self.debug_log.error(f"Error: {response.status}, {error_text}")
                raise Exception(f"Error: {response.status}, {error_text}")
            
            # Process the streaming response
            full_response = ""
            message_tool_calls = []
            tool_results = []
            
            async for line in response.content.iter_any():
                if not line:
                    continue
                    
                try:
                    line_text = line.decode('utf-8').strip()
                    if not line_text:
                        continue
                    
                    # Debug log the raw response
                    self.debug_log.debug(f"Raw response: {line_text}")
                    
                    # Parse the JSON response
                    data = json.loads(line_text)
                    
                    # Process the response data
                    content, current_tool_results = await self._process_response_data(data, message_tool_calls)
                    if content:
                        print(content, end="", flush=True)
                        full_response += content
                    if current_tool_results:
                        tool_results.extend(current_tool_results)
                    
                    # Check if this is the last message
                    if data.get("done", False):
                        print()  # Add a newline after completion
                        break
                        
                except json.JSONDecodeError as e:
                    self.debug_log.error(f"Invalid JSON: {e}")
                except Exception as e:
                    self.debug_log.error(f"Error processing response: {e}")
            
            # Post-processing: update message history and handle tool results
            self._update_message_history(full_response, message_tool_calls, tool_results)
            
            # If we have tool results, send another message to the LLM with the tool results for formatting
            if tool_results and self._should_format_with_tool_results(full_response):
                formatted_response = await self._get_formatted_response_with_tool_results(session, tool_results)
                if formatted_response:
                    return formatted_response
            
            return full_response
    
    async def _process_response_data(self, data: Dict[str, Any], message_tool_calls: List) -> Tuple[str, List]:
        """Process response data and extract content and tool calls.
        
        Args:
            data (Dict[str, Any]): The response data to process, likely from the LLM.
            message_tool_calls (List): List of processed tool calls.
            
        Returns:
            Tuple[str, List]: The content and tool results.
        """
        content = ""
        tool_results = []
        
        # Process tool calls if present
        if self._has_tool_calls(data):
            tool_calls_result = await self._handle_streaming_tool_calls(data, message_tool_calls)
            if tool_calls_result:
                tool_results.extend(tool_calls_result)
        
        # Extract message content
        if self._has_message_content(data):
            content = data["message"]["content"]
        
        return content, tool_results
    
    def _has_tool_calls(self, data: Dict[str, Any]) -> bool:
        """Check if the data contains tool calls. This effectivelye checks for the presence of
        the keys "message" and "tool_calls" in the data.
        
        Args:
            data (Dict[str, Any]): The data to check from the LLM.
            
        Returns:
            bool: True if the data contains tool calls, False otherwise.
        """
        return ("message" in data and 
                "tool_calls" in data["message"] and 
                data["message"]["tool_calls"])
    
    def _has_message_content(self, data: Dict[str, Any]) -> bool:
        """Check if the data contains message content. This effectively checks for the presence of
        the keys "message" and "content" in the data.
        
        Args:
            data (Dict[str, Any]): The data to check.
            
        Returns:
            bool: True if the data contains message content, False otherwise.
        """
        return "message" in data and "content" in data["message"]
    
    async def _handle_streaming_tool_calls(self, data: Dict[str, Any], message_tool_calls: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Process tool calls from streaming response data.
        
        Args:
            data (Dict[str, Any]): The response data from the LLM.
            message_tool_calls (List[Dict[str, Any]]): List of processed tool calls.
            
        Returns:
            List[Dict[str, Any]]: List of tool results.
        """
        tool_results = []
        current_tool_calls = data["message"]["tool_calls"]
        self.debug_log.info(f"Found tool calls: {json.dumps(current_tool_calls)}")
        
        # Process each tool call
        for tool_call in current_tool_calls:
            tool_id = tool_call.get("id", "unknown")
            # Skip if we've already processed this tool call
            if any(tc.get("id") == tool_id for tc in message_tool_calls):
                continue
                
            # Add to our tracking list
            message_tool_calls.append(tool_call)
            
            # Process the tool call
            tool_result = await self._process_tool_call(tool_call, tool_id)
            if tool_result:
                tool_results.append(tool_result)
        
        return tool_results
    
    async def _execute_tool(self, tool_id: str, function_name: str, arguments: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Execute a tool and return its result.
        
        Args:
            tool_id (str): The ID of the tool.
            function_name (str): The name of the function to execute.
            arguments (Dict[str, Any]): The arguments to pass to the function.
            
        Returns:
            Optional[Dict[str, Any]]: The tool result, or None if execution failed.
        """
        try:
            # Format the tool call for the MCPManager
            formatted_tool_call = {
                "id": tool_id,
                "function": {
                    "name": function_name,
                    "arguments": json.dumps(arguments) if isinstance(arguments, dict) else arguments
                }
            }
            
            # Process the tool call using MCPManager
            tool_responses = await mcp_manager.process_tool_calls([formatted_tool_call])
            
            if tool_responses and len(tool_responses) > 0:
                tool_response = tool_responses[0]
                result_content = tool_response.get("content", "No result")
                
                # Try to parse the content to a more user-friendly format
                try:
                    if isinstance(result_content, str):
                        parsed_result = json.loads(result_content)
                        result_content = parsed_result
                except json.JSONDecodeError:
                    # Keep as string if it's not valid JSON
                    pass
                
                # Show the tool result to the user
                print(f"[Tool result: {result_content}]\n")
                
                # Return the tool result
                return {
                    "role": "tool",
                    "tool_call_id": tool_id,
                    "name": function_name,
                    "content": str(result_content)
                }
        except Exception as e:
            self.debug_log.error(f"Error executing tool: {e}")
            print(f"[Error executing tool: {e}]\n")
        
        return None
    
    def _update_message_history(self, full_response: str, message_tool_calls: List[Dict[str, Any]], 
                                     tool_results: List[Dict[str, Any]]) -> None:
        """Update the message history with the response and tool results.
        
        Args:
            full_response (str): The complete response from the LLM.
            message_tool_calls (List[Dict[str, Any]]): List of tool calls from the response.
            tool_results (List[Dict[str, Any]]): List of tool execution results.
        """
        # Only update if we got a response or tool results
        if not full_response.strip() and not tool_results:
            return
            
        # First add the assistant message
        self.add_assistant_message(full_response)
        
        # If we had tool calls, update the last message to include them
        if message_tool_calls:
            assistant_message_with_tool_calls = {
                "role": "assistant", 
                "content": full_response,
                "tool_calls": message_tool_calls
            }
            
            # Replace the last added message with this one containing tool calls
            if self.messages and self.messages[-1]["role"] == "assistant":
                self.messages[-1] = assistant_message_with_tool_calls
            
            # Add all tool results to the message history
            for tool_result in tool_results:
                self.messages.append(tool_result)
    
    def _should_format_with_tool_results(self, full_response: str) -> bool:
        """Determine if we should send tool results back to the LLM for formatting.
        
        Args:
            full_response (str): The complete response from the LLM.
            
        Returns:
            bool: True if we should format with tool results, False otherwise.
        """
        # If the response is empty or just whitespace, or doesn't contain a helpful response
        return not full_response.strip() or "I'll use a tool" in full_response
    
    async def _get_formatted_response_with_tool_results(self, session: aiohttp.ClientSession,  
                                                      tool_results: List[Dict[str, Any]]) -> Optional[str]:
        """Send a follow-up request to the LLM to format the tool results.
        
        Args:
            session (aiohttp.ClientSession): The http session to use for the request to the LLM.
            tool_results (List[Dict[str, Any]]): The tool results to format.
            
        Returns:
            Optional[str]: The formatted response, or None if formatting failed.
        """
        try:
            self.debug_log.info("Sending follow-up request to format tool results")
            
            # Keep a copy of the current messages to restore later
            original_messages = self.messages.copy()
            
            # Get the original user query (should be the last user message)
            user_query = "Unknown request"
            for msg in reversed(self.messages):
                if msg["role"] == "user":
                    user_query = msg["content"]
                    break
            
            # Create a new message to ask the LLM to format the results
            format_request = {
                "role": "user",
                "content": f"I used tools in reaction to: `{user_query}`. Here are the tool results: {tool_results}. Provide a helpful, well-formatted answer to the original question using these results."
            }

            # Add this as a new message
            self.messages.append(format_request)
            
            # Create a payload for a non-streaming request (for simplicity)
            old_streaming = self.is_streaming
            self.is_streaming = False
            
            # Use the existing prepare_request_payload method but disable tools
            payload = self._prepare_request_payload()
            
            # Make the request
            async with session.post(f"{self.settings.ollama_api_url}/chat", json=payload) as response:
                if response.status != 200:
                    self.debug_log.error("Failed to get formatted response")
                    return None
                
                data = await response.json()
                formatted_response = data["message"]["content"]
            
            # Print the formatted response
            print("\nFormatted response based on tool results:")
            print(formatted_response)
            
            # Restore original state
            self.messages = original_messages
            self.is_streaming = old_streaming
            
            # Add the formatted response as an assistant message
            self.add_assistant_message(formatted_response)
            
            return formatted_response
            
        except Exception as e:
            self.debug_log.error(f"Error formatting with tool results: {e}")
            return None

    async def _process_tool_calls(self, tool_calls: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Process tool calls from a non-streaming response.
        
        Args:
            tool_calls (List[Dict[str, Any]]): List of tool calls from the LLM.
            
        Returns:
            List[Dict[str, Any]]: List of tool results.
        """
        # Similar to _handle_streaming_tool_calls but for non-streaming responses
        message_tool_calls = []
        tool_results = []
        
        for tool_call in tool_calls:
            tool_id = tool_call.get("id", "unknown")
            message_tool_calls.append(tool_call)
            
            # Process the tool call
            tool_result = await self._process_tool_call(tool_call, tool_id)
            if tool_result:
                tool_results.append(tool_result)
        
        # Update message history with tool calls and results
        if message_tool_calls and self.messages and self.messages[-1]["role"] == "assistant":
            # Add tool calls to the last assistant message
            self.messages[-1]["tool_calls"] = message_tool_calls
            
            # Add tool results to the conversation
            for tool_result in tool_results:
                self.messages.append(tool_result)
                
        return tool_results

    async def _process_tool_call(self, tool_call: Dict[str, Any], tool_id: str) -> Optional[Dict[str, Any]]:
        """Process a single tool call and return the result.
        
        Args:
            tool_call (Dict[str, Any]): The tool call to process.
            tool_id (str): The ID of the tool call.
            
        Returns:
            Optional[Dict[str, Any]]: The tool result, or None if processing failed.
        """
        function_name = tool_call["function"]["name"]
        arguments = tool_call["function"]["arguments"]
        
        # Parse arguments if needed
        try:
            if isinstance(arguments, str):
                arguments = json.loads(arguments)
        except json.JSONDecodeError:
            arguments = {}
        
        # Show tool usage to the user
        print(f"\n[Using tool: {function_name} with arguments: {arguments}]\n")
        
        # Execute tool and get result
        if self.tools_enabled:
            return await self._execute_tool(tool_id, function_name, arguments)
        
        return None

def print_chat_commands_help() -> None:
    """Print help for chat commands."""
    print("\n=== Chat Commands ===")
    print("Type 'help' for this help message")
    print()
    print("Type 'exit' or 'quit' to end the chat")
    print("Type 'clear' to clear the chat history")
    print("Type 'show_logs <n: int, optional>' to display the last n entries in the session logs, or everything by default.")
    print("Type 'set_log_level <level>' to change the log level (debug, info, warning, error, critical)")
    print("Type 'enable_tools' to enable MCP tools")
    print("Type 'disable_tools' to disable MCP tools")
    print("======================\n")

# Update the interactive_chat function to use MCPManager for disconnection
async def interactive_chat(settings: ChatSettings, debug_log: SessionDebugLog = None) -> None:
    """Run an interactive chat session with message history.
    
    Args:
        settings (ChatSettings): The chat settings to use.
        debug_log (SessionDebugLog, optional): The debug log to use.
    """
    # Create a chat session
    chat = ChatSession(settings)
    
    debug_log.info(f"Starting interactive chat with {settings.default_model}")
    print_chat_commands_help()
    
    async with aiohttp.ClientSession() as session:
        while True:
            try:
                # Get user input
                status = "[Tools enabled]" if chat.tools_enabled else "[Tools disabled]"
                user_message = input(f"{status} You: ")
                
                # Handle special commands
                if user_message == 'help':
                    print_chat_commands_help()
                    continue
                elif user_message in ['exit', 'quit']:
                    print("Ending chat session...")
                    break
                elif user_message == 'clear':
                    chat.messages = []
                    print("Chat history cleared!")
                    continue
                elif user_message.startswith('show_logs'):
                    logs_to_show = int(user_message.split(' ')[1]) if len(user_message.split(' ')) > 1 else None
                    print(chat.debug_log.get_logs(logs_to_show))
                    continue
                elif user_message.startswith('set_log_level '):
                    level_name = user_message.split(' ')[1]
                    level_map = {
                        "debug": logging.DEBUG,
                        "info": logging.INFO,
                        "warning": logging.WARNING,
                        "error": logging.ERROR, 
                        "critical": logging.CRITICAL
                    }
                    if level_name in level_map:
                        logging_manager.set_cli_log_level(level_map[level_name])
                        debug_log.info(f"Log level set to {level_name}")
                    else:
                        debug_log.error(f"Unknown log level: {level_name}")
                    continue
                elif user_message == 'enable_tools':
                    connected = await chat.initialize_mcp(settings.mcp_server_urls)
                    if not connected:
                         debug_log.error("Failed to connect to MCP servers. Tools not enabled.")
                    continue
                elif user_message == 'disable_tools':
                    if chat.tools_enabled:
                        await mcp_manager.disconnect_all()
                        chat.tools_enabled = False
                        # Remove the system message if it exists
                        chat.messages = [msg for msg in chat.messages if msg.get("role") != "system"]
                    continue
                elif not user_message.strip():
                    # Skip empty input
                    continue
                else:
                    # Send the query
                    print("\nAssistant: ", end="", flush=True)
                    await chat.send_message(user_message, session)
                    print()  # Add an extra newline for readability
                
            except KeyboardInterrupt:
                print("\nInterrupted. Ending chat session...")
                break
            except Exception as e:
                chat.debug_log.error(f"Error: {e}")
                print(f"\nError: {e}")

# Update the main function to use MCPManager for MCP checks
async def main(settings: ChatSettings) -> None:
    """Main entry point for the application.
    
    Args:
        settings (ChatSettings): The chat settings to use.
    """
    
    # Create a debug log for the main session
    debug_log = logging_manager.get_session("ChatSession-Main",
                                            logging.Formatter('%(asctime)s - %(name)s - %(levellevel)s - %(message)s'))

    # Create a model manager
    model_manager = ModelManager(settings, debug_log)

    # Check if Ollama service is available
    available, message = await model_manager.check_ollama_service()
    if not available:
        debug_log.error(message)
        debug_log.error(f"Please ensure the Ollama service is running at {settings.ollama_api_url} before running this script.")
        return
    
    debug_log.info(message)
    
    # Check if MCP server is available using MCPManager
    debug_log.info("\nChecking MCP server availability...")
    mcp_available = await mcp_manager.initialize(settings.mcp_server_urls)
    
    if mcp_available:
        debug_log.info("MCP server is available! Tool calling is ready to use.")
        debug_log.info("You can enable tools during the chat session by typing 'enable_tools'")
        # Disconnect after checking
        await mcp_manager.disconnect_all()
    else:
        debug_log.warning("MCP server is not available. You can start the MCP server by running:")
        debug_log.warning("python mcp_server_test.py")
        debug_log.warning("\nContinuing without MCP tools...")
    
    async with aiohttp.ClientSession() as session:
        try:
            # Check if model is available
            is_model_available = await model_manager.check_availability(session, settings.default_model)
            
            if is_model_available:
                debug_log.info(f"Model {settings.default_model} is already pulled.")
            else:
                debug_log.info(f"Pulling model {settings.default_model}...")
                await model_manager.pull_model(session, settings.default_model)

            # Start interactive chat
            await interactive_chat(settings, debug_log)
            
        except Exception as e:
            error_msg = f"An error occurred: {e}"
            debug_log.error(error_msg)
            print(error_msg)
            return
        
        finally:
            # Clean up any remaining MCP server processes
            await mcp_manager.disconnect_all()

if __name__ == "__main__":
    # Create settings
    settings = ChatSettings()
    # Use asyncio to run our async main function
    asyncio.run(main(settings))