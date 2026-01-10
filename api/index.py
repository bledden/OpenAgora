"""Vercel serverless handler for AgentBazaar API."""

import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from mangum import Mangum
from bazaar.api import app

# Mangum adapter for ASGI -> AWS Lambda/Vercel
handler = Mangum(app, lifespan="off")
