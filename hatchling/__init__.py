"""
Hatchling - LLM with MCP Tool Calling

This package provides a CLI interface for interacting with LLMs 
with MCP Tool Calling capabilities.
"""

# from importlib.metadata import version
# __version__ = version("hatchling")

from hatchling.mcp_utils.hatch_mcp import HatchMCP

__all__ = [
    'HatchMCP',
]