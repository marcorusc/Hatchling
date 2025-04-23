import asyncio
import aiohttp
import logging
from typing import Optional

from core.logging.logging_manager import logging_manager
from config.settings import ChatSettings
from core.llm.model_manager import ModelManager
from core.llm.chat_session import ChatSession
from core.chat.chat_command_handler import ChatCommandHandler
from mcp_utils.manager import mcp_manager

class CLIChat:
    """Command-line interface for chat functionality."""
    
    def __init__(self, settings: ChatSettings):
        """Initialize the CLI chat interface.
        
        Args:
            settings (ChatSettings): The chat settings to use.
            debug_log (Optional[SessionDebugLog]): Logger for debugging information. Defaults to None.
        """
        self.settings = settings
        
        # Create a debug log if not provided
        self.debug_log = logging_manager.get_session("CLIChat",
                                formatter=logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
            
        # Create the model manager
        self.model_manager = ModelManager(settings, self.debug_log)
        
        # Chat session will be initialized during startup
        self.chat_session = None
        self.cmd_handler = None
    
    async def initialize(self) -> bool:
        """Initialize the chat environment.
        
        Returns:
            bool: True if initialization was successful.
        """
        # Check if Ollama service is available
        available, message = await self.model_manager.check_ollama_service()
        if not available:
            self.debug_log.error(message)
            self.debug_log.error(f"Please ensure the Ollama service is running at {self.settings.ollama_api_url} before running this script.")
            return False
        
        self.debug_log.info(message)
        
        # Check if MCP server is available
        self.debug_log.info("Checking MCP server availability...")
        mcp_available = await mcp_manager.initialize(self.settings.mcp_server_urls)
        
        if mcp_available:
            self.debug_log.info("MCP server is available! Tool calling is ready to use.")
            self.debug_log.info("You can enable tools during the chat session by typing 'enable_tools'")
            # Disconnect after checking
            await mcp_manager.disconnect_all()
        else:
            self.debug_log.warning("MCP server is not available. You can start the MCP server by running:")
            self.debug_log.warning("python mcp_server_test.py")
            self.debug_log.warning("Continuing without MCP tools...")
            
        # Initialize chat session
        self.chat_session = ChatSession(self.settings)
        
        # Initialize command handler
        self.cmd_handler = ChatCommandHandler(self.chat_session, self.settings, self.debug_log)
        
        return True
    
    async def check_and_pull_model(self, session: aiohttp.ClientSession) -> bool:
        """Check if the model is available and pull it if necessary.
        
        Args:
            session (aiohttp.ClientSession): The session to use for API calls.
            
        Returns:
            bool: True if model is available (either already or after pulling).
        """
        try:
            # Check if model is available
            is_model_available = await self.model_manager.check_availability(session, self.settings.default_model)
            
            if is_model_available:
                self.debug_log.info(f"Model {self.settings.default_model} is already pulled.")
                return True
            else:
                self.debug_log.info(f"Pulling model {self.settings.default_model}...")
                await self.model_manager.pull_model(session, self.settings.default_model)
                return True
        except Exception as e:
            self.debug_log.error(f"Error checking/pulling model: {e}")
            return False
    
    async def start_interactive_session(self) -> None:
        """Run an interactive chat session with message history."""
        if not self.chat_session or not self.cmd_handler:
            self.debug_log.error("Chat session not initialized. Call initialize() first.")
            return
        
        self.debug_log.info(f"Starting interactive chat with {self.settings.default_model}")
        self.cmd_handler.print_commands_help()
        
        async with aiohttp.ClientSession() as session:
            # Check and pull the model if needed
            if not await self.check_and_pull_model(session):
                self.debug_log.error("Failed to ensure model availability")
                return
            
            # Start the interactive chat loop
            while True:
                try:
                    # Get user input
                    status = "[Tools enabled]" if self.chat_session.tool_executor.tools_enabled else "[Tools disabled]"
                    user_message = input(f"{status} You: ")
                    
                    # Process as command if applicable
                    is_command, should_continue = await self.cmd_handler.process_command(user_message)
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
                    await self.chat_session.send_message(user_message, session)
                    print()  # Add an extra newline for readability
                    
                except KeyboardInterrupt:
                    print("\nInterrupted. Ending chat session...")
                    break
                except Exception as e:
                    self.debug_log.error(f"Error: {e}")
                    print(f"\nError: {e}")
    
    async def initialize_and_run(self) -> None:
        """Initialize the environment and run the interactive chat session."""
        try:
            # Initialize the chat environment
            if not await self.initialize():
                return
            
            # Start the interactive session
            await self.start_interactive_session()
            
        except Exception as e:
            error_msg = f"An error occurred: {e}"
            self.debug_log.error(error_msg)
            return
        
        finally:
            # Clean up any remaining MCP server processes
            await mcp_manager.disconnect_all()