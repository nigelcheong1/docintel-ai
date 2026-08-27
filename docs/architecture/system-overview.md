# System Overview

DocIntel AI is local-first. The frontend calls FastAPI, FastAPI stores uploaded files locally, PyMuPDF extracts PDF text, sentence-transformers creates BGE embeddings, and PostgreSQL with pgvector stores searchable 384-dimensional vectors.

No paid AI APIs are required for the MVP.

```mermaid
flowchart LR
  Browser[Browser] --> Web[Next.js web app]
  Web --> API[FastAPI backend]
  API --> Storage[Local file storage]
  API --> Parser[PyMuPDF PDF parser]
  Parser --> Chunks[Text chunks]
  Chunks --> Embedder[Local BGE embeddings]
  Embedder --> DB[(PostgreSQL + pgvector)]
  API --> DB
  DB --> Search[Cited retrieval results]
  Search --> Web
```
