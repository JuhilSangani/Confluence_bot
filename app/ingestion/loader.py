import json
from pathlib import Path
from langchain_core.documents import Document

def load_confluence_documents() -> list[Document]:
    """
    Reads mock Confluence pages from a JSON file and converts
    each one into a LangChain Document object.

    Returns a list of Document objects ready for the next stage
    of the pipeline — chunking.
    """
    data_path = Path(__file__).parent.parent.parent / "data" / "confluence_pages.json"

    with open(data_path, "r", encoding="utf-8") as f:
        pages = json.load(f)

    documents =[]

    for page in pages:
        doc = Document(
            page_content = page["body"],
            metadata ={
                "id": page["id"],
                "title": page["title"],
                "space": page["space"],
                "author": page["author"],
                "url": page["url"],
            }
        )
        documents.append(doc)

    return documents