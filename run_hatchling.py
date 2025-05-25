#!/usr/bin/env python3
"""
Launcher script for Hatchling.

This script allows running the application directly from the repository
without installing it as a package.
"""
import sys
import os
from pathlib import Path

# Add the parent directory to Python path to make the hatchling package importable
sys.path.insert(0, str(Path(__file__).resolve().parent))

from hatchling.app import main

if __name__ == "__main__":
    sys.exit(main())
