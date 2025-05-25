import logging
from typing import Tuple

from hatchling.core.logging.session_debug_log import SessionDebugLog
from hatchling.core.logging.logging_manager import logging_manager
from hatchling.mcp_utils.manager import mcp_manager
from hatchling.config.settings import ChatSettings


class BaseChatCommands:
    """Handles processing of command inputs in the chat interface."""

    def __init__(self, chat_session, settings: ChatSettings, debug_log: SessionDebugLog):
        """Initialize the command handler.
        
        Args:
            chat_session: The chat session this handler is associated with.
            settings (ChatSettings): The chat settings to use.
            debug_log (SessionDebugLog): Logger for command operations.
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
            'set_log_level': (self._cmd_set_log_level, "Change log level (debug, info, warning, error, critical). Usage: set_log_level <level>"),
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
    
    def _cmd_help(self, _: str) -> bool:
        """Display help information.
        
        Args:
            _ (str): Unused arguments.
            
        Returns:
            bool: True to continue the chat session.
        """
        self.print_commands_help()
        return True
    
    def _cmd_exit(self, _: str) -> bool:
        """Exit the chat session.
        
        Args:
            _ (str): Unused arguments.
            
        Returns:
            bool: False to end the chat session.
        """
        print("Ending chat session...")
        return False
    
    def _cmd_clear(self, _: str) -> bool:
        """Clear chat history.
        
        Args:
            _ (str): Unused arguments.
            
        Returns:
            bool: True to continue the chat session.
        """
        self.chat_session.history.clear()
        print("Chat history cleared!")
        return True
    
    def _cmd_show_logs(self, args: str) -> bool:
        """Display session logs.
        
        Args:
            args (str): Optional number of log entries to show.
            
        Returns:
            bool: True to continue the chat session.
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
            args (str): Log level name (debug, info, warning, error, critical).
            
        Returns:
            bool: True to continue the chat session.
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
            logging_manager.set_log_level(level_map[level_name])
            self.debug_log.info(f"Log level set to {level_name}")
            if logging_manager.log_level > logging.INFO:
                # the only place where use a print given the change of log level might disable the logger
                print(f"Log level set to {level_name}")
        else:
            self.debug_log.error(f"Unknown log level: {level_name}. Available levels are: debug, info, warning, error, critical")
        return True
    
    async def _cmd_enable_tools(self, _: str) -> bool:
        """Enable MCP tools.
        
        Args:
            _ (str): Unused arguments.
            
        Returns:
            bool: True to continue the chat session.
        """
        connected = await self.chat_session.initialize_mcp(self.settings.mcp_server_urls)
        if not connected:
            self.debug_log.error("Failed to connect to MCP servers. Tools not enabled.")
        else:
            self.debug_log.info("MCP tools enabled successfully!")
        return True
    
    async def _cmd_disable_tools(self, _: str) -> bool:
        """Disable MCP tools.
        
        Args:
            _ (str): Unused arguments.
            
        Returns:
            bool: True to continue the chat session.
        """
        if self.chat_session.tool_executor.tools_enabled:
            await mcp_manager.disconnect_all()
            self.chat_session.tool_executor.tools_enabled = False
            # Clear messages that might have tool-specific content
            self.chat_session.history.clear()
            self.debug_log.info("MCP tools disabled successfully!")
        else:
            self.debug_log.warning("MCP tools are already disabled.")
        return True
    
    def _cmd_set_max_iterations(self, args: str) -> bool:
        """Set maximum tool call iterations.
        
        Args:
            args (str): Number of iterations.
            
        Returns:
            bool: True to continue the chat session.
        """
        try:
            iterations = int(args.strip())
            if iterations > 0:
                self.settings.max_tool_call_iteration = iterations
                self.debug_log.info(f"Maximum tool call iterations set to {iterations}")
            else:
                self.debug_log.error("Maximum iterations must be greater than 0")
        except ValueError:
            self.debug_log.error("Invalid value for maximum iterations. Usage: set_max_tool_call_iterations <positive integer>")
        return True
    
    def _cmd_set_max_working_time(self, args: str) -> bool:
        """Set maximum working time for tool operations.
        
        Args:
            args (str): Time in seconds.
            
        Returns:
            bool: True to continue the chat session.
        """
        try:
            seconds = float(args.strip())
            if seconds > 0:
                self.settings.max_working_time = seconds
                self.debug_log.info(f"Maximum working time set to {seconds} seconds")
            else:
                self.debug_log.error("Maximum working time must be greater than 0")
        except ValueError:
            self.debug_log.error("Invalid value for maximum working time. Usage: set_max_working_time <positive number>")
        return True