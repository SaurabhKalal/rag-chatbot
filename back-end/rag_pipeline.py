from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.chains import RetrievalQA
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain_ollama import OllamaLLM
from config import GROK_API_KEY
from langchain.chains import create_history_aware_retriever, create_retrieval_chain
import re

# from data_processing import create_contextual_retriever

def format_docs(retrieved_docs):
    context_text = "\n\n".join(doc.page_content for doc in retrieved_docs)
    return context_text

def get_local_chat_llm():
    try:
        print("Initializing Ollama connection...")
        
        llm = OllamaLLM(
            base_url='http://localhost:11434',
            model="qwen2.5:0.5b",
            temperature=0.7,
            top_k=10,
            top_p=0.9,
            num_ctx=2048,
            timeout=300
        )
        
        print("Testing connection...")
        test_response = llm.invoke("Hello")
        print(f"Test response: {test_response[:50]}...")
        
        return llm
        
    except Exception as e:
        print(f"Ollama connection failed: {str(e)}")
        print("\nTry these steps:")
        print("1. Run 'ollama serve' in a separate terminal")
        print("2. Verify with: curl http://localhost:11434/api/tags")
        print("3. Check model exists: ollama list")
        return None


from langchain_openai import ChatOpenAI
import os

def get_groq_chat_llm():
    try:
        print("Initializing Groq LLM connection...")

        # Set the Groq API key and endpoint (OpenAI-compatible)
        os.environ["OPENAI_API_KEY"] = GROK_API_KEY  # 🔒 Replace with your key
        groq_llm = ChatOpenAI(
            base_url="https://api.groq.com/openai/v1",
            model="llama-3.3-70b-versatile",
            api_key= GROK_API_KEY, # or "mistral-7b-instruct"
            temperature=0.3,
            max_tokens=2048,
            timeout=30,
        )

        # Optional: test the LLM
        test = groq_llm.invoke("Hello from Groq!")
        print(f"Groq response: {test.content[:60]}...")

        return groq_llm

    except Exception as e:
        print(f"Groq connection failed: {e}")
        return None



def create_simple_rag_chain(llm, vectorstore, use_contextual=False):
    try:
        retriever = vectorstore.as_retriever()
        if use_contextual:
            retriever = create_contextual_retriever(retriever, llm)
        
        return RetrievalQA.from_chain_type(
            llm=llm,
            chain_type="stuff",
            retriever=retriever,
            return_source_documents=True,
            verbose=True
        )
    except Exception as e:
        print(f"Error creating simple RAG chain: {e}")
        return None


def create_smart_conversational_rag(llm, vectorstore, use_contextual=False):
    try:
        retriever = vectorstore.as_retriever()
        if use_contextual:
            retriever = create_contextual_retriever(retriever, llm)
            
        contextualize_q_prompt = ChatPromptTemplate.from_messages([
            ("system", """You are rephrasing follow-up questions to be standalone questions.
            
            IMPORTANT RULES:
            1. If the follow-up question seems to be about a completely different topic than the recent conversation, treat it as already standalone and change it minimally.
            2. Only incorporate conversation context if the question clearly references something from the recent discussion.
            3. Preserve the original intent and scope of the question.
            4. Don't assume connections that aren't explicitly made by the user.
            
            Recent conversation context:"""),
            MessagesPlaceholder(variable_name="chat_history"),
            ("human", "Follow-up question: {input}\n\nStandalone question:"),
        ])
        
        history_aware_retriever = create_history_aware_retriever(
            llm, retriever, contextualize_q_prompt
        )
        
        qa_prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a helpful assistant answering questions based on the provided context.

            INSTRUCTIONS:
            1. Answer the question based on the context provided below.
            2. If the context doesn't contain relevant information for the question, clearly state that you don't have that information in the provided documents.
            3. Be comprehensive but accurate - don't make assumptions beyond what's in the context.
            4. If the question seems to be about a different topic than previous questions, focus only on what's relevant to the current question.
            
            Context:
            {context}"""),
            MessagesPlaceholder(variable_name="chat_history"),
            ("human", "{input}"),
        ])
        
        question_answer_chain = create_stuff_documents_chain(llm, qa_prompt)
        conversational_rag_chain = create_retrieval_chain(
            history_aware_retriever,
            question_answer_chain
        )
        
        return conversational_rag_chain
        
    except Exception as e:
        print(f"Error creating smart conversational RAG: {e}")
        return None

def create_hybrid_rag_chain(llm, vectorstore, use_contextual=False):
    try:
        retriever = vectorstore.as_retriever()
        if use_contextual:
            retriever = create_contextual_retriever(retriever, llm)
            
        simple_chain = RetrievalQA.from_chain_type(
            llm=llm,
            chain_type="stuff",
            retriever=retriever,
            return_source_documents=True,
            verbose=False
        )
        
        conversational_chain = create_smart_conversational_rag(llm, vectorstore, use_contextual)
        
        return {
            'simple': simple_chain,
            'conversational': conversational_chain
        }
        
    except Exception as e:
        print(f"Error creating hybrid RAG chain: {e}")
        return None

def create_conversational_rag(llm, vectorstore, use_contextual=False):
    try:
        retriever = vectorstore.as_retriever()
        if use_contextual:
            retriever = create_contextual_retriever(retriever, llm)
            
        contextualize_q_prompt = ChatPromptTemplate.from_messages([
            ("system", """Given a chat history and the latest user question which might reference the chat history, formulate a standalone question which can be understood without the chat history.

            IMPORTANT: 
            - If the question appears to be about a completely new topic, keep it mostly unchanged.
            - Only add context if the question explicitly references previous conversation (using words like "that", "it", "them", "also", "additionally").
            - Preserve the original question's scope and intent.
            
            Do NOT make assumptions about connections between topics."""),
            MessagesPlaceholder(variable_name="chat_history"),
            ("human", "{input}"),
        ])
        
        history_aware_retriever = create_history_aware_retriever(
            llm, retriever, contextualize_q_prompt
        )
        
        qa_prompt = ChatPromptTemplate.from_messages([
            ("system", """Answer the question based only on the following context:
            {context}
            
            Be accurate and comprehensive. If you don't know the answer based on the provided context, just say you don't know. 
            Don't make assumptions or connections that aren't clearly supported by the context."""),
            MessagesPlaceholder(variable_name="chat_history"),
            ("human", "{input}"),
        ])
        
        question_answer_chain = create_stuff_documents_chain(llm, qa_prompt)
        conversational_rag_chain = create_retrieval_chain(
            history_aware_retriever,
            question_answer_chain
        )
        
        return conversational_rag_chain
        
    except Exception as e:
        print(f"Error creating conversational RAG: {e}")
        return None
    


if __name__ == "__main__":
    llm = get_groq_chat_llm()
    if llm:
        res = llm.invoke("What's the capital of France?")
        print(res.content)