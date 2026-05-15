@echo off
echo Starting EventBot MCP Server on http://0.0.0.0:8000/mcp ...
cd /d "%~dp0"
python server.py
pause
