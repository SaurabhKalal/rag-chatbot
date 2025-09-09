from fastapi import FastAPI, File, UploadFile, HTTPException, Form
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware  # CORS import
from pydantic import BaseModel
from typing import Optional, List
import os
import tempfile
import requests
import time

from langchain_pymupdf4llm import PyMuPDF4LLMLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_pinecone import PineconeVectorStore
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from langchain_community.chat_message_histories import FileChatMessageHistory
from langchain.memory import ConversationSummaryMemory
from langchain_core.documents import Document
from pinecone import Pinecone, ServerlessSpec
from legal_advisor_chatbot import LegalChatbot

# Import your custom modules
from data_processing import clean_scraped_text, chunk_text, process_scraped_data
from web_scraper import run_scrapy_spider
from config import (
    INDEX_NAME,
    EMBEDDING_DIM,
    PINECONE_ENV,
    PINECONE_CLOUD,
    PINECONE_API_KEY,
    EMBEDDING_MODEL
)

# FIXED: Add fallback for INDEX_NAME
if INDEX_NAME is None or INDEX_NAME == "None" or not INDEX_NAME:
    INDEX_NAME = "web-content-index"  # Use one of your existing indexes
    print(f"⚠️  INDEX_NAME was None/empty, using fallback: {INDEX_NAME}")

# CREATE APP ONLY ONCE - HERE
app = FastAPI(title="RAG API - Enhanced with Session Validation")

# ADD CORS MIDDLEWARE IMMEDIATELY AFTER CREATING APP
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with your React app URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize embeddings
embeddings = HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL)

# UPDATED: Add is_admin field to QueryRequest
class QueryRequest(BaseModel):
    question: str
    session_id: Optional[str] = "default"
    is_admin: Optional[bool] = False  # Admin flag

# ADDED: Session validation request model
class SessionValidationRequest(BaseModel):
    session_id: str

# ADDED: Session ID validation function
def validate_session_id(session_id: str) -> str:
    """Validate and sanitize session ID"""
    if not session_id or session_id.strip() == "":
        raise HTTPException(status_code=400, detail="Session ID cannot be empty")
    
    # Remove any potentially problematic characters
    sanitized = session_id.strip().replace(" ", "_")
    
    # Ensure session ID is not too long
    if len(sanitized) > 100:
        raise HTTPException(status_code=400, detail="Session ID too long (max 100 characters)")
    
    return sanitized

def initialize_pinecone():
    """Initialize Pinecone client and create index if needed"""
    try:
        pc = Pinecone(api_key=PINECONE_API_KEY)
        
        # Check if index exists, if not create it
        existing_indexes = pc.list_indexes().names()
        print(f"📋 Existing indexes: {existing_indexes}")
        
        if INDEX_NAME not in existing_indexes:
            print(f"🏗️  Creating new index: {INDEX_NAME}")
            pc.create_index(
                name=INDEX_NAME,
                dimension=EMBEDDING_DIM,
                metric="cosine",
                spec=ServerlessSpec(cloud=PINECONE_CLOUD, region=PINECONE_ENV)
            )
            time.sleep(5)
        else:
            print(f"✅ Using existing index: {INDEX_NAME}")
            
        return pc
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Pinecone initialization failed: {str(e)}")

def get_groq_llm():
    """Initialize Groq LLM"""
    return ChatGroq(
        model="llama-3.3-70b-versatile",
        temperature=0,
        max_tokens=None,
        # reasoning_format="parsed"
    )

def create_unified_vector_store(documents, session_id: str):
    """Create vector store from documents"""
    print(f"🔧 Creating vector store with INDEX_NAME: {INDEX_NAME}")
    pc = initialize_pinecone()
    
    # FIXED: Pass index_name as string parameter instead of index object
    return PineconeVectorStore.from_documents(
        documents=documents,
        embedding=embeddings,
        index_name=INDEX_NAME,  # Pass as string, not index object
        namespace=session_id
    )

