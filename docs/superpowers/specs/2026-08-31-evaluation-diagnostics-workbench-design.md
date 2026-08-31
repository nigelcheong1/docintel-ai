# Evaluation Diagnostics Workbench Design

**Goal:** Make DocIntel AI testable and more trustworthy across common document types by adding golden QA evaluation, answer diagnostics, and cleaner evidence presentation.

## Scope

This phase upgrades the existing local-first RAG app without training a model. The work targets the current FastAPI, PostgreSQL, and Next.js app.

In scope:
- Golden QA cases for research papers, resumes, invoices, contracts, and reports.
- A deterministic evaluator that grades answerability, confidence, citations, intent routing, document type routing, and answer keywords.
- Search diagnostics that explain document type, query intent, quality reason, answer evidence, related evidence, and result noise.
- Search result grouping that separates cited answer evidence from related chunks.
- A richer Evaluation page that shows benchmark coverage, pass rates, failure reasons, and per-case details.

Out of scope:
- Training FUNSD or another layout model.
- External LLM generation.
- OCR quality upgrades.
- Production authentication or multi-user projects.

## Architecture

The backend keeps the current extractive, cited-answer pipeline. `/search` gains diagnostics fields derived from the existing `SearchResponse`, `AnswerQuality`, reranker signals, and answer citations. `/eval/golden` runs in-memory golden fixtures through the same document profile and document-aware answer code, so it is fast and repeatable without needing uploads or embeddings.

The frontend keeps the Search and Evaluation pages. Search renders answer evidence separately from related chunks and exposes a compact diagnostics panel. Evaluation renders the golden benchmark summary and case grid alongside the existing stored retrieval run history.

## Success Criteria

- Research-paper hard negatives continue to abstain.
- Invoice, contract, resume, report, and research-paper golden cases are evaluated in one run.
- Each golden case reports pass/fail and failure reasons.
- Search UI clearly distinguishes cited answer evidence from merely related chunks.
- Full backend and frontend tests pass.

