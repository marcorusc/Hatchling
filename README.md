# Hatchling

Hatchling is an interactive CLI-based chat application that integrates local Large Language Models (LLMs) through [Ollama](https://ollama.ai/) with the [Model Context Protocol](https://github.com/modelcontextprotocol) (MCP) for tool calling capabilities.

## Notice

2025/04/25: Hatchling is in its infancy and several updates are quickly. In particular, Hatchling currently contains MCP servers directly in its code base. This will very soon evolve toward a packages environment through additional repositories hosting MCP servers for different fields of science under the names **Hatch! XXX** (where XXX will be biology, chemistry, physics, mathematics, computer science, engineering, and so on).

## Features

- Interactive CLI-based chat interface
- Integration with Ollama API for local LLM support
- MCP tool calling capabilities
- Tool execution wrapping to babysit LLMs into doing longer tool chains to do more work

## Roadmap
- Guarentee of appropriate citation of the source software wrapped in the MCP server
- MCP servers package architecture for dynamic loading and switching of MCP servers
- Launching **Hatch! Biology** for hosting MCP servers providing access to well-established software and methods such as BLAST, UniProt (and other database) queries, PubMed articles, and such... All with citations!
- Customize LLMs system prompts, reference past messages, be in control of context history
- GUI for the chat and all management of the MCP servers
- User-defined tool chains


## Prerequisites

- [Ollama](https://ollama.ai/) installed and running locally
- [Docker](https://docs.docker.com/desktop/) (recommended for simplest setup), for [Window](https://docs.docker.com/desktop/setup/install/windows-install/), [Mac](https://docs.docker.com/desktop/setup/install/mac-install/), [Linux](https://docs.docker.com/desktop/setup/install/linux/)
- Python 3.9+ (for non-Docker installation)

## Ollama Setup

Before using Hatchling, you need to have Ollama running with the required models:

### Installing Ollama

1. Install Ollama by following the instructions at [ollama.ai](https://ollama.ai)
2. Start the Ollama service:
   ```bash
   ollama serve
   ```

### Pulling Required Models

Pull the default model (or any model you plan to use):

```bash
# Pull the default model
ollama pull mistral-small3.1

# Or pull other models
ollama pull llama2-uncensored
```

### Using Ollama with Docker

If you're using Docker for both Ollama and Hatchling:

1. Run Ollama in a container:
   ```bash
   docker run -d --gpus=all -v ollama:/root/.ollama -p 11434:11434 --name ollama ollama/ollama
   ```

2. Pull models in the Ollama container:
   ```bash
   docker exec -it ollama ollama pull mistral-small3.1
   ```

3. Configure Hatchling to connect to this Ollama instance:
   - For Linux:
     - `NETWORK_MODE=host`
   - For macOS/Windows:
     - `NETWORK_MODE=` (empty string)

## Installation & Running

### Option 1: Docker (Recommended)

The easiest and most reliable way to run Hatchling is with Docker:
1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/hatchling.git
   cd hatchling
   ```

2. Build the Docker image:
   ```bash
   docker-compose -f docker/docker-compose.yml build
   ```

3. Run the container:
   ```bash
   docker-compose -f docker/docker-compose.yml run --rm hatchling
   ```

### Option 2: Python Environment

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/hatchling.git
   cd hatchling
   ```

2. Create and activate an environment. Via Conda:
   ```bash
   conda create -n forHatchling python=3.12
   conda activate forHatchling
   ```
   OR, via Python native environment
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Install the package in development mode:
   ```bash
   pip install -e .
   ```

5. Run the application:
   ```bash
   python app.py
   ```

## Configuration

Configuration is managed through environment variables or a `.env` file:

| Variable | Description | Default |
|----------|-------------|---------|
| `OLLAMA_API_URL` | URL for the Ollama API | `http://localhost:11434/api` |
| `DEFAULT_MODEL` | Default LLM model to use | `mistral-small3.1` |
| `MCP_SERVER_PATH` | Path to the MCP server script | `mcp_utils/servers/arithmetic.py` |
| `NETWORK_MODE` | Docker network mode | `host` (for Linux) |

### Docker-Specific Configuration

When running with Docker, you can modify the environment variables:

```bash
# Set environment variables before running
export OLLAMA_API_URL=http://host.docker.internal:11434/api
export DEFAULT_MODEL=llama2-uncensored
docker-compose -f docker/docker-compose.yml up
```

Or modify the `.env` file in the project root.

## Usage

### Running with Docker

When using Docker, you can pass the same parameters through environment variables or by overriding the command:

```bash
# Basic usage
docker-compose -f docker/docker-compose.yml run --rm hatchling

# Specify a different model
docker-compose -f docker/docker-compose.yml run --rm -e DEFAULT_MODEL=llama2-uncensored hatchling

# Start with MCP server automatically and use a custom MCP server path
docker-compose -f docker/docker-compose.yml run --rm hatchling python app.py --start-mcp-server --mcp-server-path mcp_utils/servers/arithmetic.py

```

### Running the Application

```bash
# Basic usage
python app.py

# Specify a different model
python app.py --model llama2-uncensored

# Start with MCP server automatically
python app.py --start-mcp-server

# Custom MCP server path
python app.py --mcp-server-path path/to/your/mcp_server.py
```

For more complex configurations, you can create a custom `.env` file or modify the docker-compose.yml file to include your preferred settings.

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

The result of 15 × 7 is 105. #<-- This line might be different for you
```

## Extending with Custom Tools

You can extend Hatchling with custom MCP tools by creating new server modules:

1. Create a new Python file in the `mcp_utils/servers/` directory
2. Define your MCP tools using the `@mcp.tool()` decorator
3. Run the application with your custom server path:
   ```bash
   python app.py --mcp-server-path mcp_utils/servers/your_custom_server.py --start-mcp-server
   ```

### Example Custom Tool

```python
from mcp.server.fastmcp import FastMCP
from core.logging.logging_manager import logging_manager

log = logging_manager.get_session("CustomTools")
mcp = FastMCP("CustomTools")

@mcp.tool()
def my_custom_tool(param1: str, param2: int) -> str:
    """Description of what your tool does.
    
    Args:
        param1 (str): First parameter description.
        param2 (int): Second parameter description.
        
    Returns:
        str: Description of the return value.
    """
    log.info(f"Custom tool called with {param1} and {param2}")
    return f"Processed {param1} with value {param2}"

if __name__ == "__main__":
    mcp.run()
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