def create_simple_rag_chain(session_id: str):
    """Simple RAG implementation without LangChain retrievers - Most Reliable"""
    
    def get_relevant_documents(query: str):
        """Direct Pinecone search function"""
        try:
            # Get query embedding
            query_embedding = embeddings.embed_query(query)
            
            # Direct Pinecone search
            pc = initialize_pinecone()
            index = pc.Index(INDEX_NAME)
            response = index.query(
                vector=query_embedding,
                top_k=5,
                namespace=session_id,
                include_metadata=True
            )
            
            # Convert to LangChain Document format
            documents = []
            for match in response.matches:
                if match.metadata:
                    content = match.metadata.get('text', match.metadata.get('page_content', ''))
                    if content:
                        doc = Document(
                            page_content=content,
                            metadata=match.metadata
                        )
                        documents.append(doc)
            
            return documents
            
        except Exception as e:
            print(f"Error in document retrieval: {e}")
            return []
    
    llm = get_groq_llm()
    
    def rag_chain_invoke(inputs):
        question = inputs["input"]
        chat_history = inputs.get("chat_history", [])
        
        # Get relevant documents
        context_docs = get_relevant_documents(question)
        
        # Format context
        context = "\n\n".join([doc.page_content for doc in context_docs])
        
        # Create prompt
        system_message = f"""
You are a strict AI assistant. Use ONLY the below CONTEXT to answer.
Always double-check that the answer exists explicitly in the context before responding.  
If the answer is not in the context, say exactly: "I don't know based on the provided content."

CONTEXT:
{context}
"""
        
        # Format messages
        messages = [("system", system_message)]
        
        # Add chat history (last 5 messages only)
        if chat_history:
            for msg in chat_history[-5:]:
                if hasattr(msg, 'type') and hasattr(msg, 'content'):
                    messages.append((msg.type, msg.content))
        
        # Add current question
        messages.append(("human", question))
        
        # Create prompt template and get response
        prompt = ChatPromptTemplate.from_messages(messages)
        response = llm.invoke(prompt.format())
        
        return {
            "answer": response.content,
            "context": context_docs
        }
    
    # Return chain-like object
    class SimpleRAGChain:
        def invoke(self, inputs):
            return rag_chain_invoke(inputs)
    
    return SimpleRAGChain()

def create_admin_rag_chain():
    """Admin RAG implementation that searches across ALL namespaces"""
    
    def get_relevant_documents_all_namespaces(query: str):
        """Search across ALL namespaces for admin queries"""
        try:
            # Get query embedding
            query_embedding = embeddings.embed_query(query)
            
            # Get Pinecone index
            pc = initialize_pinecone()
            index = pc.Index(INDEX_NAME)
            
            # Get all existing namespaces
            stats = index.describe_index_stats()
            all_namespaces = list(stats.namespaces.keys())
            print(f"🔍 Found namespaces: {all_namespaces}")
            
            # Search across each namespace and combine results
            all_documents = []
            
            for namespace in all_namespaces:
                try:
                    print(f"🔍 Searching namespace: {namespace}")
                    response = index.query(
                        vector=query_embedding,
                        top_k=5,  # Get top 5 from each namespace
                        namespace=namespace,
                        include_metadata=True
                    )
                    
                    # Convert results to documents
                    for match in response.matches:
                        print(f"📊 Match score: {match.score}")  # Debug similarity scores
                        
                        if match.metadata:  # Remove similarity threshold completely
                            content = match.metadata.get('text', match.metadata.get('page_content', ''))
                            if content:
                                # Add namespace info to metadata
                                metadata = match.metadata.copy()
                                metadata['source_namespace'] = namespace
                                metadata['similarity_score'] = match.score
                                
                                doc = Document(
                                    page_content=content,
                                    metadata=metadata
                                )
                                all_documents.append((doc, match.score))
                    
                    print(f"🔍 Found {len(response.matches)} matches in namespace '{namespace}'")
                    
                except Exception as namespace_error:
                    print(f"Error searching namespace '{namespace}': {namespace_error}")
                    continue
            
            # Sort all documents by similarity score and take top results
            all_documents.sort(key=lambda x: x[1], reverse=True)
            top_documents = [doc for doc, score in all_documents[:10]]  # Top 10 overall
            
            print(f"🔍 Admin search found {len(top_documents)} documents across {len(all_namespaces)} namespaces")
            print(f"📊 Score range: {all_documents[0][1]:.3f} to {all_documents[-1][1]:.3f}" if all_documents else "No documents found")
            
            return top_documents
            
        except Exception as e:
            print(f"Error in admin document retrieval: {e}")
            return []
    
    llm = get_groq_llm()
    
    def admin_rag_chain_invoke(inputs):
        question = inputs["input"]
        
        # Get relevant documents from ALL namespaces
        context_docs = get_relevant_documents_all_namespaces(question)
        
        if not context_docs:
            return {
                "answer": "I don't have any relevant information to answer your question. Please make sure documents have been processed and indexed.",
                "context": []
            }
        
        # Format context with namespace info
        context_parts = []
        for doc in context_docs:
            namespace = doc.metadata.get('source_namespace', 'unknown')
            score = doc.metadata.get('similarity_score', 0)
            context_parts.append(f"[Source: {namespace}] {doc.page_content}")
        
        context = "\n\n".join(context_parts)
        
        # Create admin prompt
        system_message = f"""
You are an AI assistant with GLOBAL access to ALL processed documents across the entire knowledge base.
Use the CONTEXT below to answer questions. The context comes from multiple different sources and sessions.
Each piece of context is labeled with its source namespace for reference.

CONTEXT:
{context}
"""
        
        # Format messages
        messages = [("system", system_message)]
        messages.append(("human", question))
        
        # Create prompt template and get response
        prompt = ChatPromptTemplate.from_messages(messages)
        response = llm.invoke(prompt.format())
        
        return {
            "answer": response.content,
            "context": context_docs
        }
    
    # Return admin chain-like object
    class AdminRAGChain:
        def invoke(self, inputs):
            return admin_rag_chain_invoke(inputs)
    
    return AdminRAGChain()

