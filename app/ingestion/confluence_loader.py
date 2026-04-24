#keep loader.py (mock) intact alongside this file. Easy to switch between mock and real data via config

import re
from atlassian import Confluence
from langchain_core.documents import Document
from app.core.config import get_settings

settings = get_settings()

def get_confluence_client() -> Confluence:
    """Returns an authenticated Confluence client."""
    return Confluence(
        url=settings.CONFLUENCE_URL,
        username=settings.CONFLUENCE_EMAIL,
        password=settings.CONFLUENCE_API_TOKEN,
        cloud=True,  # must be True for Confluence Cloud
    )

def clean_confluence_content(raw_content: str) -> str:
    """Cleans raw Confluence storage format content into plain text."""
    # Remove Confluence-specific macro tags
    content = re.sub(r'<ac:[^>]+>.*?</ac:[^>]+>', ' ', raw_content, flags=re.DOTALL)
    content = re.sub(r'<ac:[^>]+/>', ' ', content)
    content = re.sub(r'<ri:[^>]+/>', ' ', content)

    # Remove all remaining HTML tags
    content = re.sub(r'<[^>]+>', ' ', content)

    # Decode common HTML entities
    content = content.replace('&amp;', '&')
    content = content.replace('&lt;', '<')
    content = content.replace('&gt;', '>')
    content = content.replace('&nbsp;', ' ')
    content = content.replace('&quot;', '"')
    content = content.replace('&#39;', "'")

    # Collapse multiple whitespace and blank lines into single spaces
    content = re.sub(r'\s+', ' ', content)

    return content.strip()

def load_confluence_documents(
    space_key: str = None,
    limit: int = 50
) -> list[Document]:
    """
    Fetches pages from a Confluence space and converts them into LangChain Document objects.

    Args:
        space_key: Confluence space key. Defaults to config value.
        limit: Maximum number of pages to fetch.

    Returns:
        List of LangChain Document objects with metadata.
    """
    # Use config space key if not explicitly provided
    if space_key is None:
        space_key = settings.CONFLUENCE_SPACE_KEY

    confluence = get_confluence_client()

    # Fetch all pages from the space with their body content
    pages = confluence.get_all_pages_from_space(
        space_key,
        start=0,
        limit=limit,
        expand='body.storage,version,space'
    )

    documents = []

    for page in pages:
        # Skip the space homepage
        if page['title'] == page.get('space', {}).get('name', ''):
            continue

        # Extract and clean the page content
        raw_content = page.get('body', {}).get('storage', {}).get('value', '')
        clean_content = clean_confluence_content(raw_content)

        # Skip pages with no meaningful content after cleaning
        if len(clean_content.strip()) < 50:
            continue

        # Build the Confluence page URL for citations
        page_url = (
            f"{settings.CONFLUENCE_URL}/wiki/spaces/"
            f"{space_key}/pages/{page['id']}"
        )

        # Create a LangChain Document — same format as mock loader
        doc = Document(
            page_content=clean_content,
            metadata={
                "id": page['id'],
                "title": page['title'],
                "space": space_key,
                "url": page_url,
                "author": page.get('version', {}).get('by', {}).get('displayName', 'Unknown'),
                "last_modified": page.get('version', {}).get('when', ''),
                "source": "confluence_api"
            }
        )
        documents.append(doc)

    print(f"Loaded {len(documents)} pages from Confluence space '{space_key}'")
    return documents