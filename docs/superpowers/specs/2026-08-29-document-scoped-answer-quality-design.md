# Document-Scoped Search And Answer Quality Design

## Goal

Make DocIntel AI searches easier to trust by letting users search one selected document and by making extractive answers cite only the document sections that actually fit the question.

## Scope

This phase improves the existing local-only search experience:

1. Add a document scope control to the Search page.
   - Default searches across all indexed documents.
   - Users can select one indexed document from a dropdown.
   - The frontend sends the selected `document_id` to the existing `/search` endpoint.

2. Harden local answer quality.
   - Keep answers extractive and citation-grounded.
   - Infer query focus for projects, education, skills, programming languages, tools, frameworks, and experience.
   - Prefer citations from matching section families when a matching section is present.
   - Stop forcing three citations when only one or two are relevant.
   - Fall back to normal top-hit evidence when the query has no clear section focus.

## User Experience

The Search page should support two common workflows:

- Search all uploaded documents when comparing a collection.
- Search one selected document when the user wants answers from a specific file.

Answers should read less like pasted mixed chunks. For example, a technical-skills query should primarily answer from skills, programming-language, framework, and tool sections, not education or experience sections. A projects query should answer from project sections when they exist.

## Architecture

The backend already accepts `SearchRequest.document_id`, so document scoping mainly needs frontend exposure and regression tests. The search service keeps the current SQL filter and pgvector flow.

Answer hardening belongs in retrieval. The reranker will expose reusable section-focus helpers, and the answer builder will use those helpers to select relevant evidence before building snippets. This keeps the behavior deterministic, local-only, and transparent.

## Non-Goals

- No OpenAI API usage.
- No paid hosted AI services.
- No model training in this phase.
- No Ollama chat generation in this phase.
- No scanned-PDF OCR or FUNSD fine-tuning in this phase.

## Success Criteria

- Frontend users can choose `All documents` or one indexed document before searching.
- Selecting a document sends `document_id` in the search request.
- Skill queries do not include unrelated education, experience, or project citations when skill-family sections are available.
- Project queries do not include unrelated skill or education citations when project sections are available.
- Programming-language queries recognize `PROGRAMMING LANGUAGES` and related skill-family sections.
- Backend and frontend tests pass.
