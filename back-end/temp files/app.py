import streamlit as st
import os
import json
import time
from datetime import datetime
import pandas as pd
from typing import List, Dict, Any
from dotenv import load_dotenv

from langchain_community.document_loaders import (
    TextLoader, PyPDFLoader, Docx2txtLoader
)

# Load environment variables
load_dotenv()
print("Loaded .env variables:", {
    k: v for k, v in os.environ.items()
    if k in ['HUGGING_FACE_ACCESS_TOKEN', 'GROQ_API_KEY']
})

from data_processing import clean_scraped_text, chunk_text, create_vector_store
from rag_pipeline import get_groq_chat_llm

try:
    from scraper import DepthRAGScraper
    from rag_pipeline import (
        get_local_chat_llm,
        create_conversational_rag,
        create_simple_rag_chain
    )
except ImportError as e:
    st.error(f"Import Error: {e}")
    st.stop()

# Initialize Session State
def initialize_session_state():
    keys = [
        'scraping_status', 'scraped_data', 'rag_chain', 'chat_history',
        'vectorstore', 'llm', 'scraping_progress', 'current_scraping_task',
        'uploaded_files', 'data_source'
    ]
    for k in keys:
        if k not in st.session_state:
            st.session_state[k] = 'idle' if k == 'scraping_status' else [] if k == 'chat_history' else None
    if st.session_state.data_source is None:
        st.session_state.data_source = 'Web Scraping'

initialize_session_state()

# Preview scraped text
def preview_scraped_text():
    path = os.path.join("depth_rag_dataset", "output", "combined_documents.txt")
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            text = f.read()
        st.text_area("📄 Scraped Text Preview", text[:3000] + "..." if len(text) > 3000 else text, height=300)
    else:
        st.warning("Scraped document not found.")

# UI Title
st.title("🤖 RAG Web Scraper & Document Chat")

# Sidebar
with st.sidebar:
    st.header("⚙️ Configuration")

    st.radio(
        "Select Data Source",
        ["Web Scraping", "Upload Documents"],
        index=0 if st.session_state.data_source == "Web Scraping" else 1,
        key="data_source"
    )

    if st.session_state.data_source == "Upload Documents":
        uploaded_files = st.file_uploader("📂 Upload Files", type=['pdf', 'docx', 'txt'], accept_multiple_files=True)
        if uploaded_files:
            st.session_state.uploaded_files = uploaded_files
            st.success(f"Uploaded {len(uploaded_files)} file(s).")

    elif st.session_state.data_source == "Web Scraping":
        st.subheader("🌐 Web Scraping Settings")
        url_input = st.text_area("Enter URLs (one per line)", height=100)
        max_depth = st.slider("Max Depth", 1, 10, 3)
        max_pages = st.slider("Max Pages", 10, 100, 30)
        delay = st.slider("Delay between requests (sec)", 1, 10, 2)
        output_dir = st.text_input("Output Directory", value="depth_rag_dataset")

    st.divider()
    use_contextual = st.checkbox("Use Contextual Retrieval", False)
    use_conversation = st.checkbox("Conversational Mode", True)

# Scraper Class
class StreamlitScraper:
    def __init__(self, progress_callback=None):
        self.progress_callback = progress_callback
        self.scraper = None

    def run_scraping(self, urls, max_depth, max_pages, delay, output_dir):
        try:
            self.scraper = DepthRAGScraper(output_dir=output_dir, max_depth=max_depth, max_pages=max_pages)
            if self.progress_callback:
                self.progress_callback("🚀 Scraper started...")
            scraped_data = self.scraper.crawl_website(urls, delay=delay)
            if scraped_data:
                metadata = self.scraper.save_results(scraped_data)
                if self.progress_callback:
                    self.progress_callback("✅ Scraping completed!")
                return True, scraped_data, metadata
            return False, None, None
        except Exception as e:
            if self.progress_callback:
                self.progress_callback(f"❌ Error: {str(e)}")
            return False, None, None