async def process_pdf(file: UploadFile):
    """Process PDF file and return chunks"""
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_file:
        content = await file.read()
        temp_file.write(content)
        temp_file_path = temp_file.name

    loader = PyMuPDF4LLMLoader(temp_file_path)
    docs = loader.load()
    os.unlink(temp_file_path)

    splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
    return splitter.split_documents(docs)

def get_summary_memory(session_id: str):
    """Get conversation memory for session"""
    os.makedirs("./chat_histories", exist_ok=True)
    file_path = f"./chat_histories/{session_id}.json"
    chat_history = FileChatMessageHistory(file_path)
    return ConversationSummaryMemory(
        llm=get_groq_llm(),
        chat_memory=chat_history,
        memory_key="chat_history",
        input_key="input",
        return_messages=True
    )

# =============================================================================
# API ENDPOINTS
# =============================================================================

# Health check and startup
@app.on_event("startup")  
async def startup_event():
    initialize_pinecone()

@app.get("/health")
async def health_check():
    return {"status": "healthy", "message": "RAG API is running"}

@app.get("/")
async def root():
    return {
        "message": "RAG API - Enhanced with Session Validation",
        "endpoints": {
            "/process": "Process URL and/or PDF document and store in vector DB",
            "/query": "Query the vector DB with a question (supports admin global access)",
            "/validate-session": "Validate if a session ID exists and has content",
            "/health": "Health check",
            "/namespaces": "Get all available namespaces",
            "/session/{session_id}/status": "Check session status"
        },
        "usage": {
            "step1": "Use /process to upload sources (URL and/or PDF)",
            "step2": "Use /query to ask questions about the processed content",
            "admin": "Admins can query across all namespaces with is_admin=true",
            "user_login": "Users must provide valid session_id that exists in the system"
        },
        "features": [
            "✅ Fixed INDEX_NAME None issue",
            "✅ Added fallback for missing config",
            "✅ Direct Pinecone search implementation", 
            "✅ Enhanced debugging output",
            "✅ Admin global namespace access",
            "✅ User session isolation",
            "✅ Session ID validation and sanitization",
            "✅ Enhanced error handling and logging",
            "✅ User login session validation"
        ]
    }

