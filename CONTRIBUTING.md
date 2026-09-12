# Contributing to DocuMind AI

Thank you for your interest in contributing to DocuMind AI! 🎉

---

## 🏁 Getting Started

1. **Fork** the repository on GitHub
2. **Clone** your fork locally
3. **Create** a feature branch: `git checkout -b feature/your-feature`
4. **Make** your changes
5. **Test** thoroughly
6. **Push** and open a **Pull Request**

---

## 🔧 Development Setup

```bash
# Clone & enter
git clone https://github.com/Harshithreddy-ux/DOCUMIND-AI_LUMINIX.git
cd DOCUMIND-AI_LUMINIX

# Create virtual environment
python3 -m venv venv && source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
pip install ruff pytest pytest-asyncio

# Start databases
docker compose up -d

# Pull Ollama models
ollama pull gemma2:2b-instruct-q4_K_M
ollama pull nomic-embed-text

# Run tests
pytest tests/ -v
```

---

## 🏛️ Understanding the 8 Pillar Architecture

Before contributing, understand which pillar your change affects:

| File | Pillar |
|------|--------|
| `perception.py` | Perception Engine (OCR, forensics) |
| `cognition.py` | Cognition Core (LLM, schema, validation) |
| `graph.py` | Automation Mesh (LangGraph routing) |
| `knowledge.py` | Knowledge Fabric (pgvector, Neo4j) |
| `main.py` | Omni-Ingestion Hub (FastAPI) |
| `app.py` | Conversation Layer + Dashboard |
| `state.py` | Trust & Governance (shared state) |

---

## 📝 Commit Message Convention

We use [Conventional Commits](https://www.conventionalcommits.org/):

```
feat: add cross-lingual document support
fix: resolve causal validator float precision issue
docs: update HITL interface screenshots
refactor: simplify embedding generation retry logic
test: add unit tests for few-shot schema synthesis
chore: bump paddleocr to 2.7.1
```

---

## 🧪 Testing

- Add unit tests for any new functions in `tests/`
- All tests must pass: `pytest tests/ -v`
- New pipeline nodes must include a docstring explaining routing logic

---

## 🔒 Code of Conduct

Be kind, inclusive, and constructive. We're all here to build something great for SMEs.

---

*Questions? Email: pujariharshithreddy@gmail.com*
