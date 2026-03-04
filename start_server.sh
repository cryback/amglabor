#!/bin/bash
# Start AMG Labor Dashboard Server

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

PID_FILE="$SCRIPT_DIR/server.pid"
LOG_FILE="$SCRIPT_DIR/server.log"
PORT=8102

# Check if already running
if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    if ps -p $PID > /dev/null 2>&1; then
        echo "✅ Labor dashboard already running (PID: $PID)"
        echo "📊 Access at: http://localhost:$PORT"
        exit 0
    fi
fi

# Kill any existing server on this port
pkill -f "python.*SimpleHTTPServer.*$PORT" 2>/dev/null
pkill -f "python.*http.server.*$PORT" 2>/dev/null
sleep 1

# Start Python HTTP server
echo "🚀 Starting AMG Labor Dashboard Server on port $PORT..."
python3 -m http.server $PORT > "$LOG_FILE" 2>&1 &
echo $! > "$PID_FILE"

sleep 2

if ps -p $(cat "$PID_FILE") > /dev/null 2>&1; then
    echo "✅ Server started successfully (PID: $(cat $PID_FILE))"
    echo "📊 Dashboard: http://localhost:$PORT"
    echo "📝 Logs: $LOG_FILE"
else
    echo "❌ Failed to start server"
    cat "$LOG_FILE"
    exit 1
fi
