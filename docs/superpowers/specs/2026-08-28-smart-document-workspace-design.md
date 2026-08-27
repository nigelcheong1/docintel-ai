# Smart Document Workspace Design

## Goal

Make DocIntel AI feel like a useful local document intelligence product instead of a basic vector-search prototype.

This phase improves the existing local-first system. It does not train a model. The app already uses AI through a pretrained local sentence-transformers embedding model plus pgvector similarity search. Training on FUNSD is better saved for a later OCR/form-understanding phase because FUNSD is strongest for layout-aware form extraction, not for improving the current text-PDF retrieval experience.

## Scope

Build three product improvements before the next manual testing session:

1. Better document management.
   - Delete stale documents from the local database and storage.
   - Reindex existing PDF documents with the newest parser/chunker/embedding pipeline.
   - Show richer document metadata such as page count and chunk count.

2. Smarter retrieval.
   - Keep vector similarity as the base ranking signal.
   - Add local reranking signals for keyword overlap and section-intent matching.
   - Prefer sections that match the user question, such as project queries matching `PROJECTS` and skill queries matching `TECHNICAL SKILLS`.

3. Cited extractive answers.
   - Return a short local answer above the evidence list.
   - Build the answer from the top cited chunks only.
   - Avoid pretending to be a generative LLM. Phrase answers as evidence-grounded extracts until Ollama or another local LLM is added.

## User Experience

The Documents page should become a practical workspace:

- Users can see documents, status, pages, chunks, and last update time.
- Users can reindex a document after chunking changes.
- Users can delete old duplicate or stale uploads.

The Search page should feel more intelligent:

- A top answer panel summarizes the best matching evidence.
- Evidence cards show section labels and ranking factors.
- Results should be better for resumes, invoices, research notes, and reports because the reranker is generic and transparent.

## Architecture

Document actions stay in the documents module. Reindexing reuses the existing `parse_pdf`, `chunk_pages`, and embedding provider flow instead of creating a parallel pipeline. Deleting a document uses SQLAlchemy cascade relationships and removes the stored file best-effort after the database row is removed.

Retrieval remains local-only. A new reranking layer converts the vector score into a blended score using section intent, keyword overlap, and source score. The API returns both the blended score and ranking explanation fields so the UI can show why a result appeared.

Answers are extractive. The answer builder selects concise sentences or snippets from the top hits and returns citations by chunk id, document filename, page number, and optional section heading.

## Non-Goals

- No OpenAI API usage.
- No paid services.
- No model training in this phase.
- No OCR implementation in this phase.
- No FUNSD training in this phase.
- No chat memory, authentication, or deployment work.

## Later Phases

1. OCR and image/scanned PDF pipeline.
2. FUNSD-based form extraction evaluation and optional fine-tuning experiment.
3. Ollama-backed local generative answer mode.
4. Visual document viewer with evidence highlights.
