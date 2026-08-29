# Document-Scoped Search And Answer Quality Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add document-scoped search to the UI and harden extractive answers so cited answers come from relevant document sections.

**Architecture:** Reuse the existing FastAPI search request, pgvector retrieval, local reranker, extractive answer builder, and Next.js search page. Add reusable query/section focus helpers in retrieval, then use those helpers in answer selection and frontend document-scope controls.

**Tech Stack:** FastAPI, SQLAlchemy, PostgreSQL/pgvector, sentence-transformers, Next.js, React, TypeScript, Tailwind CSS, Vitest, pytest.

**Spec:** `docs/superpowers/specs/2026-08-29-document-scoped-answer-quality-design.md`

## Global Constraints

- Local-only: no OpenAI API or paid hosted AI services.
- No model training in this phase.
- Keep answers extractive and grounded in returned citations.
- Reuse the existing `/search` request field `document_id`; do not create a duplicate endpoint.
- Every behavior change gets a failing test before production code.
- Leave unrelated local changes, including generated Next.js files in other worktrees, untouched.

---

### Task 1: Backend Answer Quality Hardening

**Files:**
- Modify: `apps/api/app/retrieval/reranker.py`
- Modify: `apps/api/app/retrieval/answers.py`
- Test: `apps/api/tests/retrieval/test_reranker.py`
- Test: `apps/api/tests/retrieval/test_answers.py`

**Interfaces:**
- Produces: `infer_section_intents(section_heading: str | None) -> set[str]`
- Extends: `infer_query_intents(query: str) -> set[str]`
- Keeps: `build_extractive_answer(query: str, hits: Sequence[SearchHit]) -> ExtractiveAnswer | None`

- [ ] **Step 1: Write failing answer-selection tests**

Add tests equivalent to:

```python
def test_build_extractive_answer_prefers_matching_sections_and_does_not_force_three_citations():
    skill_hit = make_hit(chunk_id="skill", text="Technical Skills Python SQL PyTorch.", page_number=1, section_heading="TECHNICAL SKILLS")
    education_hit = make_hit(chunk_id="education", text="EDUCATION B.Eng. Artificial Intelligence.", page_number=1, section_heading="EDUCATION")
    experience_hit = make_hit(chunk_id="experience", text="EXPERIENCE Mathematics Tutor.", page_number=1, section_heading="EXPERIENCE")

    answer = build_extractive_answer("What technical skills are mentioned?", [skill_hit, education_hit, experience_hit])

    assert answer is not None
    assert [citation.chunk_id for citation in answer.citations] == ["skill"]
    assert "EDUCATION" not in answer.summary
    assert "EXPERIENCE" not in answer.summary
```

- [ ] **Step 2: Write failing programming-language and project-focus tests**

Add tests equivalent to:

```python
def test_build_extractive_answer_uses_programming_language_section_for_language_queries():
    project_hit = make_hit(chunk_id="project", text="PROJECTS Thesis medical segmentation.", page_number=1, section_heading="PROJECTS")
    language_hit = make_hit(chunk_id="languages", text="Programming Languages Python, C++, C language.", page_number=1, section_heading="PROGRAMMING LANGUAGES")

    answer = build_extractive_answer("What programming languages does this candidate know?", [project_hit, language_hit])

    assert answer is not None
    assert [citation.chunk_id for citation in answer.citations] == ["languages"]
    assert "Python" in answer.summary
    assert "PROJECTS" not in answer.summary
```

- [ ] **Step 3: Write failing reranker intent tests**

Add tests equivalent to:

```python
def test_infer_query_intents_understands_programming_language_and_tools_queries():
    assert infer_query_intents("What programming languages does this candidate know?") == {"programming_language", "skill"}
    assert infer_query_intents("Which tools and frameworks are listed?") == {"framework", "skill", "tool"}
```

- [ ] **Step 4: Run focused tests and verify RED**

Run:

```powershell
$env:DOCINTEL_TEST_DATABASE_URL='postgresql+psycopg://docintel:docintel@localhost:5432/docintel_test'
C:\Users\nigel\Documents\Codex\.venvs\docintel-api\Scripts\python.exe -m pytest tests/retrieval/test_answers.py tests/retrieval/test_reranker.py
```

Expected: the new tests fail because current answers use the first three hits and the reranker does not recognize programming-language/tool/framework section families.

- [ ] **Step 5: Implement local focus helpers**

Update `apps/api/app/retrieval/reranker.py` so it includes:

```python
def infer_section_intents(section_heading: str | None) -> set[str]:
    ...
```

The helper must map `TECHNICAL SKILLS`, `CORE SKILLS`, `TOOLS & PLATFORMS`, `FRAMEWORKS & LIBRARIES`, and `PROGRAMMING LANGUAGES` into skill-family intents, while mapping `PROJECTS`, `KEY PROJECTS`, `EDUCATION`, and `EXPERIENCE` to their matching families.

- [ ] **Step 6: Select answer citations by matching section family**

