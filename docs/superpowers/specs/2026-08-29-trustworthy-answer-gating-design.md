# Trustworthy Answer Gating Design

## Goal

Make DocIntel AI behave like a reliable local RAG assistant instead of a raw nearest-neighbor demo. When evidence is strong, the app should answer with citations. When evidence is weak or the query is outside the selected document, the app should abstain clearly and suggest better questions.

## Scope

This phase improves the existing local-only search workflow:

1. Add an answer quality contract to `/search`.
   - Return whether the query is answerable from retrieved evidence.
   - Return a confidence label: `strong`, `moderate`, or `weak`.
   - Return a short reason for the decision.
   - Return suggested follow-up questions based on detected document sections.

2. Gate extractive answers before returning them.
   - Keep answers deterministic and citation-grounded.
   - Use source score, keyword overlap, and section intent as evidence signals.
   - Prefer section-matching evidence when the user asks about skills, projects, education, tools, frameworks, languages, or experience.
   - Abstain for unrelated queries even if pgvector returns nearby chunks.
   - Abstain for document-language detection queries until explicit language detection is implemented.

3. Improve the Search UI.
   - Show a confidence badge beside accepted answers.
   - Show a clear "Not enough evidence" panel when the backend abstains.
   - Show the backend reason and suggested questions.
   - Keep nearest evidence visible so users can understand what the local index found.

## User Experience

For a selected resume, answerable questions should still work:

- "What technical skills are mentioned?"
- "What projects are listed in this resume?"
- "What education background does Nigel have?"

Hard cases should no longer hallucinate answers:

- "How does invoice payment work?" should say the selected resume does not contain enough evidence.
- "What language is this document written in?" should say this local extractive mode does not perform language detection yet.

## Architecture

The backend keeps the same retrieval pipeline:

1. Embed query locally.
2. Search pgvector.
3. Rerank hits with local signals.
4. Assess evidence quality.
5. Build an extractive answer only if the quality gate allows it.

The answer quality model lives in retrieval code and is serialized as part of `SearchResponse`. The frontend consumes this model directly and does not duplicate gate logic.

## Non-Goals

- No paid APIs.
- No OpenAI API usage.
- No Ollama generation yet.
- No model training in this phase.
- No OCR or FUNSD fine-tuning in this phase.

## Success Criteria

- Unrelated selected-document questions return `answer: null` with `quality.status = "insufficient_evidence"`.
- Accepted answers include `quality.status = "answerable"` and an understandable confidence label.
- The UI displays confidence for answers and a no-answer panel for abstentions.
- Suggested questions are visible when the system abstains.
- Backend and frontend tests pass.
