import os
import re
import json
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import Pinecone as PineconeLangChain
from langchain_community.chat_message_histories import FileChatMessageHistory
from langchain_huggingface import HuggingFaceEmbeddings
from langchain.memory import ConversationSummaryMemory
from langchain_core.documents import Document
from pinecone import Pinecone
from rag_pipeline import get_local_chat_llm
from config import (
    INDEX_NAME,
    EMBEDDING_DIM,
    PINECONE_ENV,
    PINECONE_CLOUD,
    PINECONE_API_KEY,
    EMBEDDING_MODEL
)

def process_scraped_data():
    try:
        with open("output.json", "r", encoding="utf-8") as f:
            data = json.load(f)
        print(f"[DEBUG] 🔍 Extracted {len(data)} items from output.json")
        return data
    except Exception as e:
        print(f"[ERROR] Failed to load scraped data: {e}")
        return []


# Initialize embeddings using centralized config
embeddings = HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL)

def clean_scraped_text(text):
    """Clean scraped text by removing metadata and special characters."""
    patterns = [
        r'^Title:.*$', r'^URL:.*$', r'^Crawl Depth:.*$',
        r'^Quality Score:.*$', r'^Method:.*$', r'^Scraped:.*$',
        r'^=+$', r'^-+$', r'^_+$', r'^\*+$'
    ]
    for pattern in patterns:
        text = re.sub(pattern, '', text, flags=re.MULTILINE)

    text = re.sub(r'\n+', ' ', text)
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r'\[.*?\]', '', text)
    text = re.sub(r'©.*?(\s|$)', '', text)
    text = re.sub(r'All rights reserved.*?(\s|$)', '', text, flags=re.IGNORECASE)

    replacements = {
        '\u00a0': ' ', '\u2019': "'", '\u201c': '"',
        '\u201d': '"', '\u2013': '-', '\u2014': '--', '\u2026': '...'
    }
    for old, new in replacements.items():
        text = text.replace(old, new)

    return text.strip()

def chunk_text(text: str, chunk_size: int = 500, chunk_overlap: int = 50):
    """Split text into chunks with metadata."""
    try:
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap
        )
        chunks = splitter.create_documents([text])
        for chunk in chunks:
            chunk.metadata = {"source": "scraped_website"}
        return chunks
    except Exception as e:
        print(f"Error in chunking: {e}")
        return None

def initialize_pinecone():
    """Initialize Pinecone connection and index."""
    try:
        if not PINECONE_API_KEY:
            raise ValueError("Pinecone API key not found")

        pc = Pinecone(api_key=PINECONE_API_KEY)

        if INDEX_NAME not in pc.list_indexes().names():
            pc.create_index(
                name=INDEX_NAME,
                dimension=EMBEDDING_DIM,
                metric="cosine",
                spec={
                    "serverless": {
                        "cloud": PINECONE_CLOUD,
                        "region": PINECONE_ENV
                    }
                }
            )
        return pc
    except Exception as e:
        print(f"Error initializing Pinecone: {str(e)}")
        return None

def create_vector_store(chunks):
    """Create and return Pinecone vector store."""
    try:
        pc = initialize_pinecone()
        if not pc:
            raise Exception("Pinecone initialization failed")

        return PineconeLangChain.from_documents(
            documents=chunks,
            embedding=embeddings,
            index_name=INDEX_NAME
        )
    except Exception as e:
        print(f"Error creating vector store: {str(e)}")
        return None

def get_file_history(session_id: str):
    """Get file-based chat message history."""
    os.makedirs("./chat_histories", exist_ok=True)
    file_path = f"./chat_histories/{session_id}.json"
    return FileChatMessageHistory(file_path)

def get_summary_memory(session_id: str):
    """Create conversation summary memory."""
    llm = get_local_chat_llm()
    chat_history = get_file_history(session_id)
    return ConversationSummaryMemory(
        llm=llm,
        chat_memory=chat_history,
        memory_key="chat_history",
        input_key="input",
        return_messages=True
    )

# Explicitly export the embeddings object
__all__ = [
    'clean_scraped_text',
    'chunk_text',
    'create_vector_store',
    'get_file_history',
    'get_summary_memory',
    'embeddings'
]