# PROCESS ENDPOINT
@app.post("/process")
async def process_sources_endpoint(
    file: Optional[UploadFile] = File(None),
    url: Optional[str] = Form(None),
    session_id: str = Form("default")
):
    """Process URL and/or PDF document and store in vector database"""
    print("==== /process called ====")
    print("Received URL:", url)
    print("Received File:", file.filename if file else "None")
    
    # ADDED: Validate and sanitize session_id
    try:
        session_id = validate_session_id(session_id)
        print(f"🔄 Processing for session_id: {session_id}")
    except HTTPException as e:
        print(f"❌ Invalid session_id: {e.detail}")
        raise e
    
    print(f"📋 Using INDEX_NAME: {INDEX_NAME}")

    documents = []
    processing_status = []

    # ADDED: Validate that at least one source is provided
    if not url and not file:
        raise HTTPException(
            status_code=400, 
            detail="At least one source (URL or document) must be provided"
        )

    # Process URL if provided
    if url:
        try:
            # ADDED: Basic URL validation
            if not url.startswith(('http://', 'https://')):
                raise ValueError("URL must start with http:// or https://")
            
            run_scrapy_spider(url)
            raw_data = process_scraped_data()
            if not raw_data:
                raise ValueError("Scraper returned no data")
            combined_text = " ".join([entry.get("text", "") for entry in raw_data])
            clean_text = clean_scraped_text(combined_text)
            url_docs = chunk_text(clean_text, chunk_size=600, chunk_overlap=50)
            documents.extend(url_docs)
            processing_status.append(f"✓ URL scraped and processed: {len(url_docs)} chunks")
        except Exception as e:
            processing_status.append(f"✗ URL scraping/processing failed: {str(e)}")

    # Process PDF if provided
    if file:
        if not file.filename.endswith('.pdf'):
            raise HTTPException(status_code=400, detail="Only PDF files are supported")
        try:
            doc_docs = await process_pdf(file)
            documents.extend(doc_docs)
            processing_status.append(f"✓ Document processed: {len(doc_docs)} chunks")
        except Exception as e:
            processing_status.append(f"✗ Document processing failed: {str(e)}")

    # ADDED: Better error handling for no successful processing
    if not documents:
        raise HTTPException(
            status_code=400, 
            detail="No documents were successfully processed. Check the processing status for details."
        )

    # Enhanced validation
    print(f"📝 Total documents to process: {len(documents)}")
    
    # Validate document content
    non_empty_docs = [doc for doc in documents if doc.page_content.strip()]
    print(f"📄 Non-empty documents: {len(non_empty_docs)}")
    
    if not non_empty_docs:
        raise HTTPException(status_code=400, detail="All processed documents are empty")

    # Preview documents
    for i, d in enumerate(non_empty_docs[:3]):
        print(f"Chunk {i+1} Preview:", d.page_content[:200])

    # Test embedding creation
    try:
        test_embedding = embeddings.embed_query("test query")
        print(f"🧮 Embedding dimension: {len(test_embedding)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Embedding creation failed: {str(e)}")

    # Create vector store
    try:
        vector_store = create_unified_vector_store(non_empty_docs, session_id)
        processing_status.append(f"✓ Vector store updated with {len(non_empty_docs)} total chunks")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Vector store creation failed: {str(e)}")

    # Verify vectors were actually stored
    try:
        time.sleep(2)  # Wait for indexing
        pc = initialize_pinecone()
        index = pc.Index(INDEX_NAME)
        stats = index.describe_index_stats()
        namespace_stats = stats.namespaces.get(session_id)
        vector_count = namespace_stats.vector_count if namespace_stats else 0
        print(f"✅ Verified: {vector_count} vectors stored in namespace '{session_id}'")
        processing_status.append(f"✓ Verified: {vector_count} vectors indexed")
    except Exception as e:
        print(f"Warning: Could not verify vector storage: {e}")

    return JSONResponse({
        "status": "Sources processed and indexed successfully",
        "session_id": session_id,
        "processing_details": processing_status,
        "sources_processed": {
            "url_provided": url is not None,
            "document_provided": file is not None,
            "total_chunks": len(non_empty_docs)
        }
    })


