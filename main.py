from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path
import uvicorn
from chat.routes import router as chat_router
from chat.assistant.assistant import set_vectorstore
from langchain_community.vectorstores import Chroma
from langchain_community.embeddings import HuggingFaceEmbeddings

app = FastAPI(title="Viola Chatbot", version="1.0.0")

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Include chat routes
app.include_router(chat_router, prefix="/api")

@app.get("/")
async def serve_index():
    """Serve the main HTML page"""
    return FileResponse("static/index.html")

@app.on_event("startup")
async def startup_event():
    """Initialize vector store and other heavy resources"""
    print("Initializing vector store...")
    
    # Vector store configuration
    PERSIST_DIR = "./index/chroma"
    COLLECTION = "artificial_intelligence"
    EMBED = "intfloat/multilingual-e5-small"
    
    try:
        # Initialize embeddings and vector store
        emb = HuggingFaceEmbeddings(model_name=EMBED)
        vs = Chroma(
            collection_name=COLLECTION,
            persist_directory=PERSIST_DIR,
            embedding_function=emb,
        )
        retriever = vs.as_retriever(search_kwargs={"k": 6})
        
        # Inject into assistant module
        set_vectorstore(retriever, emb)
        print("Vector store initialized successfully")
        
    except Exception as e:
        print(f"Warning: Could not initialize vector store: {e}")
        # Set a dummy retriever so the app doesn't crash
        set_vectorstore(None, None)

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="127.0.0.1",
        port=8000,
        reload=True
    )
