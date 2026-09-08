# Production RAG Pipeline Design

## Goal

Make DocIntel AI behave like a finished document RAG workspace: uploads should become searchable in the background, retrieval should combine semantic and lexical evidence, summaries and study questions should use the strongest available generation path, and users should be able to inspect citations directly from the UI.

## Product Scope

This phase keeps DocIntel local-first. The app must run without paid API keys by using deterministic local extractive generation, while allowing an optional configured LLM provider to improve summaries, study questions, and answer feedback.

The target user flow is:

1. Upload a PDF or image.
2. See processing begin immediately.
3. Watch document readiness by stage and page health.
4. Search across one or all documents.
5. Generate cited summaries and study questions.
6. Submit study answers and receive scored feedback.
7. Open citations in a source viewer with page preview and evidence context.

## Backend Architecture

### Processing Jobs

Add a small processing status layer instead of introducing a separate queue service. FastAPI `BackgroundTasks` will run indexing after upload and reindex requests return quickly. The database remains the durable source of truth through document status, timing fields, page/chunk counts, and new status read models.

Document status values should be expanded only where needed:

- `uploaded`
- `processing`
- `ocr_processing`
- `embedding`
- `indexed`
- `deferred_ocr`
- `failed`

The status endpoint will derive stage progress from existing persisted data:

- upload saved
- text/OCR extraction
- chunking
- embeddings
- ready or failed

### Retrieval

Keep pgvector similarity search as the primary retrieval path. Add hybrid retrieval that merges:

- vector candidates from `chunk_embeddings`
- lexical candidates from query term overlap
- document-aware answer evidence when a selected document has a known type

The reranker should expose ranking signals for vector score, keyword overlap, section intent, and lexical score. If vector search fails because pgvector, embeddings, or the model are unavailable, the search endpoint should degrade to lexical retrieval and return diagnostics explaining the fallback.

### Generation

Add an optional LLM provider interface with these operations:

- summarize context
- generate study questions from context
- evaluate a user answer

The default provider is local/extractive and deterministic. A Groq-compatible HTTP provider can be enabled with `DOCINTEL_LLM_PROVIDER=groq` and `DOCINTEL_GROQ_API_KEY`. The API must not fail startup if no key is configured.

Study and summary generation should build compact cited context from hybrid retrieval and then call the configured provider. Provider output is sanitized and tied back to citations already chosen by retrieval.

## Frontend Architecture

### Documents

Document rows should show richer processing state:

- status badge
- stage label
- progress percent
- page/chunk counts
- text/OCR quality
- retry action for failed/deferred OCR

The documents page should poll while any document is still processing.

### Search And Workbench

Search results and workbench citations should open a source viewer panel. The source viewer shows:

- document filename
- page number
- section heading if available
- page image preview
- evidence snippet
- score/ranking signals
- link to full document workbench

The source viewer should be reusable from search, summary, and study tabs.

### Study Mode

Study questions should support multiple attempts. The UI shows the latest score plus attempt history summary. The answer feedback should name missing high-value terms when local evaluation is used.

## Testing Requirements

- Model tests for any status enum/model/schema changes.
- Service tests for derived processing status.
- Retrieval tests for hybrid merge, lexical fallback, and ranking signals.
- LLM provider tests for local fallback and disabled external provider behavior.
- Study service tests showing summary/questions use retrieved cited context.
- Router tests for async upload/reindex status semantics.
- Frontend API client tests for status/source viewer payloads.
- React tests for progress display, polling decision, source viewer interactions, and study feedback.

## Non-Goals

- No real distributed worker service in this phase.
- No user accounts or authentication.
- No paid API key requirement.
- No migration framework replacement.
