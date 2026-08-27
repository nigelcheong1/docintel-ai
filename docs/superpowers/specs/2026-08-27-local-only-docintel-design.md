# DocIntel AI Local-Only Project Design

Date: 2026-08-27
Repository: `nigelcheong1/docintel-ai`
Status: Draft for review

## 1. Purpose

DocIntel AI is a full-stack multimodal document intelligence platform. In week one, a user uploads PDFs for indexing and may upload document images for tracked storage with a clear deferred-OCR status. The system extracts text and layout metadata from PDFs, indexes document chunks with local embeddings, and returns cited evidence for search and question answering.

The project is designed for a portfolio and resume. It should show practical AI engineering instead of only a demo chatbot: document processing, retrieval, vector search, evaluation, Docker infrastructure, backend APIs, and a polished frontend.

## 2. Product Goal

Build a local-first platform that can:

1. Accept PDF uploads for indexing and image uploads for deferred OCR handling.
2. Extract text, page numbers, and useful layout metadata from PDFs.
3. Split extracted content into searchable chunks.
4. Generate embeddings locally with an open-source embedding model.
5. Store chunks and vectors in PostgreSQL with pgvector.
6. Retrieve relevant chunks for a user question.
7. Show citations and supporting evidence in the frontend.
8. Evaluate retrieval quality with a small repeatable benchmark.

The first release will not use OpenAI, Anthropic, hosted vector databases, or paid APIs.

## 3. Recommended Scope

### In Scope for Week One

- Monorepo structure with separate frontend and backend apps.
- Docker Compose for PostgreSQL with pgvector.
- FastAPI backend with health, upload, document, search, and evaluation endpoints.
- Next.js frontend with upload, document list, document detail, search, and evaluation views.
- Local parsing for PDFs using PyMuPDF.
- Local text chunking and metadata persistence.
- Local embeddings using `sentence-transformers` and `BAAI/bge-small-en-v1.5`.
- Vector similarity search using pgvector.
- FUNSD dataset download or ingestion script for local experiments.
- Basic tests and README documentation.

### Deferred Until After Week One

- Ollama local LLM answer generation.
- OCR for low-quality scanned documents.
- Bounding-box citation overlays in a PDF/image viewer.
- User accounts and authentication.
- Cloud deployment.
- Large-scale dataset training.
- Fine-tuning.

## 4. Why Retrieval First

The recommended build order is retrieval plus citations before local LLM answers.

This gives a reliable AI foundation:

- Retrieval can be evaluated without paid LLM calls.
- Citations make the app trustworthy.
- The product remains useful even before generative answers.
- Local LLM integration can be added later as a thin layer over the retrieval pipeline.

The frontend will describe results as evidence-backed search and document Q&A. When Ollama is added later, generated answers will cite the same retrieved chunks.

## 5. Users and Portfolio Story

Primary user: a recruiter, interviewer, or technical reviewer exploring the project locally.

Secondary user: a student or analyst who wants to search a set of forms, reports, or scanned documents.

Portfolio story:

> Built a local-first multimodal document intelligence system using FastAPI, Next.js, PostgreSQL/pgvector, PyMuPDF, and open-source embeddings. The system indexes PDFs, performs vector retrieval, returns citations, and evaluates retrieval quality without paid AI APIs.

## 6. System Architecture

The app will use a monorepo:

```text
docintel-ai/
  apps/
    web/              # Next.js frontend
    api/              # FastAPI backend
  packages/
    shared/           # Optional shared contracts later
  infra/
    docker/           # Database init scripts
  docs/
    architecture/     # Diagrams and explanatory docs
    superpowers/specs/
  data/               # Ignored local datasets
  storage/            # Ignored uploaded documents
  docker-compose.yml
  README.md
  .env.example
```

Core runtime:

```text
Browser
  -> Next.js web app
  -> FastAPI API
  -> PostgreSQL + pgvector
  -> Local filesystem storage
  -> Local embedding model
```

Docker will run infrastructure services first. The backend and frontend can run directly on the host during development for faster iteration. Later, backend and frontend Dockerfiles can be added for one-command startup.

## 7. Component Design

### Frontend: `apps/web`

Responsibilities:

- Upload documents.
- Show processing status and indexed document metadata.
- Provide document search and question input.
- Display retrieved evidence with page number, score, and source snippet.
- Show evaluation run summaries.

Expected screens:

- Dashboard: recent documents, indexing status, quick search.
- Upload: drag-and-drop file upload.
- Documents: table/list of uploaded documents.
- Document detail: extracted pages/chunks and search within a document.
- Ask/Search: global question input and cited evidence results.
- Evaluation: benchmark queries and retrieval metrics.

