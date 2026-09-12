<div align="center">

  <h1>DocuMind AI</h1>
  <h3><em>Autonomous Document Intelligence Fabric for Enterprise & SMEs</em></h3>

  <p>
    <a href="https://github.com/Harshithreddy-ux/DOCUMIND-AI/blob/main/LICENSE"><img src="https://img.shields.io/badge/License-MIT-blue.svg" alt="License"></a>
    <a href="https://github.com/Harshithreddy-ux/DOCUMIND-AI/actions"><img src="https://img.shields.io/badge/Build-Passing-brightgreen.svg" alt="CI Status"></a>
    <img src="https://img.shields.io/badge/Python-3.10+-3776AB.svg?logo=python&logoColor=white" alt="Python Version">
    <img src="https://img.shields.io/badge/Orchestration-LangGraph-6f42c1.svg" alt="LangGraph">
    <img src="https://img.shields.io/badge/LLM-Ollama_4--bit-FF6F00.svg" alt="Ollama">
    <img src="https://img.shields.io/badge/OS-Windows_11-0078D4.svg?logo=windows&logoColor=white" alt="Windows 11">
    <img src="https://img.shields.io/badge/VRAM-≤_4GB-red.svg" alt="VRAM Ceiling">
  </p>

  <p>
    <strong>Transforming unstructured business documents (invoices, contracts, receipts, purchase orders) into a structured, queryable knowledge graph with automated decisioning and human-in-the-loop governance.</strong>
  </p>

  <p>
    <a href="#-system-architecture">Architecture</a> •
    <a href="#-document-processing-workflow">Workflow</a> •
    <a href="#-quick-start-windows-11">Quick Start</a> •
    <a href="#-core-innovations">Innovations</a> •
    <a href="#-api-reference-summary">API Reference</a> •
    <a href="#-author--maintainer">Author</a>
  </p>

</div>

---

## 🏛️ System Architecture

```mermaid
graph TD
    subgraph Ingestion ["1. Omni-Ingestion Hub"]
        A[Web Upload] --> G[FastAPI Gateway]
        B[Email MIME] --> G
        C[Slack Events] --> G
        D[Mobile Capture] --> G
    end

    subgraph Pipeline ["2. LangGraph State Machine"]
        G --> H[Ingest Node]
        H --> I[Perception Engine<br/>PaddleOCR + LayoutParser]
        I --> J[Cognition Core<br/>Ollama 4-bit LLM]
        J --> K{Confidence >= 80%?}
        K -- No --> L[Human-in-the-Loop Review]
        L --> M[Connect Node]
        K -- Yes --> M
        M --> N[Act Node<br/>Automation Mesh]
    end

    subgraph Storage ["3. Knowledge Fabric"]
        M --> O[(PostgreSQL + pgvector)]
        M --> P[(Neo4j Graph Database)]
    end

    subgraph UI ["4. Application Layer"]
        O --> Q[Streamlit Dashboard]
        P --> Q
        Q --> R[RAG Conversation Layer]
        Q --> S[Living Document Graph]
        Q --> T[Financial Pulse Analytics]
    end
```

---

## 🔄 Document Processing Workflow

```mermaid
sequenceDiagram
    autonumber
    actor Client
    participant API as FastAPI Gateway
    participant LG as LangGraph Pipeline
    participant Perception as Perception Engine
    participant LLM as Cognition Core (Ollama)
    participant HITL as Streamlit HITL UI
    participant DB as Knowledge Fabric (PG + Neo4j)

    Client->>API: Upload Document (PDF/PNG/JPG)
    API->>LG: Async Dispatch Pipeline Job
    LG->>Perception: Extract Text, Layout Bounding Boxes & Forensics
    Perception-->>LG: Text Stream + Bounding Boxes + Forensics Flags
    LG->>LLM: Classify & Extract Structured JSON
    LLM-->>LG: Extracted JSON + Causal Check + Confidence Score
    alt Confidence < 80% or Causal Failure
        LG->>HITL: Halt at awaiting_hitl
        Client->>HITL: Review PDF & Edit Low-Confidence Fields
        HITL->>LG: Resume Pipeline with Corrections
    end
    LG->>DB: Atomic Store (Embeddings → pgvector, Entity Links → Neo4j)
    LG-->>Client: Pipeline Complete (Job Status Response)
```

---

## ⚡ Quick Start (Windows 11)