# Create one chatbot instance per session
chatbot_instances = {}

# Define request models 
class ChatRequest(BaseModel):
    question: str
    session_id: Optional[str] = "default"
    retrieved_sources: Optional[List[str]] = None
    context_count:   Optional[int]          = None
    is_admin_query:  Optional[bool]         = None

class ResetRequest(BaseModel):
    session_id: Optional[str] = "default"

@app.post("/chat_legal")
async def chat(request: ChatRequest):
    session_id = request.session_id
    user_input = request.question

    # Reuse chatbot instance per session
    if session_id not in chatbot_instances:
        chatbot_instances[session_id] = LegalChatbot()

    bot = chatbot_instances[session_id]
    response = await bot.chat(user_input=user_input, session_id=session_id)
    return {"answer": response,"session_id":session_id,"retrieved_sources":None,"context_count":None,"is_admin_query":None}


# QUERY ENDPOINT
@app.post("/query")
async def query_endpoint(request: QueryRequest):
    """Query the vector database with a question"""
    print(f"🔍 Querying with session_id: {request.session_id}")
    print(f"🛡️ Admin query: {request.is_admin}")
    print(f"📋 Using INDEX_NAME: {INDEX_NAME}")
    
    # ADDED: Validate session_id
    try:
        if request.session_id != '*':  # Admin uses '*' for global search
            request.session_id = validate_session_id(request.session_id)
    except HTTPException as e:
        return JSONResponse({
            "error": f"Invalid session ID: {e.detail}",
            "session_id": request.session_id
        })
    
    # For admin queries, search across ALL namespaces
    if request.is_admin:
        try:
            pc = initialize_pinecone()
            index = pc.Index(INDEX_NAME)
            stats = index.describe_index_stats()
            total_vectors = stats.total_vector_count
            
            if total_vectors == 0:
                return JSONResponse({
                    "error": "No documents found in the entire knowledge base.",
                    "session_id": request.session_id,
                    "suggestion": "Process some documents first"
                })
            
            print(f"📊 Admin searching across ALL namespaces with {total_vectors} total vectors")
            
            # Create admin RAG chain that searches all namespaces
            rag_chain = create_admin_rag_chain()
            
            # Execute admin query
            result = rag_chain.invoke({
                "input": request.question
            })
            
        except Exception as e:
            print(f"Error in admin query: {e}")
            return JSONResponse({
                "error": f"Failed to process admin query: {str(e)}",
                "session_id": request.session_id
            })
            
    else:
        # Regular user query (existing logic)
        try:
            pc = initialize_pinecone()
            index = pc.Index(INDEX_NAME)
            stats = index.describe_index_stats()
            namespace_stats = stats.namespaces.get(request.session_id)
            vector_count = namespace_stats.vector_count if namespace_stats else 0
            
            if vector_count == 0:
                return JSONResponse({
                    "error": f"No vectors found in namespace '{request.session_id}'. Please process documents first.",
                    "session_id": request.session_id,
                    "suggestion": "Use /process endpoint to upload and process documents first"
                })
            
            print(f"📊 User namespace '{request.session_id}' has {vector_count} vectors")
            rag_chain = create_simple_rag_chain(request.session_id)
            memory = get_summary_memory(request.session_id)
            
            result = rag_chain.invoke({
                "input": request.question,
                "chat_history": memory.chat_memory.messages
            })
            
            # Save conversation to memory
            try:
                memory.save_context(
                    {"input": request.question},
                    {"output": result["answer"]}
                )
            except Exception as e:
                print(f"Memory save failed: {e}")
                
        except Exception as e:
            print(f"RAG chain failed: {e}")
            return JSONResponse({
                "error": f"Failed to process query: {str(e)}",
                "session_id": request.session_id
            })

    # Log retrieved context
    print("🔍 Retrieved context chunks:")
    for i, doc in enumerate(result.get("context", [])):
        print(f"Chunk {i+1}:", doc.page_content[:250], "\n---")

    return JSONResponse({
        "answer": result["answer"],
        "session_id": request.session_id,
        "retrieved_sources": [doc.page_content for doc in result.get("context", [])],
        "context_count": len(result.get("context", [])),
        "is_admin_query": request.is_admin
    })

