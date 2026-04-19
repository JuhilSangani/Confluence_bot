from fastapi import FastAPI
from app.core.config import get_settings
from app.api.routes import router

settings = get_settings()

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="A RAG-based chatbot that answers questions from confluence pages with citation."
)

# Registering the API routes under the /api prefix
app.include_router(router, prefix="/api")

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