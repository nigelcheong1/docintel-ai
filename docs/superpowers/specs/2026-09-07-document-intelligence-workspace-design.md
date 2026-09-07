# Document Intelligence Workspace Design

## Goal

Add a finished document intelligence layer to DocIntel AI: users can generate cited summaries, create study questions, answer them, and receive grounded feedback without leaving the document workspace.

## Scope

This phase adapts the useful DocRAG workflow patterns while keeping DocIntel AI local-first and evidence-centered.

1. Persist generated document summaries with citations.
2. Persist generated study questions with expected answers and citations.
3. Persist user answers with score and feedback.
4. Add deterministic local generation so the feature works without a paid LLM key.
5. Add API routes for summary generation, study question generation, and answer grading.
6. Add a `Study` tab to the document workbench.
7. Add a `Summary` tab to the document workbench.

## Out Of Scope

- No paid cloud LLM integration in this phase.
- No async worker queue yet; generation runs synchronously behind explicit button actions.
- No user accounts or cross-user study progress.
- No large-scale spaced repetition algorithm.

## Backend Design

Add `DocumentSummary`, `StudyQuestion`, and `StudyAnswer` tables. Summaries and questions store citation metadata as JSON so the frontend can link users back to source pages and chunks.

Create `app.study.service` as the first generation service. It uses indexed chunks and the existing document profile to build:

- An extractive cited summary from overview/high-signal chunks.
- A deduplicated question set from important sections.
- A scored answer review based on token overlap with the expected answer and cited evidence.

This deterministic provider is deliberately simple, testable, and offline. A future phase can add an optional `LLMProvider` interface on top of the same persisted tables.

Add `app.study.router` under `/documents/{document_id}/study`:

- `GET /summary`
- `POST /summary`
- `GET /questions`
- `POST /questions`
- `POST /questions/{question_id}/answers`

Routes return 404 for missing documents, 400 for unindexed documents, and 400 when a question does not belong to the selected document.

## Frontend Design

Extend the document workbench tabs from `Overview`, `Evidence`, and `Quality` to include `Summary` and `Study`.

The `Summary` tab shows an existing summary when available and provides a generate/regenerate action. Citations appear as links into the evidence view.

The `Study` tab shows generated questions, expected answer hints, answer input, score, feedback, and citation links. Buttons use the existing teal/ink/amber palette and remain keyboard accessible.

## Testing

Backend tests cover:

- Model relationships and columns.
- Summary generation from cited chunks.
- Question generation with citation metadata and deduplication.
- Answer grading for strong and weak answers.
- API route happy paths and validation errors.

Frontend tests cover:

- API client methods for study routes.
- Workbench summary tab rendering and generation action.
- Workbench study tab rendering, question generation, answer submission, and feedback display.
