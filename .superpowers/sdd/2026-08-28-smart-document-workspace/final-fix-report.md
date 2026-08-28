# Final Fix Report

## Findings

1. Post-commit file cleanup failures: fixed. `delete_document` now reads the stored file for rollback, flushes the database delete, removes the file before the durable commit, rolls back on removal failure, and restores the original bytes if the database commit fails. The API returns `503` when file removal fails and retains the document row.
2. Failed reindex destroys the prior index: fixed. Reindex clear and rebuild now run in one transaction. Parser, embedding, or indexing failures roll back the attempt, preserve the prior pages/chunks/embeddings and indexed status, and return an HTTP action error instead of a successful `FAILED` document response.
3. Document action locking and labels: fixed. Pending action state now includes document id and action type. All row controls visibly disable during the global action lock, while only the active control shows `Reindexing...` or `Deleting...`.
4. Overlapping searches publish stale results: fixed. Search submissions use monotonically increasing request identity. Only the latest request may publish results, errors, or loading completion.
5. Image reindex control: fixed. Reindex is rendered only for `application/pdf` documents.
6. Permanent deletion confirmation: fixed. Delete actions require a lightweight browser confirmation before the request begins.
7. Query-independent extractive answers: fixed. The answer builder deterministically selects the sentence with the strongest query-term overlap from each selected hit, with stable first-sentence tie breaking and the existing character limit.

No reviewed minor findings were deferred.

## TDD Evidence

- File removal failure RED: `python -m pytest tests/documents/test_service.py::test_delete_document_keeps_database_record_when_file_removal_fails tests/documents/test_router.py::test_delete_document_endpoint_surfaces_file_removal_failure -q` -> `2 failed`; service did not raise and API returned `204`.
- File removal failure GREEN: `python -m pytest tests/documents/test_service.py -k delete_document tests/documents/test_router.py -k delete_document -q` -> `5 passed, 14 deselected`.
- Failed reindex RED: `python -m pytest tests/documents/test_service.py::test_reindex_document_preserves_prior_index_when_embedding_fails tests/documents/test_router.py::test_reindex_document_endpoint_surfaces_failure_and_preserves_prior_index -q` -> `2 failed`; service did not raise and API returned `200`.
- Failed reindex GREEN: `python -m pytest tests/documents/test_service.py tests/documents/test_router.py -q` -> `21 passed`.
- Document action state, PDF gating, and confirmation RED: `npm test -- document-list.test.tsx` -> `4 failed, 6 passed`; other rows remained enabled, delete showed the wrong state, images exposed reindex, and confirmation was not called.
- Document action state, PDF gating, and confirmation GREEN: `npm test -- document-list.test.tsx documents-page.test.tsx` -> `2 files passed, 13 tests passed`.
- Overlapping search RED: `npm test -- search-page.test.tsx` -> `1 failed, 1 passed`; the older response appeared on screen.
- Overlapping search GREEN: `npm test -- search-page.test.tsx` -> `1 file passed, 2 tests passed`.
- Query-focused answer RED: `python -m pytest tests/retrieval/test_answers.py::test_build_extractive_answer_selects_the_sentence_matching_query_terms -q` -> `1 failed`; the full unrelated chunk was returned.
- Query-focused answer GREEN: `python -m pytest tests/retrieval/test_answers.py -q` -> `3 passed`.

## Verification

- Backend focused: `DOCINTEL_TEST_DATABASE_URL=postgresql+psycopg://docintel:docintel@localhost:5432/docintel_test python -m pytest tests/documents/test_service.py tests/documents/test_router.py tests/retrieval/test_answers.py tests/retrieval/test_search_api.py -q` -> `27 passed in 2.69s`.
- Frontend focused: `npm test -- document-list.test.tsx documents-page.test.tsx search-page.test.tsx search-results.test.tsx` -> `4 files passed, 20 tests passed`.
- Full backend: `DOCINTEL_TEST_DATABASE_URL=postgresql+psycopg://docintel:docintel@localhost:5432/docintel_test python -m pytest` -> `69 passed in 2.97s`.
- Full frontend tests: `npm test` -> `10 files passed, 35 tests passed`.
- Frontend lint: `npm run lint` -> exit `0`, no findings.
- Frontend build: `npm run build` -> exit `0`; Next.js production build compiled, TypeScript completed, and 6 static pages generated.
- Diff validation: `git diff --check` -> exit `0`.

## Files Changed

- `apps/api/app/documents/service.py`
- `apps/api/app/retrieval/answers.py`
- `apps/api/tests/documents/test_router.py`
- `apps/api/tests/documents/test_service.py`
- `apps/api/tests/retrieval/test_answers.py`
- `apps/web/app/search/page.tsx`
- `apps/web/components/document-list.tsx`
- `apps/web/tests/document-list.test.tsx`
- `apps/web/tests/documents-page.test.tsx`
- `apps/web/tests/search-page.test.tsx`
- `.superpowers/sdd/2026-08-28-smart-document-workspace/final-fix-report.md`

## Concerns

- Accepted controller trade-off: a process crash after file removal and before database commit can leave a document row pointing at a missing local file.
- Commit-failure restoration keeps the stored file bytes in memory during deletion. This is bounded by the existing upload-size limit and avoids a post-commit temporary-file cleanup path.
