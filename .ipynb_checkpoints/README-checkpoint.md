Viola Chatbot (SPA + FastAPI)

This is a minimal starter that serves a plain HTML/JS/CSS single-page app and a FastAPI backend with a mocked token endpoint.

Quick start (Windows PowerShell):

# Create and activate venv
python -m venv .venv; .\.venv\Scripts\Activate.ps1

# Install deps
python -m pip install -r requirements.txt

# Run server
python main.py

Open http://127.0.0.1:8000 in your browser.

Notes:
- Token creation is mocked at GET /api/token
- Chat endpoint: POST /api/chat with body { messages: [{role, content}], token }
