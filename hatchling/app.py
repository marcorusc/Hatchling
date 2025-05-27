import asyncio
import logging
import os
import argparse
import sys
from hatchling.core.logging.logging_manager import logging_manager
from hatchling.config.settings import ChatSettings
from hatchling.ui.cli_chat import CLIChat

# Get logger with custom formatter - this takes advantage of our new implementation
log = logging_manager.get_session("AppMain", logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))                 

async def main_async():
    """
    Main entry point for the application.
    """
    try:
        # Create settings with MCP server path
        settings = ChatSettings()
        
        # Create and run CLI chat interface
        cli_chat = CLIChat(settings)
        
        await cli_chat.initialize_and_run()
        
        return 0
        
    except KeyboardInterrupt:
        log.info("Application interrupted by user")
    except Exception as e:
        log.error(f"Error in main application: {e}")

def main():
    """Entry point function that runs the async main function."""
    return asyncio.run(main_async())

if __name__ == "__main__":
    # Run the application
    sys.exit(main())