### Backend: `apps/api`

Responsibilities:

- Validate uploaded files.
- Store files under ignored local storage.
- Parse PDFs and validate image uploads for later OCR support.
- Chunk extracted text.
- Generate local embeddings.
- Persist metadata and vectors.
- Run vector search.
- Expose evaluation endpoints.

Backend modules:

- `api`: FastAPI routers and request/response schemas.
- `core`: settings, logging, and shared configuration.
- `db`: SQLAlchemy models, database session, migrations.
- `documents`: upload, storage, parsing, and processing orchestration.
- `retrieval`: chunking, embedding, vector search, citation formatting.
- `evaluation`: sample query sets, scoring, and reports.

### Database

PostgreSQL with pgvector will store metadata and vectors.

Planned tables:

- `documents`: id, filename, content type, status, created time, file path.
- `pages`: id, document id, page number, text, width, height.
- `chunks`: id, document id, page id, chunk index, text, metadata.
- `chunk_embeddings`: id, chunk id, embedding vector, model name.
- `questions`: id, text, created time.
- `retrieval_results`: id, question id, chunk id, score, rank.
- `eval_runs`: id, name, model name, metrics JSON, created time.

The embedding dimension must match the selected model. `BAAI/bge-small-en-v1.5` uses 384-dimensional embeddings, so pgvector should be configured for `vector(384)`.

## 8. AI Pipeline

### Document Processing

1. Validate file type and size.
2. Save file to local ignored storage.
3. Extract text with PyMuPDF for PDFs.
4. For image files, store the upload and return a clear "OCR not yet enabled" indexing status in week one unless basic OCR is added within the planned scope.
5. Store page text and metadata.
6. Split text into overlapping chunks.
7. Embed chunks using local `sentence-transformers`.
8. Insert vectors into pgvector.
9. Mark document status as indexed or failed.

### Retrieval

1. User submits a question or search phrase.
2. Backend embeds the query locally.
3. pgvector returns nearest chunks.
4. Backend normalizes citations: document name, page number, chunk id, score, snippet.
5. Frontend shows evidence-ranked results.

### Local Embedding Choice

Default model: `BAAI/bge-small-en-v1.5`

Reasoning:

- Good quality for retrieval.
- Small enough for local development.
- 384-dimensional vectors keep pgvector storage manageable.
- Works through `sentence-transformers`.
- No paid API key required.

Future model options:

- `BAAI/bge-m3` for stronger multilingual retrieval.
- `nomic-embed-text` through Ollama.
- `Qwen3-Embedding` if local hardware can handle it.

## 9. Dataset Plan

FUNSD will be used as the starter dataset because it is small and focused on form understanding.

Source: `https://github.com/crcresearch/FUNSD`

Local location:

```text
data/raw/funsd/
```

The dataset will not be committed. The repo will include a script or documented command to download it locally.

Dataset use in week one:

- Ingest selected FUNSD documents as sample documents.
- Create a small search benchmark from form questions and labels.
- Produce retrieval evaluation metrics for README screenshots.

## 10. API Surface

Initial REST endpoints:

- `GET /health`: backend health check.
- `POST /documents`: upload and index a document.
- `GET /documents`: list documents.
- `GET /documents/{document_id}`: document details.
- `GET /documents/{document_id}/chunks`: chunks for a document.
- `POST /search`: semantic search across indexed chunks.
- `POST /eval/runs`: run a small retrieval evaluation.
- `GET /eval/runs`: list evaluation runs.

The backend will return typed JSON responses through Pydantic schemas.

## 11. Frontend Experience

The first screen should be the usable app, not a marketing landing page.

Visual direction:

- Quiet, practical, work-focused interface.
- Dense but readable dashboard.
- Clear document states: uploaded, processing, indexed, failed.
- Evidence-first results with page numbers and confidence scores.
- No oversized hero section.

Important UI states:

- Empty document library.
- Upload in progress.
- Indexing in progress.
- Indexed document with chunks.
- Search with no results.
- Search with cited evidence.
- Processing failure with a readable error.

## 12. Docker and Local Development

Docker will run the database infrastructure:

- PostgreSQL
- pgvector extension
- Persistent database volume

Expected developer commands after implementation:

```powershell
docker compose up -d
```

Backend and frontend will initially run outside Docker:

```powershell
cd apps/api
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload
```

```powershell
cd apps/web
npm install
npm run dev
```

This split keeps the first week easier to debug on Windows. Full containerization can come later.

## 13. Error Handling

The app should handle:

- Unsupported file type.
- Empty PDF or failed text extraction.
- Database unavailable.
- Embedding model not downloaded yet.
- Vector dimension mismatch.
- Duplicate uploads.
- Search before any document is indexed.
- Large file rejected by configured size limit.

