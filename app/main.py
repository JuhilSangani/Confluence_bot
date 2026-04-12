from fastapi import FastAPI
from app.core.config import get_settings

settings = get_settings()

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="A RAG-based chatbot that answers questions from confluence pages with citation."
)

@app.get("/")
async def root():
    return{
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "running",
        "message": "Visit /docs to explore the API interactively."
    }

@app.get("/health")
async def health_check():
    return {"status": "healthy"}