# DocIntel AI

DocIntel AI is a local-first document intelligence MVP. It uploads PDFs, extracts text, chunks document content, creates local embeddings, stores vectors in PostgreSQL with pgvector, and returns cited evidence for semantic search.

The MVP does not require OpenAI, Anthropic, hosted vector databases, or paid APIs.

## Why This Project Matters

This project demonstrates full-stack AI engineering:

- FastAPI backend design
- Next.js and TypeScript frontend
- Local `BAAI/bge-small-en-v1.5` embedding model
- PostgreSQL vector search with pgvector
- PDF parsing with PyMuPDF
- Docker-based infrastructure
- Retrieval evaluation metrics
- Portfolio-ready documentation

## Architecture

See [the system overview](docs/architecture/system-overview.md).

## Local Development

See [the local development guide](docs/architecture/local-development.md).

## Dataset

FUNSD is used for local document-understanding experiments:

```powershell
python apps/api/scripts/download_funsd.py
```

The command clones the FUNSD repository into `data/raw/funsd`, which is ignored by Git. In the cloned repository, the included DVC pointer files and QA JSON files do not include the original raw images; obtain those through the original dataset download or DVC retrieval before image-based experiments.

## Current Scope

Week-one MVP:

- PDF upload and indexing
- Image upload with a deferred-OCR status
- Local BGE embeddings with 384-dimensional vectors
- pgvector semantic search
- Cited evidence UI
- Deterministic retrieval metrics

Out of scope for this MVP:

- Ollama answer generation
- OCR for scanned images
- Authentication
- Cloud deployment
- Fine-tuning
- Bounding-box overlays

