from setuptools import setup, find_packages

# Import version from dedicated version file
import os

def get_version() -> str:
    """Get the package version from the VERSION file or fallback to a default.
    
    Returns:
        str: The package version.
    """
    # Option 1: Read from a VERSION file
    if os.path.exists('VERSION'):
        with open('VERSION', 'r') as f:
            return f.read().strip()
    
    # Option 3: Fall back to default version
    return "0.1"

setup(
    name="hatchling",
    version=get_version(),
    packages=find_packages(),
)