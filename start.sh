#!/bin/bash

# LLM Council - Start script

echo "Starting LLM Council..."
echo ""

VENV_PYTHON="backend/.venv/bin/python"

if [ ! -x "$VENV_PYTHON" ]; then
    echo "No virtualenv found at backend/.venv"
    echo "Create it with: python3 -m venv backend/.venv && backend/.venv/bin/pip install -r requirements.txt"
    exit 1
fi

# Start backend
echo "Starting backend on http://localhost:8001..."
"$VENV_PYTHON" -m backend.main &
BACKEND_PID=$!

# Wait a bit for backend to start
sleep 2

# Start frontend
echo "Starting frontend on http://localhost:5173..."
cd frontend
npm run dev &
FRONTEND_PID=$!

echo ""
echo "✓ LLM Council is running!"
echo "  Backend:  http://localhost:8001"
echo "  Frontend: http://localhost:5173"
echo ""
echo "Press Ctrl+C to stop both servers"

# Wait for Ctrl+C
trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit" SIGINT SIGTERM
wait
