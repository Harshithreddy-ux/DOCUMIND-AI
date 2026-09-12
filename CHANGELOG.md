# Changelog

All notable changes to DocuMind AI will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [1.0.0] — 2026-09-12 · Initial Release

### Added
- **Infrastructure & Environment**
  - `antigravity.yaml` — AGY declarative project profile
  - `docker-compose.yml` — PostgreSQL (pgvector) + Neo4j containerisation
  - `requirements.txt` — pinned Python dependencies
  - `start.bat` — Windows 11 automated batch launcher

- **Core LangGraph Pipeline**
  - `state.py` — canonical `DocuMindState` TypedDict
  - `perception.py` — PaddleOCR + LayoutParser + visual entropy forensics
  - `cognition.py` — Few-Shot Schema Synthesis, Causal Validator, hierarchical confidence scoring via local Ollama
  - `graph.py` — LangGraph StateGraph: ingest → perceive → understand → [HITL gate] → connect → act

- **Ingestion Gateway & Knowledge Fabric**
  - `main.py` — FastAPI: async endpoints (upload, Slack/email webhooks, HITL, RAG search, graph data)
  - `knowledge.py` — pgvector storage, Neo4j graph linking, anomaly detection, duplicate detection, semantic search

- **Streamlit Dashboard**
  - `app.py` — 6-page dashboard: Home KPIs, Omni-Ingestion queue, HITL review, Living Document Graph, RAG Chat, Financial Pulse

- **Repository Infrastructure**
  - Professional `README.md` with Mermaid diagrams, architecture flow, API reference
  - GitHub Actions CI workflow (lint + test + docker-build)
  - Issue templates & Pull Request template
  - Pytest unit test suite (`tests/test_cognition.py`)
  - `CONTRIBUTING.md`, `LICENSE` (MIT), `.env.example`, `.gitignore`

### Innovations
- 🔬 **Few-Shot Schema Synthesis** — 2-3 examples → full schema in 30 seconds
- 🕸️ **Cross-Document Causal Reasoning** — temporal knowledge graph + math consistency checks
- 🔄 **Self-Healing HITL Active Learning** — auto-retry + smart human review + local fine-tuning loop
