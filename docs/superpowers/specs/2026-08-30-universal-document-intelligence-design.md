# Universal Document Intelligence Design

## Goal

Turn DocIntel AI from a reliable resume/document search prototype into a universal local document intelligence engine. The app should detect the type of uploaded text-based PDF, build a lightweight document profile, route questions by intent, answer broad document-aware questions, and abstain with type-aware guidance when a question does not fit the selected document.

## Scope

This phase keeps the system local-only and improves documents that already extract text through PyMuPDF:

1. Add document profiling.
   - Classify indexed PDFs as `research_paper`, `resume`, `invoice`, `contract`, `report`, or `generic`.
   - Extract section headings, title-like text, overview text, key dates, key numbers, and named entities.
   - Generate useful suggested questions for the detected document type.

2. Add typed query routing.
   - Detect broad overview questions such as "What is this document about?"
   - Detect fact-oriented questions for dates, amounts, parties, risks, obligations, datasets, methods, results, limitations, education, skills, projects, and experience.
   - Route questions to document-aware answer strategies before falling back to vector-hit answer gating.

3. Add document-aware extractive answers.
   - Use profile sections and document chunks, not only nearest vector hits, when the question is broad or type-specific.
   - Keep every answer citation-grounded.
   - Return type-aware no-answer reasons for mismatch cases, such as asking contract-party questions against a research paper.

4. Improve hybrid retrieval.
   - Expand query and section intent detection beyond resumes.
   - Support research-paper, invoice, contract, report, and generic-document headings.
   - Preserve source score, keyword overlap, and section-intent signals.

5. Improve the Search UI.
   - Show the selected document profile.
   - Surface document type, query intent, suggested questions, key facts, and sections.
   - Let users run suggested questions directly.

## Evaluation Data

No user-provided dataset is required for this phase. Tests will generate synthetic fixture documents for research papers, invoices, contracts, reports, and resumes. This gives repeatable evaluation coverage without licensing friction or download setup.

Public datasets such as FUNSD are better saved for a later OCR/layout-model phase. This phase does not train a model.

## User Experience

For a research paper, the app should answer:

- "What is this document about?"
- "What datasets are mentioned?"
- "What methods are used?"
- "What results are reported?"
- "What limitations or future work are discussed?"

For an invoice, the app should answer:

- "What total amount is due?"
- "When is payment due?"
- "Who is the invoice billed to?"

For a contract, the app should answer:

- "Who are the parties involved?"
- "What obligations are mentioned?"
- "What risks or termination terms are mentioned?"

For a resume, the existing resume questions should continue to work.

When a query is not appropriate for the document type, the app should say why and suggest better questions rather than producing weak text.

## Architecture

The backend keeps the existing local retrieval flow:

1. Embed query locally.
2. Search pgvector.
3. Rerank hits.
4. Build a document profile when a document is selected.
5. Route the query by intent.
6. Try document-aware extractive answer strategies.
7. Fall back to grounded hit-level answer gating.

The document profile is computed from stored pages and chunks for now. No database migration is required in this phase.

## Non-Goals

- No paid APIs.
- No OpenAI API usage.
- No Ollama generation yet.
- No OCR or scanned-PDF processing yet.
- No FUNSD fine-tuning or model training yet.
- No claim that every possible file format is fully supported. The target is robust text-based PDF intelligence across common document types.

## Success Criteria

- Selected research-paper overview questions return cited answers instead of generic no-evidence responses.
- Type-specific facts work for synthetic research paper, invoice, contract, report, and resume fixtures.
- Mismatch questions return type-aware abstentions and useful suggestions.
- `/documents/{id}/profile` returns stable document profile data.
- `/search` returns `document_type` and `query_intent`.
- Search UI shows selected-document profile and suggested questions.
- Backend and frontend tests pass.
