#!/bin/bash
# Development server runner for AI Control Layer
# Starts control layer, demo agent, and frontend in background processes

set +e
export PYTHONUTF8=1
export PYTHONIOENCODING=utf-8

echo "=== AI Control Layer Development Servers ==="

cleanup() {
    echo ""
    echo "Cleaning up processes..."
    if [ ! -z "$PID_CONTROL" ]; then
        kill $PID_CONTROL 2>/dev/null || true
        echo "  Stopped Control Layer (PID: $PID_CONTROL)"
    fi
    if [ ! -z "$PID_AGENT" ]; then
        kill $PID_AGENT 2>/dev/null || true
        echo "  Stopped Demo Agent (PID: $PID_AGENT)"
    fi
    if [ ! -z "$PID_FRONTEND" ]; then
        kill $PID_FRONTEND 2>/dev/null || true
        echo "  Stopped Frontend (PID: $PID_FRONTEND)"
    fi
    exit 0
}

trap cleanup SIGINT SIGTERM

# Start Control Layer (port 8080)
echo ""
echo "[1/3] Starting Control Layer on :8080..."
cd Backend
python -m uvicorn control_layer.presentation.main:app \
    --host 0.0.0.0 --port 8080 --workers 1 > /tmp/control_layer.log 2>&1 &
PID_CONTROL=$!
cd ..
echo "  ✓ Control Layer PID: $PID_CONTROL"

# Start Demo Agent (port 8090)
echo ""
echo "[2/3] Starting Demo Agent on :8090..."
cd Backend
python -m uvicorn demo_agent.main:app --port 8090 > /tmp/demo_agent.log 2>&1 &
PID_AGENT=$!
cd ..
echo "  ✓ Demo Agent PID: $PID_AGENT"

# Start Frontend (port 5173)
echo ""
echo "[3/3] Starting Frontend on :5173..."
cd Frontent
npm run dev > /tmp/frontend.log 2>&1 &
PID_FRONTEND=$!
cd ..
echo "  ✓ Frontend PID: $PID_FRONTEND"

# Display running URLs
echo ""
echo "=== Running Services ==="
echo "  Control Layer: http://localhost:8080/health"
echo "  Demo Agent:    http://localhost:8090/agent/health"
echo "  Dashboard:     http://localhost:5173"

echo ""
echo "Press Ctrl+C to stop all services..."
echo "  Control Layer log: /tmp/control_layer.log"
echo "  Demo Agent log:    /tmp/demo_agent.log"
echo "  Frontend log:      /tmp/frontend.log"

# Wait for any process to exit
wait
cleanup
