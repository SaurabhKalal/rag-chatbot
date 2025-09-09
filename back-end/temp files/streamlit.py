import streamlit as st
import requests
import json
from typing import Optional
import time
import uuid

# Page configuration
st.set_page_config(
    page_title="RAG Assistant",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Constants
API_BASE_URL = "http://localhost:8000"  # Change this to your API URL

# Custom CSS for better styling
st.markdown("""
<style>
    .main-header {
        text-align: center;
        padding: 1.5rem;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        border-radius: 15px;
        margin-bottom: 2rem;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
    }
    
    .status-success {
        padding: 1rem;
        background-color: #d4edda;
        color: #155724;
        border: 1px solid #c3e6cb;
        border-radius: 8px;
        margin: 1rem 0;
        border-left: 4px solid #28a745;
    }
    
    .status-error {
        padding: 1rem;
        background-color: #f8d7da;
        color: #721c24;
        border: 1px solid #f5c6cb;
        border-radius: 8px;
        margin: 1rem 0;
        border-left: 4px solid #dc3545;
    }
    
    .status-info {
        padding: 1rem;
        background-color: #d1ecf1;
        color: #0c5460;
        border: 1px solid #bee5eb;
        border-radius: 8px;
        margin: 1rem 0;
        border-left: 4px solid #17a2b8;
    }
    
    .chat-message-user {
        padding: 1rem;
        margin: 1rem 0;
        border-radius: 15px;
        background: linear-gradient(135deg, #f3e5f5 0%, #e1bee 100%);
        border-left: 4px solid #2196f3;
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
    }
    
    .chat-message-bot {
        padding: 1rem;
        margin: 1rem 0;
        border-radius: 15px;
        background: linear-gradient(135deg, #f3e5f5 0%, #e1bee 100%);
        border-left: 4px solid #9c27b0;
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
    }
    
    .source-info {
        font-size: 0.85em;
        color: #6c757d;
        background-color: #f8f9fa;
        padding: 0.75rem;
        border-radius: 8px;
        margin-top: 0.5rem;
        border: 1px solid #e9ecef;
    }
    
    .step-indicator {
        display: flex;
        justify-content: space-between;
        margin: 2rem 0;
        padding: 1rem;
        background-color: #f8f9fa;
        border-radius: 10px;
    }
    
    .step {
        text-align: center;
        flex: 1;
        padding: 0.5rem;
    }
    
    .step.active {
        background-color: #007bff;
        color: white;
        border-radius: 8px;
    }
    
    .metric-card {
        background: white;
        padding: 1rem;
        border-radius: 10px;
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
        text-align: center;
        margin: 0.5rem 0;
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state with proper defaults
def initialize_session_state():
    if 'session_id' not in st.session_state:
        st.session_state.session_id = str(uuid.uuid4())[:8]
    
    if 'chat_history' not in st.session_state:
        st.session_state.chat_history = []
    
    if 'processed_sources' not in st.session_state:
        st.session_state.processed_sources = []
    
    if 'processing_completed' not in st.session_state:
        st.session_state.processing_completed = False
    
    if 'current_step' not in st.session_state:
        st.session_state.current_step = 1

# Helper functions
def check_api_health():
    """Check if the API is running"""
    try:
        response = requests.get(f"{API_BASE_URL}/health", timeout=5)
        return response.status_code == 200
    except:
        return False

def process_sources(url: Optional[str], uploaded_file, session_id: str):
    """Process URL and/or document using the /process endpoint"""
    try:
        files = {}
        data = {"session_id": session_id}

        if url and url.strip():
            data["url"] = url.strip()

        if uploaded_file is not None:
            files["file"] = (uploaded_file.name, uploaded_file.getvalue(), uploaded_file.type)

        # ✅ DEBUG LOGGING
        print("==== Sending to /process ====")
        print("Data (form):", data)
        print("Files:", "yes" if files else "no")

        response = requests.post(
            f"{API_BASE_URL}/process",
            data=data,
            files=files if files else {},
            timeout=920
        )

        if response.status_code == 200:
            return True, response.json()
        else:
            print("Response Status:", response.status_code)
            print("Response Text:", response.text)
            return False, {
                "error": f"API Error: {response.status_code}",
                "detail": response.text
            }

    except requests.exceptions.Timeout:
        return False, {
            "error": "Request timeout",
            "detail": "The processing took too long. Please try again."
        }
    except requests.exceptions.ConnectionError:
        return False, {
            "error": "Connection error",
            "detail": "Could not connect to the API server."
        }
    except Exception as e:
        return False, {
            "error": "Unexpected error",
            "detail": str(e)
        }


def query_sources(question: str, session_id: str):
    """Query the processed sources using the /query endpoint"""
    try:
        data = {
            "question": question.strip(),
            "session_id": session_id
        }
        
        response = requests.post(
            f"{API_BASE_URL}/query",
            json=data,
            timeout=60
        )
        
        if response.status_code == 200:
            return True, response.json()
        else:
            return False, {"error": f"API Error: {response.status_code}", "detail": response.text}
            
    except requests.exceptions.Timeout:
        return False, {"error": "Request timeout", "detail": "The query took too long. Please try again."}
    except requests.exceptions.ConnectionError:
        return False, {"error": "Connection error", "detail": "Could not connect to the API server."}
    except Exception as e:
        return False, {"error": "Unexpected error", "detail": str(e)}

# Main UI
def main():
    # Initialize session state
    initialize_session_state()
    
    # Header
    st.markdown("""
    <div class="main-header">
        <h1>🤖 RAG Document Assistant</h1>
        <p>Simple two-step process: Process sources → Ask questions</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Check API health
    if not check_api_health():
        st.error("⚠️ API server is not running. Please start the FastAPI server first.")
        st.code("python main.py", language="bash")
        return
    
    # Step indicator
    st.markdown(f"""
    <div class="step-indicator">
        <div class="step {'active' if st.session_state.current_step == 1 else ''}">
            <strong>Step 1</strong><br>Process Sources
        </div>
        <div class="step {'active' if st.session_state.current_step == 2 else ''}">
            <strong>Step 2</strong><br>Ask Questions
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # Sidebar
    with st.sidebar:
        st.header("📋 Session Info")
        
        # Session management
        col1, col2 = st.columns(2)
        with col1:
            st.info(f"**ID:** {st.session_state.session_id}")
        with col2:
            if st.button("🔄 New Session", use_container_width=True):
                # Reset all session state
                for key in list(st.session_state.keys()):
                    del st.session_state[key]
                initialize_session_state()
                st.rerun()
        
        # Processing status
        st.header("📊 Status")
        if st.session_state.processing_completed:
            st.success("✅ Sources Processed")
        else:
            st.warning("⏳ No Sources Processed")
        
        # Processed sources info
        st.header("📄 Processed Sources")
        if st.session_state.processed_sources:
            for i, source in enumerate(st.session_state.processed_sources, 1):
                with st.expander(f"Source {i}", expanded=False):
                    if 'url' in source and source['url']:
                        st.write(f"**🌐 URL:** {source['url']}")
                    if 'file' in source and source['file']:
                        st.write(f"**📁 File:** {source['file']}")
                    if 'chunks' in source:
                        st.write(f"**📊 Chunks:** {source['chunks']}")
        else:
            st.write("No sources processed yet")
        
        # Chat history count
        st.header("💬 Chat Stats")
        st.markdown(f"""
        <div class="metric-card">
            <h3>{len(st.session_state.chat_history)}</h3>
            <p>Questions Asked</p>
        </div>
        """, unsafe_allow_html=True)
    
    # Main content
    if st.session_state.current_step == 1 or not st.session_state.processing_completed:
        # Step 1: Process Sources
        st.header("📤 Step 1: Process Your Sources")
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            # URL input with proper default handling
            url_input = st.text_input(
                "🌐 Enter URL (Optional)",
                value="",  # Empty default value
                placeholder="https://example.com/article",
                help="Enter a web page URL to process its content"
            )
            
            # File upload
            uploaded_file = st.file_uploader(
                "📁 Upload PDF Document (Optional)",
                type=['pdf'],
                accept_multiple_files=False,
                help="Upload a PDF document to process its content"
            )
            
            # Validation message
            if not url_input.strip() and uploaded_file is None:
                st.info("💡 Please provide at least one source: URL or PDF document")
            
        with col2:
            st.markdown("### Quick Actions")
            
            # Process button
            process_disabled = not url_input.strip() and uploaded_file is None
            
            if st.button(
                "🚀 Process Sources", 
                type="primary", 
                use_container_width=True,
                disabled=process_disabled
            ):
                if not url_input.strip() and uploaded_file is None:
                    st.error("❌ Please provide either a valid URL or upload a PDF file.")
                else:
                    with st.spinner("🔄 Processing sources... This may take a moment."):
                        success, result = process_sources(url_input, uploaded_file, st.session_state.session_id)

                        if success:
                            st.success("✅ Sources processed successfully!")

                            st.session_state.processing_completed = True
                            st.session_state.current_step = 2

                            source_info = {}
                            if url_input.strip():
                                source_info['url'] = url_input.strip()
                            if uploaded_file:
                                source_info['file'] = uploaded_file.name
                            if 'sources_processed' in result:
                                source_info['chunks'] = result['sources_processed']['total_chunks']

                            st.session_state.processed_sources.append(source_info)

                            if 'processing_details' in result:
                                st.write("**Processing Details:**")
                                for detail in result['processing_details']:
                                    if '✓' in detail:
                                        st.markdown(f'<div class="status-success">{detail}</div>', unsafe_allow_html=True)
                                    else:
                                        st.markdown(f'<div class="status-error">{detail}</div>', unsafe_allow_html=True)

                            time.sleep(2)
                            st.rerun()
                        else:
                            st.error(f"❌ Processing failed: {result.get('detail', 'Unknown error')}")

            
            # Skip to query (if sources already processed)
            if st.session_state.processing_completed:
                if st.button("💬 Go to Questions", type="secondary", use_container_width=True):
                    st.session_state.current_step = 2
                    st.rerun()
    
    if st.session_state.current_step == 2 and st.session_state.processing_completed:
        # Step 2: Ask Questions
        st.header("💬 Step 2: Ask Questions")
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            # Question input
            question = st.text_area(
                "❓ Your Question",
                value="",  # Empty default value
                placeholder="What are the main points discussed in the documents?",
                height=120,
                help="Ask any question about the processed content"
            )
            
            # Query button
            query_disabled = not question.strip()
            
            if st.button(
                "🔍 Get Answer", 
                type="primary", 
                use_container_width=True,
                disabled=query_disabled
            ):
                if question.strip():
                    with st.spinner("🤔 Thinking... Getting your answer."):
                        success, result = query_sources(question, st.session_state.session_id)
                        
                        if success:
                            # Add to chat history
                            st.session_state.chat_history.append({
                                'question': question.strip(),
                                'answer': result['answer']
                            })
                            
                            st.success("✅ Answer generated!")
                            st.rerun()
                        else:
                            st.error(f"❌ Query failed: {result.get('detail', 'Unknown error')}")
        
        with col2:
            st.markdown("### Actions")
            
            if st.button("📤 Process New Sources", type="secondary", use_container_width=True):
                st.session_state.current_step = 1
                st.rerun()
            
            if st.button("🧹 Clear Chat", type="secondary", use_container_width=True):
                st.session_state.chat_history = []
                st.rerun()
        
        # Display chat history
        st.header("💭 Conversation History")
        
        if st.session_state.chat_history:
            # Reverse order to show latest first
            for i, chat in enumerate(reversed(st.session_state.chat_history)):
                # Question
                st.markdown(f"""
                <div class="chat-message-user">
                    <strong>🙋 You asked:</strong><br>
                    {chat['question']}
                </div>
                """, unsafe_allow_html=True)
                
                # Answer
                st.markdown(f"""
                <div class="chat-message-bot">
                    <strong>🤖 Assistant:</strong><br>
                    {chat['answer']}
                </div>
                """, unsafe_allow_html=True)
                
                st.markdown("---")
        else:
            st.info("💡 No questions asked yet. Type a question above to get started!")
    
    elif st.session_state.current_step == 2 and not st.session_state.processing_completed:
        st.warning("⚠️ Please process some sources first before asking questions.")
        if st.button("📤 Go to Step 1", type="primary"):
            st.session_state.current_step = 1
            st.rerun()

if __name__ == "__main__":
    main()