#!/usr/bin/env python3
import asyncio
import logging
import os
import argparse
from core.logging.logging_manager import logging_manager
from config.settings import ChatSettings
from ui.cli_chat import CLIChat
from mcp_utils.manager import mcp_manager

# Get logger with custom formatter - this takes advantage of our new implementation
log = logging_manager.get_session("AppMain", logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))                 

async def main():
    """Main entry point for the application.
    
    Handles command-line arguments, initializes the chat environment,
    and checks MCP servers availability.
    """
    parser = argparse.ArgumentParser(description='LLM with MCP Tool Calling')
    parser.add_argument('--start-mcp-server', action='store_true', help='Start the MCP server automatically')
    parser.add_argument('--mcp-server-path', type=str, default=os.environ.get("MCP_SERVER_PATH", "mcp_utils/servers/arithmetic.py"),
                        help='Path to the MCP server script (default: mcp_utils/servers/arithmetic.py)')
    parser.add_argument('--model', type=str, default=os.environ.get("DEFAULT_MODEL", "mistral-small3.1"),
                        help='Ollama model to use (default: mistral-small3.1)')
    args = parser.parse_args()
    
    try:
        mcp_server_path = None
        
        # Resolve the server path
        if not os.path.isabs(args.mcp_server_path):
            mcp_server_path = os.path.join(os.getcwd(), args.mcp_server_path)
        if not os.path.isfile(args.mcp_server_path):
            log.error(f"MCP server script not found: {args.mcp_server_path}")
            return
        
        # Start MCP server if requested
        if args.start_mcp_server:
            # Use the MCPManager to start the server
            process = await mcp_manager.start_server(mcp_server_path)
            if not process:
                log.error(f"Failed to start MCP server: {mcp_server_path}")
                return
        
        # Create settings with MCP server path
        settings = ChatSettings(default_model=args.model, mcp_server_urls=[mcp_server_path])
        
        log.info(f"Using MCP server script: {mcp_server_path}")
        
        # Create and run CLI chat interface
        cli_chat = CLIChat(settings)
        await cli_chat.initialize_and_run()
        
    except KeyboardInterrupt:
        log.info("Application interrupted by user")
    except Exception as e:
        log.error(f"Error in main application: {e}")
    finally:
        # Clean up MCP server process if we started one
        mcp_manager.stop_all_servers()

if __name__ == "__main__":
    # Run the application
    asyncio.run(main())