Update `apps/api/app/retrieval/answers.py` so `build_extractive_answer` first looks for hits whose section intents overlap query intents. If any matching-section hits exist, use only those hits up to the existing answer citation cap. If none exist, fall back to relevant top hits using keyword overlap and current scores.

- [ ] **Step 7: Run focused tests and verify GREEN**

Run the same focused pytest command.

Expected: all selected tests pass.

- [ ] **Step 8: Commit**

```powershell
git add apps/api/app/retrieval/reranker.py apps/api/app/retrieval/answers.py apps/api/tests/retrieval/test_reranker.py apps/api/tests/retrieval/test_answers.py
git commit -m "feat: harden extractive answer quality"
```

### Task 2: Frontend Document-Scoped Search

**Files:**
- Modify: `apps/web/app/search/page.tsx`
- Modify: `apps/web/lib/api.ts`
- Test: `apps/web/tests/search-page.test.tsx`
- Test: `apps/web/tests/api-client.test.ts`

**Interfaces:**
- Consumes: `getDocuments() -> Promise<DocumentSummary[]>`
- Consumes: `searchDocuments(query: string, topK?: number, documentId?: string) -> Promise<SearchResponse>`
- UI control label: `Search scope`
- Default option label: `All documents`

- [ ] **Step 1: Write failing API client test**

Add a test equivalent to:

```typescript
it("posts search requests scoped to a selected document", async () => {
  const fetchMock = vi.fn().mockResolvedValue({
    ok: true,
    json: async () => ({ query: "invoice", hits: [], answer: null }),
  });
  vi.stubGlobal("fetch", fetchMock);

  await searchDocuments("invoice", 5, "doc-1");

  expect(JSON.parse(String(fetchMock.mock.calls[0][1]?.body))).toEqual({
    query: "invoice",
    top_k: 5,
    document_id: "doc-1",
  });
});
```

- [ ] **Step 2: Write failing Search page test**

Add a test equivalent to:

```typescript
it("loads documents and searches within the selected document", async () => {
  apiMocks.getDocuments.mockResolvedValue([{ id: "doc-1", filename: "resume.pdf", mime_type: "application/pdf", status: "indexed" }]);
  apiMocks.searchDocuments.mockResolvedValue(successfulResponse);

  render(<SearchPage />);

  fireEvent.change(await screen.findByRole("combobox", { name: "Search scope" }), { target: { value: "doc-1" } });
  fireEvent.change(screen.getByRole("textbox", { name: "Search query" }), { target: { value: "technical skills" } });
  fireEvent.submit(screen.getByRole("textbox", { name: "Search query" }).closest("form")!);

  await waitFor(() => expect(apiMocks.searchDocuments).toHaveBeenCalledWith("technical skills", 5, "doc-1"));
});
```

- [ ] **Step 3: Run focused tests and verify RED**

Run:

```powershell
npm test -- api-client.test.ts search-page.test.tsx
```

Expected: the API client test may pass if the optional argument is already wired, and the Search page test fails because the page does not load documents or render a scope selector.

- [ ] **Step 4: Implement document scope UI**

Update `apps/web/app/search/page.tsx` to fetch documents with `getDocuments()`, render a `Search scope` select with `All documents`, track `selectedDocumentId`, and pass `selectedDocumentId || undefined` to `searchDocuments`.

- [ ] **Step 5: Run focused tests and verify GREEN**

Run the same focused Vitest command.

Expected: all selected tests pass.

- [ ] **Step 6: Commit**

```powershell
git add apps/web/app/search/page.tsx apps/web/lib/api.ts apps/web/tests/search-page.test.tsx apps/web/tests/api-client.test.ts
git commit -m "feat: add document-scoped search UI"
```

### Task 3: Verification, Review, And Push

**Files:**
- No production source changes unless verification reveals a tested defect.

**Interfaces:**
- Produces: pushed branch `feature/document-scoped-answer-quality`.

- [ ] **Step 1: Run full backend tests**

```powershell
$env:DOCINTEL_TEST_DATABASE_URL='postgresql+psycopg://docintel:docintel@localhost:5432/docintel_test'
C:\Users\nigel\Documents\Codex\.venvs\docintel-api\Scripts\python.exe -m pytest
```

- [ ] **Step 2: Run full frontend tests**

```powershell
npm test
```

- [ ] **Step 3: Run frontend lint**

```powershell
npm run lint
```

- [ ] **Step 4: Run frontend build**

```powershell
npm run build
```

- [ ] **Step 5: Review the branch diff**

Review:

```powershell
git diff --stat origin/main...HEAD
git diff --check
```

- [ ] **Step 6: Push branch**

```powershell
git push -u origin feature/document-scoped-answer-quality
```

- [ ] **Step 7: Provide PR URL**

If GitHub CLI permissions are unavailable, provide:

```text
https://github.com/nigelcheong1/docintel-ai/compare/main...feature/document-scoped-answer-quality?expand=1
```