Backend errors should use clear JSON messages. Frontend errors should be visible in the relevant workflow, not hidden in console output.

## 14. Testing Strategy

Backend tests:

- Health endpoint.
- File validation.
- Text chunking.
- Embedding service interface with a lightweight fake.
- Search result formatting.
- Database model smoke tests.

Frontend tests:

- Basic render smoke tests.
- Upload form state.
- Search result rendering.

Manual verification:

- Docker database starts.
- Backend connects to database.
- A sample PDF indexes successfully.
- Search returns relevant chunks.
- FUNSD ingestion works locally.

Evaluation:

- A small benchmark query file will map questions to expected documents or chunks.
- Metrics will include hit rate at k and mean reciprocal rank.
- Ragas can be explored later, but the first evaluation must not require paid LLM calls.

## 15. Security and Privacy

No external AI API calls are required.

The project must not commit:

- `.env` files.
- Uploaded documents.
- FUNSD dataset files.
- Downloaded local models.
- Database files.

The app is intended for local development and portfolio demonstration. Production user authentication is deferred.

## 16. Week One Timeline

### Day 1: Foundation

- Clone repo and establish `main`.
- Add project spec.
- Create implementation plan after spec approval.
- Scaffold monorepo.
- Add Docker Compose for PostgreSQL and pgvector.
- Add backend and frontend skeletons.

Deliverable: repo boots with database, API health endpoint, and frontend shell.

### Day 2: Upload and Storage

- Implement file upload endpoint.
- Save uploaded files under ignored local storage.
- Add document metadata table.
- Build upload UI and document list.

Deliverable: user can upload a file and see it listed.

### Day 3: Parsing and Chunking

- Add PDF text extraction with PyMuPDF.
- Store page text.
- Implement chunking.
- Show extracted chunks in document detail.

Deliverable: uploaded PDF becomes searchable text chunks.

### Day 4: Local Embeddings and Vector Search

- Add `sentence-transformers`.
- Generate embeddings locally.
- Store vectors in pgvector.
- Implement semantic search endpoint.

Deliverable: user can search indexed documents semantically.

### Day 5: Evidence UI

- Build search page.
- Display ranked snippets, page numbers, scores, and document links.
- Add search empty/error/loading states.

Deliverable: polished retrieval UI with citations.

### Day 6: FUNSD and Evaluation

- Download or document FUNSD setup.
- Add ingestion script for sample FUNSD documents.
- Add small benchmark query set.
- Implement retrieval metrics.

Deliverable: evaluation dashboard or report with hit rate and MRR.

### Day 7: Portfolio Polish

- Add screenshots or demo instructions.
- Improve README.
- Add architecture diagram.
- Run tests and manual verification.
- Push feature branch and open PR for implementation work.

Deliverable: portfolio-ready MVP.

## 17. What Nigel Needs To Do

Before coding:

1. Keep Docker Desktop running.
2. Confirm this spec looks right.
3. Install Node.js LTS if it is not installed.
4. Confirm Python 3.11 or 3.12 is installed.

During coding:

1. Run commands I ask for if Windows, Docker, or GitHub prompts need local confirmation.
2. Avoid manually adding files under `data/`, `storage/`, or `.env` to Git.
3. Tell me if the app feels too slow on your laptop so we can choose a smaller model or batch size.

Optional later:

1. Install Ollama for local generated answers.
2. Download larger document datasets.
3. Add project screenshots to your portfolio site or resume.

## 18. Git Workflow

Because the repository starts empty, the first docs commit will establish `main`.

After this spec is approved:

1. Create branch `feature/local-first-docintel`.
2. Build the MVP in small commits.
3. Push the branch to GitHub.
4. Open a pull request.
5. Review test results and screenshots.
6. Merge after approval.

## 19. Definition of Done

The week-one MVP is complete when:

- Docker starts PostgreSQL with pgvector.
- Backend starts locally and reports healthy status.
- Frontend starts locally and can call the backend.
- User can upload a PDF.
- The system extracts and chunks text.
- Local embeddings are generated without paid APIs.
- Semantic search returns cited evidence.
- A small evaluation run reports retrieval metrics.
- README explains setup, usage, architecture, and limitations.
- Dataset and secret files are ignored by Git.
- Tests and manual verification pass.

## 20. Future Extensions

After the MVP:

- Add Ollama for local answer generation.
- Add OCR for scanned images and image-only PDFs.
- Add page preview with citation highlights.
- Add document comparison.
- Add table extraction.
- Add authentication.
- Add full Docker containerization for frontend and backend.
- Add deployable demo mode with sample data.
