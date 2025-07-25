import json
from typing import List, Dict, Tuple, Any
import logging
import aiohttp
from hatchling.core.logging.logging_manager import logging_manager
from hatchling.config.settings import AppSettings
from hatchling.core.chat.message_history import MessageHistory

class APIManager:
    """Manages API communication with the LLM."""
    
    def __init__(self, settings: AppSettings):
        """Initialize the API manager.
        
        Args:
            settings: The application settings
        """
        self.settings = settings
        provider = settings.llm.get_provider
        model = settings.llm.get_active_model()
        self.logger = logging_manager.get_session(
            f"APIManager-{provider}-{model}",
            formatter=logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        )
        self.model_name = model
    
    def prepare_request_payload(self, messages: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Prepare the request payload for the LLM API.
        
        Args:
            messages: List of message dictionaries
            
        Returns:
            The prepared payload.
        """
        payload = {
            "model": self.model_name,
            "messages": messages,
            "stream": True  # Always stream
        }
        self.logger.debug(f"Prepared payload: {json.dumps(payload)}")
        return payload
    
    def add_tools_to_payload(self, payload: Dict[str, Any], tools: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Add tools/functions to the payload depending on provider."""
        if not tools:
            return payload
        if self.settings.llm.get_provider == "openai":
            # Use the new OpenAI tools format (not the deprecated functions format)
            openai_tools = []
            for tool in tools:
                if tool.get("type") == "function":
                    # Tool is already in the correct format
                    openai_tools.append(tool)
                else:
                    # Convert to new tools format
                    openai_tools.append({
                        "type": "function",
                        "function": tool
                    })
            payload["tools"] = openai_tools
            payload["tool_choice"] = "auto"
            self.logger.debug(f"Added {len(openai_tools)} tools to OpenAI payload: {openai_tools}")
        else:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"
            self.logger.debug(f"Added {len(tools)} tools to payload: {tools}")
        return payload
    
    def has_tool_calls(self, data: Dict[str, Any]) -> bool:
        """Check if the data contains tool calls.
        
        Args:
            data: The data to check from the LLM.
            
        Returns:
            True if the data contains tool calls, False otherwise.
        """
        return ("message" in data and 
                "tool_calls" in data["message"] and 
                data["message"]["tool_calls"])
    
    def has_message_content(self, data: Dict[str, Any]) -> bool:
        """Check if the data contains message content.
        
        Args:
            data: The data to check.
            
        Returns:
            True if the data contains message content, False otherwise.
        """
        return "message" in data and "content" in data["message"]
    
    async def process_response_data(self,
                                    data: Dict[str, Any],
                                    message_tool_calls: List,
                                    tool_executor
                                    ) -> Tuple[str, List]:
        """Process response data and extract content and tool calls.
        
        Args:
            data (Dict[str, Any]): The response data to process from the LLM.
            message_tool_calls (List): List of processed tool calls.
            tool_executor: The tool execution manager to handle tool calls.
            
        Returns:
            Tuple[str, List]: A tuple containing:
                - str: The extracted content from the response
                - List: The collected tool results
        """
        content = ""
        tool_results = []
        
        # Process tool calls if present
        if self.has_tool_calls(data):
            tool_calls_result = await tool_executor.handle_streaming_tool_calls(data, message_tool_calls)
            if tool_calls_result:
                tool_results.extend(tool_calls_result)
        
        # Extract message content
        if self.has_message_content(data):
            content = data["message"]["content"]
        
        return content, tool_results
    
    async def stream_response(self,
                              session: aiohttp.ClientSession,
                              payload: Dict[str, Any],
                              history: MessageHistory,
                              tool_executor,
                              print_output: bool = True,
                              prefix: str = None,
                              update_history: bool = True) -> Tuple[str, List, List]:
        """Stream a response using the configured provider."""

        # Check if we're using OpenAI provider for proper tool format
        if self.settings.llm.get_provider == "openai":
            return await self._stream_openai_response(
                session, payload, history, tool_executor,
                print_output=print_output,
                prefix=prefix,
                update_history=update_history,
            )

        # For other providers (like Ollama), use the original generic implementation
        full_response = ""
        message_tool_calls = []
        tool_results = []
        
        if prefix and print_output:
            print(prefix)
        
        # Ollama or other providers
        api_url = f"http://{self.settings.ollama.ollama_ip}:{self.settings.ollama.ollama_port}/api/chat"
        headers = {}
            
        async with session.post(api_url, json=payload, headers=headers) as response:
            if response.status != 200:
                error_text = await response.text()
                self.logger.error(f"Error: {response.status}, {error_text}")
                raise Exception(f"Error: {response.status}, {error_text}")
            
            async for line in response.content.iter_any():
                if not line:
                    continue
                
                try:
                    line_text = line.decode('utf-8').strip()
                    if not line_text:
                        continue
                    
                    # Debug log the raw response
                    self.logger.debug(f"Raw response: {line_text}")
                    
                    # Parse the JSON response
                    data = json.loads(line_text)
                    
                    # Process the response data
                    content, current_tool_results = await self.process_response_data(data, message_tool_calls, tool_executor)

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
                    self.logger.error(f"Invalid JSON: {e}")
                except Exception as e:
                    self.logger.error(f"Error processing response: {e}")
        
        # Update message history if requested
        if update_history and history:
            history.update_message_history(full_response, message_tool_calls, tool_results)
        
        return full_response, message_tool_calls, tool_results

    async def _stream_openai_response(self,
                                      session: aiohttp.ClientSession,
                                      payload: Dict[str, Any],
                                      history: MessageHistory,
                                      tool_executor,
                                      print_output: bool = True,
                                      prefix: str = None,
                                      update_history: bool = True) -> Tuple[str, List, List]:
        """Stream a response from the OpenAI API with proper tool call handling.
        
        This method handles OpenAI's streaming tool call format correctly by maintaining
        separate accumulators for each tool call index, allowing multiple tools to be
        called simultaneously and their arguments to be streamed in fragments.
        
        Args:
            session: HTTP client session
            payload: Request payload for OpenAI API
            history: Message history to update
            tool_executor: Tool execution manager
            print_output: Whether to print response content
            prefix: Optional prefix to print
            update_history: Whether to update message history
            
        Returns:
            Tuple of (full_response, message_tool_calls, tool_results)
        """

        full_response = ""
        message_tool_calls = []
        tool_results = []
        # Support multiple simultaneous tool calls with separate accumulators per index
        tool_call_accumulators = {}  # index -> {"accumulator": str, "name": str, "id": str}

        headers = {"Authorization": f"Bearer {self.settings.openai.api_key}"}

        if prefix and print_output:
            print(prefix)

        async with session.post(f"{self.settings.openai.api_base}/chat/completions",
                                json=payload,
                                headers=headers) as response:
            if response.status != 200:
                error_text = await response.text()
                self.logger.error(f"Error: {response.status}, {error_text}")
                raise Exception(f"Error: {response.status}, {error_text}")

            async for line in response.content:
                if not line:
                    continue

                line_text = line.decode("utf-8").strip()
                if not line_text:
                    continue

                for chunk in line_text.split("\n\n"):
                    if not chunk:
                        continue
                    if chunk.startswith("data:"):
                        chunk = chunk[len("data:"):].strip()
                    if chunk == "[DONE]":
                        if print_output:
                            print()
                        break

                    try:
                        data = json.loads(chunk)
                    except json.JSONDecodeError:
                        continue

                    choices = data.get("choices", [])
                    if not choices:
                        continue
                    delta = choices[0].get("delta", {})

                    # Handle tool calls (new format)
                    if "tool_calls" in delta:
                        tool_calls = delta["tool_calls"]
                        
                        for tool_call in tool_calls:
                            # Get the index for this tool call
                            index = tool_call.get("index", 0)
                            
                            # Initialize accumulator for this index if needed
                            if index not in tool_call_accumulators:
                                tool_call_accumulators[index] = {
                                    "accumulator": "",
                                    "name": None,
                                    "id": None
                                }
                                self.logger.debug(f"Initialized tool call accumulator for index {index}")
                            
                            acc = tool_call_accumulators[index]
                            
                            # Extract ID if present
                            if "id" in tool_call and acc["id"] is None:
                                acc["id"] = tool_call["id"]
                            
                            if "function" in tool_call:
                                fc = tool_call["function"]
                                
                                # Extract function name if present
                                if "name" in fc and acc["name"] is None:
                                    acc["name"] = fc["name"]
                                
                                # Always accumulate arguments if present
                                if "arguments" in fc:
                                    acc["accumulator"] += fc["arguments"]
                            else:
                                self.logger.debug(f"Tool call missing 'function' key for index {index}")
                                continue

                    # Handle normal content
                    content_piece = delta.get("content")
                    if content_piece:
                        if print_output:
                            print(content_piece, end="", flush=True)
                        full_response += content_piece

            # Execute all accumulated tool calls
            for index, acc in tool_call_accumulators.items():
                if acc["name"] and acc["accumulator"]:
                    try:
                        args = json.loads(acc["accumulator"])
                        self.logger.debug(f"Executing tool {acc['name']} (index {index}) with args: {args}")
                    except Exception as e:
                        self.logger.error(f"Failed to parse tool arguments for {acc['name']} (index {index}): {e}")
                        args = {}
                    
                    # Execute the tool
                    tool_result = await tool_executor.execute_tool(acc["id"], acc["name"], args)
                    if tool_result:
                        # Add tool result in the format expected by update_message_history
                        tool_results.append({
                            "tool_call_id": acc["id"],
                            "name": acc["name"],
                            "content": tool_result["content"]
                        })
                        message_tool_calls.append({
                            "id": acc["id"],
                            "type": "function",  # Required by OpenAI
                            "function": {"name": acc["name"], "arguments": acc["accumulator"]}
                        })
                else:
                    if acc["name"]:
                        self.logger.error(f"Tool {acc['name']} (index {index}) missing arguments")
                    else:
                        self.logger.error(f"Tool call (index {index}) missing function name")

        if update_history and history:
            history.update_message_history(full_response, message_tool_calls, tool_results)

        return full_response, message_tool_calls, tool_results
