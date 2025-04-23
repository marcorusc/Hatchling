import aiohttp
import logging
from typing import List, Dict, Tuple, Any, Optional

from core.logging.session_debug_log import SessionDebugLog
from core.logging.logging_manager import logging_manager
from config.settings import ChatSettings
from core.chat.message_history import MessageHistory
from core.llm.tool_execution_manager import ToolExecutionManager
from core.llm.api_manager import APIManager

class ChatSession:
    def __init__(self, settings: ChatSettings):
        """Initialize a chat session with the specified settings.
        
        Args:
            settings (ChatSettings): Configuration settings for the chat session.
        """
        self.settings = settings
        self.model_name = settings.default_model
        # Get session-specific logger from the manager
        self.debug_log = logging_manager.get_session(f"ChatSession-{self.model_name}",
                                  formatter=logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
        
        # Initialize message components
        self.history = MessageHistory(self.debug_log)
        self.tool_executor = ToolExecutionManager(settings)
        self.api_manager = APIManager(settings)
    
    async def initialize_mcp(self, server_paths: List[str]) -> bool:
        """Initialize connection to MCP servers.
        
        Args:
            server_paths (List[str]): List of paths to MCP server scripts.
            
        Returns:
            bool: True if connection was successful, False otherwise.
        """
        return await self.tool_executor.initialize_mcp(server_paths)
    
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
        self.tool_executor.reset_for_new_query(user_message)

        # Prepare payload and send message to LLM
        payload = self.api_manager.prepare_request_payload(self.history.get_messages())
        if self.tool_executor.tools_enabled:
            tools = self.tool_executor.get_tools_for_payload()
            payload = self.api_manager.add_tools_to_payload(payload, tools)
        
        # Process the initial response
        full_response, message_tool_calls, tool_results = await self.api_manager.stream_response(
            session, payload, self.history, self.tool_executor, print_output=True, update_history=True
        )
        
        # Check if we have tool results that need further processing
        if self.tool_executor.tools_enabled and self.tool_executor.current_tool_call_iteration > 0:
            # Only process tool calling chains if we've started using tools
            full_response, message_tool_calls, tool_results = await self.tool_executor.handle_tool_calling_chain(
                                                        session,
                                                        self.api_manager,
                                                        self.history,
                                                        full_response,
                                                        message_tool_calls,
                                                        tool_results)
        
            full_response = await self._format_response_with_tool_results(session, message_tool_calls, tool_results, is_final=True)

        return full_response
    
    async def _format_response_with_tool_results(self, session: aiohttp.ClientSession,
                                        message_tool_calls: List[Dict[str, Any]] = None,
                                        tool_results: List[Dict[str, Any]] = None,
                                        is_final: bool = True,
                                        limit_reason: str = None) -> str:
        """Format a response based on tool results.
        
        Args:
            session (aiohttp.ClientSession): The http session to use for the request.
            message_tool_calls (List[Dict[str, Any]], optional): The tool calls to format.
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
            prompt = f"I used tools in reaction to: `{self.tool_executor.root_tool_query}`."
            prompt += "\n"
            prompt += f"Here are the tool calls: {message_tool_calls}."
            prompt += "\n"
            prompt += f"Here are the tool results: {tool_results}."
            prompt += "\n\n"
            
            if not is_final and limit_reason:
                prompt += f" However, I reached {limit_reason} ({self.tool_executor.current_tool_call_iteration} iterations)."
                prompt += "\n"
                prompt += "Provide a partial answer to the original question based on these partial results and ask if the user wants to continue processing."
            else:  # final response
                prompt += "Provide a final answer to the original question based on these complete results."
            
            prompt += "\n\n"
            prompt += "Adapt the the level of complexity and information in your answer to the the individual tool result."
            prompt += " Simple tool result leads to simple answer, while complex tool result lead to more details in the final answer."
                
            self.debug_log.info(f"Prompt for formatting:\n{prompt}")
            
            # Create a clean message history with just what we need for formatting
            clean_history = MessageHistory(self.debug_log)
            
            # Include the root query for context
            clean_history.add_user_message(self.tool_executor.root_tool_query)
            
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
            full_response, _, _ = await self.api_manager.stream_response(
                session, payload, clean_history, self.tool_executor, print_output=True, prefix=prefix, update_history=True
            )
            
            # Add the formatted response as an assistant message
            if full_response:
                self.history.add_assistant_message(full_response)
                    
        except Exception as e:
            response_type = "final" if is_final else "partial"
            full_response = f"Error formatting {response_type} response: {e}"
            self.debug_log.error(full_response)

        return full_response