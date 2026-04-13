#!/bin/bash

# Check if the backend is running
if ! curl -s http://localhost:8000/api/status > /dev/null; then
    echo "Backend is not running. Starting backend..."
    ./scripts/run_backend.sh &
    sleep 5
fi

bun run dev