import streamlit as st
import requests
import json
from qdrant_client import QdrantClient

# --- PAGE CONFIG ---
st.set_page_config(
    page_title="Linux Kernel RAG",
    page_icon="🐧",
    layout="centered"
)

# --- CONFIGURATION ---
try:
    # API Credentials
    API_KEY = st.secrets["LAMATIC_API_KEY"]
    PROJECT_ID = st.secrets["LAMATIC_PROJECT_ID"]
    
    # Flow IDs (The "Trinity")
    EMBED_FLOW_ID = st.secrets["LAMATIC_EMBED_FLOW_ID"] # Helper Flow
    CHAT_FLOW_ID = st.secrets["LAMATIC_CHAT_FLOW_ID"]   # Main Chat Flow
    
    # Qdrant Credentials
    QDRANT_URL = st.secrets["QDRANT_URL"]
    QDRANT_API_KEY = st.secrets["QDRANT_API_KEY"]
    
    # Constants
    ENDPOINT = "https://mode664-linuxkernelcompanion375.lamatic.dev/graphql"
    COLLECTION_NAME = "linux_kernel_vectors_v2" 
    
except FileNotFoundError:
    st.error("Secrets not found! Please set up `.streamlit/secrets.toml` or Streamlit Cloud Secrets.")
    st.stop()

# --- INITIALIZE QDRANT ---
@st.cache_resource
def get_qdrant_client():
    return QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)

client = get_qdrant_client()

# --- HELPER 1: Get Vector ---
def get_embedding(text):
    """Calls Lamatic Embedder Flow to convert text -> vector"""
    query = """
    query ExecuteWorkflow($workflowId: String!, $payload: JSON!) {
      executeWorkflow(workflowId: $workflowId, payload: $payload) {
        result
      }
    }
    """
    variables = {
        "workflowId": EMBED_FLOW_ID,
        "payload": { "text": text }
    }
    headers = {"Authorization": f"Bearer {API_KEY}", "x-project-id": PROJECT_ID}
    
    try:
        resp = requests.post(ENDPOINT, json={"query": query, "variables": variables}, headers=headers)
        if resp.status_code != 200:
            st.error(f"Embedder Error: {resp.text}")
            return None

        data = resp.json()
        
        # Check for GraphQL errors
        if 'errors' in data:
            st.error(f"GraphQL Error: {data['errors'][0]['message']}")
            return None

        raw = data['data']['executeWorkflow']['result']
        
        # Parse the inner result string
        try:
            if isinstance(raw, str):
                parsed = json.loads(raw)
            else:
                parsed = raw
        except:
            st.error("Failed to parse embedding result.")
            return None
        
        # Smart Find Logic: Hunt for the List of Floats
        def find_vector_recursive(obj):
            if isinstance(obj, list):
                if len(obj) > 0 and isinstance(obj[0], (float, int)):
                    return obj
                if len(obj) > 0 and isinstance(obj[0], list):
                    return find_vector_recursive(obj[0])
                return None
            if isinstance(obj, dict):
                for key in ['vector', 'embeddings', 'data', 'body']:
                    if key in obj:
                        found = find_vector_recursive(obj[key])
                        if found: return found
                for value in obj.values():
                    found = find_vector_recursive(value)
                    if found: return found
            return None

        final_vector = find_vector_recursive(parsed)
            
        return final_vector
    except Exception as e:
        st.error(f"Failed to generate embedding: {e}")
        return None

# --- HELPER 2: Get Answer---
def get_answer(question, context):
    """Calls Lamatic Chat Flow with the Question + Retrieved Context"""
    query = """
    query ExecuteWorkflow($workflowId: String!, $payload: JSON!) {
      executeWorkflow(workflowId: $workflowId, payload: $payload) {
        result
      }
    }
    """
    variables = {
        "workflowId": CHAT_FLOW_ID,
        "payload": { 
            "question": question, 
            "context": context 
        }
    }
    headers = {"Authorization": f"Bearer {API_KEY}", "x-project-id": PROJECT_ID}
    
    try:
        resp = requests.post(ENDPOINT, json={"query": query, "variables": variables}, headers=headers)
        data = resp.json()
        
        if 'errors' in data:
             return f"Server Error: {data['errors'][0]['message']}"
        
        # Parse Result
        raw_result = data['data']['executeWorkflow']['result']
        
        # Logic to handle String vs Dict responses
        if isinstance(raw_result, dict):
            parsed = raw_result
        else:
            try:
                parsed = json.loads(raw_result)
            except:
                return raw_result # Plain text fallback

        # Extract answer from 'body' or root
        if isinstance(parsed, dict):
            return parsed.get('body', {}).get('answer') or \
                   parsed.get('answer') or \
                   parsed.get('response') or \
                   str(parsed)
                   
        return str(parsed)
    except Exception as e:
        return f"Error getting answer: {e}"

# --- UI LAYOUT ---
st.title("🐧 Linux Kernel Assistant")
st.caption("Powered by **Lamatic** (Vision RAG) and **Qdrant**")

# Initialize chat history
if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "assistant", "content": "I can explain Kernel configurations and ASCII diagrams. What would you like to know?"}]

# Display history
for msg in st.session_state.messages:
    st.chat_message(msg["role"]).write(msg["content"])


# --- MAIN LOGIC ---
if prompt := st.chat_input("Ask about the Kernel (e.g. 'Explain AUDIT config')"):
    # 1. Show User Message
    st.session_state.messages.append({"role": "user", "content": prompt})
    st.chat_message("user").write(prompt)

    with st.chat_message("assistant"):
        
        # Initialize variables
        context_text = ""
        answer = ""
        
        # 2. THE THINKING PROCESS 
        with st.status("Analyzing Request...", expanded=True) as status:
            
            # Step A: Embed
            st.write("🧠 Generating Query Vector (Lamatic)...")
            query_vector = get_embedding(prompt)
            
            if query_vector:
                # Step B: Search
                st.write("🔍 Searching Qdrant Index...")
                try:
                    search_results = client.search(
                        collection_name=COLLECTION_NAME,
                        query_vector=query_vector,
                        limit=13
                    )
                except Exception as e:
                    st.error(f"Search failed: {e}")
                    search_results = []

                if search_results:
                    # Step C: Compile Context
                    context_text = "\n\n---\n\n".join([hit.payload.get("text", "") for hit in search_results])
                    st.write(f"✅ Found {len(search_results)} relevant documents.")
                    
                    # Step D: Generate
                    st.write("📝 Synthesizing Answer with LLM...")
                    answer = get_answer(prompt, context_text)
                    
                    # Close the status box cleanly
                    status.update(label="Analysis Complete", state="complete", expanded=False)
                else:
                    status.update(label="No Context Found", state="error")
                    st.warning("I couldn't find any relevant docs in Qdrant.")
            else:
                status.update(label="Vectorization Failed", state="error")

        # 3. SHOW THE ANSWER 
        if answer:
            st.markdown(answer)
            
            # Save to history
            st.session_state.messages.append({"role": "assistant", "content": answer})
            
            # 4. OPTIONAL: Sources Expander
            if context_text:
                with st.expander("📚 View Source Context"):
                    st.caption("Retrieved from Linux Kernel Docs via Qdrant")
                    st.text(context_text)
