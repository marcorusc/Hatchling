# Hatchling

![Hatchling Logo](./doc/resources/images/Logo/hatchling_wide_dark_bg_transparent.png)

Hatchling is an interactive CLI-based chat application that integrates local Large Language Models (LLMs) through [Ollama](https://ollama.ai/) with the [Model Context Protocol](https://github.com/modelcontextprotocol) (MCP) for tool calling capabilities. It is meant to be the frontend for using all MCP servers in Hatch!

## Project Update Summary

**June 27,2025**:

- Early June we held an internal hackathon centered on using *Hatchling*, developing and using MCP servers for analysis of biological data, building models and running the simulations. This helped identified some practical limits which we started solving.
- This time, we are releasing only the UI part of the update to give:
  - Syntax highlighting in the terminal for *Hatch!* and *Hatchling* commands
  - Prompts history with arrows up and down
  - Commands auto-completion
- After that we worked on the internal of the Hatch ecosystem to facilitate future updates. Deeply necessary but kinda boring, let's be honest!
- The general [roadmap](#roadmap) below is still up to date.

**May 27, 2025**: First release of the Hatch package manager ecosystem! 🎉

- The Hatch package manager is now **fully integrated into Hatchling** with built-in commands
- The package architecture for dynamic loading and switching of MCP servers is now complete
- [Related repositories](#related-repositories) established to support the pipeline.

## Features

- Interactive CLI-based chat interface
- Integration with Ollama API for local LLM support
- Ollama tool calling to MCP tools
- Tool execution wrapping to babysit LLMs into doing longer tool calling chains to do more work
- Appropriate citation of the source software wrapped in the MCP server whenever the LLM uses them

## Roadmap

- Support for vanilla MCP servers syntax (no wrapping in `HatchMCP`)
- Launching **Hatch! Biology** for hosting MCP servers providing access to well-established software and methods such as BLAST, UniProt (and other database) queries, PubMed articles, and such... All with citations!
- Customize LLMs system prompts, reference past messages, be in control of context history
- GUI for the chat and all management of the MCP servers
- User-defined tool chains

## Installation & Running

1. [Docker setup instructions](./doc/articles/docker-setup.md)

2. [Running Hatchling](./doc/articles/running_hatchling.md)

3. [In-chat commands](./doc/articles/chat_commands.md)


## Extending with your MCP Servers as *Hatch!* Packages

You can extend Hatchling with custom MCP tools by creating Hatch packages:

1. With Hatchling running, use

    ```txt
    hatch:create .local/<name> --description "Your description here"
    ```

    to populate a folder at directory `HATCH_LOCAL_PACKAGE_DIR/<name>`, where `HATCH_LOCAL_PACKAGE_DIR` is the environment variable   [you can set](./doc/articles/running_hatchling.md#configuration) in the `.env` file.

2. The `server.py` is the entry point of your MCP server.

3. Add a new tool:

    ```python
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

    Generally, you can define new tools using the `@hatch_mcp.tool()` decorator above a new function you added in the file. This follows the patterns from the [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)

4. You can add your package to your current *Hatch!* environment with:

   ```bash
   hatch:pkg:add .local/package
   ```

5. Run `enable_tools` command to have access to your *Hatch!* package in *Hatchling*

## Related Repositories

Hatchling is part of the larger Hatch ecosystem which includes:

- **[Hatch](https://github.com/CrackingShells/Hatch)**: The official package manager for the Hatch ecosystem, now fully integrated into Hatchling with built-in commands for MCP server management
  - Provides environment management for MCP server collections
  - Handles package installation from both local and registry sources
  - Template function to jump start new package development
- **[Hatch-Schemas](https://github.com/CrackingShells/Hatch-Schemas)**: Contains the JSON schemas for package metadata and validation
  - Includes schemas for both individual packages and the central registry
  - Provides versioned access to schemas via GitHub releases
  - Offers helper utilities for schema caching and updates
- **[Hatch-Validator](https://github.com/CrackingShells/Hatch-Validator)**: Validates packages against the schemas
  - Performs package validation against schema specifications
  - Resolves and validates package dependencies
  - Automatically fetches and manages schema versions
- **[Hatch-Registry](https://github.com/CrackingShells/Hatch-Registry)**: Package registry for Hatch packages
  - Maintains a centralized repository of available MCP server packages
  - Supports package versioning and dependency information
  - Provides search and discovery functionality
  - Ensures package integrity through metadata verification

These repositories work together to provide a comprehensive framework for creating, managing, and using MCP tools in Hatchling.
