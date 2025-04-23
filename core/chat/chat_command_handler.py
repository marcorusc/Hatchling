import logging
from typing import Tuple

from core.logging.session_debug_log import SessionDebugLog
from core.logging.logging_manager import logging_manager
from mcp_utils.manager import mcp_manager
from config.settings import ChatSettings


class ChatCommandHandler:
    """Handles processing of command inputs in the chat interface."""

    def __init__(self, chat_session, settings: ChatSettings, debug_log: SessionDebugLog):
        """Initialize the command handler.
        
        Args:
            chat_session: The chat session this handler is associated with
            settings (ChatSettings): The chat settings to use
            debug_log (SessionDebugLog): Logger for command operations
        """
        self.chat_session = chat_session
        self.settings = settings
        self.debug_log = debug_log
        self._register_commands()
        
    def _register_commands(self) -> None:
        """Register all available chat commands with their handlers."""
        # Commands that don't need async operations
        self.sync_commands = {
            'help': (self._cmd_help, "Display help for available commands"),
            'exit': (self._cmd_exit, "End the chat session"),
            'quit': (self._cmd_exit, "End the chat session"),
            'clear': (self._cmd_clear, "Clear the chat history"),
            'show_logs': (self._cmd_show_logs, "Display session logs. Usage: show_logs [n]"),
            'set_log_level': (self._cmd_set_log_level, "Change log level. Usage: set_log_level <level>"),
            'set_max_tool_call_iterations': (self._cmd_set_max_iterations, 
                                   "Set max tool call iterations. Usage: set_max_tool_call_iterations <n>"),
            'set_max_working_time': (self._cmd_set_max_working_time, 
                                   "Set max working time in seconds. Usage: set_max_working_time <seconds>"),
        }
        
        # Commands that need async operations
        self.async_commands = {
            'enable_tools': (self._cmd_enable_tools, "Enable MCP tools"),
            'disable_tools': (self._cmd_disable_tools, "Disable MCP tools"),
        }
        
    def print_commands_help(self) -> None:
        """Print help for all available chat commands."""
        print("\n=== Chat Commands ===")
        print("Type 'help' for this help message")
        print()
        
        # Combine all commands for display
        all_commands = {**self.sync_commands, **self.async_commands}
        
        # Group commands by functionality and print them
        for cmd_name, (_, description) in sorted(all_commands.items()):
            # Skip duplicates like 'quit' which is same as 'exit'
            if cmd_name in ['quit']:
                continue
            print(f"Type '{cmd_name}' - {description}")
            
        print("======================\n")
    
    async def process_command(self, user_input: str) -> Tuple[bool, bool]:
        """Process a potential command from user input.
        
        Args:
            user_input (str): The user's input text
            
        Returns:
            Tuple[bool, bool]: (is_command, should_continue)
              - is_command: True if input was a command
              - should_continue: False if chat session should end
        """
        user_input = user_input.strip()
        
        # Handle empty input
        if not user_input:
            return True, True
            
        # Extract command and arguments
        parts = user_input.split(' ', 1)
        command = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""
        
        # Check if the input is a registered command
        if command in self.sync_commands:
            handler_func, _ = self.sync_commands[command]
            return True, handler_func(args)
        elif command in self.async_commands:
            async_handler_func, _ = self.async_commands[command]
            return True, await async_handler_func(args)
            
        # Not a command
        return False, True
    
    def _cmd_help(self, _: str) -> bool:
        """Display help information.
        
        Args:
            _ (str): Unused arguments
            
        Returns:
            bool: True to continue the chat session
        """
        self.print_commands_help()
        return True
    
    def _cmd_exit(self, _: str) -> bool:
        """Exit the chat session.
        
        Args:
            _ (str): Unused arguments
            
        Returns:
            bool: False to end the chat session
        """
        print("Ending chat session...")
        return False
    
    def _cmd_clear(self, _: str) -> bool:
        """Clear chat history.
        
        Args:
            _ (str): Unused arguments
            
        Returns:
            bool: True to continue the chat session
        """
        self.chat_session.history.clear()
        print("Chat history cleared!")
        return True
    
    def _cmd_show_logs(self, args: str) -> bool:
        """Display session logs.
        
        Args:
            args (str): Optional number of log entries to show
            
        Returns:
            bool: True to continue the chat session
        """
        try:
            logs_to_show = int(args) if args.strip() else None
            print(self.chat_session.debug_log.get_logs(logs_to_show))
        except ValueError:
            print(f"Invalid number: {args}")
            print("Usage: show_logs [n]")
        return True
    
    def _cmd_set_log_level(self, args: str) -> bool:
        """Set the log level.
        
        Args:
            args (str): Log level name (debug, info, warning, error, critical)
            
        Returns:
            bool: True to continue the chat session
        """
        level_name = args.strip().lower()
        level_map = {
            "debug": logging.DEBUG,
            "info": logging.INFO,
            "warning": logging.WARNING,
            "error": logging.ERROR,
            "critical": logging.CRITICAL
        }
        
        if level_name in level_map:
            logging_manager.set_cli_log_level(level_map[level_name])
            self.debug_log.info(f"Log level set to {level_name}")
            print(f"Log level set to {level_name}")
        else:
            self.debug_log.error(f"Unknown log level: {level_name}")
            print(f"Unknown log level: {level_name}")
            print("Available levels: debug, info, warning, error, critical")
        return True
    
    async def _cmd_enable_tools(self, _: str) -> bool:
        """Enable MCP tools.
        
        Args:
            _ (str): Unused arguments
            
        Returns:
            bool: True to continue the chat session
        """
        connected = await self.chat_session.initialize_mcp(self.settings.mcp_server_urls)
        if not connected:
            self.debug_log.error("Failed to connect to MCP servers. Tools not enabled.")
            print("Failed to connect to MCP servers. Tools not enabled.")
        else:
            print("Tools enabled successfully!")
        return True
    
    async def _cmd_disable_tools(self, _: str) -> bool:
        """Disable MCP tools.
        
        Args:
            _ (str): Unused arguments
            
        Returns:
            bool: True to continue the chat session
        """
        if self.chat_session.tool_executor.tools_enabled:
            await mcp_manager.disconnect_all()
            self.chat_session.tool_executor.tools_enabled = False
            # Clear messages that might have tool-specific content
            self.chat_session.history.clear()
            print("Tools disabled.")
        else:
            print("Tools were not enabled.")
        return True
    
    def _cmd_set_max_iterations(self, args: str) -> bool:
        """Set maximum tool call iterations.
        
        Args:
            args (str): Number of iterations
            
        Returns:
            bool: True to continue the chat session
        """
        try:
            iterations = int(args.strip())
            if iterations > 0:
                self.settings.max_tool_call_iteration = iterations
                self.debug_log.info(f"Maximum tool call iterations set to {iterations}")
                print(f"Maximum tool call iterations set to {iterations}")
            else:
                self.debug_log.error("Maximum iterations must be greater than 0")
                print("Maximum iterations must be greater than 0")
        except ValueError:
            self.debug_log.error("Invalid value for maximum iterations")
            print("Usage: set_max_tool_call_iterations <positive integer>")
        return True
    
    def _cmd_set_max_working_time(self, args: str) -> bool:
        """Set maximum working time for tool operations.
        
        Args:
            args (str): Time in seconds
            
        Returns:
            bool: True to continue the chat session
        """
        try:
            seconds = float(args.strip())
            if seconds > 0:
                self.settings.max_working_time = seconds
                self.debug_log.info(f"Maximum working time set to {seconds} seconds")
                print(f"Maximum working time set to {seconds} seconds")
            else:
                self.debug_log.error("Maximum working time must be greater than 0")
                print("Maximum working time must be greater than 0")
        except ValueError:
            self.debug_log.error("Invalid value for maximum working time")
            print("Usage: set_max_working_time <positive number>")
        return True