### Prerequisites
- Windows 11 Desktop
- Docker Desktop (running)
- Python 3.10+
- [Ollama](https://ollama.ai) (with `gemma2:2b-instruct-q4_K_M` and `nomic-embed-text`)

### 🚀 One-Click Launch
Double-click `start.bat` in Windows Explorer or execute in your terminal:

```cmd
start.bat
```

`start.bat` automatically:
1. Boots PostgreSQL (`pgvector`) & Neo4j containers (`docker-compose up -d`).
2. Waits 5 seconds for database readiness.
3. Launches **FastAPI Gateway** on `http://localhost:8000` in a dedicated terminal.
4. Launches **Streamlit Dashboard** on `http://localhost:8501` in a dedicated terminal.
5. Launches **Cloudflare Tunnel** for webhooks if `cloudflared` is installed.

---

## 🌐 Endpoints & Dashboards

| Service | Access URL | Function |
|---|---|---|
| 📊 Streamlit Dashboard | `http://localhost:8501` | Multi-page UI (Ingestion, HITL, Graph, RAG Chat) |
| ⚡ FastAPI Gateway | `http://localhost:8000` | Asynchronous REST API & Webhook Handlers |
| 📖 Interactive API Docs | `http://localhost:8000/docs` | OpenAPI / Swagger Documentation |
| 🗄️ Neo4j Browser | `http://localhost:7474` | Cypher query console & raw graph inspection |

---

## 💡 Core Innovations

### 1. Few-Shot Schema Synthesis
Adapt to any new document type from 2-3 examples in under 30 seconds without pre-defined templates:

```mermaid
flowchart LR
    A[New Doc Type] --> B[Provide 2-3 Examples]
    B --> C[Ollama Schema Synthesizer]
    C --> D[Generated JSON Schema]
    D --> E[Production Extraction Engine]
```

### 2. Cross-Document Causal Validation
Ensures mathematical and logical consistency across extraction fields before persistence:

```mermaid
flowchart TD
    A[Extracted Fields] --> B{Subtotal + Tax - Discount == Total?}
    B -- Yes --> C[Validation Passed]
    B -- No --> D[Causal Alert & Correction Suggestion]
    D --> E[Route to HITL Review]
```

### 3. Self-Healing Active Learning
Low-confidence extractions are gated by human verification, continuously enriching training data for local model refinement.

---

## 📁 Project Structure

```
DOCUMIND-AI/
├── state.py          # Central LangGraph TypedDict state definition
├── perception.py     # PaddleOCR + LayoutParser + visual entropy forensics
├── cognition.py      # Few-Shot Schema Synthesis, Extraction & Causal Validation
├── graph.py          # LangGraph StateGraph with conditional HITL edge
├── knowledge.py      # PostgreSQL/pgvector & Neo4j graph persistence
├── main.py           # FastAPI gateway with async background execution
├── app.py            # Streamlit multi-page dashboard
├── start.bat         # Windows 11 automated batch launcher
├── docker-compose.yml# PostgreSQL (pgvector) & Neo4j setup
└── tests/            # Pytest test suite
```

---

## 🧮 Hardware & VRAM Budget (≤ 4GB VRAM)

```mermaid
pie title VRAM Allocation Share (Total: 3.3 GB / 4.0 GB Capacity)
    "PaddleOCR PP-OCRv4 (1.2 GB)" : 12
    "LayoutParser Detection (0.6 GB)" : 6
    "Ollama LLM gemma2:2b (1.5 GB)" : 15
    "Available VRAM Headroom (0.7 GB)" : 7
```

| Component | Execution Unit | Memory Usage |
|---|---|---|
| PaddleOCR PP-OCRv4 | GPU (fp16) | 1.2 GB |
| LayoutParser PaddleDetection | GPU | 0.6 GB |
| Ollama `gemma2:2b-instruct-q4_K_M` | GPU (4-bit) | 1.5 GB |
| `nomic-embed-text` | CPU | 0.0 GB |
| **Total Allocated** | **GPU** | **3.3 GB** (0.7 GB Headroom) |

---

## 📡 API Reference Summary

```http
POST   /upload              Upload document file for processing
POST   /webhook/slack       Ingest file_shared events from Slack
POST   /webhook/email       Ingest email attachments
GET    /status/{job_id}     Poll job status and pipeline stage
POST   /hitl/{job_id}       Submit human corrections to resume pipeline
GET    /documents           Retrieve processed documents
GET    /graph               Export Neo4j graph nodes and edges
GET    /search?q={query}    Semantic vector search over document corpus
GET    /health              Health check endpoint
```

---

## 👨‍💻 Author & Maintainer

**Harshith Reddy Pujari**  
*Principal Architect & Systems Developer*  
- GitHub: [@Harshithreddy-ux](https://github.com/Harshithreddy-ux)  
- Email: pujariharshithreddy@gmail.com  

---

## 📄 License
This project is licensed under the [MIT License](LICENSE).
