# System Architecture

## Architectural Style
The system follows a layered, service-oriented architecture that ensures separation of concerns, scalability, and maintainability.

---

## High-Level Architecture

User → API Layer → Service Layer → NLP/AI Components → Visualization → Response

---

## Component Breakdown

### API Layer
- Handles HTTP requests
- Validates inputs using Pydantic
- Returns structured responses
- Enforces token-based authentication (signup/login local DB)

### Service Layer
- ResumeParser
- SkillExtractor
- SkillGapAnalyzer
- CoverLetterGenerator
- ResumeUpdater
- JobRecommender (internet job listing aggregation + compatibility scoring)

### NLP / AI Layer
- Local Ollama (`llama3:8b`) for semantic gap analysis
- Rule-based extraction fallback when LLM output is invalid

### Visualization Layer
- Skill gap scorecards and advanced infographic panels
- Structured skill category output
- Priority gap tables and action-plan output

---

## Data Flow
1. Resume uploaded
2. Text extracted
3. Skills extracted
4. Skill gap analyzed
5. Results visualized
6. Optional AI text generation
7. Optional web job matching from resume profile (role + location aware)
