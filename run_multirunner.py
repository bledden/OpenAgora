#!/usr/bin/env python3
"""
Standalone entry point for the multi-runner service.
Use this as the Railway start command: python run_multirunner.py
"""
import sys
import os
import asyncio

# Ensure src is in the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

# Run the multi-runner
from agents.multi_runner.runner import main

if __name__ == "__main__":
    asyncio.run(main())