# SESSION VALIDATION ENDPOINT (NEW)
@app.post("/validate-session")
async def validate_session_endpoint(request: SessionValidationRequest):
    """Validate if a session ID exists and has content"""
    try:
        session_id = request.session_id.strip()
        print(f"🔍 Validating session: '{session_id}'")
        
        if not session_id:
            return JSONResponse({
                "valid": False,
                "error": "Session ID cannot be empty",
                "session_id": session_id
            })
        
        # Validate and sanitize session_id
        try:
            session_id = validate_session_id(session_id)
        except HTTPException as e:
            return JSONResponse({
                "valid": False,
                "error": e.detail,
                "session_id": session_id
            })
        
        # Check if session exists in Pinecone
        pc = initialize_pinecone()
        index = pc.Index(INDEX_NAME)
        stats = index.describe_index_stats()
        
        # Check if namespace exists and has vectors
        namespace_stats = stats.namespaces.get(session_id)
        
        if namespace_stats and namespace_stats.vector_count > 0:
            print(f"✅ Session validation successful: '{session_id}' has {namespace_stats.vector_count} vectors")
            return JSONResponse({
                "valid": True,
                "session_id": session_id,
                "vector_count": namespace_stats.vector_count,
                "message": f"Session found with {namespace_stats.vector_count} documents"
            })
        else:
            print(f"❌ Session validation failed: '{session_id}' not found or empty")
            return JSONResponse({
                "valid": False,
                "error": f"Session ID '{session_id}' does not exist or has no content. Please check your session ID or contact admin.",
                "session_id": session_id,
                "suggestion": "Make sure your session ID is correct and that documents have been processed for this session."
            })
            
    except Exception as e:
        print(f"Error validating session: {e}")
        return JSONResponse({
            "valid": False,
            "error": f"Failed to validate session: {str(e)}",
            "session_id": getattr(request, 'session_id', '')
        })

# SESSION STATUS ENDPOINT
@app.get("/session/{session_id}/status")
async def check_session_status(session_id: str):
    """Check the status of a specific session"""
    try:
        session_id = validate_session_id(session_id)
        pc = initialize_pinecone()
        index = pc.Index(INDEX_NAME)
        stats = index.describe_index_stats()
        namespace_stats = stats.namespaces.get(session_id)
        
        if namespace_stats and namespace_stats.vector_count > 0:
            return JSONResponse({
                "session_id": session_id,
                "exists": True,
                "vector_count": namespace_stats.vector_count,
                "status": "active",
                "valid": True
            })
        else:
            return JSONResponse({
                "session_id": session_id,
                "exists": False,
                "vector_count": 0,
                "status": "empty",
                "valid": False
            })
    except Exception as e:
        return JSONResponse({
            "session_id": session_id,
            "exists": False,
            "error": str(e),
            "status": "error",
            "valid": False
        })

# NAMESPACES ENDPOINT
@app.get("/namespaces")
async def get_namespaces():
    """Get all available namespaces from Pinecone index"""
    try:
        pc = initialize_pinecone()
        index = pc.Index(INDEX_NAME)
        stats = index.describe_index_stats()
        
        # Get all namespace names
        namespaces = list(stats.namespaces.keys())
        
        # Sort namespaces for better UX (put '0000' and 'default' first if they exist)
        priority_namespaces = ['0000', 'default']
        regular_namespaces = [ns for ns in namespaces if ns not in priority_namespaces]
        priority_existing = [ns for ns in priority_namespaces if ns in namespaces]
        
        sorted_namespaces = priority_existing + sorted(regular_namespaces)
        
        print(f"📋 Found {len(namespaces)} namespaces: {sorted_namespaces}")
        
        return JSONResponse({
            "namespaces": sorted_namespaces,
            "total_count": len(namespaces),
            "total_vectors": stats.total_vector_count
        })
        
    except Exception as e:
        print(f"Error fetching namespaces: {e}")
        return JSONResponse({
            "error": f"Failed to fetch namespaces: {str(e)}",
            "namespaces": []
        })

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
