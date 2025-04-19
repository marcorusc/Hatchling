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
    """Add two numbers together.
    
    Args:
        a (float): First number.
        b (float): Second number.
        
    Returns:
        float: Sum of a and b.
    """
    log.info(f"Adding {a} + {b}")
    return a + b

@mcp.tool()
def subtract(a: float, b: float) -> float:
    """Subtract second number from first number.
    
    Args:
        a (float): First number.
        b (float): Second number.
        
    Returns:
        float: Difference (a - b).
    """
    log.info(f"Subtracting {a} - {b}")
    return a - b

@mcp.tool()
def multiply(a: float, b: float) -> float:
    """Multiply two numbers together.
    
    Args:
        a (float): First number.
        b (float): Second number.
        
    Returns:
        float: Product of a and b.
    """
    log.info(f"Multiplying {a} * {b}")
    return a * b

@mcp.tool()
def divide(a: float, b: float) -> float:
    """Divide first number by second number.
    
    Args:
        a (float): First number (dividend).
        b (float): Second number (divisor).
        
    Returns:
        float: Quotient (a / b).
        
    Raises:
        ValueError: If the divisor (b) is zero.
    """
    if b == 0:
        log.error("Division by zero attempted")
        raise ValueError("Cannot divide by zero")
    
    log.info(f"Dividing {a} / {b}")
    return a / b

if __name__ == "__main__":
    log.info("Starting MCP server with arithmetic tools")
    
    mcp.run()