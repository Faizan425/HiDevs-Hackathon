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

# --- CONFIGURATION ) ---
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


# --- HELPER 1: Get Vector  ---
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
        
        # DEBUG: Uncomment this line if you still get errors to see the raw data on screen
        # st.write("Debug Raw Response:", resp.text) 
        
        if resp.status_code != 200:
            st.error(f"Embedder Error: {resp.text}")
            return None

        data = resp.json()
        
        # 1. Parse the inner GraphQL result string
        try:
            raw_result = data['data']['executeWorkflow']['result']
            if isinstance(raw_result, str):
                parsed = json.loads(raw_result)
            else:
                parsed = raw_result
        except:
            st.error("Failed to parse GraphQL result.")
            return None
            
        # 2. "Smart Find" Logic: Hunt for the List of Floats
        # This handles {"vector": [...]}, {"body": {"vector": [...]}}, or just [...]
        
        def find_vector_recursive(obj):
            """Recursively searches for a list of floats"""
            if isinstance(obj, list):
                # Check if it's a list of floats (The Vector!)
                if len(obj) > 0 and isinstance(obj[0], (float, int)):
                    return obj
                # Check if it's a list of lists (Batch Vector)
                if len(obj) > 0 and isinstance(obj[0], list):
                    return find_vector_recursive(obj[0])
                return None
            
            if isinstance(obj, dict):
                # Check common keys first
                for key in ['vector', 'embeddings', 'data', 'body']:
                    if key in obj:
                        found = find_vector_recursive(obj[key])
                        if found: return found
                # If not in common keys, search all values
                for value in obj.values():
                    found = find_vector_recursive(value)
                    if found: return found
            return None

        final_vector = find_vector_recursive(parsed)
        
        if final_vector:
            return final_vector
        else:
            st.error("Vector not found in response structure.")
            # st.write("Parsed Data was:", parsed) # Debug info
            return None
            
    except Exception as e:
        st.error(f"Connection Failed: {e}")
        return None

# --- HELPER 2: Get Answer ---
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
        # 2. STEP 1: EMBEDDING
        with st.status("Thinking...", expanded=False) as status:
            status.write("🧠 Generating Query Vector (Lamatic)...")
            query_vector = get_embedding(prompt)
            
            if query_vector:
                # 3. STEP 2: RETRIEVAL
                status.write("🔍 Searching Qdrant Index...")
                search_results = client.search(
                    collection_name=COLLECTION_NAME,
                    query_vector=query_vector,
                    limit=4
                )
                
                if search_results:
                    # Compile context
                    context_text = "\n\n---\n\n".join([hit.payload.get("text", "") for hit in search_results])
                    status.write(f"✅ Found {len(search_results)} relevant docs.")
                    
                    # 4. STEP 3: GENERATION
                    status.write("📝 Synthesizing Answer...")
                    answer = get_answer(prompt, context_text)
                    
                    # Show the answer
                    st.write(answer)
                    
                    # Save to history
                    st.session_state.messages.append({"role": "assistant", "content": answer})
                    
                    # Optional: Show Source (Judges love this)
                    with st.expander("View Retrieved Context (Source)"):
                        st.text(context_text)
                else:
                    st.warning("No relevant documentation found in Qdrant.")
                    status.update(label="No context found", state="error")
            else:
                st.error("Failed to vectorize question.")
                status.update(label="Vectorization Failed", state="error")
