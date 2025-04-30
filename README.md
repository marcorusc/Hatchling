# Hatchling

![Hatchling Logo](./doc/resources/images/Logo/hatchling_wide_dark_bg_transparent.png)

Hatchling is an interactive CLI-based chat application that integrates local Large Language Models (LLMs) through [Ollama](https://ollama.ai/) with the [Model Context Protocol](https://github.com/modelcontextprotocol) (MCP) for tool calling capabilities. It is meant to be the frontend for using all MCP servers in Hatch!

## Notice

> [!WARNING]  
> **2025/04/25**: Hatchling is in its infancy, and several updates are coming quickly. In particular, Hatchling currently contains MCP servers directly in its codebase. This will soon evolve toward a package-based environment through additional repositories hosting MCP servers for different fields of science under the names **Hatch! XXX** (where XXX will be biology, chemistry, physics, mathematics, computer science, engineering, and so on).

## Features

- Interactive CLI-based chat interface
- Integration with Ollama API for local LLM support
- Ollama tool calling to MCP tools
- Tool execution wrapping to babysit LLMs into doing longer tool calling chains to do more work
- Appropriate citation of the source software wrapped in the MCP server whenever the LLM uses them

## Roadmap

- Package architecture for dynamic loading and switching of MCP servers
  - Connection to multiple mcp servers
  - Versioning
  - CI/CD to the repositories
  - Allow integration of Third-party MCP servers
- Launching **Hatch! Biology** for hosting MCP servers providing access to well-established software and methods such as BLAST, UniProt (and other database) queries, PubMed articles, and such... All with citations!
- Customize LLMs system prompts, reference past messages, be in control of context history
- GUI for the chat and all management of the MCP servers
- User-defined tool chains

## Prerequisites

- [Docker Desktop](https://docs.docker.com/desktop/) installed and configured with WSL2 (Windows) or running properly on your system (macOS/Linux)
- Recommended: GPU support configured for better performance with LLMs

## Installation & Running

Hatchling is designed to run with Docker for a consistent experience across platforms:

1. **Setup Docker and Ollama**:
   - Follow the [detailed Docker setup instructions](./doc/articles/docker-setup.md) to set up Docker Desktop and Ollama with GPU support (if available)

2. **Run Hatchling**:
   ```bash
   # From the docker directory in your project
   docker-compose run --rm hatchling
   ```

For complete installation and setup details, including GPU configuration, see our [Docker Setup Guide](./doc/articles/docker-setup.md).

## Configuration

Configuration is managed through environment variables or a `.env` file:

| Variable | Description | Default |
|----------|-------------|---------|
| `OLLAMA_API_URL` | URL for the Ollama API | `http://localhost:11434/api` |
| `DEFAULT_MODEL` | Default LLM model to use | `mistral-small3.1` |
| `MCP_SERVER_PATH` | Path to the MCP server script | `mcp_utils/servers/arithmetic.py` |
| `NETWORK_MODE` | Docker network mode | `host` (for Linux) |
| `LOG_LEVEL` | The default log level at start up | `INFO` |
| `LOG_FILE` | The path to the file where log entries will be saved (rolling 10 MB) | `__logs__/app.log` |

## Usage

### Running with Docker

```bash
# Basic usage
docker-compose -f docker/docker-compose.yml run --rm hatchling

# Specify a different model
docker-compose -f docker/docker-compose.yml run --rm -e DEFAULT_MODEL=llama2-uncensored hatchling

# Start with MCP server automatically and use a custom MCP server path
docker-compose -f docker/docker-compose.yml run --rm hatchling python app.py --start-mcp-server --mcp-server-path mcp_utils/servers/arithmetic.py
```

### Chat Commands

The following commands are available during chat:

- `help` - Display help for available commands
- `clear` - Clear the chat history
- `enable_tools` - Enable MCP tools
- `disable_tools` - Disable MCP tools
- `show_logs [n]` - Display session logs (optionally limited to last n entries)
- `set_log_level <level>` - Change log level (debug, info, warning, error, critical)
- `set_max_tool_call_iterations <n>` - Set maximum tool call iterations
- `set_max_working_time <seconds>` - Set maximum working time in seconds
- `exit` or `quit` - End the chat session

### Example Usage

```
Starting interactive chat with mistral-small3.1

=== Chat Commands ===
Type 'help' for this help message

Type 'clear' - Clear the chat history
Type 'disable_tools' - Disable MCP tools
Type 'enable_tools' - Enable MCP tools
Type 'exit' - End the chat session
Type 'help' - Display help for available commands
Type 'set_log_level' - Change log level. Usage: set_log_level <level>
Type 'set_max_tool_call_iterations' - Set max tool call iterations. Usage: set_max_tool_call_iterations <n>
Type 'set_max_working_time' - Set max working time in seconds. Usage: set_max_working_time <seconds>
Type 'show_logs' - Display session logs. Usage: show_logs [n]
======================

[Tools disabled] You: enable_tools
Tools enabled successfully!

[Tools enabled] You: What is 15 * 7?
Assistant: Let me calculate 15 * 7 for you. #<-- This line might be different for you

## DEBUG/INFO level log ##

[Using tool: multiply with arguments: {'a': 15.0, 'b': 7.0}]

## DEBUG/INFO level log ##

[Tool result: 105.0]

## DEBUG/INFO level log ##

Final response based on tool results:
The result of 15 multiplied by 7 is 105. #<-- This line might be different for you

<-- vvv This section below might be different for you vvv -->

### Citations
- ArithmeticTools
  Origin: Jacopin Eliott, "Origin: Example MCP Server for Hatch!", April 2025
  Implementation: Jacopin Eliott, "MCP: Example Arithmetic Tools for Hatch!", April 2025
```

## Extending with your MCP Servers

You can extend Hatchling with custom MCP tools by creating new server modules:

1. Create a new Python file in the `mcp_utils/servers/` directory
2. Define a new Hatch MCP server using:
   ```Python
   hatch_mcp = HatchMCP("NAME",
                   origin_citation="SOFTWARE ORIGIN",
                   mcp_citation="CREDITS for the MCP SERVER")
   ```
3. Define your MCP tools using the `@mcp.tool()` decorator
4. Run the application with your custom server path:
   ```bash
   docker-compose -f docker/docker-compose.yml run --rm hatchling python app.py --mcp-server-path mcp_utils/servers/your_custom_server.py --start-mcp-server
   ```

### Example Custom Tool
An example of MCP server implementing simple arithmetic tools is available [here](./mcp_utils/servers/arithmetic.py)

```python
from mcp.server.fastmcp import FastMCP
hatch_mcp = HatchMCP("NAME",
              origin_citation="SOFTWARE ORIGIN",
              mcp_citation="CREDITS for the MCP SERVER")

@hatch_mcp.tool()
def my_custom_tool(param1: str, param2: int) -> str:
    """Description of what your tool does.
    
    Args:
        param1 (str): First parameter description.
        param2 (int): Second parameter description.
        
    Returns:
        str: Description of the return value.
    """
    hatch_mcp.logger.info(f"Custom tool called with {param1} and {param2}")
    return f"Processed {param1} with value {param2}"

if __name__ == "__main__":
    hatch_mcp.run()
```

## Development

### Project Structure

- `app.py`: Main entry point
- `config/`: Configuration management
- `core/`: Core functionality
  - `chat/`: Chat system components
  - `llm/`: LLM integration logic
  - `logging/`: Logging system
- `mcp_utils/`: MCP tool utilities
  - `servers/`: MCP server implementations
- `ui/`: User interface components
- `docker/`: Docker configuration files