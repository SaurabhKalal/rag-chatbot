import streamlit as st
import requests
import json
import time
from typing import Optional, List, Dict
import base64

# =========================
# Configuration (editable in sidebar)
# =========================
DEFAULT_API_BASE_URL = "http://127.0.0.1:8000"
DEFAULT_TEMP_URL = "process"  # or "query"
DEFAULT_PASSWORD = "password"
MAX_QUERY_CHARS = 500

# -------------------------
# Session State Init
# -------------------------
def initialize_session_state():
    """Initialize all session state variables"""
    if 'initialized' not in st.session_state:
        st.session_state.initialized = True
        # Config reflecting sidebar controls
        st.session_state.api_base_url = DEFAULT_API_BASE_URL
        st.session_state.temp_url = DEFAULT_TEMP_URL

        # Auth / role
        st.session_state.is_logged_in = False
        st.session_state.login_type = ''          # 'user' or 'admin'
        st.session_state.selected_role = ''       # 'user' or 'admin'

        # Core data
        st.session_state.session_id = ''
        st.session_state.query = ''
        st.session_state.answer = ''

        # Admin ingest form
        st.session_state.web_url = ''
        st.session_state.uploaded_file = None

        # UX messages
        st.session_state.error_message = ''
        st.session_state.success_message = ''

        # Process state
        st.session_state.processing_status = []
        st.session_state.show_next_steps = False

        # Admin session selection
        st.session_state.session_mode = ''        # 'new' or 'existing'
        st.session_state.available_namespaces = []
        st.session_state.selected_namespace = ''
        st.session_state.new_session_name = ''


def clear_messages():
    st.session_state.error_message = ''
    st.session_state.success_message = ''


def show_error(message: str):
    st.session_state.error_message = message


def show_success(message: str):
    st.session_state.success_message = message


def generate_session_id() -> str:
    ts = str(int(time.time()))
    import random, string
    rand = ''.join(random.choices(string.ascii_lowercase + string.digits, k=5))
    return f"{ts}_{rand}"

# -------------------------
# API Helpers (use dynamic sidebar-configured base URL)
# -------------------------

def _base(url_path: str) -> str:
    return f"{st.session_state.api_base_url.rstrip('/')}/{url_path.lstrip('/')}"


def test_connection() -> bool:
    """Test connection to the backend"""
    try:
        response = requests.get(_base('/health'), timeout=5)
        if response.ok:
            try:
                payload = response.json()
            except Exception:
                payload = {"detail": "ok"}
            show_success(f"✅ Connection successful: {payload}")
            return True
        else:
            show_error(f"❌ Backend is running but returned {response.status_code}")
            return False
    except requests.exceptions.RequestException:
        show_error("❌ Cannot connect to backend. Check the base URL/port.")
        return False


def fetch_namespaces() -> List[str]:
    """Fetch available namespaces for admin"""
    try:
        response = requests.get(_base('/namespaces'), timeout=8)
        if response.ok:
            data = response.json()
            return data.get('namespaces', [])
        return []
    except requests.exceptions.RequestException:
        return []


def validate_session(session_id: str) -> Dict:
    """Validate session ID"""
    try:
        response = requests.post(
            _base('/validate-session'),
            json={"session_id": session_id.strip()},
            timeout=12
        )
        if response.ok:
            return response.json()
        # try to surface server error text
        try:
            txt = response.text[:200]
        except Exception:
            txt = ''
        return {"valid": False, "error": f"HTTP {response.status_code}: {txt}"}
    except requests.exceptions.RequestException as e:
        return {"valid": False, "error": f"Connection error: {str(e)}"}


def query_documents(question: str, session_id: str, is_admin: bool = False) -> Dict:
    """Query the documents"""
    try:
        query_session_id = '*' if is_admin else session_id
        response = requests.post(
            _base('/' + st.session_state.temp_url),
            json={
                "question": question,
                "session_id": query_session_id,
                "is_admin": is_admin
            },
            timeout=40
        )
        if response.ok:
            return {"success": True, "data": response.json()}
        try:
            txt = response.text[:200]
        except Exception:
            txt = ''
        return {"success": False, "error": f"HTTP {response.status_code}: {txt}"}
    except requests.exceptions.RequestException as e:
        return {"success": False, "error": f"Connection error: {str(e)}"}


