import asyncio
import aiohttp
import logging
import json
import time  # Added import for tracking execution time
from typing import List, Dict, Tuple, Any, Optional

# Updated import path for MCPManager
from mcp_utils.manager import mcp_manager
# Updated import paths for logging and settings
from core.logging.session_debug_log import SessionDebugLog
from core.logging.logging_manager import logging_manager
from config.settings import ChatSettings
from core.llm.model_manager import ModelManager
from core.chat.chat_command_handler import ChatCommandHandler
# Import the new MessageHistory class
from core.chat.message_history import MessageHistory

class ChatSession:
    def __init__(self, settings: ChatSettings):
        """Initialize a chat session with the specified settings."""
        self.settings = settings
        self.model_name = settings.default_model
        # Get session-specific logger from the manager
        self.debug_log = logging_manager.get_session(f"ChatSession-{self.model_name}",
                                  formatter=logging.Formatter('%(asctime)s - %(name)s - %(levellevel)s - %(message)s'))
        
        # Initialize message history
        self.history = MessageHistory(self.debug_log)
        
        # MCP-related property
        self.tools_enabled = False
        
        # Tool calling control properties
        self.current_tool_call_iteration = 0
        self.tool_call_start_time = None
        self.root_tool_query = None  # Track the original user query that started the tool sequence
    
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
    
    async def send_message(self, user_message: str, session: aiohttp.ClientSession) -> str:
        """Send the current message history to the Ollama API and stream the response.
        
        Args:
            user_message (str): The user's message.
            session (aiohttp.ClientSession): The session to use for the request.
            
        Returns:
            str: The assistant's response.
        """
        # Add user message
        self.history.add_user_message(user_message)
        
        # Reset tool calling counters for a new user message
        self.current_tool_call_iteration = 0
        self.tool_call_start_time = time.time()  # Start timing
        self.root_tool_query = user_message  # Set the root query for this interaction

        # Prepare payload and send message to LLM
        payload = self._prepare_request_payload()
        if self.tools_enabled:
            payload = self._add_tools_to_payload(payload)
        
        # Process the initial response
        full_response, message_tool_calls, tool_results = await self._stream_response_from_api(
            session, payload, print_output=True, update_history=True
        )
        
        # Check if we have tool results that need further processing
        if self.tools_enabled and self.current_tool_call_iteration > 0:
            # Only process tool calling chains if we've started using tools
            full_response, message_tool_calls, tool_results = await self._handle_tool_calling_chain(
                                                        session,
                                                        full_response,
                                                        message_tool_calls,
                                                        tool_results)
        
        # If we have tool results, send another message to the LLM with the tool results for formatting
        #if tool_results:
            full_response = await self._get_formatted_response_with_tool_results(session, tool_results)

        return full_response
    
    def _prepare_request_payload(self) -> Dict[str, Any]:
        """Prepare the request payload for the LLM API.
        
        Returns:
            Dict[str, Any]: The prepared payload.
        """
        payload = {
            "model": self.model_name,
            "messages": self.history.get_messages(),
            "stream": True  # Always stream
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
            # Increment the tool call iteration counter each time a tool is executed
            self.current_tool_call_iteration += 1
            
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
        
        return None
    
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
            
            # Keep a copy of the current messages
            original_history = self.history.copy()
            
            # Get the original user query
            user_query = self.history.get_last_user_message() or "Unknown request"
            
            # Create a new message to ask the LLM to format the results
            format_request = {
                "role": "user",
                "content": f"I used tools in reaction to: `{user_query}`. Here are the tool results: {tool_results}. Provide a helpful, well-formatted answer to the original question using these results."
            }

            # Add this as a new message
            self.history.messages.append(format_request)
            
            payload = self._prepare_request_payload()
            
            # Use our shared streaming method with a custom prefix
            formatted_response, _, _ = await self._stream_response_from_api(
                session,
                payload,
                print_output=True,
                prefix="\nFormatted response based on tool results:",
                # We'll handle updating history later with the original_messages
                update_history=False
            )
            
            # Restore original state
            self.history = original_history
            
            # Add the formatted response as an assistant message
            self.history.add_assistant_message(formatted_response)
            
            return formatted_response
            
        except Exception as e:
            self.debug_log.error(f"Error formatting with tool results: {e}")
            return None

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

    async def _handle_tool_calling_chain(self,
                    session: aiohttp.ClientSession,
                    full_response: str,
                    message_tool_calls: List[Dict[str, Any]],
                    tool_results: List[Dict[str, Any]]
                    ) -> Tuple[str, List[Dict[str, Any]], List[Dict[str, Any]]]:
        """Handle the response from the LLM API and manage tool calling chains.
        
        Args:
            session (aiohttp.ClientSession): The http session to use for the request.
            full_response (str): The latest response from the LLM.
            message_tool_calls (List[Dict[str, Any]]): List of tool calls from the response.
            tool_results (List[Dict[str, Any]]): List of tool execution results.
                        
        Returns:
            Tuple[str, List[Dict[str, Any]], List[Dict[str, Any]]]: Tuple containing
            (full_response, message_tool_calls, tool_results).
        """

        _full_response, _message_tool_calls, _tool_results = full_response, message_tool_calls, tool_results
        
        # If we have tool results, we need to decide what to do next
        if tool_results:
            elapsed_time = time.time() - self.tool_call_start_time
            
            # Check if we've hit limits
            reached_max_iterations = self.current_tool_call_iteration >= self.settings.max_tool_call_iteration
            reached_time_limit = elapsed_time >= self.settings.max_working_time
            
            if reached_max_iterations or reached_time_limit:
                # We've reached a limit, generate a partial response
                limit_reason = "maximum iterations" if reached_max_iterations else "time limit"
                self.debug_log.warning(f"Reached {limit_reason} for tool calling ({self.current_tool_call_iteration} iterations, {elapsed_time:.1f}s)")
                return await self._format_response_with_tool_results(
                    session,
                    tool_results=tool_results,
                    is_final=False,
                    limit_reason=limit_reason
                ), [], []
            
            # Continue with sequential tool calling - prepare new payload with updated messages
            #Write a prompt asking the LLM whether the tool results are enough to answer the question
            self.debug_log.info("Preparing next payload for sequential tool calling")
            self.history.add_user_message(f"Given the tool results: {tool_results}, do you have enough information to answer the original query: `{self.root_tool_query}`? If not, please ask for more information or continue using tools.")
            
            # Prepare the next payload
            next_payload = self._prepare_request_payload()
            next_payload = self._add_tools_to_payload(next_payload)
            
            _full_response, _message_tool_calls, _tool_results = await self._stream_response_from_api(
                 session, next_payload, print_output=False, update_history=True
             )

            # Process the next step (recursive call)
            self.debug_log.info(f"Continuing with tool calling iteration {self.current_tool_call_iteration}/{self.settings.max_tool_call_iteration} ({elapsed_time:.1f}s elapsed)")
            _full_response, _message_tool_calls, _tool_results = await self._handle_tool_calling_chain(session, 
                                                         _full_response,
                                                         _message_tool_calls,
                                                         _tool_results)

        # Return the original response if it was a direct LLM response with no tool usage
        return _full_response, _message_tool_calls, _tool_results

    async def _stream_response_from_api(self, session, payload, print_output=True, prefix=None, update_history=True):
        """Stream a response from the API and handle common processing.
        
        Args:
            session: The aiohttp client session to use.
            payload: The request payload to send to the API.
            print_output: Whether to print the output to the console, if there are no tool calls.
            prefix: Optional prefix to print before the response.
            update_history: Whether to update message history with the response.
            
        Returns:
            tuple: (full_response, message_tool_calls, tool_results).
        """
        full_response = ""
        message_tool_calls = []
        tool_results = []
        
        if prefix and print_output:
            print(prefix)
            
        async with session.post(f"{self.settings.ollama_api_url}/chat", json=payload) as response:
            if response.status != 200:
                error_text = await response.text()
                self.debug_log.error(f"Error: {response.status}, {error_text}")
                raise Exception(f"Error: {response.status}, {error_text}")
            
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
                    if current_tool_results:
                        tool_results.extend(current_tool_results)
                    elif content:
                        if print_output:
                            print(content, end="", flush=True)
                        full_response += content
                    
                    # Check if this is the last message
                    if data.get("done", False):
                        if print_output:
                            print()  # Add a newline after completion
                        break
                    
                except json.JSONDecodeError as e:
                    self.debug_log.error(f"Invalid JSON: {e}")
                except Exception as e:
                    self.debug_log.error(f"Error processing response: {e}")
        
        # Update message history if requested
        if update_history:
            self.history.update_message_history(full_response, message_tool_calls, tool_results)
        
        return full_response, message_tool_calls, tool_results

    async def _format_response_with_tool_results(self, session: aiohttp.ClientSession,
                                          tool_results: List[Dict[str, Any]] = None,
                                          is_final: bool = True,
                                          limit_reason: str = None) -> str:
        """Format a response based on tool results.
        
        Args:
            session (aiohttp.ClientSession): The http session to use for the request.
            tool_results (List[Dict[str, Any]], optional): The tool results to format.
            is_final (bool): Whether this is the final response (True) or partial (False).
            limit_reason (str, optional): If partial, the reason for stopping (max iterations or time limit).
            
        Returns:
            str: The formatted response.
        """
        try:
            response_type = "final" if is_final else "partial"
            self.debug_log.info(f"Generating {response_type} response for tool operations")
            
            # Build the prompt based on whether it's a final or partial response
            prompt = f"I used tools in reaction to: `{self.root_tool_query}`."
            
            if not is_final and limit_reason:
                prompt += f" However, I reached {limit_reason} ({self.current_tool_call_iteration} iterations).\n\n"
                if tool_results:
                    # Convert tool results to a simpler string format to prevent JSON issues
                    simple_results = []
                    for result in tool_results:
                        simple_results.append({
                            "name": result.get("name", "unknown"),
                            "content": result.get("content", "No content")
                        })
                    prompt += f"Here are the tool results: {simple_results}.\n\n"
                prompt += "Provide a partial answer based on these results and ask if the user wants to continue processing."
            else:  # final response
                prompt += "\n\n"
                if tool_results:
                    # Convert tool results to a simpler string format
                    simple_results = []
                    for result in tool_results:
                        simple_results.append({
                            "name": result.get("name", "unknown"), 
                            "content": result.get("content", "No content")
                        })
                    prompt += f"Here are the tool results: {simple_results}.\n\n"
                prompt += "Please provide a comprehensive final answer to the original question based on all the tool operations."
                prompt += " Use clear formatting and explanations."
            
            # Create a clean message history with just what we need for formatting
            clean_history = MessageHistory(self.debug_log)
            
            # Include the root query for context
            clean_history.add_user_message(self.root_tool_query)
            
            # Add the formatting request
            clean_history.add_user_message(prompt)
            
            # Create a new payload without tools (we don't want more tool calls in the formatted response)
            payload = {
                "model": self.model_name,
                "messages": clean_history.get_messages(),
                "stream": True
            }
            
            # Get the formatted response using our shared helper
            prefix = f"\n{response_type.capitalize()} response based on tool results:"
            full_response, _, _ = await self._stream_response_from_api(
                session, payload, print_output=True, prefix=prefix, update_history=True
            )
            
            # Add the formatted response as an assistant message
            if full_response:
                self.history.add_assistant_message(full_response)
            
            return full_response
        
        except Exception as e:
            response_type = "final" if is_final else "partial"
            self.debug_log.error(f"Error formatting {response_type} response: {e}")
            return f"Error formatting the response after tool operations."

# Update the interactive_chat function to use ChatCommandHandler
async def interactive_chat(settings: ChatSettings, debug_log: SessionDebugLog = None) -> None:
    """Run an interactive chat session with message history.
    
    Args:
        settings (ChatSettings): The chat settings to use.
        debug_log (SessionDebugLog, optional): The debug log to use.
    """
    # Create a chat session
    chat = ChatSession(settings)
    
    # Create command handler
    cmd_handler = ChatCommandHandler(chat, settings, debug_log)
    
    debug_log.info(f"Starting interactive chat with {settings.default_model}")
    cmd_handler.print_commands_help()
    
    async with aiohttp.ClientSession() as session:
        while True:
            try:
                # Get user input
                status = "[Tools enabled]" if chat.tools_enabled else "[Tools disabled]"
                user_message = input(f"{status} You: ")
                
                # Process as command if applicable
                is_command, should_continue = await cmd_handler.process_command(user_message)
                if is_command:
                    if not should_continue:
                        break
                    continue
                
                # Handle normal message
                if not user_message.strip():
                    # Skip empty input
                    continue
                
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
    debug_log.info("Checking MCP server availability...")
    mcp_available = await mcp_manager.initialize(settings.mcp_server_urls)
    
    if mcp_available:
        debug_log.info("MCP server is available! Tool calling is ready to use.")
        debug_log.info("You can enable tools during the chat session by typing 'enable_tools'")
        # Disconnect after checking
        await mcp_manager.disconnect_all()
    else:
        debug_log.warning("MCP server is not available. You can start the MCP server by running:")
        debug_log.warning("python mcp_server_test.py")
        debug_log.warning("Continuing without MCP tools...")
    
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