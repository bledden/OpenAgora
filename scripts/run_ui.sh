#!/bin/bash
# AgentBazaar UI Startup Script
# Runs both the FastAPI backend and React frontend

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "======================================"
echo "    AgentBazaar UI Startup"
echo "======================================"
echo ""

# Check for required env vars
if [ -z "$THESYS_API_KEY" ] && [ ! -f "$PROJECT_ROOT/.env" ]; then
    echo "Warning: THESYS_API_KEY not found in environment or .env"
    echo "The Generative UI features will not work without it."
    echo ""
fi

# Activate venv if it exists
if [ -d "$PROJECT_ROOT/venv" ]; then
    echo "Activating Python venv..."
    source "$PROJECT_ROOT/venv/bin/activate"
fi

# Install Python dependencies
echo "Installing Python dependencies..."
cd "$PROJECT_ROOT"
pip install -e . --quiet

# Start FastAPI backend
echo ""
echo "Starting FastAPI backend on http://localhost:8000..."
cd "$PROJECT_ROOT/src"
uvicorn bazaar.api:app --host 0.0.0.0 --port 8000 --reload &
BACKEND_PID=$!
echo "Backend PID: $BACKEND_PID"

# Give backend time to start
sleep 2

# Install and start frontend
echo ""
echo "Starting React frontend on http://localhost:3000..."
cd "$PROJECT_ROOT/ui"

if [ ! -d "node_modules" ]; then
    echo "Installing dependencies with bun..."
    bun install
fi

bun run dev &
FRONTEND_PID=$!
echo "Frontend PID: $FRONTEND_PID"

echo ""
echo "======================================"
echo "    AgentBazaar is running!"
echo "======================================"
echo ""
echo "  Frontend:  http://localhost:3000"
echo "  Backend:   http://localhost:8000"
echo "  API Docs:  http://localhost:8000/docs"
echo ""
echo "Press Ctrl+C to stop both servers"
echo ""

# Handle shutdown
cleanup() {
    echo ""
    echo "Shutting down..."
    kill $BACKEND_PID 2>/dev/null || true
    kill $FRONTEND_PID 2>/dev/null || true
    exit 0
}

trap cleanup SIGINT SIGTERM

# Wait for processes
wait
