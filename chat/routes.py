from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from chat.assistant.assistant import generate_response
import secrets

router = APIRouter()

class Message(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    messages: List[Message]
    token: Optional[str] = None
    model: Optional[str] = "deepseek-r1"
    topic: Optional[str] = ""
    tutor_tools: Optional[List[str]] = []
    use_rag: Optional[bool] = False

class ChatResponse(BaseModel):
    reply: str
    status: str = "success"

class TokenResponse(BaseModel):
    token: str
    expires_in: int = 3600

class StartupMessageResponse(BaseModel):
    reply: str
    status: str = "success"

@router.get("/token")
async def create_token():
    """Mock token endpoint for frontend authentication"""
    token = secrets.token_urlsafe(32)
    return TokenResponse(token=token)

@router.post("/chat")
async def chat_endpoint(request: ChatRequest):
    """Main chat endpoint that processes messages and returns AI responses"""
    try:
        # Convert messages to dict format for the assistant
        messages_dict = [{"role": msg.role, "content": msg.content} for msg in request.messages]
        
        # Prepare payload for the assistant
        payload = {
            "messages": messages_dict,
            "token": request.token,
            "model": request.model,
            "topic": request.topic,
            "tutor_tools": request.tutor_tools,
            "use_rag": request.use_rag
        }
        
        # Generate response using the assistant
        response_text = generate_response(payload)
        
        return ChatResponse(reply=response_text)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating response: {str(e)}")

@router.get("/startup-message")
async def get_startup_message(topic: str = ""):
    """Get an initial startup message for a given topic"""
    try:
        from chat.assistant.assistant import _load_startup_text
        
        # Load the startup text from file
        startup_text = _load_startup_text()
        
        return StartupMessageResponse(reply=startup_text)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error loading startup message: {str(e)}")

@router.get("/models")
async def get_available_models():
    """Return available AI models"""
    from chat.assistant.assistant import MODELS
    return {"models": list(MODELS.keys())}
