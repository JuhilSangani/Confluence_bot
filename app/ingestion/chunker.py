from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document

def chunk_documents(documents: list[Document]) -> list[Document]:
    """
    Takes a list of full-page Documents and returns a larger list
    of smaller chunk Documents.
    """
    splitter = RecursiveCharacterTextSplitter(
        chunk_size = 500,
        chunk_overlap = 100,
        length_function = len,
        add_start_index = True,
    )
    chunks = splitter.split_documents(documents)

    return chunks