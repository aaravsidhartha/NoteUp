#!/bin/bash
set -e
cd /app/backend/mcp_toolbox && python server.py &
cd /app/backend/agents/answer_agent && python agent.py &
cd /app/backend/agents/pdf_splitter && python agent.py &
sleep 5
cd /app/backend/api
exec uvicorn main:app --host 0.0.0.0 --port 8000
