import os
import requests
import json
import time
import sys
from dotenv import load_dotenv

load_dotenv()

# --- CONFIGURATION ---
API_KEY = os.getenv("LAMATIC_API_KEY")
PROJECT_ID = os.getenv("LAMATIC_PROJECT_ID")
WORKFLOW_ID = os.getenv("LAMATIC_CHAT_FLOW_ID")
ENDPOINT=os.getenv("GRAPHQL_ENDPOINT")
# ---------------------
#-----VALIDATION--------
if not API_KEY or not WORKFLOW_ID:
  print("Error:Keys not found. Please check your .env file.")
  sys.exit(1)
#------------------------


def type_effect(text, delay=0.01):
    for char in text:
        sys.stdout.write(char)
        sys.stdout.flush()
        time.sleep(delay)
    print("")

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
                # 1. Get the result string from GraphQL
                raw_result = data['data']['executeWorkflow']['result']
                
                # 2. Parse it into a Python Dictionary
                parsed = json.loads(raw_result)
                
                # 3. CLEAN UP: Extract ONLY the text
                if isinstance(parsed, dict):
                    # Check for "answer" (The key showing in your output)
                    if 'answer' in parsed:
                        return parsed['answer']
                    
                    # Check for "body" -> "answer" (Another common format)
                    if 'body' in parsed and isinstance(parsed['body'], dict):
                        return parsed['body'].get('answer', str(parsed))
                        
                # Fallback: If we can't find the key, return the whole thing
                return str(parsed)
                    
            except Exception as e:
                # If it's just plain text, return it
                return raw_result
        else:
            return f"Error {response.status_code}: {response.text}"
    except Exception as e:
        return f"Connection Error: {e}"

def main():
    print("\033[1;32m") 
    print("==========================================")
    print("   LINUX KERNEL RAG ASSISTANT      ")
    print("==========================================\n")
    print("\033[0m")

    while True:
        user_input = input("\033[1;34mroot@kernel-rag:~$ \033[0m")
        if user_input.lower() in ['exit', 'quit']:
            break
        
        if not user_input.strip():
            continue

        print("\n\033[0;33m[!] Reading Docs...\033[0m")
        answer = send_question(user_input)
        
        print("\033[1;32m")
        type_effect(f"> {answer}")
        print("\033[0m\n")

if __name__ == "__main__":
    main()
