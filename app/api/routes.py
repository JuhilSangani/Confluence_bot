from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from app.chains.rag_chain import ask_question
from app.ingestion.loader import load_confluence_documents
from app.ingestion.chunker import chunk_documents
from app.retriever.vector_store import build_vector_store

router = APIRouter()

class ChatRequest(BaseModel):
    """
    Defines what a valid chat request must contain.
    """
    question: str = Field(
        ...,
        min_length=3,
        max_length=500,
        description="The question to ask ConfluenceBot"
    )
    k: int = Field(
        default=3,
        ge=1,
        le=10,
        description="Number of chunks to retrieve from FAISS"
    )

class CitationModel(BaseModel):
    """
    Represents a single citation — one Confluence page that was used as a source for the answer.
    """
    title: str
    url: str

class ChatResponse(BaseModel):
    """
    Defines the exact shape of every chat response.
    """
    question: str
    answer: str
    citations: list[CitationModel]
    sources_found: int

class IngestResponse(BaseModel):
    """
    Response shape for the ingestion endpoint.
    """
    message: str
    documents_loaded: int
    chunks_created: int

# ENDPOINTS
@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Main chatbot endpoint. Receives a question, runs the full
    RAG pipeline, and returns a grounded answer with citations.
    """
    try:
        result = ask_question(request.question, k=request.k)

        return ChatResponse(
            question=result["question"],
            answer=result["answer"],
            citations=[
                CitationModel(title=c["title"], url=c["url"])
                for c in result["citations"]
            ],
            sources_found=len(result["citations"]),
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"RAG pipeline error: {str(e)}"
        )

@router.get("/ingest", response_model=IngestResponse)
async def ingest():
    """
    Triggers the ingestion pipeline on demand. Loads documents, chunks them, embeds them, and saves the FAISS index to disk.
    """
    try:
        # Run the full ingestion pipeline
        documents = load_confluence_documents()
        chunks = chunk_documents(documents)
        build_vector_store(chunks)

        return IngestResponse(
            message="Ingestion complete. FAISS index updated successfully.",
            documents_loaded=len(documents),
            chunks_created=len(chunks),
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Ingestion pipeline error: {str(e)}"
        )