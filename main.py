from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import uvicorn
from chat.routes import router as chat_router
from chat.assistant.assistant import set_vectorstore
from langchain_community.vectorstores import Chroma
from langchain_community.embeddings import HuggingFaceEmbeddings

app = FastAPI(title="Viola Chatbot", version="1.0.0")

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/images", StaticFiles(directory="images"), name="images")

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
        print(f"Loading embeddings model: {EMBED}")
        # Initialize embeddings and vector store
        emb = HuggingFaceEmbeddings(model_name=EMBED)
        print(f"Embeddings loaded, initializing Chroma with collection: {COLLECTION}")
        
        vs = Chroma(
            collection_name=COLLECTION,
            persist_directory=PERSIST_DIR,
            embedding_function=emb,
        )
        print("Chroma initialized, creating retriever...")
        retriever = vs.as_retriever(search_kwargs={"k": 6})
        
        # Inject into assistant module
        print("Setting vectorstore in assistant module...")
        set_vectorstore(retriever, emb)
        print("✅ Vector store initialized successfully")
        
    except Exception as e:
        print(f"❌ Warning: Could not initialize vector store: {e}")
        import traceback
        traceback.print_exc()
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
