# Skillentia

## Overview
Skillentia provides authenticated career tooling for:
- Semantic gap analysis
- Cover letter generation
- Resume updates
- Compatible job listings with direct links

The platform uses local authentication (SQLite) and local LLM inference (Ollama `llama3:8b`) for skill-gap semantics.

## Key Features
- Resume parsing (`.pdf`, `.docx`, `.doc/.docs`, `.txt`)
- Local signup/login authentication
- One-time resume + JD capture on landing page and reuse across feature pages
- Dedicated pages for:
  - Gap Analysis
  - Cover Letter Generator
  - Resume Enhancer
  - Compatible Job Listings
- Semantic gap analysis via local LLM with deterministic fallback
- Job listing retrieval from Tavily web search (no board-link fallback mode)

## Architecture
- FastAPI backend (`/app`)
- Static frontend (`/frontend`)
- Local auth/session DB at `data/auth.db`
- Ollama integration through `app/llm/client.py`

See:
- `docs/system_architecture.md`
- `docs/api_documentation.md`

## Setup
1. Install dependencies:

```bash
pip install -r requirements.txt
```

2. Start backend:

```bash
uvicorn app.main:app --reload
```

3. Serve frontend:

```bash
cd frontend
python3 -m http.server 5500
```

4. Open:
- `http://127.0.0.1:5500/auth.html`

## Ollama Setup (Semantic Gap Analysis)
1. Install Ollama.
2. Pull model:

```bash
ollama pull llama3:8b
```

3. Ensure values in `.env` (optional if defaults are fine):
- `OLLAMA_URL=http://localhost:11434`
- `OLLAMA_MODEL=llama3:8b`

If Ollama is unavailable or returns invalid JSON, gap analysis falls back to deterministic extraction.

## Job Listing Function Reliability
- Mode: live Tavily result extraction with role/location-aware queries only.
- Response field `source_mode` is always `tavily`.

If job listings do not show:
1. Set `TAVILY_API_KEY` in `.env`.
2. Verify backend has outbound internet access.
3. Ensure JD includes role and location context.
4. Check backend logs for `/api/job-recommendations` warnings/errors.
