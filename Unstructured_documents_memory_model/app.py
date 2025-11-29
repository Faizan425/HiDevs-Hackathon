import streamlit as st
import requests
import json
import time

# --- CONFIGURATION  ---

try:
    API_KEY = st.secrets["LAMATIC_API_KEY"]
    PROJECT_ID = st.secrets["LAMATIC_PROJECT_ID"]
    WORKFLOW_ID = st.secrets["LAMATIC_CHAT_FLOW_ID"]
    ENDPOINT = "https://mode664-linuxkernelcompanion375.lamatic.dev/graphql"
except FileNotFoundError:
    st.error("Secrets not found! Please set them up in Streamlit Cloud.")
    st.stop()

# --- THE LOGIC  ---
def send_question(question):
    query = """
    query ExecuteWorkflow($workflowId: String!, $payload: JSON!) {
      executeWorkflow(
        workflowId: $workflowId
        payload: $payload
      ) {
        status
        result
      }
    }
    """
    
    variables = {
        "workflowId": WORKFLOW_ID,
        "payload": { "question": question }
    }

    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
        "x-project-id": PROJECT_ID
    }

    try:
        response = requests.post(ENDPOINT, json={"query": query, "variables": variables}, headers=headers)
        if response.status_code == 200:
            data = response.json()
            if 'errors' in data:
                return f"Server Error: {data['errors'][0]['message']}"

            try:
                raw_result = data['data']['executeWorkflow']['result']
                # Parse JSON string if needed
                try:
                    parsed = json.loads(raw_result)
                    if isinstance(parsed, dict):
                        return parsed.get('body', {}).get('answer') or \
                               parsed.get('answer') or \
                               parsed.get('response') or str(parsed)
                    return str(parsed)
                except:
                    return raw_result # Plain text
            except Exception as e:
                return f"Parsing Error: {e}"
        else:
            return f"Error {response.status_code}: {response.text}"
    except Exception as e:
        return f"Connection Error: {e}"

# --- THE UI ---
st.set_page_config(page_title="Linux Kernel RAG", page_icon="🐧")

st.title("🐧 Linux Kernel Assistant")
st.markdown("Powered by **Lamatic** (Vision AI) and **Qdrant**.")

# Initialize chat history
if "messages" not in st.session_state:
    st.session_state.messages = []

# Display chat messages from history on app rerun
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# React to user input
if prompt := st.chat_input("Ask about the Kernel (e.g. 'Explain AUDIT config')"):
    # Display user message
    st.chat_message("user").markdown(prompt)
    st.session_state.messages.append({"role": "user", "content": prompt})

    # Display assistant response
    with st.chat_message("assistant"):
        with st.spinner("Reading Documentation..."):
            response = send_question(prompt)
            st.markdown(response)
            
    st.session_state.messages.append({"role": "assistant", "content": response})
