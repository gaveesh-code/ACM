#!/bin/bash
echo "🚀 Starting Autonomous Constellation Manager..."
cd /app/backend
python3 -m uvicorn main:app --host 0.0.0.0 --port 8000