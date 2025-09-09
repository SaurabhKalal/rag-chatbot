from dotenv import load_dotenv
import os

# Load .env file
load_dotenv()

# 🔐 API Keys
HUGGING_FACE_ACCESS_TOKEN = os.getenv("HUGGING_FACE_ACCESS_TOKEN")
GROK_API_KEY = os.getenv("GROQ_API_KEY")
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")

# 📦 Pinecone Configuration
INDEX_NAME = "web-content-index"          # 🔁 Consistent name everywhere 
EMBEDDING_DIM = 384                       # for all-MiniLM-L6-v2
PINECONE_ENV = "us-east-1"
PINECONE_CLOUD = "aws"

# 🔍 Embedding Model Name
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"

# ✅ Print checks (optional for dev)
if HUGGING_FACE_ACCESS_TOKEN is None:
    print("❌ HUGGING_FACE_ACCESS_TOKEN not found.")
else:
    print("✅ Hugging Face token loaded.")

if GROK_API_KEY is None:
    print("❌ GROQ_API_KEY not found.")
else:
    print("✅ Groq API key loaded.")

if PINECONE_API_KEY is None:
    print("❌ PINECONE_API_KEY not found.")
else:
    print("✅ Pinecone API key loaded.")
