🐧 Linux Kernel Unstructured RAG (Terminal Edition)
A multimodal retrieval system that makes "messy" Linux documentation—including ASCII art diagrams—searchable via a terminal interface.

⚡ The Problem
The Linux Kernel documentation is dense and unstructured. Crucial architectural concepts are often locked away in ASCII Art diagrams (memory layouts, state machines) or complex configuration blocks. Standard RAG pipelines treat these as "noise" or raw text, making them impossible to search semantically.

🚀 The Solution
This project implements a Multimodal Ingestion Pipeline using Lamatic.ai and Qdrant.

Visual Extraction: A Vision-Language Model (Gemini 1.5 Pro) scans the documentation during ingestion. It detects ASCII diagrams and writes a semantic description (e.g., "This diagram shows the relationship between AUDIT config and NET subsystems").

Stateless ETL: The ingestion engine is decoupled from storage. A Python bridge manages the data flow, preventing vendor lock-in and handling large vector dimensions (3072-dim).

Terminal Interface: A custom GraphQL-powered CLI that mimics a Linux shell for querying the knowledge base.

🛠️ Architecture
The system follows the Unix "Pipes and Filters" design pattern:
graph LR
    A[Web Source] -->|Scrape| B(Lamatic Compute)
    B -->|Vision AI + Clean| C{Vectorize}
    C -->|JSON Output| D[Python Bridge]
    D -->|gRPC| E[(Qdrant Cloud)]
    F[User Terminal] -->|GraphQL Query| B
    B -->|Retrieval| E

Tech Stack
Compute Engine: Lamatic.ai (Flow Orchestration, Firecrawl, Gemini Vision).

Vector Storage: Qdrant Cloud (Hybrid Search, 3072-dimension vectors).

Interface: Python 3 + GraphQL.

📦 Installation
1.Clone the repository
  git clone https://github.com/yourusername/linux-rag-challenge.git
cd linux-rag-challenge
---------------------------------------------
2.Install Dependencies
   pip install -r requirements.txt
--------------------------------------------
3.Configuration Open ingest.py and chat_cli.py and set your API keys:
   API_KEY = "lamatic_..."
   PROJECT_ID = "..."
   WORKFLOW_ID = "..."
------------------------------------------------


💻 Usage
1. Ingestion (The ETL Bridge)
Run the ingestion script to scrape the Kernel Docs, process the ASCII art, and push vectors to Qdrant.

python ingest.py
-----------------------------------------------------------
2. The Chat Interface
Launch the terminal assistant.

python chat_cli.py
-----------------------------------------------------------
