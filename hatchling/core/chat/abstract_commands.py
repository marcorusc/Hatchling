"""Abstract commands module for the chat interface.

This module provides the AbstractCommands base class that defines the common structure
and shared functionality for all command handlers in the chat interface.
"""

import logging
from abc import ABC, abstractmethod
from typing import Dict, Any

from hatchling.core.logging.session_debug_log import SessionDebugLog
from hatchling.config.settings import ChatSettings

from hatch import HatchEnvironmentManager


class AbstractCommands(ABC):
    """Abstract base class for chat command handlers.
    
    This class defines the common structure and shared functionality that all
    command handlers should implement. Subclasses must implement the abstract
    methods to define their specific commands and behavior.
    """

    def __init__(self, chat_session, settings: ChatSettings, env_manager: HatchEnvironmentManager, debug_log: SessionDebugLog):
        """Initialize the command handler.
        
        Args:
            chat_session: The chat session this handler is associated with.
            settings (ChatSettings): The chat settings to use.
            env_manager (HatchEnvironmentManager): The Hatch environment manager.
            debug_log (SessionDebugLog): Logger for command operations.
        """
        self.chat_session = chat_session
        self.settings = settings
        self.env_manager = env_manager
        self.logger = debug_log
        
        # Initialize the commands dictionary
        self.commands = {}
        
        # Initialize the command registry
        self._register_commands()
        
        # Keep old format for backward compatibility
        self.sync_commands = {}
        self.async_commands = {}
        
        # Populate legacy command dictionaries
        self._build_legacy_commands()

    @abstractmethod
    def _register_commands(self) -> None:
        """Register all available commands with their handlers.
        
        Subclasses must implement this method to define their specific commands
        in the standardized format.
        """
        pass

    def _build_legacy_commands(self) -> None:
        """Build legacy command dictionaries for backward compatibility."""
        for cmd_name, cmd_info in self.commands.items():
            if cmd_info['is_async']:
                self.async_commands[cmd_name] = (cmd_info['handler'], cmd_info['description'])
            else:
                self.sync_commands[cmd_name] = (cmd_info['handler'], cmd_info['description'])

    @abstractmethod
    def print_commands_help(self) -> None:
        """Print help for all available commands.
        
        Subclasses should implement this method to provide appropriate help text
        for their command set.
        """
        # Group commands by functionality and print them
        for cmd_name, cmd_info in sorted(self.commands.items()):
            print(f"Type '{cmd_name}' - {cmd_info['description']}")

    def _print_command_help(self, command: str) -> None:
        """Print help for a specific command.
        
        Args:
            command (str): The command to print help for.
        """
        if command in self.commands:
            cmd_info = self.commands[command]
            print(f"{command}: {cmd_info['description']}")
        else:
            print(f"No help available for command: {command}")

    def _parse_args(self, args_str: str, arg_defs: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        """Parse command arguments from a string.
        
        Args:
            args_str (str): The argument string to parse.
            arg_defs (Dict): Definitions of arguments to parse, including default values.
            
        Returns:
            Dict[str, Any]: Parsed arguments.
        """
        result = {}
        
        # Initialize with defaults
        for arg_name, arg_def in arg_defs.items():
            if 'default' in arg_def:
                result[arg_name] = arg_def['default']
        
        # Split by spaces, but respect quoted strings
        parts = []
        current_part = ""
        in_quotes = False
        quote_char = None
        
        for char in args_str:
            if char in ['"', "'"]:
                if not in_quotes:
                    in_quotes = True
                    quote_char = char
                elif char == quote_char:
                    in_quotes = False
                    quote_char = None
                else:
                    current_part += char
            elif char.isspace() and not in_quotes:
                if current_part:
                    parts.append(current_part)
                    current_part = ""
            else:
                current_part += char
                
        if current_part:
            parts.append(current_part)
        
        # Process positional and named arguments
        positionals = [arg_name for arg_name, arg_def in arg_defs.items() if arg_def.get('positional', False)]
        positional_idx = 0
        
        i = 0
        while i < len(parts):
            part = parts[i]
            
            # Handle named arguments (--arg or -a style)
            if part.startswith('--') or (part.startswith('-') and len(part) == 2):
                arg_name = part.lstrip('-')
                
                # Find the actual argument name if it's an alias
                for name, arg_def in arg_defs.items():
                    if arg_name == name or arg_name in arg_def.get('aliases', []):
                        arg_name = name
                        break
                
                # Check if this argument expects a value
                if i + 1 < len(parts) and not parts[i+1].startswith('-'):
                    result[arg_name] = parts[i+1]
                    i += 2
                else:
                    # Flag argument (boolean)
                    result[arg_name] = True
                    i += 1
            else:
                # Handle positional arguments
                if positional_idx < len(positionals):
                    result[positionals[positional_idx]] = part
                    positional_idx += 1
                i += 1
        
        return result
    
    def get_command_metadata(self) -> dict:
        """Get metadata for all registered commands for autocompletion.
        
        Returns:
            dict: Dictionary containing command metadata with the new standardized format
        """
        return self.commands