# Load and build RAG chain
def load_rag_chain(documents=None, use_contextual=False, use_conversation=True):
    try:
        if documents is None:
            file_path = os.path.join("depth_rag_dataset", "output", "combined_documents.txt")
            if not os.path.exists(file_path):
                return None, "❌ No scraped text found."
            with open(file_path, 'r', encoding='utf-8') as f:
                text = f.read()
            clean = clean_scraped_text(text)
            chunks = chunk_text(clean)
        else:
            chunks = chunk_text(documents)

        vs = create_vector_store(chunks)
        llm = get_groq_chat_llm()

        if use_conversation:
            rag_chain = create_conversational_rag(llm, vs, use_contextual)
        else:
            rag_chain = create_simple_rag_chain(llm, vs, use_contextual)

        st.session_state.rag_chain = rag_chain
        st.session_state.vectorstore = vs
        st.session_state.llm = llm
        return rag_chain, "✅ RAG system initialized."

    except Exception as e:
        return None, f"❌ Error in RAG setup: {str(e)}"

# Data Input
st.subheader("📥 Data Input")

if st.session_state.data_source == "Web Scraping":
    if st.button("🚀 Start Scraping"):
        urls = [url.strip() for url in url_input.strip().split('\n') if url.strip()]
        if urls:
            scraper = StreamlitScraper(lambda msg: st.info(msg))
            success, scraped_data, metadata = scraper.run_scraping(
                urls, max_depth, max_pages, delay, output_dir
            )
            if success:
                st.session_state.scraped_data = scraped_data
                st.success("Scraping done.")
            else:
                st.error("Scraping failed.")
        else:
            st.warning("⚠️ Please enter at least one URL.")

    preview_scraped_text()

elif st.session_state.data_source == "Upload Documents":
    if st.session_state.uploaded_files:
        docs = []
        for f in st.session_state.uploaded_files:
            file_path = f"temp_{f.name}"
            with open(file_path, "wb") as temp:
                temp.write(f.read())
            ext = os.path.splitext(f.name)[-1].lower()
            loader = (
                PyPDFLoader(file_path) if ext == '.pdf'
                else Docx2txtLoader(file_path) if ext == '.docx'
                else TextLoader(file_path)
            )
            docs.extend(loader.load())
            os.remove(file_path)
        st.success(f"✅ Loaded {len(docs)} documents.")
    else:
        st.warning("📂 No files uploaded.")

# Initialize RAG
st.divider()
st.subheader("💡 Initialize RAG System")

if st.button("🔧 Initialize RAG"):
    documents = None
    if st.session_state.data_source == "Upload Documents":
        documents = docs if 'docs' in locals() else []
    with st.spinner("Setting up RAG..."):
        chain, msg = load_rag_chain(documents, use_contextual, use_conversation)
        if chain:
            st.success(msg)
        else:
            st.error(msg)

# Chat
if st.session_state.rag_chain:
    st.subheader("💬 Ask a Question")
    user_input = st.text_input("Your question:")
    if user_input and st.button("Ask"):
        try:
            if use_conversation:
                from langchain_core.messages import HumanMessage, AIMessage
                lc_history = []
                for r, m in st.session_state.chat_history:
                    lc_history.append(HumanMessage(content=m) if r == "user" else AIMessage(content=m))
                result = st.session_state.rag_chain.invoke({
                    "chat_history": lc_history, "input": user_input
                })
                answer = result.get("answer", "No answer.")
            else:
                result = st.session_state.rag_chain.invoke({"query": user_input})
                answer = result.get("result", "No answer.")
            st.session_state.chat_history.append(("user", user_input))
            st.session_state.chat_history.append(("bot", answer))
            st.markdown(f"**🤖 Answer:** {answer}")
        except Exception as e:
            st.error(f"❌ Error: {str(e)}")

# Footer
st.markdown("---")
st.markdown("<center>Built with ❤️ using Streamlit</center>", unsafe_allow_html=True)