def process_content(session_id: str, url: str = None, file_content: bytes = None, filename: str = None) -> Dict:
    """Process content (URL or file)"""
    try:
        files = {}
        data = {"session_id": session_id}

        if url:
            data["url"] = url
        if file_content and filename:
            files["file"] = (filename, file_content, "application/pdf")

        response = requests.post(
            _base('/process'),
            data=data,
            files=files if files else None,
            timeout=120
        )
        if response.ok:
            return {"success": True, "data": response.json()}
        try:
            txt = response.text[:200]
        except Exception:
            txt = ''
        return {"success": False, "error": f"HTTP {response.status_code}: {txt}"}
    except requests.exceptions.RequestException as e:
        return {"success": False, "error": f"Connection error: {str(e)}"}

# -------------------------
# UI Components
# -------------------------

def render_header():
    st.markdown(
        """
        <div style="text-align: center; padding: 1rem 0;">
            <h1 style="color: #00d4ff; font-size: 3rem; margin: 0;">RAG Chatbot</h1>
            <p style="color: #cfe8ff; font-size: 1.05rem;">AI-Powered Legal Document Analysis</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_messages():
    if st.session_state.error_message:
        st.error(f"🚫 {st.session_state.error_message}")
    if st.session_state.success_message:
        st.success(f"✅ {st.session_state.success_message}")


def render_portal_selection():
    st.markdown("### Choose Your Portal")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("👤 User Portal", use_container_width=True):
            st.session_state.login_type = 'user'
            clear_messages()
            st.rerun()
    with col2:
        if st.button("🛡️ Admin Console", use_container_width=True):
            st.session_state.login_type = 'admin'
            st.session_state.selected_role = 'admin'
            st.session_state.is_logged_in = True
            clear_messages()
            st.rerun()


def render_user_login():
    st.markdown("### 👤 User Portal Login")
    st.caption("Enter your credentials to access the AI Query Interface")

    with st.form("user_login_form"):
        session_id = st.text_input("🧠 Session ID", help="Must exist with processed documents")
        # Password with show/hide toggle
        c1, c2 = st.columns([3,1])
        with c1:
            show_pw = st.checkbox("Show password", value=False)
        with c2:
            st.write("")
        password = st.text_input("🔒 Password", type="default" if show_pw else "password", help=f"Default password is '{DEFAULT_PASSWORD}'")

        colA, colB = st.columns(2)
        with colA:
            login_submitted = st.form_submit_button("🔐 Access Portal", use_container_width=True)
        with colB:
            if st.form_submit_button("← Back", use_container_width=True):
                st.session_state.login_type = ''
                clear_messages()
                st.rerun()

    if login_submitted:
        if password != DEFAULT_PASSWORD:
            show_error("Invalid password. Default password is 'password'.")
            st.rerun()
        if not session_id.strip():
            show_error("Please enter a session ID.")
            st.rerun()

        with st.spinner("Validating session..."):
            result = validate_session(session_id)
        if result.get("valid"):
            st.session_state.session_id = session_id.strip()
            st.session_state.selected_role = 'user'
            st.session_state.is_logged_in = True
            show_success(f"Welcome! Session '{result['session_id']}' loaded with {result.get('vector_count', 0)} documents.")
            st.rerun()
        else:
            show_error(result.get("error", "Session not found"))
            st.rerun()


def render_user_interface():
    st.markdown("### 💬 AI Query Interface")

    # Admin quick switch back to Admin Console
    if st.session_state.login_type == 'admin':
        if st.button("📤 Upload New Document (Admin)"):
            st.session_state.selected_role = 'admin'
            clear_messages()
            st.rerun()

    with st.form("query_form"):
        query_text = st.text_area(
            "🧠 Your Question",
            value=st.session_state.query,
            height=150,
            placeholder=(
                "Ask anything about ALL processed documents across all sessions... (Global Search)"
                if st.session_state.login_type == 'admin'
                else "Ask me anything about the processed documents..."
            ),
            help=f"Sends POST to /{st.session_state.temp_url}"
        )
        # Character counter
        st.caption(f"{min(len(query_text), MAX_QUERY_CHARS)}/{MAX_QUERY_CHARS}")
        submit_query = st.form_submit_button("🚀 Get Intelligent Answer", use_container_width=True)

    if submit_query:
        q = (query_text or '').strip()[:MAX_QUERY_CHARS]
        if not q:
            show_error("Please enter a question.")
        else:
            st.session_state.query = q
            with st.spinner("Processing your question..."):
                result = query_documents(
                    q,
                    st.session_state.session_id,
                    is_admin=(st.session_state.login_type == 'admin')
                )
            if result.get("success"):
                st.session_state.answer = result["data"].get("answer", "")
                clear_messages()
            else:
                show_error(result.get("error", "Failed to get answer"))
        st.rerun()

    if st.session_state.answer:
        st.markdown("### 🤖 AI Response")
        st.markdown("⭐" * 5)
        st.write(st.session_state.answer)


def render_session_selection():
    st.markdown("### ⭐ Session ID Selection")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("✨ Create New Session", use_container_width=True):
            st.session_state.session_mode = 'new'
            st.session_state.new_session_name = generate_session_id()
            st.rerun()
    with col2:
        if st.button("📄 Use Existing Session", use_container_width=True):
            st.session_state.session_mode = 'existing'
            st.session_state.available_namespaces = fetch_namespaces()
            st.rerun()

    if st.session_state.session_mode == 'new':
        st.session_state.new_session_name = st.text_input(
            "New Session Name",
            value=st.session_state.new_session_name,
            help="Enter session name or use generated ID"
        )
        if st.session_state.new_session_name:
            st.info(f"📝 New Session: {st.session_state.new_session_name}")

    elif st.session_state.session_mode == 'existing':
        if st.session_state.available_namespaces:
            st.session_state.selected_namespace = st.selectbox(
                "Select Existing Namespace",
                options=[''] + st.session_state.available_namespaces,
                index=0 if not st.session_state.selected_namespace else st.session_state.available_namespaces.index(st.session_state.selected_namespace) + 1
            )
            if st.session_state.selected_namespace:
                st.info(f"📁 Existing Session: {st.session_state.selected_namespace}")
        else:
            st.warning("No existing namespaces found. Create a new session instead.")


def render_admin_interface():
    st.markdown("### 🛡️ Admin Control Center")

    if st.button("💬 Go to Chat"):
        st.session_state.selected_role = 'user'
        clear_messages()
        st.rerun()

    # Only render selection & ingest when not in next-steps
    if not st.session_state.show_next_steps:
        render_session_selection()
        session_selected = (
            (st.session_state.session_mode == 'new' and st.session_state.new_session_name.strip()) or
            (st.session_state.session_mode == 'existing' and st.session_state.selected_namespace)
        )

        if session_selected:
            st.markdown("---")
            st.markdown("### 🌐 Web Resource URL")
            st.session_state.web_url = st.text_input(
                "Enter URL",
                value=st.session_state.web_url,
                placeholder="https://example.com/page-to-process"
            )

            st.markdown("### 📄 Document Upload (PDF Only)")
            uploaded_file = st.file_uploader("Choose a PDF file", type=['pdf'])
            if uploaded_file is not None:
                st.session_state.uploaded_file = uploaded_file
                st.success(f"📁 File Ready: {uploaded_file.name}")

            can_submit = (
                (st.session_state.web_url.strip() or st.session_state.uploaded_file) and session_selected
            )
            if st.button("⚡ Process & Index Content", disabled=not can_submit, use_container_width=True):
                target_session_id = (
                    st.session_state.new_session_name.strip()
                    if st.session_state.session_mode == 'new'
                    else st.session_state.selected_namespace
                )
                with st.spinner("Processing sources..."):
                    file_content = None
                    filename = None
                    if st.session_state.uploaded_file:
                        file_content = st.session_state.uploaded_file.getvalue()
                        filename = st.session_state.uploaded_file.name
                    result = process_content(
                        target_session_id,
                        url=st.session_state.web_url.strip() or None,
                        file_content=file_content,
                        filename=filename
                    )
                if result.get("success"):
                    st.session_state.session_id = target_session_id
                    st.session_state.processing_status = result["data"].get("processing_details", [])
                    show_success(result["data"].get("status", "Processed successfully."))
                    st.session_state.show_next_steps = True
                    st.session_state.web_url = ''
                    st.session_state.uploaded_file = None
                else:
                    show_error(result.get("error", "Failed to process sources"))
                st.rerun()

    # Status & next steps
    if st.session_state.processing_status:
        st.markdown("### 📊 Processing Status")
        for status in st.session_state.processing_status:
            (st.success if status.startswith('✓') else st.error)(status)

    if st.session_state.show_next_steps:
        st.markdown("### 🎉 Processing Complete!")
        st.balloons()
        col1, col2 = st.columns(2)
        with col1:
            if st.button("💬 Chat with Document", use_container_width=True):
                st.session_state.selected_role = 'user'
                st.session_state.show_next_steps = False
                show_success("Content processed successfully! You can now ask questions about it.")
                st.rerun()
        with col2:
            if st.button("📤 Upload New Document", use_container_width=True):
                st.session_state.show_next_steps = False
                st.session_state.session_mode = ''
                st.session_state.selected_namespace = ''
                st.session_state.new_session_name = ''
                st.session_state.web_url = ''
                st.session_state.uploaded_file = None
                clear_messages()
                st.rerun()


def render_logout_button():
    if st.sidebar.button("🚪 Logout", use_container_width=True):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()

# -------------------------
# Main
# -------------------------
def main():
    st.set_page_config(
        page_title="RAG Chatbot Assistant",
        page_icon="🏠",
        layout="wide",
        initial_sidebar_state="expanded"
    )

    # Minimal styling
    st.markdown(
        """
        <style>
        .stApp { background: linear-gradient(135deg, #0f172a 0%, #111827 100%); }
        .stButton > button { background: linear-gradient(45deg, #06b6d4, #4f46e5); color: white; border: none; border-radius: 10px; padding: .5rem 1rem; font-weight: 700; }
        .stButton > button:hover { filter: brightness(1.05); }
        .stTextInput > div > div > input, .stTextArea > div > div > textarea { border-radius: 10px; }
        </style>
        """,
        unsafe_allow_html=True,
    )

    initialize_session_state()

    # Header
    render_header()

    # Sidebar controls
    with st.sidebar:
        st.markdown("### ⚙️ Settings")
        st.session_state.api_base_url = st.text_input("API Base URL", st.session_state.api_base_url)
        st.session_state.temp_url = st.selectbox("Chat endpoint", ["chat_legal", "query"], index=(0 if st.session_state.temp_url=="chat_legal" else 1))
        if st.button("🔍 Test Connection", use_container_width=True):
            test_connection()
        if st.session_state.is_logged_in:
            st.markdown("---")
            st.markdown("### 👤 Session Info")
            st.markdown(f"**User Type:** {st.session_state.login_type.title() if st.session_state.login_type else '-'}")
            st.markdown(f"**Role:** {st.session_state.selected_role.title() if st.session_state.selected_role else '-'}")
            st.markdown(f"**Session:** `{st.session_state.session_id or '-'}`")
            render_logout_button()
        st.markdown("---")
        st.markdown("### ℹ️ About")
        st.caption("AI-powered RAG Chatbot Assistant [Scrape Website and Document QnA]")

    # Global messages
    render_messages()

    # Main routing
    if not st.session_state.is_logged_in:
        if st.session_state.login_type == 'user':
            render_user_login()
        else:
            render_portal_selection()
    else:
        if st.session_state.selected_role == 'user':
            render_user_interface()
        elif st.session_state.selected_role == 'admin':
            render_admin_interface()


if __name__ == "__main__":
    main()
