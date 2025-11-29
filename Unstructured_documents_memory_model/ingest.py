import os
import requests
import json
import uuid
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct, VectorParams, Distance
from dotenv import load_dotenv

# --- CONFIGURATION -----------------------------------------
# 1. LAMATIC CONFIG (From your Ingestion Flow)
LAMATIC_API_KEY = os.getenv("LAMATIC_API_KEY")
LAMATIC_PROJECT_ID = os.getenv("LAMATIC_PROJECT_ID")
LAMATIC_INGESTION_FLOW_ID = os.getenv("LAMATIC_INGESTION_FLOW_ID")
LAMATIC_URL = os.getenv("LAMATIC_URL")
# 2. QDRANT CONFIG (From Qdrant Cloud)
QDRANT_URL = os.getenv("QDRANT_URL") # Your Cluster URL
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
COLLECTION_NAME = "collection_name"

# 3. VECTOR SIZE (Gemini Embedding-004 is usually 768)
VECTOR_SIZE = 3072 
# -----------------------------------------------------------

# Initialize Qdrant Client
q_client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)

def setup_collection():
    """Creates the collection in Qdrant if it doesn't exist"""
    if not q_client.collection_exists(COLLECTION_NAME):
        print(f"Creating collection: {COLLECTION_NAME}")
        q_client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
        )
    else:
        print(f"Collection {COLLECTION_NAME} exists.")

def call_lamatic_ingestion(url_to_scrape):
    """Calls Lamatic to scrape, clean, and vectorize."""
    print(f"Processing: {url_to_scrape}...")
    
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
        "workflowId": LAMATIC_FLOW_ID,
        "payload": { "url": url_to_scrape }
    }

    headers = {
        "Authorization": f"Bearer {LAMATIC_API_KEY}",
        "Content-Type": "application/json",
        "x-project-id": LAMATIC_PROJECT_ID
    }

    try:
        response = requests.post(LAMATIC_URL, json={"query": query, "variables": variables}, headers=headers)
        
        if response.status_code == 200:
            data = response.json()
            
            # Check for GraphQL errors
            if 'errors' in data:
                print(f"Server Error: {data['errors'][0]['message']}")
                return None

            try:
                # Get the result field
                raw_result = data['data']['executeWorkflow']['result']
                
                # --- DEBUG PRINT (Spy on the data) ---
                print(f"\n[DEBUG] Raw Response from Lamatic: {str(raw_result)[:200]}...") # Print first 200 chars
                # -------------------------------------

                # Case A: It's already a Dictionary
                if isinstance(raw_result, dict):
                    return raw_result
                    
                # Case B: It's a String
                if isinstance(raw_result, str):
                    parsed = json.loads(raw_result)
                    
                    # Check if keys are nested in "body"
                    if "body" in parsed:
                        print("[DEBUG] Found data nested in 'body'")
                        return parsed["body"]
                        
                    return parsed
                    
                return raw_result

            except Exception as e:
                print(f"Parsing Logic Error: {e} | Raw Data: {str(data)}")
                return None
        else:
            print(f"HTTP Error {response.status_code}: {response.text}")
            return None
    except Exception as e:
        print(f"Connection Error: {e}")
        return None

def upload_to_qdrant(data):
    """Takes vectors and text from Lamatic and pushes to Qdrant"""
    vectors = data.get("vectors", [])
    documents = data.get("documents", []) # Or "text" depending on your variable mapping
    source = data.get("source_url", "unknown")

    if not vectors or not documents:
        print("No data received from Lamatic.")
        return

    print(f"Received {len(vectors)} vectors. Uploading to Qdrant...")

    points = []
    for i, (vec, doc) in enumerate(zip(vectors, documents)):
        # Create a Point for Qdrant
        points.append(PointStruct(
            id=str(uuid.uuid4()), # Generate a unique ID
            vector=vec,
            payload={
                "text": doc,
                "source": source,
                "chunk_index": i
            }
        ))

    # Batch Upload
    q_client.upsert(
        collection_name=COLLECTION_NAME,
        points=points
    )
    print(f"Successfully stored {len(points)} chunks in Qdrant!")

def main():
    setup_collection()
    
    # List of URLs you want to ingest
    urls = [
        "https://www.kernel.org/doc/html/latest/process/coding-style.html",
        "https://www.kernel.org/doc/html/latest/admin-guide/mm/concepts.html" 
    ]

    for url in urls:
        result = call_lamatic_ingestion(url)
        if result:
            upload_to_qdrant(result)

if __name__ == "__main__":
    main()
