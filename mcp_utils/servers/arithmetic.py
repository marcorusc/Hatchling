import logging
from mcp.server.fastmcp import FastMCP
from core.logging.logging_manager import logging_manager

# Get a logger from the logging_manager
log = logging_manager.get_session("MCPArithmeticTools",
                                  formatter=logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))


# Create MCP server
mcp = FastMCP("MCPArithmeticTools")

@mcp.tool()
def add(a: float, b: float) -> float:
    """Add two numbers together and return the result.
    
    Args:
        a: First number
        b: Second number
        
    Returns:
        Sum of a and b
    """
    log.info(f"Adding {a} + {b}")
    return a + b

@mcp.tool()
def subtract(a: float, b: float) -> float:
    """Subtract second number from first number and return the result.
    
    Args:
        a: First number
        b: Second number
        
    Returns:
        Difference (a - b)
    """
    log.info(f"Subtracting {a} - {b}")
    return a - b

@mcp.tool()
def multiply(a: float, b: float) -> float:
    """Multiply two numbers together and return the result.
    
    Args:
        a: First number
        b: Second number
        
    Returns:
        Product of a and b
    """
    log.info(f"Multiplying {a} * {b}")
    return a * b

@mcp.tool()
def divide(a: float, b: float) -> float:
    """Divide first number by second number and return the result.
    
    Args:
        a: First number (dividend)
        b: Second number (divisor)
        
    Returns:
        Quotient (a / b)
    """
    if b == 0:
        log.error("Division by zero attempted")
        raise ValueError("Cannot divide by zero")
    
    log.info(f"Dividing {a} / {b}")
    return a / b

if __name__ == "__main__":
    log.info("Starting MCP server with arithmetic tools")
    
    mcp.run()